'use strict';

// Translator: opencode v2.3 events -> the Claude-shaped payload the vendored
// harness-profiler (reference/harness-profiler/) already knows how to record.
// Nothing here re-implements the pin's field shaping, masking or line fitting:
// buildRecord, buildEventRecord and serialize are called as-is.
//
// Event facts (Phase 0, spike-notes.md):
//   session.tool.input.started  the only event with the tool name, keyed by id
//   session.tool.called         the call start; input and assistantMessageID
//   session.tool.success/failed the completion; no duration field anywhere
//   session.step.ended          per-message tokens; lands after that step's calls
//
// Because a step's tokens arrive after its calls, `context_tokens` is unknown
// when the call ends: a record must be built at or after that step's
// `session.step.ended`. `buildRecord` re-runs `ingest` (idempotent per event id)
// and then reads the step state, so a handler buffers a step's call records and
// builds them once the step end arrives. The tests' `trace()` pre-ingests every
// event to satisfy this ordering before building.
//
// Masking: the pin's `mask` runs inside `buildRecord`. One additive step,
// `redactSecrets`, runs on the payload strings first (see its comment).

const fs = require('fs');
const path = require('path');

const hp = require('../../reference/harness-profiler/plugin/libexec/hp.js');

const HARNESS = 'opencode';
const MAIN = 'main';
const TRACE_DIR = '.harness-profile';
const TERMINAL = new Set(['session.tool.success', 'session.tool.failed']);

// Opencode's vocabulary -> the pin's. The pin only nests calls whose tool is in
// PARENT_TOOLS ('Skill', 'Agent') and only shows those rows without --verbose.
const TOOL_NAMES = { skill: 'Skill', subagent: 'Agent' };
const SPAWNING = new Set(['Agent']);

function createState(rootSessionId, { cwd = process.cwd(), parents } = {}) {
  const state = {
    rootSessionId,
    cwd,
    calls: new Map(), // tool_use_id -> { name, input, sessionID, messageID, startedAt, calledAt }
    steps: new Map(), // assistantMessageID -> tokens
    spend: new Map(), // sessionID -> { new, cached, out, calls }
    counted: new Map(), // sessionID -> Set<assistantMessageID> already in spend
    parents: new Map(), // sessionID -> parent sessionID, from ctx.session.get().parentID
    links: new Map(), // spawning tool_use_id -> child sessionID
    claimed: new Set(), // child sessionIDs already linked to a call
    openSpawns: new Map(), // sessionID -> spawning tool_use_ids still running
    seen: new Set(), // event ids
    lastAt: 0, // latest envelope `created`, for the session-end record
  };
  if (parents instanceof Map) for (const [child, parent] of parents) noteChild(state, child, parent);
  else if (parents) for (const [child, parent] of Object.entries(parents)) noteChild(state, child, parent);
  return state;
}

// Parentage is learned from ctx.session.get().parentID (session.created never
// fired in Phase 0), so the capture handler reports each new child session here.
function noteChild(state, sessionId, parentId) {
  if (!sessionId || !parentId || sessionId === parentId) return;
  state.parents.set(sessionId, parentId);
  bindOpenSpawn(state, sessionId);
}

function bindOpenSpawn(state, sessionId) {
  const parent = state.parents.get(sessionId);
  if (!parent || state.claimed.has(sessionId)) return;
  if ([...state.links.values()].includes(sessionId)) return;
  const open = state.openSpawns.get(parent) || [];
  // Only when unambiguous: a second concurrent spawn needs an explicit binding.
  if (open.length !== 1) return;
  state.links.set(open[0], sessionId);
  state.claimed.add(sessionId);
}

function callOf(state, id) {
  let call = state.calls.get(id);
  if (!call) state.calls.set(id, (call = {}));
  return call;
}

function openSpawn(state, id, sessionId) {
  if (!sessionId || !id) return;
  let open = state.openSpawns.get(sessionId);
  if (!open) state.openSpawns.set(sessionId, (open = []));
  if (!open.includes(id)) open.push(id);
}

function closeSpawn(state, id) {
  for (const open of state.openSpawns.values()) {
    const at = open.indexOf(id);
    if (at !== -1) open.splice(at, 1);
  }
}

function number(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function promptTokens(tokens) {
  const cache = tokens.cache || {};
  return number(tokens.input) + number(cache.read) + number(cache.write);
}

// One model call's spend: plain input and cache writes are new, cache reads are
// cheap, output is the reply. Reasoning is neither prompt nor reply.
function addStep(state, sessionId, messageID, tokens) {
  if (!sessionId || !messageID || !tokens) return;
  let counted = state.counted.get(sessionId);
  if (!counted) state.counted.set(sessionId, (counted = new Set()));
  if (counted.has(messageID)) return;
  counted.add(messageID);
  let spend = state.spend.get(sessionId);
  if (!spend) state.spend.set(sessionId, (spend = { new: 0, cached: 0, out: 0, calls: 0 }));
  spend.new += number(tokens.input) + number((tokens.cache || {}).write);
  spend.cached += number((tokens.cache || {}).read);
  spend.out += number(tokens.output);
  spend.calls += 1;
}

// Fill state from one event. Returns `state` so tests can chain.
function ingest(event, state) {
  if (!event || typeof event !== 'object' || !event.type) return state;
  const data = event.data || {};
  const at = typeof event.created === 'number' ? event.created : Date.parse(event.created);
  if (Number.isFinite(at)) state.lastAt = Math.max(state.lastAt, at);
  if (event.id) {
    if (state.seen.has(event.id)) return state;
    state.seen.add(event.id);
  }

  if (event.type === 'session.created') {
    // Not observed in Phase 0; harmless when a harness does emit it.
    if (data.sessionID && data.parentID) noteChild(state, data.sessionID, data.parentID);
    return state;
  }
  if (data.sessionID) bindOpenSpawn(state, data.sessionID);

  switch (event.type) {
    case 'session.tool.input.started': {
      if (!data.id) break;
      const call = callOf(state, data.id);
      call.name = call.name || data.name;
      call.sessionID = call.sessionID || data.sessionID;
      call.messageID = call.messageID || data.assistantMessageID;
      if (Number.isFinite(at)) call.startedAt = Math.min(call.startedAt ?? at, at);
      if (SPAWNING.has(TOOL_NAMES[call.name] || call.name)) openSpawn(state, data.id, call.sessionID);
      break;
    }
    case 'session.tool.called': {
      if (!data.id) break;
      const call = callOf(state, data.id);
      call.input = data.input || {};
      call.sessionID = call.sessionID || data.sessionID;
      call.messageID = call.messageID || data.assistantMessageID;
      if (Number.isFinite(at)) call.calledAt = at;
      if (SPAWNING.has(TOOL_NAMES[call.name] || call.name)) openSpawn(state, data.id, call.sessionID);
      break;
    }
    case 'session.tool.success':
    case 'session.tool.failed': {
      if (!data.id) break;
      const call = callOf(state, data.id);
      call.sessionID = call.sessionID || data.sessionID;
      call.messageID = call.messageID || data.assistantMessageID;
      closeSpawn(state, data.id);
      break;
    }
    case 'session.step.ended': {
      if (data.assistantMessageID && data.tokens) {
        state.steps.set(data.assistantMessageID, data.tokens);
        addStep(state, data.sessionID, data.assistantMessageID, data.tokens);
      }
      break;
    }
    default:
      break;
  }
  return state;
}

function toolInput(toolName, input) {
  if (toolName === 'Skill') {
    const skill = input.skill || input.name;
    return skill ? { ...input, skill } : input;
  }
  if (toolName === 'Agent') {
    const type = input.subagent_type || input.agent;
    return type ? { ...input, subagent_type: type } : input;
  }
  return input;
}

function responseOf(data) {
  const response = {};
  if (data.content !== undefined) response.content = data.content;
  if (data.metadata !== undefined) response.metadata = data.metadata;
  return response;
}

function errorText(error) {
  if (!error) return undefined;
  if (typeof error === 'string') return error;
  return error.message || error.type || undefined;
}

function durationOf(call, end) {
  const start = call && (call.calledAt ?? call.startedAt);
  if (typeof start !== 'number' || typeof end !== 'number') return undefined;
  return Math.max(0, end - start);
}

// The child a spawning call started: explicit link first, otherwise the only
// unclaimed child session recorded for that caller.
function childOf(state, id, call) {
  if (!call) return undefined;
  if (state.links.has(id)) return state.links.get(id);
  const children = [];
  for (const [child, parent] of state.parents) {
    if (parent === call.sessionID && !state.claimed.has(child)) children.push(child);
  }
  if (children.length !== 1) return undefined;
  state.links.set(id, children[0]);
  state.claimed.add(children[0]);
  return children[0];
}

// One completion event -> the payload shape buildRecord expects. Returns null
// for events that are not the end of a known tool call.
function toPayload(event, state) {
  if (!event || !TERMINAL.has(event.type)) return null;
  const data = event.data || {};
  const call = data.id ? state.calls.get(data.id) : undefined;
  if (!call || !call.name) return null;

  const toolName = TOOL_NAMES[call.name] || call.name;
  const session = data.sessionID || call.sessionID;
  const failed = event.type === 'session.tool.failed';
  const response = failed ? {} : responseOf(data);

  // Agent/Skill render as contexts only when the pin sees `agentId`. We set it
  // from parentage we resolved ourselves, never from opencode's response.
  const child = toolName === 'Agent' || toolName === 'Skill' ? childOf(state, data.id, call) : undefined;
  if (child) response.agentId = child;

  const payload = {
    hook_event_name: failed ? 'PostToolUseFailure' : 'PostToolUse',
    tool_name: toolName,
    tool_input: toolInput(toolName, call.input || {}),
    tool_response: response,
    tool_use_id: data.id,
    session_id: session,
    duration_ms: durationOf(call, event.created),
    cwd: state.cwd,
  };
  // Root records must omit agent_id: the pin keys `main` off its absence
  // (hp.js:535-537); a session id here would render a placeholder parent.
  if (session !== state.rootSessionId) payload.agent_id = session;
  if (failed) payload.error = errorText(data.error);
  return payload;
}

// The pin's `mask` (hp.js:42-46) needs a word boundary in front of the key word;
// `_` is a word character, so `GITHUB_TOKEN=`, `AWS_SECRET_ACCESS_KEY=` and
// `NEUROSTRATA_API_KEY=` never reach it. One additive rule covers the shapes
// that matter: a key name that *contains* a secret word, in any case and with
// any runner. Case-insensitive containment is what keeps `secret_key`,
// `secretKey`, `dbPassword`, `clientSecret`, `awsSecretAccessKey`,
// `credential` and `access_key` all covered by one rule instead of three
// intent-specific ones whose union kept losing shapes.
//
// The rule keeps the key name and separator and replaces only the value. Two
// details stop it from eating neighbours:
//   - the value is a complete quoted string (either quote) or an unquoted run
//     that stops at whitespace, quotes or JSON punctuation. A quoted value is
//     replaced whole, quote character kept, so `GITHUB_TOKEN="a b"` loses both
//     words and `{"GITHUB_TOKEN":"x","b":2}` keeps its shape. Matching the
//     quoted branch first is what keeps masking fail-closed: the earlier
//     balanced-quote backreference (`[^\s"'&,}]+\4`) abandoned the match when
//     the quoted value held a space, and `GITHUB_TOKEN="a b"` came out intact.
//   - a known benign key name (the token counts and the tokenizer) is returned
//     unchanged by the callback. A callback skip is clearer than lookarounds and
//     cannot be defeated by group numbering.
//
// Every quantifier is either bounded (`{0,64}` on the two name runs) or a
// single-character-class repeat (`[ \t]*` separator, `[^"\n]*` / `[^'\n]*` /
// `[^\s"'&,}]+` value), so all are linear. A name run open at both ends
// (`[A-Za-z0-9_]*(?:TOKEN|...)[A-Za-z0-9_]*`) backtracks cubically on one long
// token blob with no separator: 8 KB of repeated `TOKEN` measured 14.4 s, and
// this runs inside a capture hook. Bounded runs (`{0,64}`) take 0.01 ms on the
// same blob: `\b` pins each attempt to a word start and both name runs stop.
//
// The keyword may sit anywhere in the name, including the start: a mandatory
// leading character would leave bare `TOKEN=` and `credential=` unmatched.
const CREDENTIAL =
  /\b([A-Za-z0-9_]{0,64}(?:SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL|ACCESS_KEY|API_?KEY)[A-Za-z0-9_]{0,64})(["']?)([ \t]*[:=][ \t]*|[ \t]+)("[^"\n]*"|'[^'\n]*'|[^\s"'&,}]+)/gi;

// Keys a profiler exists to report and must keep verbatim. The instruction's
// `^(input|output)_tokens$` case is already covered by `_?tokens?`.
const BENIGN_KEY = /^(?:(?:input|output|total|num|max|prompt|completion)_?tokens?|tokenizer)$/i;

function redactMatch(match, key, keyQuote, separator, value, offset, text) {
  if (BENIGN_KEY.test(key)) return match;
  // A bare space separates a flag from its value (`--password x`); a sentence
  // such as "the token budget" keeps its words.
  if (!separator.trim() && text[offset - 1] !== '-') return match;
  // The value group is either a whole quoted string or an unquoted run; keep
  // whichever quote it used so JSON and CLI quoting survive the substitution.
  const quote = value[0] === '"' || value[0] === "'" ? value[0] : '';
  return `${key}${keyQuote}${separator}${quote}[redacted]${quote}`;
}

function redactSecrets(value) {
  if (typeof value === 'string') return value.replace(CREDENTIAL, redactMatch);
  if (Array.isArray(value)) return value.map(redactSecrets);
  if (value && typeof value === 'object') {
    const out = {};
    for (const [key, item] of Object.entries(value)) out[key] = redactSecrets(item);
    return out;
  }
  return value;
}

// One completion event -> one record. Null when the event is not a call end.
function buildRecord(event, state) {
  ingest(event, state);
  const payload = toPayload(event, state);
  if (!payload) return null;

  const record = hp.buildRecord(redactSecrets(payload), HARNESS, new Date(event.created));

  const data = event.data || {};
  const call = state.calls.get(payload.tool_use_id) || {};
  const tokens = state.steps.get(data.assistantMessageID) || state.steps.get(call.messageID);
  if (tokens) record.context_tokens = promptTokens(tokens);

  const child = record.child_agent_id;
  const spend = child && state.spend.get(child);
  if (spend) record.child_spend = { ...spend };
  return record;
}

// The root context's total spend, emitted once when the root session ends.
// contextSpend reads only SubagentStop.spend for a context with no spawn call
// (hp.js:318-332), and the root id is literally `main`.
function buildStopRecord(state, now = new Date(state.lastAt || Date.now())) {
  const at = now instanceof Date ? now : new Date(now);
  const payload = { hook_event_name: 'SubagentStop', session_id: state.rootSessionId, agent_id: MAIN, cwd: state.cwd };
  const record = hp.buildEventRecord(payload, HARNESS, at);
  const spend = state.spend.get(state.rootSessionId);
  if (spend) record.spend = { ...spend };
  return record;
}

// Append one record to the root session's trace file. Every context in the tree
// goes to the same file: the renderer groups one record array, so a child in its
// own file is an orphan (hp.js:602-628).
function writeRecord(traceDir, record, rootSessionId) {
  if (!record) return null;
  const file = path.join(traceDir, `${String(rootSessionId).replace(/[^\w.-]/g, '_')}.jsonl`);
  fs.mkdirSync(traceDir, { recursive: true });
  fs.appendFileSync(file, `${hp.serialize(record)}\n`);
  return file;
}

module.exports = {
  HARNESS,
  TRACE_DIR,
  createState,
  ingest,
  noteChild,
  redactSecrets,
  toPayload,
  buildRecord,
  buildStopRecord,
  writeRecord,
};
