---
name: auto-merge-tripwire
version: 1.0.0
author: pratik-saptarshi
description: >-
  Treat auto-merge state as a checked tripwire on every PR touch: read it
  from both REST and GraphQL, flag any arming that coincides with unresolved
  threads, failing checks, or unruled findings, disarm on sight where
  standing protective authority exists, stop the cycle where it does not,
  and leave a fully dispositioned PR's arming in place with the reasoning
  reported. Use on every PR touch — watch runs, cycle phase gates,
  pre-push, and post-push — because an armed auto-merge over unfinished
  business converts any later green moment into an unintended merge.
---

# Auto-Merge Tripwire

**Announce at start:** "I'm using the auto-merge-tripwire skill to check this PR's auto-merge state."

## When to Use

On every touch of a pull request: a watch run, a remediation-cycle phase gate, pre-push, and post-push. Auto-merge state is never assumed from a previous touch — it is read fresh each time.

Hard rules:

- Never arm auto-merge as part of a remediation cycle or a casual go-ahead. Merge is always a separate owner decision.
- Never push to a PR whose auto-merge state you have not just read.

## Procedure

### Step 1 — Check on every touch

- Read the auto-merge state from both the REST API and GraphQL. Either source alone can lag; a disagreement between them is resolved by re-reading, not by trusting one.
- Record: armed or not, armed-by, enabled-at, and merge method (merge, squash, or rebase).

### Step 2 — Test the danger conjunction

An arming is a flag when it coincides with any of:

- an unresolved review thread,
- a failing check,
- a parked or unruled finding,
- an unexecuted judge condition.

Then act by role:

- **Watch or report role:** report the flag once. Never re-report an unchanged flag on later runs.
- **Controller role with standing protective authority:** disarm on sight via the GraphQL `disablePullRequestAutoMerge` mutation, then verify first-hand that `autoMerge` is null. Report the disarm plainly: who had armed it, when, and what was outstanding. Disarming is reversible; the owner can re-arm.

### Step 3 — Cycle Phase 6 variant (no standing disarm authority)

Where the lane has no standing disarm authority, the tripwire is one of the judge's push conditions:

- If armed-with-unresolved is found at the push gate, the cycle stops — without pushing, disarming, or posting — and the disarm decision goes to the owner as a ruling.
- Precedent: PR #148 round 4 — the judge's Condition-1 tripwire found auto-merge armed (SQUASH, 2026-11-14T07:18:31Z) with one unresolved Codex P2. The cycle stopped. The owner ruled "Disarm #148 and authorize round 5"; the disarm was executed and verified null before round 5 proceeded.

### Step 4 — Handle repeated arming

Arming recurs: PR #148 was armed five times; PR #184 was armed five times.

- Check each re-arming against the Step 2 conjunction afresh.
- Count the armings and report the count.
- Never assume a prior disarm stuck.

### Step 5 — Apply the dispositioned exception

If the PR is fully dispositioned — all threads resolved, all checks green, every finding closed, and merge purely the owner's pending call — the unintended-merge rationale no longer fits:

- Leave the arming in place.
- Report it as left armed, with the reasoning.

Precedent: PR #184's fifth arming at head 97393788 (green, 0 unresolved) was left armed and reported, after four disarm-on-sight events on the same PR.

### Step 6 — Record merge execution correctly

An arming that predates a thread resolution but executes only after resolution and green checks — branch protection held — is recorded as observed, not treated as an improper merge.

Precedent: PR #182 was armed ~6 minutes before its P2 resolved; the merge executed 11 seconds after resolution with checks green.

## Evidence Standard

A completed check reports: the PR, the auto-merge state as read from both sources, armed-by, enabled-at, and merge method when armed; the conjunction result (which outstanding items held, if any); the action taken (flag reported, disarm executed and verified null, cycle stopped for a ruling, or arming left in place under the dispositioned exception); and the running arming count for that PR.

## Stop Conditions

Stop and report: the auto-merge state cannot be read from both sources; REST and GraphQL still disagree after re-reading; a disarm does not verify as `autoMerge` null; or, in a Phase 6 lane, armed-with-unresolved is found at the push gate — that stop is the procedure, and the disarm decision belongs to the owner.
