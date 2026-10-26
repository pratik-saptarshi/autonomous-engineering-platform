# Scheduler wiring — the three NeuroStrata crons

The daemon runs under `nohup` (this environment has no user D-Bus, so the
shipped systemd user units are staged but inactive — inventoried in the
synthesis page, `docs/neurostrata-memory-ops.md`). These three scheduled
jobs are its lifecycle. Job schedules are anchored in America/Chicago; the
timestamps the watchdog and reaper scripts write to their logs are pinned
to UTC (`export TZ=UTC` in both scripts) — never compare log lines against
local time. All three are silent on success; each reports to chat only on
its stated failure condition.

| Job | Cadence | Runs | Reports when |
| --- | --- | --- | --- |
| `neurostrata-watchdog` | every 2h | `bash ~/workspace/neurostrata/bin/watchdog-backup.sh`, then health-checks `neurostrata-mcp status` | daemon down after 2 restart attempts (with no expected-down line — see below), or `ERROR` in the run's log lines |
| `neurostrata-idle-reaper` | every 15m | `bash ~/workspace/neurostrata/bin/idle-reaper.sh` | the reaper script itself is broken (non-zero exit, or no fresh line in `~/workspace/neurostrata/reaper.log`); routine SKIP/REAPED outcomes never report |
| `neurostrata-export` | every 168h (7d) | `neurostrata-mcp export-graph` → `~/workspace/neurostrata/exports/memories-YYYYMMDD.json` (keeps newest 4) | the daemon is down (export skipped), the export fails, or the exported JSON fails verification |

## Watchdog (body vendored verbatim)

See `watchdog-cron-body.md` in this directory. Key terms, matching the body:
the expected-down branch comes first — if this run's log lines contain
`daemon down (reaped by idle-reaper, expected)` and no `ERROR`, the run is
routine: no attempt-2 retry, no outage alert, stay silent. Otherwise, max 2
restart attempts per run. Exit codes: the script exits 0 on both success
paths (no-change and successful backup); exit 1 on exactly two failures —
sha256 mismatch of the backup copy (the bad copy is deleted first), and
Drive catch-up failing twice on the no-change path. On the changed path a
Drive double-failure only logs `ERROR` and still exits 0 — the body's
`ERROR` rule, not the exit code, catches it. A full run (stop → consistent
copy → sha256 → Drive upload → restart → health check) takes ~10s since
the 2026-10-23 model switch (measured range 8–25s); the older ~30–45s
figure was the Nomic-era timing. Change detection runs *before* any stop,
and a daemon the reaper cleanly stopped is left down on no-change runs (it
restarts on demand — see the reaper contract below).

Drive retention: the watchdog's Drive tier has **no retention today**. Every
changed cycle uploads a full DB copy — measured ~11–13 uploads/day since
2026-10-17 (113 objects), ≈28.5 GB/yr at the current DB size — and nothing
prunes them; the tier's quota has not been priced. The retention decision
is the operator's, recorded here rather than made by this kit; the in-house
precedent is the reboot pipeline's 60-day auto-trash rule for its
snapshots. Implementing a prune for `ladybug-*.db` objects is follow-up F2.
Note the tension before acting: the unpruned Drive depth is currently the
backstop for the local keep-3 eviction window, so naive keep-N parity with
the local staging would destroy the corruption backstop.

## Idle reaper (spec — the live body is a multi-step agent procedure around the script; summarized here, not vendored)

Run `idle-reaper.sh` every 15 minutes. Routine outcomes (SKIP, REAPED) never
report — the log is the record. The body reports to chat in exactly one case:
the reaper itself is broken (the script exits non-zero, or writes no fresh
log line). The script itself enforces the whole contract (all five conditions,
clean shutdown only via `neurostrata-mcp shutdown`, never a kill): see
`bin/idle-reaper.sh` header and `runbooks/IDLE-REAPER.md`. Rollback is
disabling this cron.

## Export (spec — the live body is a multi-step agent procedure around the CLI; summarized here, not vendored)

Weekly `export-graph` with default flags. Deliberate decision: active memories
only — `--include-archived` is NOT passed; archived/tombstoned rows are covered
by the watchdog's DB file-copy tier instead. The export is read-only and never
touches daemon lifecycle; it skips if the daemon isn't answering (the watchdog
owns restarts). The body's steps, in order: status check (skip + report if
the daemon is down), export, **verify the new file** — it must exist, be
non-empty, and parse as JSON with a non-empty `nodes` array (a failed check
deletes the bad file and reports) — then prune to the newest 4 exports. That
verification step and the keep-4 rule exist only as these agent instructions;
no script implements them.

Phase-lock warning: the export's 168h anchor fires 4m24s after a watchdog
run (168h = 84 × 2h, same timezone, DST-stable), and on a no-change watchdog
cycle the daemon is deliberately left down — which would make the export
skip and lose the week. Today the export succeeds only because checkpoint
noise (measured lesson 5 in the synthesis page) makes nearly every watchdog
run take the changed path and restart the daemon first. Improvement #5
(logical-content change detection) must therefore be paired with an export
change — body or schedule; landing it alone arms weekly export skips
(follow-up F4).
