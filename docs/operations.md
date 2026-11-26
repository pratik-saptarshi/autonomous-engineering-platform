# Operations

## Scheduler

Job id `ralph-loop`, interval 2 h, timeout 2 h. Definition: `~/workspace/cron.d/hourly/ralph-loop__interval@2h.md` (read-only copy; manage via the cron tools).

```text
cron.list                 # all schedules
cron.view   {id: ralph-loop}
cron.run    {id: ralph-loop, reason: "..."}   # manual run
cron.remove {id: ralph-loop}
```

Runs report to chat only when tasks were completed or attention is needed. An empty backlog ends the run with a one-line result in run history.

### Gating scheduled jobs with the boot gate

`ops/bin/cron-with-boot-gate.sh <job-name> -- <command...>` runs `scripts/boot-gate.sh` first. If the gate fails, the job does not start and the wrapper logs `CRON-GATE: ABORT <job-name> rc=<rc>`. If the gate passes, the wrapper runs the command and its exit status is the job's exit status. Put the wrapper in front of the command of any job that starts an autonomous agent session. Do not put it in front of the NeuroStrata watchdog, because the gate needs a live daemon and the watchdog is what recovers a dead one (see `ops/crons/CRONS.md`). Changing a scheduler entry is an operator act, so a job is gated only after its entry is changed.

## NeuroStrata daemon

```bash
~/go/bin/neurostrata-mcp status   # health, lock, store size
tail -20 ~/.local/share/neurostrata/daemon.log   # startup / model load
# restart (direct nohup, appending so the crash evidence survives):
pkill -f 'neurostrata-mcp daemon'
HF_HUB_OFFLINE=1 nohup ~/go/bin/neurostrata-mcp daemon >> ~/.local/share/neurostrata/daemon.log 2>&1 &
```

If the daemon is down, restart it with the nohup command above. A bare MCP spawn does not reliably start the daemon (verified 2026-10-16, see `docs/limitation-analysis.md` section 1 and `docs/daemon-lifecycle-contract.md`). The watchdog cron also revives a daemon that died unexpectedly on its next run.

## Watchdog and backups

A cron job (`neurostrata-watchdog`, every 2 h) runs `~/workspace/neurostrata/bin/watchdog-backup.sh`: it revives a dead daemon, checksums the database, and only when the checksum changed it takes a verified copy (SIGTERM for a checkpoint-consistent copy, sha256-verified) and uploads it to Google Drive (`Musebot-Astro/database`). The last checksum lives in `~/workspace/neurostrata/.last-db-sha256`; run output goes to `~/workspace/neurostrata/watchdog.log`.

### Deploying the canonical watchdog

The canonical watchdog is `ops/bin/watchdog-backup.sh`. The script on the VM can fall behind it, so check before you trust either. From a checkout of this repo on the VM:

```bash
ops/bin/deploy-watchdog.sh --check     # exit 0 only when the deployed script matches ops/
ops/bin/deploy-watchdog.sh --dry-run   # show what a deploy would do
ops/bin/deploy-watchdog.sh --apply     # test, back up, deploy atomically, write a receipt
```

`--apply` runs `bash -n` and the behavioral suite first, saves a drifted target as `watchdog-backup.sh.bak.<UTC timestamp>` for rollback, and writes `.watchdog-deploy-receipt.json` beside the target with the UTC time, the source commit, and the SHA-256. The target defaults to `~/workspace/neurostrata/bin/watchdog-backup.sh` and can be changed with `DEPLOY_TARGET`. Details are in `ops/README.md`, section "Deployment".

### Reference vs VM adaptation

The repo carries the portable reference (`scripts/watchdog-backup.sh`); the VM runs an adaptation of it. The lifecycle now lives in both: change detection before any stop/restart decision, no stop when the DB is unchanged, restart-if-unexpectedly-down, restart-after-backup with a 60 s health poll, and an EXIT trap that restarts the daemon after any stop. "Down is intentional" is the reference's portable `WATCHDOG_LEAVE_DOWN_MARKER` file check.

What remains different in the VM adaptation — check this list before syncing either copy over the other:

- Paths: the binary is `~/go/bin/neurostrata-mcp` (reference: `~/workspace/neurostrata/bin/`), and the daemon log is `~/.local/share/neurostrata/daemon.log` (reference: `~/workspace/neurostrata/daemon.log`). Both rotate the daemon log at start — the adaptation to a timestamped sibling file (10 kept), the reference into its `logs/` directory (5 kept).
- Health-poll budget: the reference reads it from `WATCHDOG_HEALTH_TIMEOUT` (default 60); the adaptation's `wait_healthy` carries the same 60 s as a built-in default — no env knob.
- Stop failure: in the reference, a daemon that will not stop fails the run (exit 1). In the adaptation it logs ERROR and exits 0, skipping that run's backup with the daemon left running.
- "Down is intentional" is decided by the reaper-log heuristic (`reaped_expected()` compares the newest REAPED line in `reaper.log` against the last start in `watchdog.log`) — the reaper's state file is, in effect, the marker's content for this adaptation.
- One behavioral difference: with the marker present the reference exits before doing anything (no backup even if the DB changed), while the adaptation leaves a reaped daemon down only when the DB is unchanged and still takes a changed backup, restarting afterwards.
- Drive mechanics: a failed upload is retried once in-run and never fails the deployed run; the reference exits 1 on a configured-but-failing upload and lets the catch-up path repair the gap on the next run.

To restore the model cache after a wipe:

```bash
sha256sum -c ~/workspace/neurostrata/model-cache-backup.sha256
tar -xzf ~/workspace/neurostrata/model-cache-backup.tar.gz -C ~/.cache/neuro/models
```

## Memory backend

All operations go through the stdio client:

```bash
BIN=~/workspace/custom-connectors/custom.neurostrata/bin/client.py
python3 $BIN list-tools
python3 $BIN call-tool --name neurostrata_search_memory --arguments-file search.json  # {query, namespace}
python3 $BIN call-tool --name neurostrata_add_memory    --arguments-file add.json     # {content, namespace, project_root}
python3 $BIN call-tool --name neurostrata_get_memory    --arguments-file get.json     # {id, namespace}
python3 $BIN call-tool --name neurostrata_archive_memory --arguments-file a.json      # {id, namespace}
python3 $BIN call-tool --name neurostrata_list_namespaces --arguments-file empty.json # {}
```

Namespace convention: `global` for broadly-applicable lessons, project namespaces for project-specific ones. Prefer `neurostrata_supersede_memory` over archiving when a correction matters.

## beads

Per-repo issue tracking. Each repo carries its own database at `<repo>/.beads/embeddeddolt`.

```bash
cd <repo> && bd init
bd create "Title" --type task --priority 2
bd list / bd show <id> / bd close <id> / bd search "text"
bd status   # overview
```

Commit `.beads/` to version issues with the repo, or gitignore it to keep issues local.

## open-code-review

Delegation mode needs no API key:

```bash
cd <repo>
ocr delegate preview --format json
ocr delegate rule --format json <files>
```

Full `ocr review` / `ocr scan` require a configured LLM API key.

## open-connector

```bash
bash ~/workspace/custom-connectors/custom.openconnector/bin/start.sh   # ~20 s
python3 .../bin/oc.py list <service>
python3 .../bin/oc.py doc <action.id>
python3 .../bin/oc.py run <action.id> '<input-json>'
bash .../bin/stop.sh
```

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Daemon fails: `invalid peer certificate: UnknownIssuer` | TLS-intercepting proxy; binary does not trust the proxy CA | Pre-seed the model cache (runbook section 2); the binary never downloads on a cache hit |
| MCP client: invalid JSON-RPC message | Server emits `{}` after `notifications/initialized` | Tolerate non-JSON-RPC stdout lines; do not fail on them |
| `bd doctor`: "not yet supported in embedded mode" | Expected | Use `bd doctor --check={artifacts,conventions,pollution}`, `bd ping` |
| Provider calls fail from open-connector | Egress guard | Allowlist the host via `OOMOL_CONNECT_EGRESS_TRUSTED_HOSTS` |
| `neurostrata-mcp status`: "down" | Daemon died (e.g. VM restart) | Restart via nohup (`nohup …/neurostrata-mcp daemon … &`); the watchdog cron also revives it on its next run. Note: a bare MCP spawn does *not* reliably auto-start the daemon — verified 2026-10-16. |
| Watchdog always reports "another watchdog run in progress" | The daemon inherited the script's flock FD and holds the lock for its whole lifetime | Upgrade to the fixed script (closes the FD with `9>&-` on the daemon spawn); kill the old daemon once so the stale lock clears, then let the watchdog restart it |
| Cron run reports "backlog empty" | No to-do tasks | Add tasks to `~/workspace/ralph/backlog.md` |
| Loop works an example task | Backlog still has seed examples | Replace `RALPH-001`/`RALPH-002` with real work or mark them done |
