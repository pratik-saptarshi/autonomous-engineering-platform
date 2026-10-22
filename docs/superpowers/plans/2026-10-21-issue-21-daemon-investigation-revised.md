# Daemon Shutdown Investigation (Issue #21) — Revised Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Supersedes:** `2026-10-19-issue-21-daemon-investigation.md`. That plan's H4 (watchdog health-check bug) is refuted by the idle-reaper evidence below; its log paths were wrong; Tasks 1–2 were never executed. This is a clean rewrite, not a patch.

**Goal:** Determine what causes the NeuroStrata daemon's unclean shutdowns (WAL left behind) and stop the evidence destruction that keeps the cause unknown.

**Architecture:** INVESTIGATION plan, not implementation. Phase A (Tasks 1–2): stop destroying evidence + instrument — safe, immediate, parallel. Phase B (Tasks 3–5): test the three revised hypotheses against collected data. Task 6 (fix) is intentionally deferred until a hypothesis is confirmed. Task 7 reports.

**Tech Stack:** bash, the deployed watchdog script, daemon logs, system memory stats.

**Spec:** https://github.com/pratik-saptarshi/autonomous-engineering-platform/issues/21

## What changed since the original plan (verified 2026-10-21)

- **The idle reaper explains the 2h-grid pattern.** Deployed 2026-10-19, it sends SIGTERM after 45 idle minutes (`~/workspace/neurostrata/bin/idle-reaper.sh`, every 15m). Reaper log confirms: `REAPED uptime=53m conns=0`. The watchdog then finds the daemon down and restarts it. This cycle — not a bug — is the "death" pattern.
- **H4 (watchdog health-check false positive) is refuted.** The daemon really is down when the watchdog checks; the reaper shut it down.
- **SIGTERM shutdowns are clean.** Daemon log shows `Received SIGTERM, shutting down.` → `Checkpoint complete. NeuroStrata Daemon stopped.` The reaper is not the unclean killer. (HTTP shutdowns — via the daemon's management endpoint, used by the watchdog's backup flow — are likewise clean: `Shutdown requested over HTTP.` → `Checkpoint complete.`)
- **WAL warnings persist anyway.** `~/.local/share/neurostrata/daemon.log` shows repeated `the last shutdown was not clean -- a 42 byte write-ahead log was left behind` at startup. Something besides the reaper kills the daemon without cleanup.
- **Correct log path:** `~/.local/share/neurostrata/daemon.log` (41KB, live). The original plan's `~/workspace/neurostrata/daemon.log` is stale (466 bytes, Oct 18).

## Revised hypotheses

- **H1 — OOM killer:** memory pressure triggers the kernel OOM killer (SIGKILL, no cleanup possible). Predicts: deaths correlate with high memory; no shutdown sequence in log.
- **H2 — Daemon crash:** neurostrata-mcp crashes spontaneously (panic, unhandled error). Predicts: crash trace in the preserved log before the WAL warning.
- **H3 — External SIGKILL:** something other than the reaper sends SIGKILL (a second reaper, container runtime, admin action). Predicts: abrupt log end with no shutdown sequence and no OOM evidence.

## Global Constraints

- Do NOT change the deployed watchdog's or reaper's behavior until the unclean killer is identified — they are the recovery mechanism.
- Do NOT run experiments that risk extended daemon downtime during working hours (weekdays 08:00–18:00 America/Chicago); schedule disruptive tests for off-hours or note them as such.
- Every diagnostic change must be reversible; document what was changed.
- Conventional Commits for any repo changes; author `Musebot-Astro <6238157+pratik-saptarshi@users.noreply.github.com>`.
- Exact-path `git add` only; never `git add -A` (repo has no `.gitignore`).

## Review Focus

- **Distinguish the two shutdown types.** Reaper SIGTERM → `Checkpoint complete` (clean, expected). The WAL warnings come from something else. Every diagnostic must separate "reaper cycle" events from "unclean death" events or the data is noise.
- **Evidence destruction is still the meta-bug.** The daemon log is not rotated; if the log fills or the VM is replaced, the crash evidence is gone. Task 1 is still the highest-leverage step.
- **The 42-byte WAL is constant.** Every warning reports exactly 42 bytes — this smells like a startup-time WAL, not accumulated writes. Note it; it may indicate the daemon dies during/just after startup, not under load.
- **Absence of evidence is not evidence.** If OOM sources are inaccessible (no dmesg), record H1 as unverifiable explicitly.
- **Correlation is not causation.** A WAL warning at startup N only proves the shutdown before N was unclean — match it to the nearest preceding shutdown event, not to the nearest watchdog run.

---

## File Structure

- Modify: `~/workspace/neurostrata/bin/watchdog-backup.sh` (DEPLOYED copy — log rotation only; operational change, not committed).
- Create: `~/workspace/neurostrata/bin/sample-daemon-rss.sh` + `~/workspace/neurostrata/daemon-rss.log` (new instrumentation).
- Modify (repo): `docs/limitation-analysis.md` §1(f) — only in Task 7, after findings exist. Repo checkout: `~/workspace/repos/autonomous-engineering-platform`.

---

### Task 1: Stop destroying evidence (log rotation, corrected paths)

**Files:**
- Modify: `~/workspace/neurostrata/bin/watchdog-backup.sh` (deployed copy)

**Interfaces:**
- Consumes: nothing (first task)
- Produces: daemon log preserved across restarts at its REAL path.

**Rationale:** The daemon log (`~/.local/share/neurostrata/daemon.log`) is the only crash evidence. It is never rotated. Without preservation, all diagnosis is speculation.

- [ ] **Step 1: Inspect how the deployed script handles the daemon log**

Run: `grep -n 'DAEMON_LOG\|daemon.log' ~/workspace/neurostrata/bin/watchdog-backup.sh`
Expected: find the log path variable (currently `DAEMON_LOG="$HOME/.local/share/neurostrata/daemon.log"`) and any truncation/redirect on restart.

- [ ] **Step 2: Add timestamped rotation before (re)start**

Before the daemon is (re)started, add (adapting to the script's actual variable names):
```bash
if [ -f "$DAEMON_LOG" ]; then
  mv "$DAEMON_LOG" "$DAEMON_LOG.$(date +%Y%m%d-%H%M%S)"
fi
# keep the last 10 rotations
ls -1t "$DAEMON_LOG".* 2>/dev/null | tail -n +11 | xargs -r rm -f
```

- [ ] **Step 3: Verify syntax and document**

Run: `bash -n ~/workspace/neurostrata/bin/watchdog-backup.sh && echo SYNTAX-OK`
Append to `~/workspace/neurostrata/OPERATIONS.md` (create it if absent): date, what changed, why, and that it is reversible by reverting the edit.

- [ ] **Step 4 (observation):** After the next daemon restart, `ls ~/.local/share/neurostrata/daemon.log.*` shows a rotated file.

---

### Task 2: Instrument resource usage (corrected paths)

**Files:**
- Create: `~/workspace/neurostrata/bin/sample-daemon-rss.sh`, `~/workspace/neurostrata/daemon-rss.log`

**Interfaces:**
- Consumes: nothing (parallel with Task 1)
- Produces: time-series of daemon RSS (Resident Set Size — actual RAM footprint in KB) + system memory.

- [ ] **Step 1: Create the sampler**

Write `~/workspace/neurostrata/bin/sample-daemon-rss.sh`:
```bash
#!/usr/bin/env bash
# Sample daemon RSS + system memory every 5 min. Appended to daemon-rss.log.
while true; do
  rss=$(ps -o rss= -C neurostrata-mcp 2>/dev/null | awk '{s+=$1} END {print s+0}')
  mem=$(free -m | awk '/^Mem:/ {print $3"/"$2}')
  echo "$(date '+%Y-%m-%d %H:%M:%S') rss_kb=${rss} mem_used_total=${mem} daemon_procs=$(pgrep -fc neurostrata-mcp || echo 0)"
  sleep 300
done
```

- [ ] **Step 2: Start it persistently**

Run: `chmod +x ~/workspace/neurostrata/bin/sample-daemon-rss.sh && nohup ~/workspace/neurostrata/bin/sample-daemon-rss.sh >> ~/workspace/neurostrata/daemon-rss.log 2>&1 &`
Verify within 30s: `tail -2 ~/workspace/neurostrata/daemon-rss.log` shows a fresh sample line.
Note: the sampler does not survive VM reboots (no @reboot cron). If the VM is replaced, restart it; Task 4 needs ≥24h of continuous samples.

- [ ] **Step 3 (observation):** After 24h, the log shows RSS trend for H1 correlation.

---

### Task 3: Identify the unclean killer (replaces old H4 test)

**Interfaces:**
- Consumes: Task 1 (preserved logs with WAL warnings intact)
- Produces: timestamped list of unclean deaths, separated from reaper-cycle events.

**Rationale:** The old Task 3 tested whether the watchdog's health check was wrong. It isn't — the reaper explains the pattern. The new question: which shutdowns leave WALs, and what precedes them?

- [ ] **Step 1: Enumerate every WAL warning with its startup context**

Run:
```bash
grep -n "not clean" ~/.local/share/neurostrata/daemon.log | cut -d: -f1 | while read ln; do
  echo "=== WAL at log line $ln ==="
  sed -n "$((ln-3)),$((ln+1))p" ~/.local/share/neurostrata/daemon.log
done
```
Record: how many WAL warnings, and for each, what the PREVIOUS shutdown looked like (SIGTERM+checkpoint = clean; HTTP+checkpoint = clean; abrupt end = unclean).

- [ ] **Step 2: Correlate unclean deaths with reaper and watchdog logs**

For each WAL warning's startup time, check:
```bash
# was the reaper active near the preceding shutdown?
grep -B5 -A5 '<timestamp>' ~/workspace/neurostrata/reaper.log
# what did the watchdog do?
grep -B5 -A5 '<timestamp>' ~/workspace/neurostrata/watchdog.log
```

- [ ] **Step 3 (observation — the decision point):**
  - If every WAL warning's preceding shutdown was a reaper SIGTERM → the daemon's SIGTERM handler has a race (H2 variant) → proceed to Task 5.
  - If WAL warnings follow abrupt log ends with no reaper/SIGTERM/HTTP shutdown → external SIGKILL or crash → proceed to Tasks 4–5.
  - If no WAL warnings appear in fresh post-Task-1 logs → the unclean killer may be gone (historical only) → record and monitor.

---

### Task 4: Test H1 — OOM killer

**Interfaces:**
- Consumes: Task 2's RSS log + Task 3's unclean-death timestamps (need ≥1 unclean death captured)
- Produces: verdict on H1.

- [ ] **Step 1: Try every available OOM-evidence source**

Run each; record which are accessible:
```bash
dmesg 2>&1 | grep -i oom | tail -5
journalctl -k 2>&1 | grep -i 'killed process' | tail -5
grep -i 'out of memory' /var/log/syslog 2>&1 | tail -5
grep -i 'killed process' /var/log/kern.log 2>&1 | tail -5
```

- [ ] **Step 2: Correlate unclean deaths (NOT reaper cycles) with memory pressure**

For each unclean-death timestamp from Task 3, pull the nearest RSS-log samples (±15 min).

- [ ] **Step 3 (observation):**
  - OOM-killer lines naming neurostrata-mcp → **H1 CONFIRMED**.
  - Unclean deaths consistently occur at >90% memory with growing RSS → H1 supported.
  - Unclean deaths occur at moderate memory (<75%) with flat RSS, no OOM lines → **H1 refuted**; proceed to Task 5.
  - No OOM sources accessible AND no correlation → H1 **unverifiable** — record explicitly.

---

### Task 5: Test H2/H3 — crash vs external SIGKILL

**Interfaces:**
- Consumes: Task 1's preserved logs + Task 3's unclean-death list
- Produces: verdict on H2 (crash) vs H3 (external SIGKILL).

- [ ] **Step 1: Examine the preserved pre-shutdown log for each unclean death**

For the most recent unclean death, pull the 30 lines before the WAL-warning startup:
Look for: Rust panic traces, `ERROR` lines, stack traces, or abrupt end (no shutdown sequence at all).

- [ ] **Step 2: Audit for SIGKILL sources**

Run:
```bash
# any other reaper-like automation?
ps aux | grep -iE 'reaper|monit|supervisord|oom' | grep -v grep
# what else runs on the 2h grid or near unclean-death times?
ls ~/workspace/cron.d/hourly/ ~/workspace/system-cron.d/hourly/ 2>/dev/null
```

- [ ] **Step 3 (observation):**
  - Panic/error trace before the WAL warning → **H2 CONFIRMED** (file the trace; next step is upstream report or version pin).
  - Abrupt end + a correlated external event → **H3 supported** (identify and address the killer).
  - Abrupt end + nothing external + no OOM → inconclusive; note the constant 42-byte WAL size as a lead (dies at/just after startup?).

---

### Task 6: Fix and harden (only after a hypothesis is confirmed)

**Interfaces:**
- Consumes: verdict from Tasks 3–5
- Produces: targeted fix — NOT a speculative rewrite.

Do not write this task's steps in advance. The fix depends entirely on the confirmed cause:
- H1 confirmed → reduce memory footprint, add early-warning restart, or document the constraint.
- H2 confirmed → pin a fixed upstream version or file the upstream issue with the preserved trace.
- H3 confirmed → remove/disable the killer or guard the daemon against it.

- [ ] **Step 1: Implement the targeted fix** (defined after diagnosis)
- [ ] **Step 2: Observe for 48h** — zero WAL warnings in fresh daemon logs
- [ ] **Step 3: Revert temporary instrumentation** if any remains

---

### Task 7: Report and update docs

**Files:**
- Modify (repo): `docs/limitation-analysis.md` §1(f). Repo checkout: `~/workspace/repos/autonomous-engineering-platform`.

**Interfaces:**
- Consumes: findings from Tasks 3–6
- Produces: issue #21 updated; docs reflect reality.

- [ ] **Step 1: Update limitation-analysis.md §1(f)**

On a branch `docs/issue-21-findings` (Conventional Commits as `Musebot-Astro <6238157+pratik-saptarshi@users.noreply.github.com>`): record the reaper explanation for the 2h-grid pattern (H4 refuted), which hypothesis was confirmed for the WAL warnings (or that the cause remains open with what was ruled out), and what was changed. Open a PR; do not merge (Pratik decides).

- [ ] **Step 2: Post a summary comment on issue #21** with the verdict and link the doc update.

- [ ] **Step 3: Stop the RSS sampler** (or keep it for ongoing monitoring — decide explicitly).

---

## Self-Review

**1. Spec coverage:** Issue #21 asks for root-cause diagnosis of silent deaths. This revision accounts for the reaper (the 2h-grid explanation), refocuses on the WAL warnings (the actual unclean-death evidence), corrects all log paths, and preserves the evidence-first sequencing.

**2. Step scan:** Each step is one action with a checkable observation. Task 3 is the new load-bearing diagnostic (separating reaper cycles from unclean deaths). Task 6 remains deferred by design.

**3. Review Focus:** The five points cover the critical distinctions: reaper-cycle vs unclean-death separation, evidence preservation priority, the 42-byte WAL anomaly, explicit unverifiability, and correct temporal correlation.

**4. Proportion:** Shorter than the original — the refuted H4 test is replaced by a leaner correlation task, and the redundant instrumentation is consolidated.
