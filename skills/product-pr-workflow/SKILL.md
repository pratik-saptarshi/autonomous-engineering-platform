---
name: product-pr-workflow
version: 1.0.0
author: pratik-saptarshi
description: >-
  The PR-lifecycle umbrella: sequence an open PR — or a fleet of them — from
  intake and independent review through a fixed verdict taxonomy, the owner's
  ruling, verified remediation, merge gating, post-merge spot checks, and
  closure of any PR the work supersedes. Use whenever a PR needs review,
  findings need disposition, a reviewed branch needs landing, or open PRs
  need one operating picture. This skill names the component skill for each
  stage and the rule governing each hand-off; it does not re-specify their
  internals.
---

# Product PR Workflow

**Announce at start:** "I'm using the product-pr-workflow skill for this PR lifecycle run."

## Role

This is the umbrella. It decides *which stage a PR is in, which component skill owns that stage, and what evidence moves it to the next one*. Component skills do the work of their stage; when a stage's procedure is needed, read that skill — do not improvise a local version of it here.

## Component Map

| Stage | Component skill | Owns |
|---|---|---|
| Intake / batch review | `pr-fleet-review` | Reviewing a batch of open PRs oldest-first, one verdict each |
| Panel review | `overseer`, `roundtable_review` | Adversarial multi-lens panels and judge verdicts on a single PR or plan |
| Remediation | `remediation-cycle` | Verifying reviewer findings, remediating confirmed ones, panel + judge gating the push |
| Fix validation | `fix-validation-protocol` | Proving someone else's landed fix actually closes each finding |
| Restack | `stacked-pr-restack` | Rebuilding a reviewed branch onto a moved base with a byte-identical residual |
| Merge gating | `ci_gate_polling` | Pinning the head SHA and expected check set before trusting CI state |
| Post-merge battery | `post-merge-spot-check` | Gate battery on the merged tree, with pre-existing-vs-introduced attribution |
| Superseded closure | `superseded-pr-closure` | Closing a displaced PR with its verification chain preserved |

Cross-cutting: `humanizer` and `factchk` for the outgoing-text gate (below); `feature-pr-pipeline` when the work itself originates here rather than arriving as an external PR.

## The Lifecycle

### Stage 1 — Intake and review

Pin the PR's head SHA before reading anything. Review the diff against the base at that head. For a single PR needing depth, empanel `overseer` or `roundtable_review`; for a batch, run `pr-fleet-review`. A review produces findings with severity and file:line evidence — nothing enters the taxonomy as an impression.

### Stage 2 — Verdict

Every reviewed PR leaves with exactly one verdict:

- **MERGE-READY** — no surviving findings; CI and thread state verified at the pinned head.
- **MERGE WITH FIXES** — findings verified, fixes scoped; names the conditions.
- **DO NOT MERGE** — a surviving finding blocks landing in any form as filed.
- **FOLLOW-UP FINDINGS** — the PR already merged (or lands regardless); findings become tracked follow-ups, explicitly *no revert*.
- **SUPERSEDED** — another PR carries the same intent further; this one closes unmerged via `superseded-pr-closure`.

### Stage 3 — Owner ruling

The verdict and its evidence go to the owner. The ruling sets scope: which findings are fixed, waived, or filed; whether the PR lands; and in what form. Work proceeds on the ruling as given, even when it widens or narrows the recommendation.

### Stage 4 — Remediation

Findings the ruling sends to fix run under `remediation-cycle`: nothing is a finding until verified, the remediation force works design-notes-first with no push, an independent panel and supreme judge gate the push, and **merge is always a separate decision** — no auto-merge ever rides along with a remediation cycle.

### Stage 5 — Fix validation

When the fix was landed by someone else (another session, a maintainer, a bot), validate it with `fix-validation-protocol` before calling any finding closed. A fix that arrived from the remediation force in Stage 4 is already judge-gated and skips this stage.

### Stage 6 — Restack, when the base moved

If the base branch advanced under a reviewed branch and the branch must be rebuilt, use `stacked-pr-restack`: the rebuilt branch carries exactly the reviewed residual, proven byte-identical, with a disclosure comment on the PR. Never restack by hand-editing the residual into a new shape and calling it the same review.

### Stage 7 — Merge gating

Before any merge: poll CI under `ci_gate_polling` discipline — pinned head SHA, expected check set named in advance. Conversation resolution is required: every review thread resolved, one fix-citing reply per thread. **Never arm auto-merge on a PR with unresolved threads**, and never let one reviewer's approval override another reviewer's open findings. The merge itself needs its own authorization (see Authorization Model).

### Stage 8 — Post-merge spot check

After landing, run `post-merge-spot-check` against the base at its new pinned head: behavioural battery on the merged tree, plus a pre-change build so any defect the battery surfaces is attributed — introduced by this PR or pre-existing — with proof, not by assumption.

### Stage 9 — Superseded closure

Any PR displaced by the landed work closes via `superseded-pr-closure`: signed record comment preserving the verification chain, explicit branch-retention decision, close unmerged, verify `mergedAt` is null.

## Authorization Model

Posting, pushing, and merging are **separate approvals** — a yes to one is never a yes to another. A casual "proceed" authorizes the stage under discussion, not the whole lifecycle. Durable or externally visible state (comments, pushes, merges, branch deletions, label or ruleset changes) needs the owner's explicit approval naming the action. Auto-merge is armed only under the conditions of Stage 7 and only where the owner has approved it for that PR or repo.

## Outgoing-Text Gate

Every text published under this workflow — PR bodies, review comments, closure records, disclosure comments — passes three checks before posting: `humanizer` (no AI writing patterns), `factchk` (every claim verified against the live state it describes), and a conciseness pass. Every published text ends with the author's signature line. A text that fails any check does not post.

## Hard Rules

- Pin the head before reviewing; re-pin after every push — a verdict names the head it was reached at.
- Nothing is a finding until verified at code level.
- A verdict is per-PR and singular; a batch gets one verdict per PR, never a blended one.
- Merge is a separate decision at every stage, including after a judge's all-CLOSED.
- Leave every working tree clean at the end of a stage (`git status`).

## Stop Conditions

Stop and ask the owner: a ruling is needed and none has been given; a stage's evidence contradicts the verdict it was filed under; any irreversible action (merge of a contested PR, branch deletion, history rewrite) not explicitly approved. Everything else: rule on it, record the ruling in the stage's record, keep moving.
