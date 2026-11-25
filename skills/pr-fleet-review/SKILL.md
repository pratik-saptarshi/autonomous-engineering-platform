---
name: pr-fleet-review
version: 1.0.1
author: pratik-saptarshi
description: >-
  Batch review of a fleet of open PRs on one repository: pin the inventory
  (head SHA, base, size per PR), run one independent reviewer per PR with
  premise-checking, then an adversarial panel and judge per PR producing
  verdicts in a fixed taxonomy, derive a stack-aware landing sequence, and
  publish through the outgoing-text gate. Merges happen only on the owner's
  separate direction; fixes authors push are re-reviewed finding by finding.
  Use when the user asks to review all open PRs on a repo, a contributor's
  whole PR fleet, or a batch of PRs as one programme.
---

# PR Fleet Review

**Announce at start:** "I'm using the pr-fleet-review skill for this fleet review run."

## When to Use

Use when a set of open PRs on one repository must be reviewed as a programme — every open PR in scope, a contributor's fleet, or a named batch — where verdicts must be comparable across PRs and landing order matters.

Do NOT use for: a single PR (ordinary review suffices), findings on our own PR under active remediation (use `remediation-cycle`), or merge execution alone (merges are a separate owner-directed step this skill prepares but never performs on its own authority).

## Hard Rules

- **Nothing is a finding until verified.** A reviewer's claim enters the record only with evidence from the diff, the code at the pinned head, or a reproduction.
- **Heads are pinned; drift voids verdicts.** Any head movement after pinning means that PR is re-reviewed before its verdict is trusted or published.
- **A red CI is not a finding against the PR until proven otherwise.** A failure claimed to be a pre-existing flake must be proven as such against the base branch — the same failure reproduced or observed on the base — never assumed.
- **Merges are always the owner's separate decision.** No verdict, however clean, arms auto-merge or merges anything.
- **Publication is gated.** Nothing is posted to GitHub until the owner directs publication, and every posted text passes the outgoing-text gate (factcheck, humanizer, conciseness) first.

## The Programme

```text
Stage 0: Pin        → inventory: every in-scope PR, head SHA, base, size
Stage 1: Review     → one independent reviewer per PR, premise-checked
Stage 2: Adjudicate → adversarial panel + judge per PR, fixed taxonomy
Stage 3: Sequence   → stack-awareness: overlaps, containment, landing order
Stage 4: Publish    → gated review publication (owner-directed)
Stage 5: Land       → merges on the owner's separate direction only
Stage 6: Re-review  → finding-by-finding on every author fix push
```

### Stage 0 — Pin the inventory

- Enumerate every open PR in scope from the live repo state: number, title, author, head SHA, base branch, additions/deletions, changed-file count, draft state.
- Record the inventory in the run's records directory before any review starts; it is the baseline every later drift check compares against.
- **Out-of-scope states stay on record.** A PR in the programme's scope that is no longer open still gets an inventory entry with its state: closed by an automated guard (see Guard-closed PRs below), or already merged under a target a later ruling superseded (see Stale-target merges below). Such entries are not reviewed as open PRs and are not dropped as routine closures or routine merges.
- **Gate:** inventory complete and recorded; no in-scope PR missing.

### Stage 1 — Independent review

- One independent reviewer per PR; a reviewer never reviews a PR they authored or fixed. Review oldest-to-newest when the owner so directs, otherwise in inventory order.
- **Premise-checking:** the PR's own claims (body, commit messages, linked issues) are verified against its diff. A refuted claim is cut from the verdict, or carried only at the severity the surviving evidence supports — never repeated at the PR's own valuation.
- Each reviewer returns findings with severity and file:line evidence, plus a draft verdict from the Stage 2 taxonomy.
- **Gate:** every PR has an independent review with evidence-backed findings or an explicit no-findings result.

### Stage 2 — Adversarial panel + judge

- Per PR, run the `roundtable_review` machinery: an adversarial panel argues the findings and the draft verdict; a judge rules per finding (stands / falls / re-scoped) and assigns the PR's verdict from the fixed taxonomy:

| Verdict | Meaning |
| --- | --- |
| MERGE-READY | No surviving findings; nothing blocks a merge decision. |
| MERGE WITH FIXES | Named fixes are required first; each maps to a surviving finding. |
| DO NOT MERGE | A surviving defect or false premise disqualifies the PR as filed. |
| FOLLOW-UP FINDINGS — no revert | For an already-merged PR: findings stand as follow-ups; the merge is not undone. |
| SUPERSEDED | Another PR in the fleet contains or replaces this PR's content; close, never merge. |

- **Gate:** every PR carries a judge-assigned verdict; every surviving finding is mapped to diff evidence.

### Stage 3 — Stack-awareness and landing sequence

- Compare the fleet against itself: which PRs overlap in files, which heads contain other heads, which findings one PR's head already closes in another.
- Where overlap exists, the judge mandates a landing sequence — e.g. a PR whose head also closes another PR's P1 lands first; contained or replaced PRs are ruled SUPERSEDED and become closures, not merges.
- Record the sequence and the evidence for each containment claim (ancestry or tree comparison, not titles or intuition).
- **Gate:** a written landing sequence covering every PR not ruled DO NOT MERGE or SUPERSEDED, and a closure path for every SUPERSEDED PR.

### Stage 4 — Gated publication

- On the owner's direction only, publish each PR's review. Every text passes the outgoing-text gate and carries the publication signature.
- Each review opens with its **merge-status label line**, mapped mechanically from the verdict (e.g. "Merge status: MERGE WITH FIXES"), so the verdict is readable without opening the body.
- Post in COMMENT state by default. CHANGES_REQUESTED or APPROVE follow-ups are posted only where the owner directs them per PR.
- **Gate:** published reviews match the judged verdicts exactly; nothing posted beyond the owner's direction.

### Stage 5 — Landing

- Merges execute only on the owner's separate, per-PR direction. Immediately before each merge, verify the live head still equals the pinned head; a moved head returns that PR to Stage 1.
- Execute in the Stage 3 sequence; verify the merge result and the new base head after each landing before starting the next.
- **Gate:** each merge verified against its pinned head, or the PR is out of the sequence with the reason recorded.

### Stage 6 — Finding-by-finding re-review

- When an author pushes fixes, re-pin the head and re-review **per original finding**: map every finding to the hunk that claims to close it — a nearby change is not a closing change.
- **Mutation proof on load-bearing tests:** for a test cited as a fix's evidence, deliberately break what it guards (e.g. corrupt the fixture value) and confirm the test fails; a test that cannot fail closes nothing.
- Re-list review threads after fetching the latest state — new findings may have landed post-fix — and verify thread state, not just code state.
- Update the PR's verdict per finding (closed / open / re-scoped) and overall; return to Stage 4 for any publication the owner directs.
- **Gate:** every original finding carries a current disposition backed by its closing hunk or a stated reason it remains open.

## Guard-closed PRs, stale-target merges, and mid-programme intake

### Guard-closed PRs and the Dependabot refile

- When an automated guard closes a PR for touching a protected tree — the Dependabot-against-`reference/**` shape — record the closure as a guard closure, with the guard and the protected tree named. The guard's decision is not appealed inside the review: guards of this kind have no opt-out, and the fleet review never weakens, bypasses, or reopens around one.
- Whether an equivalent change is still needed is a **human judgement**, recorded as a ruling by the owner or the PR's maintainer — never inferred from the guard closure itself (a guard closure says the tree was protected, not that the change was unwanted) and never from the reviewer's own assessment alone.
- If the ruling is to proceed, the refile is a new, human-authored change, and its **refile packet** must enumerate exactly three values: the **corrected target tree** (where the change may land instead of the protected tree), the **dependency change** (the package and version movement the closed PR carried), and the **authorising ruling** (who ruled, and where it is recorded). A packet missing any of the three does not proceed.
- The refile executes as a normal change against the corrected target tree — through `feature-pr-pipeline` where that workflow applies — not by reopening the closed Dependabot PR. The fleet record links the guard-closed PR, the packet, and the refiled PR together.

### Stale-target merges

- When a PR has already merged under a target (base, version, or landing target) that was stale at merge time and a later ruling has superseded that target, surface the merge in the fleet record as a **stale-target merge** — a distinct item, never folded into the routine merge count or reported as an ordinary landing.
- Its entry carries the **ruling trail**: the target it merged under, the ruling that superseded that target, and the merge's current disposition (stands as-is, follow-up required, or superseding change filed — each with its evidence or link).
- Surfacing is not reversal: undoing or superseding the merge itself remains the owner's separate decision, per the Hard Rules.

### Mid-programme intake queue

- Findings that arrive after a PR's review has closed — while the programme is still running — enter a named **intake queue** in the run's records; they do not reopen the closed review. The PR's judged verdict stands as the record of that review.
- Each intake item is named (PR, finding, source, date) and carries a **disposition** that routes it: accepted as a follow-up finding, routed to Stage 6 re-review as an author-fix item, refuted with evidence, or held for an owner ruling. An item with no disposition is not absorbed, deferred silently, or merged into the closed review's findings.
- Intake items are reported alongside the fleet's verdicts, as their own list, so the owner rules on the queue as a queue.

## Stop Conditions

Stop and ask the owner: a head drifts mid-publication or mid-merge; two reviewers' verified findings contradict on the same evidence; a PR's premise is refuted but the owner previously ruled on the strength of that premise. Everything else: rule on it, record the ruling, keep going.
