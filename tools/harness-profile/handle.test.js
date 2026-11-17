'use strict';

// Evals E6-E9b for the opt-in capture handler, plus the three M2 residuals
// carried into C1: live parentage must say which path resolved it, concurrent
// spawns must bind deterministically, and a `session.get` miss must never be
// cached as "no parent".
//
// Parentage order under test: the spawn response (authoritative) reconciles an
// earlier `session.get`/FIFO binding; `session.get` binds while the response is
// in flight; FIFO is provisional. E8, E8d, E8e and E8f cover both arrival orders
// and two out-of-order children. C1's slice is E6-E9b; M3 also needs C2's
// E10-E13, so these tests passing does not close M3.
//
// The handler is the only thing under test here. The `.opencode/plugins/`
// entry point is thin ESM that subscribes and calls `handleEvent`; E9b imports
// it dynamically and asserts the shape opencode 2.3 accepts, so the plugin
// cannot be dead while this suite is green.

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

// Drive one plugin `setup()` against `dir` and resolve once its subscription
// has consumed `events`. The plugin module is ESM and cached per process, which
// is the scope its dedupe promises ("once per process"), so repeated calls here
// exercise the same module-level state a long-lived `opencode serve` would.
async function drivePlugin(dir, events, write) {
  const module = await import(pathToFileURL(PLUGIN).href);
  let delivered = 0;
  const ctx = {
    directory: dir,
    event: {
      subscribe: () => (async function* stream() {
        for (const event of events) {
          delivered += 1;
          yield event;
        }
      })(),
    },
    session: { get: async ({ sessionID }) => ({ id: sessionID }) },
  };
  const dispose = await module.default.setup(ctx, { write });
  for (let i = 0; i < 100 && delivered < events.length; i += 1) {
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  await new Promise((resolve) => setTimeout(resolve, 50));
  await dispose();
  return delivered;
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

// opencode 2.3's spawn response carries `metadata: {sessionID, background}`
// (task tool). A test that isolates a non-response parentage source removes it
// rather than exercising an event shape the runtime does not send.
function withoutSpawnResponse(data) {
  for (const event of data.events) {
    if (event.type === 'session.tool.success' && event.data.id === 'call_spawn') {
      delete event.data.metadata;
    }
  }
  return data;
}

// Two concurrent spawning calls for one parent. `first` is the order in which
// the children's events are observed (which is what FIFO guesses from);
// `responses` is the order in which the spawn responses arrive (which is
// authoritative). opencode 2.3's real metadata is on every response.
function concurrentSpawn({ first, responses }) {
  const root = 'ses_root_concurrent';
  const childA = 'ses_child_a';
  const childB = 'ses_child_b';
  const callOf = { [childA]: 'call_a', [childB]: 'call_b' };
  const events = [
    ['session.tool.input.started', root, 'call_a', 'msg_r', 'subagent', {}],
    ['session.tool.called', root, 'call_a', 'msg_r', '', { agent: 'general', description: 'a', prompt: 'a' }],
    ['session.tool.input.started', root, 'call_b', 'msg_r', 'subagent', {}],
    ['session.tool.called', root, 'call_b', 'msg_r', '', { agent: 'general', description: 'b', prompt: 'b' }],
  ];
  for (const child of first) {
    const suffix = child === childA ? 'a' : 'b';
    const tokens = child === childA ? 1 : 2;
    events.push(
      ['session.tool.input.started', child, `call_r${suffix}`, `msg_${suffix}`, 'read', {}],
      ['session.tool.called', child, `call_r${suffix}`, `msg_${suffix}`, '', { filePath: suffix }],
      ['session.tool.success', child, `call_r${suffix}`, `msg_${suffix}`, '', { content: [{ type: 'text', text: suffix }] }],
      ['session.step.ended', child, '', `msg_${suffix}`, '', { tokens: { input: tokens, output: tokens, reasoning: 0, cache: { read: 0, write: 0 } } }],
    );
  }
  for (const child of responses) {
    events.push([
      'session.tool.success',
      root,
      callOf[child],
      'msg_r',
      '',
      { content: [{ type: 'text', text: 'done' }], metadata: { sessionID: child, background: true } },
    ]);
  }
  events.push(['session.step.ended', root, '', 'msg_r', '', { tokens: { input: 10, output: 10, reasoning: 0, cache: { read: 0, write: 1 } } }]);
  return {
    root,
    childA,
    childB,
    events: events.map(([type, sessionID, id, assistantMessageID, name, data], index) => ({
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
    })),
  };
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

test('E8h: a background spawn ends at the child stop, not at its launch', async () => {
  const dir = scratch();
  const data = fixture('subagent.json');
  // The child's turn ends after the root's steps flushed the spawn record, so
  // the child's SubagentStop is the later of the two ends.
  data.events.push(
    { id: 'evt_child_idle', created: 1794932006000, type: 'session.execution.succeeded', data: { sessionID: CHILD } },
    { id: 'evt_root_idle', created: 1794932007000, type: 'session.execution.succeeded', data: { sessionID: ROOT } },
  );
  const state = handle.createState({
    cwd: dir,
    env: enabled(dir),
    sessionGet: (id) => ({ id, parentID: id === CHILD ? ROOT : undefined }),
  });
  const records = await feed(state, data.events);

  // opencode's `metadata.background` must reach the top level the pinned
  // builder reads; nested, hp.js isBackground() never sees it.
  const spawn = byId(records, 'call_spawn');
  assert.equal(spawn.background, true, 'metadata.background was not promoted to the top level');

  // The pinned renderer decides the duration: withStop extends a background
  // call to its child's SubagentStop; without the flag the call reads as
  // finished and keeps its launch latency.
  const stop = records.find((record) => record.event === 'SubagentStop' && record.agent_id === CHILD);
  assert.ok(stop, 'no child SubagentStop was written');
  const forest = hp.buildForest(records);
  const nodes = [];
  const walk = (list) => {
    for (const node of list) {
      nodes.push(node);
      walk(node.children);
    }
  };
  walk(forest);
  const node = nodes.find((candidate) => candidate.record && candidate.record.tool_use_id === 'call_spawn');
  assert.ok(node, 'the spawn call is not in the forest');
  const start = Date.parse(spawn.at) - (spawn.duration_ms || 0);
  assert.equal(node.record.duration_ms, Date.parse(stop.at) - start, 'the background call kept its launch latency instead of ending at the child stop');
  fs.rmSync(dir, { recursive: true, force: true });
});

test('E8: the spawn response outranks session.get and reconciles its binding (response after FIFO)', async () => {
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

  // Both sources are present. The child's first event binds through the API
  // (and the sole open spawn's FIFO tie-break) before the spawning call ends;
  // the response then arrives and is authoritative, so it reconciles that
  // earlier binding instead of being refused.
  const records = await feed(state, fixture('subagent.json').events);
  const spawn = byId(records, 'call_spawn');

  assert.equal(spawn.tool, 'Agent');
  assert.equal(spawn.name, 'general', 'the real spawn input names the agent');
  assert.equal(spawn.child_agent_id, CHILD, 'the spawning call carries the child session');
  assert.deepEqual(spawn.child_spend, { new: 230, cached: 1100, out: 50, calls: 2 });
  assert.deepEqual(handle.parentageOf(state, CHILD), { parent: ROOT, via: 'spawn-response' });
  assert.equal(handle.spawnResponseOf(state, 'call_spawn'), CHILD);

  // The API really did resolve first (so both sources were present), once.
  assert.ok(looks.includes(CHILD), 'session.get did not run, so this is not the both-sources case');
  assert.equal(looks.filter((id) => id === CHILD).length, 1, `child looked up ${looks.length} times`);

  // Superseding a non-response binding is recorded, not silent.
  assert.deepEqual(handle.reconciliationsOf(state), [
    { spawn: 'call_spawn', from: CHILD, to: CHILD, parent: ROOT },
  ]);
  fs.rmSync(dir, { recursive: true, force: true });
});

test('E8a: session.created is the parentage source only when there is no session API', async () => {
  const dir = scratch();
  // Isolate the event fallback: remove the spawn response's session id, which
  // opencode 2.3 does send, so only `session.created` can bind here.
  const data = withoutSpawnResponse(fixture('subagent.json'));
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
  // No session.get at all and no child events: the response is the only source.
  // opencode 2.3 does return the child id in the spawn response metadata,
  // `{sessionID, background}`; the live smoke's debug sidecar records the same
  // shape (`spawnResponses: [{call, sessionID}]`).
  const data = fixture('subagent.json');
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
  // Isolate the retry: no spawn response session id, so only the API can bind.
  const events = withoutSpawnResponse(fixture('subagent.json')).events;
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

test('E8d: out-of-order concurrent children are corrected by the spawn responses', async () => {
  // Children are observed B then A, so FIFO guesses A<-B and B<-A. Both calls'
  // responses carry 2.3's real metadata (`{sessionID, background}`) and arrive
  // in spawn order, which re-points both calls. The final records must be
  // correct by call, not by observation order.
  const dir = scratch();
  const data = concurrentSpawn({ first: ['ses_child_b', 'ses_child_a'], responses: ['ses_child_a', 'ses_child_b'] });
  const parents = { [data.childA]: data.root, [data.childB]: data.root };
  const state = handle.createState({
    cwd: dir,
    env: enabled(dir),
    sessionGet: (id) => ({ id, parentID: parents[id] }),
  });
  const records = await feed(state, data.events);

  assert.equal(byId(records, 'call_a').child_agent_id, data.childA, 'call_a must carry child A');
  assert.equal(byId(records, 'call_b').child_agent_id, data.childB, 'call_b must carry child B');
  assert.deepEqual(byId(records, 'call_a').child_spend, { new: 1, cached: 0, out: 1, calls: 1 });
  assert.deepEqual(byId(records, 'call_b').child_spend, { new: 2, cached: 0, out: 2, calls: 1 });
  assert.deepEqual(handle.parentageOf(state, data.childA), { parent: data.root, via: 'spawn-response' });
  assert.deepEqual(handle.parentageOf(state, data.childB), { parent: data.root, via: 'spawn-response' });

  // The renderer's own view: two child contexts, neither orphaned.
  const { contexts } = hp.contextsOf(records);
  assert.equal(contexts.filter((context) => context.parent !== undefined).length, 2, 'both children hang off main');

  const reconciled = handle.reconciliationsOf(state);
  assert.equal(reconciled.length, 2, 'both swapped calls must record a reconciliation');
  assert.deepEqual(
    reconciled.map((entry) => `${entry.spawn}:${entry.to}`).sort(),
    ['call_a:ses_child_a', 'call_b:ses_child_b'],
  );
  fs.rmSync(dir, { recursive: true, force: true });
});

test('E8e: the same two children are correct when the responses arrive reversed', async () => {
  // Identical observation order (B then A), but call B's response lands before
  // call A's. Arrival order must not change the final attribution.
  const dir = scratch();
  const data = concurrentSpawn({ first: ['ses_child_b', 'ses_child_a'], responses: ['ses_child_b', 'ses_child_a'] });
  const parents = { [data.childA]: data.root, [data.childB]: data.root };
  const state = handle.createState({
    cwd: dir,
    env: enabled(dir),
    sessionGet: (id) => ({ id, parentID: parents[id] }),
  });
  const records = await feed(state, data.events);

  assert.equal(byId(records, 'call_a').child_agent_id, data.childA);
  assert.equal(byId(records, 'call_b').child_agent_id, data.childB);
  assert.deepEqual(byId(records, 'call_a').child_spend, { new: 1, cached: 0, out: 1, calls: 1 });
  assert.deepEqual(byId(records, 'call_b').child_spend, { new: 2, cached: 0, out: 2, calls: 1 });
  assert.deepEqual(handle.parentageOf(state, data.childA), { parent: data.root, via: 'spawn-response' });
  assert.deepEqual(handle.parentageOf(state, data.childB), { parent: data.root, via: 'spawn-response' });

  const reconciled = handle.reconciliationsOf(state);
  assert.equal(reconciled.length, 2);
  assert.deepEqual(
    reconciled.map((entry) => `${entry.spawn}:${entry.to}`).sort(),
    ['call_a:ses_child_a', 'call_b:ses_child_b'],
  );
  fs.rmSync(dir, { recursive: true, force: true });
});

test('E8f: a response observed first binds the child; later child events do not override it (FIFO after response)', async () => {
  const dir = scratch();
  const data = fixture('subagent.json');
  const response = data.events.find((event) => event.type === 'session.tool.success' && event.data.id === 'call_spawn');
  const childEvents = data.events.filter((event) => event.data.sessionID === CHILD);
  const rest = data.events.filter((event) => event !== response && event.data.sessionID !== CHILD);
  // Arrival order: root call start, spawn response, then every child event.
  const events = [...rest.slice(0, 2), response, ...childEvents, ...rest.slice(2)];

  const looks = [];
  const state = handle.createState({
    cwd: dir,
    env: enabled(dir),
    sessionGet: (id) => {
      looks.push(id);
      return { id, parentID: id === CHILD ? ROOT : undefined };
    },
  });
  const records = await feed(state, events);

  const spawn = byId(records, 'call_spawn');
  assert.equal(spawn.child_agent_id, CHILD);
  // The response already made the child a member of the root tree, so the
  // child's own events never need an API lookup (and cannot be re-bound).
  assert.equal(looks.filter((id) => id === CHILD).length, 0, 'the child was re-resolved after the response bound it');
  assert.deepEqual(handle.parentageOf(state, CHILD), { parent: ROOT, via: 'spawn-response' });
  assert.deepEqual(spawn.child_spend, { new: 230, cached: 1100, out: 50, calls: 2 });
  assert.deepEqual(handle.reconciliationsOf(state), []);
  fs.rmSync(dir, { recursive: true, force: true });
});

test('E8g: one response binds its child and the other call keeps the displaced child', async () => {
  // Both calls complete, but only call A's response carries 2.3's session id
  // (the shape a host that omits metadata for one call produces). FIFO has
  // guessed A<-B and B<-A from the observation order. A's response then takes
  // child A for call A, which must release both stale links: call A's previous
  // guess (child B) and call B's link to the child A is taking. Without the
  // releases, both calls end up claiming child A and child B's spend is lost.
  const dir = scratch();
  const data = concurrentSpawn({ first: ['ses_child_b', 'ses_child_a'], responses: ['ses_child_a', 'ses_child_b'] });
  for (const event of data.events) {
    if (event.type === 'session.tool.success' && event.data.id === 'call_b') delete event.data.metadata;
  }
  const parents = { [data.childA]: data.root, [data.childB]: data.root };
  const state = handle.createState({
    cwd: dir,
    env: enabled(dir),
    sessionGet: (id) => ({ id, parentID: parents[id] }),
  });
  const records = await feed(state, data.events);

  assert.equal(byId(records, 'call_a').child_agent_id, data.childA);
  assert.equal(byId(records, 'call_b').child_agent_id, data.childB, 'the unresponded call double-bound child A');
  assert.deepEqual(byId(records, 'call_a').child_spend, { new: 1, cached: 0, out: 1, calls: 1 });
  assert.deepEqual(byId(records, 'call_b').child_spend, { new: 2, cached: 0, out: 2, calls: 1 });
  assert.deepEqual(handle.parentageOf(state, data.childA), { parent: data.root, via: 'spawn-response' });

  const { contexts } = hp.contextsOf(records);
  assert.deepEqual(contexts.map((context) => context.id).sort(), ['main', data.childA, data.childB].sort(), 'the renderer lost a child context');
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

// D1's operator surface for a capture that quietly writes nothing: the refusal
// reason lives in `state.warnings`, which no operator can read from outside the
// long-lived process. The plugin must therefore copy it to stderr — the
// `opencode serve` log — once per process, not once per event. Without this,
// E11's no-repository refusal and C2's unverifiable-exclusion refusal are
// invisible while the session looks healthy and the trace is simply absent.
test('E14d: the plugin surfaces capture refusals once per process', async () => {
  const previous = process.env.AEP_HARNESS_PROFILE;
  const previousDir = process.env.AEP_HARNESS_PROFILE_DIR;
  const dir = scratch('hp-handle-refusal-');
  process.env.AEP_HARNESS_PROFILE = '1';
  delete process.env.AEP_HARNESS_PROFILE_DIR;

  const writes = [];
  // Injected sink, not a `process.stderr.write` patch: Node's runner may run
  // test files concurrently, and a global stub would capture another file's
  // writes and fail it unpredictably.
  const write = (chunk) => {
    writes.push(String(chunk));
    return true;
  };
  try {
    const events = [
      { type: 'session.created', data: { sessionID: 'ses_refused' } },
      { type: 'session.created', data: { sessionID: 'ses_refused' } },
      { type: 'session.created', data: { sessionID: 'ses_refused' } },
    ];
    await drivePlugin(dir, events, write);

    assert.equal(writes.length, 1, `expected one refusal line for three events, got ${writes.length}: ${writes.join('')}`);
    assert.match(writes[0], /^\[aep-harness-profile\] /, 'the line must name the plugin for the server log');
    assert.match(writes[0], /trace capture skipped/, 'the line must say capture was skipped');
    assert.match(writes[0], /AEP_HARNESS_PROFILE_DIR/, 'the line must name the escape hatch');
    assert.match(writes[0], /no git repository/i, 'the line must carry the refusal reason');
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
    if (previous === undefined) delete process.env.AEP_HARNESS_PROFILE;
    else process.env.AEP_HARNESS_PROFILE = previous;
    if (previousDir === undefined) delete process.env.AEP_HARNESS_PROFILE_DIR;
    else process.env.AEP_HARNESS_PROFILE_DIR = previousDir;
  }
});

// The other half of "once per process": a second `setup()` in the same process
// (the serve reloads a plugin without restarting) must not repeat a warning the
// process already logged. A `Set` scoped to one `setup()` passes the per-event
// test above and fails this one.
test('E14d: a second setup in the same process does not repeat the warning', async () => {
  const previous = process.env.AEP_HARNESS_PROFILE;
  const previousDir = process.env.AEP_HARNESS_PROFILE_DIR;
  const dir = scratch('hp-handle-refusal-once-');
  process.env.AEP_HARNESS_PROFILE = '1';
  delete process.env.AEP_HARNESS_PROFILE_DIR;

  const events = [{ type: 'session.created', data: { sessionID: 'ses_refused_once' } }];
  const first = [];
  const second = [];
  try {
    await drivePlugin(dir, events, (chunk) => {
      first.push(String(chunk));
      return true;
    });
    await drivePlugin(dir, events, (chunk) => {
      second.push(String(chunk));
      return true;
    });

    assert.equal(first.length, 1, `the first setup must log the refusal once, got ${first.length}`);
    assert.equal(second.length, 0, `a second setup repeated the refusal: ${second.join('')}`);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
    if (previous === undefined) delete process.env.AEP_HARNESS_PROFILE;
    else process.env.AEP_HARNESS_PROFILE = previous;
    if (previousDir === undefined) delete process.env.AEP_HARNESS_PROFILE_DIR;
    else process.env.AEP_HARNESS_PROFILE_DIR = previousDir;
  }
});

// A sink that throws (EPIPE on a closed stderr) must not burn the warning: the
// plugin records it as reported only after the write lands, so a later setup
// with a working sink still delivers it once.
test('E14d: a throwing sink does not suppress the warning permanently', async () => {
  const previous = process.env.AEP_HARNESS_PROFILE;
  const previousDir = process.env.AEP_HARNESS_PROFILE_DIR;
  const dir = scratch('hp-handle-refusal-throw-');
  process.env.AEP_HARNESS_PROFILE = '1';
  delete process.env.AEP_HARNESS_PROFILE_DIR;

  const events = [{ type: 'session.created', data: { sessionID: 'ses_refused_throw' } }];
  const writes = [];
  try {
    await drivePlugin(dir, events, () => {
      throw new Error('EPIPE');
    });
    await drivePlugin(dir, events, (chunk) => {
      writes.push(String(chunk));
      return true;
    });

    assert.equal(writes.length, 1, `the warning was lost after a throwing sink: ${writes.length} line(s)`);
    assert.match(writes[0], /trace capture skipped/, 'the recovered line must carry the refusal');
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
    if (previous === undefined) delete process.env.AEP_HARNESS_PROFILE;
    else process.env.AEP_HARNESS_PROFILE = previous;
    if (previousDir === undefined) delete process.env.AEP_HARNESS_PROFILE_DIR;
    else process.env.AEP_HARNESS_PROFILE_DIR = previousDir;
  }
});
