'use strict';
// Checks the recorded e2e run: the fixture harness used every feature the
// profiler shows, and the committed outputs match what hp renders today.
// Re-record with e2e/claude/run.sh, re-render with `node e2e/render.js --png`.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const { contextsOf } = require('../plugin/libexec/hp.js');
const { outputs } = require('../e2e/render.js');

const OUTPUT = path.join(__dirname, '..', 'e2e', 'claude', 'output');
const records = fs.readFileSync(path.join(OUTPUT, 'trace.jsonl'), 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
const calls = records.filter((r) => r.tool);
const { contexts, markers } = contextsOf(records);
// The context started by the Skill or Agent call with this name.
const started = (name) => contexts.find((c) => c.id === calls.find((r) => r.name === name && r.child_agent_id).child_agent_id);

test('e2e claude: the fixture exercised every kind of context', () => {
  assert.strictEqual(started('validator').kind, 'fresh', 'forked skill starts fresh');
  assert.strictEqual(started('estimator').kind, 'fresh', 'custom subagent starts fresh');
  assert.strictEqual(started('general-purpose').kind, 'fresh');
  assert.strictEqual(started('fork').kind, 'copy', 'fork subagent copies main');
  assert.strictEqual(started('fork').hue, contexts[0].hue, 'a copy keeps its parent color');
});

test('e2e claude: inline skills in main and in a subagent, a failure, a compaction', () => {
  const inline = markers.filter((m) => m.kind === 'inline');
  assert.ok(inline.some((m) => m.ctx === 'main' && m.name === 'implementor'), 'inline skill in main');
  assert.ok(inline.some((m) => m.ctx === started('validator').id && m.name === 'checklist'), 'inline skill inside a forked skill');
  assert.ok(calls.some((r) => r.tool === 'Bash' && r.ok === false), 'a failed call');
  const compact = markers.find((m) => m.kind === 'compact');
  assert.ok(compact, 'a compaction');
  assert.ok(calls.some((r) => r.tool === 'Skill' && Date.parse(r.at) > compact.at), 'a skill after the compaction');
  const fork = calls.find((r) => r.child_agent_type === 'fork');
  const fresh = calls.find((r) => r.name === 'general-purpose');
  assert.ok(Date.parse(fresh.at) - fresh.duration_ms < Date.parse(fork.at), 'two subagents ran at once');
  assert.ok(calls.some((r) => r.tool === 'Agent' && r.name === 'watcher' && r.background), 'a background subagent');
});

test('e2e claude: committed outputs match the current renderer', () => {
  for (const [name, text] of Object.entries(outputs(OUTPUT))) {
    assert.strictEqual(fs.readFileSync(path.join(OUTPUT, name), 'utf8'), text, `${name} is stale: run node e2e/render.js --png`);
  }
});

test('e2e toy: the README example has its skills, one subagent and matching outputs', () => {
  const dir = path.join(__dirname, '..', 'e2e', 'toy', 'output');
  const toy = fs.readFileSync(path.join(dir, 'trace.jsonl'), 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
  const skills = [...new Set(toy.filter((r) => r.tool === 'Skill').map((r) => r.name))];
  assert.deepStrictEqual(skills, ['orchestrator', 'planner', 'implementor', 'validator', 'github']);
  assert.deepStrictEqual(toy.filter((r) => r.tool === 'Agent').map((r) => r.name), ['process-story']);
  for (const [name, text] of Object.entries(outputs(dir))) {
    assert.strictEqual(fs.readFileSync(path.join(dir, name), 'utf8'), text, `${name} is stale: run node e2e/render.js --png`);
  }
});
