# Product Refinement Loop

A reusable multi-stage workflow for turning approved decisions or rough requirements into implementable, SMART-scoped work items with beads issues. Use when the user asks to "refine," "break down," or "plan" a body of work with product rigor.

## When to use
- Dano has approved a set of decisions and wants them decomposed into capabilities → features → stories → acceptance criteria → functions → tasks
- The output must meet SMART criteria (Specific, Measurable, Achievable, Relevant, Time-bound)
- The final output feeds beads issues for tracking

## When NOT to use
- For code implementation (use SDD/TDD skills)
- For reviewing existing PRs (use dap-overseer or roundtable_review)
- For simple task breakdowns that don't need adversarial validation

## The loop (7 stages)

### Stage 1 — Product breakdown
Spawn a product manager subagent. Brief it with:
- The approved decisions or requirements (source of truth)
- The repo context and key files
- Required output hierarchy: **Capabilities** → **Features** → **User stories** → **Acceptance criteria** → **Functions** → **Tasks**
- Constraints: existing repo rules (synthetic fixtures, language scope, deferred items, no new dependencies without review)
- Output: structured document at `~/workspace/plans/<date>-<topic>-product-breakdown.md`

### Stage 2 — Engineering analyst critique
Spawn an engineering analyst subagent with the Stage 1 output. Brief:
- Critique ruthlessly: are ACs actually testable? Are tasks right-sized? Missing edge cases? Hidden dependencies? Scope creep?
- Does SMART hold up, or are some "criteria" vague?
- Flag any scope questions the breakdown can't answer — distinguish ones with sensible defaults from ones that genuinely need Dano
- Return: issues by severity (BLOCKER/MAJOR/MINOR) with concrete fix suggestions

### Stage 3 — Judge
Spawn a judge subagent with Stage 1 output + Stage 2 critique. Brief:
- Decide APPROVE or REQUEST CHANGES
- Minor/fixable-inline issues → APPROVE with fixes noted
- Structural problems (untestable criteria, wrong decomposition) → REQUEST CHANGES with exact rework list
- Return: verdict with reasoning

### Stage 4 — Overseer panel (optional, on request)
Per `dap-overseer` skill: 3 independent reviewers (correctness / completeness / judgment soundness) validating the judge's verdict against the actual document and repo state. Consolidate into a report. Post findings to the relevant PR if Dano asks.

### Stage 5 — Rework (only if REQUEST CHANGES)
- Present Dano with the scope questions that genuinely need him; apply defaults for the rest
- Spawn ONE fresh rework agent (not the original author) with the fix list + Dano's answers
- Rework agent rewrites the breakdown in place, addressing every blocker/major/minor

### Stage 6 — Targeted re-review
- Fresh analyst reviews ONLY the reworked sections (not the full document)
- Verdict: APPROVE (zero blockers/majors) or REQUEST CHANGES with specifics
- One round; escalate to full re-review only if systemic rot appears

### Stage 7 — Beads (only if APPROVED)
- Check existing beads first — no duplicates
- Create issues for approved work items with testable ACs
- Link to parent issue where appropriate
- Respect sequencing constraints (e.g. "after PR #N merges")
- Mark blocked items as blocked, not ready
- Do NOT assign to the Ralph loop unless Dano explicitly says so

## Key lessons (baked in from 2026-10-18)
- **Baseline honesty:** the breakdown must never claim work "landed" that's only on an open PR branch. Always verify `git log origin/main` vs branch state.
- **Guard vs AC consistency:** any "never do X" guard must be checked against every AC that might require X. Include a joint-satisfiability proof for guards.
- **Deferred != designed:** if the owner deferred something (key management, register build), the breakdown must label it blocked/deferred, not design around it.
- **Owner-reserved questions:** if a beads issue says "neither alternative is selected," the breakdown must ask, not answer.
- **Fixture compatibility:** new rules (language refusal, field requirements) must be checked against ALL existing fixtures, not just new ones.
- **No implementation from unapproved breakdowns:** the judge's REQUEST CHANGES explicitly blocks the Ralph loop and implementers until rework passes.

## Coordinator pattern
Use a single coordinator subagent managing stage-to-stage handoffs. The coordinator:
- Spawns each stage's agent with the prior stage's output
- Does NOT open PRs, merge, or post to GitHub (report back; the parent handles external actions)
- Reports: per-stage summary, verdicts, and final beads IDs
