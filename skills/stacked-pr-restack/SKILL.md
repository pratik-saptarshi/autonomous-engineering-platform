---
name: stacked-pr-restack
version: 1.0.0
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
- Save the three-dot diff (`git diff <old-base>...<reviewed-head>`) and its per-file added/removed line counts. This artifact is the definition of "the reviewed residual" for every later step.
- Confirm the review verdict on record names this head. If the branch has moved since review, stop — there is no reviewed residual to carry.

### Step 2 — Rebuild as a single commit on the new base

- Create the new branch state from the current base head; apply the residual as **one commit** (cherry-pick the range squashed, or apply the saved diff and commit once). Conventional Commits message; note the restack in the body.
- Resolve conflicts only in favour of the residual's intent: where base and residual both changed the same lines, the result must be what the residual meant, on top of the base's new state.
- **Stop condition:** a conflict whose resolution would change behaviour — new logic, a dropped safeguard, a different observable outcome — is not a restack problem. Stop and report; the branch needs a fix round and re-review, not a restack.

### Step 3 — Prove equivalence

Compare the rebuilt branch's three-dot diff against the new base with the saved residual from Step 1:

- Per file: added-line multiset and removed-line multiset must be **byte-identical** to the reviewed residual's.
- Per-file added/removed counts must match the Step 1 record exactly.
- Any difference — one line, one file — fails the proof. Diagnose whether it's a conflict-resolution slip (redo Step 2) or a genuine behaviour change (stop, per Step 2's condition). Never edit the residual to make the proof pass and still call it the reviewed change.

### Step 4 — Push behind a tripwire

- Immediately before pushing, re-read the remote branch head. If it differs from the reviewed head pinned in Step 1, stop — someone else has moved the branch, and overwriting their work is not authorized.
- Push with `--force-with-lease` against the pinned expected head. Never a bare force push.

### Step 5 — Disclose on the PR

Post a signed comment on the PR (through the outgoing-text gate: humanizer, fact-check, conciseness) stating: the old head and old base, the new head and new base, why the restack happened, and the Step 3 equivalence result — residual line counts and the byte-identity claim. The review verdict now applies to the new head *because of this proof*, and the comment is the record of that transfer. If the original PR was mechanically closed when its base branch was deleted, open the replacement PR against the new base and put the disclosure there, linking the closed original.

## Evidence Standard

A completed restack reports: reviewed head → new head, old base → new base, residual size (files, added/removed lines), the byte-identity proof result, and the disclosure comment URL. Precedent: three runs of this procedure, most recently a 337-line reviewed residual rebuilt onto an advanced base and proven byte-identical line-set for line-set, with the review verdict carrying to the new head on the strength of the proof alone.

## Stop Conditions

Stop and report: the reviewed head cannot be pinned; equivalence fails for a behaviour reason; the remote head moved before the push; the owner has not approved the force push.
