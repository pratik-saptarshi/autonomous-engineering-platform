# WATCHDOG-DELTAS.md — `ops/bin/watchdog-backup.sh` vs the live script

Canonical watchdog source: `~/workspace/neurostrata/bin/watchdog-backup.sh`
(live script, on-demand model, Oct 28 patch).

- Live sha256: `bb0754cc8c29a5e42599c6a93ff89cee72ceaadc07aa3467517e79729bf0cf86`
  (332 lines, verified 2026-11-04 at build start; re-verified unchanged at build end)
- New sha256: `f3cdd2bc533a986bee94d8718e3a096633282d394e33c26887fa99787ce03894`
  (333 lines, after fix round 2 — Delta D; prior three-delta build was
  `1598bffb1d3bed8d12b7bfcdcb343634254e261e52b5386f213476d72aaec9ad`,
  331 lines)
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

## Notes (not deltas)

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
