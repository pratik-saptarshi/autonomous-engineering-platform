# Scheduler wiring — the three NeuroStrata crons

The daemon runs under `nohup` (this environment has no user D-Bus, so the
shipped systemd user units are staged but inactive). These three scheduled
jobs are its lifecycle. All times America/Chicago. All three are silent on
success; each reports to chat only on its stated failure condition.

| Job | Cadence | Runs | Reports when |
| --- | --- | --- | --- |
| `neurostrata-watchdog` | every 2h | `bash ~/workspace/neurostrata/bin/watchdog-backup.sh`, then health-checks `neurostrata-mcp status` | daemon down after 2 restart attempts, or `ERROR` in the run's log lines |
| `neurostrata-idle-reaper` | every 15m | `bash ~/workspace/neurostrata/bin/idle-reaper.sh` | never (log-only: `~/workspace/neurostrata/reaper.log`) |
| `neurostrata-export` | every 168h (7d) | `neurostrata-mcp export-graph` → `~/workspace/neurostrata/exports/memories-YYYYMMDD.json` (keeps newest 4) | the export fails |

## Watchdog (body vendored verbatim)

See `watchdog-cron-body.md` in this directory. Key terms: max 2 restart attempts
per run; a full run (stop → consistent copy → sha256 → Drive upload → restart →
health check) takes ~30–45s; change detection runs *before* any stop, and a
daemon the reaper cleanly stopped is left down on no-change runs (it restarts
on demand — see the reaper contract below).

## Idle reaper (spec — the live body is a one-liner around the script)

Run `idle-reaper.sh` every 15 minutes, silent. The script itself enforces the
whole contract (all five conditions, clean shutdown only via
`neurostrata-mcp shutdown`, never a kill): see `bin/idle-reaper.sh` header and
`runbooks/IDLE-REAPER.md`. Rollback is disabling this cron.

## Export (spec — the live body is a one-liner around the CLI)

Weekly `export-graph` with default flags. Deliberate decision: active memories
only — `--include-archived` is NOT passed; archived/tombstoned rows are covered
by the watchdog's DB file-copy tier instead. The export is read-only and never
touches daemon lifecycle; it skips if the daemon isn't answering (the watchdog
owns restarts).
