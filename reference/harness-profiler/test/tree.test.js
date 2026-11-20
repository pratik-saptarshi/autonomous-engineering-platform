'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const { renderTree, renderHtml, contextsOf, tree } = require('../plugin/libexec/hp.js');
const { callColumn, captureFixture, captureContexts, tempRepo, WEB_RECEIVED_S } = require('./helpers.js');

const demo = () => captureFixture('claude-web.jsonl', { times: WEB_RECEIVED_S }).records;

test('demo session, Skill and Agent calls only', () => {
  assert.equal(renderTree(demo()), [
    'time     duration             new  cached    out  call',
    '16:21:08     7 ms ▎                               greet (skill) inline',
    '16:21:11     10 s ████████                        review (skill) new context a3628f -> PASS: notes.txt has 3 lines.',
    '16:21:23    7.0 s ██████▋                         counter (agent) new context a0b843 (Count words in notes.txt: Count the …) -> 3',
  ].join('\n'));
});

test('demo session, every call with --verbose', () => {
  const lines = callColumn(renderTree(demo(), { verbose: true }));
  assert.deepEqual(lines.map((l) => l.replace(/ \(Count words.*\) -> 3$/, ' (…) -> 3').replace(/wc -w \S+/, 'wc -w notes.txt')), [
    'greet (skill) inline',
    'date -u (Bash)',
    'review (skill) new context a3628f -> PASS: notes.txt has 3 lines.',
    '  cat notes.txt; echo "---"; wc -l notes.txt (Bash)',
    'false (Bash) failed -> Exit code 1',
    'counter (agent) new context a0b843 (…) -> 3',
    '  wc -w notes.txt (Bash)',
  ]);
});

test('false stays in main although it finished while counter worked', () => {
  const records = demo().map((r) => (r.name === 'false' ? { ...r, at: '2026-11-09T16:21:25.000Z' } : r));
  const lines = callColumn(renderTree(records, { verbose: true }));
  const counter = lines.findIndex((l) => l.startsWith('counter (agent)'));
  assert.ok(lines.indexOf('false (Bash) failed -> Exit code 1') > counter);
});

test('a call whose parent is missing goes under a placeholder', () => {
  const records = demo().filter((r) => r.name !== 'counter');
  const lines = callColumn(renderTree(records));
  assert.equal(lines.at(-1), 'counter (agent) [a0b843] parent not recorded');
  assert.match(callColumn(renderTree(records, { verbose: true })).at(-1), /^  wc -w .* \(Bash\)$/);
});

test('duplicate tool_use_ids print once', () => {
  const records = demo();
  assert.equal(renderTree([...records, ...records]), renderTree(records));
});

test('lines stay under 160 chars without --verbose', () => {
  const records = demo().map((r) => ({ ...r, args: r.args && r.args.repeat(5), result: r.result && r.result.repeat(50) }));
  for (const line of renderTree(records).split('\n')) assert.ok(line.length <= 160, line);
});

test('picks the newest session, a session by prefix, or all sessions of a branch', () => {
  const dir = tempRepo();
  captureFixture('claude-web.jsonl', { dir, times: WEB_RECEIVED_S });
  const older = path.join(dir, '.harness-profile', '11cf7c7a-26c6-42e2-a845-ec55adc4e67a.jsonl');
  const shifted = fs.readFileSync(older, 'utf8').trim().split('\n').map((l) => {
    const r = JSON.parse(l);
    return JSON.stringify({ ...r, session: 'bbbb', at: new Date(Date.parse(r.at) + 3600e3).toISOString(), branch: 'other' });
  });
  fs.writeFileSync(path.join(dir, '.harness-profile', 'bbbb.jsonl'), shifted.join('\n') + '\n');

  assert.match(tree([], dir), /\n17:21:08 +7 ms \S* +greet \(skill\)/);
  assert.match(tree(['11cf'], dir), /\n16:21:08 +7 ms \S* +greet \(skill\)/);
  assert.match(tree(['--branch', 'demo'], dir), /^# session 11cf7c7a-26c6-42e2-a845-ec55adc4e67a \(2026-11-09 16:21:03 UTC\)\ntime +duration/);
  assert.throws(() => tree(['--branch', 'nope'], dir), /No session recorded on branch nope/);
  assert.throws(() => tree(['zzz'], dir), /No session starts with zzz/);
});

test('contexts: main, a fresh forked skill, a copy, a fresh agent', () => {
  const { contexts, markers } = contextsOf(captureContexts().records);
  assert.deepEqual(contexts.map((c) => [c.id.slice(0, 6), c.parent, c.kind, c.label, c.hue]), [
    ['main', undefined, 'root', 'main', 0],
    ['a5cf64', 'main', 'fresh', 'review (skill)', 1],
    ['a79e01', 'main', 'copy', 'fork (agent)', 0],
    ['a674d2', 'main', 'fresh', 'general-purpose (agent)', 2],
  ], 'a copy keeps its parent\'s color, a fresh context gets a new one');
  assert.deepEqual(markers.map((m) => [m.kind, m.ctx, new Date(m.at).toISOString().slice(11, 19), m.trigger || m.name]), [
    ['compact', 'main', '11:58:26', 'manual'],
    ['inline', 'main', '12:00:14', 'greet'],
  ]);
});

test('text names each new context, copies and compactions', () => {
  const lines = callColumn(renderTree(captureContexts().records)).map((l) => (l.startsWith('--') ? l : l.replace(/ (\((?!skill\)|agent\))|->).*$/, '')));
  assert.deepEqual(lines, [
    'review (skill) new context a5cf64',
    'fork (agent) new context a79e01, copy of main',
    'general-purpose (agent) new context a674d2',
    '-- main compacted (manual)',
    'greet (skill) inline',
  ]);
  assert.match(renderTree(captureContexts().records), /\n11:58:26 +-- main compacted/);
});

test('a compaction recorded twice prints once', () => {
  const { records } = captureContexts();
  assert.equal(renderTree([...records, ...records]), renderTree(records));
});

test('color only when asked, one per fresh context, same words', () => {
  const records = captureContexts().records;
  const colored = renderTree(records, { color: true });
  assert.notEqual(colored, renderTree(records));
  assert.equal(colored.replace(/\x1b\[\d+m/g, ''), renderTree(records));
  assert.equal(new Set(colored.match(/\x1b\[3\dm/g)).size, 2);
  assert.match(callColumn(colored)[1], /^fork \(agent\)/, 'the copy of main stays uncolored like main');
});

test('html holds the four contexts and every call', () => {
  const { records, dir } = captureContexts();
  const page = tree(['--format', 'html'], dir);
  assert.match(page, /^<!doctype html>/);
  const data = JSON.parse(page.match(/const D = (.*);\n/)[1]);
  assert.equal(data.contexts.length, 4);
  assert.deepEqual(data.contexts.map((c) => c.kind), ['root', 'fresh', 'copy', 'fresh']);
  assert.equal(data.calls.length, records.filter((r) => r.tool).length);
  assert.doesNotMatch(page, /<(script|link|img)[^>]+(src|href)=["']?(https?:)?\/\//i, 'loads nothing from the network');
});

test('html keeps tool output inert', () => {
  const attack = '</script><img src=x onerror=alert(1)>';
  const records = captureContexts().records.map((r) => (r.tool === 'Agent' ? { ...r, result: attack, name: attack } : r));
  const page = renderHtml({ id: 'x', records });
  assert.equal(page.split('</script>').length, 2, 'only the page closes its script');
  assert.doesNotMatch(page, /<img/);
  assert.equal(JSON.parse(page.match(/const D = (.*);\n/)[1]).calls.find((c) => c.tool === 'Agent').result, attack);
});

test('html wants one session', () => {
  const dir = tempRepo();
  captureFixture('claude-web.jsonl', { dir, times: WEB_RECEIVED_S });
  captureContexts({ dir });
  for (const f of fs.readdirSync(path.join(dir, '.harness-profile'))) {
    const file = path.join(dir, '.harness-profile', f);
    fs.writeFileSync(file, fs.readFileSync(file, 'utf8').replace(/"branch":"demo"/g, '"branch":"same"'));
  }
  assert.throws(() => tree(['--branch', 'same', '--format', 'html'], dir), /one session\. Pick one by id prefix:\n {2}11cf7c7a/);
  assert.throws(() => tree(['--format', 'pdf'], dir), /Unknown format pdf/);
});

test('a background skill ends at its last SubagentStop and shows that result', () => {
  const at = (s) => `2026-11-14T22:${s}.000Z`;
  const call = { v: 2, harness: 'claude', session: 's', at: at('11:50'), tool_use_id: 't1', tool: 'Skill', name: 'validator', duration_ms: 25, ok: true, child_agent_id: 'a1' };
  const stops = [
    { v: 2, harness: 'claude', session: 's', at: at('13:31'), event: 'SubagentStop', agent_id: 'a1', agent_type: 'general-purpose', result: 'Waiting on reviewer.' },
    { v: 2, harness: 'claude', session: 's', at: at('13:44'), event: 'SubagentStop', agent_id: 'a1', agent_type: 'general-purpose', result: '**PASS**' },
  ];
  for (const [label, record] of [
    ['captured as background', { ...call, background: true }],
    ['captured with the launch notice as its result', { ...call, result: 'Running in the background as @validator' }],
  ]) {
    const out = renderTree([record, ...stops]);
    assert.match(out, /114 s .*validator \(skill\).*background.*\*\*PASS\*\*/, label);
    assert.doesNotMatch(out, /Running in the background|Waiting on/, label);
    assert.match(renderTree([record]), /running +validator \(skill\).*background/, `${label}, still running`);
    assert.doesNotMatch(renderTree([record]), /25 ms/, `${label}, still running`);
    const data = (records) => JSON.parse(renderHtml({ id: 'x', records }).match(/const D = (.*);\n/)[1]);
    assert.equal(data([record]).calls[0].running, true, `${label}, still running in the page`);
    assert.equal(data([record, ...stops]).calls[0].running, undefined, label);
    assert.doesNotMatch(renderTree([record]), /Running in the background/, `${label}, still running`);
  }
});

test('a background context shows what it handed back, not a later remark', () => {
  const at = (s) => `2026-11-15T17:${s}.000Z`;
  const base = { v: 2, harness: 'claude', session: 's' };
  const records = [
    { ...base, at: at('57:16'), tool_use_id: 't1', tool: 'Agent', name: 'process-story', duration_ms: 25, ok: true, child_agent_id: 'a1', background: true },
    { ...base, at: at('58:18'), agent_id: 'a1', tool_use_id: 't2', tool: 'SubagentHandback', duration_ms: 7, ok: true, result: 'Both verdicts are PASS.' },
    { ...base, at: at('58:18'), event: 'SubagentStop', agent_id: 'a1', agent_type: 'process-story' },
    { ...base, at: at('58:21'), event: 'SubagentStop', agent_id: 'a1', agent_type: 'process-story', result: 'The completion notice adds nothing new.' },
  ];
  const out = renderTree(records);
  assert.match(out, /65 s .*process-story \(agent\).*background -> Both verdicts are PASS\./);
  assert.doesNotMatch(out, /adds nothing new/);
});
