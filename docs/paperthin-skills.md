# paperthin skills

Vendored into `~/workspace/custom-skills/` on 2026-10-18. Upstream:
[LilMGenius/paperthin](https://github.com/LilMGenius/paperthin) (MIT),
pinned to commit `7d5dc62`. All 28 `SKILL.md` files are verbatim copies —
nothing rewritten, nothing trimmed. Attribution (license, notice) lives in
`~/workspace/custom-skills/paperthin-attribution/`.

## What it is

A skill library of low-level agentic design patterns. Its thesis: every
skill removes rather than adds — anti-slop reflexes that keep artifacts
clean, claims true, and plans honest. It ships for every major agent host
(Claude Code, Codex, OpenCode, Cursor, Copilot, Pi, and others); here the
files are vendored the same way as the superpowers and mattpocock sets.

Skills are split into two invocation classes. **Model-invoked** skills can
fire on their own when the trigger fits. **User-invoked** skills (marked in
upstream frontmatter with `disable-model-invocation: true`) only fire when
a human names them — deliberately, because their trigger is a human-decided
act (commit, release, merge) or because a standing reflex would bias the
agent (demolition, compression).

## Why adopted

Three gaps in the existing library that paperthin fills:

1. **Writing hygiene.** Nothing in the current set fights artifact rot.
   `re0`, `debloat`, `shower`, `dedash`, `detool`, `reorder`, and `ssotize`
   give the loop reflexes for rewriting drifted artifacts, compressing
   bloat, cold-reading with fresh eyes, and consolidating scattered facts
   to a single source of truth.
2. **Truth checks.** `factchk` verifies reality-grounded claims in both
   directions (could the absurd be real, the obvious false?). `mandela`
   audits evals for leakage — whether outside ground-truth actually
   entered the loop or the verifier merely agreed with the designer. `sip`
   runs the suite on the model's own output right after it is produced,
   when author bias is highest.
3. **Risk handling.** `autobahn` carves guardrail-adjacent scope out up
   front so the safe remainder runs at full strength; `hate` returns the
   one objection that could kill a plan plus the cheapest test. These
   complement the existing guard rules and review panels at the planning
   stage rather than the review stage.

Adjacent overlaps (not duplicates): `macrothink` with the grilling
interview, `prism` with the overseer adversarial panels, `re0-git` /
`re0-release` / `re0-merge` with finishing-a-development-branch and
receiving-review, the `coil/` loop skills with the ralph lanes and retro.

## The catalog

### depth/ — one artifact, now

| Skill | What it does | Invoked by |
|---|---|---|
| re0 | Rewrite a drifted artifact into a clean v0, not another patch | model |
| readchk | Check the model's read of the request; surface only a real surviving fork | model |
| aim | Read handed-over data and propose the intent to confirm, instead of asking | model |
| modelchk | Size the cheapest sufficient tier and reasoning effort | model |
| hate | Refuse to be nice: the one objection that could kill it, plus the cheapest test | user |
| macrothink | Strip the bait, fan out fresh reads, report divergence first | user |
| feynman | Press a just-made decision until it can be explained, or flag the gap | user |
| autobahn | Carve unsafe scope out up front, run the safe rest at full strength, log the descope | model |
| reorder | Realign a drifted listing under one stated principle; move items only, reword nothing | user |
| detool | Replace incidental stack nouns with the mechanism they mean | model |
| dedash | Remove em-dashes and look-alikes, picking the punctuation each spot needs | user |
| debloat | Compress a bloated artifact to its load-bearing density; cut words, never a rule | user |
| shower | Cold-read it with fresh, zero-context eyes: does it stand alone? | model |
| factchk | Verify what's asserted against sources both ways | model |
| mandela | Audit for leakage: does outside ground-truth actually enter? | model |
| sip | After any change, taste it with the repo's own clean-and-true checks | model |
| re0-git | Rewrite a finished commit's message so `git log` alone hands off | user |
| re0-release | Run the shipping and releasing checklist, then tag and publish once confirmed | user |
| re0-merge | Review and land a contribution: gate it, keep the author's credit | user |

### breadth/ — many artifacts, now

| Skill | What it does | Invoked by |
|---|---|---|
| ssotize | Audit scatter, then consolidate to one home and point the rest at it | model |
| re0-upgrade | Upgrade to the full current catalog in one command | user |

### coil/ — one project, across iterations

| Skill | What it does | Invoked by |
|---|---|---|
| re0-plan | Open a new iteration folder with DESIGN/WORKFLOW/EVIDENCE before the first turn | user |
| re0-loop | Run the build → QA → memo → work loop so learning compounds, not code | model |
| re0-memo | Pull the lessons and anti-patterns from a finished or failed cycle | model |
| re0-work | Start over from v0, keeping only the lessons that earned reuse | model |
| catchup | Rebuild lost context from live state: what needs them, what changed, what new words mean | model |
| nba | Read the live cycle state and return the single next best action, not a menu | model |

### mesh/ — many minds, across rounds

| Skill | What it does | Invoked by |
|---|---|---|
| prism | Split one artifact across independent lenses; return where they clash and the question that resolves it | user |

## Updating

Re-clone upstream, re-copy the 28 files, and diff against the pinned
commit before replacing. The upstream `/re0-upgrade` workflow covers
renames and retirements; apply its report, don't hand-edit around it.
