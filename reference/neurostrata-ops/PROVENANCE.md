# Provenance — vendored NeuroStrata memory-ops kit

- **Source:** the operator's live NeuroStrata ops directory (`~/workspace/neurostrata/`)
  on the Muse VM — the working home of the daemon watchdog, idle reaper, runbooks,
  and scheduler bodies that keep the memory daemon alive and backed up.
- **Snapshot date:** 2026-10-25
- **License:** MIT (operator-authored operational material, per the operator's
  standing licensing policy for locally authored work).
- **Why this exists:** the NeuroStrata *source* is vendored at
  `reference/neurostrata/`, but the *operations* that make the memory system
  accumulate and survive — lifecycle scripts, scheduler wiring, runbooks, and the
  measured lessons behind them — lived only on one VM. This kit preserves them so
  another instance can rebuild the same memory operations from the repo alone.
  Synthesis and setup: `docs/neurostrata-memory-ops.md`.

## Files

| Kit path | Live source | Notes |
| --- | --- | --- |
| `bin/watchdog-backup.sh` | `~/workspace/neurostrata/bin/watchdog-backup.sh` | One generalization: a comment naming the daemon's cwd was de-specified (no functional change). |
| `bin/idle-reaper.sh` | `~/workspace/neurostrata/bin/idle-reaper.sh` | Verbatim. |
| `runbooks/OPERATIONS.md` | `~/workspace/neurostrata/OPERATIONS.md` | Verbatim. |
| `runbooks/IDLE-REAPER.md` | `~/workspace/neurostrata/IDLE-REAPER.md` | Verbatim. |
| `model-switch/MODEL-SWITCH-BGESMALLQ-PLAN.md` | `~/workspace/neurostrata/MODEL-SWITCH-BGESMALLQ-PLAN.md` | Verbatim — the executed embedding-model switch procedure. |
| `crons/watchdog-cron-body.md` | `~/workspace/neurostrata/watchdog-cron-body.md` | Verbatim scheduler body. |
| `crons/CRONS.md` | authored for this kit | Schedule specs for all three crons; the reaper/export bodies are reconstructed specs (their live bodies are one-liners around the scripts), marked as such in the file. |
| `PROVENANCE.md` | authored for this kit | This file. |

## Not vendored (deliberately)

- `.drive-database-folder-id` — the Drive backup folder id is deployment-local
  configuration, read by `watchdog-backup.sh` from a dotfile at runtime. It is
  never committed; a fresh instance creates its own folder and dotfile.
- Logs, backups, exports, and the memory store itself — runtime state, preserved
  by the backup tiers the kit describes, not by git.

## Refresh procedure

Re-copy the live files over the kit paths, re-apply the one noted generalization,
regenerate `.github/vendor-neurostrata-ops.sha256` from inside this directory
(`find . -type f | sort | xargs sha256sum`), update the snapshot date, and commit
with the change that motivated the refresh.
