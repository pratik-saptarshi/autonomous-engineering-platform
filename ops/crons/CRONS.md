# Scheduler wiring — NeuroStrata lifecycle jobs (current reality)

This page records the scheduled jobs that actually exist for the
NeuroStrata lifecycle, as of 2026-11-04 (idle-reaper status corrected
2026-11-11). Retired jobs are listed with their evidence so a future
reader does not re-wire them by mistake.

| Job | Cadence | Runs | Status |
| --- | --- | --- | --- |
| `neurostrata-watchdog` | Every 2h | `bash ~/workspace/neurostrata/bin/watchdog-backup.sh` | Current — see `watchdog-cron-record.md` and the canonical script in `ops/bin/watchdog-backup.sh` |
| `neurostrata-idle-reaper` | Every 15m | `bash ~/workspace/neurostrata/bin/idle-reaper.sh` | Current — 2026-11-04 retirement reversed 2026-11-11, see `ops/bin/RETIRED.md` |
| `neurostrata-export` | Was every 168h (7d) | `neurostrata-mcp export-graph` to `~/workspace/neurostrata/exports/` | Retired — see evidence below |

## Standalone idle reaper — retirement reversed (2026-11-11)

The 2026-11-04 retirement of this job was based on evidence that no
longer holds: a live `~/workspace/neurostrata/bin/idle-reaper.sh`
exists, the `neurostrata-idle-reaper` cron (every 15m) is present in
the environment goal's cron set, and `reaper.log` is actively
written (the watchdog's `reaped_expected` parses it). Idle-stop was
not absorbed into the watchdog: the current watchdog has no idle
check. The reaper is a current job. Full record: `ops/bin/RETIRED.md`.

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
