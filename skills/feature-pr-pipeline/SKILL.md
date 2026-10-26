---
name: feature-pr-pipeline
version: 1.0.0
author: pratik-saptarshi
description: >
  Standardized feature-to-PR workflow — plan, implement with subagent-driven
  TDD, independent whole-branch review, hygiene pass, then PR with CI and
  review-comment gating. Use when the user asks for the standard workflow,
  says "make this the standard process", or requests a multi-step feature,
  fix, or docs change that will end as a pull request.
---

# Feature-to-PR Pipeline

**Announce at start:** "I'm using the feature-pr-pipeline skill for this feature-to-PR run."

## When to Use

Use for any multi-step feature, fix, or docs change that will end as a pull request: plan → implement → review → hygiene → PR → CI gate.

Do NOT use for: one-line fixes (do them directly), exploratory spikes (no PR planned), or work the user asked to keep local-only.

**Authorization (read once):** pushing a branch and opening a PR each require the user's explicit per-action authorization naming the exact branch/PR — except on repos where the user has authorized the auto-merge rule (see below), where scheduled pipeline runs may push + open PRs autonomously once all hygiene gates pass. Merging: default is explicit per-PR authorization, never bundled into a general "proceed". On repos under the auto-merge rule (branch protection with required CI checks + required conversation resolution in place), Stage 7 enables GitHub auto-merge (`gh pr merge --squash --auto`) instead of asking per PR; GitHub then merges only when CI is green and zero review threads are unresolved. Direct merges (merge button, `gh pr merge` without `--auto`) always need explicit per-PR authorization. Branch deletion, force-push, and history rewrite need separate explicit per-action approval naming exact targets. Never bypass branch protection.

## Prerequisites

This skill orchestrates five companion workflow skills. At Stage 0, confirm each is installed (or that you know its procedure):
- `writing-plans` — implementation plans with task-level tests
- `subagent-driven-development` — fresh implementer subagent + reviewer per task
- `test-driven-development` — RED → GREEN → refactor
- `scrubbing-public-tree` — pre-push hygiene pass
- `finishing-a-development-branch` — push/PR integration decision

If a companion is missing, install it or substitute its documented procedure before proceeding — the stages below reference these skills as written.

## The Pipeline

```
Stage 0: Setup      → worktree + branch from the repo's default branch, verify base
Stage 1: Plan       → writing-plans (TDD checks per task)
Stage 2: Implement  → subagent-driven-development + test-driven-development
Stage 3: Review     → fresh independent whole-branch reviewer
Stage 4: Hygiene    → scrubbing-public-tree on the branch
Stage 5: Integrate  → finishing-a-development-branch (push + open PR)
Stage 6: Gate       → CI green + every review comment resolved
Stage 7: Merge      → auto-merge (`gh pr merge --squash --auto`) on repos under the auto-merge rule; otherwise explicit per-PR authorization, else stop and report
```

### Stage 0 — Setup

- Fetch origin; create an isolated worktree + feature branch **from the repository's default branch** (resolve it — e.g. `git symbolic-ref refs/remotes/origin/HEAD` — never assume `origin/main`, and never branch from a diverged local branch).
- Verify the base: the commit(s) being built on must be ancestors of the new branch.
- Save the plan under the goal's `files/plans/` (or the repo's `docs/superpowers/plans/` when the tree is clean) — never in a dirty working tree.
- **Gate:** isolated worktree + branch exist on the verified base; plan location chosen; companion skills confirmed available (see Prerequisites).

### Stage 1 — Plan

- Follow `writing-plans`. Additionally, give every task a **TDD check script** (shell assertions in `/tmp`, never committed): it must FAIL on the unmodified tree (RED) and PASS after the edit (GREEN).
- Capture repo-specific rules in the plan's Global Constraints (e.g. no `bd` in worktrees, provenance hash updates, Markdown-only).
- **Gate:** plan covers every task with a RED-verified check script; Global Constraints recorded.

### Stage 2 — Implement

- Follow `subagent-driven-development` and `test-driven-development` as written: fresh implementer subagent per task, task reviewer after each, each task check (RED) → edit → check (GREEN) → Conventional Commit.
- Run continuously — no check-ins between tasks. Rule on ambiguity, record rulings in the ledger, keep going.
- **Gate:** every task committed GREEN; all task reviews clean.

### Stage 3 — Independent review

- Assign a FRESH agent (never a task implementer/reviewer) to review the whole branch diff vs base: spec compliance, non-regression of prior safeguards, code/prose quality. Run SDD fix rounds on findings.
- **Gate:** independent review reports no unresolved findings.

### Stage 4 — Hygiene

- Run `scrubbing-public-tree` against the branch's changed files before any push. Fix real findings; classify false positives — never weaken a guard to silence a match. If the skill file itself changed, recompute any pinned hashes afterward.
- **Gate:** hygiene reports no unresolved real findings.

### Stage 5 — Integrate

- Follow `finishing-a-development-branch` for the push/PR decision, per the Authorization rule above (ask once, name the branch).
- **Gate:** branch pushed and PR opened with user authorization. If the user declines, the pipeline ends here: report the local branch state and stop — do not proceed to Stage 6.

### Stage 6 — Gate

- Monitor CI to completion. Read every review comment and inline thread. Fix real findings; adjudicate non-findings explicitly. Route every fix back through the applicable gates (independent review for logic/prose changes, hygiene for any new content) before pushing the update. Repeat until CI is green and all threads resolved.
- **Codex final-head gate.** Where the repo's Codex review is active, Stage 6 is not complete until Codex has reviewed the PR's FINAL head (the summary comment's `commit_sha` equals the current head) — unless the class-recurrence trigger below has fired and its census + cap-and-file are recorded, in which case the census's own commits may postdate Codex's last review by design. This gate is a staleness check: it establishes that Codex has reviewed the current tree, and nothing more. Codex silence is not evidence of correctness, and high-risk surfaces still require independent panel or human review per this pipeline. **Class-recurrence trigger:** when a second finding lands in the same defect class or mechanism (classes per the pattern analysis's taxonomy) after that class was claimed fixed, stop point-fixing that class. The next step is a generalization pass — a full census of the component across its mechanism families (grammar, state, identity, provenance, surfaces) — before any further point fix in that class. The default continuation after the census is cap-and-file: the census's remaining findings in that class are filed as issues and the PR may proceed, with the user notified asynchronously. Autonomous lanes never park waiting for a user decision on this trigger.
- **Gate:** CI green; every review comment and thread resolved; Codex (where the repo's Codex review is active) has reviewed the final head, or the class-recurrence trigger fired and its census + cap-and-file are recorded.

### Stage 7 — Merge

- On repos under the auto-merge rule: enable auto-merge with `gh pr merge --squash --auto <pr>`. Branch protection (required CI checks + required conversation resolution) gates the actual merge — it happens only when CI is green and every thread is resolved. Do not wait for CI; report the PR URL and that auto-merge is queued.
- Otherwise default: STOP and report (PR URL, CI status, comment dispositions) for a merge decision. Merge only under the Authorization rule above.
- **Gate:** auto-merge enabled, or merge done with explicit authorization, or report delivered and handed to the user.

## Stop Conditions

Stop and ask the user: any irreversible or destructive operation; any action the Authorization rule covers; a plan so broken every path forward is a guess. Everything else: rule on it, record the ruling, keep going.
