---
name: defect-class-census
version: 1.0.0
author: pratik-saptarshi
description: >-
  Sibling-defect census seeded from one confirmed bug: extract the seed's
  mechanism, enumerate every sibling site sharing that mechanism, and
  classify each candidate CONFIRMED (reproduced with controls), PLAUSIBLE
  (traced by reading, unreproduced), or REFUTED (evidence it cannot occur).
  Only the confirmed set is filed, grouped by theme; plausible candidates
  are parked for an owner-directed reproduction run and refuted ones are
  recorded so the ground is never re-walked. Use when the user asks whether
  more defects like a confirmed one exist, or directs a similar-types /
  sibling-bug hunt from a known defect.
---

# Defect-Class Census

**Announce at start:** "I'm using the defect-class-census skill for this sibling-defect census."

## When to Use

Use after a defect is confirmed, when the question is whether the same mechanism produced siblings — across data types, conversion paths, call sites, or directions of operation in the same component.

Do NOT use for: the seed defect itself (fix or file it through its own lane), a general code review with no seed mechanism, or filing anything beyond the confirmed set this census produces.

## Hard Rules

- **The seed is a mechanism, not a symptom.** The census hunts the mechanism's other manifestations; a sibling that merely looks similar does not belong to the class.
- **Only CONFIRMED candidates are filed.** Plausible candidates are never filed and never mentioned in the confirmed filings. Refuted candidates are never filed.
- **Every candidate gets a classification and an evidence note** — no candidate leaves the census unclassified.
- **Interaction is scoping, never a fix claim.** Where an in-flight fix changes how a candidate would manifest, state that as scoping ("with fix X landed, this surfaces as an error instead of a panic") and never as evidence the candidate is fixed.

## The Census

```
Stage 0: Seed       → mechanism extraction from the confirmed defect
Stage 1: Enumerate  → the full sibling space, listed before any testing
Stage 2: Classify   → per candidate: reproduce, trace, or refute
Stage 3: File       → the confirmed set only, grouped by theme
Stage 4: Park       → plausible candidates recorded, refuted recorded
Stage 5: Report     → counts and evidence per class, bounded next step
```

### Stage 0 — Seed and mechanism

- Start from one defect already confirmed by reproduction. Extract its mechanism in one paragraph: the precise operation that goes wrong (e.g. a width derived from the declared type being reused as the stored value's width), the inputs that trigger it, and the observable failure.
- Name the class after the mechanism, not the seed's location or symptom.
- **Gate:** mechanism statement written; a candidate can be tested for membership against it mechanically.

### Stage 1 — Enumerate the sibling space

- List every site sharing the mechanism before testing any of them: every conversion path, data type, call site, and both directions of an operation (write and read, encode and decode) where the mechanism could operate.
- The enumeration is systematic — derived from the code's own structure (type tables, match arms, trait implementations), not from spot-checking familiar places.
- **Gate:** a written candidate list with, per candidate, the site and why the mechanism could reach it.

### Stage 2 — Classify every candidate

| Class | Evidence bar |
|---|---|
| CONFIRMED | Reproduced against the current code with controls: the failure occurs, a control case behaves correctly, and test output or a minimal repro is recorded. |
| PLAUSIBLE | The pattern is real and the path is traced by reading, but no reproduction has been run (or the repro is inconclusive). |
| REFUTED | Positive evidence it cannot occur: a guard, an invariant, a type constraint, or a failed reproduction under the conditions the mechanism requires. |

- Run reproductions for candidates in severity order where the mechanism's reach differs; a candidate whose reproduction is blocked by environment limits is PLAUSIBLE with the blocker recorded, never silently dropped.
- Where a sibling candidate shares the seed's exact code path, say so — it may extend the seed's filing rather than stand alone.
- **Gate:** every enumerated candidate classified, with its evidence note.

### Stage 3 — File the confirmed set only

- File the CONFIRMED candidates, grouped by theme (one issue per coherent theme, per-candidate detail inside), through the standard upstream-issue-filing practice: each text passes the outgoing-text gate (factcheck, humanizer, conciseness) and carries the publication signature.
- Each filing states the mechanism, the reproduction evidence, and the affected sites. Plausible candidates do not appear in these filings, even as asides.
- **Gate:** filings cover exactly the confirmed set — count in the report matches count filed.

### Stage 4 — Park and record

- **Plausible candidates** are written to the census record with their traces and the reproduction each would need. They earn a scoped reproduction run only on the owner's direction (the bounded next step, Stage 5) — the census does not expand into those runs on its own.
- **Refuted candidates** are written to the census record with their refuting evidence, so a later census or reviewer never re-walks the same ground.
- **Interaction scoping:** for any candidate whose manifestation changes under an in-flight fix, record the scoped behaviour alongside its classification, labelled as scoping.
- **Gate:** census record holds every plausible and refuted candidate with its evidence.

### Stage 5 — Report

- Report counts per class (confirmed / plausible / refuted) with the evidence index, the filings made (links), and the parked list.
- Close with the **bounded next step** as an option for the owner: one scoped reproduction run per plausible candidate or per plausible theme, with its estimated effort — offered, never started without direction.
- **Gate:** report delivered; no reproduction run, filing, or code change beyond the confirmed set has been started.

## Stop Conditions

Stop and ask the owner: the seed's mechanism cannot be stated precisely enough to test membership; a reproduction would require production data or credentials; a confirmed candidate's fix is already in flight and the owner must rule whether the filing duplicates it. Everything else: classify on the evidence, record it, keep going.
