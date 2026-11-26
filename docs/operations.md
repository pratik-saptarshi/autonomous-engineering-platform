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

`ops/bin/cron-with-boot-gate.sh <job-name> -- <command...>` runs `scripts/boot-gate.sh` first. If the gate fails, the job does not start and the wrapper logs `CRON-GATE: ABORT <job-name> rc=<rc>`. If the gate passes, the wrapper runs the command and its exit status is the job's exit status. Put the wrapper in front of the command of any job that starts an autonomous agent session. Do not put it in front of the NeuroStrata watchdog, because the gate needs an answering daemon and the watchdog must run while the daemon is down to capture crash evidence and back up a changed database (see `ops/crons/CRONS.md`). Changing a scheduler entry is an operator act, so a job is gated only after its entry is changed.

## NeuroStrata daemon

```bash
~/go/bin/neurostrata-mcp status   # health, lock, store size
tail -20 ~/workspace/neurostrata/daemon.log   # startup / model load
# restart (direct nohup, appending so the crash evidence survives):
pkill -f 'neurostrata-mcp daemon'
HF_HUB_OFFLINE=1 nohup ~/go/bin/neurostrata-mcp daemon >> ~/workspace/neurostrata/daemon.log 2>&1 &
```

The canonical watchdog (`ops/bin/watchdog-backup.sh`) reads and rotates `~/workspace/neurostrata/daemon.log`, so the commands above use that path. The deployed adaptation described under "Reference vs VM adaptation" below logs to `~/.local/share/neurostrata/daemon.log` instead. Use whichever file your deployed watchdog reads.

If the daemon is down, restart it directly with the `nohup` command above. A bare MCP spawn does not reliably start the daemon (verified 2026-10-16, see `docs/limitation-analysis.md` section 1 and `docs/daemon-lifecycle-contract.md`). The canonical watchdog (`ops/bin/watchdog-backup.sh`) never restarts the daemon itself; it captures crash evidence and backs up a changed database.

## Watchdog and backups

A cron job (`neurostrata-watchdog`, every 2 h) runs `~/workspace/neurostrata/bin/watchdog-backup.sh`. In the canonical on-demand script (`ops/bin/watchdog-backup.sh`), the watchdog never restarts the daemon: it captures crash evidence after an unexpected death, checksums the database, stops an idle daemon when needed, and only when the checksum changed takes a verified copy (SIGTERM for a checkpoint-consistent copy, sha256-verified) and uploads it to Google Drive (`Musebot-Astro/database`). The last checksum lives in `~/workspace/neurostrata/.last-db-sha256`; run output goes to `~/workspace/neurostrata/watchdog.log`.

### Deploying the canonical watchdog

The canonical watchdog is `ops/bin/watchdog-backup.sh`. The script on the VM can fall behind it, so check before you trust either. From a checkout of this repo on the VM:

```bash
ops/bin/deploy-watchdog.sh --check     # exit 0 only when the deployed script matches ops/
ops/bin/deploy-watchdog.sh --dry-run   # show what a deploy would do
ops/bin/deploy-watchdog.sh --apply     # test, back up, deploy atomically, write a receipt
```

`--apply` runs `bash -n` and the behavioral suite first, saves a drifted target as `watchdog-backup.sh.bak.<UTC timestamp>` for rollback, and writes `.watchdog-deploy-receipt.json` beside the target with the UTC time, the source commit, and the SHA-256. The target defaults to `~/workspace/neurostrata/bin/watchdog-backup.sh` and can be changed with `DEPLOY_TARGET`. Details are in `ops/README.md`, section "Deployment".

### Canonical vs legacy vs VM adaptation

Three watchdog artifacts exist in this ecosystem; check `ops/README.md` and `ops/bin/WATCHDOG-DELTAS.md` as the single source of truth for the canonical script:

- **Canonical (`ops/bin/watchdog-backup.sh`):** on-demand model; resolves `neurostrata-mcp` preferring `~/go/bin/neurostrata-mcp` (then `~/workspace/neurostrata/bin/neurostrata-mcp`, then `PATH`, or `AEP_MCP_BIN`); **never restarts the daemon itself**; captures crash bundles and rotates `~/workspace/neurostrata/daemon.log` to `daemon.log.<UTC>.pre-restart` on unexpected deaths (Delta F/G); fails loudly (exit 1) if the daemon will not stop (Delta E).
- **Legacy portable reference (`scripts/watchdog-backup.sh`):** older always-on-era script kept with `scripts/tests/test_watchdog.sh`. It still carries restart-if-down, restart-after-backup, EXIT-trap restart, and `WATCHDOG_LEAVE_DOWN_MARKER`. Do not treat its always-on restart promises as current canonical practice.
- **Historical VM adaptation (deployed pre-deploy-kit record):** ran the older always-on lifecycle with `~/go/bin/neurostrata-mcp`, `~/.local/share/neurostrata/daemon.log`, stop-failure exit 0, `reaped_expected()` heuristic, and single in-run Drive retry. Run `ops/bin/deploy-watchdog.sh --check` on the host before trusting what is live.

To restore the model cache after a wipe:

```bash
sha256sum -c ~/workspace/neurostrata/model-cache-backup.sha256
tar -xzf ~/workspace/neurostrata/model-cache-backup.tar.gz -C ~/.cache/neuro/models
```

## Memory backend

Live operations use the `neurostrata-mcp` CLI (`~/go/bin/neurostrata-mcp status`, `neurostrata-mcp list <namespace>`) and MCP stdio tools registered in the client (`neurostrata_search_memory`, `neurostrata_add_memory`, `neurostrata_get_memory`, `neurostrata_archive_memory`, `neurostrata_list_namespaces`, `neurostrata_supersede_memory`).

> **Planned / not built (VM record only):** The earlier stdio wrapper `~/workspace/custom-connectors/custom.neurostrata/bin/client.py` is not built in this repo (see `docs/runbook.md` Appendix A). Do not expect `client.py` on a fresh host.

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
| `neurostrata-mcp status`: "down" | Daemon died (e.g. VM restart) | Restart directly via `nohup` (`HF_HUB_OFFLINE=1 nohup ~/go/bin/neurostrata-mcp daemon >> ~/workspace/neurostrata/daemon.log 2>&1 &`). The canonical watchdog does not restart the daemon, and a bare MCP spawn does *not* reliably start it (verified 2026-10-16). |
| Watchdog always reports "another watchdog run in progress" | The daemon inherited the script's flock FD and holds the lock for its whole lifetime | Upgrade to the canonical script (`ops/bin/deploy-watchdog.sh --apply`); kill the old daemon once so the stale lock clears, then restart the daemon directly via `nohup`. |
| Cron run reports "backlog empty" | No to-do tasks | Add tasks to `~/workspace/ralph/backlog.md` |
| Loop works an example task | Backlog still has seed examples | Replace `RALPH-001`/`RALPH-002` with real work or mark them done |
