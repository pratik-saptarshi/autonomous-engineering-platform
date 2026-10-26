# Provenance — vendored NeuroStrata memory-ops kit

- **Source:** the operator's live NeuroStrata ops directory (`~/workspace/neurostrata/`)
  on the Muse VM — the working home of the daemon watchdog, idle reaper, runbooks,
  and scheduler bodies that keep the memory daemon alive and backed up.
- **Snapshot date:** 2026-10-25; amended and re-vendored 2026-10-26
  (panel-review amendments, 2026-10-26).
- **License:** MIT (operator-authored operational material, per the operator's
  standing licensing policy for locally authored work).
- **Why this exists:** the NeuroStrata *source* is vendored at
  `reference/neurostrata/`, but the *operations* that make the memory system
  accumulate and survive — lifecycle scripts, scheduler wiring, runbooks, and the
  measured lessons behind them — lived only on one VM. This kit is a dated
  procedural snapshot and doctrine record of them — how the system is run, what
  was measured, and what is known to be missing — with drift detection as a
  named, owned follow-up (F6). It is not a self-sufficient rebuild kit; the
  gaps are listed in `docs/neurostrata-memory-ops.md` ("Known gaps").
  Synthesis and setup: `docs/neurostrata-memory-ops.md`.
- **Fidelity:** the vendored files are byte-identical to the live sources as
  of 2026-10-26, except the one noted generalization in
  `bin/watchdog-backup.sh`. CI's vendor-integrity check proves only that the
  kit files match `.github/vendor-neurostrata-ops.sha256` — internal
  consistency against the manifest. It cannot detect drift from the live
  source; nothing in CI compares this kit to `~/workspace/neurostrata/`.

## Files

| Kit path | Live source | Notes |
| --- | --- | --- |
| `bin/watchdog-backup.sh` | `~/workspace/neurostrata/bin/watchdog-backup.sh` | One generalization: a comment naming the daemon's cwd was de-specified (no functional change). |
| `bin/idle-reaper.sh` | `~/workspace/neurostrata/bin/idle-reaper.sh` | Verbatim. |
| `runbooks/OPERATIONS.md` | `~/workspace/neurostrata/OPERATIONS.md` | Verbatim. |
| `runbooks/IDLE-REAPER.md` | `~/workspace/neurostrata/IDLE-REAPER.md` | Verbatim. |
| `model-switch/MODEL-SWITCH-BGESMALLQ-PLAN.md` | `~/workspace/neurostrata/MODEL-SWITCH-BGESMALLQ-PLAN.md` | Verbatim — the executed embedding-model switch procedure. |
| `crons/watchdog-cron-body.md` | `~/workspace/neurostrata/watchdog-cron-body.md` | Verbatim scheduler body. |
| `crons/CRONS.md` | authored for this kit | Schedule specs for all three crons; the reaper/export bodies are summarized as specs rather than vendored verbatim (their live bodies are multi-step agent procedures around the scripts), marked as such in the file. |
| `PROVENANCE.md` | authored for this kit | This file. |

## Not vendored (deliberately)

- `.drive-database-folder-id` — the Drive backup folder id is deployment-local
  configuration, read by `watchdog-backup.sh` from a dotfile at runtime. It is
  never committed; a fresh instance creates its own folder and dotfile.
- Logs, backups, exports, and the memory store itself — runtime state, preserved
  by the backup tiers the kit describes, not by git.
- `bin/watch-daemon-death.sh` — the #21 daemon-death canary (a diagnostic
  instrument from the daemon-death investigation, not part of the standing
  lifecycle). Named here so its absence is a decision, not an oversight.
- `bin/sample-daemon-rss.sh` — the daemon RSS sampler used for one-off memory
  measurements; same reasoning.
- The model-cache tarball (`~/workspace/neurostrata/model-cache-backup.tar.gz`,
  ~500 MB) — the restore path for the embedder cache depends on it, but it is
  a binary artifact and far too large for git; a rebuild must obtain or
  regenerate it out-of-band (see "Known gaps" in the synthesis page).
- `model-switch-20261023/repopulate.py` — the one-off script that repopulated
  the fresh BGE store from the pre-switch export (with ID remapping) during
  the 2026-10-23 model switch. The vendored plan describes the procedure;
  without this script its central step is not executable from the repo.

## Publication note (threat model)

This kit publishes the daemon's topology, the jobs' cadences, and the
daemon's downtime pattern to a public repository. That exposure was weighed
in the 2026-10-26 adversarial panel review of this kit and accepted by the
operator; the one datum withheld is the Drive folder id (above).

## Refresh procedure

Re-copy the live files over the kit paths, re-apply the one noted generalization,
regenerate `.github/vendor-neurostrata-ops.sha256` from inside this directory
(`find . -type f | sort | xargs sha256sum`), update the snapshot date, and commit
with the change that motivated the refresh.
