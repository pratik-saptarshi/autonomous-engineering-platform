---
name: post-merge-spot-check
version: 1.0.2
author: pratik-saptarshi
description: >-
  Run a gate battery against a merged PR's base at its pinned head:
  behavioural tests on the merged tree, version-over-version byte
  comparison where a dependency changed, an independent oracle for expected
  outputs, a snapshot-open test for state stores, and a pre-change build as
  attribution proof — so any defect surfaced is proven pre-existing or
  introduced, never guessed. Use right after a merge lands, especially a
  dependency bump or a change with a wide blast radius.
---

# Post-Merge Spot Check

**Announce at start:** "I'm using the post-merge-spot-check skill for this post-merge battery."

## When to Use

A PR has merged and the question is whether the merged tree is actually sound — beyond "CI was green on the PR head". The battery runs against the **base branch at its post-merge head**, because that tree (base + merge) is what everyone now builds on, and it is not always identical in behaviour to the PR head that CI saw.

The battery's defining feature is attribution: it is designed so that when it surfaces a defect, the same run proves whether the merged PR introduced it or it was already there.

## The Battery

Pin the post-merge base head SHA first; every result names it. Run all five legs; a leg that cannot run is reported as NOT RUN with the reason, never silently skipped. When the merge was a squash merge, run the tree-fidelity step below first and report its result before any behavioural leg.

### Tree-fidelity step — Squash merges (runs before Leg 1)

A squash merge rewrites the PR into a single new commit, so the PR head is not an ancestor of the merge and "CI was green on the head" says nothing about whether the merged tree is the tree that was reviewed. The merge commit's tree is the evidence. Compare the merge commit's tree against the PR head's tree per-file — hash every file in both trees and diff the two hash lists — and report fidelity first, before Leg 1 runs: every file identical, or each differing file named with its two hashes. A difference is not automatically a defect (a base that moved under the PR can explain one), but it must be enumerable and explained before the behavioural legs' results are read as applying to the reviewed change.

Worked shape: AEP PR #191 merged as squash merge commit `6ad68c2a` from PR head `014fd108`; the post-merge spot-check compared the two trees per-file and found them byte-identical, so the battery's results applied to exactly the reviewed tree.

### Leg 1 — Behavioural tests on the merged tree

Run the project's real test battery against a clean checkout of the merged base head — the affected packages in full, not just the PR's touched files. Record pass/fail counts and any skip that is environment-gated.

### Leg 2 — Version-over-version byte comparison

Where the PR changed a dependency (lockfile bump, vendored snapshot, generated artifact): build or extract the artifact under the old version and the new version and compare bytes. Identical output where identity is expected is strong evidence; any difference must be enumerable and explained by the version change itself, not by the PR's other edits.

### Leg 3 — Independent oracle

For behaviour with an expected output, compute the expectation independently of the code under test — a second implementation, a hand-computed fixture, published reference values — and compare. An oracle derived from the code's own output proves nothing; if no independent oracle exists for a surface, say so rather than dressing the code's output up as one.

### Leg 4 — Snapshot-open test for state stores

If the project persists state (databases, snapshot files, caches with a format), open a pre-existing snapshot — created before the merge — with the merged tree's code, and exercise a read and a write. Format or identity checks that refuse real pre-existing state are merge defects even when every unit test passes, because production state was written by the old code.

### Leg 5 — Pre-change build as attribution proof

Build the same battery (Legs 1–4, as applicable) against the base head *before* the merge — the parent commit — in a separate checkout. Any defect that reproduces identically on the pre-change build is **pre-existing**; any defect present only on the merged tree is **introduced**. This leg runs even when Legs 1–4 are green-so-far, because its value is realized the moment anything else fails.

### Residual re-probing — Parked residuals from the pre-merge record

The pre-merge record (panel, judge, or remediation-cycle record) may park residuals — known defects or capped behaviours deliberately left open at merge time. Legs 1–5 classify defects the battery itself surfaces; they do not settle those parked items. Re-probe every parked residual at the merged tree: re-run its recorded reproduction against a clean checkout of the pinned post-merge head, and land each residual in exactly one of:

- **discharged** — the reproduction now fails on the merged tree; cite the re-probe evidence (the reproduction, the pinned head, and its failing result). The residual is closed, not merely unobserved.
- **still-reproducing** — the reproduction still succeeds on the merged tree; the residual stays parked, restated as observed at the merged tree (its original statement plus the re-probe result), so the next record inherits a current claim, not a stale one.
- **capped-behaving-as-ruled** — the residual was capped by an owner ruling (a bounded ignore, an accepted limit, a governed exception) and the re-probe shows the behaviour staying within that cap. It stays parked under the ruling, neither discharged nor escalated; if the re-probe shows the cap exceeded, it does not land here — it is still-reproducing, restated with the breach named.

A residual that cannot be re-probed (no recorded reproduction, or the reproduction no longer runs) is reported as NOT RE-PROBED with the reason, never silently dropped and never landed in a class without evidence. The verdict below reports the re-probe outcome for every parked residual by name, alongside the per-leg results.

## Verdict

Report per leg: PASS / FAIL / NOT RUN (reason). For a squash merge, report the tree-fidelity result first, before the per-leg results. Report each parked residual's re-probe landing (discharged / still-reproducing / capped-behaving-as-ruled, or NOT RE-PROBED with the reason). Then the attribution statement, which is the point of the exercise:

- **Clean** — all legs pass; nothing to attribute.
- **Defects, pre-existing** — named defects, each with the Leg 5 proof (identical failure on the pre-change build). These become tracked follow-ups; they are not the merged PR's fault and never a reason to revert on their own.
- **Defects, introduced** — named defects present only on the merged tree. This is a merge incident: report immediately with the introducing PR identified; remediation runs under the remediation cycle, and revert is the owner's decision.

## Merge-Condition Honour Audit

A second battery, distinct from the tree gate battery above. That battery asks whether the merged tree is sound; this one asks whether the merge honoured its conditions. After a batch of merges, audit each merged PR against its **recorded panel/judge merge conditions at the merge instant**:

- the exact head merged vs the judged pin;
- gate receipts present;
- review threads resolved;
- PR-body corrections applied;
- auto-merge state at merge time.

Classify each PR:

- **HONORED** — every recorded condition held at the merge instant.
- **PARTIALLY HONORED** — name the specific breach (e.g. substance discharged but judged-head discipline breached).
- **NOT HONORED** — a gating condition did not hold at the merge instant.

Governance breaches — body corrections never applied, receipts counted from a review's own markers — are **report-only** records, not new filings. Only genuinely new defects discovered by the audit get filed.

Precedent: the 2026-11-18 post-merge audit found no bypass at any merge instant — #262 HONORED at its exact pin, #263 HONORED at its merge instant, #206/#219 PARTIALLY HONORED on substance with a judged-head discipline breach, #218's body corrections never applied (report-only) — and filed 11 genuinely new issues, #284–#294.

### Stop-on-merge branch

If a PR merges mid-review at exactly the pinned head, stop the pre-merge verification on the merge. Only on a fresh owner direction, resume the same battery as a post-merge verification, issuing FOLLOW-UP FINDINGS / revert verdicts rather than a pre-merge verdict.

Precedent: PR #164 merged mid-verification at the pinned head — verification stopped, then resumed post-merge on the owner's direction; the third merged-while-reviewing case after #127/#142.

## Evidence Standard

The battery that validated this pattern ran against a merged dependency-adoption PR's base at its pinned head and surfaced three defects in an underlying library — write corruption, nondeterministic garbage on extreme inputs, and a read panic — every one proven pre-existing by the pre-change build and byte-identical reproduction on the old version, so the PR was cleared and the defects were filed where they belonged instead of blamed on the merge.

## Stop Conditions

Stop and report: the post-merge head moves during the battery (re-pin and restart); no pre-merge parent is reachable for Leg 5 (attribution becomes impossible — say so plainly rather than guessing); an introduced defect is severe enough that leaving the base as-is risks other work (report at once, do not wait for the full battery).
