'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const { capture } = require('../plugin/libexec/hp.js');

const FIXTURES = path.join(__dirname, 'fixtures');

// Seconds past 16:21:00 UTC at which the recorder received each line of
// claude-web.jsonl, so captured records keep the real timing.
const WEB_RECEIVED_S = [3, 9, 9, 10, 10, 11, 11, 15, 15, 21, 21, 23, 23, 23, 23, 28, 28, 29, 30, 35];
const WEB_T0 = Date.parse('2026-11-09T16:21:00Z');

// The same for claude-contexts.jsonl, past 11:57:00 UTC: a forked skill, a
// `fork` and a general-purpose subagent, a manual /compact, an inline skill.
const CONTEXTS_RECEIVED_S = [23, 24, 27, 27, 31, 31, 35, 35, 36, 36, 39, 39, 44, 44, 46, 46, 47, 47, 50, 50, 51, 51, 55, 55,
  64, 64, 85, 86, 105, 105, 105, 105, 106, 107, 110, 110, 114, 114, 191, 192, 195, 195, 198, 198, 198, 198, 203, 203];
const CONTEXTS_T0 = Date.parse('2026-11-10T11:57:00Z');

// The same for claude-background.jsonl, past 13:28:00 UTC: a `fork` and a
// general-purpose subagent run in the background.
const BACKGROUND_RECEIVED_S = [19, 23, 24, 25, 26, 26, 28];
const BACKGROUND_T0 = Date.parse('2026-11-10T13:28:00Z');

function fixtureLines(name) {
  return fs.readFileSync(path.join(FIXTURES, name), 'utf8').trim().split('\n');
}

// The call column of `tree` output: drops the header and the fixed columns.
function callColumn(text) {
  const lines = text.split('\n');
  const width = lines.find((l) => l.startsWith('time ')).indexOf('call');
  return lines.filter((l) => !l.startsWith('time ')).map((l) => (l.startsWith('# ') ? l : l.slice(width)));
}

const created = [];
process.on('exit', () => created.forEach((dir) => fs.rmSync(dir, { recursive: true, force: true })));

function tempDir(prefix = 'hp-test-') {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  created.push(dir);
  return dir;
}

function tempRepo() {
  const dir = tempDir();
  fs.mkdirSync(path.join(dir, '.git', 'info'), { recursive: true });
  fs.writeFileSync(path.join(dir, '.git', 'HEAD'), 'ref: refs/heads/demo\n');
  return dir;
}

function captureFixture(name, { dir = tempRepo(), times, t0 = WEB_T0 } = {}) {
  const env = { CLAUDE_PROJECT_DIR: dir };
  let file;
  fixtureLines(name).forEach((line, i) => {
    const payload = JSON.parse(line);
    payload.cwd = dir;
    const now = new Date(t0 + (times ? times[i] : i) * 1000);
    file = capture('claude', JSON.stringify(payload), env, now) || file;
  });
  const records = fs.readFileSync(file, 'utf8').trim().split('\n').map((l) => JSON.parse(l));
  return { dir, file, records };
}

const captureContexts = (options = {}) =>
  captureFixture('claude-contexts.jsonl', { times: CONTEXTS_RECEIVED_S, t0: CONTEXTS_T0, ...options });

const captureBackground = (options = {}) =>
  captureFixture('claude-background.jsonl', { times: BACKGROUND_RECEIVED_S, t0: BACKGROUND_T0, ...options });

module.exports = { callColumn, fixtureLines, tempDir, tempRepo, captureFixture, captureContexts, captureBackground, WEB_RECEIVED_S };
