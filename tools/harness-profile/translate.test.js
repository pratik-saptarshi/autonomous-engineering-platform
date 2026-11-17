'use strict';

// Evals E1-E4b for the opencode -> harness-profiler translator. Fixtures are
// event sequences in the shapes observed in Phase 0 (see spike-notes.md):
// the tool name arrives on `session.tool.input.started`, the call on
// `session.tool.called`, completion on `session.tool.success`/`failed`, and
// per-step tokens on `session.step.ended` (which, as in a real session, lands
// after the calls of that step have completed).

const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const hp = require('../../reference/harness-profiler/plugin/libexec/hp.js');
const translate = require('./translate.js');

const EVENTS = path.join(__dirname, 'testdata', 'events');
const CHILD = 'ses_child_agent';
const ROOT = 'ses_root_agent';

function fixture(name) {
  return JSON.parse(fs.readFileSync(path.join(EVENTS, name), 'utf8'));
}

// Feed a fixture through the public API the way a capture handler would: state
// is filled first (completion events precede the step.ended carrying their
// usage), then one record is built per terminal event.
function trace(name, options) {
  const data = fixture(name);
  const state = translate.createState(data.rootSessionId, options);
  for (const event of data.events) translate.ingest(event, state);
  const records = [];
  for (const event of data.events) {
    const record = translate.buildRecord(event, state);
    if (record) records.push(record);
  }
  return { data, state, records };
}

function call(records, id) {
  const found = records.find((record) => record.tool_use_id === id);
  assert.ok(found, `no record for ${id}`);
  return found;
}

test('E1: a call record carries the pin schema fields from the completion event', () => {
  const { records } = trace('tool-calls.json');
  // Only the three completions produce records: input streaming, calls and
  // step ends are state, not calls.
  assert.deepEqual(records.map((record) => record.tool_use_id).sort(), ['call_read', 'call_shell', 'call_skill']);

  const shell = call(records, 'call_shell');
  assert.equal(shell.v, 2);
  assert.equal(shell.harness, 'opencode');
  assert.equal(shell.session, 'ses_root_tools');
  assert.equal(shell.tool_use_id, 'call_shell');
  assert.equal(shell.at, new Date(1794931114300).toISOString());
  // No duration field exists in opencode: success.created - called.created.
  assert.equal(shell.duration_ms, 1794931114300 - 1794931110200);
  assert.equal(shell.tool, 'shell');
  assert.equal(shell.ok, true);
  assert.ok(Buffer.byteLength(hp.serialize(shell)) <= 4096, 'serialize keeps a record under 4096 bytes');

  const failed = call(records, 'call_read');
  assert.equal(failed.ok, false);
  assert.equal(failed.duration_ms, 1794931120500 - 1794931120100);
  assert.match(failed.result, /File not found: \.\/nope\.txt/);
  // Masking is the pin's: a secret-looking key never reaches the record.
  assert.ok(!failed.args.includes('test-placeholder-value'));
});

test('E2: skill maps to Tool "Skill" and subagent to "Agent"', () => {
  const { records } = trace('tool-calls.json');
  const skill = call(records, 'call_skill');
  assert.equal(skill.tool, 'Skill');
  assert.equal(skill.name, 'braindump');
  assert.equal(skill.child_agent_id, undefined, 'an inline skill starts no context');

  const nested = trace('subagent.json', { parents: { [CHILD]: ROOT } });
  const spawn = call(nested.records, 'call_spawn');
  assert.equal(spawn.tool, 'Agent');
  assert.equal(spawn.name, 'general');
});

test('E3: root-session records omit agent_id; child records name their session', () => {
  const { records } = trace('subagent.json', { parents: { [CHILD]: ROOT } });

  const spawn = call(records, 'call_spawn');
  assert.ok(!('agent_id' in spawn), 'the root context is omitted, not spelled out or null');

  const child = call(records, 'call_child_read');
  assert.equal(child.session, CHILD);
  assert.equal(child.agent_id, CHILD);
});

test('E4: context_tokens is the prompt side of the emitting step only', () => {
  const { records } = trace('tool-calls.json');

  const shell = call(records, 'call_shell');
  assert.equal(shell.context_tokens, 14 + 109312 + 0);
  // output and reasoning are not prompt-side; a naive total would be far larger.
  assert.notEqual(shell.context_tokens, 14 + 109312 + 59 + 73);

  // A step with a non-zero cache write (the Phase 0 fixture gap).
  const skill = call(records, 'call_skill');
  assert.equal(skill.context_tokens, 86 + 109184 + 2048);

  const nested = trace('subagent.json', { parents: { [CHILD]: ROOT } });
  assert.equal(call(nested.records, 'call_child_read').context_tokens, 100 + 500 + 10);
});

test('E4b: child_spend rides the spawning call and a SubagentStop carries root spend', () => {
  const { records, state } = trace('subagent.json', { parents: { [CHILD]: ROOT } });

  const spawn = call(records, 'call_spawn');
  assert.equal(spawn.child_agent_id, CHILD);
  assert.deepEqual(spawn.child_spend, { new: 230, cached: 1100, out: 50, calls: 2 });

  const stop = translate.buildStopRecord(state);
  assert.equal(stop.v, 2);
  assert.equal(stop.harness, 'opencode');
  assert.equal(stop.session, ROOT);
  assert.equal(stop.event, 'SubagentStop');
  assert.equal(stop.agent_id, 'main');
  assert.equal(stop.at, new Date(1794932004000).toISOString());
  assert.deepEqual(stop.spend, { new: 170, cached: 4150, out: 20, calls: 2 });

  // What the renderer actually reads.
  const spend = hp.contextSpend([...records, stop]);
  assert.deepEqual(spend.get('main'), { new: 170, cached: 4150, out: 20, calls: 2 });
  assert.deepEqual(spend.get(CHILD), { new: 230, cached: 1100, out: 50, calls: 2 });
});

test('writeRecord appends every context to the root session file, via the pin serialize', () => {
  const { data, state, records } = trace('subagent.json', { parents: { [CHILD]: ROOT } });
  const stop = translate.buildStopRecord(state);
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'hp-translate-'));
  const traceDir = path.join(dir, '.harness-profile');

  try {
    for (const record of [...records, stop]) translate.writeRecord(traceDir, record, data.rootSessionId);

    const files = fs.readdirSync(traceDir);
    assert.deepEqual(files, [`${ROOT}.jsonl`], 'one file per session tree, named after the root');

    const file = path.join(traceDir, files[0]);
    const lines = fs.readFileSync(file, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
    assert.equal(lines.length, records.length + 1);
    assert.ok(lines.some((line) => line.agent_id === CHILD), 'the child record is in the root file');
    assert.ok(lines.some((line) => line.event === 'SubagentStop' && line.agent_id === 'main'));

    // Read back: the pin nests the child under the spawning call, no orphan.
    const forest = hp.buildForest(lines);
    assert.equal(forest.length, 1);
    assert.equal(forest[0].children.length, 1);
    assert.ok(!forest[0].placeholder);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
