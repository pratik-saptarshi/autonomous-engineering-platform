# Watchdog Deployment Process Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a documented, verifiable deployment process for `scripts/watchdog-backup.sh` so repo fixes reach the production `neurostrata-watchdog` cron, and perform the first deployment under the new process.

**Architecture:** Docs-first, then one validated deployment. Task 1 documents the deploy procedure in `docs/operations.md`; Task 2 creates `docs/process/watchdog-deployments.md` as the append-only deployment log (date + git SHA + sha256sum per deploy, backfilled with the current production state); Task 3 executes the first deployment — the issue-#15-fixed script — following the documented steps, which validates the process end to end.

**Tech Stack:** Markdown docs, bash, sha256sum.

**Spec:** GitHub issue #18 (pratik-saptarshi/autonomous-engineering-platform): repo `scripts/watchdog-backup.sh` and deployed `~/workspace/neurostrata/bin/watchdog-backup.sh` differ (verified via `diff -q`); no deployment record exists; no documented deploy step. Suggested fix: document a deploy step in operations.md, record checksums, and verify cron pickup.

## Global Constraints

- Conventional Commits for every commit; author `Musebot-Astro <6238157+pratik-saptarshi@users.noreply.github.com>`.
- Do not break the running `neurostrata-watchdog` cron: serialize the deploy with watchdog runs by HOLDING the flock at `~/workspace/neurostrata/.watchdog.lock` across the backup + deploy steps (a check-then-copy races the 2h cron: the watchdog can start between the check and the overwrite). Deploy via atomic rename (temp file + `mv`), never in-place `cp` — `bash script.sh` reads incrementally, so an in-place overwrite mid-run executes mixed content, while rename lets a concurrent reader keep the old inode.
- Preserve file ownership and mode on deploy (currently `root:nogroup`, `770` — verified via `ls -la`).
- Never deploy an unverified script: it must pass `bash -n`, shellcheck, and `shfmt -d -i 2` first.
- **Dependency:** Task 3 requires issue #15's fix merged to the repo first. Tasks 1 and 2 are independent of each other and of #15 — they may run in parallel.
- Exact-path `git add` only; never `git add -A` (repo has no `.gitignore`).
- `docs/process/` does not exist yet; creating it follows the repo's scrubbing-public-tree convention (process docs live under `docs/process/`).

## Review Focus

- **Deploying while a watchdog run is in progress** — `bash script.sh` reads the file incrementally during execution, so overwriting it mid-run risks executing mixed content, and a check-then-copy races the 2h cron (the watchdog can acquire the lock after the check but before the copy). The procedure must HOLD the flock at `~/workspace/neurostrata/.watchdog.lock` across the entire backup + deploy (blocking acquire with timeout — if a run is active, wait for it; while held, a cron-fired watchdog exits cleanly via its own `flock -n` path) and deploy via atomic rename (temp file in the same dir + `mv`), never in-place `cp`. The Task 1 doc pins this as mandatory.
- **Rollback** — a bad deploy must be revertible. The procedure must back up the current deployed file (timestamped copy) before overwriting.
- **Checksum record atomicity** — the deployment log entry is part of the deploy, not an afterthought; Task 3 writes it in the same task as the file replacement.
- **Permission preservation** — the deployed file is `root:nogroup` mode `770`; the procedure sets owner/mode explicitly rather than inheriting from the copy.
- **Cron pickup verification** — confirm the cron body still references the file path and that the next run executes the new script (check `watchdog.log` for the new behavior after the next scheduled run).

---

### Task 1: Document the deploy procedure in docs/operations.md

**Files:**
- Modify: `docs/operations.md` (add a "Deploying the watchdog" subsection under the existing "Watchdog and backups" section)

**Interfaces:**
- Consumes: none
- Produces: documented deploy procedure (pre-deploy checks, copy + permissions, checksum record, post-deploy verification, rollback)

- [ ] **Step 1: Read the current "Watchdog and backups" section**

Read `docs/operations.md`, find the "Watchdog and backups" section, and identify the insertion point (end of that section, before the next `##` heading).

- [ ] **Step 2: Write the "Deploying the watchdog" subsection**

Add the subsection covering, in order:
1. **Preconditions:** the script change is merged; CI (shell-lint) is green on it; issue #15's fail-fast guard is present (so a bad path can never silently deploy).
1. **Serialize with the watchdog:** acquire the flock at `~/workspace/neurostrata/.watchdog.lock` and HOLD it across steps 2–3. Do not check-then-release — the check races the 2h cron. Blocking acquire with a 10-minute timeout (a normal watchdog run finishes in well under a minute):
```bash
exec 8>"$HOME/workspace/neurostrata/.watchdog.lock"
flock --timeout 600 8 || { echo "FATAL: watchdog lock not acquired within 10 min (a run may be stuck — investigate with pgrep -f watchdog-backup.sh)" >&2; exit 1; }
# fd 8 stays open through steps 2-3; the lock releases when this shell exits.
# While held, a cron-fired watchdog exits cleanly via its own `flock -n` path.
```
2. **Back up the live file (under the held lock):** `cp ~/workspace/neurostrata/bin/watchdog-backup.sh ~/workspace/neurostrata/bin/watchdog-backup.sh.bak-$(date +%Y%m%d)` (rollback copy).
3. **Deploy atomically (under the held lock):** copy to a temp file in the SAME directory, set owner/mode on the temp file, verify syntax, then rename over the target — never `cp` over the live path in place:
```bash
cp <repo>/scripts/watchdog-backup.sh ~/workspace/neurostrata/bin/watchdog-backup.sh.new
chown root:nogroup ~/workspace/neurostrata/bin/watchdog-backup.sh.new
chmod 770 ~/workspace/neurostrata/bin/watchdog-backup.sh.new
bash -n ~/workspace/neurostrata/bin/watchdog-backup.sh.new && echo "syntax OK"
mv ~/workspace/neurostrata/bin/watchdog-backup.sh.new ~/workspace/neurostrata/bin/watchdog-backup.sh
sha256sum ~/workspace/neurostrata/bin/watchdog-backup.sh   # record for the log entry
```
(`mv` within one filesystem is atomic: a concurrent reader keeps the old inode instead of executing mixed content.)
5. **Verify cron pickup:** the `neurostrata-watchdog` cron runs `bash ~/workspace/neurostrata/bin/watchdog-backup.sh` each cycle, so no cron change is needed; confirm the next run's `watchdog.log` lines reflect the new script (e.g. the on-demand log messages).
6. **Record:** append an entry to `docs/process/watchdog-deployments.md` (date, repo git SHA, sha256sum, notes).
7. **Rollback:** if the next run misbehaves, restore the `.bak-<date>` copy, re-verify with `bash -n`, and log the rollback in the deployments file.

- [ ] **Step 3: Verify the docs change**

Run the repo's markdownlint on the file (must pass under `.markdownlint.yaml`); confirm no dangling references (every path mentioned exists or is marked as an example).

- [ ] **Step 4: Commit**

```bash
git add docs/operations.md
git commit -m "docs(operations): document watchdog deployment procedure"
```

---

### Task 2: Create the deployment log with the current production baseline

**Files:**
- Create: `docs/process/watchdog-deployments.md`

**Interfaces:**
- Consumes: none (independent of Task 1)
- Produces: append-only deployment log, backfilled with the current production state

- [ ] **Step 1: Record the current deployed checksum**

Run: `sha256sum ~/workspace/neurostrata/bin/watchdog-backup.sh` and `ls -la ~/workspace/neurostrata/bin/watchdog-backup.sh` (capture size, mtime, owner, mode). Also run `git -C ~/workspace/worktrees/aep-ci-pr log -1 --format=%H -- scripts/watchdog-backup.sh` to note the repo SHA the deployed file most recently corresponds to (it won't match exactly — the files differ — so mark it "pre-process baseline, no exact repo SHA").

- [ ] **Step 2: Create `docs/process/watchdog-deployments.md`**

Format (append-only, newest at top or bottom — pick one and document the choice):

```markdown
# watchdog-backup.sh deployment log

Append-only record of what is live at ~/workspace/neurostrata/bin/watchdog-backup.sh.
Each entry: date, repo git SHA deployed, sha256sum of the deployed file, deployed-by, notes.

## 2026-10-17 (baseline, pre-process)
- Deployed file sha256: <value from Step 1>
- Repo SHA: n/a (predates this log; file differs from repo — always-on model)
- Notes: baseline entry created with the deployment process (issue #18).
```

- [ ] **Step 3: Verify the record**

Re-run `sha256sum ~/workspace/neurostrata/bin/watchdog-backup.sh` and confirm the value in the file matches exactly (copy-paste, no retyping).

- [ ] **Step 4: Commit**

```bash
git add docs/process/watchdog-deployments.md
git commit -m "docs(process): add watchdog deployment log with production baseline"
```

---

### Task 3: Perform the first deployment under the new process (requires #15 merged)

**Files:**
- Modify (live environment, NOT the repo): `~/workspace/neurostrata/bin/watchdog-backup.sh`
- Modify: `docs/process/watchdog-deployments.md` (append the new entry)

**Interfaces:**
- Consumes: issue #15's fixed `scripts/watchdog-backup.sh` (merged to the repo); Task 1's procedure; Task 2's log
- Produces: deployed fixed script; new log entry; verified cron pickup

- [ ] **Step 1: Verify preconditions and acquire the lock**

Confirm: issue #15's fix is merged (repo `scripts/watchdog-backup.sh` contains the fail-fast guard — `grep -q 'FATAL: neurostrata-mcp' scripts/watchdog-backup.sh`); CI is green on the merge commit. Then acquire the watchdog lock and hold it for Steps 2–3 (see Task 1, procedure step 2 — blocking `flock --timeout 600`; this serializes with any in-progress run instead of racing it).

- [ ] **Step 2: Back up the live file (under the held lock)**

Run: `cp ~/workspace/neurostrata/bin/watchdog-backup.sh ~/workspace/neurostrata/bin/watchdog-backup.sh.bak-$(date +%Y%m%d)`
Verify: `ls -la ~/workspace/neurostrata/bin/watchdog-backup.sh.bak-*` shows the new backup.

- [ ] **Step 3: Deploy the fixed script atomically (under the held lock)**

Run:
```bash
cp ~/workspace/worktrees/aep-ci-pr/scripts/watchdog-backup.sh ~/workspace/neurostrata/bin/watchdog-backup.sh.new
chown root:nogroup ~/workspace/neurostrata/bin/watchdog-backup.sh.new
chmod 770 ~/workspace/neurostrata/bin/watchdog-backup.sh.new
bash -n ~/workspace/neurostrata/bin/watchdog-backup.sh.new && echo "syntax OK"
mv ~/workspace/neurostrata/bin/watchdog-backup.sh.new ~/workspace/neurostrata/bin/watchdog-backup.sh
sha256sum ~/workspace/neurostrata/bin/watchdog-backup.sh
```
Expected: syntax OK; capture the sha256sum for the log entry. (Note: use the repo path that reflects the merged #15 fix — if the worktree branch has moved on, use the main checkout at `~/workspace/repos/autonomous-engineering-platform`. The `mv` is the atomic publish; a concurrent reader keeps the old inode.)

- [ ] **Step 4: Verify the deployed file matches the repo script**

Run: `diff ~/workspace/worktrees/aep-ci-pr/scripts/watchdog-backup.sh ~/workspace/neurostrata/bin/watchdog-backup.sh` (adjust repo path as in Step 3)
Expected: no output (identical).

- [ ] **Step 5: Verify cron pickup**

Confirm the `neurostrata-watchdog` cron body still invokes `bash ~/workspace/neurostrata/bin/watchdog-backup.sh` (no cron change needed). After the next scheduled run (≤2h) — or a manual `cron.run` of `neurostrata-watchdog` — check `~/workspace/neurostrata/watchdog.log` for the new script's log lines (on-demand model messages) and confirm exit 0.

- [ ] **Step 6: Append the deployment log entry and commit**

Add to `docs/process/watchdog-deployments.md`:
```markdown
## <date> — issue #15 fix deployed
- Deployed file sha256: <value from Step 3>
- Repo SHA: <merge commit SHA of the #15 fix>
- Notes: first deployment under the documented process; on-demand model now live.
```
Then:
```bash
git add docs/process/watchdog-deployments.md
git commit -m "docs(process): record watchdog deployment of issue-15 fix"
```
