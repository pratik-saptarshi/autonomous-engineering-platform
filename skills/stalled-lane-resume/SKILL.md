---
name: stalled-lane-resume
version: 1.0.0
author: pratik-saptarshi
description: >-
  Recover a multi-phase coordinator-driven programme (panel, cycle,
  evaluation) whose coordinator has stalled, without re-running completed
  work and without trusting status claims: inventory the programme's
  on-disk artefacts first-hand, correct the tracking record to the
  verified state, close the stalled coordinator, and dispatch a fresh
  coordinator with a resume packet covering only the missing phases.
  Use when a programme's reported progress and its on-disk state may
  have diverged, or when its coordinator has gone silent.
---

# Stalled Lane Resume

**Announce at start:** "I'm using the stalled-lane-resume skill to recover this stalled programme from its on-disk state."

## When to Use

A multi-phase programme — a review panel, a remediation cycle, an evaluation — is run by a coordinator that dispatches phase subagents and tracks progress. The coordinator has stalled: it has gone silent, stopped advancing phases, or reported a state the work does not support. The goal is to resume from the last verified on-disk state, running only the phases that never ran.

Do NOT use for: a programme still advancing normally (a slow phase is not a stall — confirm it from disk first), or a programme the owner has ordered stopped (a stop is durable; do not resume it under this procedure).

## Procedure

### Step 1 — Detect from disk, not from status

Inventory the programme's on-disk artefacts first-hand before believing any status claim:

- List which phase files exist, with their timestamps, and which expected phase outputs are missing.
- Compare the inventory against the programme's phase plan. The last phase with a complete artefact set on disk is the last completed phase; everything after it is unrun, whatever the record says.
- Treat every tracking record claim — "pending", "waiting", a late phase named as next — as a claim to verify against the inventory, not as a fact.

Precedents: the verification-frameworks panel's record said it was "waiting for the independent judge's verdict"; disk showed it had stalled at Phase 2 (6 dossiers, 5 reviews, 4 of 5 reflections) and the judge phase had never started. PR #120's panel had no file in the panel directory newer than ~7 hours; the coordinator had treated a mid-panel update as completion and never ran Phases 6–15.

### Step 2 — Correct the record

Before any resume is dispatched, write the verified state over the stale tracking claim:

- State the discrepancy explicitly: the record said X; disk shows Y.
- Record the stall itself in the programme ledger: when it was detected, the last verified completed phase, and the cause, if known.
- Do not dispatch a resume against an uncorrected record — the next coordinator will inherit the false state and act on it.

### Step 3 — Close the zombie

Stop the stalled coordinator explicitly and confirm it is stopped. Never leave two coordinators believing they own the programme, and never dispatch a resume before the zombie is closed.

### Step 4 — Resume by packet

Write a resume packet and dispatch a **fresh** coordinator to run **only** the missing phases from the saved state. The packet contains:

- The verified completed phases, each with its artefact paths. Completed phases are inputs, not re-runs.
- The exact remaining phases, in order.
- The standing constraints that governed the original run: pins, scope limits, gating rules, and any owner rulings already made.
- The anti-stall discipline from Step 6, written into the brief.

**Hard rule:** never re-run a completed phase to "be safe". Re-running destroys the audit chain — the original outputs are the record later phases and verdicts cite — and can change verdicts that were already reached on the original evidence.

Precedents: the verification-frameworks panel completed via a `RESUME-PACKET.md` dispatch covering only the missing phases; the judge's verdict was to adopt none of the six frameworks. The PR #120 panel continuation coordinator finished Phases 6–15 reusing all five round-1 files as inputs.

### Step 5 — Fresh-relaunch variant

When no usable intermediate state exists — for example, a coordinator stuck in `pending_init` with no output on disk — do not resume. Close the stalled coordinator per Step 3 and relaunch the whole programme fresh with a new coordinator. There is no saved state to preserve, and pretending otherwise invents one.

Precedent: dap PR #212's first panel coordinator stalled ~2 hours in `pending_init` with no output; it was closed and a fresh panel completed the work.

### Step 6 — Anti-stall discipline

Write these rules into every resume brief, and into the brief of every new coordinator-driven programme:

- Each phase's output lands on disk before the next phase launches. A phase with no artefact is a phase that did not happen.
- A subagent that goes silent is closed and re-dispatched rather than waited on.
- Progress is reported from artefacts, not from agent self-report.

## Evidence Standard

A completed resume reports: the discrepancy found (record claim vs. disk state, with the artefact inventory behind it), the corrected record, confirmation the stalled coordinator was closed, the resume packet path, which phases the fresh coordinator ran and which completed-phase artefacts it consumed as inputs, and the programme's final outcome. No completed phase appears in the report as re-run.

## Stop Conditions

Stop and report: the on-disk inventory cannot establish which phases completed (artefacts ambiguous, missing, or contradictory); the stalled coordinator cannot be confirmed stopped; the owner has ordered the programme stopped or has not approved resuming it; usable intermediate state is claimed but does not exist on disk — in that case report and use the fresh-relaunch variant only with the discrepancy on record.
