# Fix Daemon Auto-Restart Doc Contradictions (Issue #16) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all false claims that a dead NeuroStrata daemon revives via MCP auto-spawn, so every doc agrees with the verified finding (direct nohup restart works; MCP-spawn revive is unreliable).

**Architecture:** Two surgical text edits (one deletion, one rewrite) plus a repo-wide grep sweep to prove no other auto-restart claims remain. No code changes; docs only.

**Tech Stack:** Markdown docs in the AEP repo worktree.

**Spec:** GitHub issue #16 (pratik-saptarshi/autonomous-engineering-platform). The verified ground truth is `docs/limitation-analysis.md` item 1 Resolution (line 11): "revives a dead daemon via direct `nohup` restart (an MCP-spawn revive was tried and found unreliable — the stdio server hangs without starting the daemon)". The troubleshooting table at `docs/operations.md:98` agrees. The false claims are at `docs/operations.md:26` and `README.md:117`.

## Global Constraints

- Worktree: `~/workspace/worktrees/aep-ci-pr`, branch `feat/ci-platform-gates`. Exact-path `git add` only (repo has no `.gitignore`); never `git add -A`.
- Commit identity: `Musebot-Astro <6238157+pratik-saptarshi@users.noreply.github.com>`; Conventional Commits subjects.
- Do NOT touch `docs/limitation-analysis.md` or the troubleshooting table — they are already correct.
- Do NOT merge; this plan ends with a commit on the branch for PR #12 review.

## Review Focus

- A reader following the edited operations.md daemon section must never conclude MCP-spawn revive works — verify the surrounding paragraph still reads coherently after the deletion.
- A reader following the edited README bullet must get the same mechanism as limitation-analysis.md — verify the rewritten bullet names direct nohup restart, not MCP spawn.
- No other file in the repo may still claim auto-restart — the grep sweep must cover README.md, docs/, and skills/ (skill docs were found referencing nonexistent paths before).

---

### Task 1: Fix `docs/operations.md:26`

**Files:**
- Modify: `docs/operations.md` (delete line 26; keep surrounding section coherent)

**Interfaces:**
- Consumes: the verified finding (limitation-analysis.md item 1, operations.md:98)
- Produces: a daemon section with no auto-restart claim

- [ ] **Step 1: Read the current section**

Run: `sed -n '14,28p' docs/operations.md`
Expected: line 26 reads "If the daemon is down, the next MCP client spawn restarts it automatically." with the restart code block above it and "## Watchdog and backups" below.

- [ ] **Step 2: Delete line 26 and bridge the paragraph**

Remove the sentence "If the daemon is down, the next MCP client spawn restarts it automatically." Replace it with one sentence pointing at the verified mechanism: "If the daemon is down, restart it via the nohup command above (the watchdog cron does not restart it — `scripts/watchdog-backup.sh` treats a down daemon as expected idle state and exits 0; a bare MCP spawn does not reliably auto-start it — see Troubleshooting)."

- [ ] **Step 3: Verify the section reads coherently**

Run: `sed -n '14,28p' docs/operations.md`
Expected: code block, then the replacement sentence, then "## Watchdog and backups" — no dangling references, no leftover auto-spawn claim.

- [ ] **Step 4: Commit**

```bash
git add docs/operations.md
git commit -m "docs(operations): remove false MCP auto-spawn revive claim"
```

### Task 2: Fix `README.md:117`

**Files:**
- Modify: `README.md` (Known limitations bullet, line 117)

**Interfaces:**
- Consumes: the Task 1 wording (for consistency)
- Produces: a README bullet matching limitation-analysis.md

- [ ] **Step 1: Read the current bullet**

Run: `sed -n '114,118p' README.md`
Expected: bullet starting "- The NeuroStrata daemon runs under `nohup`..." containing "revives a dead daemon via MCP auto-spawn" and "A dead daemon is also restarted automatically on the next MCP spawn."

- [ ] **Step 2: Rewrite the revive mechanism**

Replace "that revives a dead daemon via MCP auto-spawn" with "that revives a dead daemon via direct nohup restart (MCP-spawn revive verified unreliable 2026-10-16)". Delete the sentence "A dead daemon is also restarted automatically on the next MCP spawn."

- [ ] **Step 3: Verify against the analysis doc**

Run: `grep -c 'MCP auto-spawn\|automatically on the next MCP spawn' README.md`
Expected: `0`

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): correct watchdog revive mechanism to direct nohup restart"
```

### Task 3: Sweep for remaining auto-restart claims

**Files:**
- Modify: none (verification only; fix any hits as new edits in this task)

**Interfaces:**
- Consumes: Tasks 1-2 completions
- Produces: proof of zero remaining false claims

- [ ] **Step 1: Grep the whole AEP-authored tree**

Run: `grep -rn -i 'auto-spawn\|automatically restart\|restarts it automatically\|restarted automatically' README.md docs/ skills/ AGENTS.md 2>/dev/null | grep -v 'does \*not\*\|does not reliably\|verified unreliable'`
Expected: zero lines. Any hit is a new occurrence of the false claim — fix it with the same "direct nohup restart" wording before proceeding.

- [ ] **Step 2: Confirm the true claims still stand**

Run: `grep -rn 'direct .nohup. restart\|does .not. reliably auto-start' docs/ README.md | head -5`
Expected: at least the limitation-analysis.md Resolution line and the operations.md troubleshooting row are present.

- [ ] **Step 3: Commit (only if Step 1 produced fixes)**

```bash
git add -u  # only if files changed in Step 1
git commit -m "docs: remove residual MCP auto-spawn revive claims"  # only if files changed
```
If Step 1 found nothing, skip this step — no empty commit.

> **Reconciliation note (2026-10-23):** The 'watchdog cron does not restart it' claim is accurate for the REPO script and for the deployed script's no-change+reaped path. It does not cover the deployed script's change-path unconditional restart — see `docs/daemon-lifecycle-contract.md` § The Fork. The plan's core correction (MCP-spawn revive is unreliable; use direct nohup) stands; the demand-path gap is now tracked in `docs/daemon-lifecycle-contract.md` § Known gaps.
