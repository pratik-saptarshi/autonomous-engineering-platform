'use strict';

const { spawnSync } = require('node:child_process');

// Opt-in capture handler for opencode 2.3. This is the logic the thin ESM
// plugin subscribes to; nothing here runs unless AEP_HARNESS_PROFILE is set.
//
// Event ordering (Phase 0): a step's tokens arrive at `session.step.ended`,
// after every call of that step has completed. Records are therefore buffered
// per assistant message and built/flushed at that step's end. Building them at
// the completion event would lose `context_tokens` (the translator's header
// documents the same contract).
//
// Parentage precedence, highest first:
//
//   1. The spawn response — `session.tool.success.metadata.sessionID`, the
//      authoritative call -> child mapping opencode 2.3 returns (it sends
//      `{sessionID, background}`). It wins whenever it arrives, even after an
//      earlier binding: a `session.get`/FIFO link for that open spawn is
//      reconciled in place — the call is re-pointed, the displaced child is
//      released, and the record built later carries the corrected
//      `child_agent_id` and `child_spend`. Arrival order never decides.
//   2. `ctx.session.get().parentID` — the authoritative parent of a child
//      session, and what binds the child while a response is still in flight.
//      A lookup miss is *not* remembered: the session's events are deferred and
//      the lookup is retried on each following event. Only a real answer (a
//      parent id, or a session object with no parent) is cached.
//   3. FIFO among still-open spawns for the same parent — a provisional
//      fallback for out-of-order observation when several spawns are open. It
//      is never final: either call's response supersedes it.
//
// `session.created` is a host-dependent extra, honored only when there is no
// session API at all, so it can never outrank the API path.
//
// Hygiene: the trace directory is excluded through the repository's own
// `info/exclude` on the first event, unconditionally (the pin skips it when the
// directory already exists), and the entry is read back before any record is
// written. The directory is pruned at the same moment — 14 days or 32 MiB by
// default, older-files-first, limited to this handler's own `ses_*` files.
// Without a usable repository above the working directory and without an
// explicit `AEP_HARNESS_PROFILE_DIR`, capture writes nothing: a trace that
// cannot be shown to be excluded from git (no repository, a malformed `.git`, an
// unwritable or unverified `info/exclude`) is not written at all, and the
// refusal reason is recorded once in `state.warnings` instead of failing the
// session. The committed `.gitignore` entry is the second layer: it covers a
// fresh clone and a runtime write that cannot land. An explicit
// `AEP_HARNESS_PROFILE_DIR` is honored outside every repository, but when its
// final path (symlinks resolved) is inside a work tree it must be named by that
// repository's `.gitignore` or common `info/exclude`; otherwise the trace would
// be committable and capture refuses it (the reason and both remedies are
// recorded in `state.warnings`). A symlink is judged by its target, so a link
// outside the repository that points into it is refused like any in-repo path,
// and a link whose target is outside is honored.

const fs = require('fs');
const path = require('path');

const translate = require('./translate.js');
const hp = require('../../reference/harness-profiler/plugin/libexec/hp.js');

const ENABLE = 'AEP_HARNESS_PROFILE';
const DIR = 'AEP_HARNESS_PROFILE_DIR';
const DEBUG = 'AEP_HARNESS_PROFILE_DEBUG';
const RETENTION = 'AEP_HARNESS_PROFILE_RETENTION_DAYS';
const MAX_BYTES = 'AEP_HARNESS_PROFILE_MAX_BYTES';

// A session whose lookup keeps missing holds its events, bounded so a broken
// API cannot grow the capture without limit. Nothing is written for it.
const MAX_DEFERRED = 64;

// Growth is bounded on two axes. Age is the primary one: the evaluation
// measured ~430 B per record and ~1 MB/day across four lanes, so 14 days is
// ~14 MB steady state. The byte ceiling caps what accumulates between starts
// (a burst of sessions, duplicated writers) and is set at roughly twice that
// steady state; the oldest trace files go first. Both are env-overridable and
// `0` disables that bound.
const RETENTION_DAYS = 14;
const MAX_TRACE_BYTES = 32 * 1024 * 1024;
const DAY_MS = 24 * 60 * 60 * 1000;

// Trace files this handler owns: one JSONL per root session plus the debug
// sidecar, both named from a root session id, which always starts with `ses_`.
// Anything else in the directory (an operator's `notes.jsonl`, another tool's
// `*-traces.jsonl`, a subdirectory) is never pruned, which matters because an
// explicit `AEP_HARNESS_PROFILE_DIR` may be shared.
const TRACE_FILE = /^ses_[\w.-]+\.(?:jsonl|parentage\.json)$/;

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

// A destination must be judged by the path it finally lands on: a symlink whose
// target is inside the work tree would otherwise be judged by its own (outside)
// path and pass as safe. `fs.realpathSync` resolves every existing component, so
// a directory that does not exist yet is resolved through its nearest existing
// ancestor and the missing tail is re-appended. An unresolvable path (a symlink
// loop, an unreadable component) returns null, and the caller fails closed
// rather than guessing which side of the work tree it is on.
function resolvedDestination(dir) {
  let current = path.resolve(dir);
  const missing = [];
  for (;;) {
    try {
      const real = fs.realpathSync(current);
      return missing.length ? path.join(real, ...missing.reverse()) : real;
    } catch (error) {
      if (error.code !== 'ENOENT' && error.code !== 'ENOTDIR') return null;
      const up = path.dirname(current);
      if (up === current) return null;
      missing.push(path.basename(current));
      current = up;
    }
  }
}

// A worktree's `.git` is a file pointing at its own git dir; worktrees share
// the main repository's info/exclude through `commondir`. Only a directory that
// actually exists is accepted as the target, so a malformed pointer
// (`gitdir: /nonexistent`, an empty `.git` file) cannot send the exclusion into
// a directory git never reads.
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
  if (!isDirectory(dir)) return null;
  const pointer = path.join(dir, 'commondir');
  if (!fs.existsSync(pointer)) return dir;
  try {
    const common = path.resolve(dir, fs.readFileSync(pointer, 'utf8').trim());
    return isDirectory(common) ? common : null;
  } catch {
    return null;
  }
}

function isDirectory(target) {
  try {
    return fs.statSync(target).isDirectory();
  } catch {
    return false;
  }
}

// ---------- ignore-file matching ----------
//
// An explicit `AEP_HARNESS_PROFILE_DIR` used to bypass both git layers: it was
// honored even inside the work tree, so `git status` showed `A traces/...`.
// When the resolved destination is inside a repository it must now be named by
// `.gitignore` (the committed layer) or the common `info/exclude` (the runtime
// layer). The check reads the two files and matches the directory path; it
// never shells out to git, because this runs inside a capture hook. Matching
// is deliberately a subset of gitignore syntax (anchoring, `*`, `**`, `?`,
// trailing-slash directory patterns, negation) — a shape it cannot evaluate is
// treated as "not ignored", which refuses the write instead of risking one.

// Path of `dir` below `root`, with forward slashes; null when it is not below.
function relativePath(root, dir) {
  const rel = path.relative(root, dir);
  if (!rel || rel === '.') return '';
  if (path.isAbsolute(rel) || rel === '..' || rel.startsWith(`..${path.sep}`)) return null;
  return rel.split(path.sep).join('/').replace(/\/+$/, '');
}

// The ignore decision is git's, not ours. A hand-rolled matcher is what missed
// `!trace[s]/` re-including an approved destination: character classes, nested
// files, `core.excludesFile` and precedence are exactly what git already knows.
// The destination is a directory, and a trailing slash is what makes a
// directory-only pattern (`foo/`) answer for a directory that does not exist
// yet. Any non-zero result — including git being unavailable — is "not proven
// ignored", so capture fails closed.
function gitIgnored(root, dir) {
  const rel = relativePath(root, dir);
  if (!rel) return false;
  const result = spawnSync('git', ['-C', root, 'check-ignore', '-q', '--', `${rel}/`], { stdio: 'ignore' });
  return result.status === 0;
}

// Unconditional and idempotent: the pin only writes this when it creates the
// trace directory, so a pre-existing `.harness-profile/` would stay visible to
// git without this path. The return value is the point: `ok` means the entry is
// *in the file now*, read back from disk — not that a write was attempted. A
// throw is not the only failure mode (a redirected path, a stale mount), so the
// exact line is the test, and the caller refuses to write a trace otherwise.
function excludeTraceDir(cwd) {
  const root = gitRoot(cwd);
  if (!root) return { ok: false, reason: `no git repository above ${cwd}` };
  const dir = commonGitDir(root);
  if (!dir) {
    return {
      ok: false,
      reason: `the .git at ${path.join(root, '.git')} does not resolve to a git directory (malformed pointer or missing target)`,
    };
  }
  const exclude = path.join(dir, 'info', 'exclude');
  const line = `${translate.TRACE_DIR}/`;
  let current;
  try {
    current = fs.existsSync(exclude) ? fs.readFileSync(exclude, 'utf8') : '';
  } catch (error) {
    return { ok: false, reason: `cannot read ${exclude}: ${error.code || error.message}` };
  }
  if (current.split(/\r?\n/).includes(line)) return { ok: true, changed: false, exclude };
  try {
    fs.mkdirSync(path.dirname(exclude), { recursive: true });
    fs.appendFileSync(exclude, `${current && !current.endsWith('\n') ? '\n' : ''}${line}\n`);
  } catch (error) {
    return { ok: false, reason: `cannot write ${exclude}: ${error.code || error.message}` };
  }
  let landed;
  try {
    landed = fs.readFileSync(exclude, 'utf8').split(/\r?\n/).includes(line);
  } catch (error) {
    return { ok: false, reason: `cannot verify ${exclude}: ${error.code || error.message}` };
  }
  if (!landed) return { ok: false, reason: `the exclusion did not land in ${exclude}` };
  return { ok: true, changed: true, exclude };
}

// ---------- retention ----------

function bound(value, fallback) {
  if (typeof value !== 'string' || !value.trim()) return fallback;
  const parsed = Number(value.trim());
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

function retentionDays(env) {
  return bound((env || {})[RETENTION], RETENTION_DAYS);
}

function maxTraceBytes(env) {
  return bound((env || {})[MAX_BYTES], MAX_TRACE_BYTES);
}

// The trace files directly in `dir`, with the facts pruning needs. A missing or
// unreadable directory is empty, not an error: the first capture may run before
// anything has been written. Subdirectories are never entered or removed.
function traceFiles(dir) {
  let names;
  try {
    names = fs.readdirSync(dir);
  } catch {
    return [];
  }
  const files = [];
  for (const name of names) {
    if (!TRACE_FILE.test(name)) continue;
    const file = path.join(dir, name);
    let stat;
    try {
      stat = fs.lstatSync(file);
    } catch {
      continue;
    }
    if (stat.isFile()) files.push({ file, mtime: stat.mtimeMs, size: stat.size });
  }
  return files;
}

// Bound the trace directory: remove files older than `days` by mtime, then the
// oldest files until the directory fits `maxBytes`. Both are measured on the
// files this handler owns, so a shared `AEP_HARNESS_PROFILE_DIR` keeps its other
// contents. `0` disables a bound. Idempotent: a second run with the same inputs
// removes nothing. Returns the removed paths.
function pruneTraces(dir, options = {}) {
  const now = options.now ?? Date.now();
  const days = options.days ?? RETENTION_DAYS;
  const maxBytes = options.maxBytes ?? MAX_TRACE_BYTES;
  const removed = [];
  const kept = [];
  for (const entry of traceFiles(dir)) {
    if (days > 0 && now - entry.mtime > days * DAY_MS) {
      try {
        fs.rmSync(entry.file, { force: true });
        removed.push(entry.file);
        continue;
      } catch {
        // A file we cannot remove is still counted against the byte budget.
      }
    }
    kept.push(entry);
  }
  let total = kept.reduce((sum, entry) => sum + entry.size, 0);
  if (maxBytes > 0 && total > maxBytes) {
    kept.sort((a, b) => a.mtime - b.mtime);
    for (const entry of kept) {
      if (total <= maxBytes) break;
      try {
        fs.rmSync(entry.file, { force: true });
        removed.push(entry.file);
        total -= entry.size;
      } catch {
        // Keep the entry (and its bytes) rather than claiming a bound we miss.
      }
    }
  }
  return removed;
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
    prepared: false,
    protection: undefined, // undefined until the exclusion is checked; then {ok, reason?, changed?, exclude?}
    gitRoot: options.gitRoot !== undefined ? options.gitRoot : gitRoot(cwd),
    errors: [],
    warnings: [], // capture refusals, for tests/debug (see protectedDestination)
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
      reconciliations: [], // response bindings that superseded an earlier one
    };
    state.trees.set(id, tree);
    seedSpendFromTrace(state, tree);
  }
  state.sessionRoot.set(id, id);
  return tree;
}

// A restarted `opencode serve` is a fresh process with an empty spend map that
// appends to the same trace file. The pinned renderer keeps only the LAST
// SubagentStop per context (`contextSpend`), so a process-local subtotal would
// erase everything captured before the restart. Seed from the file, with the
// renderer's own precedence: spawn-call `child_spend` first, then stops, each
// last-wins in file order. Only the newest bytes are read — the last stop per
// context is what matters, and it is always in the tail.
const SEED_BYTES = 4 * 1024 * 1024;

function seedSpendFromTrace(state, tree) {
  const dir = traceDirOf(state);
  const file = path.join(dir, `${String(tree.rootSessionId).replace(/[^\w.-]/g, '_')}.jsonl`);
  let text;
  try {
    const size = fs.statSync(file).size;
    const fd = fs.openSync(file, 'r');
    try {
      const length = Math.min(size, SEED_BYTES);
      const buffer = Buffer.alloc(length);
      fs.readSync(fd, buffer, 0, length, size - length);
      text = buffer.toString('utf8');
    } finally {
      fs.closeSync(fd);
    }
    if (size > SEED_BYTES) text = text.slice(text.indexOf('\n') + 1); // drop the torn head
  } catch {
    return; // first capture in this destination, or unreadable
  }
  const childSpend = new Map();
  const stops = new Map();
  for (const line of text.split('\n')) {
    if (!line.trim()) continue;
    let record;
    try {
      record = JSON.parse(line);
    } catch {
      continue; // a torn line is skipped, as the renderer does
    }
    if (record.event === 'SubagentStop' && record.agent_id && record.spend) {
      // The translator keys the root's spend by session id, while the stop
      // record carries the renderer's `main` id (translate.buildStopRecord);
      // key the restore the same way the next stop will read it.
      const key = record.agent_id === 'main' ? tree.rootSessionId : record.agent_id;
      stops.set(key, record.spend);
    } else if (record.child_agent_id && record.child_spend) childSpend.set(record.child_agent_id, record.child_spend);
  }
  for (const [id, spend] of childSpend) tree.t.spend.set(id, spend);
  for (const [id, spend] of stops) tree.t.spend.set(id, spend);
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
// provisional tie-break: the first child session whose parentage is learned
// takes the earliest-started still-open call (FIFO, the order openSpawns keeps).
// This is only a guess for out-of-order observation. When the spawn response
// for either call arrives it supersedes the guess: `bindSpawnResponse` re-points
// the call and releases the displaced child.
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

function hasExplicitDir(state) {
  const override = (state.env || {})[DIR];
  return typeof override === 'string' && override.trim() !== '';
}

// Fail closed: a trace in an implicit directory is written only when its
// exclusion is proven on disk. That covers three shapes the old "does a git
// root exist" test let through: no repository at all, a malformed `.git` whose
// target git never reads, and a repository whose `info/exclude` cannot be
// written or read back (EACCES, a redirected path). The runtime write itself is
// still attempted whenever a repository is found, even with an explicit
// destination, so the pin's own capture stays excluded.
//
// An explicit `AEP_HARNESS_PROFILE_DIR` is the operator's choice of destination,
// but it is not a way around the ledger rule: a destination whose final path
// (symlinks resolved) is inside a git work tree is honored only when
// `.gitignore` or the common `info/exclude` names it. Otherwise `git status`
// would show the trace as untracked (verified: an unignored `<repo>/traces`
// produced `A traces/ses_*.jsonl`, and a symlink outside the repository pointing
// at that directory produced the same `?? traces/` with no warning), so capture
// refuses and names both remedies. A destination outside every repository is
// honored as before (tests, ad-hoc capture, an operator-controlled directory).
//
// The refusal is recorded once per state, naming the reason, so a plugin can
// surface it; it is not an error and never fails the session.
function protectedDestination(state) {
  if (state.protection === undefined) {
    state.protection = state.gitRoot
      ? excludeTraceDir(state.cwd)
      : { ok: false, reason: `no git repository above ${state.cwd} and ${DIR} is unset` };
  }
  if (hasExplicitDir(state)) {
    const dir = traceDirOf(state);
    // Judge the final path, not the operator's string: a symlink into the work
    // tree is inside it for git's purposes, whatever its own path looks like.
    const resolved = resolvedDestination(dir);
    if (!resolved) {
      const warning =
        `trace capture skipped: ${DIR}=${dir} cannot be resolved to a real path (symlink loop or unreadable component), `
        + `so the trace cannot be shown to be outside the git work tree; point ${DIR} at a resolvable directory `
        + '(for example one outside the repository) and retry';
      if (!state.warnings.includes(warning)) state.warnings.push(warning);
      return false;
    }
    const root = gitRoot(resolved);
    // Outside every work tree: the escape hatch is unchanged.
    if (!root) return true;
    // Compare canonical paths: a repository can be reached through a symlinked
    // prefix (`/var` -> `/private/var` on macOS), and a spelling mismatch would
    // read as "outside the work tree" and silently approve the destination.
    const rootReal = resolvedDestination(root) || root;
    // One git answer per destination per process: the hook must stay cheap.
    if (!state.explicitIgnored) state.explicitIgnored = new Map();
    let ignored = state.explicitIgnored.get(resolved);
    if (ignored === undefined) {
      ignored = gitIgnored(rootReal, resolved);
      state.explicitIgnored.set(resolved, ignored);
    }
    if (ignored) return true;
    const common = commonGitDir(root);
    const sources = [path.join(root, '.gitignore')];
    if (common) sources.push(path.join(common, 'info', 'exclude'));
    const rel = relativePath(rootReal, resolved) || path.basename(resolved);
    const shown = resolved === dir ? dir : `${dir} (resolves to ${resolved})`;
    const warning =
      `trace capture skipped: ${DIR}=${shown} is inside the git work tree at ${root} but not ignored by `
      + `${sources.join(' or ')}, so the trace would be committable; move the directory outside the repository, `
      + `or add an ignore rule for it (for example \`${rel}/\` in .gitignore) and retry`;
    if (!state.warnings.includes(warning)) state.warnings.push(warning);
    return false;
  }
  if (state.protection.ok) {
    // The default destination is `<git root>/.harness-profile`, and a symlink
    // there is judged by its target: excluding the link's name does not exclude
    // the file it resolves to. An explicit destination already gets this check;
    // the implicit one must not be the weaker path.
    const dir = traceDirOf(state);
    const resolved = resolvedDestination(dir);
    if (!resolved) {
      const warning =
        `trace capture skipped: the default destination ${dir} cannot be resolved to a real path `
        + '(symlink loop or unreadable component), so the trace cannot be shown to be excluded from git; '
        + `point ${DIR} at a resolvable directory and retry`;
      if (!state.warnings.includes(warning)) state.warnings.push(warning);
      return false;
    }
    const root = state.gitRoot;
    if (!root) return true;
    // Same canonical comparison as the explicit branch.
    const rootReal = resolvedDestination(root) || root;
    const rel = relativePath(rootReal, resolved);
    if (rel === null) {
      // Resolved outside this checkout — but a *different* work tree still
      // commits what it does not ignore. Validate against the repository that
      // actually contains the target, as the explicit branch does.
      const destRoot = gitRoot(resolved);
      if (!destRoot) return true; // outside every work tree
      const destRootReal = resolvedDestination(destRoot) || destRoot;
      if (gitIgnored(destRootReal, resolved)) return true;
      const warning =
        `trace capture skipped: the default destination ${dir} resolves to ${resolved}, which is inside the `
        + `git work tree at ${destRoot} but not ignored there, so the trace would be committable in that `
        + `repository; add an ignore rule for it there, move the link outside every repository, or point `
        + `${DIR} at a protected directory and retry`;
      if (!state.warnings.includes(warning)) state.warnings.push(warning);
      return false;
    }
    if (!rel) {
      const warning =
        `trace capture skipped: the default destination ${dir} resolves to the repository root ${root}, `
        + 'so no trace directory can be excluded; point AEP_HARNESS_PROFILE_DIR at a directory and retry';
      if (!state.warnings.includes(warning)) state.warnings.push(warning);
      return false;
    }
    if (gitIgnored(rootReal, resolved)) return true;
    const warning =
      `trace capture skipped: the default destination ${dir} resolves to ${resolved}, which is inside the `
      + `git work tree at ${root} but not ignored, so the trace would be committable; add an ignore rule for `
      + `\`${rel}/\` or point ${DIR} at a directory outside the repository and retry`;
    if (!state.warnings.includes(warning)) state.warnings.push(warning);
    return false;
  }
  const warning =
    `trace capture skipped: ${state.protection.reason}, so the trace could not be excluded from git; `
    + `set ${DIR} to capture in an explicit directory`;
  if (!state.warnings.includes(warning)) state.warnings.push(warning);
  return false;
}

// Preparation runs once, before the first event is dispatched: the exclusion is
// already verified by `protectedDestination`, so this only bounds the
// directory's growth. It is best-effort; a failure is recorded and capture
// continues. Pruning runs once per process, so the bounds hold across process
// starts rather than continuously within one long-lived process.
function ensurePrepared(state) {
  if (state.prepared) return;
  state.prepared = true;
  try {
    pruneTraces(traceDirOf(state), { days: retentionDays(state.env), maxBytes: maxTraceBytes(state.env) });
  } catch (error) {
    state.errors.push(error);
  }
}

function writeOne(state, tree, record) {
  if (!record) return null;
  ensurePrepared(state);
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
      reconciliations: tree.reconciliations,
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

// A provisional (FIFO/session.get) link is dropped without touching the child's
// parent: it keeps its tree, only its call attribution is reopened.
function releaseLink(tree, callId) {
  const t = tree.t;
  const child = t.links.get(callId);
  if (!child) return undefined;
  t.links.delete(callId);
  t.claimed.delete(child);
  const entry = tree.parentage.get(child);
  if (entry && entry.via !== 'spawn-response') tree.parentage.set(child, { ...entry, unbound: true });
  return child;
}

// Put a call back in the open list after its provisional child was taken by
// another call's authoritative response. Ordered by call start so "earliest
// still-open" keeps its meaning for the FIFO fallback.
function reopenSpawn(t, callId) {
  const call = t.calls.get(callId);
  if (!call || !call.sessionID) return;
  let open = t.openSpawns.get(call.sessionID);
  if (!open) t.openSpawns.set(call.sessionID, (open = []));
  if (open.includes(callId)) return;
  open.push(callId);
  const startOf = (id) => {
    const linked = t.calls.get(id) || {};
    return linked.startedAt ?? linked.calledAt ?? Number.POSITIVE_INFINITY;
  };
  open.sort((a, b) => startOf(a) - startOf(b));
}

// The spawn response is authoritative for call -> child. It does not refuse a
// child another source already tentatively bound: it takes the child over,
// releases the call's previous guess, and records the correction so the
// record built at the parent's step end carries the right child and spend.
function bindSpawnResponse(state, tree, callId, childId) {
  const t = tree.t;
  tree.spawnResponses.set(callId, childId || null);
  if (!childId) return;
  const call = t.calls.get(callId);
  if (!call || !call.sessionID || childId === call.sessionID) return;
  // A child already rooted on its own wrote records to its own file; re-rooting
  // would strand them. Only a response that beat the child's first event can
  // bind it (the API path makes that rare, and `session.get` prevents it in
  // production).
  const existingRoot = state.sessionRoot.get(childId);
  if (existingRoot && existingRoot === childId && state.trees.has(childId)) return;

  const parent = call.sessionID;
  const hadEarlierBinding = t.links.has(callId) || tree.parentage.has(childId);
  const previous = t.links.get(callId);
  if (previous && previous !== childId) releaseLink(tree, callId);
  for (const [other, linked] of [...t.links]) {
    if (linked !== childId || other === callId) continue;
    releaseLink(tree, other);
    // Only reopen a call that has not answered yet; a response already seen is
    // final for its own call.
    if (!tree.spawnResponses.has(other)) reopenSpawn(t, other);
  }

  t.parents.set(childId, parent);
  t.links.set(callId, childId);
  t.claimed.add(childId);
  pruneOpen(t, callId);
  state.parents.set(childId, parent);
  state.via.set(childId, 'spawn-response');
  state.sessionRoot.set(childId, tree.rootSessionId);
  tree.parentage.set(childId, { parent, via: 'spawn-response' });
  if (hadEarlierBinding) tree.reconciliations.push({ spawn: callId, from: previous || null, to: childId, parent });
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
  const release = { calls: new Set(), steps: new Set() };
  for (const event of events) {
    const record = translate.buildRecord(event, tree.t);
    if (record) {
      writeOne(state, tree, record);
      records.push(record);
    }
    const data = event.data || {};
    if (data.id) release.calls.add(data.id);
    if (data.assistantMessageID) release.steps.add(data.assistantMessageID);
  }
  // A long-lived service would otherwise keep every completed call's full input
  // (and its step's tokens) reachable forever — 100 completed sessions with
  // 1 MiB write inputs left 100 MiB reachable though nothing was pending.
  // Spend, links and parentage survive: they are what background children need.
  for (const id of release.calls) tree.t.calls.delete(id);
  for (const mid of release.steps) tree.t.steps.delete(mid);
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
  const payload = {
    hook_event_name: 'SubagentStop',
    session_id: childSessionId,
    agent_id: childSessionId,
    cwd: state.cwd,
  };
  const record = hp.buildEventRecord(payload, translate.HARNESS, new Date(at || tree.t.lastAt || Date.now()));
  // Spend is optional: a child that fails or is interrupted before its first
  // token-bearing step has none, and its terminal event must still end the
  // call (hp.js withStop) — otherwise the renderer keeps it `running` with
  // only its launch latency, forever. `contextSpend` reads `stop.spend` when
  // present and ignores its absence, so omitting it is safe.
  if (spend) record.spend = { ...spend };
  return record;
}

// Completed sessions would otherwise be retained for the life of the service.
// Keep a bounded number of trees, evicting the least recently active one that
// has nothing in flight. Eviction is safe: a resumed session reseeds its
// cumulative spend from the trace on disk (seedSpendFromTrace), and a tree with
// pending steps or open spawns is never evicted.
const MAX_TREES = 200;

function evictInactiveTrees(state) {
  if (state.trees.size <= MAX_TREES) return;
  const candidates = [...state.trees.values()]
    // A running tool is neither pending nor an open spawn: keep its call map,
    // or the tree is dropped mid-call and the completion has nothing to record.
    .filter((tree) => tree.pending.size === 0
      && tree.t.calls.size === 0
      && ![...tree.t.openSpawns.values()].some((open) => open.length > 0))
    .sort((a, b) => (a.lastAt || 0) - (b.lastAt || 0));
  const excess = state.trees.size - MAX_TREES;
  for (const tree of candidates.slice(0, excess)) {
    state.trees.delete(tree.rootSessionId);
    for (const [session, root] of [...state.sessionRoot]) {
      if (root === tree.rootSessionId) state.sessionRoot.delete(session);
    }
  }
}

async function dispatch(state, event, tree) {
  const data = event.data || {};
  const t = tree.t;
  if (Number.isFinite(event.created)) tree.lastAt = Math.max(tree.lastAt || 0, event.created);
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
    // No repository and no explicit destination: write nothing (fail closed).
    if (!protectedDestination(state)) return null;
    ensurePrepared(state);
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
      evictInactiveTrees(state);
      return records.length ? records : null;
    }

    const tree = await ensureTree(state, sessionId);
    if (!tree) {
      state.deferred.set(sessionId, { events: [event] });
      return null;
    }
    const records = await dispatch(state, event, tree);
    evictInactiveTrees(state);
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

// Response bindings that superseded an earlier (session.get/FIFO) binding, in
// arrival order. Evidence for tests and for the debug sidecar.
function reconciliationsOf(state) {
  const all = [];
  for (const tree of state.trees.values()) all.push(...tree.reconciliations);
  return all;
}

module.exports = {
  ENABLE,
  DIR,
  DEBUG,
  RETENTION,
  MAX_BYTES,
  RETENTION_DAYS,
  MAX_TRACE_BYTES,
  createState,
  handleEvent,
  parentageOf,
  reconciliationsOf,
  spawnResponseOf,
  traceDirOf,
  excludeTraceDir,
  pruneTraces,
};
