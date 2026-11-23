---
name: exclusion-ledger-first-sweep
description: Any recurring sweep reads a persistent seen/owned ledger before generating picks, and appends only after a confirmed outcome..
---

> Installed live 2026-11-23 from pattern-mining candidate A6, approved by Pratik in the Pattern mining lane (pattern-mining report, 2026-11-23).

# Exclusion-Ledger-First Sweep

## Rule

No recurring sweep generates picks from scratch. It reads its exclusion ledger first, excludes everything the ledger covers, and appends to the ledger only after a confirmed outcome.

## The ledger

- One ledger per sweep domain (seen postings; owned items; seen films), in the sweep's own workspace, in a machine-readable form the sweep actually parses.
- Entry = item identity + disposition + date + source. Identity must be stable across runs (a canonical id or title+edition), because list ordering and aggregator URLs are not stable.

## Procedure

1. First run only: bootstrap the ledger before searching, by inventorying existing seen/owned items across all sources. A sweep with an unbootstrapped empty ledger must not present picks. Every run: read the ledger before searching, and exclude ledger items from results *before* ranking or presenting — never present an owned/seen item and rely on the reader to filter.
2. Append only after a confirmed outcome (applied/closed, purchased/verified in library, watched). A presented-but-undecided item is not appended. Record the outcome atomically with processing where the medium allows, and before acting on an item, reconcile outcomes completed by overlapping or interrupted runs — a completed outcome is never processed twice.
3. Correct false entries in place, with the correction visible — never delete the entry: record the correction and the prior value in the ledger's history (per `disposition-in-place`), update the entry's current disposition, and re-offer the item if still live.
4. Cross-source exclusion: ownership/seen status on *any* platform or source counts, not only the source being swept.
5. If the ledger is missing or unreadable, the sweep stops and reports — it does not run unfiltered.

## Boundary

`recurring-workflows` specifies loop/checkpoint structure generally. This skill specifies the ledger protocol that makes a sweep safe to repeat.

## Evidence

- Job search: austin-job-sweep dedupes via seen_postings.json, standing since 2026-10-17, running through Nov 2026.
- Books: owned.md created 2026-10-24; both deal-sweep crons updated 2026-10-25 to read it first and exclude owned-on-any-platform.
- Movies: seen-films.txt never-re-pick rule; a wrong entry corrected in place 2026-10-24 and the film re-offered.
