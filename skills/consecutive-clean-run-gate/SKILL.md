---
name: consecutive-clean-run-gate
description: Re-point automation at a new source of truth, or expand a pilot's scope, only after N consecutive clean runs..
---

> Installed live 2026-11-23 from pattern-mining candidate A5, approved by Pratik in the Pattern mining lane (pattern-mining report, 2026-11-23).

# Consecutive-Clean-Run Gate

## Postulate
One clean run is an anecdote. Automation may be re-pointed at a new source of truth — or a pilot's scope expanded — only after a stated number (default 2) of consecutive clean runs of the new source, each independently checked.

## Procedure
1. State the gate before the runs start: what counts as clean (the exact comparison, e.g. 0 mismatches on read-back), how many consecutive runs, and what the gate unlocks.
2. Each run is verified independently of the producer (read back the artifact; compare against the independent source). A run verified only by its own producer does not count.
3. A dirty run resets the count to zero and is investigated before the next run; it is never averaged away.
4. When the gate is met, the re-pointing / scope expansion is still presented to the owner as a decision — the gate makes it *eligible*, not automatic.
5. Record gate, runs, and verdicts in the owning lane's record so a later reader can re-derive the count.

## Boundary
`overseer` supervises running work. This gate governs a single promotion decision: when a new source or scope has earned trust.

## Evidence
- AEP fork-fleet census, 2026-11-20 + 11-21: two consecutive clean nightly runs (148 forks, 0 mismatches) met the P4 gate; only then was re-pointing the weekly sweep proposed.
- OpenChamber bridge, 2026-11-20 -> 11-22: scoped re-reviews adopted immediately; implementer use withheld until two further clean pilots (waves 8/9) supplied the runs.
