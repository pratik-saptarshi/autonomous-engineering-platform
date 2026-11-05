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
