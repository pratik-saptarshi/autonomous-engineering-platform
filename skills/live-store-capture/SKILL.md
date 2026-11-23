---
name: live-store-capture
version: 1.0.0
author: pratik-saptarshi
description: >-
  Capture or inventory a live production store without mutating it:
  guard-hash the store's config before and after, work from a backup
  copy under a scratch HOME when a freshness gate refuses live export,
  run exports and clears against the copy only, reconcile to the
  expected reachable count, and disclose any direct-open side effect
  on the live store. Use when a task needs the contents of a live
  store — an inventory, a migration corpus, a recoverability count —
  and the store must not change underneath the capture.
---

# Live-Store Capture

**Announce at start:** "I'm using the live-store-capture skill to capture this live store under guard."

## When to Use

A task needs the contents of a live production store — an inventory, a
migration corpus, a count by recoverability class — and the store is
still in service, so the capture itself must not change it. The store's
own tooling may refuse to export it directly, may open it in ways that
write to it, and may not tell you either fact plainly. This skill is
the discipline that keeps the capture honest.

Do NOT use for: ordinary reads through a running daemon's API (that is
the store's normal surface, not a capture), backups taken purely for
disaster recovery with no inventory taken from them, or work on a store
that is already offline and disposable.

Evidence: one full execution, 2026-11-22, against a live graph store
whose export surface refused all live exports. The guard held, the
capture reconciled exactly, and the one live-store side effect was a
disclosed checkpoint — see "The corners" for what that run taught.

## The procedure

### 1. Guard-hash before

Before any live-surface work, record the sha256 of the store's guard
config — the config file whose change would mean the store's identity
or settings moved:

```bash
sha256sum "$HOME/.config/<store>/embedders.json"   # example guard file; use the store's own
```

Record the value in the capture record. This is the before-hash; every
later claim of "the live store did not change" rests on it.

### 2. Take a backup copy; never capture from the live store

Use the store tooling's backup surface to produce a copy of the store.
Treat the copy — never the live store — as the capture source.

Know which path the backup actually took before relying on its
properties (corner C2 below): a backup may dispatch through a running
daemon, open the store and checkpoint before copying, copy the raw
files without opening, or be performed by a script that copies raw
files and companions. Establish which one happened and record it.

### 3. Point a scratch HOME at the copy

If the store's config resolves its database path via `$HOME`, build a
scratch HOME whose config points at the copy, copy the guard-relevant
config into it, and run every surface with that HOME in effect:

```bash
SCRATCH=/path/to/scratch
mkdir -p "$SCRATCH/home/.config/<store>"
printf '{"db_path": "%s/backup/store.db"}\n' "$SCRATCH" \
  > "$SCRATCH/home/.config/<store>/config.json"
cp "$HOME/.config/<store>/embedders.json" "$SCRATCH/home/.config/<store>/"
export HOME="$SCRATCH/home"
```

### 4. Exports and clears run against the copy only

If a freshness gate refuses live export, do not clear the live store's
flags and do not export the live store. Clear flags — and run every
export variant — against the copy under the scratch HOME, and only
there. A clear or an export that touches the live store fails the
capture's premise even if its output looks identical.

Note that clearing is not only an explicit clear flag: a successful
export may itself clear freshness flags afterwards. That is safe on
the copy and is one more reason the live store is never exported.

### 5. Guard-hash after; halt on any difference

Repeat the step 1 hash after all live-surface work. **If the
after-hash differs from the before-hash in any character, halt and
report the mismatch.** The capture is not presented as clean, and no
further work proceeds on the strength of it.

### 6. Reconcile to the expected reachable count

On matching hashes, reconcile the capture: the fullest export's total
must equal the sum of the independent per-namespace totals taken on
the copy, and must match the count the capture set out to explain. A
matching hash with an unreconciled count is not a pass — report the
gap. State the count as a **surfaces-reachable count** whenever no
surface exposes a raw row count: surfaces that look independent may
derive their counts from the same filtered rows, so their agreement is
not independent evidence about hidden rows.

### 7. Disclose direct-open side effects

If any step direct-opened the live store — most often the backup step
when the daemon is down, or an export attempt the freshness gate
refused after opening the store — the capture record must say so,
naming the side effect (typically a WAL checkpoint: a file-level WAL
flush that changes no logical content). Distinguish it from the
exports and clears, which touched the copy only. A record that claims
the live store was "never touched" when a step opened it fails this
skill, however clean the capture otherwise is.

Retain a log for every capture step. A step that was executed but not
logged is marked in the record as an unlogged observation, not cited
as evidence. And cite at-capture sizes from the backup's manifest, not
from the copy file's current size: opening the copy mutates the copy.

## The corners

Each of these was hit in the evidence run. Silence on any of them in a
capture plan is a gap.

- **C1 — Freshness flags do not fully determine the export set.** Some
  row classes are always suppressed — mesh-conflicting rows, hidden
  ingest-stage namespaces, generation-superseded scoped rows — with no
  flag escape hatch. Handling: expect the suppression, name the
  suppressed classes in the record, and report counts as
  surfaces-reachable counts (step 6), never as raw totals.
- **C2 — A backup spans several distinct raw-file paths.** Daemon
  dispatch, open-store checkpoint-and-copy, a no-open file copy, and
  script-level raw copies can all answer to "backup", with different
  side effects. Handling: establish which path a given backup took
  before relying on its properties, and record it (step 2).
- **C3 — The installed binary may lack a flag the source defines.** In
  the evidence run the installed binary had no `backup --no-open`,
  although the source at a newer head defined one; the flag was
  code-attested only, never binary-exercised. Handling: verify every
  capability the capture depends on against the installed binary's
  actual behaviour — its help output and a trial run — not against the
  source tree.

## Stop conditions

- Guard-hash mismatch at step 5: halt and report; the capture is not
  clean.
- The only way to export is to clear or export the live store: stop —
  that is the failure this skill exists to prevent.
- A step direct-opened the live store and the record cannot state its
  side effect: the record is incomplete until it does.

## Related

- `neurostrata_memory` — what to do with durable facts once a capture
  surfaces them; this skill governs taking the capture, not keeping
  its lessons.
