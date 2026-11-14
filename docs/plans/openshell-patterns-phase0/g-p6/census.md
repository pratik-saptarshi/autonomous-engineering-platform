# G-P6 — Launch-path census: findings

Gate (plan §2, pre-registered): enumerate every autonomous launch path and
mark which invoke `scripts/boot-gate.sh`. **Pass:** any launch path does not
invoke the gate. **Kill:** coverage is already 100%.

## Method (complete, not sampled)

- Scheduler enumeration via `cron.list` (including disabled) — 52 schedules —
  cross-checked against the on-disk definition corpus
  (`~/workspace/cron.d`, `~/workspace/goals/*/crons`,
  `~/workspace/system-cron.d`: 61 files; the file corpus is a superset that
  includes expired one-off definitions).
- `hooks.list` (including disabled) — 1 hook.
- Content check: `grep` for `boot-gate` across every definition file, the
  hook script, and every launcher mechanism in the AEP repo and the live
  runtime worktree (`scripts/lane-coord.sh`, `scripts/orch/*`,
  `scripts/scan-gate.sh`, `ops/bin/*`, `~/workspace/neurostrata/bin/*`,
  live `~/workspace/custom-skills`).

## Result: invocation coverage is 0%

**No autonomous launch path invokes `boot-gate.sh`.** Zero of 61 cron
definition files mention it; the one hook does not call it; no launcher
script calls it. The only executions of `boot-gate.sh` anywhere in the
environment are its own `--self-test` and the fixture copies inside
`lane-coord.sh`'s self-test harness. `boot-gate.sh`'s own header concedes
this ("Whether and when anything invokes boot-gate.sh is issue #17's
unexecuted scope") — the census now executes that scope.

### Class 1 — scheduler task crons (25 user/goal schedules; all: NO)

Enabled: aep-vendored-weekly-sweep, amc-saturday-planner,
amc-saturday-planner-wed, austin-job-sweep, book-deals-tracker-daily-refresh,
dap-build-check-3h, dap-nightly-build, dap-roadmap-reconcile,
fork-upstream-sync-daily, ghg-drift-check, macbook-battery-weekly-checkin,
neurostrata-export, neurostrata-idle-reaper, neurostrata-watchdog,
ns-backlog-refinement-loop, orch-demand-accrual, reboot-backup-twice-weekly,
skill-sync-daily, vm-restart-tracker, infimobile-renewal-reshop-2027
(runonce, 2027). Disabled: aep-revendor-neurostrata-1766850.
None of their bodies invoke or reference the gate; each run starts work
with no preflight of any kind.

### Class 2 — system crons (27 schedules; all: NO)

deterministic-doctor, profile-image, feed-pulse-00 … feed-pulse-23, and the
heartbeat (mode=heartbeat). Runtime-managed; listed for completeness — they
start agent work on schedule and none invoke the gate.

### Class 3 — hooks (1; NO)

dap-pr182-watch (disabled): its polling script wakes a worker agent; it
does not invoke the gate.

### Class 4 — lane-coord.sh claims (NO, with a partial substitute)

`scripts/lane-coord.sh` (repo and live runtime copy) never invokes
boot-gate.sh — its five mentions are a comment ("boot-gate idiom") and
self-test fixtures. Lane claims do perform their **own** narrower
preflight: the launch policy (`scripts/policy.data`) is loaded, validated,
and hash-bound to the committed blob at claim time. That covers
boot-gate's *policy* check only — not its binaries, daemon, guard, or
gh-auth checks — and only for work launched through a lane claim.

### Class 5 — AEP orchestrator, scripts/orch (NO)

The orchestration engine (claims/engine/workflow) contains no boot-gate
reference; the orch-demand-accrual cron that drives it is in Class 1.

### Class 6 — daemon lifecycle scripts (NO)

`watchdog-backup.sh` and `idle-reaper.sh` (repo `ops/bin/` and the live
`~/workspace/neurostrata/bin/` copies) start/stop/reap the NeuroStrata
daemon without invoking the gate. (Noted as daemon lifecycle rather than
agent-work launches; included so the census is complete. Per standing
rules, nothing in this census contacted the daemon.)

## Verdict: **PASS** — decisively

Coverage is not partial; it is zero. Every autonomous launch path class
bypasses the gate, so the Phase 2b wiring build earns its place under the
plan's criterion. Two facts the build should inherit from this census:
(1) the gap is total, so wiring design — not gap-hunting — is the work;
(2) lane claims already carry a policy-binding preflight of their own, so
the wiring should compose with it rather than duplicate it.
