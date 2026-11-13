# G-P11 — Authority-index time-to-answer test: findings

Gate (plan §2, pre-registered): hand-build a one-page authority-surface
list; time five realistic questions answered with and without it. **Pass:**
the page measurably cuts answer time OR catches a surface the unaided
answer missed. **Kill:** unaided answers are as fast and complete.

## Instruments

- Unaided surface list written BEFORE any extraction
  (`unaided-surface-list.txt`) — 13 surfaces from session knowledge.
- Mechanical extraction (`extraction.json`, `protection-develop.json`,
  `protection-main.json`, `ruleset-26571395.json`,
  `ruleset-26916648.json`): GitHub API for protection + rulesets, AST
  parse for ghg caps, grammar parse for policy.data, file censuses for
  scope/manifest/vendor/workflows/baselines.
- Hand-built one-page prototype: `authority-index-prototype.md` (15 rows).
- Five questions: (Q1) which paths may a lane worker not touch, and how
  does the list change? (Q2) what limits a lane's GitHub API usage, and
  where are the numbers set? (Q3) what must be true for a PR to merge
  into develop, and what can stop it? (Q4) how does a skill enter the
  governed sync set, and what pins its content? (Q5) what preflight is
  supposed to run before autonomous work, and what enforces it?

## Time leg — honestly inconclusive for an expert tester

Unaided verification lookups, timed: Q1 0.02s, Q2 0.00s, Q3 ~3s (API
latency), Q4 0.00s, Q5 0.04s. An expert who already knows where every
surface lives answers from primary sources in seconds either way; the
page cannot measurably beat that, and this tester cannot simulate a
cold auditor. Measured in *operations* instead: unaided answers needed
2–4 distinct sources and up to 3 API calls per question; aided answers
need exactly 1 (the page). The time leg is recorded as **not
demonstrated** rather than stretched — the verdict rests on the
completeness leg, which the plan's OR-criterion makes sufficient.

## Completeness leg — the page catches three things the unaided view missed

1. **The ruleset layer.** The unaided list named "branch protection" as
   one surface. Extraction shows governance is split: classic protection
   (8 checks, conversation resolution) **plus two active rulesets** on
   the default branch (`aep-default-branch-guard`, `default-set`)
   carrying deletion/force-push blocks, a CodeQL code-scanning merge
   gate, a code-quality gate, strict status checks, and required linear
   history. An answer built from classic protection alone — the natural
   unaided move — is materially incomplete.
2. **A stale fact corrected.** Lane records from 2026-11-09 state that
   develop requires 1 approving review. At extraction time, **neither
   branch's protection contains a review requirement at all** (the key
   is absent). Whether the change was deliberate or a promotion-election
   side effect is out of scope here; the index's value is that it reads
   the current surface instead of the remembered one.
3. **SkillSpector baselines.** 13 per-skill security-scan disposition
   files (`skillspector-baselines/`) gate skill changes; the unaided
   list did not name them. (Also surfaced: CODEOWNERS is a single
   effective rule line — a near-empty surface an auditor would otherwise
   over-weight.)

## Generation feasibility (for the Phase 3 build)

11 of 15 prototype rows are fully generatable from an API or a parseable
file; 3 rows are generatable with a pointer component (ghg's runtime env
override, the G-P6 census, the Dependabot settings toggle); 2 rows are
pointer-only by nature (procedural standing rules; harness/guard
runtime state). No row restates a surface's contents. The generator the
plan prices (~200 lines) is feasible as specified.

## Verdict: **PASS**

On the completeness leg of the plan's OR-criterion: the hand-built page
catches a surface layer the unaided answer missed (rulesets), corrects
a stale remembered fact (review requirement), and adds a surface the
unaided list omitted (SkillSpector baselines). The time leg is recorded
as not demonstrated for an expert tester. Phase 3 (the generated index)
has earned its build.
