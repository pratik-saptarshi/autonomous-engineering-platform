'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const { init, doctor, HOOK_COMMAND, OLD_HOOK_COMMAND } = require('../plugin/libexec/hp.js');
const { tempDir, tempRepo, captureFixture } = require('./helpers.js');

const settingsOf = (repo) => JSON.parse(fs.readFileSync(path.join(repo, '.claude', 'settings.json'), 'utf8'));

test('init claude copies the hook and registers it once, keeping other settings', () => {
  const repo = tempRepo();
  fs.mkdirSync(path.join(repo, '.claude'));
  const existing = {
    permissions: { allow: ['Bash(ls)'] },
    hooks: { PostToolUse: [{ matcher: 'Edit', hooks: [{ type: 'command', command: 'fmt' }] }], Stop: [] },
  };
  fs.writeFileSync(path.join(repo, '.claude', 'settings.json'), JSON.stringify(existing));

  init(['claude'], path.join(repo));
  const once = settingsOf(repo);
  init(['claude'], repo);
  assert.deepEqual(settingsOf(repo), once, 'a second run changes nothing');

  assert.deepEqual(once.permissions, existing.permissions);
  assert.deepEqual(once.hooks.Stop, []);
  assert.equal(once.hooks.PostToolUse[0].matcher, 'Edit');
  for (const event of ['PostToolUse', 'PostToolUseFailure', 'PreCompact', 'PostCompact', 'SessionStart']) {
    const ours = once.hooks[event].filter((e) => e.hooks[0].command === HOOK_COMMAND);
    assert.equal(ours.length, 1, event);
    assert.equal(ours[0].matcher, '*');
    assert.equal(ours[0].hooks[0].async, true, `${event} runs in the background`);
  }
  const hp = path.join(repo, '.claude', 'harness-profiler', 'hp.sh');
  assert.ok(fs.statSync(hp).mode & 0o100);
  assert.ok(fs.existsSync(path.join(repo, '.claude', 'harness-profiler', 'hp.js')));
  assert.ok(fs.existsSync(path.join(repo, '.claude', 'harness-profiler', 'view.html')));
  assert.match(fs.readFileSync(path.join(repo, '.claude', 'skills', 'show-profile', 'SKILL.md'), 'utf8'), /^---\nname: show-profile\n/);
});

test('show-profile finds the launcher from either install', () => {
  const plugin = path.join(__dirname, '..', 'plugin', 'skills', 'show-profile');
  assert.ok(fs.existsSync(path.join(plugin, '..', '..', 'libexec', 'hp.sh')), 'the plugin: ../../libexec/hp.sh from the skill');
  const skill = fs.readFileSync(path.join(plugin, 'SKILL.md'), 'utf8');
  assert.match(skill, /`\.claude\/harness-profiler\/hp\.sh` at the git root/);
  assert.ok(skill.indexOf('../../libexec/hp.sh') < skill.indexOf('.claude/harness-profiler/hp.sh'), 'the plugin first: a committed copy can be older');
});

test('the committed hook records a call', () => {
  const repo = tempRepo();
  init(['claude'], repo);
  const payload = { session_id: 's1', hook_event_name: 'PostToolUse', tool_name: 'Skill', tool_input: { skill: 'greet' }, tool_response: { success: true }, tool_use_id: 't1', duration_ms: 3, cwd: repo };
  const command = settingsOf(repo).hooks.PostToolUse[0].hooks[0].command;
  const run = spawnSync('sh', ['-c', command], { input: JSON.stringify(payload), env: { ...process.env, CLAUDE_PROJECT_DIR: repo } });
  assert.equal(run.status, 0);
  assert.match(fs.readFileSync(path.join(repo, '.harness-profile', 's1.jsonl'), 'utf8'), /"name":"greet"/);
});

test('init refuses outside a git repository', () => {
  assert.throws(() => init(['claude'], tempDir()), /inside a git repository/);
});

test('doctor reports node, trace dir, hook source and newest call', () => {
  const repo = tempRepo();
  const home = tempDir();
  assert.match(doctor(repo, {}, home), /hook: +not installed/);
  assert.match(doctor(repo, {}, home), /newest: +no calls recorded yet/);

  init(['claude'], repo);
  captureFixture('claude-web.jsonl', { dir: repo });
  const report = doctor(repo, {}, home);
  assert.match(report, new RegExp(`node: +${process.execPath.replace(/[/\\.]/g, '\\$&')}`));
  assert.match(report, /hook: +committed hooks/);
  assert.match(report, /traces: +.*\.harness-profile/);
  assert.match(report, /newest: +2026-11-09T16:21:\d\d/);
});

test('doctor asks to rerun init when the committed hook misses events', () => {
  const repo = tempRepo();
  const home = tempDir();
  init(['claude'], repo);
  assert.doesNotMatch(doctor(repo, {}, home), /update:/);
  const settings = settingsOf(repo);
  delete settings.hooks.PreCompact;
  delete settings.hooks.SessionStart;
  fs.writeFileSync(path.join(repo, '.claude', 'settings.json'), JSON.stringify(settings));
  assert.match(doctor(repo, {}, home), /update: +the committed hook misses PreCompact, SessionStart; run harness-profiler init claude again/);
  settings.hooks.PostToolUse[0].hooks[0].async = false;
  fs.writeFileSync(path.join(repo, '.claude', 'settings.json'), JSON.stringify(settings));
  assert.match(doctor(repo, {}, home), /update: +the committed hook misses PreCompact, SessionStart and is not async;/);
  fs.appendFileSync(path.join(repo, '.claude', 'harness-profiler', 'hp.js'), '\n');
  assert.match(doctor(repo, {}, home), /is not async and has another version of hp\.js; run harness-profiler init claude again/);
});

test('the committed hook renders html from its own copy', () => {
  const repo = tempRepo();
  init(['claude'], repo);
  captureFixture('claude-web.jsonl', { dir: repo });
  const run = spawnSync('sh', [path.join(repo, '.claude', 'harness-profiler', 'hp.sh'), 'tree', '--format', 'html'], { cwd: repo, env: { ...process.env, CLAUDE_PROJECT_DIR: repo } });
  assert.equal(run.status, 0, run.stderr.toString());
  assert.match(run.stdout.toString(), /^<!doctype html>/);
});

test('init claude upgrades an entry an older init wrote, in place', () => {
  const repo = tempRepo();
  fs.mkdirSync(path.join(repo, '.claude'));
  const old = { matcher: '*', hooks: [{ type: 'command', command: HOOK_COMMAND, timeout: 5 }] };
  const other = { matcher: 'Edit', hooks: [{ type: 'command', command: 'fmt' }] };
  fs.writeFileSync(path.join(repo, '.claude', 'settings.json'), JSON.stringify({ hooks: { PostToolUse: [old, other, old] } }));
  init(['claude'], repo);
  const entries = settingsOf(repo).hooks.PostToolUse;
  assert.equal(entries.length, 2);
  assert.equal(entries[0].hooks[0].async, true);
  assert.deepEqual(entries[1], other);
});

test('init claude replaces a hook committed under the old launcher name', () => {
  const repo = tempRepo();
  const dir = path.join(repo, '.claude', 'harness-profiler');
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'hp'), '#!/bin/sh\n');
  const old = { matcher: '*', hooks: [{ type: 'command', command: OLD_HOOK_COMMAND, timeout: 5, async: true }] };
  fs.writeFileSync(path.join(repo, '.claude', 'settings.json'), JSON.stringify({ hooks: { PostToolUse: [old] } }));
  assert.match(doctor(repo, {}, tempDir()), /update: +the committed hook misses .* and has another version of hp\.sh/);
  init(['claude'], repo);
  const entries = settingsOf(repo).hooks.PostToolUse;
  assert.equal(entries.length, 1);
  assert.equal(entries[0].hooks[0].command, HOOK_COMMAND);
  assert.ok(!fs.existsSync(path.join(dir, 'hp')), 'the old launcher is gone');
  assert.doesNotMatch(doctor(repo, {}, tempDir()), /update:/);
});
