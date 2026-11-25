---
name: authorization-currency-check
version: 1.0.1
author: pratik-saptarshi
description: >-
  Before executing any owner-authorized work — a remediation cycle, a push,
  a closure batch, a posting — verify the authorization is still live by
  checking live state first-hand, in order: already done by a parallel lane,
  fixed in flight by the author lane, moot because the target no longer
  exists in the authorized form, or conditional with the condition not
  literally met. Use whenever an authorization arrives or is acted on after
  any delay, handoff, or parallel activity, and before any spend beyond the
  live-state reads themselves.
---

# Authorization Currency Check

**Announce at start:** "I'm using the authorization-currency-check skill to verify this authorization is still live before executing it."

## When to Use

An owner authorization exists on record — run a remediation cycle, push a head, close a batch, post a text — and any time has passed, any handoff has occurred, or any parallel lane (author lane, another session) has been active since it was given. Authorizations decay: the work may already be done, the finding may already be fixed, or the target may no longer exist in the authorized form.

Do NOT use for: work the owner authorized in the same breath and that starts immediately with no parallel lane active (execute it), or as a substitute for the owner's ruling — this check never widens, narrows, or re-interprets an authorization; it only establishes whether the authorized work is still the work that remains.

## Procedure

Run the branches in order. Check against **live state** — API and git, read first-hand — never against the record that carried the authorization. The check runs **before any spend**: no design notes, no panel, no code, beyond the live-state reads themselves.

### Step 1 — Already Done

Has a parallel lane already executed exactly the authorized work?

- Compare the landed state against the authorization exactly: pinned heads and commits, diffs, thread states, closure states.
- If it matches exactly: execute nothing. Close the record gap instead — verify the match first-hand, and if a record correction is owed, post or file only that distinction note.
- Precedents: three superseded PRs found already closed at exactly the pinned heads with comments on record — nothing was posted; a P1-distinction note closed the record gap. A skills push found ALREADY PUSHED — local and remote heads identical via API and `ls-remote`, checked before and after.
- **Stop condition:** the landed state differs from the authorization in any particular — different head, partial execution, extra changes. That is not this branch; stop and report the delta.

### Step 2 — Fixed in Flight (cycle variant)

Was the authorized finding fixed by the author lane mid-flight or before intake?

- Spot-check the landed commit against the finding before opening any cycle phase.
- If fixed: halt the cycle at intake or spot-check. Do not duplicate the fix. Switch the lane to the fix-validation-protocol over the landed commit — map hunk to finding, A/B reproduction, mutation non-vacuity, thread census and state — and record the un-run phases as not run.
- Precedents: AEP #156 round 2 halted at Phase 1 intake when a parallel commit had fixed both items; trio items B and C stopped at spot-check on the same basis; the #167 pad-to and blank-baseline cycles were superseded mid-run; the #182 Go-scope cycle switched to fix-validation after the PR merged.
- **Stop condition:** the landed change touches the finding's area but does not close it. That is not this branch; proceed with the authorized cycle, scoped to what remains.

### Step 3 — Moot

Does the target still exist in the authorized form?

- Check live: PR state (open, merged, closed), finding state, thread state.
- If the target no longer exists in the authorized form — PR merged or closed, finding fixed and thread resolved — report the authorization moot with the live evidence, start no work, and do not re-raise the item.
- Precedent: PR #166 — the authorization arrived after the merge; verified merged at `46cdf7f` with the finding fixed in `744ae4a`; reported moot, no cycle run.
- **Stop condition:** live state is ambiguous or unreachable. Do not declare mootness from a stale record; stop and report what could not be verified.

### Step 4 — Condition Not Literally Met

Was the authorization conditional ("if X, do Y"), and is X literally true?

- State X exactly as given and test it against the live result, word for word. A near miss — a favourable verdict that is not all-green, a pass with exceptions — is not X.
- If X is not literally true: do not treat the condition as satisfied. Put the exact gap to the owner and take a specific ruling on the gap before doing Y.
- Precedent: dap PR #212 — "if panel and judge report all green, merge" was not treated as satisfied when the premises came back THIN; the owner ruled record-then-merge instead.
- **Stop condition:** any gap between the condition as written and the result as found, however small. Only the owner closes a gap in their own condition.

### Step 5 — Flag Scope

Has a flag tripped in this lane, and does the ruling on record actually cover what it tripped on? A ruling's coverage is exactly what it named — no more, no less. Test the flag against the ruling's own phrasing:

- **Named flag on named content.** A ruling that clears a named flag on named content covers that flag on that content only. A NEW flag, or the same flag on different content, in the same lane is **not** covered: same lane does not extend coverage. Stop the lane at the new flag and put it to the owner for a fresh ruling, reporting the flag, the content it tripped on, and that the prior ruling does not cover it.
- **Category-phrased ruling.** A ruling phrased as a category — "git operations in this clone are fine" — covers every operation inside that category. When a later flag names an operation inside the category, test membership (this operation, in this clone, of this kind) and, if it falls inside, treat the ruling as covering it and proceed; do not stop the lane or demand a fresh ruling for what the category plainly covers.
- Precedents (2026-11-22, the pattern proven live twice in one day): a ruling clearing a named flag on named content did not cover a new flag on different content in the same lane — the lane stopped for a fresh ruling; a category-phrased ruling did cover a later flag naming an operation inside its category, and work proceeded.
- **Stop condition:** the flagged content or operation falls outside both the named scope and any category the ruling named — a different clone, a different kind of operation, a flag the ruling never mentioned. That is not covered; stop and take the flag to the owner.

### Step 6 — Authorization Live

Only if no branch above applies: the work has not been done, the finding has not been fixed, the target exists in the authorized form, any condition is literally met, and any flag that tripped is covered by the ruling that cleared it. Execute the authorization as given, and say in the execution report that the currency check ran and found it live.

## Evidence Standard

A completed check reports: the authorization as recorded (what work, at which pinned heads or targets), the live state read first-hand (source: API, git, `ls-remote`; heads, states, timestamps), the branch that applied, and the action taken — nothing executed, validation switched, moot reported, gap put to the owner, or execution proceeded. A stale record found during the check is corrected first-hand before any re-reporting; never re-report a state you have not re-read.

## Stop Conditions

Stop and report: live state cannot be read; the landed state partially matches the authorization; more than one branch appears to apply; or you cannot tell which branch applies. When in doubt which branch applies, stop and report rather than executing.
