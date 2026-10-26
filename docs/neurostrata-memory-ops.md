# NeuroStrata memory operations

How the live memory system is run, kept alive, backed up, and — most importantly —
made to *accumulate*. The daemon's source is vendored at `reference/neurostrata/`;
the operational kit (scripts, runbooks, scheduler bodies) is vendored at
`reference/neurostrata-ops/` with its own `PROVENANCE.md`. This page is the
synthesis: doctrine, architecture, measured lessons, and the fresh-instance
setup checklist. This page, with the kit, is a dated procedural snapshot and
doctrine record — how the system is run, what was measured, and what is
known to be missing — with drift detection as a named, owned follow-up (see
Known gaps, F6). Snapshot date 2026-10-25; amendments 2026-10-26. It is not
a self-sufficient rebuild kit: the Known gaps section below names what a
rebuild still needs from outside this repo.

## Doctrine (standing rule, adopted 2026-10-25)

- **NeuroStrata is the primary memory system.** Learnings, patterns, and project
  memory across every work lane are inscribed into NeuroStrata as the work
  closes. Files (curated summaries, goal workspaces, lane charters) are the
  pointer/summary layer, not the primary store.
- **Inscribe pointers, not dumps:** one tight entry per learning, naming its
  source file, issue, or PR so the detail stays reachable.
- **One namespace per lane** (existing as of 2026-10-26: `dap`, `aep`, `guard`,
  `global`, `neurostrata`, `environment`, `jobs`, `life`; create a lane's
  namespace on its first inscription).
- **Retrieval starts from NeuroStrata** when a session picks up a lane.
- **Backfill is staged:** legacy file-only learnings are inventoried first and
  inscribed only from an approved candidate list — never bulk-imported blind.

## Architecture on one page

- One daemon, `neurostrata-mcp` (127.0.0.1:34343), serves every console from an
  embedded LadybugDB store. It runs under `nohup`: the environment has no user
  D-Bus, so systemd user units are staged but inactive. There is deliberately
  **no boot autostart** — after a host reboot the daemon is down until demanded
  or the watchdog's next run.
- The embedder is **BGESmallENV15Q** (384-dim), chosen model first in
  `embedders.json`. It replaced Nomic (768-dim) on 2026-10-23: daemon RSS fell
  ~885 MB → ~145 MB. The model cache is seeded manually and the daemon always
  runs with `HF_HUB_OFFLINE=1`: the HTTP client's TLS stack rejects the egress
  proxy's interception certificate, so any runtime download attempt fails.
- Lifecycle is three scheduled jobs (specs in
  `reference/neurostrata-ops/crons/CRONS.md`):
  - **Watchdog, every 2h** — change detection *before* any stop; consistent DB
    copy via graceful shutdown; sha256-verified local backup plus a Google
    Drive tier; poll-until-healthy restart (max 2 attempts); a daemon the
    reaper cleanly stopped is left down on no-change runs.
  - **Idle reaper, every 15m** — clean shutdown (`neurostrata-mcp shutdown`,
    never a kill) only when ALL hold: watchdog lock free, daemon healthy, zero
    established connections on 34343, uptime ≥ 45 min, no CLI process active.
  - **Export, weekly** — `export-graph` snapshot (active memories only, by
    deliberate decision); read-only, never touches lifecycle.
- An outer layer sits beyond this kit: a twice-weekly whole-environment backup
  (tarball to Drive). Its staging carries the identity/memory file layer, the
  skills, cron-definition mirrors, and the latest memory export JSON only —
  the ops directory and the store are NOT in it. Store recovery therefore
  never runs from the tarball: it runs through the watchdog's Drive tier (a
  staged DB copy), or by recomputing the store from the export JSON.
- The staged systemd user units (in `~/.config/systemd/user/`, not vendored)
  are `neurostrata.service` (the daemon; `Restart=on-failure`; its launch
  path sets no `HF_HUB_OFFLINE=1`, so activating it as-is would run the
  daemon without the offline pin), `neurostrata-backup.service`, and
  `neurostrata-backup.timer` (a competing backup regime — the upstream
  repo's `scripts/backup.sh`, md5-verified, keep-7, on a 00,12 calendar —
  whose target directory does not exist on this VM). They are inert here
  only because this VM has no user D-Bus; on a D-Bus-ful instance they would
  activate. Treat them as staged artifacts, not as part of the lifecycle
  above.

One control sits outside this kit and is NOT vendored: the watch-the-watchers
audit — a mandatory monthly `cron.list` / `cron.view` check that the watchdog
and export jobs still exist and are enabled, with its owning tracked item
kept permanently open. It lives in §1c of the root `~/workspace/OPERATIONS.md`.
Do not confuse that file with this kit's `runbooks/OPERATIONS.md`: two
different documents share the name, and only the root one carries the audit
obligation. A rebuild that follows this kit alone loses that control unless
it also adopts the root runbook's §1c.

## Measured lessons

1. **Accumulation is a practice, not a daemon property.** The store was created
   2026-10-16/17 by a single bulk import (82 task entries) plus 8 hand entries.
   The weekly exports then prove a flat line: **90 memories on 2026-10-17 and
   90 on 2026-10-24**, identical per namespace — across the heaviest work week
   in the environment's history, net accumulation was zero because every lane
   recorded its learnings in files. The daemon being up is not the bottleneck;
   inscription as a closing step is. Hence the doctrine above.
2. **Duty cycle is real, and only safe if clients auto-spawn.** Watchdog (2h)
   plus reaper (45-min idle) settle into ~53 minutes up per cycle — the daemon
   is down more than half the day. That is harmless *only* because MCP stdio
   auto-spawns a detached daemon on demand (cold start measured 5s, well
   inside the ~30s client budget). Auto-spawn was source-verified but, at the
   time of writing, never live-tested per client — verify it for each new
   client before trusting the duty cycle, or a session that starts while the
   daemon sleeps silently loses its inscriptions.
3. **The embedding model is a retrieval dependency, not a detail.** Under
   Nomic, retrievals attempted to write an empty vector and were refused, so
   read counts never rose and the ranking filter had nothing to rank by —
   recall looked empty while the data sat there. The model switch procedure
   (vendored in the kit) is the safe pattern: fresh store in the new width,
   repopulate with ID remapping, and a preservation triple-check *before*
   cutover — export reconciliation count-for-count, doctor counts, and
   baseline recall queries returning the same top hits.
4. **A task namespace is not a recall surface.** In NeuroStrata 1.9.0, tasks
   are not search-indexed: semantic search over the 82-entry task namespace
   returns nothing under either embedding model, and its memories never accrue
   read counts. Do not mistake a large task store for searchable memory.
5. **File-hash change detection fires on checkpoint noise.** A graceful
   shutdown checkpoints the WAL and changes the DB file's sha256 with zero
   logical writes, so the watchdog takes a "changed" backup nearly every cycle.
   Harmless (backups are cheap and verified) but noisy. Candidate fix —
   designed, not implemented: compare a logical-content hash derived from
   `export-graph` instead of the file hash.
6. **Verify health without loading the model.** `neurostrata-mcp status` is
   model-load-free and prints the contract line
   `status: healthy -- one daemon is serving every console`.
   `doctor` gives per-namespace counts and never-read counts — the fastest
   accumulation audit there is.

## Known gaps (as of the 2026-10-26 amendments)

What this snapshot does not carry, stated plainly so no reader mistakes it
for a self-sufficient rebuild kit:

- **No install source.** Nothing in the kit says where `neurostrata-mcp`
  comes from, and the repo's materials point two ways: the deployed daemon
  and these ops docs are 1.9.0, while the vendored source snapshot at
  `reference/neurostrata/` is 1.11.0. Which artifact a fresh instance should
  install is undecided here (see `docs/neurostrata-reference.md` for the
  snapshot-vs-deployed distinction).
- **No model-cache seeding procedure.** The embedder cache is seeded manually
  today; the sequence — which model files, from where, verified how — is not
  written down in the kit. The model-cache tarball the restore path depends
  on is not vendored either (see the kit's `PROVENANCE.md`).
- **No `embedders.json` schema or example.** The live default is BGE-first
  (BGESmallENV15Q first/default), which supersedes the vendored model-switch
  plan's Nomic-first staged state; that plan is a historical procedure, not
  the current configuration.
- **Scheduler identity.** The three jobs in `crons/CRONS.md` are agent-prompt
  jobs for one specific harness's scheduler, not crontab entries; porting
  them to another scheduler means translating the bodies, not copying lines
  into cron.
- **Inscription mechanics absent.** The doctrine's closing step — how a lane
  actually writes a memory (the CLI/MCP surface, namespace and type
  conventions) — is not specified in this kit.
- **Drive tier optionality.** The Drive tier is optional in the script: when
  it is unconfigured the tier is a no-op and local backups still run (and a
  later-configured tier receives catch-up uploads). The checklist below and
  the runbooks have historically presented it as a required step; the
  consistent statement is this one — an optional tier, with local backups as
  the floor.

## Follow-ups (recorded 2026-10-26; none block the kit)

- **F1 — Saved-cron sync for C2.** Sync the saved `neurostrata-watchdog`
  scheduler body to the amended vendored text in `crons/`; until it
  lands, the live false-page spec remains live. An operator step outside
  this snapshot.
- **F2 — Drive retention implementation.** A prune mechanism plus standing
  authorization for `ladybug-*.db` Drive objects, per the policy disclosed
  in `crons/CRONS.md`. P1-grade urgency as a live follow-up.
- **F3 — Retrieval probe.** A synthetic inscription + search round-trip (or
  equivalent recall check) as a standing ops artifact. Checklist step 8 is
  currently the system's only retrieval probe — one-time, manual, and
  unspecified.
- **F4 — Improvement #5 precondition.** The logical-content-hash
  change-detection fix (measured lesson 5) must not land without a paired
  export change (body or schedule) — see the phase-lock note in
  `crons/CRONS.md`. It will also collapse the Drive upload rate and change
  local eviction dynamics, which F2's policy should anticipate.
- **F5 — Standing restore verification.** A periodic automated
  restore-and-doctor check against the newest staged backup — the mechanism
  that closes detection latency for bad backups. Recommended, not gated.
- **F6 — Drift alarm.** Install the VM-side drift-alarm job (hash the live
  ops files, compare against this kit's manifest, report only on mismatch),
  or keep it named here as a required companion with an owner. Until one of
  those holds, no text in this kit may claim drift detection exists.
- **F7 — Classifier and contract residuals.** The downtime classifier's
  blind spot (it counts only watchdog-logged starts; the runbook's own
  manual-restart restore manufactures an invisible start) and the watchdog's
  exit-code symmetry rework — the cron body now documents the actual
  behavior instead (documented in the cron body); neither change is required.
- **F8 — Housekeeping record.** Uninventoried live store clones
  (`phase-b-store-copy/`, `task7-store-copy/`) and a stray manual-start
  daemon log under `logs/` in the live ops directory; this kit never names
  its own repo, and the docs-lint exclusion also exempts the kit's two
  authored files (`crons/CRONS.md`, `PROVENANCE.md`).
- **F9 — Review-gate process change (standing).** Every review verdict on a
  change that vendors or touches executable artifacts carries an explicit
  "layer audited" declaration (fidelity / behavior / both); a fidelity-only
  audit may be cited only as verification of the copy; script-bearing
  changes pass a behavioral gate (empty-state and restore-state execution,
  or a contract audit) before merge.
- **F10 — Custody note.** Both Drive tiers are plaintext under an explicit,
  recorded operator decision, and the reboot README's challenge phrase
  remains an unset placeholder. Recorded so the claim re-scope above does
  not silently imply a protection that does not exist.

## Fresh-instance setup checklist

1. Install `neurostrata-mcp` 1.9.0; put `~/go/bin` on PATH.
2. Seed the embedder model cache manually (offline); write `embedders.json`
   with BGESmallENV15Q first; export `HF_HUB_OFFLINE=1` in every launch path.
3. Start the daemon (`neurostrata-mcp daemon` under `nohup`); require the
   exact healthy status line and a listening 127.0.0.1:34343.
4. Run `doctor`: namespaces present, counts sane, embedder initializes from
   the local cache with no network attempt.
5. Copy the kit's `bin/` scripts into the live ops directory; optionally
   create the Drive folder and its `.drive-database-folder-id` dotfile
   (never committed) — without it the watchdog runs local-only (see Known
   gaps).
6. Install the three crons from `crons/CRONS.md`; verify one watchdog run
   end-to-end: backup file written, sha256 matches, Drive upload logged
   (when the Drive tier is configured), daemon healthy after.
7. Measure cold start (daemon down → first healthy): must be well inside the
   MCP client's auto-start budget (~30s); 5s is the reference measurement.
8. File one memory through a real client session and recall it — the
   accumulation loop, not the daemon, is the deliverable.
