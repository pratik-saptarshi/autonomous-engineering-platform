---
name: catchup
description: "Rebuild the human's lost context on a project from live state, in plain language: what needs them, what changed, what new words mean. Use when the human returns after a gap, says they can't follow the project anymore, asks what happened or what a term means, or before deciding what to do next when their mental model is stale. Read-only; it briefs, it does not act."
---

Catch the human up at their eye level, from state, not from memory.

## Goal

`catchup` is the re-entry point for a lost human. Long agent cycles coin words, rename files, run
experiments, and make calls faster than the owner can follow. Before any next action makes sense,
the owner's mental model must be reloaded. `catchup` reads the live project state and returns a
briefing a person with zero retained context can act on. It runs before the next move gets decided:
catchup restores the map, so that decision starts from truth instead of a stale memory of it.

## Workflow

1. Read live state only: recent file mtimes, git log/diffs, plan and state docs, re0-memo notes,
   task boards. Never brief from conversation memory alone — memory is what drifted.
2. Anchor on the human's last touch (their last message, judgment, or commit). Everything after
   that point is the delta; everything before it is assumed known and stays out.
3. Compose in decision order, not chronological order:
   - **Needs you** — decisions, judgments, or inputs only the human can give, each self-contained
     enough to act on without opening another file.
   - **Changed while you were away** — outcomes, not process. "The plan's scoring rule was
     replaced" beats "I ran three analysis passes."
   - **New words** — every term coined or repurposed since their last touch, one line each, with
     where it lives. Skip terms they already used themselves.
4. Gloss on first use: any project-specific term appearing in the briefing gets an inline
   plain-language aside at its first occurrence, even if a glossary section follows.
5. Keep the default short (a screen or less). End with drill-down offers per section, not with
   everything expanded.

## Ruling-batch items

When several decisions queue at once, present them as a ruling batch: one item per decision
cluster, each in the same shape, so the human can settle the whole batch in a few short replies.

Per cluster:

- **What sits in front of you** — the decision itself and its concrete object (the PR, the
  condition, the claim), self-contained: no file needs opening to rule on it.
- **The real benefit** — what ruling this way actually gains, in outcomes, not effort saved.
- **The honest cost** — what it risks, spends, or forecloses, stated even when it argues
  against the recommendation.
- **Recommendation** — one clear call. A cluster with no recommendation is a briefing failure:
  the agent did the analysis, so the agent owes the answer it points to.
- **Reply shapes** — the exact short replies that settle the cluster, keyed to it, e.g.
  `#48: C7 = waive` / `#48: C7 = satisfy`, or `#48: remediation = go` / `#48: remediation = hold`.
  A reply in that shape is a complete ruling; act on exactly its scope and record it as settled.

Clusters the human has already ruled on leave the batch — silence the settled applies to
batches too. This shape is used wherever a batch of rulings is put to the human, whether it
rides inside a catchup briefing's "Needs you" section or stands alone.

## Rules

- State-grounded: every claim traces to a file, commit, or artifact the human can open. No "as
  we discussed."
- Read-only on the project. `catchup` briefs; it does not fix, rename, or decide.
- The ask comes first. A briefing that buries the one question needing the human is a log.
- Outcome voice, not journey voice. Narrating the agent's process is self-report, not briefing.
- Silence the settled: closed decisions and healthy metrics get one line or none.
- Honest completeness: "done" means verified done; "moved" is not "reconciled"; say which.
- Do not re-explain terms the human demonstrably knows (they used them first).

## Verification

Before finishing:

1. Cold-read the briefing: no sentence requires pre-gap memory or an unglossed coined term to parse.
2. The "needs you" items are each actionable without opening another file.
3. Every claim has a checkable source (file, commit, artifact path).
4. It fits on a screen, with expansion offered rather than delivered.
