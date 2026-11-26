# WATCHDOG-DELTAS.md — `ops/bin/watchdog-backup.sh` vs the live script

Canonical watchdog source: `~/workspace/neurostrata/bin/watchdog-backup.sh`
(live script, on-demand model, Oct 28 patch).

- Live sha256: `bb0754cc8c29a5e42599c6a93ff89cee72ceaadc07aa3467517e79729bf0cf86`
  (332 lines, verified 2026-11-04 at build start, re-verified unchanged at build end)
- Delta D build sha256: `f3cdd2bc533a986bee94d8718e3a096633282d394e33c26887fa99787ce03894`
  (333 lines, after fix round 2, landed in PR #95 as commit `6f93208e`).
  The prior three-delta build was
  `1598bffb1d3bed8d12b7bfcdcb343634254e261e52b5386f213476d72aaec9ad`
  (331 lines).
- Delta E sha256: `5199425a830b79bd3715df1cfd87904227e9a13fbf5823d073eb404257f09453`
  (339 lines, landed in PR #163 as commit `f9dcd636`).
- Current sha256 after Delta F: `f6ee0938d9268a4f931f73100d2ac8adbb3542d0c8494b2c6eaa91a7771ec164`
  (438 lines, issue #21 phase 1).
- Delta count: six (A through F).
- `bash -n ops/bin/watchdog-backup.sh`: clean.

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

## Delta E: stop failure exits 1 instead of exiting 0 (PR #163, commit `f9dcd636`)

Defect: the previous step 3 line was `stop_daemon || exit 0`. A daemon that
would not stop made the run exit 0 and skip the backup, so a wedged
daemon looked like a healthy run forever. The only trace was a missing
"done" line in the log.

Fix: step 3 is now an `if ! stop_daemon` block. On failure it logs
`ERROR: daemon would not stop` with a note that the backup was skipped
and the daemon left running, then exits 1. A three-line comment above the
block explains why.

The header's exit-condition sentence gained a matching clause, so the
header and the code agree that a daemon that would not stop is a
failure.

Why exit 1: copying a live DB would produce the torn backup that the
quiesce step exists to prevent. Skipping the backup is still correct,
but the run must fail so the scheduler can alert.

Evidence:

- Audit: `git log --oneline -- ops/bin/watchdog-backup.sh` lists exactly
  two commits, `6f93208e` (PR #95, baseline for Delta A through D) and
  `f9dcd636` (PR #163, Delta E).
- `git show f9dcd636 -- ops/bin/watchdog-backup.sh` shows two hunks: the
  header exit-condition comment (two lines replaced by three) and the
  step 3 block (two lines replaced by seven). The file went from 333
  lines to 339 lines and from sha256 `f3cdd2bc...` to `5199425a...`.
- Regression test: case (g) in `ops/tests/test_watchdog_ops.sh` (wedged
  daemon on the changed-DB path) asserts a non-zero exit, the "would not
  stop" log line, and no staged backup. It was added in the same commit.

Divergence from the deployed script: `docs/operations.md` records that
the deployed adaptation logs the error and exits 0 on a stop failure.
This repo cannot verify the live host. Until the deploy step in
`ops/README.md` runs, treat the deployed watchdog as the older behavior
and run `ops/bin/deploy-watchdog.sh --check` on the host to find out.

## Delta F: crash evidence capture and pre-restart log preservation (issue #21, phase 1)

Defect: the NeuroStrata daemon died unexpectedly three times on
2026-10-18 and twice overnight before that, with no crash trace. The
daemon log was truncated by the restart command (`> daemon.log`), so each
death destroyed its own evidence. The old `rotate_daemon_log()` in this
file was never called, so nothing preserved the log either.

Change, all in `ops/bin/watchdog-backup.sh`:

- New state files under `~/workspace/neurostrata/`. `.daemon-seen-up`
  holds the epoch of the last healthy observation. `.daemon-down-accounted`
  holds `<epoch> <reason>` for the last down state that was accounted for.
- `daemon_died_unexpectedly()` decides when a down daemon is a death. It is
  one when `.daemon-seen-up` exists (the watchdog saw it up and has not
  stopped it since), or when `.last-daemon-use` is newer than the last
  accounted stop. With no history at all it records a `bootstrap` baseline
  and returns false, so a first run or a fresh deploy never invents a crash.
- `stop_daemon` now records `intentional` after a successful stop, and the
  healthy path records `.daemon-seen-up`. An idle stop by this script is
  therefore never a death.
- `capture_death_diagnostics()` runs only from the daemon-down branch, and
  only when `daemon_died_unexpectedly` is true. It writes
  `logs/crash-<UTC>.log` with mode 600 holding the UTC time, the last 100
  lines of `daemon.log`, OOM hints from `dmesg` (falling back to a note when
  `dmesg` is unreadable), `free -m`, `df -h`, `ulimit -a`, and
  `neurostrata-mcp --version`. Every probe is best effort and cannot fail
  the run. It then calls `rotate_daemon_log` and records `captured`, so the
  same death is never captured twice.
- `rotate_daemon_log()` is rewritten and now called. It moves `daemon.log`
  to `daemon.log.<UTC>.pre-restart` beside it, so a later restart that
  truncates `daemon.log` cannot touch the evidence. The previous version,
  which wrote `logs/daemon-<local time>.log` and kept 5, was never called
  and is gone.
- `prune_newest()` caps both artifact families at 10 files, newest kept.
  Timestamp collisions within one second get a numeric suffix.
- The header gained a "Crash evidence" paragraph.

Known limits, stated plainly:

- A daemon stopped by anything other than this watchdog (a VM restart, a
  manual `shutdown`) counts as a death and produces a bundle. That is a
  cheap false positive and the bundle shows what happened.
- A daemon that starts and dies between two runs without ever being seen
  healthy or touching `.last-daemon-use` is not detected.
- This is phase 1 only. It captures evidence, it does not fix the cause.
  The root cause stays open until a deployed watchdog has collected a few
  bundles (see `docs/limitation-analysis.md` section 1).

Tests: cases (h) through (l) in `ops/tests/test_watchdog_ops.sh`. (h) is
the pre-restart sentinel surviving a truncating restart, (i) is the crash
bundle contents and mode, (j) is the retention cap over 15 deaths, (k) is
an intentional idle stop emitting no bundle, and (l) is the classification
rules (no history, and client use after the last accounted stop). The
suite stays green under PID-namespace isolation.

Divergence from the deployed script: the deployed watchdog has none of this
until it is redeployed. Run `ops/bin/deploy-watchdog.sh --check` on the
host, then `--apply`.

## Notes (not deltas)

- The live line-43 comment ("see 9>&- in start_daemon") still references
  the removed function in the new file. It was left in place because fix
  round 1 authorized Delta C only; a comment fix would be a further hunk.
- The `/opt/hatch/bin/hatch_gws_cli` runtime binary path is unchanged
  from live (allowlisted exception: required for the Drive upload tier;
  no credential value is embedded — only the binary path).

## Resolved blocker (fix round 1) — pre-existing live defect, fixed by Delta C

The blocker described in the original report (idle no-change exit 127,
`stop_daemon` called before definition) is resolved by Delta C above,
applied under the coordinator's ruling. The full suite was re-run after
the move; see the fix-round-1 appendix in `task-1-report.md`. The live
script itself still carries the defect — this file does not, by design.
