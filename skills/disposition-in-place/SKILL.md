---
name: disposition-in-place
description: Tracker discipline — never delete or silently overwrite a tracked item; flip its status in place and append the old value to history first..
---

> Installed live 2026-11-23 from pattern-mining candidate A9, approved by Pratik in the Pattern mining lane (pattern-mining report, 2026-11-23).

# Disposition In Place + Append-Only History

## Rule

A tracked item is never deleted and never silently overwritten. Its status changes in place, with a dated reason, and any value being replaced is appended to an append-only history first.

## Procedure

1. **Close in place:** a finished, stale, or abandoned item gets a status (Stale / Closed / Done) + a one-line reason citing the evidence and the date — in the same row/record, not a new one.
2. **History before overwrite:** before replacing a value that changes over time (price, status, URL), append the old value, its source, and the timestamp to the history record (a history tab / log section). Then overwrite.
3. **Derive, don't delete:** expired or superseded entries get a derived status from their dates/data where possible, so reports stay reproducible.
4. **Move, don't delete:** an item that leaves one list for another (cart -> wishlist, active -> archive) is moved with its history intact.
5. **Verify by re-read:** after a disposition change, re-read the record and confirm the new status and reason landed. Back up the tracker before a batch of dispositions.
6. **No lost updates:** serialize edits to a record, or use version-checked updates — append the prior value and write only if the record is unchanged since it was read; if it changed, re-read and re-apply the disposition, so a concurrent update is never silently lost.

## Boundary

`knowledge-organization` and `documents` cover organising and editing content. This rule covers the lifecycle discipline of tracked items specifically: status, history, and non-deletion.

## Evidence

- Books tracker, 2026-11-07: Price History seeded with 156 observations, append-before-overwrite on each sweep; expired deals given a derived Live/Expired status; non-free picks moved to wishlist, nothing deleted.
- Job tracker, Nov 2026: rows closed in place on the owner's word — Schwab row 91 (2026-11-09), Everlywell row 94 -> Stale (2026-11-18), SailPoint row 96 -> Stale (2026-11-20), each backed up first and verified by re-read.
