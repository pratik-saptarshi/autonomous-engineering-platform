---
name: adoption-evaluation
version: 1.0.0
author: pratik-saptarshi
description: >-
  Evaluate an external project or tool for adoption by read-only first-hand
  inspection at a pinned HEAD, re-measured runtime feasibility on this
  machine, per-target fit analysis disposing of every adoption form, and a
  null-hypothesis test, then deliver a verdict from the fixed taxonomy in a
  standalone HTML report. Use when considering whether to vendor, fork,
  adopt as a tool, adapt, keep fleet-only, or reject an external project or
  tool for a target in this environment.
---

# Adoption Evaluation

**Announce at start:** "I'm using the adoption-evaluation skill to evaluate this candidate for adoption."

## When to Use

An external project, tool, or idea is proposed for use in this environment and the question is whether — and in what form — to adopt it. The evaluation produces one verdict per target, from evidence gathered first-hand, not from the candidate's README, marketing, or reputation.

Do NOT use for: adopting third-party skills into the skill library (that is `adopting-external-skills`, skills-only), or locally authored skills. Do NOT use to implement an adoption already ruled on — landing is Step 9, and only after the owner's ruling.

## Procedure

### Step 1 — Read-only first-hand inspection

Inspect before installing or running anything:

- Clone or inspect the candidate at a pinned HEAD; record the SHA. Read the actual code, not summaries of it.
- Read the actual license texts, including vendored subtrees and indirect dependencies. Grade against the accepted set in Step 5. A disqualified license hiding in a benchmarking-only indirect dependency is a PASS-WITH-CAVEAT with a vendoring exclusion, not a silent pass.
- Check health and provenance via API: bus factor, release cadence, governance, maintenance activity.
- Install nothing in this step.

**Stop condition:** the HEAD cannot be pinned, or a license text that governs distributed code cannot be obtained. Report the gap; do not grade from a license name alone.

### Step 2 — Runtime feasibility, re-measured here

Measure this machine first-hand — device nodes, container runtime, GPU, memory, disk — and test the candidate's hard requirements against the measurement. A candidate that cannot run here is decided on that fact, not on its README's claims. Record the measured values, not just the conclusion.

### Step 3 — Fit analysis, per target, every form disposed

Analyse each candidate target separately: a candidate can be REJECT for one target and FLEET-ONLY for another, and the verdicts are stated independently. For each target, dispose of every adoption form explicitly, with a reason for each — none left unconsidered:

- VENDOR — copy the code into the target tree.
- FORK — maintain a fork under the fleet model.
- ADOPT-AS-TOOL — run the pinned artefact as a tool, without vendoring.
- ADAPT — take the idea or design, reimplemented or integrated selectively.
- FLEET-ONLY — keep on the fork fleet only, with no target integration.
- REFERENCE-ONLY — keep nothing but recorded borrowings (Step 6).

### Step 4 — Null-hypothesis test

State what happens if nothing is adopted, or the current tool is kept. The evaluation must beat that baseline on evidence. If it does not, the verdict is not an adoption verdict, however good the candidate looks in isolation.

### Step 5 — Verdict from the fixed taxonomy

Issue exactly one verdict per target:

- ADOPT
- ADOPT-AS-TOOL (pilot first)
- ADAPT
- FLEET-ONLY
- REJECT

Grade the license separately: PASS / PASS-WITH-CAVEAT / FAIL, against the accepted set — MIT, Apache-2.0, CC0. A FAIL blocks any form that distributes or integrates the code; a PASS-WITH-CAVEAT names the exclusion that makes it pass.

### Step 6 — Reference-only borrowings

Record ideas worth keeping even on a REJECT — a design, a mechanism, a check — explicitly, each in one line with why it is worth keeping. A REJECT with no borrowings considered is incomplete.

### Step 7 — Revisit triggers

List numbered triggers (R1…Rn), each an observable precondition that would change the verdict — not a date or a sentiment. Name which triggers are load-bearing: the ones gating the others, whose firing reopens the evaluation first.

### Step 8 — Deliverable

Deliver a standalone HTML report, verdict first, then the evidence: pinned HEAD, inspection findings, license grade, runtime measurements, per-target fit table, null-hypothesis result, borrowings, and revisit triggers.

### Step 9 — Landing, ADOPT-AS-TOOL only, after the owner's ruling

No landing work starts before the owner rules on the report. On an ADOPT-AS-TOOL ruling, package as follows:

- Pin the artefact; verify its hash or attestation through two independent channels.
- Ship a hardening launcher with telemetry, sharing, remote access, and auto-update disabled.
- Add thin wrapper skills over the tool; keep the tool itself unmodified.
- Provide an idempotent installer with per-artefact SHA256 verification, exercised four ways before delivery: fresh install, re-run, `--check`, and tamper-abort.
- The package stops at the push line for the owner's decision. Do not push on the strength of the adoption ruling alone.

**Governance constraint (hard rule):** nothing may be adopted in a form that routes around this environment's gates — the Verified Remediation Cycle, review panels, or the skill-ingestion gate. A form that bypasses a gate is rejected regardless of its other merits.

## Evidence Standard

A completed evaluation reports: pinned HEAD, license grade with the texts read (including indirect dependencies), measured runtime facts for this machine, a per-target verdict with every adoption form disposed, the null-hypothesis result, reference-only borrowings, and numbered revisit triggers with the load-bearing ones named. Precedent: nine in-window evaluations run on this one skeleton — Plannotator (ADOPT-AS-TOOL, pilot), Nuclei (FLEET-ONLY, add-as-tool as the next step), StreamFusion (REJECT), Switchyard (FLEET-ONLY), Memorilla (REJECT for both targets), omo-slim and its patch kit (REJECT, both), Substrate (FLEET-ONLY), A2UI (REJECT) alongside the Modern Web Guidance pilot — plus the isolation adoption (survey, then pilot, then simultaneous adoption) and the AI-software-factory idea intake (dossier, panel seats, judge verdict per item).

## Stop Conditions

Stop and report: the HEAD cannot be pinned; a governing license text is unavailable; runtime feasibility cannot be measured first-hand; the owner has not ruled and landing work is being requested; or the only viable adoption form would route around a gate.
