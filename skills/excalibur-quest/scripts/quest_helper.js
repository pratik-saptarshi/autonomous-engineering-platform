// Copyright 2026 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/**
 * @fileoverview Cross-platform helper CLI for excalibur-quest remediation orchestrations.
 * Zero-dependency, compatible with Windows, macOS, and Linux Node.js environments.
 */

const fs = require('fs');
const path = require('path');
const { execSync, execFileSync } = require('child_process');

class QuestDB {
  constructor(dbDir) {
    this.dbDir = dbDir;
    if (!fs.existsSync(this.dbDir)) {
      fs.mkdirSync(this.dbDir, { recursive: true });
    }
    this.jsonDb = path.join(this.dbDir, 'quest_db.json');
    this.useDolt = this.checkDolt();
  }

  checkDolt() {
    try {
      execSync('dolt version', { stdio: 'ignore' });
      return true;
    } catch (e) {
      return false;
    }
  }

  loadQuest(issueId) {
    if (this.useDolt) {
      try {
        const query = `SELECT data FROM quests WHERE issue_id = '${issueId}'`;
        const res = execFileSync('dolt', ['sql', '-q', query, '-r', 'json'], { encoding: 'utf8' }).trim();
        if (res) {
          const rows = JSON.parse(res);
          if (rows && rows.rows && rows.rows.length > 0) {
            return JSON.parse(rows.rows[0].data);
          }
        }
      } catch (e) {
        console.error('Dolt load failed, falling back to JSON:', e.message);
      }
    }

    if (fs.existsSync(this.jsonDb)) {
      try {
        const data = JSON.parse(fs.readFileSync(this.jsonDb, 'utf8'));
        return data[issueId];
      } catch (e) {
        console.error('JSON load failed:', e.message);
      }
    }
    return null;
  }

  _writeQuestToDolt(issueId, questData) {
    execFileSync('dolt', ['sql', '-q', 'CREATE TABLE IF NOT EXISTS quests (issue_id VARCHAR(50) PRIMARY KEY, data TEXT)'], { stdio: 'ignore' });
    const escapedData = JSON.stringify(questData).replace(/'/g, "''");
    execFileSync('dolt', ['sql', '-q', `REPLACE INTO quests (issue_id, data) VALUES ('${issueId}', '${escapedData}')`], { stdio: 'ignore' });
  }

  // Rewrites the JSON store with questData under issueId. The caller
  // must hold the DB lock: the file is rewritten wholesale, so the
  // read-modify-write has to be atomic against other writers.
  // A failed write throws: callers must never report success for a
  // quest that was not persisted.
  //
  // The new snapshot is published atomically: it is written to a temp
  // file in the same directory, flushed, and renamed over the store.
  // A concurrent loadQuest — which does not take the DB lock —
  // therefore always opens a complete snapshot (the old one or the
  // new one), never the truncated file an in-place write exposes
  // mid-write. The temp name is PID-scoped, so the permitted
  // concurrent instances never collide on it; a crashed writer's
  // leftover temp is never mistaken for the store (loadQuest reads
  // only the store path) and never blocks a later write.
  _writeQuestToJson(issueId, questData) {
    let data = {};
    if (fs.existsSync(this.jsonDb)) {
      try {
        data = JSON.parse(fs.readFileSync(this.jsonDb, 'utf8'));
      } catch (e) {}
    }
    data[issueId] = questData;

    // Rename replaces the store file, so the replacement carries the
    // current store's permissions where there is one. It also makes
    // writability a property of the directory: a read-only store file
    // in a writable directory is now genuinely — and atomically —
    // replaced, while a read-only directory still fails the write
    // loudly, as round 4 requires.
    let storeMode = null;
    try {
      storeMode = fs.statSync(this.jsonDb).mode & 0o777;
    } catch (e) {}

    const tmpPath = `${this.jsonDb}.tmp.${process.pid}`;
    let fd = null;
    try {
      fd = fs.openSync(tmpPath, 'w');
      if (storeMode !== null) {
        try { fs.fchmodSync(fd, storeMode); } catch (e) {}
      }
      fs.writeFileSync(fd, JSON.stringify(data, null, 2), 'utf8');
      fs.fsyncSync(fd);
      fs.closeSync(fd);
      fd = null;
      fs.renameSync(tmpPath, this.jsonDb);
    } catch (e) {
      if (fd !== null) {
        try { fs.closeSync(fd); } catch (ignored) {}
      }
      try { fs.unlinkSync(tmpPath); } catch (ignored) {}
      throw e;
    }
  }

  // Backend write with no lock handling of its own; the caller is
  // responsible for holding the DB lock (see updateQuest).
  _storeQuest(issueId, questData) {
    if (this.useDolt) {
      try {
        this._writeQuestToDolt(issueId, questData);
        return;
      } catch (e) {
        console.error('Dolt write failed, falling back to JSON:', e.message);
      }
    }
    this._writeQuestToJson(issueId, questData);
  }

  saveQuest(issueId, questData) {
    if (this.useDolt) {
      try {
        this._writeQuestToDolt(issueId, questData);
        return;
      } catch (e) {
        console.error('Dolt write failed, falling back to JSON:', e.message);
      }
    }

    const releaseLock = this.acquireDbLock();
    try {
      this._writeQuestToJson(issueId, questData);
    } finally {
      releaseLock();
    }
  }

  // Atomically applies `mutator` to the freshest stored quest and
  // persists the result. An operation whose work spans a slow step
  // between load and save (sync's GitHub request) must mutate through
  // here: saving the snapshot it loaded before that step would
  // silently overwrite a concurrent update (e.g. a close that
  // completed the quest in the meantime). The mutator receives the
  // current stored quest and returns the quest to store, or null to
  // abort the write. Returns the stored quest, the unmodified current
  // quest when the mutator aborts, or null when no quest is stored
  // for issueId.
  //
  // The DB lock is held only for this load-mutate-store step — never
  // across a network call — and serializes the step against every
  // other updateQuest and against saveQuest's JSON writes, on both
  // backends. It is the same lock, taken in the same seat-then-store
  // order as everywhere else in this file, so no new lock ordering
  // is introduced; _storeQuest never re-acquires it, so the spin
  // lock cannot self-deadlock here.
  updateQuest(issueId, mutator) {
    const releaseLock = this.acquireDbLock();
    try {
      const current = this.loadQuest(issueId);
      if (!current) {
        return null;
      }
      const updated = mutator(current);
      if (!updated) {
        return current;
      }
      this._storeQuest(issueId, updated);
      return updated;
    } finally {
      releaseLock();
    }
  }

  acquireDbLock() {
    const lockPath = this.jsonDb + '.lock';
    while (true) {
      try {
        const fd = fs.openSync(lockPath, 'wx');
        return () => {
          try { fs.closeSync(fd); } catch (e) {}
          try { fs.unlinkSync(lockPath); } catch (e) {}
        };
      } catch (err) {
        if (err.code !== 'EEXIST') {
          throw err;
        }
        // Drop locks abandoned by crashed writers so the DB cannot wedge.
        try {
          if (Date.now() - fs.statSync(lockPath).mtimeMs > 30000) {
            fs.unlinkSync(lockPath);
            continue;
          }
        } catch (e) {}
        const start = Date.now();
        while (Date.now() - start < 50) {}
      }
    }
  }
}

function tryReclaimSeat(lockPath) {
  const ownerPath = path.join(lockPath, 'owner');
  let pid = null;
  try {
    pid = parseInt(fs.readFileSync(ownerPath, 'utf8').trim(), 10);
  } catch (e) {}

  if (Number.isInteger(pid) && pid > 0) {
    // The seat has a recorded owner; it is abandoned only if that process
    // no longer exists. PID reuse can make a dead owner's seat look held
    // (the recycled PID belongs to a live process), never the reverse, so
    // this fails safe: the seat frees when that process exits.
    try {
      process.kill(pid, 0);
      return false;
    } catch (err) {
      if (err.code !== 'ESRCH') {
        return false; // EPERM: owner exists under another user
      }
    }
  } else {
    // No ownership record: the seat predates ownership recording, or its
    // owner has not written the record yet. Reclaim only once the seat is
    // clearly stale (same 30s rule as the DB lock above) so a seat that
    // is mid-acquisition is never stolen from a live process.
    try {
      if (Date.now() - fs.statSync(lockPath).mtimeMs < 30000) {
        return false;
      }
    } catch (e) {
      return false;
    }
  }

  try { fs.unlinkSync(ownerPath); } catch (e) {}
  try {
    fs.rmdirSync(lockPath);
    return true;
  } catch (e) {
    return false;
  }
}

function acquireConcurrencySlot(lockDir, maxConcurrent = 3) {
  if (!fs.existsSync(lockDir)) {
    fs.mkdirSync(lockDir, { recursive: true });
  }

  while (true) {
    for (let i = 0; i < maxConcurrent; i++) {
      const lockPath = path.join(lockDir, `lock_${i}`);
      const ownerPath = path.join(lockPath, 'owner');
      try {
        fs.mkdirSync(lockPath);
        // Record ownership so a later process can reclaim this seat if
        // this one is killed before its exit hooks can release it.
        try {
          fs.writeFileSync(ownerPath, String(process.pid), 'utf8');
        } catch (e) {}
        console.error(`Acquired Roundtable seat ${i + 1} of ${maxConcurrent}`);
        return () => {
          try {
            fs.unlinkSync(ownerPath);
          } catch (e) {}
          try {
            fs.rmdirSync(lockPath);
          } catch (e) {}
        };
      } catch (err) {
        if (err.code !== 'EEXIST') {
          throw err;
        }
        if (tryReclaimSeat(lockPath)) {
          i--; // Seat was abandoned; retry it immediately.
        }
      }
    }
    console.error('Roundtable seats full. Waiting for slot...');
    const start = Date.now();
    while (Date.now() - start < 1000) {}
  }
}

function printHelpAndExit() {
  console.log(`
Excalibur Quest remediation coordinator.

Usage: node quest_helper.js <command> [options]

Commands:
  init   Initialize remediation beads database
  sync   Sync local beads state to GitHub
  close  Close beads and finalize quest

Options:
  --issue-id      Target GitHub issue number (required)
  --reviews-path  Path to JSON review findings file
  --repo-owner    GitHub repository owner (sync only)
  --repo-name     GitHub repository name (sync only)
  --output        Output JSON status file path (required)
`);
  process.exit(1);
}

function parseArgs() {
  const args = {};
  const argv = process.argv.slice(2);
  const command = argv[0];
  if (!command || !['init', 'sync', 'close'].includes(command)) {
    printHelpAndExit();
  }
  args.command = command;

  for (let i = 1; i < argv.length; i++) {
    if (argv[i].startsWith('--')) {
      const key = argv[i].slice(2).replace(/-([a-z])/g, (g) => g[1].toUpperCase());
      const val = argv[i + 1];
      if (val && !val.startsWith('--')) {
        args[key] = val;
        i++;
      } else {
        args[key] = true;
      }
    }
  }

  if (!args.issueId || !args.output) {
    console.error('Error: --issue-id and --output are required.\n');
    printHelpAndExit();
  }
  return args;
}

function runInit(args, db) {
  let beads = [];
  if (args.reviewsPath && fs.existsSync(args.reviewsPath)) {
    try {
      const reviews = JSON.parse(fs.readFileSync(args.reviewsPath, 'utf8'));
      if (reviews.findings) {
        beads = reviews.findings.map((r, idx) => ({
          id: `bead-${idx + 1}`,
          title: r.title || `Remediation item ${idx + 1}`,
          severity: r.severity || 'MEDIUM',
          status: 'PENDING'
        }));
      }
    } catch (e) {
      console.error('Failed to load reviews path:', e.message);
    }
  }

  if (beads.length === 0) {
    beads = [
      { id: 'bead-1', title: 'Audit source for security vulnerabilities', severity: 'CRITICAL', status: 'PENDING' },
      { id: 'bead-2', title: 'Verify tokio async I/O migrations', severity: 'HIGH', status: 'PENDING' },
      { id: 'bead-3', title: 'Check static analyzer schemas', severity: 'MEDIUM', status: 'PENDING' }
    ];
  }

  const questData = {
    issue_id: args.issueId,
    status: 'ACTIVE',
    beads: beads,
    created_at: Date.now() / 1000
  };
  db.saveQuest(args.issueId, questData);
  return questData;
}

function runSync(args, db) {
  const quest = db.loadQuest(args.issueId);
  if (!quest) {
    console.error(`Error: Quest for issue ${args.issueId} not initialized.`);
    process.exit(1);
  }

  if (!args.repoOwner || !args.repoName) {
    console.error('Error: --repo-owner and --repo-name are required for sync.');
    process.exit(1);
  }

  console.error(`Syncing beads status to GitHub repo ${args.repoOwner}/${args.repoName}...`);

  let commentBody = `### Excalibur Quest Sync Update\n\n**Quest Status:** ${quest.status}\n\n**Beads Progress:**\n`;
  for (const b of quest.beads || []) {
    const statusBox = b.status === 'COMPLETED' ? '[x]' : '[ ]';
    commentBody += `- ${statusBox} **${b.id}**: ${b.title} (${b.severity})\n`;
  }

  let synced;
  try {
    execFileSync('gh', ['issue', 'comment', String(args.issueId), '--repo', `${args.repoOwner}/${args.repoName}`, '--body', commentBody], { stdio: 'pipe' });
    console.error('Successfully synced comment to GitHub.');
    synced = true;
  } catch (e) {
    console.error('Warning: gh CLI sync failed (continuing locally):', e.message);
    synced = false;
  }

  // The GitHub request above is the slow step: the snapshot loaded at
  // the top of this function may be stale by now — a concurrent close
  // may have completed the quest, or the quest may have been
  // re-initialized. Apply only the field sync owns (github_synced)
  // onto the freshest stored quest instead of saving the stale
  // snapshot wholesale, which would silently revert the concurrent
  // update (a COMPLETED quest must never come back as ACTIVE).
  let applied = true;
  const result = db.updateQuest(args.issueId, (current) => {
    if (current.created_at !== quest.created_at) {
      // The stored quest is a new incarnation created by a re-init
      // while the GitHub request ran; sync's result is not its own.
      applied = false;
      return null;
    }
    if (current.status !== quest.status) {
      console.error(`Note: quest ${args.issueId} was updated concurrently (${quest.status} -> ${current.status}); the newer state is preserved.`);
    }
    current.github_synced = synced;
    return current;
  });
  if (!result) {
    console.error(`Error: Quest for issue ${args.issueId} no longer exists.`);
    process.exit(1);
  }
  if (!applied) {
    console.error(`Warning: quest ${args.issueId} was re-initialized during sync; the sync result was not recorded on the new quest.`);
  }
  return result;
}

function runClose(args, db) {
  const quest = db.loadQuest(args.issueId);
  if (!quest) {
    console.error(`Error: Quest for issue ${args.issueId} not found.`);
    process.exit(1);
  }

  // Complete the freshest stored quest rather than the snapshot
  // above, so a metadata update that landed after the load (e.g. a
  // sync's github_synced stamp) is not clobbered — the mirror image
  // of the sync-side fix in runSync.
  const result = db.updateQuest(args.issueId, (current) => {
    current.status = 'COMPLETED';
    if (current.beads) {
      current.beads.forEach(b => b.status = 'COMPLETED');
    }
    return current;
  });
  if (!result) {
    console.error(`Error: Quest for issue ${args.issueId} not found.`);
    process.exit(1);
  }
  console.error(`Successfully closed quest ${args.issueId}.`);
  return result;
}

function main() {
  const args = parseArgs();

  let workspaceRoot;
  try {
    workspaceRoot = execSync('git rev-parse --show-toplevel', { encoding: 'utf8' }).trim();
  } catch (e) {
    workspaceRoot = process.cwd();
  }

  const lockDir = path.join(workspaceRoot, '.excalibur_locks');
  const cleanup = acquireConcurrencySlot(lockDir);

  // Register cleanup exit hooks
  process.on('exit', cleanup);
  process.on('SIGINT', () => { cleanup(); process.exit(); });
  process.on('SIGTERM', () => { cleanup(); process.exit(); });

  try {
    const db = new QuestDB(path.join(workspaceRoot, '.excalibur_quest'));
    let result;

    if (args.command === 'init') {
      result = runInit(args, db);
    } else if (args.command === 'sync') {
      result = runSync(args, db);
    } else if (args.command === 'close') {
      result = runClose(args, db);
    }

    try {
      fs.writeFileSync(args.output, JSON.stringify(result, null, 2), 'utf8');
      console.log(`Success! Data written to: ${args.output}`);
    } catch (e) {
      console.error(`Error writing output to ${args.output}:`, e.message);
      process.exit(1);
    }
  } catch (e) {
    // A command whose work could not be persisted (or otherwise
    // failed) must not report success: exit non-zero, before any
    // output file is written. The seat is still released — by the
    // finally below on normal unwind, and by the exit hook on
    // process.exit.
    console.error('Error:', e.message);
    process.exit(1);
  } finally {
    cleanup();
  }
}

main();
