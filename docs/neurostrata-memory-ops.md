# NeuroStrata memory operations

How the live memory system is run, kept alive, backed up, and — most importantly —
made to *accumulate*. The daemon's source is vendored at `reference/neurostrata/`;
the operational kit (scripts, runbooks, scheduler bodies) is vendored at
`reference/neurostrata-ops/` with its own `PROVENANCE.md`. This page is the
synthesis: doctrine, architecture, measured lessons, and the fresh-instance
setup checklist. It exists so another instance can rebuild the same memory
operations from this repo alone.

## Doctrine (standing rule, adopted 2026-10-25)

- **NeuroStrata is the primary memory system.** Learnings, patterns, and project
  memory across every work lane are inscribed into NeuroStrata as the work
  closes. Files (curated summaries, goal workspaces, lane charters) are the
  pointer/summary layer, not the primary store.
- **Inscribe pointers, not dumps:** one tight entry per learning, naming its
  source file, issue, or PR so the detail stays reachable.
- **One namespace per lane** (existing: `dap`, `aep`, `guard`, `global`; create
  a lane's namespace on its first inscription).
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
  (tarball to Drive) that preserves the live ops directory, the store, and the
  file memory layer together, so a lost VM can be rebuilt wholesale.

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

## Fresh-instance setup checklist

1. Install `neurostrata-mcp` 1.9.0; put `~/go/bin` on PATH.
2. Seed the embedder model cache manually (offline); write `embedders.json`
   with BGESmallENV15Q first; export `HF_HUB_OFFLINE=1` in every launch path.
3. Start the daemon (`neurostrata-mcp daemon` under `nohup`); require the
   exact healthy status line and a listening 127.0.0.1:34343.
4. Run `doctor`: namespaces present, counts sane, embedder initializes from
   the local cache with no network attempt.
5. Copy the kit's `bin/` scripts into the live ops directory; create the Drive
   folder and its `.drive-database-folder-id` dotfile (never committed).
6. Install the three crons from `crons/CRONS.md`; verify one watchdog run
   end-to-end: backup file written, sha256 matches, Drive upload logged,
   daemon healthy after.
7. Measure cold start (daemon down → first healthy): must be well inside the
   MCP client's auto-start budget (~30s); 5s is the reference measurement.
8. File one memory through a real client session and recall it — the
   accumulation loop, not the daemon, is the deliverable.
