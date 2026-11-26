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

## Gating autonomous jobs with the boot gate

`ops/bin/cron-with-boot-gate.sh` runs `scripts/boot-gate.sh` before a scheduled job and refuses to start the job when the gate fails. Wrap a job by putting the wrapper in front of its command in the scheduler entry:

```bash
ops/bin/cron-with-boot-gate.sh <job-name> -- <command...>
```

- A passing gate hands over to the command, prints the gate's per-check lines (including `BOOT-GATE-RESULT: POLICY-OK`), and propagates the job's exit status unchanged.
- While the job runs, the wrapper heartbeats `~/workspace/neurostrata/.last-daemon-use` (override with `AEP_DAEMON_ACTIVITY_FILE`) so the watchdog cannot mistake a long job that uses the daemon for an idle one and stop it mid-run.
- A failing gate logs `CRON-GATE: ABORT <job-name> rc=<rc>` on stderr, prints the gate's own reason, exits with the gate's status, and never starts the job.
- A missing or non-executable gate is a failure with `rc=127`. The wrapper never runs a job it could not gate.
- `AEP_BOOT_GATE_BIN` overrides the gate path and `AEP_CRON_GATE_LOG` names a file that also receives the ABORT line.

This repo ships the wrapper and its test (`ops/tests/test_cron_boot_gate.sh`). It does not edit any host scheduler, so no job is gated until an operator changes that job's scheduler entry. Gate every job that starts an autonomous agent session.

### Exclusion: the NeuroStrata watchdog

Do not wrap `neurostrata-watchdog`. The gate's daemon check needs an answering daemon, while the watchdog must run even when the daemon is down so it can capture crash evidence and back up a changed database (the canonical watchdog never restarts the daemon itself; recover manually with `nohup`). Wrapping it behind the boot gate would block crash capture and quiescent backups whenever the daemon is down. The watchdog stays ungated and keeps the entry shown in the table above.
