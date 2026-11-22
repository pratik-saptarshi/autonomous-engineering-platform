---
name: superseded-pr-closure
version: 1.0.0
author: pratik-saptarshi
description: >-
  Close a PR that another PR has superseded, without losing its record:
  post a signed comment preserving the verification chain — what was
  reviewed, at which head, what landed instead and where, and why this
  branch must never merge — state the branch-retention decision, then close
  unmerged and verify it. Use when a replacement PR carries the same intent
  further and the original needs a clean, auditable end.
---

# Superseded PR Closure

**Announce at start:** "I'm using the superseded-pr-closure skill to close this superseded PR."

## When to Use

Another PR (the successor) now carries this PR's intent — same change at a newer pin, a re-scoped replacement, a restack that opened as a new PR. This PR will never merge, but its review history is evidence; closing it must preserve that evidence, not bury it.

Closing is an externally visible action: it needs the owner's approval, either for this PR specifically or as part of an approved batch disposition.

## Procedure

### Step 1 — Establish the supersession

Name the successor PR and prove the relationship before writing anything: the successor contains this PR's intent (diff comparison, ancestry, or a pinned-pin comparison showing it is strictly further along). If the successor only *overlaps*, this is not a supersession — stop and report; partial overlap is a ruling for the owner, not a closure.

### Step 2 — Port anything that lives only here

Check for records that exist only on this PR: a finding's disposition thread, a tracking reference, a review verdict the successor's record doesn't carry. Port each to the successor (a comment there, citing this PR) *before* closing. Closing first and porting second loses the thread context.

### Step 3 — Post the record comment

One signed comment on this PR (through the outgoing-text gate: humanizer, fact-check, conciseness) stating:

- What was reviewed here, and at which head SHA the review verdict was reached.
- The verdict, in one line.
- What landed instead: the successor PR, its merge commit or current head, and where the content now lives.
- Why this branch must never merge (e.g. it would downgrade a snapshot, duplicate a landed change, or resurrect a superseded base).
- The branch decision from Step 4, stated explicitly.

### Step 4 — Decide branch retention, in the comment

Default: **retain the branch** as the evidence record of the reviewed head — the comment's claims point at it. Delete the branch only when the owner directs it or repo convention requires it, and say which in the comment. Never delete a branch that is the sole record of a reviewed head without the owner's explicit word.

### Step 5 — Close unmerged and verify

Close the PR without merging. Then verify from the API, not the UI: state is CLOSED and `mergedAt` is null. A closure that merged — or a merge commit attributed to this PR — is a failure of this procedure; report it immediately.

## Report

PR number, successor PR, record comment URL, branch decision taken, verified `mergedAt: null`. Five-plus runs of this pattern have closed displaced PRs across three repos with their verification chains intact and zero accidental merges.
