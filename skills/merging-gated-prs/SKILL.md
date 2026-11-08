---
name: merging-gated-prs
description: Use when the owner gives a conditional merge instruction for a pull request — "merge if clean and green", "merge when checks pass and nothing is outstanding" — or when a standing conditional covers a named class of PRs and a merge decision falls due under it
---

# Merging Gated PRs

## Overview

The owner's conditional instruction is the only merge authorization that
exists. Your job is to establish, from a census of the exact head, whether
the condition's terms are met — never to widen them. Read the instruction
narrowly, per PR, on the exact head SHA. If a term is not established, it
is not met.

## When to Use

- The owner says "merge PR N if …", with any condition attached
- A standing conditional covers a class of PRs and one is ready for a decision

**When NOT to use:** an unconditional per-PR merge instruction (just merge
and verify), or a PR nobody has authorized merging under any condition.

## The Census

All GitHub calls go through the gateway (`~/go/bin/ghg`, `GHG_ACTOR` set;
pre-flight with `ghg check`, everything else `ghg run --`). Collect, on
the PR's current head:

1. **State:** `pr view N --json state,mergeable,mergeStateStatus,headRefOid`.
   Cross-check `headRefOid` against the branch ref
   (`api repos/<owner>/<repo>/git/ref/heads/<branch>`) — the PR field can
   lag a fresh push by minutes. If they differ, the census is on the wrong
   tree: wait, re-fetch, restart the census.
2. **Checks:** conclusions for the latest run of every check on that exact
   SHA (`api repos/<owner>/<repo>/commits/<sha>/check-runs`).
3. **Threads:** the FULL review-thread list (GraphQL `reviewThreads`,
   paged until `totalCount` is exhausted). A truncated listing is not a
   census — a tail-cut view has hidden a blocking thread in this fleet.
4. **Reviews and comments:** every review with its `commit` SHA, and the
   issue comments. Codex on this fleet posts its verdict as an issue
   comment carrying a `codex-review-state` receipt. Parse the receipt:
   its `commit_sha` and `has_any_findings`.
5. **Codex state** — classify exactly one:
   - `CLEAN-ON-HEAD`: receipt `commit_sha` equals the head and
     `has_any_findings` is false.
   - `FINDINGS-ON-HEAD`: receipt on the head with findings true, or open
     threads from a review of the head.
   - `PENDING`: no receipt binds the head (a verdict exists only for a
     superseded head, or none exists at all). Pending is a state to
     report, never a pass to absorb.
6. **Fix verification:** for every resolved thread whose reply claims a
   fix ("Fixed in …"), verify the fix is in the head's tree — read the
   flagged file at the head (`api .../contents/<path>?ref=<head>`) and
   confirm the flagged content is gone or corrected. A resolved mark is
   a UI state, not evidence; a "fix" commit that touched a different file
   leaves the finding outstanding.
7. **Freshness:** findings trail review completion by minutes. If a
   review or receipt landed within the last few minutes, dwell at least
   5 minutes and re-run the census before deciding.

## Decide

Owner shorthand maps to census predicates:

| Term | Predicate on the exact head |
|---|---|
| clean | state OPEN, mergeable MERGEABLE, mergeStateStatus CLEAN |
| green | every required check concluded success on the head SHA |
| no review comments | zero unresolved threads AND zero outstanding findings (including findings whose "fix" failed step 6) |

Two gates are **unconditional** — they hold under every instruction,
whatever shorthand the owner used: zero unresolved threads, and zero
outstanding findings, on the exact head. An instruction that names
only some terms ("merge if green") does not waive them, and a clean
current-head Codex receipt does not establish that conversations from
an earlier review are resolved. The repository's own rule requires
conversation resolution before merge; certify it in the census rather
than relying on branch protection to enforce it.

Merge only when every predicate in the owner's condition holds, the
unconditional gates hold, **and** Codex state is `CLEAN-ON-HEAD` — or
the owner's instruction explicitly covers merging without a
current-head Codex verdict. A clean receipt on the head supports
merging; it is not a "review comment" against the PR. A receipt bound
to a superseded head is neutral evidence: it neither blocks nor
clears.

If Codex state is `PENDING` and the instruction does not cover it: do
not merge. Report the census and the pending state, and ask. Silence
from Codex is recorded as pending, never as earned.

## Merge

1. Pre-flight: `ghg check -- pr merge N --repo <owner>/<repo> --squash
   --match-head-commit <censused-sha>`.
   Exit 75 means stop and report the stage reached — never retry around
   the gate, never set GHG_BYPASS. (The check is a budget pre-flight;
   the head binding takes effect in step 2.)
2. `ghg run -- pr merge N --repo <owner>/<repo> --squash
   --match-head-commit <censused-sha>`. The flag binds the merge to the
   censused head: if the head has moved since the census, the merge is
   refused. A refusal on head mismatch voids the census — restart it
   from Census step 1 on the new head. Never drop the flag and retry.
   The flag binds the tree, not the review state: a thread opened on
   the same head after the census is stopped by the dwell rule and by
   conversation-resolution protection, not by this flag.
3. Verify from the API, not the command output: `pr view` shows
   state MERGED, the merge commit SHA, and a `headRefOid` still equal
   to the censused SHA.
4. Never bypass branch protection. A merge instruction never implies
   branch deletion; `--delete-branch` needs its own authorization.

## If Not Merging

When a predicate fails on a real blocker — outstanding findings, failing
checks, conflicts, a fix that failed verification — do not merge and do
not improvise a fix loop. Spawn an analyst agent loaded with the
superpowers skills (analysis/implementation side) and the overseer
skills (panel review), briefed with the census facts and the blocker
items. The analyst is read-only for this purpose: it does not merge,
push, or resolve threads. Report its analysis to the owner together
with the census.

If this run itself fixes a finding (under separate authorization),
reply on that thread with "Fixed in <sha>" and re-verify the fix in the
tree before resolving the thread.

## Report

State: the head SHA censused, check conclusions, thread counts
(total / unresolved), Codex state with the receipt's SHA, the decision
taken under the owner's instruction, and the verified outcome (merge
commit SHA, or the analyst's findings, or the pending question asked).

## Rationalizations

| Excuse | Reality |
|---|---|
| "The Codex comment says no major issues" | The receipt binds a SHA. If it isn't the head, it is not a verdict on this tree. |
| "The thread is resolved, so the finding is closed" | Resolved is a UI state. Verify the head's content (census step 6). |
| "CI is green and it's CLEAN — that's what the owner meant" | The condition is conjunctive. Every predicate, on the exact head, or it is not met. |
| "The owner is waiting / about to fly" | Time pressure does not widen a narrow instruction. |
| "Codex reviewed the previous heads clean" | A no-show on this head is pending, recorded as pending — never as a pass. |
| "The diff since the reviewed head is trivial" | Any tree difference voids a SHA-bound receipt. Renames are not trivial: names are identifiers other files resolve. |
| "Nothing will push to this branch in the next minute" | The census binds a SHA; the merge must bind the same SHA. A benign fix push voids the receipt and the checks just as surely as a hostile one. |
| "The owner only said 'green'" | Conversation resolution is not shorthand-scoped. Unresolved threads and outstanding findings block every merge under this skill, whatever terms the owner named. |
| "There are literally comments on the PR, so the condition fails" | A clean receipt on the head is evidence for merging, not a comment against it. The predicate is unresolved threads and outstanding findings. |

## Red Flags — Stop

- About to merge with a Codex receipt whose SHA you have not compared
  to `headRefOid`
- Thread count taken from a truncated or summary view
- A resolved thread accepted without reading the flagged file at head
- `headRefOid` unchecked against the branch ref after a recent push
- A no-show about to be reported as "Codex clean"
- About to merge without `--match-head-commit` set to the censused SHA
