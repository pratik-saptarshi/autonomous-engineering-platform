# NeuroStrata Idle Reaper — Operations Runbook

Frees the daemon's ~800MB RSS when it sits idle. The reaper only ever shuts the
daemon down cleanly (`neurostrata-mcp shutdown`, checkpointed); restart paths
already exist and need no changes.

## Installed

- **Script:** `~/workspace/neurostrata/bin/idle-reaper.sh` (executable; do not edit without a new plan task)
- **Cron:** `neurostrata-idle-reaper` — interval every 15 min (`interval@15m`, America/Chicago), owner `goal:environment-maintenance-daemon-watchdog-backups`
- **Cron definition copy (read-only):** `~/workspace/goals/environment-maintenance-daemon-watchdog-backups/crons/minutely/neurostrata-idle-reaper__interval@15m.md`
- **Log:** `~/workspace/neurostrata/reaper.log` — one timestamped line per run: `SKIP <reason>` or `REAPED uptime=<Xm> conns=0`
- **Delivery:** silent. The log file is the record. The cron body instructs the run to end with a one-line status and send no chat message for routine SKIP/REAPED outcomes. The only chat-reporting case is the script itself being broken (missing/not executable/exit non-zero with no fresh log line).
- **Env overrides (all optional, read by the script at each run):**
  - `REAPER_MIN_UPTIME_MIN` — default `45`
  - `REAPER_LOCK_FILE` — default `$HOME/workspace/neurostrata/.watchdog.lock`
  - `REAPER_LOG` — default `$HOME/workspace/neurostrata/reaper.log`
- **Task-1 gate (cold-start latency, measured 2026-10-19):** `COLD_START_HEALTHY_S=5`, threshold 25s → **PASS**. (Gate: if a future measurement exceeds 25s, disable the reaper — the MCP stdio auto-start only waits ~30s for daemon readiness.)

## How it decides (all must hold to reap)

1. Watchdog lock free (`flock -n`; if held → SKIP, the watchdog is mid-run)
2. Daemon healthy (`neurostrata-mcp status` shows `status: healthy`)
3. Zero established TCP connections on 127.0.0.1:34343
4. Daemon uptime ≥ `REAPER_MIN_UPTIME_MIN` (default 45 min)
5. No `neurostrata-mcp` CLI process active (excluding the daemon itself)

## Rollback (disable)

Exact steps (cron tools; no file edits):

1. `cron.update` with `id: "neurostrata-idle-reaper"`, `enabled: false`.
2. Confirm: `cron.status` with `id: "neurostrata-idle-reaper"` shows `enabled: false`.

What happens next: nothing else to unwind. The daemon simply stays up; if it is
currently down (reaped), it stays down by design — the watchdog's no-change
path classifies it as reaped-expected and leaves it down. It comes back when
the DB next changes (that watchdog run restarts it after the backup), when an
MCP stdio spawn starts it on demand (verified in source), or when you start it
manually (below). No state files, no config changes, no other jobs depend on
the reaper.

How to verify rollback: `cron.list` (with `include_disabled: true`) shows the
cron disabled, and no new REAPED lines appear in
`~/workspace/neurostrata/reaper.log`. Do NOT verify by daemon health: a daemon
that was reaped-down at rollback time stays down indefinitely (above), so a
"not running" status is the expected state, not a failed rollback. To confirm
the daemon itself still works, demand-start it once (an MCP client spawn, or
the manual start below), see `status: healthy`, and leave it up — with the
reaper disabled it will stay up.

**Daemon down and needed NOW** — don't wait for the 2h watchdog; start it
exactly as the watchdog does, then confirm health:

```bash
HF_HUB_OFFLINE=1 nohup ~/go/bin/neurostrata-mcp daemon >> ~/.local/share/neurostrata/daemon.log 2>&1 &
sleep 10; ~/go/bin/neurostrata-mcp status | head -1   # expect: status: healthy
```

## Re-enable

1. `cron.update` with `id: "neurostrata-idle-reaper"`, `enabled: true`.
2. Confirm: `cron.status` with `id: "neurostrata-idle-reaper"` shows `enabled: true` and a `next_run_local` ~15 min out.
3. Wait for one natural 15-minute boundary (do NOT force-run), then verify with the Validate steps below.

## Validate

After any change (install, disable, re-enable, tuning):

```bash
tail -5 ~/workspace/neurostrata/reaper.log   # fresh SKIP/REAPED line, current timestamp
~/go/bin/neurostrata-mcp status 2>/dev/null | head -1   # healthy, or "daemon: not running" right after a REAPED line (expected)
ls ~/.config/NeuroStrata/data/db/ladybug.db.wal.unclean.* 2>/dev/null | wc -l   # unclean-shutdown markers; growth is the current steady state — see below
```

About the marker count: the markers grow in steady state at roughly the
watchdog's 2h cadence (nine present on 2026-10-26), and their source is
undetermined — no script reads them. A new marker after a REAPED line
therefore no longer proves an unclean reaper shutdown. Treat a new marker
as an attribution question: correlate its timestamp against `reaper.log`
and `watchdog.log` before concluding anything. The old prescription —
disable the cron on any new marker — is suspended pending that attribution;
followed literally, it would now fire on normal steady-state growth.

## Tuning

- `REAPER_MIN_UPTIME_MIN` (default 45): the idle threshold in minutes. Lower
  (e.g. 20) reaps sooner after activity ends — more memory-hours saved, but a
  brief MCP session costs a cold start (~5s measured) on next use. Higher
  (e.g. 90) keeps the daemon warm longer — fewer cold starts, less savings.
  Do NOT edit the script to change the default. The script runs in the cron
  worker's environment, so the only persistent path is exporting it in the
  cron body: `cron.update` with the complete revised body, adding
  `export REAPER_MIN_UPTIME_MIN=<n>` before the script invocation. The
  daemon/watchdog environment never reaches the script and cannot carry this
  setting.
- Do NOT tune by shortening the 15-min interval: the script already no-ops
  cheaply; more frequent runs only add log noise.
- After tuning, run the Validate steps and watch one full 2h watchdog cycle
  to confirm no interference (reaper log should show SKIP lock-held at most
  once per watchdog backup run, never a reap mid-backup).

## Known limitations

- **MCP stdio auto-spawn is source-verified only, never live-tested.** The
  binary spawns a detached daemon when an MCP client connects while the
  daemon is down (`src/main.rs`), but no MCP client exists in this
  environment yet, so the path has never executed here. Live testing is
  deferred until an MCP client is wired up; the 48h soak will not cover it.
- **The auto-spawned daemon runs without `HF_HUB_OFFLINE=1`.** It inherits
  the MCP client's environment, not the watchdog's. On this MITM-proxy VM a
  future MCP-triggered spawn could fail at model load — the same
  rustls/`SSL_CERT_FILE` issue that forced manual model seeding. When an MCP
  client is introduced, live-test the spawn path and confirm the model loads
  before relying on it.
