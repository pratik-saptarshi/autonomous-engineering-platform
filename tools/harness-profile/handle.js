'use strict';

// Opt-in capture handler for opencode 2.3. This is the logic the thin ESM
// plugin subscribes to; nothing here runs unless AEP_HARNESS_PROFILE is set.
//
// Event ordering (Phase 0): a step's tokens arrive at `session.step.ended`,
// after every call of that step has completed. Records are therefore buffered
// per assistant message and built/flushed at that step's end. Building them at
// the completion event would lose `context_tokens` (the translator's header
// documents the same contract).
//
// Parentage: `session.created` never fired in Phase 0, so a child is bound
// through `ctx.session.get().parentID` whenever the API is available. (The
// 2.3 spawn response does carry a session id in `metadata`, and some hosts emit
// `session.created`; both are recorded, but the API is the primary path and the
// live smoke asserts which one actually bound.) A lookup miss is *not*
// remembered: the session's events are deferred and the lookup is retried on
// each following event. Only a real answer (a parent id, or a session object
// with no parent) is cached.

const fs = require('fs');
const path = require('path');

const translate = require('./translate.js');
const hp = require('../../reference/harness-profiler/plugin/libexec/hp.js');

const ENABLE = 'AEP_HARNESS_PROFILE';
const DIR = 'AEP_HARNESS_PROFILE_DIR';
const DEBUG = 'AEP_HARNESS_PROFILE_DEBUG';

// A session whose lookup keeps missing holds its events, bounded so a broken
// API cannot grow the capture without limit. Nothing is written for it.
const MAX_DEFERRED = 64;

// The spawning tool names, before the translator's mapping to `Agent`.
const SPAWN_TOOLS = new Set(['subagent', 'task', 'Agent', 'Task']);

const SPAWN_RESPONSE_KEYS = [
  'sessionID',
  'sessionId',
  'session_id',
  'childSessionID',
  'childSessionId',
  'child_session_id',
  'agentID',
  'agentId',
  'agent_id',
];

function truthy(value) {
  if (typeof value !== 'string') return Boolean(value);
  return !['', '0', 'false', 'off', 'no'].includes(value.trim().toLowerCase());
}

function isEnabled(env) {
  return truthy((env || {})[ENABLE]);
}

function isDebug(env) {
  return truthy((env || {})[DEBUG]);
}

// ---------- git integration ----------

function gitRoot(start) {
  let dir = path.resolve(start);
  for (;;) {
    if (fs.existsSync(path.join(dir, '.git'))) return dir;
    const up = path.dirname(dir);
    if (up === dir) return null;
    dir = up;
  }
}

// A worktree's `.git` is a file pointing at its own git dir; worktrees share
// the main repository's info/exclude through `commondir`.
function commonGitDir(root) {
  const dotGit = path.join(root, '.git');
  let dir;
  try {
    dir = fs.statSync(dotGit).isDirectory()
      ? dotGit
      : path.resolve(root, fs.readFileSync(dotGit, 'utf8').match(/^gitdir:\s*(.+)$/m)[1].trim());
  } catch {
    return null;
  }
  const pointer = path.join(dir, 'commondir');
  return fs.existsSync(pointer) ? path.resolve(dir, fs.readFileSync(pointer, 'utf8').trim()) : dir;
}

// Unconditional and idempotent: the pin only writes this when it creates the
// trace directory, so a pre-existing `.harness-profile/` would stay visible to
// git without this path.
function excludeTraceDir(cwd) {
  const root = gitRoot(cwd);
  if (!root) return false;
  const dir = commonGitDir(root);
  if (!dir) return false;
  const exclude = path.join(dir, 'info', 'exclude');
  const line = `${translate.TRACE_DIR}/`;
  const current = fs.existsSync(exclude) ? fs.readFileSync(exclude, 'utf8') : '';
  if (current.split(/\r?\n/).includes(line)) return false;
  fs.mkdirSync(path.dirname(exclude), { recursive: true });
  fs.appendFileSync(exclude, `${current && !current.endsWith('\n') ? '\n' : ''}${line}\n`);
  return true;
}

// ---------- state ----------

function createState(options = {}) {
  const env = options.env || process.env;
  const cwd = path.resolve(options.cwd || process.cwd());
  const state = {
    cwd,
    env,
    sessionGet: typeof options.sessionGet === 'function' ? options.sessionGet : undefined,
    trees: new Map(), // rootSessionId -> tree
    sessionRoot: new Map(), // sessionId -> rootSessionId
    parents: new Map(), // sessionId -> parentId | null (a definitive "no parent")
    via: new Map(), // sessionId -> parentage source
    resolving: new Set(),
    deferred: new Map(), // sessionId -> { events }
    excluded: false,
    gitRoot: options.gitRoot !== undefined ? options.gitRoot : gitRoot(cwd),
    errors: [],
  };
  if (options.rootSessionId) createRootTree(state, options.rootSessionId);
  return state;
}

function createRootTree(state, id) {
  let tree = state.trees.get(id);
  if (!tree) {
    tree = {
      rootSessionId: id,
      t: translate.createState(id, { cwd: state.cwd, parents: state.parents }),
      pending: new Map(), // (session, assistantMessageID) -> terminal events not yet built
      parentage: new Map(), // child -> { parent, via }
      spawnResponses: new Map(), // spawn call -> child session id | null
      tieBreaks: [], // concurrent-spawn bindings, for the debug sidecar
    };
    state.trees.set(id, tree);
  }
  state.sessionRoot.set(id, id);
  return tree;
}

// Consult the session API only while a session's parent is unknown. A miss
// (undefined, a throw, or a malformed answer) returns undefined and is not
// cached: the caller defers and asks again on the next event.
async function lookupParent(state, id) {
  if (state.parents.has(id)) return state.parents.get(id);
  if (!state.sessionGet) return null; // no API at all: treat as a root
  let session;
  try {
    session = await state.sessionGet(id);
  } catch (error) {
    state.errors.push(error);
    return undefined;
  }
  const info = session && session.data && typeof session.data === 'object' && !session.parentID ? session.data : session;
  if (!info || typeof info !== 'object') return undefined;
  // An error envelope is a miss, not a session with no parent. Only a real
  // session object may be cached as a root.
  if (typeof info.id !== 'string' || !info.id) return undefined;
  const parent = typeof info.parentID === 'string' && info.parentID && info.parentID !== id ? info.parentID : null;
  state.parents.set(id, parent);
  state.via.set(id, 'session.get');
  return parent;
}

async function ensureTree(state, id) {
  if (!id) return null;
  if (state.sessionRoot.has(id)) return state.trees.get(state.sessionRoot.get(id)) || null;
  if (state.resolving.has(id)) return null;
  state.resolving.add(id);
  try {
    let parent;
    if (state.parents.has(id)) parent = state.parents.get(id);
    else parent = await lookupParent(state, id);
    if (parent === undefined) return null;
    if (parent === null || parent === id) return createRootTree(state, id);

    const parentTree = await ensureTree(state, parent);
    if (!parentTree) return null;
    state.parents.set(id, parent);
    state.sessionRoot.set(id, parentTree.rootSessionId);
    attachChild(state, parentTree, id, parent, state.via.get(id) || 'session.get');
    return parentTree;
  } finally {
    state.resolving.delete(id);
  }
}

// Bind a child to its tree. `translate.noteChild` handles the unambiguous
// one-open-spawn case. When several spawning calls are open for the same
// parent, the translator deliberately refuses; this handler then applies the
// deterministic tie-break: the first child session whose parentage is learned
// takes the earliest-started still-open call (FIFO, the order openSpawns keeps).
// There is no spawn-call -> child API in opencode 2.3, so an ordering rule is
// the only deterministic choice; children that emit their first event out of
// order can still be misattributed.
function attachChild(state, tree, child, parent, via) {
  state.parents.set(child, parent);
  state.sessionRoot.set(child, tree.rootSessionId);
  const t = tree.t;
  translate.noteChild(t, child, parent);
  if (!t.claimed.has(child)) {
    const open = t.openSpawns.get(parent) || [];
    const candidate = open.find((callId) => !t.links.has(callId));
    if (candidate) {
      t.links.set(candidate, child);
      t.claimed.add(child);
      tree.tieBreaks.push({ spawn: candidate, child, parent });
    }
  }
  for (const [callId, linked] of t.links) {
    if (linked !== child) continue;
    pruneOpen(t, callId);
    tree.parentage.set(child, { parent, via });
    return;
  }
  tree.parentage.set(child, { parent, via, unbound: true });
}

// A bound spawning call is no longer open; leaving it in the list would let it
// be rebound to a later child.
function pruneOpen(t, callId) {
  for (const open of t.openSpawns.values()) {
    const at = open.indexOf(callId);
    if (at !== -1) open.splice(at, 1);
  }
}

// ---------- trace writing ----------

function traceDirOf(state) {
  const override = (state.env || {})[DIR];
  if (typeof override === 'string' && override.trim()) return path.resolve(state.cwd, override.trim());
  return path.join(gitRoot(state.cwd) || state.cwd, translate.TRACE_DIR);
}

function ensureExclusion(state) {
  if (state.excluded) return;
  state.excluded = true;
  try {
    excludeTraceDir(state.cwd);
  } catch (error) {
    state.errors.push(error);
  }
}

function writeOne(state, tree, record) {
  if (!record) return null;
  ensureExclusion(state);
  const dir = traceDirOf(state);
  const file = path.join(dir, `${String(tree.rootSessionId).replace(/[^\w.-]/g, '_')}.jsonl`);
  try {
    // Create the file 0600 before the append, so there is no window where a
    // new trace exists with the process umask (the pin's writer uses append).
    fs.mkdirSync(dir, { recursive: true });
    fs.closeSync(fs.openSync(file, 'a', 0o600));
  } catch (error) {
    state.errors.push(error);
  }
  const written = translate.writeRecord(dir, record, tree.rootSessionId);
  if (written) {
    try {
      // Narrow a file that already existed with a wider mode too.
      fs.chmodSync(written, 0o600);
    } catch (error) {
      state.errors.push(error);
    }
  }
  return written;
}

function writeDebugSidecar(state, tree) {
  if (!isDebug(state.env)) return;
  try {
    const dir = traceDirOf(state);
    const body = {
      root: tree.rootSessionId,
      parentage: [...tree.parentage].map(([child, info]) => ({ child, ...info })),
      spawnResponses: [...tree.spawnResponses].map(([call, child]) => ({ call, sessionID: child })),
      tieBreaks: tree.tieBreaks,
    };
    const file = path.join(dir, `${String(tree.rootSessionId).replace(/[^\w.-]/g, '_')}.parentage.json`);
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(file, `${JSON.stringify(body, null, 2)}\n`, { mode: 0o600 });
    fs.chmodSync(file, 0o600);
  } catch (error) {
    state.errors.push(error);
  }
}

// ---------- event dispatch ----------

function inDirectory(state, event) {
  const dir = event.location && event.location.directory;
  if (typeof dir !== 'string' || !dir) return true;
  const resolved = path.resolve(dir);
  if (resolved === state.cwd) return true;
  // A session in a subdirectory of the same repository belongs here; a session
  // in another location does not (Phase 0 saw other locations' events).
  if (!state.gitRoot) {
    return resolved.startsWith(`${state.cwd}${path.sep}`) || state.cwd.startsWith(`${resolved}${path.sep}`);
  }
  const other = gitRoot(resolved);
  return Boolean(other && other === state.gitRoot);
}

function spawnResponseChild(data) {
  const metadata = data && data.metadata;
  if (!metadata || typeof metadata !== 'object') return undefined;
  const candidates = [];
  const consider = (value) => {
    if (typeof value === 'string' && /^ses_/.test(value)) candidates.push(value);
  };
  for (const key of SPAWN_RESPONSE_KEYS) consider(metadata[key]);
  for (const value of Object.values(metadata)) {
    if (!value || typeof value !== 'object') continue;
    for (const key of SPAWN_RESPONSE_KEYS) consider(value[key]);
  }
  return candidates.find((id) => id !== data.sessionID);
}

function bindSpawnResponse(state, tree, callId, childId) {
  tree.spawnResponses.set(callId, childId || null);
  if (!childId) return;
  const call = tree.t.calls.get(callId);
  if (!call || !call.sessionID || childId === call.sessionID) return;
  if (tree.t.claimed.has(childId)) return;
  // The child's events already created a tree of their own; re-rooting would
  // strand its records in another file. The API path is what prevents that.
  const existingRoot = state.sessionRoot.get(childId);
  if (existingRoot && existingRoot === childId && state.trees.has(childId)) return;

  state.parents.set(childId, call.sessionID);
  state.via.set(childId, 'spawn-response');
  state.sessionRoot.set(childId, tree.rootSessionId);
  tree.t.parents.set(childId, call.sessionID);
  tree.t.links.set(callId, childId);
  tree.t.claimed.add(childId);
  pruneOpen(tree.t, callId);
  tree.parentage.set(childId, { parent: call.sessionID, via: 'spawn-response' });
}

function buffer(tree, event) {
  const key = pendingKey(event);
  if (!tree.pending.has(key)) tree.pending.set(key, []);
  tree.pending.get(key).push(event);
}

// A call is pending under (session, assistant message): a root turn-end must
// never flush a still-running child's calls, because the child's step tokens
// arrive later.
function pendingKey(event) {
  const data = event.data || {};
  return `${data.sessionID || ''}\u0000${data.assistantMessageID || ''}`;
}

function flush(state, tree, key) {
  const events = tree.pending.get(key);
  if (!events) return [];
  tree.pending.delete(key);
  const records = [];
  for (const event of events) {
    const record = translate.buildRecord(event, tree.t);
    if (record) {
      writeOne(state, tree, record);
      records.push(record);
    }
  }
  return records;
}

// The ending session's calls only; other sessions in the same tree are still
// running and their steps have not reported tokens yet.
function flushSession(state, tree, sessionId) {
  const prefix = `${sessionId}\u0000`;
  const records = [];
  for (const key of [...tree.pending.keys()]) {
    if (key.startsWith(prefix)) records.push(...flush(state, tree, key));
  }
  return records;
}

function buildChildStopRecord(state, tree, childSessionId, at) {
  const spend = tree.t.spend.get(childSessionId);
  if (!spend) return null;
  const payload = {
    hook_event_name: 'SubagentStop',
    session_id: childSessionId,
    agent_id: childSessionId,
    cwd: state.cwd,
  };
  const record = hp.buildEventRecord(payload, translate.HARNESS, new Date(at || tree.t.lastAt || Date.now()));
  record.spend = { ...spend };
  return record;
}

async function dispatch(state, event, tree) {
  const data = event.data || {};
  const t = tree.t;
  const records = [];

  if (event.type === 'session.tool.success' || event.type === 'session.tool.failed') {
    translate.ingest(event, t);
    const call = data.id ? t.calls.get(data.id) : undefined;
    if (event.type === 'session.tool.success' && call && SPAWN_TOOLS.has(call.name)) {
      bindSpawnResponse(state, tree, data.id, spawnResponseChild(data));
    }
    buffer(tree, event);
    // Out-of-order safety: if the step already ended, build now rather than wait.
    if (t.steps.has(data.assistantMessageID)) records.push(...flush(state, tree, pendingKey(event)));
    return records;
  }

  if (event.type === 'session.step.ended') {
    translate.ingest(event, t);
    records.push(...flush(state, tree, pendingKey(event)));
    return records;
  }

  if (
    event.type === 'session.execution.succeeded' ||
    event.type === 'session.execution.failed' ||
    event.type === 'session.execution.interrupted'
  ) {
    translate.ingest(event, t);
    // A tool whose step never ended still produced a call; keep it rather than
    // losing the record. Its context_tokens are simply absent. Only this
    // session's calls: another session in the same tree may still be running.
    records.push(...flushSession(state, tree, data.sessionID));
    if (data.sessionID === tree.rootSessionId) {
      // A root execution end is a turn, not the session: a background subagent
      // wakes the root for another turn. Emit the root spend each time; the
      // pin's `subagentStops` keeps the last stop per agent, so the final turn
      // wins with the complete total (hp.js:483-490).
      const stop = translate.buildStopRecord(t, new Date(event.created || t.lastAt || Date.now()));
      writeOne(state, tree, stop);
      records.push(stop);
      writeDebugSidecar(state, tree);
    } else {
      // The spawn record was written when the parent's step ended, before the
      // child's steps existed, so it cannot carry child_spend. The pin's own
      // mechanism for a background subagent is a SubagentStop keyed by the
      // child context; `contextSpend` reads that (hp.js:318-332).
      const stop = buildChildStopRecord(state, tree, data.sessionID, event.created);
      if (stop) {
        writeOne(state, tree, stop);
        records.push(stop);
      }
    }
    return records;
  }

  translate.ingest(event, t);
  return records;
}

async function handleEvent(event, state) {
  if (!isEnabled(state.env)) return null;
  if (!event || typeof event !== 'object' || !event.type) return null;
  try {
    ensureExclusion(state);
    if (!inDirectory(state, event)) return null;

    const data = event.data || {};
    const sessionId = typeof data.sessionID === 'string' ? data.sessionID : undefined;
    if (!sessionId) return null;

    // Use the event only when there is no session API. The API is the
    // authoritative source and the one production always has; preferring it
    // means the live smoke proves the path that actually runs
    // (`ctx.session.get().parentID`), not an event some hosts do not emit.
    if (event.type === 'session.created' && !state.sessionGet && typeof data.parentID === 'string' && data.parentID && data.parentID !== sessionId) {
      state.parents.set(sessionId, data.parentID);
      state.via.set(sessionId, 'session.created');
    }

    const waiting = state.deferred.get(sessionId);
    if (waiting) {
      if (waiting.events.length < MAX_DEFERRED) waiting.events.push(event);
      const tree = await ensureTree(state, sessionId);
      if (!tree) return null;
      state.deferred.delete(sessionId);
      const records = [];
      for (const deferred of waiting.events) records.push(...(await dispatch(state, deferred, tree)));
      return records.length ? records : null;
    }

    const tree = await ensureTree(state, sessionId);
    if (!tree) {
      state.deferred.set(sessionId, { events: [event] });
      return null;
    }
    const records = await dispatch(state, event, tree);
    return records.length ? records : null;
  } catch (error) {
    // Capture must never fail a session. The error is kept for tests/debug.
    state.errors.push(error);
    return null;
  }
}

// ---------- evidence ----------

function parentageOf(state, sessionId) {
  for (const tree of state.trees.values()) {
    if (tree.parentage.has(sessionId)) return tree.parentage.get(sessionId);
  }
  return undefined;
}

function spawnResponseOf(state, callId) {
  for (const tree of state.trees.values()) {
    if (tree.spawnResponses.has(callId)) return tree.spawnResponses.get(callId);
  }
  return undefined;
}

module.exports = {
  ENABLE,
  DIR,
  DEBUG,
  createState,
  handleEvent,
  parentageOf,
  spawnResponseOf,
  traceDirOf,
  excludeTraceDir,
};
