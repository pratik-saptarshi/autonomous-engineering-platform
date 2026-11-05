# Scheduler wiring — NeuroStrata lifecycle jobs (current reality)

This page records the scheduled jobs that actually exist for the
NeuroStrata lifecycle, as of 2026-11-04. Retired jobs are listed with
their evidence so a future reader does not re-wire them by mistake.

| Job | Cadence | Runs | Status |
| --- | --- | --- | --- |
| `neurostrata-watchdog` | Every 2h | `bash ~/workspace/neurostrata/bin/watchdog-backup.sh` | Current — see `watchdog-cron-record.md` and the canonical script in `ops/bin/watchdog-backup.sh` |
| `neurostrata-idle-reaper` | Was every 15m | `bash ~/workspace/neurostrata/bin/idle-reaper.sh` | Retired — see `ops/bin/RETIRED.md` |
| `neurostrata-export` | Was every 168h (7d) | `neurostrata-mcp export-graph` to `~/workspace/neurostrata/exports/` | Retired — see evidence below |

## Retired: standalone idle reaper

Evidence: no live `~/workspace/neurostrata/bin/idle-reaper.sh`, no
idle-reaper cron in `~/workspace/cron.d` or goal crons, no `reaper.log`
under `~/workspace/neurostrata/`. Full note: `ops/bin/RETIRED.md`.
Idle-stop behavior was absorbed, not abolished: it lives on inside the
canonical watchdog (`ops/bin/watchdog-backup.sh`, `IDLE_SECS` idle check).

## Retired: export job

Evidence verified at build time (2026-11-04):

- No cron file for an export job exists in `~/workspace/cron.d` or in any
  goal's `crons/` directory (searched for export-job and export-graph
  references; no matches).
- No `~/workspace/neurostrata/exports/` directory exists, so no export
  output is being produced or retained.
- No export script exists in `~/workspace/neurostrata/bin/` (only the
  daemon binary and `watchdog-backup.sh`).
- The only NeuroStrata cron in the live goal crons is the watchdog
  (every 2h) plus an unrelated one-shot validation job.

The kit's earlier scheduler page described a 168h export job; that job
no longer exists in the live scheduler. Do not re-create it from the kit
page without a fresh decision.
