---
name: pr-fleet-review
version: 1.0.0
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

```
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
- **Gate:** inventory complete and recorded; no in-scope PR missing.

### Stage 1 — Independent review

- One independent reviewer per PR; a reviewer never reviews a PR they authored or fixed. Review oldest-to-newest when the owner so directs, otherwise in inventory order.
- **Premise-checking:** the PR's own claims (body, commit messages, linked issues) are verified against its diff. A refuted claim is cut from the verdict, or carried only at the severity the surviving evidence supports — never repeated at the PR's own valuation.
- Each reviewer returns findings with severity and file:line evidence, plus a draft verdict from the Stage 2 taxonomy.
- **Gate:** every PR has an independent review with evidence-backed findings or an explicit no-findings result.

### Stage 2 — Adversarial panel + judge

- Per PR, run the `roundtable_review` machinery: an adversarial panel argues the findings and the draft verdict; a judge rules per finding (stands / falls / re-scoped) and assigns the PR's verdict from the fixed taxonomy:

| Verdict | Meaning |
|---|---|
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

## Stop Conditions

Stop and ask the owner: a head drifts mid-publication or mid-merge; two reviewers' verified findings contradict on the same evidence; a PR's premise is refuted but the owner previously ruled on the strength of that premise. Everything else: rule on it, record the ruling, keep going.
