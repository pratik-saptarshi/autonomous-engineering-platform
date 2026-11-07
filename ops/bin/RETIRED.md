# Retired: standalone idle reaper

The standalone idle reaper (`idle-reaper.sh` in this directory) is retired.
Do not deploy it.

## What retired, precisely

The STANDALONE reaper is retired. Idle-stop BEHAVIOR was absorbed, not
abolished: it lives on inside the canonical watchdog
(`ops/bin/watchdog-backup.sh`, IDLE_SECS idle check), which backs up and
stops an idle daemon under the on-demand model.

## Retirement evidence (verified 2026-11-04)

- No live `~/workspace/neurostrata/bin/idle-reaper.sh`.
- No idle-reaper cron in `~/workspace/cron.d` or goal crons.
- No `reaper.log` under `~/workspace/neurostrata/`.

## Provenance note

This file's companion `idle-reaper.sh` is a copy of the kit file
(`reference/neurostrata-ops/bin/idle-reaper.sh`) with a retirement banner
prepended as its first comment block. Byte-identity to the kit file is
explicitly NOT required for this retired file: the banner is an
intentional addition. The kit original is untouched under its vendor
manifest.

## Fix round 2 note (2026-11-04) — the "banner-only" claim is superseded

The companion file no longer differs from the kit copy by the banner
alone. Fix round 2 (Neo-approved: fix all shell-lint findings in code,
including reformatting) changed it further: the SC2188 bare-redirection
fix (`9>&-` → `exec 9>&-`, which closes FD 9 in the shell itself —
the naive `true 9>&-` would have applied only to the `true` command
and left the shell's FD 9 open) plus a full `shfmt -i 2` reformat.
Any earlier "banner-only" description of this file is superseded by
this note.
