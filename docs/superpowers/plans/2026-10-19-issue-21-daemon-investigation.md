# Daemon Death Investigation (Issue #21) Plan

> **SUPERSEDED** by `2026-10-21-issue-21-daemon-investigation-revised.md` (2026-10-21). The idle reaper (deployed 10-19) refuted H4; log paths were wrong; Tasks 1–2 never executed. Do not use this version.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Determine the root cause of the NeuroStrata daemon's silent deaths and fix the evidence-destruction that keeps the cause unknown.

**Architecture:** This is an INVESTIGATION plan, not an implementation plan. Tasks are diagnostic steps; "tests" are observations that confirm or refute hypotheses. The plan runs in two phases: (A) stop destroying evidence + instrument (Tasks 1-2, safe, immediate), then (B) test the four hypotheses against collected data (Tasks 3-6). Task 7 reports and updates the docs.

**Tech Stack:** bash, the deployed watchdog script (`~/workspace/neurostrata/bin/watchdog-backup.sh`), daemon logs, system memory stats.

**Spec:** https://github.com/pratik-saptarshi/autonomous-engineering-platform/issues/21

## Background evidence (verified 2026-10-19)

- `~/workspace/neurostrata/watchdog.log`: `daemon down — restarting directly` at 06:01, 08:01, 10:01, 12:01 UTC on 2026-10-19 — **every** 2h watchdog run finds it down.
- `~/workspace/neurostrata/daemon.log`: `WARNING: the last shutdown was not clean -- a 42 byte write-ahead log was left behind` — unclean shutdown (crash or kill, not clean exit). (WAL = write-ahead log; its presence proves the daemon didn't shut down cleanly.)
- 2026-10-18: 3 deaths observed (before 09:01, ~12:35, ~17:14 CDT); the 12:35 and 17:14 deaths were off the cron grid (manual observations).
- Memory at one observation: 6480/7935 MB used (82%) — tight but not critical.
- `dmesg` not accessible in this environment (OOM-killer evidence may be unobtainable directly).

## Hypotheses

- **H1 — OOM killer:** memory pressure (82% observed + 547MB model) triggers the kernel OOM killer. Predicts: deaths correlate with high memory usage; no clean shutdown.
- **H2 — Daemon bug:** neurostrata-mcp 1.9.0 crashes on its own (panic, unhandled error). Predicts: crash trace in stderr/log before death; deaths independent of cron schedule.
- **H3 — External killer:** something else SIGTERMs/SIGKILLs it (another cron, a process reaper, VM-level action). Predicts: deaths correlate with a specific external event; clean-ish signal handling if SIGTERM.
- **H4 — Watchdog false positive / watchdog-is-the-killer:** the health check misreports a live daemon as down, then the watchdog kills the healthy daemon during "cleanup." Predicts: daemon actually alive just before the watchdog's check; deaths align EXACTLY to watchdog runs (as observed on 10-19); WAL "not clean" caused by the watchdog's own kill.

## Global Constraints
- Do NOT change the deployed watchdog's restart behavior until the cause is known — it is the only thing keeping the daemon up.
- Do NOT run experiments that risk extended daemon downtime during the user's working hours (weekdays 08:00–18:00 America/Chicago); schedule disruptive tests for off-hours or note them as such.
- Every diagnostic change must be reversible; document what was changed.
- Conventional Commits for any repo changes.

## Review Focus
- **The 10-19 pattern (deaths exactly on the 2h grid) vs the 10-18 pattern (two deaths off-grid)** — H4 explains the first but not the second. Both patterns must be accounted for; a single-hypothesis conclusion that ignores one is wrong.
- **Evidence destruction is the meta-bug:** every restart truncates the log that would show the crash. Task 1 is the highest-leverage step — without it, Tasks 3-6 are guessing.
- **The deployed watchdog is the OLD version** (`~/workspace/neurostrata/bin/watchdog-backup.sh`, always-on model) — investigate THAT script's health-check logic, not the repo's newer on-demand version.
- **Absence of evidence is not evidence:** if OOM can't be checked (no dmesg), say so explicitly rather than silently dropping H1.
- **Correlation is not causation:** a death at :01 could be the watchdog killing it OR the daemon dying on its own just before the check — Task 4's independent pre-check is what separates them.

---

## File Structure

- Modify: `~/workspace/neurostrata/bin/watchdog-backup.sh` (DEPLOYED copy — log rotation instead of truncation; instrument health check). Note: this is outside the repo; changes here are operational, not committed.
- Create: `~/workspace/neurostrata/daemon-rss.log` (new instrumentation log — RSS/memory samples).
- Modify (repo): `docs/limitation-analysis.md` §1(f) — only in Task 7, after findings exist.
- Modify (repo): `scripts/watchdog-backup.sh` — only if Task 1's log-rotation fix should also land in the repo version (decide in Task 7).

---

### Task 1: Stop destroying evidence (log rotation)

**Files:**
- Modify: `~/workspace/neurostrata/bin/watchdog-backup.sh` (deployed copy)

**Interfaces:**
- Consumes: nothing (first task)
- Produces: daemon.log preserved across restarts — every later task depends on this.

**Rationale:** Every restart currently truncates `~/workspace/neurostrata/daemon.log`, destroying the crash evidence. Without this fix, all subsequent diagnosis is speculation.

- [ ] **Step 1: Inspect how the deployed script handles the log**

Run: `grep -n 'daemon.log' ~/workspace/neurostrata/bin/watchdog-backup.sh`
Expected: find the line(s) that truncate/redirect the log on restart (likely `> "$LOG"` or `nohup ... > daemon.log`).

- [ ] **Step 2: Change truncation to timestamped rotation**

Before the daemon is (re)started, add:
```bash
if [ -f ~/workspace/neurostrata/daemon.log ]; then
  mv ~/workspace/neurostrata/daemon.log ~/workspace/neurostrata/daemon.log.$(date +%Y%m%d-%H%M%S)
fi
# keep the last 10 rotations
ls -1t ~/workspace/neurostrata/daemon.log.* 2>/dev/null | tail -n +11 | xargs -r rm -f
```
(Adapt to the script's actual variable names for the log path.)

- [ ] **Step 3: Verify the change is syntactically valid and document it**

Run: `bash -n ~/workspace/neurostrata/bin/watchdog-backup.sh && echo SYNTAX-OK`
Then append a line to `~/workspace/neurostrata/OPERATIONS.md` (or the local ops notes) recording: date, what changed, why, and that it's reversible by reverting the edit.

- [ ] **Step 4 (observation):** The next daemon restart preserves the pre-restart log. Confirm by listing `~/workspace/neurostrata/daemon.log.*` after the next watchdog run — a rotated file must exist.

---

### Task 2: Instrument resource usage

**Files:**
- Create: `~/workspace/neurostrata/daemon-rss.log` (via a lightweight sampler; RSS = Resident Set Size, the daemon's actual RAM footprint)

**Interfaces:**
- Consumes: Task 1 (evidence preservation in place)
- Produces: time-series of daemon RSS + system memory, correlatable with death times.

- [ ] **Step 1: Create the sampler**

Write `~/workspace/neurostrata/bin/sample-daemon-rss.sh`:
```bash
#!/usr/bin/env bash
# Sample daemon RSS + system memory every 5 min. Appended to daemon-rss.log.
# Cheap; safe to leave running.
while true; do
  rss=$(ps -o rss= -C neurostrata-mcp 2>/dev/null | awk '{s+=$1} END {print s+0}')
  mem=$(free -m | awk '/^Mem:/ {print $3"/"$2}')
  echo "$(date '+%Y-%m-%d %H:%M:%S') rss_kb=${rss} mem_used_total=${mem} daemon_procs=$(pgrep -fc neurostrata-mcp || echo 0)"
  sleep 300
done
```

- [ ] **Step 2: Start it (persistent)**

Run: `nohup ~/workspace/neurostrata/bin/sample-daemon-rss.sh >> ~/workspace/neurostrata/daemon-rss.log 2>&1 &`
Verify: `tail -2 ~/workspace/neurostrata/daemon-rss.log` shows a fresh sample line within 30s.

- [ ] **Step 3 (observation):** After 24h, the log shows RSS trend. **H1 test:** if RSS grows unboundedly before a death → memory leak supports H1/H2. If RSS is flat and deaths still occur → weakens H1.

---

### Task 3: Test H4 — is the daemon really dead when the watchdog says so?

**Files:**
- Modify: `~/workspace/neurostrata/bin/watchdog-backup.sh` (deployed copy — temporary instrumentation, reverted after)

**Interfaces:**
- Consumes: Tasks 1-2 (evidence + instrumentation running)
- Produces: verdict on H4 (false positive vs real death).

**Rationale:** The 10-19 deaths align exactly to watchdog runs. The distinguishing test: independently verify daemon liveness in the seconds BEFORE the watchdog's health check.

- [ ] **Step 1: Instrument the health check to log raw evidence**

In the deployed script's health-check function, before it returns "down", add logging of:
```bash
echo "$(date): health-check raw: pgrep_count=$(pgrep -fc 'neurostrata-mcp daemon' || echo 0), port_34343=$(ss -ltn 2>/dev/null | grep -c 127.0.0.1:34343 || echo 0)" >> ~/workspace/neurostrata/watchdog.log
```
(Adapt to the script's actual check; the point is to record process existence AND port state at decision time.)

- [ ] **Step 2: Wait for 2 watchdog cycles (4h), then read the evidence**

Run: `grep 'health-check raw' ~/workspace/neurostrata/watchdog.log | tail -4`

- [ ] **Step 3 (observation — the decision point):**
  - If `pgrep_count=0` AND `port_34343=0` at "down" verdicts → daemon genuinely dead → **H4 refuted**; proceed to H1/H2/H3.
  - If `pgrep_count>=1` OR `port_34343=1` at any "down" verdict → **H4 CONFIRMED** (health check is wrong and/or the watchdog kills live daemons) → skip to Task 6 with this finding.

- [ ] **Step 4: Revert the temporary instrumentation** (keep the Task 1 log rotation).

---

### Task 4: Test H1 — OOM killer

**Interfaces:**
- Consumes: Task 2's RSS log (needs ≥1 death captured)
- Produces: verdict on H1.

- [ ] **Step 1: Try every available OOM-evidence source**

Run each; record which are accessible:
```bash
dmesg 2>&1 | grep -i oom | tail -5
journalctl -k 2>&1 | grep -i 'killed process' | tail -5
grep -i 'out of memory' /var/log/syslog 2>&1 | tail -5
grep -i 'killed process' /var/log/kern.log 2>&1 | tail -5
```

- [ ] **Step 2: Correlate deaths with memory pressure**

For each death timestamp in watchdog.log, pull the nearest RSS-log samples:
```bash
grep 'daemon down' ~/workspace/neurostrata/watchdog.log | tail -3
# for each timestamp T, show daemon-rss.log lines within ±15 min of T
```

- [ ] **Step 3 (observation):**
  - OOM-killer lines naming neurostrata-mcp → **H1 CONFIRMED**.
  - Deaths consistently occur at >90% memory usage with growing RSS → H1 supported (mitigate: reduce footprint, add swap, or schedule restarts).
  - Deaths occur at moderate memory (<75%) with flat RSS, and no OOM lines → **H1 refuted**; proceed to H2/H3.
  - No OOM sources accessible AND no correlation → H1 **unverifiable** — record explicitly, do not silently drop.

---

### Task 5: Test H2/H3 — crash vs external killer

**Interfaces:**
- Consumes: Task 1's preserved logs (need ≥1 post-fix death with intact pre-restart log)
- Produces: verdict on H2 (bug) vs H3 (external killer).

- [ ] **Step 1: Examine the preserved pre-restart log after the next death**

Run: `ls -1t ~/workspace/neurostrata/daemon.log.* | head -1 | xargs tail -30`
Look for: Rust panic traces, `ERROR` lines, `invalid peer certificate`, stack traces, or abrupt end (no shutdown sequence).

- [ ] **Step 2: Audit for external killers**

Run:
```bash
# what's scheduled around :01 (when deaths are found)?
grep -rl '01' ~/workspace/cron.d/hourly/ ~/workspace/system-cron.d/hourly/ 2>/dev/null
# any process-reaper or OOM-adjacent tooling?
ps aux | grep -iE 'oom|reaper|supervisord|monit' | grep -v grep
```

- [ ] **Step 3 (observation):**
  - Panic/error trace in the preserved log → **H2 CONFIRMED** (file the trace; next step is upstream report or version change).
  - Abrupt log end + a correlated external event (another job at :01, a reaper) → **H3 supported** (identify and address the killer).
  - Abrupt log end + nothing external → H2/H3 inconclusive; escalate (binary-level debugging or upstream issue).

---

### Task 6: Fix and harden (only after a hypothesis is confirmed)

**Interfaces:**
- Consumes: verdict from Tasks 3-5
- Produces: targeted fix — NOT a speculative rewrite.

Do not write this task's steps in advance. The fix depends entirely on the confirmed cause:
- H1 confirmed → reduce memory footprint, add early-warning restart, or document the constraint.
- H2 confirmed → pin a fixed upstream version or file the upstream issue with the preserved trace.
- H3 confirmed → remove/disable the killer or guard the daemon against it.
- H4 confirmed → fix the health check; consider whether the watchdog's kill-on-"down" is safe.

- [ ] **Step 1: Implement the targeted fix** (defined after diagnosis)
- [ ] **Step 2: Observe for 48h** — zero unclean deaths in watchdog.log + daemon-rss.log
- [ ] **Step 3: Revert temporary instrumentation** from Task 3 if still present

---

### Task 7: Report and update docs

**Files:**
- Modify (repo): `docs/limitation-analysis.md` §1(f) — repo checkout at `~/workspace/repos/autonomous-engineering-platform` (or the active PR worktree; use whichever is on `main`)
- Modify (repo): `scripts/watchdog-backup.sh` — only if Task 1's rotation should land here too

**Interfaces:**
- Consumes: findings from Tasks 3-6
- Produces: issue #21 updated; docs reflect reality.

- [ ] **Step 1: Update limitation-analysis.md §1(f)**

Record: the 2026-10-18/19 death incidents, which hypothesis was confirmed (or that the cause remains open with what was ruled out), and what was changed. If the cause is still open, update the "mitigated" label to reflect that the watchdog masks but does not fix.

- [ ] **Step 2: Decide on the repo's watchdog script**

If Task 1's log-rotation is valuable generally, port it to the repo's `scripts/watchdog-backup.sh` as a separate commit.

- [ ] **Step 3: Post a summary comment on issue #21** with the verdict and link the doc update.

- [ ] **Step 4: Stop the RSS sampler** (or keep it if the team wants ongoing monitoring — decide explicitly).

---

## Self-Review

**1. Spec coverage:** Issue #21 asks for: preserve pre-restart log (Task 1), capture diagnostics (Tasks 2-5), investigate the binary (Task 5), update §1(f) (Task 7). All covered. The issue's "mitigated label is misleading" concern is addressed in Task 7.

**2. Step scan:** Each step is one action with a checkable observation. Task 6 is intentionally deferred — writing fix steps before diagnosis would be speculation, which is exactly the failure mode this plan exists to avoid.

**3. Type consistency:** N/A (diagnostic plan; no cross-task interfaces beyond evidence files, which are named explicitly).

**4. Review Focus:** The header's five points are the investigation's load-bearing reasoning: the two death patterns must both be explained (H4 vs H2), evidence destruction is fixed first, the deployed (old) script is the investigation target, unverifiable H1 must be explicit, and Task 3's pre-check is what separates correlation from causation.

**5. Proportion:** The plan is long because the diagnosis has four hypotheses and the evidence pipeline (Tasks 1-2) must be built before any of them can be tested. No step is speculative treatment.
