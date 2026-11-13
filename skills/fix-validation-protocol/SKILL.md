---
name: fix-validation-protocol
version: 1.0.0
author: pratik-saptarshi
description: >-
  Validate a fix someone else landed against the findings it claims to
  close: map every finding to its diff hunk, prove the tests non-vacuous by
  mutation, re-list review threads at the latest head, verify thread state
  as well as code state, and leave the working tree clean. Use when a
  reviewer, bot, maintainer, or parallel session has pushed a fix and the
  question is whether the findings are actually closed — "tests pass" is
  never sufficient evidence on its own.
---

# Fix Validation Protocol

**Announce at start:** "I'm using the fix-validation-protocol skill to validate this fix."

## When to Use

A fix has landed (new head on the PR, or a merged commit) and someone asserts the findings are addressed. This protocol produces a per-finding verdict: CLOSED, NOT CLOSED, or MIS-STATED (fixed, but the claim about how is wrong). It does not fix anything itself; failures become fix tasks for the remediation lane.

## The Checklist

Work all five steps, in order, at the fix's pinned head. Record evidence as you go — each step names what counts as evidence.

### Step 1 — Map every finding to its diff hunk

For each original finding, identify the exact hunk(s) in the fix diff that address it.

- A finding with no corresponding hunk is NOT CLOSED, however close a nearby change looks.
- A hunk that touches the same file but a different mechanism does not count; the mapping is finding → mechanism → hunk.
- **Evidence:** a table of finding → commit → file:hunk, or the explicit statement "no hunk" per unmapped finding.

### Step 2 — Prove non-vacuity by mutation

For each finding whose fix is guarded by a test, deliberately break what the test guards and confirm the test fails.

- Mutate the behaviour the finding was about (revert the guarded line, typo the fixture value, drop the check) in a throwaway state — never in a commit.
- Run the named test: it must FAIL under the mutation and PASS without it. A test that stays green under mutation is vacuous for this finding; the finding is NOT CLOSED on test evidence.
- Restore the mutation completely before moving on.
- **Evidence:** per finding, the mutation applied, the failing output under mutation, and the passing output after restore.

### Step 3 — Re-list review threads after fetching latest

Fetch the PR's current state and re-list all review threads.

- New threads may have landed after the fix was pushed (reviewers re-run on new heads). A validation against the pre-fix thread list is stale.
- Any new thread is a new finding: it enters Step 1 of a fresh pass, it is not waved through as "post-fix noise".
- **Evidence:** thread census at the fix head — total, resolved, unresolved, and the head SHA the census was taken at.

### Step 4 — Verify thread state, not just code state

For each original thread, check its resolution state on the PR itself.

- Code fixed + thread unresolved = not closed operationally: branch protection counts the thread, not the code. The fix is real but the finding remains open until the thread carries a fix-citing reply and is resolved.
- Reply claims are checked against the code, not trusted: if a reply says "fixed in <sha>", confirm <sha> is an ancestor of the pinned head and its hunk is the Step 1 mapping. A reply whose mechanism description doesn't match the code is MIS-STATED and gets a correction.
- **Evidence:** per thread — state (resolved/unresolved), cited commit, ancestor check result.

### Step 5 — Leave the working tree clean

Revert every checkout, mutation, and experiment used during validation.

- `git status` must be clean in every worktree touched; no mutated file, scratch test, or staged change survives.
- **Evidence:** final `git status` output per worktree.

## Verdict

Report per finding: CLOSED (all applicable steps pass), NOT CLOSED (name the failed step and its evidence), or MIS-STATED (fix real, claim wrong — name the correction needed). The fix as a whole validates only when every finding is CLOSED. "Tests pass" alone never appears as a verdict.

## Stop Conditions

Stop and report: the fix head moves mid-validation (re-pin and restart the census); a mutation cannot be restored cleanly; thread state and code state disagree in a way that needs an owner's ruling (e.g. a reviewer disputes the fix on a resolved thread).
