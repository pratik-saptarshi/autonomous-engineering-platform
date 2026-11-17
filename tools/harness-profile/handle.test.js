'use strict';

// Evals E6-E9b for the opt-in capture handler, plus the three M2 residuals
// carried into C1: live parentage must say which path resolved it, concurrent
// spawns must bind deterministically, and a `session.get` miss must never be
// cached as "no parent".
//
// The handler is the only thing under test here. The `.opencode/plugins/`
// entry point is thin ESM that subscribes and calls `handleEvent`; E9b imports
// it dynamically and asserts the shape opencode 2.3 accepts, so M3 cannot pass
// while the plugin is dead.

const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const handle = require('./handle.js');
const hp = require('../../reference/harness-profiler/plugin/libexec/hp.js');

const EVENTS = path.join(__dirname, 'testdata', 'events');
const PLUGIN = path.join(__dirname, '..', '..', '.opencode', 'plugins', 'harness-profile.js');
const ROOT = 'ses_root_agent';
const CHILD = 'ses_child_agent';

function fixture(name) {
  return JSON.parse(fs.readFileSync(path.join(EVENTS, name), 'utf8'));
}

// A temp git root. A real `.git` directory is enough for root discovery and
// `info/exclude`; no git binary is needed.
function repo(prefix = 'hp-handle-') {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  fs.mkdirSync(path.join(root, '.git'), { recursive: true });
  return root;
}

function scratch(prefix = 'hp-handle-dir-') {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function enabled(dir, extra = {}) {
  return { AEP_HARNESS_PROFILE: '1', AEP_HARNESS_PROFILE_DIR: dir, ...extra };
}

async function feed(state, events) {
  const records = [];
  for (const event of events) {
    const out = await handle.handleEvent(event, state);
    if (out) records.push(...out);
  }
  return records;
}

function byId(records, id) {
  const found = records.find((record) => record.tool_use_id === id);
  assert.ok(found, `no record for ${id}`);
  return found;
}

test('E6: without AEP_HARNESS_PROFILE handleEvent is inert', async () => {
  const root = repo();
  const cwd = path.join(root, 'a', 'b');
  fs.mkdirSync(cwd, { recursive: true });
  let lookedUp = 0;
  const state = handle.createState({
    cwd,
    env: {},
    // Inert means the API is not consulted either.
    sessionGet: () => {
      lookedUp += 1;
      return { id: ROOT };
    },
  });

  const data = fixture('tool-calls.json');
  for (const event of data.events) {
    assert.equal(await handle.handleEvent(event, state), null, `not inert on ${event.type}`);
  }

  assert.equal(lookedUp, 0, 'the inert path called session.get');
  assert.equal(fs.existsSync(path.join(root, '.harness-profile')), false, 'a trace directory was created');
  assert.equal(fs.existsSync(path.join(root, '.git', 'info', 'exclude')), false, 'the exclusion was written');
  assert.deepEqual(state.errors, []);
  fs.rmSync(root, { recursive: true, force: true });
});

test('E6b: an explicit off value is inert too', async () => {
  const root = repo();
  const state = handle.createState({ cwd: root, env: { AEP_HARNESS_PROFILE: '0' } });
  const data = fixture('tool-calls.json');
  for (const event of data.events) assert.equal(await handle.handleEvent(event, state), null);
  assert.equal(fs.existsSync(path.join(root, '.harness-profile')), false);
  fs.rmSync(root, { recursive: true, force: true });
});

test('E7: one record per call with durations paired from the event envelope', async () => {
  const dir = scratch();
  const state = handle.createState({ cwd: dir, env: enabled(dir) });
  const records = await feed(state, fixture('tool-calls.json').events);

  assert.deepEqual(records.map((record) => record.tool_use_id).sort(), ['call_read', 'call_shell', 'call_skill']);

  const shell = byId(records, 'call_shell');
  assert.equal(shell.duration_ms, 1794931114300 - 1794931110200);
  assert.equal(shell.ok, true);
  assert.equal(shell.tool, 'shell');

  const failed = byId(records, 'call_read');
  assert.equal(failed.duration_ms, 1794931120500 - 1794931120100);
  assert.equal(failed.ok, false);

  // A record is built only after its step's tokens arrive, never at the
  // completion event: the completion is buffered and flushed at step.ended.
  assert.ok(records.every((record) => Number.isFinite(record.context_tokens)), 'a record was built without its step');
  assert.deepEqual(state.errors, []);
  fs.rmSync(dir, { recursive: true, force: true });
});

test('E7b: step tokens join a specific call by assistantMessageID (non-zero cache.write)', async () => {
  const dir = scratch();
  const state = handle.createState({ cwd: dir, env: enabled(dir) });
  const records = await feed(state, fixture('tool-calls.json').events);

  const shell = byId(records, 'call_shell');
  assert.equal(shell.context_tokens, 14 + 109312 + 0);
  const skill = byId(records, 'call_skill');
  // The Phase 0 gap: every sample had cache.write = 0; this step has 2048.
  assert.equal(skill.context_tokens, 86 + 109184 + 2048);
  assert.notEqual(skill.context_tokens, 86 + 109184);
  fs.rmSync(dir, { recursive: true, force: true });
});

test('E7c: a child turn-end records its spend so the live tree has no blank child column', async () => {
  const dir = scratch();
  const data = fixture('subagent.json');
  data.events.push(
    {
      id: 'evt_child_idle',
      created: 1794932002500,
      type: 'session.execution.succeeded',
      data: { sessionID: CHILD },
    },
    {
      id: 'evt_root_idle',
      created: 1794932004200,
      type: 'session.execution.succeeded',
      data: { sessionID: ROOT },
    },
  );
  const state = handle.createState({
    cwd: dir,
    env: enabled(dir),
    sessionGet: (id) => ({ id, parentID: id === CHILD ? ROOT : undefined }),
  });
  const records = await feed(state, data.events);

  const childStop = records.find((record) => record.event === 'SubagentStop' && record.agent_id === CHILD);
  assert.ok(childStop, 'no child SubagentStop was written');
  assert.deepEqual(childStop.spend, { new: 230, cached: 1100, out: 50, calls: 2 });

  const spend = hp.contextSpend(records);
  assert.deepEqual(spend.get(CHILD), { new: 230, cached: 1100, out: 50, calls: 2 });
  assert.deepEqual(spend.get('main'), { new: 170, cached: 4150, out: 20, calls: 2 });
  fs.rmSync(dir, { recursive: true, force: true });
});

test('E8: parentage arrives through ctx.session.get().parentID and says so', async () => {
  const dir = scratch();
  const parents = { [CHILD]: ROOT };
  const looks = [];
  const state = handle.createState({
    cwd: dir,
    env: enabled(dir),
    sessionGet: (id) => {
      looks.push(id);
      return { id, parentID: parents[id] };
    },
  });

  const records = await feed(state, fixture('subagent.json').events);
  const spawn = byId(records, 'call_spawn');

  assert.equal(spawn.tool, 'Agent');
  assert.equal(spawn.name, 'general', 'the real spawn input names the agent');
  assert.equal(spawn.child_agent_id, CHILD, 'the spawning call carries the child session');
  assert.deepEqual(handle.parentageOf(state, CHILD), { parent: ROOT, via: 'session.get' });

  // `session.get` is consulted once per session, only while its parent is
  // unknown, and not again after the answer arrives.
  assert.equal(looks.filter((id) => id === CHILD).length, 1, `child looked up ${looks.length} times`);
  fs.rmSync(dir, { recursive: true, force: true });
});

test('E8a: session.created is the parentage source only when there is no session API', async () => {
  const dir = scratch();
  const data = fixture('subagent.json');
  // `session.created` for a child arrives after the spawning call started, as
  // it must for any parentage source to find the open spawn.
  data.events.splice(2, 0, {
    id: 'evt_created_child',
    created: 1794932000090,
    type: 'session.created',
    data: { sessionID: CHILD, parentID: ROOT },
  });
  const state = handle.createState({ cwd: dir, env: enabled(dir) });
  const records = await feed(state, data.events);

  assert.equal(byId(records, 'call_spawn').child_agent_id, CHILD);
  assert.deepEqual(handle.parentageOf(state, CHILD), { parent: ROOT, via: 'session.created' });
  fs.rmSync(dir, { recursive: true, force: true });
});

test('E8b: a spawn response carrying a session id binds that child, and says so', async () => {
  const dir = scratch();
  // No session.get at all: the response is the only source. This is the path a
  // host takes when it does return the child id; the live smoke asserts that
  // opencode 2.3 does not, which is why the API path is the one that fires.
  const data = fixture('subagent.json');
  for (const event of data.events) {
    if (event.type === 'session.tool.success' && event.data.id === 'call_spawn') {
      event.data.metadata = { ...(event.data.metadata || {}), sessionID: CHILD };
    }
  }
  const state = handle.createState({ cwd: dir, env: enabled(dir) });
  // Only the root's events: a child session that appeared before the response
  // would have been rooted on its own, which is the documented limitation.
  const events = data.events.filter((event) => event.data.sessionID !== CHILD);
  const records = await feed(state, events);

  const spawn = byId(records, 'call_spawn');
  assert.equal(spawn.child_agent_id, CHILD);
  assert.deepEqual(handle.parentageOf(state, CHILD), { parent: ROOT, via: 'spawn-response' });
  assert.equal(handle.spawnResponseOf(state, 'call_spawn'), CHILD);
  fs.rmSync(dir, { recursive: true, force: true });
});

test('E8c: a session.get miss is retried, never cached as "no parent"', async () => {
  const dir = scratch();
  let childLookups = 0;
  const answers = [
    undefined, // first event: the API cannot answer yet
    { id: CHILD, parentID: ROOT },
  ];
  const events = fixture('subagent.json').events;
  const state = handle.createState({
    cwd: dir,
    env: enabled(dir),
    sessionGet: (id) => {
      if (id === CHILD) {
        childLookups += 1;
        return answers[Math.min(childLookups - 1, answers.length - 1)];
      }
      return { id };
    },
  });

  const records = await feed(state, events);
  const spawn = byId(records, 'call_spawn');

  assert.equal(spawn.child_agent_id, CHILD, 'the retry after the miss bound the child');
  assert.deepEqual(handle.parentageOf(state, CHILD), { parent: ROOT, via: 'session.get' });
  assert.ok(childLookups >= 2, 'a miss was cached instead of retried');
  fs.rmSync(dir, { recursive: true, force: true });
});

test('E8d: concurrent spawns bind FIFO to the first observed child', async () => {
  // Two spawning calls are open for the same parent when both children appear.
  // There is no spawn-call -> child API, so the branch that used to produce
  // `parent not recorded` must pick deterministically: the first child session
  // whose parent is learned binds to the earliest-started still-open call.
  const dir = scratch();
  const root = 'ses_root_concurrent';
  const childA = 'ses_child_a';
  const childB = 'ses_child_b';
  const parents = { [childA]: root, [childB]: root };
  const events = [
    ['session.tool.input.started', root, 'call_a', 'msg_r', 'subagent', {}],
    ['session.tool.called', root, 'call_a', 'msg_r', '', { agent: 'general', description: 'a', prompt: 'a' }],
    ['session.tool.input.started', root, 'call_b', 'msg_r', 'subagent', {}],
    ['session.tool.called', root, 'call_b', 'msg_r', '', { agent: 'general', description: 'b', prompt: 'b' }],
    ['session.tool.input.started', childA, 'call_ra', 'msg_a', 'read', {}],
    ['session.tool.called', childA, 'call_ra', 'msg_a', '', { filePath: 'a' }],
    ['session.tool.success', childA, 'call_ra', 'msg_a', '', { content: [{ type: 'text', text: 'a' }] }],
    ['session.step.ended', childA, '', 'msg_a', '', { tokens: { input: 1, output: 1, reasoning: 0, cache: { read: 0, write: 0 } } }],
    ['session.tool.input.started', childB, 'call_rb', 'msg_b', 'read', {}],
    ['session.tool.called', childB, 'call_rb', 'msg_b', '', { filePath: 'b' }],
    ['session.tool.success', childB, 'call_rb', 'msg_b', '', { content: [{ type: 'text', text: 'b' }] }],
    ['session.step.ended', childB, '', 'msg_b', '', { tokens: { input: 2, output: 2, reasoning: 0, cache: { read: 0, write: 0 } } }],
    ['session.tool.success', root, 'call_a', 'msg_r', '', { content: [{ type: 'text', text: 'da' }] }],
    ['session.tool.success', root, 'call_b', 'msg_r', '', { content: [{ type: 'text', text: 'db' }] }],
    ['session.step.ended', root, '', 'msg_r', '', { tokens: { input: 10, output: 10, reasoning: 0, cache: { read: 0, write: 1 } } }],
  ].map(([type, sessionID, id, assistantMessageID, name, data], index) => ({
    id: `evt_${index}`,
    created: 1800000000000 + index * 100,
    type,
    data: {
      sessionID,
      assistantMessageID,
      ...(id ? { id } : {}),
      ...(name ? { name } : {}),
      ...data,
    },
  }));

  const state = handle.createState({
    cwd: dir,
    env: enabled(dir),
    sessionGet: (id) => ({ id, parentID: parents[id] }),
  });
  const records = await feed(state, events);

  assert.equal(byId(records, 'call_a').child_agent_id, childA, 'the earliest open spawn took the first child');
  assert.equal(byId(records, 'call_b').child_agent_id, childB, 'the second spawn took the second child');
  assert.deepEqual(handle.parentageOf(state, childA), { parent: root, via: 'session.get' });
  assert.deepEqual(handle.parentageOf(state, childB), { parent: root, via: 'session.get' });

  // The renderer's own view: two child contexts, neither orphaned.
  const { contexts } = hp.contextsOf(records);
  assert.equal(contexts.filter((context) => context.parent !== undefined).length, 2, 'both children hang off main');
  fs.rmSync(dir, { recursive: true, force: true });
});

test('E9: trace dir honors AEP_HARNESS_PROFILE_DIR, else the git root; exclusion is unconditional and 0600', async () => {
  const root = repo();
  const cwd = path.join(root, 'a', 'b');
  fs.mkdirSync(cwd, { recursive: true });

  // The pin only calls its exclusion on first directory creation. Pre-create it
  // so this asserts our unconditional path, not the pin's.
  fs.mkdirSync(path.join(root, '.harness-profile'), { recursive: true });

  const state = handle.createState({ cwd, env: { AEP_HARNESS_PROFILE: '1' } });
  await feed(state, fixture('tool-calls.json').events);

  const file = path.join(root, '.harness-profile', 'ses_root_tools.jsonl');
  assert.ok(fs.existsSync(file), 'the default trace did not land at the git root');
  assert.equal(fs.statSync(file).mode & 0o777, 0o600, 'a new trace file must be 0600');

  const excludeFile = path.join(root, '.git', 'info', 'exclude');
  const exclude = fs.readFileSync(excludeFile, 'utf8');
  assert.equal(exclude.split(/\r?\n/).filter((line) => line === '.harness-profile/').length, 1, 'exclusion written exactly once');

  // Idempotent: a second capture through the same root does not append again.
  const second = handle.createState({ cwd, env: { AEP_HARNESS_PROFILE: '1' } });
  await feed(second, fixture('tool-calls.json').events);
  assert.equal(
    fs.readFileSync(excludeFile, 'utf8').split(/\r?\n/).filter((line) => line === '.harness-profile/').length,
    1,
    'the exclusion was appended twice',
  );

  // Override wins over the git root.
  const override = scratch();
  const overridden = handle.createState({ cwd, env: enabled(override) });
  await feed(overridden, fixture('tool-calls.json').events);
  const overriddenFile = path.join(override, 'ses_root_tools.jsonl');
  assert.ok(fs.existsSync(overriddenFile), 'AEP_HARNESS_PROFILE_DIR was ignored');
  assert.equal(fs.statSync(overriddenFile).mode & 0o777, 0o600);

  fs.rmSync(root, { recursive: true, force: true });
  fs.rmSync(override, { recursive: true, force: true });
});

test('E9b: the plugin module has the shape opencode 2.3 accepts', async () => {
  const previous = process.env.AEP_HARNESS_PROFILE;
  const previousDir = process.env.AEP_HARNESS_PROFILE_DIR;
  delete process.env.AEP_HARNESS_PROFILE;
  delete process.env.AEP_HARNESS_PROFILE_DIR;
  try {
    const module = await import(pathToFileURL(PLUGIN).href);
    const definition = module.default;
    // Plain ESM default object. Never Plugin.define, never deep equality on a
    // framework's opaque wrapper: 2.3's loader rejects anything but `{id, setup}`.
    assert.equal(typeof definition, 'object');
    assert.ok(definition, 'no default export');
    assert.equal(typeof definition.id, 'string');
    assert.ok(definition.id.trim().length > 0, 'the plugin id is empty');
    const setup = definition.setup || definition.effect;
    assert.equal(typeof setup, 'function', 'the plugin exposes no callable setup/effect');

    let subscriptions = 0;
    let signal;
    const ctx = {
      directory: scratch(),
      event: {
        subscribe(options) {
          subscriptions += 1;
          signal = options && options.signal;
          return (async function* empty() {})();
        },
      },
      session: { get: async ({ sessionID }) => ({ id: sessionID }) },
    };
    const dispose = await setup(ctx);
    assert.equal(subscriptions, 1, 'the plugin must register exactly one subscription');
    assert.ok(signal instanceof AbortSignal, 'the subscription has no abort signal');
    assert.equal(typeof dispose, 'function', 'setup returns no disposer');
    await dispose();
    assert.equal(signal.aborted, true, 'the disposer did not abort the subscription');
    fs.rmSync(ctx.directory, { recursive: true, force: true });
  } finally {
    if (previous === undefined) delete process.env.AEP_HARNESS_PROFILE;
    else process.env.AEP_HARNESS_PROFILE = previous;
    if (previousDir === undefined) delete process.env.AEP_HARNESS_PROFILE_DIR;
    else process.env.AEP_HARNESS_PROFILE_DIR = previousDir;
  }
});
