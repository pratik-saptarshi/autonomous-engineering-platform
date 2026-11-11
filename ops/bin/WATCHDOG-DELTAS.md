# WATCHDOG-DELTAS.md — `ops/bin/watchdog-backup.sh` vs the live script

Canonical watchdog source: `~/workspace/neurostrata/bin/watchdog-backup.sh`
(live script, direct-restart model).

- Live sha256: `6a7d4fb3071483f0b3c9da2ad9029acce6ed69072f3cb3cc8fb643993e73cd12`
  (447 lines, verified 2026-11-11 at re-baseline)
- Repo sha256: `ee38932c4676d6d368db43ae187af5479e7dbabac029cc4daf7b30519e695063`
  (462 lines, after the 2026-11-11 re-baseline below)
- `bash -n ops/bin/watchdog-backup.sh`: clean. `shellcheck` (CI set;
  verified under 0.9.0, 0.10.0, and the CI runner's 0.11.0): clean.
  `shfmt -d -i 2` (pinned v3.10.0, as CI): clean.
  `ops/tests/test_watchdog_ops.sh`: ALL PASS.

## Re-baseline 2026-11-11 — per-delta dispositions

The 2026-11-04 repo build (record retained below) was derived from
the live script of that era (sha256 `bb0754cc…`, 332 lines, on-demand
model). Live has since been rewritten around a different model: no
MCP client exists in this deployment, so the watchdog restarts the
daemon directly and guards the restart with an EXIT trap; it polls
health instead of sleeping a fixed window; it distinguishes an
idle-reaper shutdown from an unexpected one (`reaped_expected`); it
prunes the Drive snapshot folder under the 2026-10-27 owner rule; it
pins `TZ=UTC`; and it orders staging by filename-embedded timestamp
(Overseer A1/A2). The repo copy was therefore stale in both
directions. This re-baseline takes the CURRENT live script as the
base and re-adjudicates every 2026-11-04 delta against it:

- **Delta A (header rewrite to on-demand truth): NOT re-applied —
  superseded.** The on-demand model it documented no longer exists
  in live. The current live header (adaptation notes plus the
  seven-step run description) is the truthful one and is carried
  verbatim.
- **Delta B (dead `start_daemon` removal): NOT re-applied.** The
  precondition is gone: in current live, `start_daemon` is called
  from the EXIT trap, the unexpected-down path, and the post-backup
  restart. Removing it would break the script.
- **Delta C (`stop_daemon` moved above first use): MOOT.** Current
  live has no `stop_daemon` function and no use-before-definition;
  the stop is inline in step 3, so there is nothing to move. One
  behavioral difference is inherited from live unchanged and is
  flagged here, not fixed: the inline stop signals only the first
  `pgrep` match, where the 2026-11-04 baseline's `stop_daemon`
  signalled every match (its comment warned that the binary forks
  and `head -1` can miss the live daemon). Live is canonical; if
  that behavior is wanted back it must land in live first and be
  backported by a future re-baseline.
- **Delta D (shellcheck fixes + shfmt reformat): RE-APPLIED, with
  the SC2012 resolutions changed where live's semantics moved.**
  - `shfmt -w -i 2` (pinned v3.10.0, as CI) over the whole file.
  - `drive_catch_up`'s newest-staged selection and the step-8
    staging prune: find-based and NUL-safe as in fix round 2, but
    ordered by filename (`-printf '%f'`, `sort -z`) — NOT by mtime.
    Live orders these by filename-embedded timestamp on purpose
    (Overseer A2): staged copies are made with `cp -p` and carry
    their source's mtime, so round 2's mtime pipelines would have
    selected and pruned the wrong copies. Verified by direct
    pipeline probes with scrambled mtimes (filename order wins;
    empty staging yields an empty selection and deletes nothing)
    and by behavioral case (g), which also pins the prune's
    watermark protection.
  - The daemon-log rotation in `start_daemon` keeps fix round 2's
    mtime find pipeline: rotation files are created by `mv`, so
    mtime is the true criterion there.
  - New findings since the 2026-11-04 build, fixed in code:
    SC2034 — the unused `line` local in `drive_prune_snapshots`
    is removed. SC2120/SC2119 — `wait_healthy` is now called with
    its explicit 60-second argument at all three call sites (the
    same value as its `${1:-60}` default).
  - SC2317 (9 hits, all inside `on_exit`): false positive,
    suppressed with a scoped directive and an in-file
    justification instead of a restructure. `on_exit` runs only
    via the EXIT trap; its restart block is reachable whenever
    step 3 sets `RESTART_NEEDED=true` before an abrupt exit.
    Shellcheck's reachability pass cannot model trap invocation
    (reproduced on 0.9.0 and 0.10.0; string-compare and
    init-order variants do not clear it). The CI runner's
    shellcheck 0.11.0 raises the companion SC2329 ("function
    never invoked") on the same handler — same root cause — and
    the first CI run of the re-baseline PR caught it; the scoped
    suppression names both codes.
- **Public-tree scrub (new in this re-baseline):** one machine path
  carried in from live is generalized in the repo copy — the
  `start_daemon` core-dump comment's "the daemon's cwd (/home/hatch,
  per core_pattern)" reads "the daemon's working directory (per
  core_pattern)" here. The live file keeps its machine-specific
  wording; the public tree does not carry it. No behavior change.

Also carried in with the new base — live features with no 2026-11-04
counterpart: `drive_prune_snapshots`, `reaped_expected`,
`wait_healthy`, the `TZ=UTC` pin, Drive catch-up in-run retry, and
`BIN` at `~/go/bin/neurostrata-mcp`. Dropped with the old base
(they existed only in the on-demand baseline): `archive_logs`,
`log_memory`, `rotate_daemon_log`, and the `IDLE_SECS` idle check —
idle-stop is the standalone idle-reaper's job again (see
`ops/bin/RETIRED.md`, whose retirement this re-baseline reverses).

The behavioral suite was re-specified for the direct-restart model
in the same re-baseline: the fixture stub now lives at the
watchdog's real `BIN` path (`~/go/bin`), cases (b)/(c) pin the
reaped-vs-unexpected down behavior, (d)/(e) pin restart-after-backup,
and case (g) pins the prune's filename ordering and watermark
protection.

## Notes (not deltas)

- The `/opt/hatch/bin/hatch_gws_cli` runtime binary path is unchanged
  from live (allowlisted exception: required for the Drive upload tier;
  no credential value is embedded — only the binary path).

## 2026-11-04 build record (superseded — retained for lineage)

The 2026-11-04 build recorded live sha256
`bb0754cc8c29a5e42599c6a93ff89cee72ceaadc07aa3467517e79729bf0cf86`
(332 lines) → repo sha256
`f3cdd2bc533a986bee94d8718e3a096633282d394e33c26887fa99787ce03894`
(333 lines, after fix round 2). Its delta sections follow verbatim;
claims in them describe the superseded on-demand baseline, and the
Delta C section's "exactly three logical changes" sentence was
already superseded by its own Delta D section.

## Delta A — "Every run" header block rewritten to on-demand truth

Before (live header): step 1 promised "if the daemon is down, restart it
directly (nohup)"; step 2 said the daemon "is never stopped when there is
nothing to back up" and omitted the exit-1 on Drive catch-up failure; step 3
promised "restart the daemon with HF_HUB_OFFLINE=1"; the exit-condition line
said "Exit 0 unless the backup copy itself failed verification or a
configured Drive upload failed."

After (new header): step 1 states daemon-down is the expected idle state,
change detection still runs, a changed DB is backed up as a quiescent copy,
the daemon stays down, the MCP client restarts it, and this script never
restarts the daemon itself; step 2 notes the daemon-down Drive catch-up
exit-1 and that the idle path stops the daemon by design after the
no-change check; step 3 describes stop-copy-verify-record with the daemon
staying down afterwards; the exit-condition line adds the daemon-down
no-change Drive catch-up failure. The "Two watermarks, two tiers"
paragraph is verbatim from live.

## Delta B — dead `start_daemon` definition removed

Before (live lines 48–56): `start_daemon()` defined (log, daemon-log
rotation, `nohup "$BIN" daemon`, `sleep 12`). It is never called anywhere
in the file (only a comment at live line 43 references it).

After: the definition is removed. No other code changed.

## Delta C — `stop_daemon` definition moved above its first use (fix round 1, coordinator-authorized)

Defect (pre-existing in live, NOT introduced by Delta A/B): the live
script calls `stop_daemon` at live line 252 (idle no-change path) before
its definition at live line 260. Bash executes top-down, so the call
fails with `stop_daemon: command not found` and exit 127.

Evidence:
- Sandbox repro on the UNMODIFIED live script (fixture HOME, stub daemon
  up, last-use epoch, unchanged DB, under `unshare -pf --mount-proc`):
  `daemon idle … — backing up and stopping`, `no DB changes … — skipping
  backup`, then `watchdog-backup.sh: line 252: stop_daemon: command not
  found`, exit 127. Full output in `task-1-report.md`.
- Production log corroboration: the live `watchdog.log` contains 71
  "no DB changes" lines but zero "done (daemon stopped, idle)"
  completions — the idle no-change path never completed in production,
  consistent with it dying at the `stop_daemon` call every time.

Fix: the `stop_daemon` definition (22 lines, body byte-identical to
live — verified by byte comparison before the move) was moved above its
first use, to just before the "# 2. Idle check" section (new line 217);
first call is now at new line 273 (idle no-change), second call at new
line 282 (quiesce step, unchanged position relative to its comment).
No other change: no body edit, no comment added, no reordering of any
other function.

Why the move is safe: a function definition has no side effects until
called, so defining `stop_daemon` earlier cannot change the behavior of
any path that previously reached the definition first (the quiesce path
at new line 282 calls the identical body), and it repairs the one path
that previously called it too early (idle no-change at new line 273).
The final live→ops diff shows exactly three logical changes — the
header-block hunk(s), the `start_daemon` removal hunk, and the
`stop_daemon` move hunk (add before idle-check + remove at old site) —
and no other hunk.

## Delta D — shellcheck fixes + shfmt reformat (fix round 2, Neo-approved)

CI's shell-lint job failed on the PR #95 head (proven from the
attempt-2 job log, not transient): 5 shellcheck findings in
`ops/bin/*.sh` plus shfmt formatting diffs in both files. The CI
commands are unchanged (`shellcheck scripts/*.sh ops/bin/*.sh` and
`shfmt -d -i 2` over the same set). Fix round 2 was Neo-approved with
the scope "fix all findings in code, including reformatting" — which
supersedes the small-diff property: **the diff vs live is no longer
three small hunks.** It is now three small hunks plus the Delta D
rewrites below plus a whole-file `shfmt -i 2` reformat of the
watchdog. The Delta C section's "exactly three logical changes"
sentence is superseded by this section.

SC2012 rewrites (`ls -1t` → NUL-safe `find -printf '%T@ %p\0'` +
`sort -znr` pipeline, GNU coreutils on the runner), keep-counts
unchanged:
- Newest staged DB (old line 74): `newest="$(ls -1t
  "$STAGE"/db-*.db 2>/dev/null | head -1 || true)"` →
  `newest="$(find "$STAGE" -maxdepth 1 -type f -name 'db-*.db'
  -printf '%T@ %p\0' 2>/dev/null | sort -znr | head -z -n 1 |
  cut -z -d ' ' -f 2- | tr -d '\0' || true)"`. Empty staging yields
  an empty string, no failure.
- `prune_staging` (old lines 98–99): both `ls -1t … | tail -n +4 |
  xargs -r rm -f` lines → `find … -printf '%T@ %p\0' | sort -znr |
  tail -z -n +4 | cut -z -d ' ' -f 2- | xargs -0 -r rm -f`
  (keep newest 3 of `db-*.db` and of `logs-*.tar.gz`).
- Log rotation (old line 144): `ls -1t "$LOGS_DIR"/daemon-*.log …
  | tail -n +6 | xargs -r rm -f` → the same `find` pipeline with
  `tail -z -n +6` (keep newest 5).
- `find` exits 0 on no match, unlike `ls` (exit 2) — so the rewritten
  pipelines are safe under `set -euo pipefail` where the old ones
  were not. `-type f` restricts matches to regular files (staged
  backups and logs are files; the old glob would also have matched
  directories, which `rm -f` cannot remove).

Parked-defect outcome (build ledger, fix round 1): the
`prune_staging` empty-staging defect is RESOLVED by this rewrite, not
merely disclosed. Probed end-to-end (fixture HOME, stub daemon,
`unshare -pf --mount-proc`): idle-daemon no-change with EMPTY staging
now reaches `stop_daemon` (TERM delivered, daemon stopped) and exits
0 with "done (daemon stopped, idle)" — the exact path that previously
died at `prune_staging`'s `ls` exit 2 before `stop_daemon`. Direct
pipeline probes confirm: empty inputs exit 0 and delete nothing;
keep-counts verified (5 files → newest 3 survive, spaced filename
survives; 7 logs → newest 5 survive).

Reformat: after the rewrites, `shfmt -w -i 2` was run on
`ops/bin/watchdog-backup.sh` and `ops/bin/idle-reaper.sh` only (the
test file and `scripts/*.sh` were already clean and are untouched).
`shfmt -d -i 2` over `ops/bin/*.sh`, `ops/tests/*.sh`, and
`scripts/*.sh` is now empty, and the behavioral suite
(`ops/tests/test_watchdog_ops.sh`, all cases) passes under PID
namespace isolation after the rewrites + reformat.

The retired reaper's SC2188 fix is NOT part of this file's delta
count — it is recorded in `ops/bin/RETIRED.md` (bare `9>&-` →
`exec 9>&-` plus reformat; the naive `true 9>&-` was rejected
because it would have applied only to the `true` command).

## Notes (not deltas) — 2026-11-04 build

- The live line-43 comment ("see 9>&- in start_daemon") still references
  the removed function in the new file. It was left in place because fix
  round 1 authorized Delta C only; a comment fix would be a further hunk.
- `rotate_daemon_log()` is now uncalled in the new file: its only caller
  was `start_daemon`. It was left in place for the same reason.
- The `/opt/hatch/bin/hatch_gws_cli` runtime binary path is unchanged
  from live (allowlisted exception: required for the Drive upload tier;
  no credential value is embedded — only the binary path).

## Resolved blocker (fix round 1) — pre-existing live defect, fixed by Delta C

The blocker described in the original report (idle no-change exit 127,
`stop_daemon` called before definition) is resolved by Delta C above,
applied under the coordinator's ruling. The full suite was re-run after
the move; see the fix-round-1 appendix in `task-1-report.md`. The live
script itself still carries the defect — this file does not, by design.
