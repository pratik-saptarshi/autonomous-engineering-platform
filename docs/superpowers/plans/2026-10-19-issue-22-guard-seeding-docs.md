# Document Guard-Namespace Seeding for boot-gate.sh (Issue #22) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a fresh-VM operator a documented, copy-pasteable path to seed the `guard` namespace so `scripts/boot-gate.sh` check 3 can pass, and link it from the script's header.

**Architecture:** One new runbook subsection (with the three exact guard-rule texts and the seeding commands) plus a one-line cross-reference in the boot-gate.sh header comment. Docs only; no behavior change.

**Tech Stack:** Markdown docs in the AEP repo worktree; `neurostrata-mcp add` CLI for the seeding commands.

**Spec:** GitHub issue #22 (pratik-saptarshi/autonomous-engineering-platform). Ground truth (verified 2026-10-19 via `neurostrata-mcp list guard`): the namespace holds exactly 3 memories of type `guard_rule`; the gate requires ≥3 AND one containing the string "Destructive GitHub actions". Seeding syntax verified: `neurostrata-mcp add <NAMESPACE> <MEMORY_TYPE> <CONTENT> [LOCATION]`.

## Global Constraints

- Worktree: `~/workspace/worktrees/aep-ci-pr`, branch `feat/ci-platform-gates`. Exact-path `git add` only; never `git add -A`.
- Commit identity: `Musebot-Astro <6238157+pratik-saptarshi@users.noreply.github.com>`; Conventional Commits subjects.
- The three rule texts below are copied verbatim from the live guard namespace — reproduce them EXACTLY (em-dashes, punctuation, and the "2026-10-17" date in rule 3). The gate's substring check depends on "Destructive GitHub actions" appearing verbatim in rule 1.
- Rules 2 and 3 are DAP-repo-specific; rule 1 is the universal one. The runbook must say so, and must state that all three are currently required for the gate's ≥3 threshold.
- Do NOT merge; this plan ends with commits on the branch for PR #12 review.

## Review Focus

- An operator copy-pasting the seeding commands must get exactly the three rules the gate expects — verify the documented texts byte-match the live namespace (the plan's verification step diffs them).
- The seeding step must come AFTER the daemon is running (runbook §3) — verify the new subsection is placed after §3, not before.
- The boot-gate.sh header reference must name the exact runbook section — verify the section anchor text matches.

---

### Task 1: Add "Seed the guard namespace" to the runbook

**Files:**
- Modify: `docs/runbook.md` (new subsection after §3 "Start the daemon", before §4)

**Interfaces:**
- Consumes: the three verified rule texts below
- Produces: a runbook subsection with copy-pasteable seeding commands

**The three guard rules (verbatim):**

Rule 1 (required — the gate greps for "Destructive GitHub actions"):
> Destructive GitHub actions — branch deletion, force-push, history rewrite, repository deletion — each require the user's explicit per-action authorization naming the exact target. Never bundle this permission into a general proceed or a compound question; ask separately every time.

Rule 2 (DAP-repo-specific):
> In the document-accessibility-pipeline repo, never push without the user's explicit authorization. Publishing goes only through scripts/source-publisher.sh publish. Leave repo-rule-gated changes as local commits or open PRs.

Rule 3 (DAP-repo-specific):
> Merging a PR: default requires the user's explicit per-PR authorization — independent review approved, CI green on the exact head, every review comment analyzed against current code and addressed. On repos under the user's auto-merge rule (2026-10-17; DAP: branch protection with required CI checks + required conversation resolution), the pipeline enables GitHub auto-merge (squash) instead; GitHub merges only when CI is green and zero review threads are unresolved. Never merge directly on behalf of a reviewer and never bypass branch protection.

- [ ] **Step 1: Locate the insertion point**

Run: `grep -n '^## 4\.' docs/runbook.md`
Expected: the `## 4. MCP client and connector registration` heading line number. The new subsection goes immediately before it.

- [ ] **Step 2: Insert the new subsection**

Insert at the end of §3 (after the daemon-forking paragraph, immediately before the `## 4. MCP client` heading at line 80), as a `###`-level subsection of §3 (the runbook's top-level sections are `##`-numbered 1-8; do not renumber them):

```markdown
### Seed the guard namespace

`scripts/boot-gate.sh` check 3 requires ≥3 memories in the `guard`
namespace, including one containing "Destructive GitHub actions". On a fresh
VM the namespace is empty and the gate fails closed. Seed it now (daemon must
be running — see §3):

```bash
BIN=~/go/bin/neurostrata-mcp   # or wherever the binary lives (§1)
$BIN add guard guard_rule "Destructive GitHub actions — branch deletion, force-push, history rewrite, repository deletion — each require the user's explicit per-action authorization naming the exact target. Never bundle this permission into a general proceed or a compound question; ask separately every time."
$BIN add guard guard_rule "In the document-accessibility-pipeline repo, never push without the user's explicit authorization. Publishing goes only through scripts/source-publisher.sh publish. Leave repo-rule-gated changes as local commits or open PRs."
$BIN add guard guard_rule "Merging a PR: default requires the user's explicit per-PR authorization — independent review approved, CI green on the exact head, every review comment analyzed against current code and addressed. On repos under the user's auto-merge rule (2026-10-17; DAP: branch protection with required CI checks + required conversation resolution), the pipeline enables GitHub auto-merge (squash) instead; GitHub merges only when CI is green and zero review threads are unresolved. Never merge directly on behalf of a reviewer and never bypass branch protection."
```

Rules 2 and 3 are specific to the document-accessibility-pipeline repo; rule 1
is universal. All three are currently needed for the gate's ≥3 threshold —
if you replace the DAP-specific rules, keep the count at ≥3.

Verify: `neurostrata-mcp list guard` should show `Found 3 memories`, and
`scripts/boot-gate.sh` check 3 should print `BOOT-GATE: guards ok`.
```

- [ ] **Step 3: Verify the rule texts byte-match the live namespace**

Run: `neurostrata-mcp list guard > /tmp/guard-live.txt` and for each of the three documented texts, `grep -F -q '<first 40 chars of rule>' /tmp/guard-live.txt && echo "rule N matches"`.
Expected: all three match. (Full byte-compare isn't possible from the doc rendering; the 40-char prefix plus the gate's own substring check is the practical verification.)

- [ ] **Step 4: Commit**

```bash
git add docs/runbook.md
git commit -m "docs(runbook): document guard namespace seeding for boot-gate"
```

### Task 2: Cross-reference from boot-gate.sh header

**Files:**
- Modify: `scripts/boot-gate.sh` (header comment only, no behavior change)

**Interfaces:**
- Consumes: Task 1's new subsection anchor
- Produces: a header comment pointing at the seeding docs

- [ ] **Step 1: Read the current header**

Run: `sed -n '1,18p' scripts/boot-gate.sh`
Expected: the contract comment block ending before `set -euo pipefail`.

- [ ] **Step 2: Add the cross-reference**

Append to the header comment (keeping the existing style):
```
# Check 3 needs ≥3 guard rules incl. "Destructive GitHub actions"; on a fresh
# VM seed them first — see docs/runbook.md "Seed the guard namespace".
```

- [ ] **Step 3: Verify syntax unchanged and self-test still passes**

Run: `bash -n scripts/boot-gate.sh && ./scripts/boot-gate.sh --self-test | tail -1`
Expected: `SELF-TEST: all ok` (comment-only change; behavior identical).

- [ ] **Step 4: Commit**

```bash
git add scripts/boot-gate.sh
git commit -m "docs(boot-gate): reference guard seeding docs in header"
```

### Task 3: End-to-end verification

**Files:**
- Modify: none

- [ ] **Step 1: Confirm the docs chain is complete**

Run: `grep -n 'Seed the guard namespace' docs/runbook.md && grep -n 'Seed the guard namespace' scripts/boot-gate.sh`
Expected: both files reference the section; the runbook contains the three `add` commands.

- [ ] **Step 2: Confirm the runbook verification checklist mentions guards**

Run: `grep -n -i 'guard' docs/runbook.md | head`
Expected: at least the new subsection and the verification command. If the §8 checklist has no guard line, add one: `- [ ] boot-gate.sh check 3 passes (guard namespace seeded — see "Seed the guard namespace")` and commit it as part of this task.

- [ ] **Step 3: Report**

No further commits unless Step 2 added the checklist line (then: `git add docs/runbook.md && git commit -m "docs(runbook): add guard check to verification checklist"`).
