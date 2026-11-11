# Standalone idle reaper — retirement REVERSED (2026-11-11)

The 2026-11-04 retirement recorded at the bottom of this file is
reversed. The standalone idle reaper is a live production component:
as of the 2026-11-11 ops re-baseline, all three retirement premises
fail verification.

- A live `~/workspace/neurostrata/bin/idle-reaper.sh` exists
  (sha256 `ceb00d0fb6b90b5a51728b3e90515020b93fe2a79e63e1b9adb14c5482a6807e`,
  98 lines) and is the canonical source for `ops/bin/idle-reaper.sh`.
- The `neurostrata-idle-reaper` cron (every 15m) is present in the
  environment goal's cron set and runs it.
- `~/workspace/neurostrata/reaper.log` is actively written, and the
  live watchdog parses its REAPED lines (`reaped_expected`) to tell
  a reaped daemon from a crashed one.

The model moved back: idle-stop was NOT absorbed into the watchdog
after all. The current live watchdog has no idle check — it leaves
a reaped daemon down and restarts an unexpectedly down one.
Idle-stop lives in the standalone reaper, exactly where
`docs/daemon-lifecycle-contract.md` describes it.

Disposition of the companion file: `ops/bin/idle-reaper.sh` is
re-baselined from the current live script — verbatim except the two
standing repo-side fixes (SC2188: bare `9>&-` → `exec 9>&-`; full
`shfmt -i 2` reformat) — and the in-file "RETIRED — DO NOT DEPLOY"
banner is removed. Repo sha256 after re-baseline:
`787fb88cf721c832752953e7b00d126f9d6fea49351c7d5c3b82448d4e1ef126`
(98 lines). This file is retained as the record of the retirement
and its reversal; the filename is historical.

## 2026-11-04 retirement record (superseded — retained for lineage)

### Retired: standalone idle reaper

The standalone idle reaper (`idle-reaper.sh` in this directory) is retired.
Do not deploy it.

#### What retired, precisely

The STANDALONE reaper is retired. Idle-stop BEHAVIOR was absorbed, not
abolished: it lives on inside the canonical watchdog
(`ops/bin/watchdog-backup.sh`, IDLE_SECS idle check), which backs up and
stops an idle daemon under the on-demand model.

#### Retirement evidence (verified 2026-11-04)

- No live `~/workspace/neurostrata/bin/idle-reaper.sh`.
- No idle-reaper cron in `~/workspace/cron.d` or goal crons.
- No `reaper.log` under `~/workspace/neurostrata/`.

#### Provenance note

This file's companion `idle-reaper.sh` is a copy of the kit file
(`reference/neurostrata-ops/bin/idle-reaper.sh`) with a retirement banner
prepended as its first comment block. Byte-identity to the kit file is
explicitly NOT required for this retired file: the banner is an
intentional addition. The kit original is untouched under its vendor
manifest.

#### Fix round 2 note (2026-11-04) — the "banner-only" claim is superseded

The companion file no longer differs from the kit copy by the banner
alone. Fix round 2 (Neo-approved: fix all shell-lint findings in code,
including reformatting) changed it further: the SC2188 bare-redirection
fix (`9>&-` → `exec 9>&-`, which closes FD 9 in the shell itself —
the naive `true 9>&-` would have applied only to the `true` command
and left the shell's FD 9 open) plus a full `shfmt -i 2` reformat.
Any earlier "banner-only" description of this file is superseded by
this note.
