# Wire boot-gate.sh Into Autonomous Crons (Issue #17) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `scripts/boot-gate.sh` actually execute before autonomous work by prepending a fail-closed preflight step to the cron definitions that perform GitHub writes.

**Architecture:** No repo files change. The wiring is done via `cron.update` on live cron definitions (the `.md` files under `~/workspace/goals/*/crons/` are read-only copies — editing them does nothing). Each target cron gets a "Step 0" prepended to its body: run the gate, abort the run on non-zero exit.

**Tech Stack:** cron tool (`cron.view` / `cron.update`), bash, `scripts/boot-gate.sh`.

**Spec:** GitHub issue #17 (pratik-saptarshi/autonomous-engineering-platform). Verified: zero `boot-gate` references in any cron definition (grep over `~/workspace/cron.d/`, `~/workspace/goals/*/crons/`, `~/workspace/system-cron.d/`).

## Global Constraints

- **Precondition:** PR #12 must be merged to `main` before wiring. The gate path below points at the main checkout (`~/workspace/repos/autonomous-engineering-platform/scripts/boot-gate.sh`); it does not exist there until the PR merges. Task 1 verifies this.
- **Precondition:** Guard namespace must be seeded (issue #22) before wiring. The gate fails closed when guards are missing — wiring it into crons first would block every run. Verify `neurostrata-mcp list guard` shows ≥3 guard memories before proceeding; if not, complete the #22 plan first.
- **Never edit the `.md` files** under `~/workspace/cron.d/`, `~/workspace/goals/*/crons/`, or `~/workspace/system-cron.d/` — they are read-only copies. Use `cron.view` to read and `cron.update` with the **complete revised body** (all existing instructions preserved verbatim, gate section prepended).
- **Do NOT wire `neurostrata-watchdog`** — it is the recovery mechanism for a dead daemon; a fail-closed gate on daemon health would block the very run that revives it.
- **Do NOT wire low-stakes crons** (`amc-saturday-planner`, `neurostrata-export`, `dap-roadmap-reconcile`, `github-pat-expiry-reminder`) — the gate's guard checks (destructive GitHub actions, push authorization) are scoped to crons that perform GitHub writes.
- Target crons: `dap-build-check-3h` and `dap-nightly-build` (both push branches, open PRs, enable auto-merge).
- `cron.update` preserves `owner`, `delivery`, and schedule unless the task says otherwise — pass only `id` and the revised `body`.

## Review Focus

- A cron run hitting a failed gate must abort before ANY GitHub write — the gate step must be first and unconditional, not buried after work-picking.
- The `cron.update` body must be byte-complete — a truncated body would silently delete the cron's instructions; the verification step diffs the viewed body against the updated body.
- If the gate itself errors (missing binary, hung daemon), the cron must treat it as failure, not skip it — the step wording must say "non-zero exit = stop", with no "if the gate is unavailable, proceed" escape hatch.

---

### Task 1: Verify preconditions and draft the gate preamble

**Files:**
- Modify: none (verification + drafting)

**Interfaces:**
- Consumes: none
- Produces: the exact preamble text every target cron will share; go/no-go on PR #12 merge

- [ ] **Step 1: Confirm PR #12 is merged**

Run: `gh pr view 12 --repo pratik-saptarshi/autonomous-engineering-platform --json state,mergedAt --jq '{state, mergedAt}'`
Expected: `state: "MERGED"`. If not merged, STOP — do not proceed to Task 2 (the script path doesn't exist on main yet). Report back.

- [ ] **Step 2: Confirm the script exists at the stable path**

Run: `ls -la ~/workspace/repos/autonomous-engineering-platform/scripts/boot-gate.sh && bash -n ~/workspace/repos/autonomous-engineering-platform/scripts/boot-gate.sh && echo OK`
Expected: file exists, syntax OK.

- [ ] **Step 3: Draft the shared preamble**

The exact markdown to prepend (after the `# Title` line, before existing `## 1.`):

```markdown
## 0. Preflight gate — fail-closed (runs first, every run)

The daemon may be legitimately stopped (on-demand model + idle reaper) — a stopped
daemon is NOT a gate failure, but the gate needs it answering. Ensure it is up first:
run `~/go/bin/neurostrata-mcp status`; if the output does not contain "answering",
start it with `HF_HUB_OFFLINE=1 nohup ~/go/bin/neurostrata-mcp daemon >>~/.local/share/neurostrata/daemon.log 2>&1 &`
then poll `~/go/bin/neurostrata-mcp status` every 5s until "answering" (timeout 60s).
If it never answers, STOP and report the startup failure.

Then run `bash ~/workspace/repos/autonomous-engineering-platform/scripts/boot-gate.sh`.
It checks: required binaries on PATH, NeuroStrata daemon answering, guard
namespace holds the standing guard rules (≥3, incl. the destructive-GitHub-actions
rule), and `gh` authenticated.

- If it exits non-zero: STOP IMMEDIATELY. Do not pick up work, do not push,
  do not open PRs, do not enable auto-merge. End the run reporting the gate
  failure verbatim.
- There is no "gate unavailable, proceed anyway" path. A gate error IS a failure.
```

Record this text for Tasks 2-3. No commit (no repo files change in this plan).

### Task 2: Wire `dap-build-check-3h`

**Files:**
- Modify: live cron definition `dap-build-check-3h` (via `cron.update`; no repo files)

**Interfaces:**
- Consumes: Task 1 preamble text and go-ahead
- Produces: `dap-build-check-3h` body with Step 0 prepended

- [ ] **Step 1: View the current body**

Run: `cron.view` with `id: dap-build-check-3h`. Save the full body text.

- [ ] **Step 2: Prepend the preamble and update**

Call `cron.update` with `id: dap-build-check-3h` and `body:` = preamble (Task 1, Step 3) + "\n\n" + the complete original body, unchanged. Verify the update response shows the new body.

- [ ] **Step 3: Verify the update is complete (no truncation)**

Run: `cron.view` with `id: dap-build-check-3h`. Confirm: (a) the Step 0 section is first, (b) the original "## 1. Pick ONE ready item" section is intact verbatim, (c) the Beads bookkeeping section is intact. If anything is missing, restore from the Step 1 saved body and repeat Step 2.

- [ ] **Step 4: Dry-run the gate invocation**

Run: `bash ~/workspace/repos/autonomous-engineering-platform/scripts/boot-gate.sh; echo "exit=$?"`
Expected: exit 0 with four "BOOT-GATE: ... ok" lines (environment is healthy). This proves the exact command in the preamble works.

### Task 3: Wire `dap-nightly-build`

**Files:**
- Modify: live cron definition `dap-nightly-build` (via `cron.update`; no repo files)

**Interfaces:**
- Consumes: Task 1 preamble text
- Produces: `dap-nightly-build` body with Step 0 prepended

- [ ] **Step 1: View the current body**

Run: `cron.view` with `id: dap-nightly-build`. Save the full body text.

- [ ] **Step 2: Prepend the preamble and update**

Call `cron.update` with `id: dap-nightly-build` and `body:` = preamble + "\n\n" + complete original body, unchanged.

- [ ] **Step 3: Verify the update is complete**

Run: `cron.view` with `id: dap-nightly-build`. Confirm Step 0 is first and all original sections are intact verbatim.

### Task 4: Final verification — no other crons touched, gate live

**Files:**
- Modify: none

- [ ] **Step 1: Confirm exactly two crons changed**

Run: `grep -rl 'boot-gate' ~/workspace/cron.d/ ~/workspace/goals/*/crons/ ~/workspace/system-cron.d/ 2>/dev/null`
Expected: the read-only copies do NOT update (they regenerate from saved definitions) — so instead verify via `cron.view` on both ids showing the Step 0 preamble. (The .md files are stale copies; do not be alarmed they lack the text.)

- [ ] **Step 2: Confirm the watchdog was NOT wired**

Run: `cron.view` with `id: neurostrata-watchdog`, grep the body for `boot-gate`.
Expected: no match. The recovery mechanism must never be gated.

- [ ] **Step 3: Report**

No commit (no repo files changed). Report: both crons wired, watchdog untouched, gate dry-run green.
