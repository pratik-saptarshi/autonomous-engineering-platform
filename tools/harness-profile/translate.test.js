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
  const line = hp.serialize(shell);
  assert.ok(Buffer.byteLength(line) < 300, 'a fixture-sized record needs no line fitting');
  assert.equal(shell.args, '{"command":"echo hi"}', 'the pin did not truncate args');

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
  assert.ok(!('child_agent_id' in skill), 'an inline skill starts no context');

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

test('E1b: a credential literal in a tool argument is redacted before the pin sees it', () => {
  const { records } = trace('secrets.json');
  const record = call(records, 'call_secret');

  assert.ok(!record.args.includes('GITHUB_TOKEN=x1'), 'the GITHUB_TOKEN value is gone');
  assert.ok(!record.args.includes('AWS_SECRET_ACCESS_KEY=x2'), 'the AWS_SECRET_ACCESS_KEY value is gone');
  // Mixed case with no underscore between the words: the shapes the round-3
  // rules lost. The pin's own `mask` needs a word boundary and does not help.
  assert.ok(!record.args.includes('secretKey=abc'), 'the camelCase secretKey value is gone');
  assert.ok(!record.args.includes('dbPassword=def'), 'the camelCase dbPassword value is gone');
  assert.ok(record.args.includes('GITHUB_TOKEN=[redacted]'), 'the env-style rule fired');
  assert.ok(record.args.includes('AWS_SECRET_ACCESS_KEY=[redacted]'), 'the _-prefixed name is redacted too');
  assert.ok(record.args.includes('secretKey=[redacted]'), 'the mixed-case name is redacted end to end');
  assert.ok(record.args.split('[redacted]').length - 1 >= 5, 'the Authorization/Bearer value is redacted too');
  assert.ok(!record.args.includes('Bearer fakebear'), 'no Bearer value survives the pin');
  // The profiler's own numbers are not credentials: no rule touches them.
  assert.ok(record.args.includes('input_tokens=109326'), 'input_tokens survives masking');
  assert.ok(record.args.includes('output_tokens=42'), 'output_tokens survives masking');
  assert.equal(record.context_tokens, 10 + 100 + 0);
});

test('redactSecrets covers mixed-case and non-underscore credential names', () => {
  // Round-3's three rules were case-sensitive (env) or demanded an underscore
  // before the word (suffix), so every shape below leaked end to end. One
  // case-insensitive containment rule covers them without a third alternation.
  const redacted = [
    ['GITHUB_TOKEN=x1', 'x1'],
    ['AWS_SECRET_ACCESS_KEY=x2', 'x2'],
    ['client_secret=x3', 'x3'],
    ['--password x4', 'x4'],
    ['TOKEN=x5', 'x5'],
    ['secret_key=abc', 'abc'],
    ['secretKey=abc', 'abc'],
    ['dbPassword=abc', 'abc'],
    ['clientSecret=abc', 'abc'],
    ['awsSecretAccessKey=abc', 'abc'],
    ['credential=abc', 'abc'],
    ['access_key=abc', 'abc'],
  ];
  for (const [input, value] of redacted) {
    const out = translate.redactSecrets(input);
    // Absence of the value is the assertion, never a substring of the output.
    assert.ok(!out.includes(value), `${input} leaked its value: ${out}`);
    // Everything but the value survives, so the record still says which key it was.
    assert.equal(out.replace('[redacted]', ''), input.replace(value, ''), `${input} lost more than its value: ${out}`);
  }
});

test('redactSecrets spares the token-count and tokenizer keys a profiler keeps', () => {
  // The numbers the profile exists to report, plus neighbouring shapes that
  // must not trip the rule. These are the keys opencode actually emits.
  for (const kept of [
    'input_tokens=109326',
    'output_tokens=42',
    'total_tokens=5',
    'tokenizer=cl100k',
    'num_tokens=3',
    'max_tokens=4096',
    'PATH=/usr/bin',
  ]) {
    assert.equal(translate.redactSecrets(kept), kept);
  }
  // The skip is a whole-name test, so it holds next to a real redaction.
  assert.equal(translate.redactSecrets('input_tokens=5 auth_token=abc'), 'input_tokens=5 auth_token=[redacted]');
  // Accepted residue: any other name containing TOKEN is redacted, including a
  // rate metric. A miss costs more than an over-redaction.
  assert.equal(translate.redactSecrets('tokens_per_sec=12'), 'tokens_per_sec=[redacted]');
});

test('redactSecrets keeps JSON quoting, neighbours and CLI forms intact', () => {
  // CLI style, `=` and whitespace alike; a bare space separates only a flag.
  assert.equal(translate.redactSecrets('--password x4'), '--password [redacted]');
  assert.equal(translate.redactSecrets('--token=x5'), '--token=[redacted]');
  assert.equal(translate.redactSecrets('the token budget is 4096'), 'the token budget is 4096');

  // JSON-shaped args keep their quoting and their neighbours: only the value goes.
  assert.equal(
    translate.redactSecrets('{"GITHUB_TOKEN":"x6","b":2}'),
    '{"GITHUB_TOKEN":"[redacted]","b":2}',
  );
  assert.equal(
    translate.redactSecrets('{"env":{"secretKey":"x7"},"cwd":"/w"}'),
    '{"env":{"secretKey":"[redacted]"},"cwd":"/w"}',
  );

  // Nested strings are visited; every other value survives untouched.
  assert.deepEqual(translate.redactSecrets({ command: 'secretKey=x8', count: 2, meta: { ok: true } }), {
    command: 'secretKey=[redacted]',
    count: 2,
    meta: { ok: true },
  });
});

test('redactSecrets fails closed on quoted values containing whitespace', () => {
  // Round 4 balanced the opening quote with a backreference (`[^\s"'&,}]+\4`),
  // and the value class cannot hold a space, so a quoted value with one dropped
  // the whole match and came out intact. A quoted value is now matched as a
  // complete string and replaced whole, quotes kept.
  assert.equal(translate.redactSecrets('GITHUB_TOKEN="a b"'), 'GITHUB_TOKEN="[redacted]"');
  assert.equal(translate.redactSecrets('client_secret="a b"'), 'client_secret="[redacted]"');
  assert.equal(translate.redactSecrets('DB_PASSWORD="hunter two"'), 'DB_PASSWORD="[redacted]"');
  assert.equal(translate.redactSecrets("api_key='sk live 42'"), "api_key='[redacted]'");
  assert.equal(translate.redactSecrets('--password "a b"'), '--password "[redacted]"');

  // The JSON neighbour is the integrity check: the object still parses, and
  // neither word of the value survives.
  const json = '{"client_secret":"a b","x":1}';
  const out = translate.redactSecrets(json);
  assert.equal(out, '{"client_secret":"[redacted]","x":1}');
  assert.deepEqual(JSON.parse(out), { client_secret: '[redacted]', x: 1 });
  assert.ok(!out.includes('a b'), 'the spaced value leaked');

  // An empty quoted value is masked too: the rule never leaves a readable slot.
  assert.equal(translate.redactSecrets('{"token":""}'), '{"token":"[redacted]"}');
});

test('redactSecrets closes the hyphenated-header and unterminated-quote gaps', () => {
  // HTTP header shapes spell KEY with a hyphen and often carry an `X-` prefix.
  // The paired keywords accept `-` as well as `_`; the prefix is preserved and
  // only the value goes.
  assert.equal(translate.redactSecrets('X-API-Key: abc'), 'X-API-Key: [redacted]');
  assert.equal(translate.redactSecrets('x-api-key=abc'), 'x-api-key=[redacted]');
  assert.equal(translate.redactSecrets('api-key=abc'), 'api-key=[redacted]');
  assert.equal(translate.redactSecrets('X-ACCESS-KEY: abc'), 'X-ACCESS-KEY: [redacted]');

  // A closing quote clipped by the 200-char args limit must not fail open. The
  // quoted span runs to the closing quote or to end of line, so every word of
  // the value is gone; only the opening quote is restored, never a fabricated
  // closer.
  assert.equal(translate.redactSecrets('TOKEN="a b'), 'TOKEN="[redacted]');
  assert.equal(translate.redactSecrets("client_secret='x y"), "client_secret='[redacted]");

  for (const [input, value] of [
    ['X-API-Key: abc', 'abc'],
    ['x-api-key=abc', 'abc'],
    ['api-key=abc', 'abc'],
    ['TOKEN="a b', 'a b'],
    ["client_secret='x y", 'x y'],
  ]) {
    const out = translate.redactSecrets(input);
    assert.ok(!out.includes(value), `${input} leaked its value: ${out}`);
  }
});

test('redactSecrets stays linear on a pathological single-token blob', () => {
  // The previous pattern's unbounded name runs backtracked cubically here:
  // 8 KB of repeated `TOKEN` took 14.4 s inside a capture hook. The bounded
  // rule measures ~0.01 ms; the budget only has to catch a return to cubic
  // behaviour, so it is set well above jitter and far below the old number.
  const blob = 'TOKEN'.repeat(1638); // 8190 bytes, no separator anywhere
  const started = process.hrtime.bigint();
  const redacted = translate.redactSecrets(blob);
  const ms = Number(process.hrtime.bigint() - started) / 1e6;

  assert.equal(redacted, blob, 'nothing in the blob is a key, so nothing changes');
  assert.ok(ms < 100, `8 KB blob took ${ms.toFixed(1)} ms — the name runs are unbounded again`);
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
