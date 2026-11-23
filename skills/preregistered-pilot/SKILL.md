---
name: preregistered-pilot
version: 1.0.1
author: pratik-saptarshi
description: >-
  Run a tool or capability pilot whose verdict cannot be negotiated after
  the fact: select the subject from a classified census of real work, freeze
  the pre-registration before building, register every trusted boundary
  before relying on it, run in owner-gated stages, and judge strictly
  against the frozen criteria. Use when a pilot's result will feed an
  adoption decision, or when a favoured candidate risks being pre-committed
  before the evidence exists.
---

# Pre-Registered Pilot

**Announce at start:** "I'm using the preregistered-pilot skill to run this pilot under frozen criteria."

## When to Use

A tool, capability, or method is being evaluated and the verdict matters — it will feed an adoption decision, close a line of work, or be cited later as proof. The pilot exists to produce a verdict the evidence earned, not one negotiated once the results are known.

Do NOT use for: exploratory spikes with no decision attached (just run them and report), or work already in flight under another gate — pre-registration only binds if it is written before the run starts.

## Procedure

### Step 1 — Census-first subject selection

Choose the pilot subject from a classified census of real work, never by pre-commitment:

- Build the census first: e.g. the 100 most recent fix commits classified by class × component × catchability, plus an inventory of existing controls already covering the space.
- The favoured candidate enters the census as one row among others, with no privileged status. Selection is a ruling on the census, recorded with its reasoning.
- Precedent: in the Kani pilot's Stage 0, the identity-decision core was treated as one candidate row, not a pre-committed subject; the secrets scanner was selected from the census.

### Step 2 — Pre-registration, frozen before building

Before any building starts, write the pre-registration to the pilot's state directory. It fixes:

- Scope caps: size, harness/task counts, and any other bound that keeps the pilot a pilot.
- The exact success criteria, stated so each can be checked pass/fail without interpretation.
- Kill criteria: conditions under which the pilot stops early.
- The named adversarial test set — mutants, tasks, or cases — that must all be caught or passed.
- The graduation bar, if the pilot feeds an adoption decision.

Criteria are not edited mid-run. A needed change is a new pre-registration, recorded as such, with the run it supersedes named.

**Phase E — the pre-implementation eval phase.** When the pilot's plan is an SDD-style plan with implementation work, the plan's first phase is a named pre-implementation eval phase, Phase E, which precedes implementation. Phase E composes five eval types as one phase: lock-diff, audit-baseline, CI-set-pinning, acceptance, RED-capture.

- **Fixture-fixed pass values.** Each eval's pass value is fixed by fixture in advance, written into the pre-registration before the eval runs. A Phase E entry that is only a heading or a name, with no fixture-fixed pass value, does not count as an eval — a hollow heading fails.
- **Admission rule — mutation proof per eval.** A proposed eval is admitted into Phase E only with its own mutation proof: a demonstration that deliberately breaking what the eval guards makes the eval fail. A proposed eval with no mutation proof is rejected as unproven. (`fix-validation-protocol` prescribes mutation proof for fix tests; the admission rule for Phase-E evals is this skill's.)
- **Evidence-absent completion bar.** If an eval reports its mechanical evidence as "none available" mid-phase, Phase E cannot complete, and implementation does not start on the basis of a completed Phase E. The gap is recorded — which eval, and what evidence was unavailable — not waved through.
- **Precedent disclosure.** The Phase-E evals (Rocinante) precedent: "E1–E3 completed without mechanical evidence; E4 entered a fix round; E5/E6 did not complete; the run's coordinator stalled and was replaced."

### Step 3 — Trusted-boundary register

Before anything relies on the method, enter every seam it cannot prove or cover in a trusted-boundary register:

- Register-before-reliance is a hard rule: an unregistered seam may not carry weight in any result.
- The register ships with the results, so a reader can see exactly what was assumed rather than proven.
- Precedent: the Kani register carried T1 OnceLock tables, T2 input envelope, T3 entropy modelling, and T4 pattern-engine inventory; when Kani proved unable to model the regex crate, the regex extraction seam was carried as a bounded registered item rather than silently assumed away.

### Step 4 — Run in stages, owner-gated

- Run the pilot in stages as pre-registered. Each stage is authorized separately by the owner before it starts.
- No silent scope growth between stages: work outside the frozen scope waits for a new pre-registration.
- Stage results are recorded as observed, including failures, before the next stage is proposed.

### Step 5 — Judge strictly against the frozen criteria

- If a criterion is unmet, the pilot did not succeed — full stop. The record is never relabelled to fit the outcome.
- Phase E completion is judged by the Step 2 Phase-E rules, including the evidence-absent bar: a phase declared complete while an admitted eval's evidence stands recorded as none available is not a pass.
- A split result is ruled by the owner as a partial success or a negative; that ruling, not a reinterpretation of the criteria, is what closes the pilot.
- Precedent: Kani Stage 1 froze the criterion "ALL harnesses pass"; it closed at 9/13, the owner accepted a partial success, and the pilot closed on the delivered split.
- A mutant or test that survives is a result, not an inconvenience to be tuned away. The only exception is one bounded repair cycle per surviving item, and only if it was pre-registered.

### Step 6 — Comparison variant

When the pilot compares guided vs unguided work, the pre-registration additionally fixes:

- The tasks, the scoring dimensions, and the pass threshold.
- Blind scoring: scorers do not know which output is guided.

A missed bar closes the pilot. Precedent: the Modern Web Guidance comparison set a graduation bar of ≥3 of 4 guided wins with no accessibility regressions; guided won 1 of 4, and the pilot closed NEGATIVE with no standing wrapper.

### Step 7 — Close-out and artefact disposal

Dispose of the artefacts per the verdict:

- On a negative: package/wrapper goes to recoverable trash; retain the pilot record, gate artefacts, and evidence.
- On a partial success: publish only what the frozen criteria actually proved, with the record corrected to the narrower claim.
- Post-close corrections are made first-hand and supersede the close-out wording where they conflict. Precedent: the Kani v2 correction established that v1's "9 verified" harnesses were concrete-input batteries, not symbolic proofs — the record was corrected, not defended.

## Evidence Standard

A completed pilot reports: the census and the selection ruling, the frozen pre-registration as written before the run, the trusted-boundary register, per-stage results against each criterion (met / unmet, with counts), the owner's verdict on any split result, and the artefact disposal record. Every claim in the close-out traces to one of these artefacts; a claim with no artefact behind it does not ship.

## Stop Conditions

Stop and report: the subject was pre-committed before the census; a criterion needs editing after the run has started (that is a new pre-registration, not an edit); a result relies on an unregistered trusted boundary; scope has grown between stages without authorization; a surviving mutant or failed test is being tuned away outside a pre-registered repair cycle; a Phase E is declared complete while an admitted eval's mechanical evidence is recorded as none available.
