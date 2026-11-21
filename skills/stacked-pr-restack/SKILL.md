---
name: stacked-pr-restack
version: 1.0.1
author: pratik-saptarshi
description: >-
  Rebuild a reviewed PR branch onto a moved base carrying exactly the
  reviewed residual: capture the three-dot diff first, rebuild as a single
  commit on the new base, prove the new diff byte-identical to the reviewed
  residual, push force-with-lease behind a head tripwire, and disclose the
  restack on the PR. Use when a branch's base has advanced (its parent PR
  merged, the stack shifted) and the branch must be re-based without
  re-reviewing content nobody changed.
---

# Stacked PR Restack

**Announce at start:** "I'm using the stacked-pr-restack skill to rebuild this branch onto its new base."

## When to Use

A PR was reviewed at a known head against a base that has since moved — typically because the PR below it in a stack merged and its branch was deleted, mechanically closing or stranding this one. The goal is a branch whose diff against the new base is *the same change that was reviewed*, no more and no less, so the existing review verdict still applies.

Do NOT use for: a branch whose content itself needs changing (that's a new fix round, then a fresh review), or a rebase the owner hasn't approved — force-pushing a reviewed branch rewrites its head and always needs its own authorization.

## Procedure

### Step 1 — Capture the reviewed residual

Before touching anything, record the reviewed change exactly:

- Pin the reviewed head SHA and the old base.
- Save the three-dot diff to a file (`git diff <old-base>...<reviewed-head> > reviewed.diff`) and its per-file added/removed line counts. This artifact is the definition of "the reviewed residual" for every later step.
- Confirm the review verdict on record names this head. If the branch has moved since review, stop — there is no reviewed residual to carry.

### Step 2 — Rebuild as a single commit on the new base

- Create the new branch state from the current base head; apply the residual as **one commit** (cherry-pick the range squashed, or apply the saved diff and commit once). Conventional Commits message; note the restack in the body.
- Resolve conflicts only in favour of the residual's intent: where base and residual both changed the same lines, the result must be what the residual meant, on top of the base's new state.
- **Stop condition:** a conflict whose resolution would change behaviour — new logic, a dropped safeguard, a different observable outcome — is not a restack problem. Stop and report; the branch needs a fix round and re-review, not a restack.

### Step 3 — Prove equivalence

The proof is an ordered byte comparison of the two three-dot diffs. Nothing weaker transfers the verdict.

- Save the rebuilt branch's three-dot diff the same way as Step 1: `git diff <new-base>...<rebuilt-head> > rebuilt.diff`.
- Byte-compare the two saved diffs: `cmp reviewed.diff rebuilt.diff`. Exit 0 — identical bytes — is the only passing proof, and only this result may be called **byte-identical**.
- Any difference fails the proof and the verdict does **not** transfer. Diagnose whether it's a conflict-resolution slip (redo Step 2) or a genuine behaviour change (stop, per Step 2's condition). Never edit the residual to make the proof pass and still call it the reviewed change.
- One legitimate difference class exists: the two diffs are taken against different bases, so index lines and context that merely reflect the base move can differ on a faithful rebuild. Such a difference passes only when the operator shows — and records in the Step 5 disclosure — that every differing byte is confined to those base-reflecting lines and the added/removed payload is identical **in order**. Any other difference, or no recorded showing, fails the proof.
- Per-file added/removed counts and added/removed line multisets may be computed to localise a `cmp` failure, as a labelled **diagnostic only**. A multiset is order- and position-blind: its match is never the proof, never transfers a verdict, and must never be reported as "byte-identical".

### Step 4 — Push behind a tripwire

- Immediately before pushing, re-read the remote branch head. If it differs from the reviewed head pinned in Step 1, stop — someone else has moved the branch, and overwriting their work is not authorized.
- Push with `--force-with-lease` against the pinned expected head. Never a bare force push.

### Step 5 — Disclose on the PR

Post a signed comment on the PR (through the outgoing-text gate: humanizer, fact-check, conciseness) stating: the old head and old base, the new head and new base, why the restack happened, and the Step 3 equivalence result — the `cmp` byte-comparison outcome on the two saved diffs (plus, where the base-reflection showing was used, that showing; residual line counts may be reported as information, labelled as such, never as the proof). The review verdict now applies to the new head *because of this proof*, and the comment is the record of that transfer. If the original PR was mechanically closed when its base branch was deleted, open the replacement PR against the new base and put the disclosure there, linking the closed original.

### Step 6 — Judged-commit re-pin inside a running cycle

A variant of the same transfer, inside a running remediation cycle: the cycle's base moves mid-cycle — e.g. the author lane merges `develop` into the branch — after a commit has already been judged.

- Carry the judged commit onto the new base by cherry-pick, and prove the carry by **tree-hash equality**: pin the judged commit's tree hash (`git rev-parse <judged-head>^{tree}`) at judging time, and after the cherry-pick show the rebased head's tree hash equals it. A tree hash commits to every file's full ordered content, so — unlike a line-multiset comparison — reordering and context moves change it. (Step 3's `cmp` of patch text is not used here: the base legitimately moves under a cherry-picked patch, so patch bytes can differ on a faithful carry; the judged object is the resulting tree.) A tree that differs is not the judged change, and the verdict does not carry.
- Re-run the combined gate green at the rebased head.
- Name the **actual final head** in the PR body and the gate line. The rebase changes the hash — claiming the judged hash as the pushed head would be false.
- On the strength of the tree-hash equality proof plus the gate re-run, the judge's verdict carries to the rebased head **without re-judging**.
- Precedent: the PR #184 freshness cycle — judged `ccd2e8e2` cherry-picked onto `68b8eecd`, patch byte-identical, combined gate green, pushed as `35a9646e`.

### Fork-base retarget rejection — correct the record

- If GitHub rejects retargeting a PR's base to a fork-only branch (HTTP 422), any earlier disclosure that promised that retarget is now false. Do not let the misstatement stand.
- Post signed **correction** comments on the affected PRs stating that the retarget was rejected, what the bases actually remain, and what happens instead — through the outgoing-text gate, as with any disclosure under Step 5.
- Precedent: ladybug-rust #56/#57 — the bases remained `main`; correction comments were posted on both PRs.

## Evidence Standard

A completed restack reports: reviewed head → new head, old base → new base, residual size (files, added/removed lines), the byte-identity proof result, and the disclosure comment URL. Precedent: three runs of this procedure, most recently a 337-line reviewed residual rebuilt onto an advanced base and proven byte-identical line-set for line-set, with the review verdict carrying to the new head on the strength of the proof alone.

## Stop Conditions

Stop and report: the reviewed head cannot be pinned; equivalence fails for a behaviour reason; the remote head moved before the push; the owner has not approved the force push.
