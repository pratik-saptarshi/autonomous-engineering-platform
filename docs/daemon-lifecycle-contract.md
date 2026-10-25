# NeuroStrata Daemon Lifecycle Contract

> **Status:** descriptive. This document describes what the daemon lifecycle
> actually does today — including the repo-vs-deployed script fork and the
> behavioral gaps — not what it should do. It is a reference for plans and
> jobs, not a policy. Last verified: 2026-10-24.

---

## 1. The Fork

There are **two** watchdog scripts, and they disagree.

| | Repo script (`repo-scripts`) | Deployed script (`deployed-bin`) |
|---|---|---|
| Path | `scripts/watchdog-backup.sh` (in this repo) | `~/workspace/neurostrata/bin/watchdog-backup.sh` (on the VM) |
| Daemon-down behavior | Three-way decision after change detection (see §3 Transitions): leave-down marker present → leave down; DB unchanged → restart; DB changed → take the backup while down, restart after the copy. The change path stops via `stop_daemon()` (`watchdog-backup.sh:199`, defined before the flow); a daemon that will not stop fails the run (exit 1). | Three-way decision + change-path restart (see §3 Transitions) |
| `reaped_expected()` | Absent — zero occurrences. The intentional-down signal is the `WATCHDOG_LEAVE_DOWN_MARKER` file check instead (`leave_down_intentional()`, `watchdog-backup.sh:65`) | Present (`watchdog-backup.sh:163`) |
| `start_daemon()` | Present (`watchdog-backup.sh:69`) and called — on the down/unchanged path and after the change-path copy (via `start_and_wait()`, `watchdog-backup.sh:98`) | Present (`watchdog-backup.sh:112`) |
| EXIT trap | Present (`watchdog-backup.sh:238`; `on_exit()` at `:227`) — restarts the daemon if the run stopped it, unless the leave-down marker is present | Present (`watchdog-backup.sh:192`) |

Diff magnitude: **553 changed lines**
(`diff scripts/watchdog-backup.sh ~/workspace/neurostrata/bin/watchdog-backup.sh | wc -l` → 553, verified 2026-10-24).

No sync mechanism exists between the two scripts (verified 2026-10-22: no
`cp`/`rsync` of the script in repo scripts/, crontab, or OPERATIONS.md; the
deployed script is edited in place). The 2026-10-21 log-rotation edit landed
deployed-only with a `.bak` file and no plan update — see §6 Known gaps.

**Canonical rule:** when the two scripts disagree, the **deployed** script
governs runtime behavior; the **repo** script governs what the plans were
written against. Henceforth cited as `deployed-bin` / `repo-scripts`.

---

## 2. States

Each state has an observable predicate and documented limits. Predicates are
runnable as written; where a predicate is weak, the limit says so.

### HEALTHY

- **Predicate (deployed-bin):** `daemon_healthy()` passes —
  `neurostrata-mcp status` output greps for `"status: healthy"`
  (`watchdog-backup.sh:66`).
- **Predicate (boot-gate):** `check_daemon()` passes — `neurostrata-mcp status`
  output matches `*"daemon: listening"*"answering"*` (`boot-gate.sh:60`).
- **Limit:** the co-occurrence of "status: healthy" and "answering" in a single
  `neurostrata-mcp status` output is **UNVERIFIED** — the daemon was not
  started to compare outputs (547MB model load + port bind is an operational
  side effect inappropriate for a docs-only contract). Treat the two
  predicates as the two observers' definitions of healthy, not as proven
  equivalent.

### DOWN_REAPED

- **Predicate (deployed-bin):** not healthy **AND** `reaped_expected()` returns
  true — the last "REAPED" line in the reaper log is newer than the last
  start line in `watchdog.log`, compared as epoch timestamps
  (`watchdog-backup.sh:163-176`, decision at `watchdog-backup.sh:202`).
- **Limits (do NOT treat as cleanly observable):**
  - *Log-dependence:* if no REAPED line exists, `reaped_expected()` returns
    false and the classifier fails closed to DOWN_UNEXPECTED (restart)
    (`watchdog-backup.sh:167-169`). Missing logs → always restart, never
    leave down.
  - *TZ asymmetry:* see §6.
  - *Out-of-band starts:* `reaped_expected()` only reads `watchdog.log`
    (`watchdog-backup.sh:166`); boot-gate nohup starts write nothing there.
    A reaped → nohup-started → crashed daemon is misclassified REAPED_DOWN
    and left down on the no-change path.
  - *Meaning:* "the reaper shut it down" is the best available inference, not
    a verified fact.

### DOWN_UNEXPECTED

- **Predicate (deployed-bin):** not healthy **AND** `reaped_expected()` returns
  false (`watchdog-backup.sh:202`). This is the **fail-closed bucket**: it
  includes genuine crashes, trap-failed restarts, and every case where the
  logs are insufficient to prove a reap.
- **Limit:** the trap-failed state (EXIT trap logged ERROR at
  `watchdog-backup.sh:187`) has no distinct predicate — it lands here and is
  retried on the next run with no alerting. See §6.

### State summary

| State | Predicate source | Meaning |
|---|---|---|
| HEALTHY | `deployed-bin` :66 / `boot-gate.sh` :60 | Daemon serving |
| DOWN_REAPED | `deployed-bin` :163-176, :202 | Probably reaped; limits apply |
| DOWN_UNEXPECTED | `deployed-bin` :202 (negation) | Fail-closed: crash, trap-fail, or unknown |

---

## 3. Transitions

Every transition names which script performs it.

### deployed-bin transitions

- **HEALTHY → down (reaped):** the idle reaper runs `neurostrata-mcp shutdown`
  (clean checkpoint — never SIGKILL) after all 6 preconditions hold
  (`idle-reaper.sh:18`; preconditions at `idle-reaper.sh:34,43,49,56,61,81`).
- **HEALTHY → down (change path):** watchdog SIGTERM-stops the daemon before
  backup (`watchdog-backup.sh:243-255`), then restarts it after
  (`watchdog-backup.sh:276-277`). A daemon still up after the 30 s stop
  loop logs ERROR and the run **exits 0**, skipping the backup
  (`watchdog-backup.sh:251-254`) — the deployed script does not fail on a
  stop failure; the repo script does (see repo-scripts transitions).
- **DOWN_UNEXPECTED → HEALTHY (no-change path):** DB unchanged and daemon
  down-unexpected → `start_daemon` + `wait_healthy`
  (`watchdog-backup.sh:220-228`).
- **DOWN (any reason) → HEALTHY (change path):** DB changed and daemon not
  running → log "daemon was not running — will start it after the backup",
  `RESTART_NEEDED=true` **unconditionally — no `reaped_expected()` check**
  (`watchdog-backup.sh:257-259`), then `start_daemon` after the backup copy
  verifies (`watchdog-backup.sh:276-277`). **Any formulation implying the watchdog
  "only restarts on unexpected-down" is false.**
- **EXIT-trap guarantee:** `on_exit` runs on script exit (`watchdog-backup.sh:192`);
  if `RESTART_NEEDED` is still true it attempts `start_daemon` + `wait_healthy`
  (`watchdog-backup.sh:180-190`).
- **EXIT-trap failure mode:** on failure it logs "exit trap: ERROR — daemon
  still down; next watchdog run will retry" (`watchdog-backup.sh:187`) and
  sets no distinguishable marker — the next run classifies via the normal
  `reaped_expected()` path.

### repo-scripts transitions

- **Daemon-active gate first:** a healthy daemon whose last client use is
  recent is left entirely alone (exit 0) before any other daemon-state
  decision (`watchdog-backup.sh:240-261`).
- **Change detection before any stop/restart decision:** DB hashes are
  computed first (`watchdog-backup.sh:262-277`); an unchanged DB never
  stops the daemon — the run runs Drive catch-up and exits 0
  (`watchdog-backup.sh:299-309`).
- **HEALTHY → down (change path):** `stop_daemon` at `watchdog-backup.sh:321`
  — the function is defined at `:199`, before the flow, so the call
  executes: the daemon is SIGTERM-stopped (all matching PIDs) before the
  backup copy. A daemon that will not stop **fails the run** (exit 1,
  `watchdog-backup.sh:321-324`) — where the deployed script skips with
  exit 0. After the copy verifies (`watchdog-backup.sh:331-341`) the
  daemon is restarted with a health poll (`watchdog-backup.sh:345`); the
  EXIT trap (`watchdog-backup.sh:238`) performs the restart if the run
  dies between the stop and the restart, unless the leave-down marker is
  present.
- **DOWN → left down (marker):** daemon down and the file named by
  `WATCHDOG_LEAVE_DOWN_MARKER` exists → the run logs and exits 0, whatever
  the DB state (`watchdog-backup.sh:280-284`).
- **DOWN_UNEXPECTED → HEALTHY (no-change path):** down, no marker, DB
  unchanged → `start_and_wait` restarts the daemon, then Drive catch-up,
  exit 0 (`watchdog-backup.sh:285-294`).
- **DOWN (any non-marker reason) → backup while down (change path):** down,
  no marker, DB changed → no pre-restart; the change path's stop is a
  no-op on a down daemon, the copy proceeds, and the daemon is restarted
  after it (`watchdog-backup.sh:295`, then the change path above).

### Out-of-band transitions (neither script)

- **Boot-gate start:** direct nohup when a job needs the daemon
  (see §4 Ownership). Writes nothing to `watchdog.log`.
- **Manual nohup:** `HF_HUB_OFFLINE=1 nohup ~/go/bin/neurostrata-mcp daemon ... &`.

---

## 4. Ownership

| Actor | May start | May stop | Circumstances | Must not |
|---|---|---|---|---|
| Idle-reaper cron (15m) | No | Yes — `neurostrata-mcp shutdown` only | 45+ idle min and all 6 preconditions (`idle-reaper.sh:34,43,49,56,61,81`) | SIGKILL the daemon; shut down while lock held, connections active, or CLI active |
| Watchdog cron (2h) | Yes — `start_daemon` | Yes — SIGTERM on change path | No-change+unexpected-down; change+down(any reason) (`watchdog-backup.sh:220-228,257-259,276-277`) | Restart a reaped daemon on the no-change path (`watchdog-backup.sh:216-219`) |
| Boot-gate / job preamble | Yes — direct nohup | No | Job needs the daemon and it is not answering (`boot-gate.sh:60`) | Start while the watchdog lock is held (see race note) |
| Human operator | Yes — direct nohup | Yes — `neurostrata-mcp shutdown` preferred | Manual intervention, incident response | Edit the deployed script without updating the repo copy (widens the fork, §6) |

**Lockless-nohup race note.** The boot-gate's nohup path takes no lock. A
start landing between the watchdog's change-path SIGTERM-stop
(`watchdog-backup.sh:243-255`) and its backup copy can corrupt the backup. The
copy-verify logic (`watchdog-backup.sh:265-271`) catches torn copies (partial
write during `cp` → hash mismatch → deleted, exit 1), but it verifies copy ==
source-at-hash-time, not source consistency: a write landing after the copy,
or WAL-only writes not in the copied `$DB` file, would produce a
checksum-passing but stale or inconsistent backup. The race is therefore NOT
contained — the worst case is a bad backup that looks good, not a failed run.
(These are worst-case analyses of the mechanism, not observed events.)
Mitigation today: none automated; the race window is seconds
per 2h cycle. The contract records it; closing it (lock the nohup path, or
re-check daemon state after acquiring the watchdog lock) is follow-up work.

**Standing rule:** no actor starts the daemon while the watchdog lock
(`~/workspace/neurostrata/.watchdog.lock`) is held.

---

## 5. What to do in each state

Instructions for dependent jobs, citing this contract's own states.

- **HEALTHY:** proceed; the daemon is serving. No action needed.
- **DOWN_REAPED:** proceed without the daemon **OR** start it via direct
  nohup if your job needs it; **do not treat as failure** — a reaped daemon
  is the expected idle state. Note the revive gap (§6 Known gaps): there is
  no reliable demand-revive today, so a job that needs the daemon should
  start it itself rather than wait.
- **DOWN_UNEXPECTED:** the watchdog will restart it on the next 2h run (or
  sooner on the change path). If your job needs the daemon now, start it via
  direct nohup. If DOWN_UNEXPECTED recurs across runs, investigate — check
  the EXIT-trap ERROR line (`watchdog-backup.sh:187`) and the WAL warnings.

---

## 6. Known gaps

Each gap: what it is, both evidences, operational consequence today, what
would close it. None of these are blessed; all are open.

### Gap 1 — MCP-spawn demand path (broken, needs a fix)

- **What:** the reaper's design assumes an MCP client can demand-revive a
  reaped daemon.
- **Evidence A** (`idle-reaper.sh:6-7`): "MCP stdio mode auto-spawns a
  detached daemon if none is running (src/main.rs:1399, verified in source)".
- **Evidence B** (`docs/limitation-analysis.md:11`): "an MCP-spawn revive was
  tried and found unreliable — the stdio server hangs without starting the
  daemon" (verified 2026-10-16).
- **Consequence today:** the watchdog's no-change path leaves reaped daemons
  down (`watchdog-backup.sh:216-219`); with MCP-spawn unreliable, reaped
  daemons revive only on coincidental DB changes, manual nohup, or the
  boot-gate.
- **Closes when:** MCP auto-spawn is fixed, or an explicit demand-revive path
  is added. Framing it as "don't rely on it" as settled policy is rejected —
  that severs the reaper's design without naming the gap.

### Gap 2 — TZ asymmetry in `reaped_expected()`

- **What:** the deployed watchdog pins `export TZ=UTC` (`watchdog-backup.sh:57`)
  because mixed-timezone lines corrupt recency comparisons; the reaper's
  `ts()` uses ambient TZ with no pin (`idle-reaper.sh:28`).
- **Consequence today:** a manual reaper run under non-UTC TZ writes lines the
  watchdog's `date -d` misparses by the UTC offset (up to 6h for US
  timezones), potentially misclassifying reaped vs unexpected.
- **Closes when:** the reaper pins `TZ=UTC` (one-line change, untested).

### Gap 3 — Trap-failed misclassification

- **What:** the EXIT trap's failure mode logs an ERROR
  (`watchdog-backup.sh:187`) but sets no marker distinguishable from a
  normal unexpected-down.
- **Consequence today:** a daemon the trap failed to restart is retried on
  the next run with no alerting; repeated trap failures are invisible except
  in log text.
- **Closes when:** the trap writes a distinct marker (e.g., a state file or
  a structured log line) that the next run — or monitoring — can key on.

### Gap 4 — The fork itself (no sync mechanism)

- **What:** the repo and deployed watchdog scripts differ by 553 lines with
  no sync mechanism (§1). The lifecycle semantics have converged (both
  implement the decision order of §3); what still differs is mechanism and
  detail — paths, the intentional-down signal (marker file vs
  `reaped_expected()`), stop-failure exit (1 vs 0), Drive mechanics.
- **Consequence today:** plans written against `repo-scripts` describe
  behavior the runtime (`deployed-bin`) does not exhibit, and vice versa;
  every claim about "the watchdog" must name which script.
- **Closes when:** a sync mechanism exists (deploy-from-repo pipeline) or the
  repo script is removed as a reference and the deployed script becomes the
  single source of truth.

---

## 7. Refresh trigger

**manual, best-effort** — re-verify the cited file:line references against
both scripts on any watchdog-related change. This contract rots the moment
either script changes without a contract update, and no automated check
exists today: the 2h watchdog cron was not modified to log script hashes
(out of scope for this docs PR), so there is no CONTRACT STALE alert. A
future change may add the hash check described below; until then, this
trigger is honest about being manual. No owner is assigned to the
re-verification — it happens when someone touches watchdog-related code
and remembers to check.

*Proposed mechanism (not implemented):* add a script-hash check to the
existing 2h watchdog cron. Each run would log `sha256sum` of both scripts
(`~/workspace/neurostrata/bin/watchdog-backup.sh` and the repo
`scripts/watchdog-backup.sh`); on hash change, log an alert line
(`CONTRACT STALE: watchdog script changed — re-verify
docs/daemon-lifecycle-contract.md`).
