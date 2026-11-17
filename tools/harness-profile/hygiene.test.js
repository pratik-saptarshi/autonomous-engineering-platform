'use strict';

// Hygiene evals E10-E13 for the opt-in capture handler. C1's E6-E9b proved the
// capture records the right thing; these prove it stays out of git and cannot
// grow without bound.
//
// E10 pre-existing trace dir: the pin calls its exclusion only when it creates
//     the directory, so a `.harness-profile/` that already exists would stay
//     visible to git without the handler's own unconditional write. The test
//     pre-creates the directory, then asserts the repository's `info/exclude`
//     is the source `git check-ignore -v` names. E10b repeats it with the
//     committed `.gitignore` layer present, so both layers are shown to hold and
//     the attribution case stays in a repo whose `.gitignore` has only `dist/`.
// E11 no git repository and no explicit dir: fail closed. The trace could not
//     be excluded from git, so no record (masked or not) is written into an
//     unprotected directory; the handler records one warning instead. An
//     explicit `AEP_HARNESS_PROFILE_DIR` is the documented escape hatch and is
//     tested here too. E11b covers the other unprotected shapes: a repository
//     whose `info/exclude` cannot be written (EACCES) and a malformed `.git`
//     file. Both must write nothing; the old guard only asked whether a git
//     root existed, so both wrote a committable trace. E11c adds the explicit
//     in-repo rule, and E11d proves it judges the resolved path, so a symlink
//     into the work tree is refused while one outside it still captures.
// E12 concurrent writers: two processes append to the same session file. Every
//     line must be one complete record; a writer that emits the body and the
//     newline as separate appends interleaves them.
// E13 retention: age-prune with a default window plus a hard byte ceiling, both
//     env-overridable, idempotent, and limited to this writer's own `ses_*`
//     trace names, so a shared explicit directory keeps foreign files.
//
// The concurrency test uses real processes: in-process appends are serialized
// by JavaScript, so only separate processes can interleave at the write(2)
// level, which is the failure mode this eval exists for.

const test = require('node:test');
const assert = require('node:assert');
const { execFileSync, spawn } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { setTimeout: sleep } = require('node:timers/promises');

const handle = require('./handle.js');

const EVENTS = path.join(__dirname, 'testdata', 'events');
const ROOT = 'ses_root_hygiene';
const DAY = 24 * 60 * 60 * 1000;

function fixture(name) {
  return JSON.parse(fs.readFileSync(path.join(EVENTS, name), 'utf8'));
}

function scratch(prefix = 'hp-hygiene-') {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

// A real git repository: E10 asserts through `git check-ignore` and
// `git status`, so a bare `.git` directory is not enough here.
function gitRepo(prefix = 'hp-hygiene-repo-') {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  execFileSync('git', ['init', '-q', root], { stdio: 'ignore' });
  return root;
}

function enabled(extra = {}) {
  return { AEP_HARNESS_PROFILE: '1', ...extra };
}

async function feed(state, events) {
  const records = [];
  for (const event of events) {
    const out = await handle.handleEvent(event, state);
    if (out) records.push(...out);
  }
  return records;
}

function touch(dir, name, ageDays, { now = Date.now(), body = '{"v":2}\n' } = {}) {
  const file = path.join(dir, name);
  fs.writeFileSync(file, body);
  const when = new Date(now - ageDays * DAY);
  fs.utimesSync(file, when, when);
  return file;
}

function names(files) {
  return files.map((file) => path.basename(file)).sort();
}

test('E10: a pre-existing trace dir is excluded through the repository info/exclude, not a .gitignore', async () => {
  const root = gitRepo();
  const cwd = path.join(root, 'a', 'b');
  fs.mkdirSync(cwd, { recursive: true });
  // A copy that already ran capture: the directory and a trace exist before
  // this handler sees its first event. That is the case the pin's own capture
  // skips (it only excludes when it creates the directory).
  fs.mkdirSync(path.join(root, '.harness-profile'), { recursive: true });
  fs.writeFileSync(path.join(root, '.harness-profile', 'ses_previous.jsonl'), '{"v":2}\n');
  // An unrelated committed ignore file, so precedence is exercised rather than
  // assumed: the entry under test is the runtime one, not this file's.
  fs.writeFileSync(path.join(root, '.gitignore'), 'dist/\n');

  const state = handle.createState({ cwd, env: enabled() });
  const records = await feed(state, fixture('tool-calls.json').events);
  assert.ok(records.length > 0, 'the capture wrote no records');

  const dir = path.join(root, '.harness-profile');
  const file = path.join(dir, 'ses_root_tools.jsonl');
  assert.ok(fs.existsSync(file), 'the default trace did not land at the git root');
  assert.equal(fs.statSync(file).mode & 0o777, 0o600, 'a new trace file must be 0600');

  const excludeFile = path.join(root, '.git', 'info', 'exclude');
  const entry = () => (fs.existsSync(excludeFile)
    ? fs.readFileSync(excludeFile, 'utf8').split(/\r?\n/).filter((line) => line === '.harness-profile/').length
    : 0);
  assert.equal(entry(), 1, 'the exclusion was not written exactly once');

  // The required end-to-end check: git itself ignores the pre-existing dir, and
  // the source it names is the repository's info/exclude.
  const ignoreSource = () => {
    const checked = execFileSync('git', ['-C', root, 'check-ignore', '-v', '.harness-profile/x'], { encoding: 'utf8' }).trim();
    const match = /^(.*):(\d+):(.*)\t(.*)$/.exec(checked);
    assert.ok(match, `unexpected check-ignore output: ${checked}`);
    assert.equal(match[3], '.harness-profile/', 'the matching pattern is not the trace dir');
    assert.equal(match[4], '.harness-profile/x');
    return fs.realpathSync(path.resolve(root, match[1]));
  };
  const excludeReal = fs.realpathSync(excludeFile);
  assert.equal(ignoreSource(), excludeReal, 'check-ignore did not name the repository info/exclude');
  assert.deepEqual(execFileSync('git', ['-C', root, 'status', '--porcelain', '--', '.harness-profile'], { encoding: 'utf8' }), '', 'the ledger is visible to git status');
  assert.deepEqual(state.errors, []);

  // Idempotent: a second capture writes no second entry and stays ignored.
  const second = handle.createState({ cwd, env: enabled() });
  await feed(second, fixture('tool-calls.json').events);
  assert.equal(entry(), 1, 'the exclusion was appended twice');
  assert.equal(ignoreSource(), excludeReal);
  assert.deepEqual(execFileSync('git', ['-C', root, 'status', '--porcelain', '--', '.harness-profile'], { encoding: 'utf8' }), '');

  fs.rmSync(root, { recursive: true, force: true });
});

test('E10b: with the committed .gitignore layer present, both layers hold and info/exclude still gets the entry', async () => {
  const root = gitRepo();
  const cwd = path.join(root, 'a', 'b');
  fs.mkdirSync(cwd, { recursive: true });
  fs.mkdirSync(path.join(root, '.harness-profile'), { recursive: true });
  fs.writeFileSync(path.join(root, '.harness-profile', 'ses_previous.jsonl'), '{"v":2}\n');
  // The committed layer, exactly as this repository ships it.
  fs.writeFileSync(path.join(root, '.gitignore'), 'dist/\n/.harness-profile/\n');

  const state = handle.createState({ cwd, env: enabled() });
  const records = await feed(state, fixture('tool-calls.json').events);
  assert.ok(records.length > 0, 'the capture wrote no records');
  assert.deepEqual(state.warnings, [], 'a writable repository is not a refusal');

  // Layer 1: the runtime entry is still written and readable as the exact line.
  const excludeFile = path.join(root, '.git', 'info', 'exclude');
  const entries = fs.readFileSync(excludeFile, 'utf8').split(/\r?\n/).filter((line) => line === '.harness-profile/');
  assert.equal(entries.length, 1, 'the runtime entry was not written exactly once');

  // Layer 2: git ignores the trace, and the committed file is what names it
  // (per-directory .gitignore outranks $GIT_DIR/info/exclude). The attribution
  // proof for the runtime write lives in E10's own dist/-only repo above.
  const checked = execFileSync('git', ['-C', root, 'check-ignore', '-v', '.harness-profile/x'], { encoding: 'utf8' }).trim();
  const match = /^(.*):(\d+):(.*)\t(.*)$/.exec(checked);
  assert.ok(match, `unexpected check-ignore output: ${checked}`);
  assert.equal(fs.realpathSync(path.resolve(root, match[1])), fs.realpathSync(path.join(root, '.gitignore')));
  assert.deepEqual(execFileSync('git', ['-C', root, 'status', '--porcelain', '--', '.harness-profile'], { encoding: 'utf8' }), '', 'the ledger is visible to git status');

  fs.rmSync(root, { recursive: true, force: true });
});

test('E11: with no git repository and no explicit dir, capture writes nothing (fail closed)', async () => {
  // A temp directory with no `.git` anywhere above it. The default trace dir
  // would be `.harness-profile/` here, unprotected: git could commit it.
  const dir = scratch('hp-hygiene-nogit-');
  const state = handle.createState({ cwd: dir, env: enabled() });
  const records = await feed(state, fixture('tool-calls.json').events);

  assert.deepEqual(records, [], 'a record was returned from an unprotected directory');
  assert.equal(fs.existsSync(path.join(dir, '.harness-profile')), false, 'a trace directory was created without a git root');
  assert.deepEqual(fs.readdirSync(dir), [], 'capture left files in an unprotected directory');
  assert.equal(state.warnings.length, 1, 'the refusal must be recorded once, not per event');
  assert.match(state.warnings[0], /no git repository/i);
  assert.match(state.warnings[0], /AEP_HARNESS_PROFILE_DIR/, 'the warning must name the escape hatch');
  assert.deepEqual(state.errors, []);

  // The explicit override is the documented escape hatch: the operator names the
  // destination, so capture is allowed outside a repository (E9 already relies
  // on this for tests and ad-hoc capture).
  const override = scratch('hp-hygiene-override-');
  const explicit = handle.createState({ cwd: dir, env: enabled({ AEP_HARNESS_PROFILE_DIR: override }) });
  const written = await feed(explicit, fixture('tool-calls.json').events);
  assert.ok(written.length > 0, 'the explicit override wrote nothing');
  assert.ok(fs.existsSync(path.join(override, 'ses_root_tools.jsonl')));
  assert.deepEqual(explicit.warnings, [], 'an explicit destination is not a refusal');

  fs.rmSync(dir, { recursive: true, force: true });
  fs.rmSync(override, { recursive: true, force: true });
});

test('E11c: an explicit trace dir inside the repository must be ignored, or capture fails closed', async () => {
  // `git status` reported `A traces/ses_*.jsonl` for this shape: the explicit
  // override skipped both git layers, so a trace inside the work tree could be
  // committed. An explicit destination inside a repository is now accepted only
  // when `.gitignore` or the common `info/exclude` actually names it.
  const root = gitRepo();
  const unignored = path.join(root, 'traces');

  // (a) Inside the work tree and named by neither layer: fail closed.
  const refused = handle.createState({ cwd: root, env: enabled({ AEP_HARNESS_PROFILE_DIR: unignored }) });
  const blocked = await feed(refused, fixture('tool-calls.json').events);
  assert.deepEqual(blocked, [], 'a record was written into an unignored in-repo directory');
  assert.equal(fs.existsSync(unignored), false, 'the unignored trace directory was created');
  assert.equal(refused.warnings.length, 1, 'the refusal must be recorded once, not per event');
  assert.match(refused.warnings[0], /inside the git work tree/i, 'the warning must name the location problem');
  assert.match(refused.warnings[0], /not ignored/i, 'the warning must name the cause');
  assert.match(refused.warnings[0], /outside the repository/i, 'the warning must name the first remedy');
  assert.match(refused.warnings[0], /ignore rule/i, 'the warning must name the second remedy');
  assert.deepEqual(execFileSync('git', ['-C', root, 'status', '--porcelain', '--', 'traces'], { encoding: 'utf8' }), '', 'the refused capture left a committable trace');

  // (b) Inside the work tree and ignored by the committed layer, using the
  // anchored form this repository itself ships (`/.harness-profile/`): capture
  // is allowed, and git agrees the directory is invisible.
  fs.writeFileSync(path.join(root, '.gitignore'), '/traces/\n');
  const accepted = handle.createState({ cwd: root, env: enabled({ AEP_HARNESS_PROFILE_DIR: unignored }) });
  const written = await feed(accepted, fixture('tool-calls.json').events);
  assert.ok(written.length > 0, 'an ignored in-repo destination wrote nothing');
  assert.ok(fs.existsSync(path.join(unignored, 'ses_root_tools.jsonl')), 'the trace did not land in the explicit directory');
  assert.deepEqual(accepted.warnings, [], 'an ignored in-repo destination is not a refusal');
  assert.deepEqual(execFileSync('git', ['-C', root, 'status', '--porcelain', '--', 'traces'], { encoding: 'utf8' }), '', 'the accepted trace is visible to git');

  // (c) Ignored only by the common info/exclude (the runtime layer): allowed
  // too, so the check is not limited to `.gitignore`.
  const captures = path.join(root, 'captures');
  fs.appendFileSync(path.join(root, '.git', 'info', 'exclude'), 'captures/\n');
  const viaExclude = handle.createState({ cwd: root, env: enabled({ AEP_HARNESS_PROFILE_DIR: captures }) });
  const captured = await feed(viaExclude, fixture('tool-calls.json').events);
  assert.ok(captured.length > 0, 'a destination ignored through info/exclude wrote nothing');
  assert.ok(fs.existsSync(path.join(captures, 'ses_root_tools.jsonl')), 'the info/exclude destination stayed empty');
  assert.deepEqual(viaExclude.warnings, [], 'an info/exclude-ignored destination is not a refusal');

  fs.rmSync(root, { recursive: true, force: true });
});

test('E11b: an unverifiable exclusion writes no records and warns with the reason', async (t) => {
  // The three shapes the "does a git root exist" guard let through. Each must
  // write nothing and name the reason once.
  const capture = async (cwd) => {
    const state = handle.createState({ cwd, env: enabled() });
    const records = await feed(state, fixture('tool-calls.json').events);
    return { state, records };
  };

  // (a) The repository exists but info/exclude cannot be written: 0555 info,
  // 0444 exclude leaves the file readable and the append EACCES.
  if (typeof process.getuid === 'function' && process.getuid() === 0) {
    t.diagnostic('skipping the EACCES case: root bypasses permission bits');
  } else {
    const root = gitRepo();
    const info = path.join(root, '.git', 'info');
    const exclude = path.join(info, 'exclude');
    fs.chmodSync(exclude, 0o444);
    fs.chmodSync(info, 0o555);
    try {
      const { state, records } = await capture(root);
      assert.deepEqual(records, [], 'a record was written although the exclusion failed');
      assert.equal(fs.existsSync(path.join(root, '.harness-profile')), false, 'a trace directory was created without a verified exclusion');
      assert.equal(state.warnings.length, 1, 'the refusal must be recorded once');
      assert.match(state.warnings[0], /EACCES|EPERM/, 'the warning must name the write error');
      assert.match(state.warnings[0], /AEP_HARNESS_PROFILE_DIR/, 'the warning must name the escape hatch');
      assert.deepEqual(state.errors, [], 'a refusal is a warning, not a handler error');
      assert.deepEqual(execFileSync('git', ['-C', root, 'status', '--porcelain'], { encoding: 'utf8' }), '', 'the refused capture left the tree dirty');

      // The normal path is unaffected once the permission is restored.
      fs.chmodSync(info, 0o755);
      fs.chmodSync(exclude, 0o644);
      const normal = await capture(root);
      assert.equal(normal.records.length, 3, 'the writable path stopped capturing');
      assert.deepEqual(normal.state.warnings, [], 'a writable repository is not a refusal');
      assert.equal(
        fs.readFileSync(exclude, 'utf8').split(/\r?\n/).filter((line) => line === '.harness-profile/').length,
        1,
        'the exclusion was not written once the permission was restored',
      );
      assert.doesNotThrow(
        () => execFileSync('git', ['-C', root, 'check-ignore', '-q', '.harness-profile/x']),
        'the restored repository does not ignore the ledger',
      );
    } finally {
      fs.chmodSync(info, 0o755);
      fs.chmodSync(exclude, 0o644);
      fs.rmSync(root, { recursive: true, force: true });
    }
  }

  // (b) `.git` is a file whose target does not exist: git would refuse the
  // repository, so the exclusion cannot be shown to be in effect.
  const dangling = scratch('hp-hygiene-dangling-');
  fs.writeFileSync(path.join(dangling, '.git'), 'gitdir: /nonexistent/hp-hygiene-gitdir\n');
  const first = await capture(dangling);
  assert.deepEqual(first.records, [], 'a dangling .git still wrote records');
  assert.equal(fs.existsSync(path.join(dangling, '.harness-profile')), false);
  assert.equal(first.state.warnings.length, 1);
  assert.match(first.state.warnings[0], /does not resolve|malformed/i, 'the warning must name the malformed .git');

  // (c) `.git` is a file with no gitdir line at all.
  const garbage = scratch('hp-hygiene-garbage-git-');
  fs.writeFileSync(path.join(garbage, '.git'), 'this is not a gitdir pointer\n');
  const second = await capture(garbage);
  assert.deepEqual(second.records, [], 'a garbage .git still wrote records');
  assert.equal(fs.existsSync(path.join(garbage, '.harness-profile')), false);
  assert.equal(second.state.warnings.length, 1);
  assert.match(second.state.warnings[0], /does not resolve|malformed/i);

  fs.rmSync(dangling, { recursive: true, force: true });
  fs.rmSync(garbage, { recursive: true, force: true });
});

test('E11d: an explicit trace dir is judged by its resolved path, so a symlink into the work tree is refused', async () => {
  // Reviewer repro: AEP_HARNESS_PROFILE_DIR pointed at a symlink outside the
  // work tree whose target was `<repo>/traces`. The path-string check looked
  // outside, so capture wrote and `git status` showed `?? traces/` with no
  // warning. The destination must be judged by its final path.
  const root = gitRepo();
  const inside = path.join(root, 'traces');
  fs.mkdirSync(inside);
  const links = scratch('hp-hygiene-links-');
  const intoRepo = path.join(links, 'traces-link');
  fs.symlinkSync(inside, intoRepo, 'dir');

  const refused = handle.createState({ cwd: root, env: enabled({ AEP_HARNESS_PROFILE_DIR: intoRepo }) });
  const blocked = await feed(refused, fixture('tool-calls.json').events);
  assert.deepEqual(blocked, [], 'a record was written through a symlink into an unignored in-repo directory');
  assert.equal(fs.existsSync(path.join(inside, 'ses_root_tools.jsonl')), false, 'the trace landed in the symlink target');
  assert.equal(refused.warnings.length, 1, 'the refusal must be recorded once, not per event');
  assert.match(refused.warnings[0], /inside the git work tree/i, 'the warning must name the location problem');
  assert.match(refused.warnings[0], /not ignored/i, 'the warning must name the cause');
  assert.match(refused.warnings[0], /resolves to/i, 'the warning must name the resolved path that was judged');
  assert.equal(execFileSync('git', ['-C', root, 'status', '--porcelain', '--', 'traces'], { encoding: 'utf8' }), '', 'the refused capture left a committable trace');

  // The other direction: a symlink whose target is outside every repository is
  // still the documented escape hatch, and the records land in the target.
  const outside = scratch('hp-hygiene-outside-');
  const outsideLink = path.join(links, 'outside-link');
  fs.symlinkSync(outside, outsideLink, 'dir');
  const accepted = handle.createState({ cwd: root, env: enabled({ AEP_HARNESS_PROFILE_DIR: outsideLink }) });
  const written = await feed(accepted, fixture('tool-calls.json').events);
  assert.ok(written.length > 0, 'an out-of-repo symlink destination wrote nothing');
  assert.ok(fs.existsSync(path.join(outside, 'ses_root_tools.jsonl')), 'the trace did not land in the symlink target');
  assert.deepEqual(accepted.warnings, [], 'an out-of-repo symlink destination is not a refusal');
  assert.equal(execFileSync('git', ['-C', root, 'status', '--porcelain', '--', 'traces'], { encoding: 'utf8' }), '', 'the accepted trace is visible to git');

  fs.rmSync(root, { recursive: true, force: true });
  fs.rmSync(links, { recursive: true, force: true });
  fs.rmSync(outside, { recursive: true, force: true });
});

// The two-writer child. It waits for a `go` file so both processes append at
// the same time, then feeds `count` calls through the real handler. Each line is
// built and appended by `translate.writeRecord`, exactly as in production.
const WRITER = `'use strict';
const fs = require('node:fs');
const [, , handlePath, dir, tag, count, readyFile, goFile, root] = process.argv;
const handle = require(handlePath);
const pause = new Int32Array(new SharedArrayBuffer(4));
fs.writeFileSync(readyFile, '');
while (!fs.existsSync(goFile)) Atomics.wait(pause, 0, 0, 1);
const state = handle.createState({
  cwd: dir,
  env: { AEP_HARNESS_PROFILE: '1', AEP_HARNESS_PROFILE_DIR: dir },
});
const total = Number(count);
const pad = 'x'.repeat(1500);
(async () => {
  for (let i = 0; i < total; i += 1) {
    const id = 'call_' + tag + '_' + i;
    const message = 'msg_' + tag + '_' + i;
    const at = Date.now();
    const events = [
      { id: 'e_' + tag + '_' + i + '_in', created: at, type: 'session.tool.input.started', data: { sessionID: root, assistantMessageID: message, id, name: 'shell' } },
      { id: 'e_' + tag + '_' + i + '_call', created: at + 1, type: 'session.tool.called', data: { sessionID: root, assistantMessageID: message, id, input: { command: pad, index: i } } },
      { id: 'e_' + tag + '_' + i + '_ok', created: at + 2, type: 'session.tool.success', data: { sessionID: root, assistantMessageID: message, id, content: [{ type: 'text', text: 'ok ' + i }] } },
      { id: 'e_' + tag + '_' + i + '_end', created: at + 3, type: 'session.step.ended', data: { sessionID: root, assistantMessageID: message, tokens: { input: 1, output: 1, reasoning: 0, cache: { read: 0, write: 0 } } } },
    ];
    for (const event of events) await handle.handleEvent(event, state);
  }
})().catch((error) => { console.error(error); process.exit(1); });
`;

function runWriter(args) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, args, { stdio: ['ignore', 'ignore', 'pipe'] });
    let stderr = '';
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.on('error', reject);
    child.on('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`writer exited ${code}: ${stderr}`));
    });
  });
}

async function waitFor(files, timeout = 5000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if (files.every((file) => fs.existsSync(file))) return;
    await sleep(5);
  }
  throw new Error('writers did not become ready');
}

test('E12: two concurrent writers produce only complete, well-formed JSON lines', async () => {
  const dir = scratch('hp-hygiene-race-');
  const script = path.join(dir, 'writer.js');
  const go = path.join(dir, 'go');
  fs.writeFileSync(script, WRITER);
  const perWriter = 150;

  const tags = ['a', 'b'];
  const ready = tags.map((tag) => path.join(dir, `${tag}.ready`));
  // Both processes load, signal ready, and wait for the same `go` file, so the
  // appends start together rather than one writer finishing first.
  const running = tags.map((tag, at) => runWriter([
    script,
    path.join(__dirname, 'handle.js'),
    dir,
    tag,
    String(perWriter),
    ready[at],
    go,
    ROOT,
  ]));
  await waitFor(ready);
  fs.writeFileSync(go, '');
  await Promise.all(running);

  const file = path.join(dir, `${ROOT}.jsonl`);
  assert.ok(fs.existsSync(file), 'the writers produced no trace');
  assert.equal(fs.statSync(file).mode & 0o777, 0o600, 'the raced file must still be 0600');

  const text = fs.readFileSync(file, 'utf8');
  assert.ok(text.endsWith('\n'), 'the last line is not newline-terminated');
  const lines = text.slice(0, -1).split('\n');
  assert.equal(lines.length, perWriter * 2, 'a record was split or lost');

  const seen = new Set();
  for (const [index, line] of lines.entries()) {
    assert.notEqual(line.trim(), '', `line ${index} is empty (a split newline)`);
    let record;
    try {
      record = JSON.parse(line);
    } catch (error) {
      assert.fail(`line ${index} is not one complete record (${error.message}): ${line.slice(0, 120)}`);
    }
    assert.match(record.tool_use_id, /^call_[ab]_\d+$/, `line ${index} belongs to neither writer`);
    assert.ok(!seen.has(record.tool_use_id), `line ${index} duplicates ${record.tool_use_id}`);
    seen.add(record.tool_use_id);
  }
  assert.equal(seen.size, perWriter * 2, 'both writers are not fully represented');

  fs.rmSync(dir, { recursive: true, force: true });
});

test('E13: retention prunes traces older than the default window and is idempotent', () => {
  const dir = scratch('hp-hygiene-retention-');
  const now = Date.now();
  const old = touch(dir, 'ses_old.jsonl', 30, { now });
  const oldSidecar = touch(dir, 'ses_old.parentage.json', 30, { now });
  const recent = touch(dir, 'ses_recent.jsonl', 13, { now });
  const current = touch(dir, 'ses_current.jsonl', 0.1, { now });
  const boundary = touch(dir, 'ses_boundary.jsonl', 14.5, { now });
  const unrelated = touch(dir, 'notes.txt', 30, { now });
  // A shared AEP_HARNESS_PROFILE_DIR: another tool's JSONL is not ours to prune,
  // even though it has the same extension and is far outside the window.
  const foreign = touch(dir, 'other-tool-traces.jsonl', 30, { now });
  const operatorNotes = touch(dir, 'notes.jsonl', 30, { now });
  const nested = path.join(dir, 'nested.jsonl');
  fs.mkdirSync(nested);
  touch(nested, 'inside.jsonl', 30, { now });

  assert.equal(handle.RETENTION_DAYS, 14, 'the documented default window moved');

  const removed = handle.pruneTraces(dir, { now });
  assert.deepEqual(names(removed), ['ses_boundary.jsonl', 'ses_old.jsonl', 'ses_old.parentage.json']);
  for (const gone of [old, oldSidecar, boundary]) assert.equal(fs.existsSync(gone), false, `${gone} survived`);
  for (const kept of [recent, current, unrelated, foreign, operatorNotes]) assert.equal(fs.existsSync(kept), true, `${kept} was pruned`);
  assert.equal(fs.existsSync(path.join(nested, 'inside.jsonl')), true, 'prune recursed into a directory named like a trace');

  // Idempotent: the second run has nothing left to remove and deletes nothing.
  const before = fs.readdirSync(dir).sort();
  assert.deepEqual(handle.pruneTraces(dir, { now }), []);
  assert.deepEqual(fs.readdirSync(dir).sort(), before, 'the second prune changed the directory');

  // A directory that does not exist is not created just to prune it.
  const missing = path.join(dir, 'missing');
  assert.deepEqual(handle.pruneTraces(missing, { now }), []);
  assert.equal(fs.existsSync(missing), false);

  fs.rmSync(dir, { recursive: true, force: true });
});

test('E13b: the byte budget removes the oldest trace files until the directory fits', () => {
  const dir = scratch('hp-hygiene-budget-');
  const now = Date.now();
  assert.equal(handle.MAX_TRACE_BYTES, 32 * 1024 * 1024, 'the documented byte budget moved');
  const body = 'x'.repeat(600);
  const oldest = touch(dir, 'ses_a.jsonl', 3, { now, body });
  const middle = touch(dir, 'ses_b.jsonl', 2, { now, body });
  const newest = touch(dir, 'ses_c.jsonl', 1, { now, body });
  const unrelated = touch(dir, 'notes.txt', 4, { now, body });
  const foreign = touch(dir, 'other-tool-traces.jsonl', 5, { now, body });

  // 1,800 bytes of traces against a 1,000-byte ceiling: drop oldest-first. The
  // foreign JSONL is neither counted nor removed.
  const removed = handle.pruneTraces(dir, { now, days: 0, maxBytes: 1000 });
  assert.deepEqual(names(removed), ['ses_a.jsonl', 'ses_b.jsonl']);
  for (const gone of [oldest, middle]) assert.equal(fs.existsSync(gone), false);
  assert.equal(fs.existsSync(newest), true, 'the newest trace was pruned before an older one');
  assert.equal(fs.existsSync(unrelated), true, 'a non-trace file counted against the budget');
  assert.equal(fs.existsSync(foreign), true, 'a foreign .jsonl was pruned from a shared directory');

  const total = fs.readdirSync(dir).filter((name) => /^ses_.*\.jsonl$/.test(name)).reduce((sum, name) => sum + fs.statSync(path.join(dir, name)).size, 0);
  assert.ok(total <= 1000, `${total} bytes remain above the budget`);
  assert.deepEqual(handle.pruneTraces(dir, { now, days: 0, maxBytes: 1000 }), [], 'the size prune is not idempotent');

  fs.rmSync(dir, { recursive: true, force: true });
});

test('E13c: capture prunes on its first event, and both bounds are env-overridable', async () => {
  // The age bound through the handler: a 3-day-old file goes when the window is
  // one day; a half-day-old file stays.
  const root = gitRepo();
  const dir = path.join(root, '.harness-profile');
  fs.mkdirSync(dir);
  const stale = touch(dir, 'ses_stale.jsonl', 3);
  const live = touch(dir, 'ses_live.jsonl', 0.5);
  const withWindow = handle.createState({ cwd: root, env: enabled({ AEP_HARNESS_PROFILE_RETENTION_DAYS: '1' }) });
  await feed(withWindow, fixture('tool-calls.json').events);
  assert.equal(fs.existsSync(stale), false, 'the age override did not prune the stale trace');
  assert.equal(fs.existsSync(live), true, 'the age override pruned a file inside its window');
  assert.ok(fs.existsSync(path.join(dir, 'ses_root_tools.jsonl')), 'capture did not write after pruning');
  assert.deepEqual(withWindow.errors, []);

  // The byte bound through the handler: age disabled, a 1,000-byte ceiling.
  // E11c's rule means an explicit destination inside the repository must be
  // ignored, so the byte-budget directory gets its own committed-layer entry.
  const sized = path.join(root, '.harness-profile-sized');
  fs.writeFileSync(path.join(root, '.gitignore'), '/.harness-profile-sized/\n');
  fs.mkdirSync(sized);
  const bigOld = touch(sized, 'ses_big_old.jsonl', 3, { body: 'x'.repeat(600) });
  const bigNew = touch(sized, 'ses_big_new.jsonl', 2, { body: 'x'.repeat(600) });
  const withBudget = handle.createState({ cwd: root, env: enabled({
    AEP_HARNESS_PROFILE_DIR: sized,
    AEP_HARNESS_PROFILE_RETENTION_DAYS: '0',
    AEP_HARNESS_PROFILE_MAX_BYTES: '1000',
  }) });
  await feed(withBudget, fixture('tool-calls.json').events);
  assert.equal(fs.existsSync(bigOld), false, 'the byte override did not prune the oldest trace');
  assert.equal(fs.existsSync(bigNew), true, 'the byte override pruned the newest trace first');
  assert.deepEqual(withBudget.errors, []);

  // A window of 0 disables the age bound rather than pruning everything.
  const kept = scratch('hp-hygiene-nowindow-');
  const old = touch(kept, 'ses_old.jsonl', 90);
  handle.pruneTraces(kept, { days: 0, maxBytes: 0 });
  assert.equal(fs.existsSync(old), true, 'days=0 must disable the age bound');

  fs.rmSync(root, { recursive: true, force: true });
  fs.rmSync(kept, { recursive: true, force: true });
});

test('E10c: an explicit destination governed by a nested .gitignore is refused', async () => {
  // The guard reads the root .gitignore and the common info/exclude only. A
  // nested file can negate the root rule (`!.harness-profile/`), so approving
  // the destination would write a committable trace. Precedence cannot be
  // verified without re-implementing gitignore, so capture fails closed.
  const root = gitRepo();
  const cwd = path.join(root, 'a');
  fs.mkdirSync(cwd, { recursive: true });
  fs.mkdirSync(path.join(root, 'nested', '.harness-profile'), { recursive: true });
  fs.writeFileSync(path.join(root, '.gitignore'), '.harness-profile/\n');
  fs.writeFileSync(path.join(root, 'nested', '.gitignore'), '!.harness-profile/\n');

  const dest = path.join(root, 'nested', '.harness-profile');
  const state = handle.createState({ cwd, env: enabled({ AEP_HARNESS_PROFILE_DIR: dest }) });
  const records = await feed(state, fixture('tool-calls.json').events);

  assert.equal(records.length, 0, 'capture wrote into a destination a nested ignore file re-includes');
  assert.deepEqual(fs.readdirSync(dest), [], 'a trace file was written');
  assert.match(state.warnings.join('\n'), /nested/i, 'the refusal does not name the nested ignore file');
});

test('E10d: a default .harness-profile that is a symlink is judged by its target', async () => {
  // Excluding the symlink's name does not exclude its target. The default path
  // must resolve the destination too, not only the explicit one.
  const root = gitRepo();
  const cwd = path.join(root, 'a');
  fs.mkdirSync(cwd, { recursive: true });
  fs.mkdirSync(path.join(root, 'traces'), { recursive: true });
  fs.symlinkSync(path.join(root, 'traces'), path.join(root, '.harness-profile'));
  fs.writeFileSync(path.join(root, '.gitignore'), 'dist/\n');

  const refused = handle.createState({ cwd, env: enabled() });
  const records = await feed(refused, fixture('tool-calls.json').events);
  assert.equal(records.length, 0, 'capture wrote through a symlink whose target is committable');
  assert.deepEqual(fs.readdirSync(path.join(root, 'traces')), [], 'a trace file landed in the symlink target');
  assert.match(refused.warnings.join('\n'), /resolves|target/i, 'the refusal does not name the resolved target');

  // The same destination is accepted once its target is ignored.
  fs.writeFileSync(path.join(root, '.gitignore'), 'dist/\ntraces/\n');
  const accepted = handle.createState({ cwd, env: enabled() });
  const written = await feed(accepted, fixture('tool-calls.json').events);
  assert.ok(written.length > 0, 'an ignored symlink target was refused');
  assert.ok(fs.readdirSync(path.join(root, 'traces')).length > 0, 'no trace landed in the ignored target');
});

test('E13d: a flushed call releases its input and step tokens', async () => {
  // A long-lived service must not retain every completed call's payload: 100
  // sessions with 1 MiB inputs left 100 MiB reachable though nothing was
  // pending. Spend and links survive; the payload does not.
  const dir = scratch();
  const big = 'x'.repeat(1024 * 1024);
  const session = 'ses_root_release';
  const events = [
    { id: 'r1', created: 1794932100000, type: 'session.tool.input.started', data: { sessionID: session, id: 'call_big', name: 'write' } },
    { id: 'r2', created: 1794932100001, type: 'session.tool.called', data: { sessionID: session, id: 'call_big', assistantMessageID: 'm1', input: { content: big } } },
    { id: 'r3', created: 1794932100002, type: 'session.tool.success', data: { sessionID: session, id: 'call_big', assistantMessageID: 'm1', content: [{ type: 'text', text: 'ok' }] } },
    { id: 'r4', created: 1794932100003, type: 'session.step.ended', data: { sessionID: session, assistantMessageID: 'm1', tokens: { input: 10, output: 5, reasoning: 0, cache: { read: 0, write: 0 } } } },
    { id: 'r5', created: 1794932100004, type: 'session.execution.succeeded', data: { sessionID: session } },
  ];
  const state = handle.createState({ cwd: dir, env: enabled({ AEP_HARNESS_PROFILE_DIR: dir }), sessionGet: (id) => ({ id }) });
  const records = await feed(state, events);
  assert.ok(records.length > 0, 'nothing was recorded');

  const tree = [...state.trees.values()][0];
  assert.equal(tree.t.calls.size, 0, 'a completed call kept its input reachable');
  assert.equal(tree.t.steps.size, 0, 'a completed step kept its tokens reachable');
  // The cumulative spend a later stop needs is still there.
  assert.deepEqual(tree.t.spend.get(session), { new: 10, cached: 0, out: 5, calls: 1 });
  fs.rmSync(dir, { recursive: true, force: true });
});

test('E13e: inactive session trees are bounded, and a resumed session reseeds its spend', async () => {
  // state.trees otherwise grows for the service's lifetime. Completed sessions
  // are evicted least-recently-active first; a tree with nothing in flight is
  // safe to drop because a resume restores spend from the trace on disk.
  const dir = scratch();
  const total = 205;
  const turn = (session, index) => [
    { id: `t${index}a`, created: 1794932200000 + index * 10 + 0, type: 'session.tool.input.started', data: { sessionID: session, id: `c_${index}`, name: 'bash' } },
    { id: `t${index}b`, created: 1794932200000 + index * 10 + 1, type: 'session.tool.called', data: { sessionID: session, id: `c_${index}`, assistantMessageID: `m_${index}`, input: {} } },
    { id: `t${index}c`, created: 1794932200000 + index * 10 + 2, type: 'session.tool.success', data: { sessionID: session, id: `c_${index}`, assistantMessageID: `m_${index}`, content: [{ type: 'text', text: 'ok' }] } },
    { id: `t${index}d`, created: 1794932200000 + index * 10 + 3, type: 'session.step.ended', data: { sessionID: session, assistantMessageID: `m_${index}`, tokens: { input: 1, output: 1, reasoning: 0, cache: { read: 0, write: 0 } } } },
    { id: `t${index}e`, created: 1794932200000 + index * 10 + 4, type: 'session.execution.succeeded', data: { sessionID: session } },
  ];
  const state = handle.createState({ cwd: dir, env: enabled({ AEP_HARNESS_PROFILE_DIR: dir }), sessionGet: (id) => ({ id }) });
  for (let i = 0; i < total; i += 1) {
    await feed(state, turn(`ses_root_bounded_${i}`, i));
  }
  assert.ok(state.trees.size <= 200, `retained ${state.trees.size} session trees`);

  // The first session is gone from memory; a resume must still be cumulative,
  // because the trace on disk is the source of truth.
  const first = 'ses_root_bounded_0';
  assert.equal(state.trees.has(first), false, 'the oldest completed tree was not evicted');
  const resumed = handle.createState({ cwd: dir, env: enabled({ AEP_HARNESS_PROFILE_DIR: dir }), sessionGet: (id) => ({ id }) });
  const again = [
    { id: 'z1', created: 1794932300000, type: 'session.step.ended', data: { sessionID: first, assistantMessageID: 'mz', tokens: { input: 5, output: 5, reasoning: 0, cache: { read: 0, write: 0 } } } },
    { id: 'z2', created: 1794932300001, type: 'session.execution.succeeded', data: { sessionID: first } },
  ];
  const written = await feed(resumed, again);
  const stop = written.find((record) => record.event === 'SubagentStop');
  assert.ok(stop, 'the resumed session wrote no stop');
  assert.deepEqual(stop.spend, { new: 6, cached: 0, out: 6, calls: 2 }, 'the resume did not restore the prior spend');
  fs.rmSync(dir, { recursive: true, force: true });
});

test('E10e: an ignore-file negation that re-includes the destination is refused', async () => {
  // `!trace[s]/` re-includes `traces`; a hand-rolled glob matcher escapes the
  // brackets and misses it, approving a committable trace. The verdict is git's.
  const root = gitRepo();
  const cwd = path.join(root, 'a');
  fs.mkdirSync(cwd, { recursive: true });
  fs.mkdirSync(path.join(root, 'traces'), { recursive: true });
  fs.writeFileSync(path.join(root, '.gitignore'), 'traces/\n!trace[s]/\n');

  const dest = path.join(root, 'traces');
  const refused = handle.createState({ cwd, env: enabled({ AEP_HARNESS_PROFILE_DIR: dest }) });
  const records = await feed(refused, fixture('tool-calls.json').events);
  assert.equal(records.length, 0, 'capture wrote where git would not ignore it');
  assert.deepEqual(fs.readdirSync(dest), [], 'a trace file was written');
  assert.match(refused.warnings.join('\n'), /not ignored|committable/i);

  // Control: the same destination is accepted when git really ignores it.
  fs.writeFileSync(path.join(root, '.gitignore'), 'traces/\n');
  const accepted = handle.createState({ cwd, env: enabled({ AEP_HARNESS_PROFILE_DIR: dest }) });
  const written = await feed(accepted, fixture('tool-calls.json').events);
  assert.ok(written.length > 0, 'an ignored destination was refused');
  assert.ok(fs.readdirSync(dest).length > 0, 'nothing was written to the ignored destination');
  fs.rmSync(root, { recursive: true, force: true });
});

test('E13f: a running tool call keeps its session tree from eviction', async () => {
  // A running call is neither pending nor an open spawn. Evicting its tree
  // loses the call's name, input and start time — none of it on disk yet — so
  // the completion could never be recorded.
  const dir = scratch();
  const env = enabled({ AEP_HARNESS_PROFILE_DIR: dir });
  const running = 'ses_root_running';
  const state = handle.createState({ cwd: dir, env, sessionGet: (id) => ({ id }) });
  await feed(state, [
    { id: 'run1', created: 1794932400000, type: 'session.tool.input.started', data: { sessionID: running, id: 'call_shell', name: 'bash' } },
    { id: 'run2', created: 1794932400001, type: 'session.tool.called', data: { sessionID: running, id: 'call_shell', assistantMessageID: 'mrun', input: { command: 'sleep 100' } } },
  ]);
  assert.ok(state.trees.has(running), 'the running session tree was never created');

  for (let i = 0; i < 205; i += 1) {
    const session = `ses_root_fill_${i}`;
    const base = 1794932500000 + i * 10;
    await feed(state, [
      { id: `f${i}a`, created: base, type: 'session.tool.input.started', data: { sessionID: session, id: `cf_${i}`, name: 'bash' } },
      { id: `f${i}b`, created: base + 1, type: 'session.tool.called', data: { sessionID: session, id: `cf_${i}`, assistantMessageID: `mf_${i}`, input: {} } },
      { id: `f${i}c`, created: base + 2, type: 'session.tool.success', data: { sessionID: session, id: `cf_${i}`, assistantMessageID: `mf_${i}`, content: [] } },
      { id: `f${i}d`, created: base + 3, type: 'session.step.ended', data: { sessionID: session, assistantMessageID: `mf_${i}`, tokens: { input: 1, output: 1, reasoning: 0, cache: { read: 0, write: 0 } } } },
      { id: `f${i}e`, created: base + 4, type: 'session.execution.succeeded', data: { sessionID: session } },
    ]);
  }

  assert.ok(state.trees.has(running), 'the running call tree was evicted');
  assert.ok(state.trees.get(running).t.calls.has('call_shell'), 'the running call was dropped');

  const done = await feed(state, [
    { id: 'run3', created: 1794932600000, type: 'session.tool.success', data: { sessionID: running, id: 'call_shell', assistantMessageID: 'mrun', content: [{ type: 'text', text: 'ok' }] } },
    { id: 'run4', created: 1794932600001, type: 'session.step.ended', data: { sessionID: running, assistantMessageID: 'mrun', tokens: { input: 3, output: 2, reasoning: 0, cache: { read: 0, write: 0 } } } },
  ]);
  assert.ok(done.some((record) => record.tool_use_id === 'call_shell'), 'the completion produced no record');
  fs.rmSync(dir, { recursive: true, force: true });
});

test('E10g: a default symlink into another checkout is judged by that checkout', async () => {
  // Outside *this* repository is not the same as outside every repository: a
  // link into another checkout writes a trace that repository can commit.
  const a = gitRepo('hp-hygiene-a-');
  const b = gitRepo('hp-hygiene-b-');
  fs.mkdirSync(path.join(a, 'work'), { recursive: true });
  fs.mkdirSync(path.join(b, 'traces'), { recursive: true });
  fs.symlinkSync(path.join(b, 'traces'), path.join(a, '.harness-profile'));
  fs.writeFileSync(path.join(b, '.gitignore'), 'dist/\n');

  const refused = handle.createState({ cwd: path.join(a, 'work'), env: enabled() });
  const records = await feed(refused, fixture('tool-calls.json').events);
  assert.equal(records.length, 0, 'capture wrote into another checkout that does not ignore it');
  assert.deepEqual(fs.readdirSync(path.join(b, 'traces')), [], 'a trace landed in the other checkout');
  assert.match(refused.warnings.join('\n'), /another|inside the git work tree|not ignored/i);

  // The same link is accepted once the destination repository ignores it.
  fs.writeFileSync(path.join(b, '.gitignore'), 'dist/\ntraces/\n');
  const accepted = handle.createState({ cwd: path.join(a, 'work'), env: enabled() });
  const written = await feed(accepted, fixture('tool-calls.json').events);
  assert.ok(written.length > 0, 'a destination the other repository ignores was refused');
  assert.ok(fs.readdirSync(path.join(b, 'traces')).length > 0, 'nothing was written to the ignored target');
  fs.rmSync(a, { recursive: true, force: true });
  fs.rmSync(b, { recursive: true, force: true });
});
