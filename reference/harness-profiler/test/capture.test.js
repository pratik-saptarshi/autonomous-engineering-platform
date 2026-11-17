'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const { buildRecord, buildEventRecord, capture, serialize, mask, renderTree, fillContextTokens, contextSpend, contextsOf } = require('../plugin/libexec/hp.js');
const { callColumn, fixtureLines, tempDir, tempRepo, captureFixture, captureContexts, captureBackground } = require('./helpers.js');

const callsOf = (records) => records.filter((r) => r.tool);

const HP = path.join(__dirname, '..', 'plugin', 'libexec', 'hp.sh');

for (const fixture of ['claude-web.jsonl', 'claude-local.jsonl']) {
  test(`${fixture}: one record per tool call and one per session start`, () => {
    const { records } = captureFixture(fixture);
    const calls = fixtureLines(fixture).map((l) => JSON.parse(l)).filter((p) => p.hook_event_name.startsWith('PostToolUse'));
    assert.deepEqual(callsOf(records).map((r) => r.tool_use_id), calls.map((p) => p.tool_use_id));
    assert.deepEqual(records.filter((r) => r.event === 'SessionStart').map((r) => r.source), ['startup']);
    const children = callsOf(records).filter((r) => r.child_agent_id).map((r) => r.child_agent_id);
    assert.deepEqual(records.filter((r) => r.event === 'SubagentStop').map((r) => r.agent_id).sort(), children.sort());
    for (const r of callsOf(records)) {
      assert.equal(r.v, 2);
      assert.equal(r.harness, 'claude');
      assert.equal(r.branch, 'demo');
      assert.match(r.at, /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/);
    }
  });

  test(`${fixture}: Skill, Agent and failed Bash records`, () => {
    const records = callsOf(captureFixture(fixture).records);
    const by = (tool, name) => records.find((r) => r.tool === tool && r.name === name);

    const greet = by('Skill', 'greet');
    assert.equal(greet.child_agent_id, undefined);
    assert.equal(greet.result, undefined, 'an inline skill has no result');

    const review = by('Skill', 'review');
    assert.match(review.child_agent_id, /^a[0-9a-f]{16}$/);
    assert.match(review.result, /^PASS/);
    const reviewBash = records.find((r) => r.agent_id === review.child_agent_id);
    assert.equal(reviewBash.tool, 'Bash');
    assert.equal(reviewBash.agent_type, 'general-purpose');

    const counter = by('Agent', 'counter');
    assert.ok(counter.tokens > 27000);
    assert.equal(counter.result, '3');
    assert.match(counter.args, /^Count words in notes\.txt: Count the words/);

    const failed = by('Bash', 'false');
    assert.equal(failed.ok, false);
    assert.equal(failed.result, 'Exit code 1');
    assert.equal(failed.agent_id, undefined, 'false ran in main while counter worked');
  });
}

test('contexts fixture: subagent types and one compaction', () => {
  const { records } = captureContexts();
  const spawns = callsOf(records).filter((r) => r.child_agent_id);
  assert.deepEqual(spawns.map((r) => [r.tool, r.name, r.child_agent_type]), [
    ['Skill', 'review', undefined],
    ['Agent', 'fork', 'fork'],
    ['Agent', 'general-purpose', 'general-purpose'],
  ]);
  const events = records.filter((r) => !r.tool);
  assert.deepEqual(events.filter((r) => r.event.endsWith('Compact')).map((r) => `${r.event} ${r.trigger}`), ['PreCompact manual', 'PostCompact manual']);
  assert.deepEqual(events.filter((r) => r.event === 'SessionStart').map((r) => r.source), ['startup', 'resume', 'compact', 'resume', 'resume']);
  assert.equal(events.find((r) => r.source === 'resume').context_tokens, 43208);
  for (const r of events) assert.deepEqual(Object.keys(r).filter((k) => k !== 'agent_id').slice(0, 5), ['v', 'harness', 'at', 'session', 'event']);
  const stops = events.filter((r) => r.event === 'SubagentStop');
  assert.deepEqual(stops.map((r) => r.agent_type), ['general-purpose', 'fork', 'general-purpose', undefined], 'the last one is the compaction');
  assert.match(stops[1].result, /^The user's first/);
});

test('a version 1 trace still renders, every subagent fresh', () => {
  const v1 = callsOf(captureContexts().records).map(({ child_agent_type: _, ...r }) => ({ ...r, v: 1 }));
  const lines = callColumn(renderTree(v1));
  assert.match(lines[1], /^fork \(agent\) new context a79e01 \(/);
  assert.equal(lines.length, 4, 'no compaction line without events');
});

test('adds the trace dir to .git/info/exclude once', () => {
  const dir = tempRepo();
  fs.writeFileSync(path.join(dir, '.git', 'info', 'exclude'), '# local\n*.swp');
  captureFixture('claude-web.jsonl', { dir });
  captureFixture('claude-web.jsonl', { dir });
  assert.equal(fs.readFileSync(path.join(dir, '.git', 'info', 'exclude'), 'utf8'), '# local\n*.swp\n.harness-profile/\n');
});

test('worktrees exclude through the common git dir and read their own HEAD', () => {
  const main = tempRepo();
  const wtGit = path.join(main, '.git', 'worktrees', 'wt');
  fs.mkdirSync(wtGit, { recursive: true });
  fs.writeFileSync(path.join(wtGit, 'HEAD'), 'ref: refs/heads/feature/x\n');
  fs.writeFileSync(path.join(wtGit, 'commondir'), '../..\n');
  const wt = tempDir();
  fs.writeFileSync(path.join(wt, '.git'), `gitdir: ${wtGit}\n`);
  const { records } = captureFixture('claude-web.jsonl', { dir: wt });
  assert.equal(callsOf(records)[0].branch, 'feature/x');
  assert.match(fs.readFileSync(path.join(main, '.git', 'info', 'exclude'), 'utf8'), /^\.harness-profile\/$/m);
});

test('a session started below the git root still writes to the root', () => {
  const repo = tempRepo();
  const sub = path.join(repo, 'packages', 'app');
  fs.mkdirSync(sub, { recursive: true });
  const payload = { ...JSON.parse(fixtureLines('claude-web.jsonl')[2]), cwd: sub };
  const file = capture('claude', JSON.stringify(payload), { CLAUDE_PROJECT_DIR: sub });
  assert.equal(file, path.join(repo, '.harness-profile', `${payload.session_id}.jsonl`));
});

test('names: cd prefix dropped, mcp tools shortened, default agent type', () => {
  const base = { session_id: 's', hook_event_name: 'PostToolUse', cwd: '/nonexistent', tool_use_id: 't' };
  const bash = buildRecord({ ...base, tool_name: 'Bash', tool_input: { command: 'cd "/a b" && make test\nmore' } }, 'claude');
  assert.equal(bash.name, 'make test');
  assert.equal(bash.args, 'cd "/a b" && make test ⏎ more');
  const mcp = buildRecord({ ...base, tool_name: 'mcp__github__get_file', tool_input: { path: 'x' } }, 'claude');
  assert.equal(mcp.tool, 'mcp');
  assert.equal(mcp.name, 'get_file');
  assert.equal(mcp.args, '{"path":"x"}');
  const agent = buildRecord({ ...base, tool_name: 'Agent', tool_input: { description: 'd', prompt: 'p' } }, 'claude');
  assert.equal(agent.name, 'general-purpose');
});

test('result: a subagent reply without its tools-used preamble', () => {
  const payload = { session_id: 's', hook_event_name: 'PostToolUse', cwd: '/nonexistent', tool_use_id: 't', tool_name: 'Agent', tool_input: { subagent_type: 'estimator', prompt: 'p' },
    tool_response: { content: [{ type: 'text', text: '<tools-used-before-summary>Bash</tools-used-before-summary>\nS' }] } };
  assert.equal(buildRecord(payload, 'claude').result, 'S');
});

test('result: a SubagentStop message without its tools-used preamble', () => {
  const payload = { session_id: 's', hook_event_name: 'SubagentStop', cwd: '/nonexistent', agent_id: 'a1',
    last_assistant_message: '<tools-used-before-summary>Bash</tools-used-before-summary>\nS' };
  assert.equal(buildEventRecord(payload, 'claude').result, 'S');
});

test('a skill forked in the background records background and no result', () => {
  const payload = { session_id: 's', hook_event_name: 'PostToolUse', cwd: '/nonexistent', tool_use_id: 't', tool_name: 'Skill', tool_input: { skill: 'validator' },
    tool_response: { success: true, commandName: 'validator', status: 'forked', background: true, agentId: 'a1', result: 'Running in the background as @validator' } };
  const record = buildRecord(payload, 'claude');
  assert.equal(record.background, true);
  assert.equal(record.child_agent_id, 'a1');
  assert.equal(record.result, undefined, 'the launch notice is not a result');
});

test('a hand-back records the report as its result', () => {
  const payload = { session_id: 's', hook_event_name: 'PostToolUse', cwd: '/nonexistent', agent_id: 'a1', tool_use_id: 't', tool_name: 'SubagentHandback',
    tool_input: { message: 'Both verdicts are PASS.\n\n- details' }, tool_response: [{ type: 'text', text: '{"success":true,"message":"Report delivered to your caller."}' }] };
  const record = buildRecord(payload, 'claude');
  assert.equal(record.result, 'Both verdicts are PASS.');
  assert.equal(record.args, undefined, 'the report is not repeated as args');
});

test('masks secrets in args, result and secret-looking input keys', () => {
  assert.equal(mask('curl -H "X-Auth: Bearer abcdefghijkl"'), 'curl -H "X-Auth: Bearer [redacted]"');
  assert.doesNotMatch(mask('curl -H "Authorization: Bearer abcdefghijkl"'), /abcdefghijkl/);
  assert.equal(mask('git push https://ghp_abcdefghijklmnop@github.com/x'), 'git push https://[redacted]@github.com/x');
  assert.equal(mask('API_KEY=hunter2hunter2 run'), 'API_KEY=[redacted] run');
  const base = { session_id: 's', hook_event_name: 'PostToolUse', cwd: '/nonexistent', tool_use_id: 't' };
  const r = buildRecord({ ...base, tool_name: 'WebFetch', tool_input: { url: 'u', api_token: 'zzz' }, tool_response: 'token=abc123456789' }, 'claude');
  assert.equal(r.args, '{"url":"u","api_token":"[redacted]"}');
  assert.equal(r.result, 'token=[redacted]');
});

test('a record never exceeds 4096 bytes', () => {
  const record = { v: 1, args: 'x'.repeat(200), result: '€'.repeat(3000) };
  const line = serialize(record);
  assert.ok(Buffer.byteLength(line) <= 4096);
  assert.equal(JSON.parse(line).args.length, 200, 'args shrink only when result alone is not enough');
});

test('the launcher fails open: exit 0, no output, even on garbage', () => {
  const dir = tempRepo();
  for (const input of ['not json', '', fixtureLines('claude-web.jsonl')[2]]) {
    const run = spawnSync('sh', [HP, 'capture', 'claude'], { input, cwd: dir, env: { ...process.env, CLAUDE_PROJECT_DIR: dir } });
    assert.equal(run.status, 0);
    assert.equal(run.stdout.length + run.stderr.length, 0);
  }
  assert.equal(fs.readdirSync(path.join(dir, '.harness-profile')).length, 1);
});

test('the launcher exits 0 silently when it finds no node', () => {
  const env = { PATH: '/nonexistent', HOME: '/nonexistent', HP_NODE: '/nonexistent/node' };
  const run = spawnSync('/bin/sh', [HP, 'capture', 'claude'], { input: '{}', env });
  assert.equal(run.status, 0);
  assert.equal(run.stdout.length + run.stderr.length, 0);
  const doctor = spawnSync('/bin/sh', [HP, 'doctor'], { env });
  assert.equal(doctor.status, 1);
  assert.match(doctor.stderr.toString(), /node not found/);
});

test('the launcher needs nothing on PATH once it has node', () => {
  const run = spawnSync('/bin/sh', [HP, 'capture', 'claude'], { input: '{}', env: { PATH: '/nonexistent', HP_NODE: process.execPath } });
  assert.equal(run.status, 0);
  assert.equal(run.stdout.length + run.stderr.length, 0);
});

test('context tokens come from the transcript line that asked for the call', () => {
  const dir = tempDir();
  const transcript = path.join(dir, 's.jsonl');
  const asked = (id, input, cached) => JSON.stringify({ type: 'assistant', message: { usage: { input_tokens: input, cache_read_input_tokens: cached, cache_creation_input_tokens: 10, output_tokens: 99 }, content: [{ type: 'tool_use', id }] } });
  fs.writeFileSync(transcript, [asked('t1', 2, 42000), '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1"}]}}'].join('\n') + '\n');
  fs.mkdirSync(path.join(dir, 's', 'subagents'), { recursive: true });
  fs.writeFileSync(path.join(dir, 's', 'subagents', 'agent-a1.jsonl'), asked('t2', 1, 26000) + '\n');
  const base = { session_id: 's', hook_event_name: 'PostToolUse', tool_name: 'Bash', tool_input: {}, transcript_path: transcript, cwd: '/nonexistent' };
  assert.equal(buildRecord({ ...base, tool_use_id: 't1' }, 'claude').context_tokens, 42012, 'input + cache read + cache creation, not output');
  assert.equal(buildRecord({ ...base, tool_use_id: 't2', agent_id: 'a1' }, 'claude').context_tokens, 26011, 'a subagent reads its own transcript');
  assert.equal(buildRecord({ ...base, tool_use_id: 't3' }, 'claude').context_tokens, undefined);
  assert.equal(buildRecord({ ...base, tool_use_id: 't1', transcript_path: '/nonexistent.jsonl' }, 'claude').context_tokens, undefined);

  const records = [{ event: 'SessionStart', transcript }, { tool: 'Bash', tool_use_id: 't2' }, { tool: 'Bash', tool_use_id: 't1', context_tokens: 5 }];
  assert.deepEqual(fillContextTokens(records).map((r) => r.context_tokens), [undefined, 26011, 5], 'render time fills what capture missed');
});

test('a context spends every model call it makes, each one reading its history again', () => {
  const dir = tempDir();
  const transcript = path.join(dir, 's.jsonl');
  const turn = (id, cached, extra = {}) => JSON.stringify({ type: 'assistant', message: { id, usage: { input_tokens: 1, cache_read_input_tokens: cached, cache_creation_input_tokens: 10, output_tokens: 9 }, content: [{ type: 'text', text: 'x' }] }, ...extra });
  fs.writeFileSync(transcript, [turn('m1', 1000), turn('m1', 1000), turn('m2', 2000), '{"type":"user","message":{"content":"hi"}}'].join('\n') + '\n');
  fs.mkdirSync(path.join(dir, 's', 'subagents'), { recursive: true });
  fs.writeFileSync(path.join(dir, 's', 'subagents', 'agent-a1.jsonl'), [turn('k1', 500), turn('k2', 600)].join('\n') + '\n');

  const agent = { session_id: 's', hook_event_name: 'PostToolUse', tool_name: 'Agent', tool_use_id: 't1', tool_input: { subagent_type: 'general-purpose' }, tool_response: { agentId: 'a1', agentType: 'general-purpose' }, transcript_path: transcript, cwd: '/nonexistent' };
  const record = buildRecord(agent, 'claude');
  assert.deepEqual(record.child_spend, { new: 22, cached: 1100, out: 18, calls: 2 }, 'input and cache writes are new, cache reads stay apart');

  const spend = contextSpend([{ event: 'SessionStart', transcript }, record]);
  assert.deepEqual(spend.get('main'), { new: 22, cached: 3000, out: 18, calls: 2 }, 'a response split over lines counts once');
  assert.deepEqual(spend.get('a1'), record.child_spend);
  assert.deepEqual(contextSpend([record]).get('a1'), record.child_spend, 'the captured numbers when the transcripts are gone');
  const stop = { event: 'SubagentStop', agent_id: 'a1', spend: { new: 1, cached: 2, out: 3, calls: 4 } };
  assert.deepEqual(contextSpend([record, stop]).get('a1'), stop.spend, 'a background call is captured before its subagent ends');
  assert.match(renderTree([record]), /\n[\d:]+ +0 ms +22 +1\.1k +18 {2}general-purpose \(agent\) new context a1/);
});

test('a background subagent ends at its SubagentStop, and its call names the copy', () => {
  const { records } = captureBackground();
  const agents = callsOf(records).filter((r) => r.tool === 'Agent');
  assert.deepEqual(agents.map((r) => [r.name, r.child_agent_type, r.background, r.result]), [
    ['fork', 'fork', true, undefined],
    ['general-purpose', 'general-purpose', true, undefined],
  ], 'the response says only async_launched, so the type comes from subagent_type');
  assert.deepEqual(contextsOf(records).contexts.map((c) => [c.name, c.kind, c.hue]), [
    [undefined, 'root', 0], ['fork', 'copy', 0], ['general-purpose', 'fresh', 1],
  ]);
  assert.deepEqual(callColumn(renderTree(records)), [
    'fork (agent) new context a0c311, copy of main, background (Count lines in notes.txt…) -> Output of `wc -l no…',
    'general-purpose (agent) new context a47c81, background (Count bytes in notes.txt: …) -> The exact output of …',
  ]);
});
