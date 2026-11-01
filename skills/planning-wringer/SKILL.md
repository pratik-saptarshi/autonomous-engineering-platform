---
name: planning-wringer
description: Use when a plan needs adversarial validation before implementation — when building the wrong thing is expensive, when a plan gates downstream work or unblocks tracked items, or when an issue/beads closure must survive review.
---

# Planning Wringer

## Overview

A plan is an argument; the wringer is its stress test. Five phases — draft, adversarial panel, refine, independent review, execution handoff — turn "looks complete" into "verified against ground truth." It caught a plan-killing overclaim in its first use (a bead closure its own notes forbade).

## When to Use

- The plan closes a tracked item or unblocks dependent work — closure claims need evidence, not optimism.
- The plan encodes "decided" values — someone must check the decisions actually say that.
- The implementer is autonomous (subagent-driven or cron) — no human in the loop to catch drift.
- Stakes are high and the plan is cheap to rework.

When NOT to use: trivial or reversible changes, plans the author will execute inline with full context, or when the spec itself is the open question (wrangle the spec first).

## The Wringer

**Phase 1 — Draft the plan.** REQUIRED: use the writing-plans skill. Extensive, test-first tasks with exact values, per-task verification, plus an explicit Test Plan and Acceptance Criteria section. Self-review per the skill before proceeding.

**Phase 2 — Adversarial panel.** Dispatch 3 parallel persona reviewers against the plan, each instructed to verify the plan's load-bearing claims with tools (read the code, the decision records, the issue notes) — never to trust the plan's assertions. Minimum set:
- **Feasibility Analyst** — backward-reason from the desired outcome; verdict FEASIBLE / FEASIBLE-WITH-CHANGES / INFEASIBLE.
- **Risk Assessor** — rank failure modes by likelihood × impact; flag downstream/autonomous consequences of the plan succeeding.
- **Devil's Advocate** — try to kill the plan. Challenge its core premises, compare against known failure patterns (closing on fixture-only evidence, encoding undecided values as decided, conflating mechanical with substantive readiness).

Synthesize as judge: adjudicate disagreements against ground truth, keep every P1.

**Phase 3 — Refine.** Fold panel findings into the plan as a clean rewrite (paperthin `re0`: rewrite, don't patch). Kill or reshape tasks the panel disproved — do not keep a disproved task with a caveat. Ensure the Test Plan and Acceptance Criteria cover every panel finding.

**Phase 4 — Independent reviewer.** Fresh agent, no prior context, reviews the refined plan on its own merits. It re-verifies the plan's factual claims against reality (code, records, notes) and checks every acceptance criterion is mechanically checkable. Verdict: APPROVED / APPROVED-WITH-CHANGES / REJECTED. Apply the changes.

**Phase 5 — Execution handoff.** Present the final plan: panel verdicts, what changed and why, and any scope ruling the panel produced (e.g., "delivers the work but does not close the item"). End with the execution-mode question (recommend one); do not start implementation until answered.

## Quick Reference

| Phase | Input | Output | Kill signal |
|-------|-------|--------|-------------|
| Draft | writing-plans skill | Extensive plan + test plan + AC | — |
| Panel | Plan + ground truth | Findings w/ severity + evidence | Devil's Advocate verdict |
| Refine | Findings | Clean v0 plan | Disproved task survives |
| Independent review | Refined plan | APPROVED / changes / REJECTED | Factual errors |
| Handoff | Final plan | Execution-mode answer | — |

## Common Mistakes

- **Reviewers trust the plan.** A reviewer that quotes the plan back instead of checking the repo is decoration. Instruct explicitly: verify with tools, cite file:line.
- **Keeping a killed task with a caveat.** If the panel proved a task wrong (misencoded decision, vacuous safety net), delete or reshape it. Caveats don't survive autonomous execution.
- **Mechanical ≠ substantive readiness.** "Closes the gate so X becomes pickable" is a mechanical fact; whether X is actually ready is a separate claim the plan must defend or disclaim.
- **Decided values the decision never decided.** Tiers and classes are not single values. Quote the decision text; if the value isn't there, the plan invents it.
- **Closing against the item's own notes.** Read the issue's notes before planning closure — an unrebutted "keep this gate in progress" forbids it regardless of what the plan delivers.
- **Skipping Phase 4 because the panel was harsh.** The panel argued with the draft; the independent reviewer checks the rewrite. Different job, still needed.
