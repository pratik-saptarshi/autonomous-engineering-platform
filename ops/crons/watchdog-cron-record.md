# Scheduler record: NeuroStrata watchdog

Derived from the live cron definition's body only (front-matter discarded;
it carries internal scheduler IDs that must never reach a public repo).
Source re-read at build time: `~/workspace/goals/engineering-ecosystem-limitation-fixes/crons/hourly/neurostrata-watchdog__interval@2h.md`,
body lines 20–24. Corrections recorded 2026-11-04.

| Field | Value |
| --- | --- |
| Job | `neurostrata-watchdog` |
| Cadence | Every 2 hours |
| Runs | `bash ~/workspace/neurostrata/bin/watchdog-backup.sh` (canonical copy: `ops/bin/watchdog-backup.sh` in this repo) |
| Reports when | Daemon state, whether the database changed, whether a backup was taken and uploaded, and any errors. If nothing changed and the daemon is healthy, one line is enough. |

## Current behavior (corrected)

1. Check the daemon. If the daemon is down, run change detection anyway —
   the daemon is **not** restarted by this job. Under the on-demand model
   the daemon stays down after a watchdog run; the MCP client restarts it
   on the next coding loop. This script itself never restarts the daemon.
2. Checksum the database and compare against the last recorded checksum.
3. Only when the checksum changed since the last backup: stop the daemon,
   take a verified copy, upload the copy to the configured Drive folder,
   and record the new checksum. The daemon stays down after the backup.
4. If nothing changed:
   - Active daemon: leave it running and report the unchanged state in one line.
   - Idle daemon: the daemon is stopped by design (see the `IDLE_SECS` idle check in `ops/bin/watchdog-backup.sh`), then report the unchanged state.

## Corrections applied 2026-11-04

- The source body claimed the daemon is restarted by the scheduler when
  down. That is stale: the on-demand model replaced scheduler restarts
  with client-side restart on next use.
- The source body claimed the daemon is restarted after a backup is taken.
  That is stale: the daemon stays down after backup by design.
- The source body's agent-runtime instruction (where to write
  observations) was dropped: it does not belong in a scheduler record.

## Follow-up (outside this PR)

The live cron body itself still carries the stale sentences above. Fixing
the live cron definition is a separate step from publishing this record.
