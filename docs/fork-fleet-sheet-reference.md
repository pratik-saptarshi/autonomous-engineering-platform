# Fork fleet sheet — reference

The standing record of Pratik's fork fleet: for every eligible fork
(a fork whose default branch is `develop`), whether its mirror branch
tracks upstream, whether `develop` tracks the mirror, and which bot
last moved what. Implemented by `scripts/fork_fleet_census.py` under
the plan in `docs/plans/2026-11-18-fork-fleet-sheet-plan.html`.

## The sheet

- Title: **Fork fleet — sync status**
- ID: `1YXvmXV7aMmkJ4b0FdiQXamEUbGRMBJLYx8pIfpoQrFM`
- URL: <https://docs.google.com/spreadsheets/d/1YXvmXV7aMmkJ4b0FdiQXamEUbGRMBJLYx8pIfpoQrFM/edit>
- Tabs: `Fleet status` (one row per fork) and `Summary` (counts,
  blocked list, top develop lags, definitions — rewritten each run).
- Columns A:P are machine-owned. Columns Q:R (`Owner notes`,
  `Decision`) are human-owned: the batch never writes, clears, moves,
  or re-sorts them, and rows are never deleted — departed forks are
  marked `retired` in place.

## What the columns mean

| Column | Meaning |
| --- | --- |
| A | Fork repo (`owner/name`) — the row key |
| B | Upstream repo (the fork's parent) |
| C | Upstream default branch — the fork's mirror branch has this name |
| D | Mirror status (vocabulary below) |
| E | Mirror behind: upstream commits the mirror lacks |
| F | Mirror unique: commits unique to the mirror |
| G | Mirror head SHA (short form; full SHA in the census JSON) |
| H | Upstream head SHA |
| I | Develop status (vocabulary below) |
| J | Develop behind mirror: mirror commits not in `develop` (the lag) |
| K | Develop fork-local: `develop` commits the mirror lacks |
| L | Develop head SHA |
| M | Last sync applied at (from fork-sync's JSON run record) |
| N | Last updated by (bot name; attribution rules below) |
| O | Row last verified at — the measuring run's observation-start watermark for the row (see Attribution); advances only when the run actually measured the row, and a failed observation keeps the last verified stamp |
| P | Machine notes (error class for `unknown` rows, retired date) |

Mirror status: `current` (mirror head == upstream head), `behind`
(0 unique, N upstream commits missing), `blocked-diverged` (mirror
carries unique commits; sync never forces), `no-mirror` (no branch
named after the upstream default), `skip` (no parent recorded),
`unknown` (measurement failed — counts are blank, never a fabricated
zero), `retired`.

Develop status: `current` (develop == mirror), `ff-ready` (behind
the mirror by N, 0 fork-local), `fork-local` (develop carries commits
the mirror lacks), `unknown` / `skip` / `retired` as above.

Every figure comes from a live compare taken at census time through
the ghg gateway. Figures are never parsed from the sync text log:
the 2026-11-17/18 incident produced 0 / 1,658 / 258 commits of
develop lag for the same repo from three log-derived sources, where
a direct compare said 258. The two compares also cross-check the
mirror tip; a disagreement marks the row `unknown` instead of
publishing two disagreeing figures.

## Attribution (column N)

A closed vocabulary: a bot `GHG_ACTOR` or `unknown (external
change)`. Mirror movements are attributable to `fork-sync` (the only
automation that moves mirrors) when its JSON run record shows an
APPLIED sync for the repo after the row's previous verification.
Run-record timestamps are ISO 8601 with a UTC offset (fork-sync
writes America/Chicago local time); the census compares them as
datetimes, never as bare strings. The "previous verification" a
sync record is compared against is the row's own measurement
time (column O carries the per-repo observation-start
watermark, `observed_from`, the census recorded), not the run's
completion time — a sync applied while a census is still
measuring later repos postdates that repo's compares and stays
attributable on the next census. The census
also re-reads the run record after measurement finishes, so a
sync recorded while the census was running is not lost to a
stale pre-census copy. The window is bounded on both sides: a
record counts only if it falls after the row's previous
verification and not after the current row's own measurement
time — a sync applied after its repo was measured (while later
repos were still being processed) cannot explain the movement
that observation recorded, and stays unconsumed for the next
census, which measures the synced head. The lower bound is the
previous observation's start, not its completion, for the same
reason one level down: an observation's compares may snapshot a
head at any point inside its window, so a sync that lands after
the snapshot but before that measurement completes postdates
the head the observation recorded, yet is inside the window the
next census attributes against. Column O therefore carries the
start watermark; the current observation's upper bound remains
its own measurement-completion time (`measured_at`). First observations are
bounded more tightly, by the observation start: only a record
predating a newly discovered repo's first observation is copied
into column M (it is already reflected in the measured head),
while a record landing inside that first window is ambiguous —
the compares may have snapshotted the old head before it — and
stays unconsumed until a later census observes its movement.
One exception: when the first observation's compares already
measured the synced head, the movement never appears as a
movement at all, so a later unchanged observation reconciles
the deferred record into column M (column N's attribution is
unchanged — no movement was observed). Reconciliation requires
the record to fall inside the window of the observation that
established the baseline head; a record landing between
observations is never reconciled, because against an
already-established baseline an unchanged head means the sync
explains nothing the sheet tracks. When a mirror sync and a develop movement
are observed in the same census, column M still records the sync,
but column N reads `unknown (external change)`: fork-sync never
touches `develop`, so the bot cannot be credited with the last
change when an external movement is part of what was observed. An axis that fails to measure
keeps its last measured head as the baseline in the sheet (counts
blank, status `unknown`, verification stamp not advanced), so a
sync applied during a failed observation is still attributable
when measurement recovers. A blank head cell is an absent
baseline, not a previous head: when an axis has never been
measured successfully (a newly discovered fork's first census
may have failed outright), its first successful measurement is
initialization — it establishes the baseline and is not
classified as a movement, so a recovered repo is not stamped
`unknown (external change)` for branches that never moved.
First-observation rows are stamped `fork-fleet-census`. Develop
movements are not bot-made today, so a develop change with no
recorded bot action is `unknown (external change)` — a person is
never inferred from commit authorship (author is not actor, and the
pusher is not recoverable from the compare API).

## The nightly run (agent procedure)

The census script never talks to Google; the scheduled agent run is
the writer, through the Sheets connector:

1. Run the census (the script routes every GitHub call through ghg
   under its own actor, `fork-fleet-census`):
   `python3 scripts/fork_fleet_census.py --output <census.json>
   --prev-rows <prev.json> --rows-output <rows.json>
   --sync-record <lane>/files/sync-run-record.json`, where
   `<prev.json>` is the sheet's current A:P range as JSON and
   `<lane>` is `~/workspace/aep-vendored-repo-maintenance`.
2. Exit 2 (budget denial / gateway failure / repo-list failure /
   input or output I/O failure): stop. The sheet stays untouched;
   report the stage. Exit 1 is a partial census (some rows `unknown`
   or partially measured, e.g. an unreadable upstream head) and
   still writes. Exit 0 is complete.
3. Validate before writing: `python3 scripts/fork_fleet_census.py
   --check <census.json>`.
4. Write only what changed: the rows flagged in `<rows.json>` (one
   values batchUpdate over A:P ranges), the column-O verification
   stamp for all rows, and the Summary rewrite. All writes use
   `valueInputOption=RAW`. Never write Q:R.
5. Read the written ranges back and report counts (rows changed /
   new / retired / unknown) to the AEP vendored repo maintenance
   chat. Retain the census JSON and the computed rows under the
   lane's `files/fork-fleet-sheet/` as the run record and the retry
   artefact if a write fails.

## Staleness rule

If the Summary tab's census timestamp is older than 48 hours, the
sheet is stale: re-derive any figure live before a decision uses it.
A missed night loses nothing — the census is read-only and the next
run re-measures everything.

## Scope boundary

The census observes and records; it never syncs, merges, or pushes
(plan decision D6). Mirror syncs belong to `fork-sync`; forward
merges of `develop` belong to the fleet plan's per-action approvals.
