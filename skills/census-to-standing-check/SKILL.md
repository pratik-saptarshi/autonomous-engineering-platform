---
name: census-to-standing-check
description: Convert a defect class into a machine-checked standing check scoped by the invariant, not the finding's location..
---

> Installed live 2026-11-23 from pattern-mining candidate A1, approved by Pratik in the Pattern mining lane (pattern-mining report, 2026-11-23).

# Census to Standing Check

## Trigger

An external or independent review raises a defect, and the same mechanism could plausibly exist at other sites — or the same class has been raised before.

## Rule

A defect class that receives only site fixes keeps producing findings. A class that receives a census stops recurring in the censused scope.

## Procedure

1. Name the invariant the defect violates, in one sentence. The census scope is drawn by that invariant, not by the finding's location.
   - Entry-level: enumerate every public entry point and its validation order.
   - Decode/record-level: enumerate every field and its independent anchor.
   - Operation-level: enumerate every step prefix and its retry/completability outcome.
2. The census itself is performed — or consumed, if already run — via `defect-class-census`: seed mechanism, mechanical sibling enumeration (grep / AST / registry, never from memory), and CONFIRMED / PLAUSIBLE / REFUTED classification. This skill does not re-run that classification; it consumes the census's output.
3. Fix only the sites the owner has ruled for remediation, as one wave — never fix an unruled site on the census's authority alone. Unruled defective sites stay as named residuals; residuals of the same mechanism are ONE combined entry stating the compound shape.
4. Deliver the census as a machine-checked artifact: an audit test or gate check that re-enumerates the sites. An unclassified new site fails the check. A hand-written census is a draft with an expiry date, never the final deliverable.
5. Counts in any report come from the machine artifact, never from a hand summary.

## Boundary (non-duplication)

`defect-class-census` performs the census itself (seed mechanism, sibling enumeration, CONFIRMED/PLAUSIBLE/REFUTED classification). This skill governs what happens next: invariant-drawn scope for that census and its conversion into a machine-checked standing check. A shape-assumption audit — enumerating the fixture shapes a system quietly assumes (self-inflicted, second-execution, foreign-form) — supplies the audit axes. This skill supplies the conversion discipline: census -> standing check, invariant-drawn scope. Use both together; neither replaces the other.

## Evidence

- AEP, 2026-10-25: Codex-countermeasures census, 39/39 findings reproduced; class-recurrence trigger in feature-pr-pipeline Stage 6.
- replay-core, 2026-11-20: PR #2 + #7 pattern analysis (30 findings) — censused class 3 -> 0 findings; uncensused class kept producing findings + 2 open P1s.
