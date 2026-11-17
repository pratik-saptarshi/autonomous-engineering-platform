'use strict';

// The M2 gate (E5): the vendored renderer judges what the translator actually
// wrote to disk. Nothing here reads the translator's in-memory records or a
// hand-authored record file: the fixture is an opencode event sequence, a
// handler turns it into records the way a capture handler would (per-step, at
// `session.step.ended`, as translate.js' header requires), and every assertion
// runs against the JSONL parsed back from the root session's trace file through
// the pin's own contextsOf / renderTree / renderHtml / contextSpend.
//
// A pass therefore means: two contexts, a child whose parent is `main`, no
// `parent not recorded` placeholder, an inline Skill marker, and non-zero spend
// for both contexts — all through the pin, none of it through the translator's
// assertions.

const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const hp = require('../../reference/harness-profiler/plugin/libexec/hp.js');
const translate = require('./translate.js');

const FIXTURE = path.join(__dirname, 'testdata', 'nested-session.json');
const ROOT = 'ses_root_gate';
const CHILD = 'ses_child_gate';

function fixture() {
  return JSON.parse(fs.readFileSync(FIXTURE, 'utf8'));
}

// A capture handler, reduced to the ordering the translator requires: a call's
// records are built once the step that holds it has reported its tokens. The
// completion events are buffered per assistant message and flushed at
// `session.step.ended`; every record goes through translate.writeRecord, so
// file placement and the pin's serialize run exactly as in production.
function capture(data, traceDir) {
  const state = translate.createState(data.rootSessionId, { cwd: data.cwd });
  const pending = new Map(); // assistantMessageID -> terminal events not yet built

  for (const event of data.events) {
    translate.ingest(event, state);
    const inner = event.data || {};

    if (event.type === 'session.tool.success' || event.type === 'session.tool.failed') {
      const key = inner.assistantMessageID || '';
      if (!pending.has(key)) pending.set(key, []);
      pending.get(key).push(event);
    } else if (event.type === 'session.step.ended') {
      const key = inner.assistantMessageID || '';
      for (const ended of pending.get(key) || []) {
        const record = translate.buildRecord(ended, state);
        translate.writeRecord(traceDir, record, data.rootSessionId);
      }
      pending.delete(key);
    }
  }

  // A call whose step never ended would silently lose its tokens; the fixture
  // must be complete enough to build every record through the file path.
  assert.equal(pending.size, 0, `calls left without a token-bearing step: ${[...pending.keys()].join(', ')}`);

  translate.writeRecord(traceDir, translate.buildStopRecord(state), data.rootSessionId);
  return state;
}

// The pin's readTrace is not exported; a torn line is skipped the same way.
function readTrace(file) {
  const records = [];
  for (const line of fs.readFileSync(file, 'utf8').split('\n')) {
    if (!line.trim()) continue;
    try { records.push(JSON.parse(line)); } catch { /* skipped, as the pin does */ }
  }
  return records;
}

// The pin inlines its page data as `const D = /*DATA*/null;`.
function pageData(html) {
  const match = /const D = (\{.*\});/.exec(html);
  assert.ok(match, 'renderHtml inlined its data object');
  return JSON.parse(match[1]);
}

function nonZeroSpend(spend, label) {
  assert.ok(spend, `${label} has no spend entry`);
  for (const field of ['new', 'cached', 'out', 'calls']) {
    assert.ok(spend[field] > 0, `${label} spend.${field} is not positive: ${JSON.stringify(spend)}`);
  }
}

test('M2 gate: the pin renders two nested contexts from the trace the translator wrote', () => {
  const data = fixture();
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'hp-gate-'));
  const traceDir = path.join(dir, translate.TRACE_DIR);

  try {
    capture(data, traceDir);

    // Step 1: file placement is part of the contract. One tree, one file, named
    // after the root session; the child's records ride in it.
    assert.deepEqual(fs.readdirSync(traceDir), [`${ROOT}.jsonl`], 'one file per session tree');
    const records = readTrace(path.join(traceDir, `${ROOT}.jsonl`));
    assert.ok(records.length >= 4, 'the records were written to the file');
    assert.ok(records.some((r) => r.agent_id === CHILD), 'the child wrote into the root file');
    assert.ok(records.some((r) => r.event === 'SubagentStop' && r.agent_id === 'main'), 'root spend was recorded');

    // Step 2: the pin's view of the tree. Exactly two contexts, child under main.
    const { contexts, markers } = hp.contextsOf(records);
    assert.equal(contexts.length, 2, `expected main and one child, got ${contexts.map((c) => c.id).join(', ')}`);
    assert.equal(contexts[0].id, 'main');
    assert.equal(contexts[0].parent, undefined, 'main has no parent');
    const child = contexts.find((c) => c.id === CHILD);
    assert.ok(child, `context ${CHILD} is missing`);
    assert.equal(child.parent, 'main', 'the child context hangs off main, not off nothing');
    assert.equal(child.tool, 'Agent', 'the child was started by an Agent call');
    assert.equal(child.name, 'general');

    // Step 3: no placeholder anywhere in the rendered tree. A missing parent is
    // rendered as `parent not recorded`; both default and verbose views must be free of it.
    assert.ok(!records.some((r) => r.tool && r.agent_id && !records.some((p) => p.child_agent_id === r.agent_id)),
      'no call sits in a context whose spawning call is missing');
    const text = hp.renderTree(records);
    const verbose = hp.renderTree(records, { verbose: true });
    assert.ok(!text.includes('parent not recorded'), `default tree contains a placeholder:\n${text}`);
    assert.ok(!verbose.includes('parent not recorded'), `verbose tree contains a placeholder:\n${verbose}`);
    // Forest roots are calls, not contexts: every top-level main call is a root,
    // which is normal. What must never appear is a placeholder node — the pin's
    // form of an orphan — nor a child that is not nested under its spawn.
    const forest = hp.buildForest(records);
    const placeholders = [];
    const walk = (nodes) => {
      for (const node of nodes) {
        if (node.placeholder) placeholders.push(node.agent);
        walk(node.children);
      }
    };
    walk(forest);
    assert.deepEqual(placeholders, [], 'no node renders as parent not recorded');
    const spawnNode = forest.find((node) => node.record && node.record.tool === 'Agent');
    assert.ok(spawnNode, 'the Agent call is in the forest');
    assert.equal(spawnNode.children.length, 1, 'the child call is nested under the Agent call');
    assert.equal(spawnNode.children[0].record.agent_id, CHILD);

    // Step 4: the inline Skill is a marker in main, not a context of its own.
    const inline = markers.filter((m) => m.kind === 'inline');
    assert.equal(inline.length, 1, 'exactly one inline skill marker');
    assert.equal(inline[0].ctx, 'main', 'the inline skill runs in the caller context');
    assert.equal(inline[0].name, 'braindump');
    assert.equal(contexts.filter((c) => c.tool === 'Skill' && c.id !== 'main').length, 0, 'no context for an inline skill');
    assert.match(text, /braindump \(skill\) inline/, 'the text tree shows the inline skill');
    assert.match(text, /general \(agent\) new context ses_ch/, 'the text tree shows the child context');

    // Step 5: spend, read by the pin from the file. Child spend rides the Agent
    // call; root spend rides the SubagentStop event record.
    const spend = hp.contextSpend(records);
    nonZeroSpend(spend.get(CHILD), `child ${CHILD}`);
    nonZeroSpend(spend.get('main'), 'root main');

    // The renderer's own columns must show the child's spend, not just the map.
    const agentLine = text.split('\n').find((line) => line.includes('(agent)'));
    assert.ok(agentLine, `no agent line in:\n${text}`);
    const childSpend = spend.get(CHILD);
    assert.match(agentLine, new RegExp(`${childSpend.new}\\s+`), `the agent line does not show new tokens: ${agentLine}`);
    assert.match(agentLine, new RegExp(`${childSpend.out}\\s+general \\(agent\\)`), `the agent line does not show out tokens: ${agentLine}`);

    // Step 6: the HTML page is built from the same parsed file and agrees.
    const page = pageData(hp.renderHtml({ id: ROOT, records }));
    assert.equal(page.contexts.length, 2);
    const pageChild = page.contexts.find((c) => c.id === CHILD);
    assert.ok(pageChild, 'the page has the child context');
    assert.equal(pageChild.parent, 'main');
    nonZeroSpend(pageChild.spent, 'html child');
    nonZeroSpend(page.contexts.find((c) => c.id === 'main').spent, 'html root');
    assert.equal(page.markers.filter((m) => m.kind === 'inline').length, 1);
    assert.ok(page.calls.some((c) => c.ctx === CHILD && c.tool === 'read'), 'the child call is in the page');
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('M2 gate: context_tokens comes from the step that ended after the call', () => {
  // Anti-gaming companion: the gate's records must carry the token numbers the
  // fixture's step.ended events hold, not zeros and not a later step's usage.
  const data = fixture();
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'hp-gate-tokens-'));
  try {
    capture(data, path.join(dir, translate.TRACE_DIR));
    const records = readTrace(path.join(dir, translate.TRACE_DIR, `${ROOT}.jsonl`));
    const byId = new Map(records.filter((r) => r.tool_use_id).map((r) => [r.tool_use_id, r]));

    assert.equal(byId.get('call_gate_skill').context_tokens, 300 + 4096 + 128);
    assert.equal(byId.get('call_gate_child_read').context_tokens, 120 + 8000 + 0);
    assert.equal(byId.get('call_gate_spawn').context_tokens, 420 + 4600 + 512);
    assert.equal(byId.get('call_gate_resume').context_tokens, 500 + 5200 + 0);

    // Child spend is the sum of the child's two steps, deduped by message id.
    assert.deepEqual(byId.get('call_gate_spawn').child_spend, { new: 334, cached: 17000, out: 85, calls: 2 });
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
