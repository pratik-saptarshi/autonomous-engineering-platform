---
name: post-merge-spot-check
version: 1.0.0
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

Pin the post-merge base head SHA first; every result names it. Run all five legs; a leg that cannot run is reported as NOT RUN with the reason, never silently skipped.

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

## Verdict

Report per leg: PASS / FAIL / NOT RUN (reason). Then the attribution statement, which is the point of the exercise:

- **Clean** — all legs pass; nothing to attribute.
- **Defects, pre-existing** — named defects, each with the Leg 5 proof (identical failure on the pre-change build). These become tracked follow-ups; they are not the merged PR's fault and never a reason to revert on their own.
- **Defects, introduced** — named defects present only on the merged tree. This is a merge incident: report immediately with the introducing PR identified; remediation runs under the remediation cycle, and revert is the owner's decision.

## Evidence Standard

The battery that validated this pattern ran against a merged dependency-adoption PR's base at its pinned head and surfaced three defects in an underlying library — write corruption, nondeterministic garbage on extreme inputs, and a read panic — every one proven pre-existing by the pre-change build and byte-identical reproduction on the old version, so the PR was cleared and the defects were filed where they belonged instead of blamed on the merge.

## Stop Conditions

Stop and report: the post-merge head moves during the battery (re-pin and restart); no pre-merge parent is reachable for Leg 5 (attribution becomes impossible — say so plainly rather than guessing); an introduced defect is severe enough that leaving the base as-is risks other work (report at once, do not wait for the full battery).
