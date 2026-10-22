# Watchdog BIN Path Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the two defects in `scripts/watchdog-backup.sh` — the `BIN` path pointing to a nonexistent binary (silent no-op) and `stop_daemon` called before its definition — so the repo script is safe to deploy.

**Architecture:** Two surgical edits to `scripts/watchdog-backup.sh`: correct the `BIN` path and add a fail-fast executable check (so a future path regression can never again degrade silently); relocate the `stop_daemon()` definition above the main flow with a byte-identical body. A third small task corrects the stale header comment that describes the old always-on model.

**Tech Stack:** Bash (`set -euo pipefail`), shellcheck, shfmt.

**Spec:** GitHub issue #15 (pratik-saptarshi/autonomous-engineering-platform): "`BIN` points to a binary that does not exist (line 30)" and "`stop_daemon` called before definition (line 204 vs 212)". Suggested fix: line 30 → `BIN="$HOME/go/bin/neurostrata-mcp"`; add fail-fast `[ -x "$BIN" ]` check; move `stop_daemon()` above the main flow.

## Global Constraints

- Conventional Commits for every commit; author `Musebot-Astro <6238157+pratik-saptarshi@users.noreply.github.com>`.
- Do not modify `reference/esf/` (byte-identical vendor constraint).
- The script must remain shellcheck-clean and `shfmt -d -i 2` clean (CI enforces both).
- Preserve the on-demand lifecycle model — do not reintroduce always-on behavior.
- Exact-path `git add` only; never `git add -A` (repo has no `.gitignore`).
- Do not touch the deployed copy at `~/workspace/neurostrata/bin/watchdog-backup.sh` (deployment is issue #18's scope).

## Review Focus

- **BIN path containing spaces or special chars** — the fail-fast check and every `"$BIN"` use must stay quoted; the Task 1 test pins this by running with a space in the fake HOME path.
- **Fail-fast check placement** — it must run after `mkdir -p "$STAGE"` so `log()` can write to `$LOG`; placed earlier, the FATAL message itself would crash on a missing log dir. The Task 1 test asserts the FATAL message appears in output.
- **`stop_daemon` relocation must not alter behavior** — same function body, new position only; the Task 2 test diffs the body before/after (must be byte-identical).
- **Future BIN regression** — the fail-fast check is the permanent guard; the Task 1 fake-HOME test pins it (the test fails if the check is ever removed).
- **Healthy no-change path still exits 0 with a valid BIN** — the guard must not fire when the binary exists; verified in Task 1 Step 5 against the real environment.

---

### Task 1: Fix BIN path and add fail-fast executable check

**Files:**
- Modify: `scripts/watchdog-backup.sh:30` (BIN assignment)
- Modify: `scripts/watchdog-backup.sh` (insert fail-fast check after line 40, `mkdir -p "$STAGE"`)

**Interfaces:**
- Consumes: none (first task)
- Produces: corrected `BIN="$HOME/go/bin/neurostrata-mcp"`; fail-fast guard `[ -x "$BIN" ] || { log "FATAL: ..."; exit 1; }` placed where `log()` can write

- [ ] **Step 1: Write the failing test** — save as `/tmp/test-bin-guard.sh`:

```bash
#!/usr/bin/env bash
# The script must fail fast (not silently exit 0) when BIN is not executable.
set -u
SCRIPT="$HOME/workspace/worktrees/aep-ci-pr/scripts/watchdog-backup.sh"
export HOME="/tmp/wdtest fakehome"
rm -rf "$HOME"
out="$(bash "$SCRIPT" 2>&1)"
rc=$?
if [ "$rc" -ne 0 ] && echo "$out" | grep -q "FATAL"; then
  echo "PASS: fail-fast guard triggered (rc=$rc)"
else
  echo "FAIL: rc=$rc (expected non-zero with FATAL in output)"
  echo "--- output was:"; echo "$out"
  exit 1
fi
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `bash /tmp/test-bin-guard.sh`
Expected: FAIL with `rc=0` — the script logs "daemon idle (on-demand model) — nothing to do" and exits 0 (the silent no-op: `daemon_healthy` fails because `$BIN` doesn't exist, so the main flow takes the idle branch).

- [ ] **Step 3: Implement in `scripts/watchdog-backup.sh`**

Change line 30 to:
```bash
BIN="$HOME/go/bin/neurostrata-mcp"
```

After line 40 (`mkdir -p "$STAGE"`), insert:
```bash
# Fail fast on a bad binary path: without this, a missing $BIN makes
# daemon_healthy() always fail and the script silently exits 0 forever.
[ -x "$BIN" ] || { log "FATAL: neurostrata-mcp not found or not executable at $BIN"; exit 1; }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `bash /tmp/test-bin-guard.sh`
Expected: PASS with `rc=1` and "FATAL" in output.

- [ ] **Step 5: Verify no regression with a valid BIN**

Run: `bash -n scripts/watchdog-backup.sh` (must print nothing) and `~/go/bin/shfmt -d -i 2 scripts/watchdog-backup.sh` (must print nothing). Then run the script against the real environment (real `$HOME`, daemon healthy): it must proceed past the guard (no FATAL) — assert exit code is 0 and the log shows the normal flow, not the FATAL line.

- [ ] **Step 6: Commit**

```bash
git add scripts/watchdog-backup.sh
git commit -m "fix(scripts): point watchdog BIN at real binary and fail fast if missing"
```

---

### Task 2: Move stop_daemon definition above the main flow

> **Note:** Task 1 inserts lines into this file, so the line numbers below (204/212) are pre-Task-1 values. Re-derive with `grep -n` before starting; the test in Step 1 computes positions dynamically and is the source of truth.

**Files:**
- Modify: `scripts/watchdog-backup.sh` (relocate the `stop_daemon()` block from lines 212-234 to before line 159, the `# 1. On-demand model` main-flow section)

**Interfaces:**
- Consumes: Task 1's modified `scripts/watchdog-backup.sh`
- Produces: `stop_daemon()` defined before its first call site (line 204); function body byte-identical

- [ ] **Step 1: Write the failing test** — save as `/tmp/test-func-order.sh`:

```bash
#!/usr/bin/env bash
# stop_daemon() must be defined before its first call site (bash does not hoist).
set -u
F=~/workspace/worktrees/aep-ci-pr/scripts/watchdog-backup.sh
def=$(grep -n '^stop_daemon() {' "$F" | cut -d: -f1)
first_call=$(grep -n 'stop_daemon' "$F" | grep -v '()' | head -1 | cut -d: -f1)
if [ "$def" -lt "$first_call" ]; then
  echo "PASS: defined at $def, first called at $first_call"
else
  echo "FAIL: defined at $def, first called at $first_call (definition must come first)"
  exit 1
fi
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `bash /tmp/test-func-order.sh`
Expected: FAIL with "defined at 212, first called at 204".

- [ ] **Step 3: Implement in `scripts/watchdog-backup.sh`**

Cut the entire `stop_daemon() { ... }` block (from the `# 3. Quiesce:` comment through the closing `}`) and paste it immediately before the `# 1. On-demand model (2026-10-17):` comment block that starts the main flow. Do not alter the function body — relocation only. Leave a brief comment at the old location is unnecessary; just move it.

- [ ] **Step 4: Run the test to verify it passes**

Run: `bash /tmp/test-func-order.sh`
Expected: PASS (definition line < first call line).

Then verify the body is unchanged: extract the function before/after via `git diff` and confirm the diff shows only moved lines (no content changes within the function). Also `bash -n scripts/watchdog-backup.sh` must print nothing.

- [ ] **Step 5: Commit**

```bash
git add scripts/watchdog-backup.sh
git commit -m "fix(scripts): define stop_daemon before its first call site"
```

---

### Task 3: Correct the stale header comment

**Files:**
- Modify: `scripts/watchdog-backup.sh:1-13` (header comment block)

**Interfaces:**
- Consumes: Tasks 1-2's modified `scripts/watchdog-backup.sh`
- Produces: header comment accurately describing the on-demand model

- [ ] **Step 1: Rewrite header step 1**

The header currently says "1. Watchdog: if the daemon is down, restart it directly (nohup)" — this describes the old always-on model and contradicts the on-demand behavior at the main flow ("If it is down, that is the expected idle state — nothing to do"). Replace step 1 with text matching the on-demand model, e.g.: "1. Watchdog (on-demand model): if the daemon is down, that is the expected idle state — nothing to do. An idle daemon is backed up (if changed) and stopped; the MCP client restarts it on next use."

- [ ] **Step 2: Verify**

Read the header and the on-demand comment block (the `# 1. On-demand model` section); confirm they no longer contradict. Run `bash -n` and `shfmt -d -i 2` (comment-only change, but keep the habit).

- [ ] **Step 3: Commit**

```bash
git add scripts/watchdog-backup.sh
git commit -m "docs(scripts): correct watchdog header to describe on-demand model"
```
