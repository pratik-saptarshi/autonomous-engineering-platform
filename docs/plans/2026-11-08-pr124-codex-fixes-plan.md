# PR #124 Codex Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adjudicate and fix the six Codex findings (3×P1, 3×P2) on PR #124 (head `dff8e07`) so the cross-platform Go runtime branch can pass the final-head Codex gate with zero unresolved threads.

**Architecture:** Fixes land on the existing PR branch in the dedicated worktree, one task per finding, each driven by a TDD check script that is RED on the unmodified tree. Shared-platform defects (F1 timeout kill, F4 Windows job assignment) are fixed in `internal/platform/process` so every caller benefits; runner-policy defects (F2 empty discovery, F6 Make-target probe) stay in `internal/verifier/runner`; packaging defects stay in `Makefile` (F5) and `cmd/aep` (F3 — the missing command is implemented, the unit is not repointed).

**Tech Stack:** Go 1.27.3 (go.mod; local toolchain auto-switches), POSIX process groups + Windows Job Objects (`golang.org/x/sys`), GNU Make, bash, systemd units. No new dependencies.

**Spec:** The six Codex review threads on PR #124 (pratik-saptarshi/autonomous-engineering-platform), receipt bound to head `dff8e07`, `has_any_findings=true`. Each task quotes the finding, gives this plan's adjudication against the tree at `dff8e07`, and records the RED run of its check script (all six were run on 2026-11-08 and failed as recorded).

## Global Constraints

- Conventional Commit subjects; commit author `Musebot-Astro <6238157+pratik-saptarshi@users.noreply.github.com>`.
- Work ONLY in `~/workspace/worktrees/aep-pr124-fixes` on branch `feat/cross-platform-go-runtime`. Fixes stack on `dff8e07`; the PR's base is unchanged. Never touch the parked main checkout.
- All GitHub calls through ghg: `GHG_ACTOR=<task-slug> ~/go/bin/ghg run -- <gh args…>`; pre-flight gated steps with `ghg check`. On exit 75: stop and report the stage; never `GHG_BYPASS=1`.
- Go commands run in a login shell with `GOTMPDIR=$HOME/.gotmp` (e.g. `bash -lc 'export GOTMPDIR=$HOME/.gotmp; cd ~/workspace/worktrees/aep-pr124-fixes && go test ./internal/verifier/runner/'`).
- VM memory is tight (~1.6 GiB effective): package-scoped `go test` only, never the full suite in one invocation; no parallel heavy builds.
- TDD check scripts live in `/tmp` (`/tmp/check-f1.sh` … `/tmp/check-f6.sh`, already written and RED-verified) and are NEVER committed.
- No `bd` (Beads) commands — `bd` resolves to the main checkout's database from worktrees.
- No branch deletion, force-push, or history rewrite without separate per-action approval.
- Suggested implementation order: Task 6 (F6) → Task 2 (F2) → Task 1 (F1) → Task 4 (F4) → Task 5 (F5) → Task 3 (F3). One commit per task.

## Review Focus

- **Group escape (F1):** a grandchild that calls `setsid` leaves the leader's process group and can hold the output pipes past the group kill. Expected: `Wait` still returns within its bounded drain (grace + 2s) with the context error; the escapee itself is out of the platform's reach and is a documented residual. Pinned in Task 1, Step 5.
- **Budget vs timeout (F1):** total-budget expiry mid-command must behave exactly like per-command timeout (same context path, group terminated, receipt `timed_out=true`). Pinned in Task 1, Step 5.
- **Supervisor tick overrun (F3):** a verification tick that runs longer than `--interval` must never overlap the next tick (sequential loop; `time.Ticker` drops missed beats). Pinned in Task 3, Step 4.
- **Suspended-process failure path (F4):** if job assignment succeeds but resume fails, the child must not be left suspended forever — it is terminated via the job before `Start` returns the error. Pinned structurally in Task 4, Step 3 (no Windows runtime exists here).
- **Make-target false positives (F6):** a line beginning with `test:` in a non-rule context (e.g. inside a define block) enables make-test under the parity regex — the same behaviour as `scripts/mechanical_verify.py`, accepted deliberately for parity; a `# test:` comment line does not match in either implementation, because the line does not begin with `test:`. A Makefile with `.PHONY: test` but no recipe still schedules a target that make can run. Noted in Task 6; no extra test.

---

### Task 1 — F1 (P1): timeout must terminate the process group before waiting

**Thread:** `PRRT_kwDOVM-V9860-EUQ`, `internal/verifier/runner/runner.go:214`. Codex: `process.NewCommand` uses `exec.CommandContext` with default cancellation (kills only the leader), while `exec.Cmd.Wait` also waits for the output-copy goroutines to reach EOF; a surviving child holding the pipes means `pg.Wait()` never returns and the subsequent `pg.Kill()` is never reached, defeating both timeouts. Trigger group/job termination from cancellation rather than after `Wait`, and bound pipe draining.

**Adjudication: REAL, exactly as described.**
- `internal/platform/process/process.go:34` — `exec.CommandContext(ctx, …)`; Go's default `Cancel` is `Process.Kill` on the leader only.
- `internal/platform/process/process_posix.go:38-40` — `Wait()` is a bare `p.cmd.Wait()`; with `Stdout`/`Stderr` set to the runner's `TailCappedBuffer` (not `*os.File`), `cmd.Wait` waits for the internal copy goroutines, which need pipe EOF.
- `internal/verifier/runner/runner.go:213-219` — `pg.Kill()` (the group-wide kill, `process_posix.go:50-65`) is only called *after* `pg.Wait()` returns. Deadlock ordering confirmed by reading.
- **Reproduction (RED, 2026-11-08):** `/tmp/check-f1.sh` runs `aep verify` (per-command timeout 1s) against a fixture whose Makefile test target is `sh -c "sleep 60 & wait"`. Result: `verify rc=124 elapsed=20s` — verify was still blocked at 20s and had to be killed by the script's outer `timeout`; the leaked `sleep 60` was cleaned up by the script. Expected post-fix elapsed: ~2–4s (1s timeout + 750ms grace + drain).

**Decision — fix location:** `internal/platform/process`, not the runner. The `ProcessGroup` interface already promises "Wait waits for completion or context cancellation" and "Kill terminates the entire process tree" (`process.go:17-24`); the runner is only today's caller, and a runner-local workaround would leave the abstraction's contract false. The platform group must therefore own a reference to the command context (it currently discards it — `NewCommand` receives `ctx` but `newPlatformProcessGroup` does not keep it).

**Files:**
- Modify: `internal/platform/process/process.go` (pass `ctx` into `newPlatformProcessGroup`; document the new `Wait` contract)
- Modify: `internal/platform/process/process_posix.go` (ctx-aware `Wait`, idempotent `Kill`)
- Modify: `internal/platform/process/process_windows.go` (same `Wait` shape; `Kill` already terminates the job)
- Test: `internal/platform/process/process_test.go` (add `TestProcessGroup_WaitTerminatesGroupOnTimeout`)
- No change needed in `internal/verifier/runner/runner.go` — its post-`Wait` `pg.Kill()` becomes a harmless idempotent no-op and stays as belt-and-braces.

**Interfaces:**
- Consumes: existing `NewCommand(ctx, name, args, cfg) ProcessGroup`.
- Produces: `Wait()` returns promptly after context cancellation, having terminated the whole group/job; `Kill()` is idempotent (second and later calls are immediate no-ops). New unexported field on both platform structs: `ctx context.Context`, `terminated atomic.Bool` (or a `sync.Once`-guarded flag).

- [ ] **Step 1: Run the check script — confirm RED**

Run: `/tmp/check-f1.sh`
Expected: FAIL — `verify rc=124 elapsed=20s`, `F1 VIOLATION: verify itself had to be killed by the outer timeout (hung in Wait)`. (Recorded 2026-11-08.)

- [ ] **Step 2: Write the failing unit test**

Add to `process_test.go`: `TestProcessGroup_WaitTerminatesGroupOnTimeout` — skip on Windows (`runtime.GOOS == "windows"`); create a command `sh -c 'sleep 30 & wait'` with a 500ms-timeout context and `Stdout`/`Stderr` set to `io.Discard`-equivalent buffers (use `bytes.Buffer` via a small locked writer or `io.Discard` — a non-file writer is what forces the copy goroutines); `Start`, then time `Wait()`; assert elapsed < 5s and the returned error is non-nil.

Run: `bash -lc 'export GOTMPDIR=$HOME/.gotmp; cd ~/workspace/worktrees/aep-pr124-fixes && go test ./internal/platform/process/ -run WaitTerminatesGroup -v -timeout 30s'`
Expected: FAIL by test-internal timeout/elapsed assertion on the unmodified tree (do not let it hang CI: the test itself fails at its 5s assertion, then calls `pg.Kill()` for cleanup).

- [ ] **Step 3: Implement ctx-aware Wait + idempotent Kill (POSIX)**

`posixProcessGroup` gains `ctx` and `terminated`. `Wait()`:
```go
done := make(chan error, 1)
go func() { done <- p.cmd.Wait() }()
select {
case err := <-done:
    return err
case <-p.ctx.Done():
    _ = p.Kill()
    select {
    case err := <-done:
        return err
    case <-time.After(p.gracePeriod + 2*time.Second):
        return p.ctx.Err() // bounded drain: a group escapee may hold the pipes; do not block forever
    }
}
```
`Kill()`: if `terminated.Swap(true)` already set, return nil at once; otherwise the existing SIGTERM → grace → SIGKILL sequence against `-pgid`. Constructor in `process_posix.go` unchanged (Setpgid stays); `newPlatformProcessGroup(cmd, grace, ctx)` signature updated in both platform files and in `process.go`.

- [ ] **Step 4: Mirror the Wait shape on Windows**

`windowsProcessGroup.Wait()`: same goroutine+select structure; on `ctx.Done()` call `p.Kill()` (TerminateJobObject + handle close, already idempotent via the `InvalidHandle` reset) and apply the same bounded drain (`gracePeriod + 2s`, then return `ctx.Err()`). Keep the existing deferred handle-close, guarded so a post-`Kill` close is a no-op.

- [ ] **Step 5: Verify — unit test, package tests, Review Focus cases, check script**

Run: package tests for `internal/platform/process` and `internal/verifier/runner` (separately).
Then two extra probes (throwaway fixtures, not committed): (a) **setsid escapee** — Makefile target `sh -c "setsid sleep 60 & wait"`: verify must still return within ~6s of the 1s timeout with `timed_out=true` (the escapee process itself may survive — kill it after the probe and record that as the documented residual); (b) **budget expiry** — same fixture as the check script but `--timeout 60 --budget 2`: receipt shows `timed_out=true` and verify exits in ~4s.
Run: `/tmp/check-f1.sh`
Expected: PASS — `verify rc=1 elapsed≈2–4s`, receipt line shows `timed_out=true`, no `sleep 60` survives, script prints `F1 OK`.

- [ ] **Step 6: Commit**

```bash
git add internal/platform/process/
git commit -m "fix(platform): terminate the process group when the command context expires"
```

**Idempotence / crash end-state (pipeline prompt):** Calling `Kill` twice is safe — the second call is an immediate no-op (`terminated` flag on POSIX; invalidated job handle on Windows), and `Wait` after a completed kill returns as soon as the pipes reach EOF. If the verifier process crashes *between* SIGTERM and SIGKILL, the group has received SIGTERM only: cooperative children exit, a stubborn survivor can persist — the same residual class as a `setsid` escapee. No persistent state is corrupted either way: receipts and tail buffers are in-memory only, so a re-run of verification starts from a clean slate and re-discovers/re-executes from scratch. End state after a completed timeout-kill: no process of the group remains, pipes at EOF, `Wait` unblocked, receipt recorded with `timed_out=true`, exit code 124.

---

### Task 2 — F2 (P1): verification must not pass when zero checks are discovered

**Thread:** `PRRT_kwDOVM-V9860-OkS`, `internal/verifier/runner/runner.go:179`. Codex: for an empty directory, an unsupported project, or a nonexistent `--root`, discovery returns no commands and the branch returns `Pass: true`; `scripts/mechanical_verify.py` explicitly returns nonzero when discovery produces no mechanical evidence.

**Adjudication: REAL, and worse than stated — a nonexistent root also passes.**
- `runner.go:171-180` — `result.Pass` initialised `true`; `if len(cmds) == 0 { return result, nil }`.
- `DiscoverCommands` never errors on a missing root: every probe is `fileExists(...)`, all false, returns empty slice + nil error.
- Parity claim verified: `scripts/mechanical_verify.py:5240-5248` — `if not commands: print("VERIFY: no verification commands discovered … — no mechanical evidence available"); return 2`.
- **Reproduction (RED, 2026-11-08):** `/tmp/check-f2.sh` — `aep verify --root <empty tmpdir> --min-mem 0` → `Discovered: 0`, `Status: PASS`, exit 0; `--root /nonexistent-…` → identical PASS, exit 0.

**Files:**
- Modify: `internal/verifier/runner/runner.go` (`RunVerification`: validate root, refuse zero-discovery)
- Test: `internal/verifier/runner/runner_test.go` (three new tests)
- No change in `cmd/aep/main.go` — `runVerify` already exits 1 on a non-nil error.

**Interfaces:**
- Produces (pinned behaviour): `RunVerification` returns a non-nil error when (a) the root does not exist or is not a directory, or (b) discovery yields zero commands. In case (b) it also returns a result with `Pass: false, Discovered: 0` alongside the error; in case (a) the result may be nil.

- [ ] **Step 1: Run the check script — confirm RED**

Run: `/tmp/check-f2.sh`
Expected: FAIL — two `F2 VIOLATION: verify succeeded with zero discovered checks` lines. (Recorded 2026-11-08.)

- [ ] **Step 2: Write the failing tests**

Add to `runner_test.go`:
- `TestRunVerification_NonexistentRoot` — root = `filepath.Join(t.TempDir(), "does-not-exist")`; assert `err != nil`.
- `TestRunVerification_EmptyDirNoChecks` — empty `t.TempDir()`; assert `err != nil` and (`res == nil || !res.Pass`).
- `TestRunVerification_UnsupportedProject` — dir containing only `README.md`; same assertions.
All call `RunVerification(context.Background(), root, 0, 5*time.Second, 10*time.Second)` (minMem 0 bypasses the memory preflight, as the existing tests do).

Run: `bash -lc 'export GOTMPDIR=$HOME/.gotmp; cd ~/workspace/worktrees/aep-pr124-fixes && go test ./internal/verifier/runner/ -run "TestRunVerification_(NonexistentRoot|EmptyDirNoChecks|UnsupportedProject)" -v'`
Expected: FAIL — all three return `Pass: true`, nil error today.

- [ ] **Step 3: Implement the refusal**

In `RunVerification`, before discovery:
```go
info, err := os.Stat(repoRoot)
if err != nil || !info.IsDir() {
    return nil, fmt.Errorf("verification root %q does not exist or is not a directory", repoRoot)
}
```
(`os` is already imported.) Replace the zero-commands early return:
```go
if len(cmds) == 0 {
    result.Pass = false
    return result, fmt.Errorf("no verification checks discovered at %q: refusing to report success without mechanical evidence", repoRoot)
}
```

- [ ] **Step 4: Verify**

Run: the three new tests + full `internal/verifier/runner` package tests; then `/tmp/check-f2.sh`.
Expected: tests PASS; script prints no VIOLATION and exits 0 (both roots now exit non-zero with the refusal message). Note the existing `TestDiscoverCommands` expectation (empty dir → 0 commands, nil error) is about `DiscoverCommands` itself and stays valid — discovery semantics do not change, only the run-level verdict.

- [ ] **Step 5: Commit**

```bash
git add internal/verifier/runner/
git commit -m "fix(verifier): refuse success when no checks are discovered"
```

---

### Task 3 — F3 (P1): VM service must invoke an implemented `aep` command

**Thread:** `PRRT_kwDOVM-V9860-L_L`, `scripts/package-vm.sh:48`. Codex: the service invokes `aep supervisor --loop`, but `cmd/aep/main.go` only dispatches `version`, `info`, `boot`, `verify`, `lock-test`; no supervisor implementation exists anywhere in the tree; under `Restart=on-failure` the packaged service crash-loops. Implement the entry point or point the unit at an existing one.

**Adjudication: REAL.** Verified by reading: dispatch switch at `cmd/aep/main.go:26-44` has exactly the five commands Codex lists; default branch prints `Unknown command` and exits 1. A tree-wide search for `supervisor` finds no implementation in the branch's own CLI/runtime/scripts (only vendored `reference/**` material and old plan docs). `scripts/package-vm.sh:44-55` — `ExecStartPre=/usr/local/bin/aep boot`, `ExecStart=/usr/local/bin/aep supervisor --loop`, `Type=simple`, `Restart=on-failure`, `RestartSec=10s`.

**Decision — implement a minimal `supervisor` command; do NOT repoint the unit.** Reasons:
1. **Repointing makes the unit start but not work.** The only long-running-shaped candidates don't exist; the one-shot candidates are wrong: `boot` is already the unit's `ExecStartPre` (repointing duplicates it and the service would exit 0 immediately, doing nothing), and `verify` has no meaningful default root on a provisioned VM (its `--root` defaults to the service's working directory, which systemd leaves undefined here) — the "Ralph Execution Loop" the unit advertises would still not exist.
2. **The workload already exists as composable pieces.** A supervisor tick is exactly: boot gate (memory + platform preflight) then one bounded verification pass. Both exist (`runBootGate`'s checks in `main.go:99-117`; `runner.RunVerification` as used by `runVerify`). The missing piece is only the loop + signal handling — roughly 80 lines in `cmd/aep/main.go`, no new packages.
3. **The unit's shape confirms a daemon was intended:** `Type=simple` + `Restart=on-failure` + a `--loop` flag describe a long-running process, not a oneshot. (The companion `.timer` becomes vestigial once the service loops — activating an already-active service is a no-op, so leaving it is harmless; removing it is a packaging decision outside this finding.)

**Minimal supervisor specification (pinned):**
- Invocation: `aep supervisor [--loop] [--once] [--interval <dur>] [--root <path>] [--min-mem <MiB>] [--timeout <sec>] [--budget <sec>]`. Defaults: root `.`, interval `2h` (mirrors the timer cadence the bundle already ships), min-mem 384, timeout 300, budget 600 (same defaults as `verify`).
- One tick = boot-gate checks (memory probe + 384MiB floor + platform line, refactored to return an error) followed by `runner.RunVerification`. Tick outcome logged to stdout as `SUPERVISOR: tick ok (discovered=N executed=M)` or `SUPERVISOR: tick failed: <err>`.
- Boot-gate failure inside a tick is fatal: `supervisor` exits 1 (environment unfit; systemd's `Restart=on-failure` + `RestartSec` own the retry policy). A verification failure (error or `!Pass`) is logged and, in loop mode, does **not** exit — a failing check must not crash-loop the service; in `--once` mode it exits 1.
- Loop mode (`--loop`, or default when neither flag is given? — no: pinned the other way) — behaviour: with `--loop`, tick immediately, then on a `time.Ticker(interval)` until SIGINT/SIGTERM, then exit 0. Without `--loop` and without `--once`, run exactly one tick and exit with the tick's status (so a bare `aep supervisor` always terminates). Ticks are sequential — a tick longer than the interval delays the next one; missed beats are dropped by the ticker, never queued.
- Usage text gains the line `supervisor    Run the execution loop (boot gate + verification ticks)`, indented two spaces to align with the other usage entries.

**Files:**
- Modify: `cmd/aep/main.go` (dispatch case, usage line, `runSupervisor` + `supervisorTick`, refactor `runBootGate` into `bootGate() error` with the existing `boot` subcommand keeping its exact output/exit behaviour)
- Test: `cmd/aep/main_test.go` (create; tick-level tests)
- `scripts/package-vm.sh`: **no change** — its `ExecStart` becomes valid as written.

**Interfaces:**
- Produces: `func supervisorTick(ctx context.Context, root string, minMemBytes uint64, perCmdTimeout, totalBudget time.Duration) error` in package `main` — nil only when the boot gate passes and verification passes; `func bootGate() error` — the existing boot checks without `os.Exit`/printing split (printing stays in the caller where the current output format is a contract).

- [ ] **Step 1: Run the check script — confirm RED**

Run: `/tmp/check-f3.sh` (parses the unit's `ExecStart=` line, asserts the subcommand is in `aep` usage, then runs `aep supervisor --once` against a trivial Makefile fixture)
Expected: FAIL — `unit ExecStart subcommand: supervisor`, `F3 VIOLATION: 'supervisor' not in aep usage`. (Recorded 2026-11-08.)

- [ ] **Step 2: Write the failing tests**

Create `cmd/aep/main_test.go`:
- `TestSupervisorTick_Pass` — fixture dir with a Makefile `test:` target `@true`; assert `supervisorTick(ctx, dir, 0, 5s, 10s) == nil`.
- `TestSupervisorTick_EmptyRootFails` — empty temp dir; assert non-nil error (depends on Task 2's refusal — if Task 2 hasn't landed yet this test fails for the discovery reason only after it does; order per Global Constraints puts F3 last).

Run: `bash -lc 'export GOTMPDIR=$HOME/.gotmp; cd ~/workspace/worktrees/aep-pr124-fixes && go test ./cmd/aep/ -v'`
Expected: FAIL — `supervisorTick` undefined (compile error).

- [ ] **Step 3: Implement**

Refactor `runBootGate` → `bootGate() error` + a printing wrapper preserving current `boot` output. Add the `supervisor` case to the dispatch switch, the usage line, `supervisorTick`, and `runSupervisor` implementing the pinned spec (flags via `flag.NewFlagSet("supervisor", …)` like `runVerify`; loop via `signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)` + `time.NewTicker`).

- [ ] **Step 4: Verify**

Run: `go test ./cmd/aep/`; then `/tmp/check-f3.sh` (expects `F3 OK`, `supervisor --once` exit 0); then a manual loop smoke: `timeout 3 /tmp/aep supervisor --loop --interval 1s --root <fixture>` rebuilt binary — expect ≥2 `tick ok` lines and a clean exit 0 from the timeout's SIGTERM path (exit code 0, not 124 — check with `timeout -s TERM` semantics; if the harness reports 124, inspect: the process must exit promptly on SIGTERM).
Review Focus case: tick-overrun single-flight is by construction (sequential loop + ticker) — state this in the commit body rather than adding a timing test.

- [ ] **Step 5: Commit**

```bash
git add cmd/aep/
git commit -m "feat(cli): implement the supervisor loop the VM service invokes"
```

---

### Task 4 — F4 (P2): Windows job membership must be established before child code runs

**Thread:** `PRRT_kwDOVM-V9860-EUT`, `internal/platform/process/process_windows.go:56`. Codex: `p.cmd.Start()` launches the command normally before it is assigned to the job object; a promptly-spawning command creates children outside the job, and later assignment does not adopt them; such children survive `TerminateJobObject`. Create suspended, assign, then resume — or an equivalent creation-time association.

**Adjudication: REAL.** `process_windows.go:51-71` — `cmd.Start()` (line 51) precedes `OpenProcess` (line 58) and `AssignProcessToJobObject` (line 66). Between process creation and assignment the child's main thread runs unsuspended; anything it spawns in that window is outside the job permanently. The window is small but the guarantee the type advertises ("full hierarchy tracking", `process.go:14`) is absolute, so the finding stands as written.

**Decision — suspended create via `exec.Cmd`, resume via Toolhelp thread lookup.** The Go-feasible pattern that keeps the existing `exec.Cmd` plumbing (the runner passes in-memory `io.Writer`s, so abandoning `exec.Cmd` for raw `CreateProcess` would mean reimplementing pipe/copy plumbing — rejected):
1. In the Windows constructor (`newPlatformProcessGroup`), set `cmd.SysProcAttr = &syscall.SysProcAttr{CreationFlags: windows.CREATE_SUSPENDED}` — `exec` honours `CreationFlags`, and the process's main thread is created suspended: no child code runs, so nothing can spawn outside the job.
2. `Start()` order becomes: create job + set `KILL_ON_JOB_CLOSE` (unchanged) → `cmd.Start()` (suspended) → `OpenProcess` → `AssignProcessToJobObject` → `resumeMainThread(pid)` → return.
3. `resumeMainThread(pid uint32) error` (new, `process_windows.go`): `windows.CreateToolhelp32Snapshot(windows.TH32CS_SNAPTHREAD, 0)`; iterate `windows.ThreadEntry32` via `Thread32First`/`Thread32Next` for `Th32OwnerProcessID == pid` (a freshly created process has exactly one thread); `windows.OpenThread(windows.THREAD_SUSPEND_RESUME, false, tid)`; call `windows.ResumeThread` until it reports a previous suspend count ≤ 1 (loop cap 32); close both handles. No matching thread → error.
4. Failure handling after `Start()`: if assignment or resume fails, terminate before returning the error — via the job if assignment already succeeded, else `cmd.Process.Kill()` (valid on a suspended process) — and close the job handle. A suspended process must never be left behind (Review Focus).

**Evidence gate (honest limits):** there is **no Windows runtime in this environment**, so the gate is: `GOOS=windows go build` + `go vet` on the package, the structural ordering assertions in `/tmp/check-f4.sh` (CREATE_SUSPENDED present; `AssignProcessToJobObject` textually precedes `ResumeThread`), existing POSIX package tests still green, and an explicit "Windows runtime behaviour unverified — validated by cross-compile + code inspection only" line in the PR body at Stage 6. API availability (`CreateToolhelp32Snapshot`, `Thread32First/Next`, `OpenThread`, `ResumeThread`, `CREATE_SUSPENDED` in `golang.org/x/sys/windows`) is proven by the cross-build step itself.

**Files:**
- Modify: `internal/platform/process/process_windows.go` (constructor CreationFlags, Start ordering, `resumeMainThread`)
- No test file change is possible for Windows behaviour here; POSIX `process_test.go` must keep passing unchanged.

**Interfaces:**
- Consumes: Task 1's `newPlatformProcessGroup(cmd, grace, ctx)` signature (this task's constructor change is inside the Windows implementation of that same constructor).
- Produces: unchanged `ProcessGroup` behaviour contract; on Windows the contract's hierarchy guarantee now holds from process creation.

- [ ] **Step 1: Run the check script — confirm RED**

Run: `/tmp/check-f4.sh`
Expected: cross-build/vet pass, then FAIL — `F4 VIOLATION: CREATE_SUSPENDED not used — child code runs before job assignment`. (Recorded 2026-11-08.)

- [ ] **Step 2: Implement the constructor change**

In `newPlatformProcessGroup` (windows): ensure `SysProcAttr` exists and OR in `windows.CREATE_SUSPENDED`:
```go
if cmd.SysProcAttr == nil { cmd.SysProcAttr = &syscall.SysProcAttr{} }
cmd.SysProcAttr.CreationFlags |= windows.CREATE_SUSPENDED
```

- [ ] **Step 3: Reorder Start and add resumeMainThread**

Rewrite `Start()` to the pinned order (job → limits → Start → OpenProcess → Assign → resume), with the failure path terminating the (possibly suspended) child and closing the job before returning a wrapped error. Add `resumeMainThread` as specified. `Kill()` and `Wait()` need no logic change beyond Task 1's.

- [ ] **Step 4: Verify**

Run: `/tmp/check-f4.sh` — expected `F4 OK (structural; Windows runtime unverified in this environment)`; `GOOS=windows go build ./...` for the whole module; POSIX `go test ./internal/platform/process/`.

- [ ] **Step 5: Commit**

```bash
git add internal/platform/process/process_windows.go
git commit -m "fix(platform): create Windows processes suspended and assign the job before resuming"
```

---

### Task 5 — F5 (P2): `make binaries` / `make all` must rebuild when inputs change

**Thread:** `PRRT_kwDOVM-V9860-L_N`, `Makefile:23`. Codex: after the first successful build, the four binary file-targets have no prerequisites, so source/module/flag changes never rebuild; VM packages then ship the old executable. A dry run with all four outputs present confirms make reports nothing to do.

**Adjudication: REAL.** `Makefile:21-38` — `binaries` aggregates four file targets; each file target's rule has **zero prerequisites** (e.g. `dist/bin/aep-linux-amd64:` with only a recipe). Making the aggregate `.PHONY` would not help (it is not — line 14 declares `all binaries vm oci clean test` phony, and phony-ness of the aggregate does not propagate to file prerequisites anyway, as Codex notes).
- **Reproduction (RED, 2026-11-08):** `/tmp/check-f5.sh` copies the module (excluding `.git`/`reference`/`dist`) to a throwaway dir, runs `make binaries`, appends a comment line to `cmd/aep/main.go`, runs `make binaries` again: `binary mtime before=1794118492 after-source-touch=1794118492` — no rebuild.

**Decision — prerequisites, not forced recipes.** Codex offers either; prerequisites preserve make's incremental no-op when nothing changed (a forced `.PHONY` binary would rebuild four cross-compiled binaries on every `make vm`/`make all`), so: collect the real inputs once and attach them to every binary target.

**Files:**
- Modify: `Makefile` (add `GO_SOURCES`, attach prerequisites to the four binary targets)

**Interfaces:** none (build-system internal).

- [ ] **Step 1: Run the check script — confirm RED**

Run: `/tmp/check-f5.sh`
Expected: FAIL — identical mtimes, `F5 VIOLATION: binary not rebuilt after source change`. (Recorded 2026-11-08; first build ≈35s on this VM.)

- [ ] **Step 2: Implement**

In `Makefile` after the `DIST_*` block:
```make
GO_SOURCES := $(shell find cmd internal -type f -name '*.go')
```
Change each binary target line to `dist/bin/aep-<os>-<arch>: $(GO_SOURCES) go.mod go.sum`. The `dist/vm/*` targets already depend on the binary targets, so VM bundles inherit the freshness. No recipe changes.

- [ ] **Step 3: Verify**

Run: `/tmp/check-f5.sh` — expected `F5 OK` (mtime advances after the touch). Additionally confirm the no-change case stays a no-op: in the same throwaway copy, a third `make binaries` with no edits prints `make: Nothing to be done for 'binaries'` (or equivalent up-to-date output) — prerequisites must not turn into forced rebuilds.

**Known residual (record, don't fix):** `LDFLAGS` embeds `$(shell git rev-parse --short HEAD)`; a commit that changes no Go source will not trigger a rebuild, so the stamped commit can lag. That is outside the finding (sources/modules/flags) and is noted here so Stage 3 doesn't re-raise it as a discovery.

- [ ] **Step 4: Commit**

```bash
git add Makefile
git commit -m "fix(build): rebuild distribution binaries when Go inputs change"
```

---

### Task 6 — F6 (P2): Make test target must be confirmed to exist before scheduling

**Thread:** `PRRT_kwDOVM-V9860-OkT`, `internal/verifier/runner/runner.go:150`. Codex: discovery schedules `make test` for any Makefile; a build-only Makefile makes `make test` exit 2 and fails verification even when other checks pass. `scripts/mechanical_verify.py` checks for a `test:` declaration first; preserve that check.

**Adjudication: REAL, parity claim verified.**
- `runner.go:147-154` — `fileExists(Makefile)` alone schedules `make-test`; no content inspection.
- Parity verified: `scripts/mechanical_verify.py:2029-2037` reads the Makefile and requires `re.search(r"^test:", text, re.MULTILINE)` before adding its make-test command.
- **Reproduction (RED, 2026-11-08):** `/tmp/check-f6.sh` fixture = `go.mod` + one `.go` file (go-test passes) + Makefile with only a `build:` target. Current output: `discovered: 2`, go-test exit 0, **make-test exit 1** (runner maps make's failure; make itself reports no such target), `pass: false`.

**Files:**
- Modify: `internal/verifier/runner/runner.go` (gate step 5 of `DiscoverCommands` on a new `hasMakeTestTarget` helper)
- Test: `internal/verifier/runner/runner_test.go` (extend discovery tests)

**Interfaces:**
- Produces: `func hasMakeTestTarget(makefilePath string) bool` — true iff the file reads successfully and matches `(?m)^test:` (deliberate byte-parity with `mechanical_verify.py`'s `^test:`: `test :` with a space does **not** count, and neither does a commented-out `# test:` line, which does not begin with `test:`; a line that does begin with `test:` matches in both implementations even when it is not a real rule — e.g. inside a define block — and matching the Python verifier's behaviour is the point).

- [ ] **Step 1: Run the check script — confirm RED**

Run: `/tmp/check-f6.sh`
Expected: FAIL — `F6 VIOLATION: make-test scheduled although the Makefile declares no test target`. (Recorded 2026-11-08.)

- [ ] **Step 2: Write the failing tests**

Extend `TestDiscoverCommands` (or add `TestDiscoverCommands_MakeTarget`): (a) Makefile with only `build:` → no `make-test` in the result; (b) Makefile with a `test:` target → `make-test` present; (c) Makefile that is unreadable/missing → no `make-test` (already covered by (a)'s path through the helper returning false on read error — assert (a) and (b) at minimum).

Run: `bash -lc 'export GOTMPDIR=$HOME/.gotmp; cd ~/workspace/worktrees/aep-pr124-fixes && go test ./internal/verifier/runner/ -run DiscoverCommands -v'`
Expected: FAIL on case (a) — make-test is discovered today.

- [ ] **Step 3: Implement**

Add `regexp` to imports; helper:
```go
var makeTestTargetRe = regexp.MustCompile(`(?m)^test:`)

func hasMakeTestTarget(makefilePath string) bool {
    data, err := os.ReadFile(makefilePath)
    if err != nil {
        return false
    }
    return makeTestTargetRe.Match(data)
}
```
Gate discovery step 5 on `fileExists(...) && hasMakeTestTarget(...)`.

- [ ] **Step 4: Verify**

Run: full `internal/verifier/runner` package tests; `/tmp/check-f6.sh` — expected `F6 OK` (make-test absent from the JSON, `pass: true` on go-test alone). Also confirm the existing `TestRunVerification_Pass` (Makefile *with* `test:`) still passes.

- [ ] **Step 5: Commit**

```bash
git add internal/verifier/runner/
git commit -m "fix(verifier): schedule make test only when a test target is declared"
```

---

## Stage 3 / Stage 6 notes

**Whole-branch review scope.** The reviewable delta is `dff8e07..HEAD` on `feat/cross-platform-go-runtime` (the six fix commits) — not the whole PR #124 diff. The independent whole-branch reviewer checks: (1) each task's fix actually changes the flagged mechanism at the flagged file:line; (2) no fix alters behaviour beyond its finding (especially: `DiscoverCommands` semantics unchanged apart from the F6 gate — `TestDiscoverCommands`' empty-dir contract is untouched; `boot` subcommand output/exit behaviour byte-identical after the F3 refactor); (3) all six `/tmp/check-f*.sh` scripts GREEN against the final tree; (4) package-scoped tests green for `internal/platform/process`, `internal/verifier/runner`, `cmd/aep`; (5) `GOOS=windows go build ./...` green.

**Thread disposition mechanics.** After the fix commits are pushed (plain `git push` of the PR branch; pre-flight any ghg-gated step with `ghg check`), reply on each Codex thread with `Fixed in <sha>` naming that task's commit, **only after verifying the fix is present in the tree at the pushed head** (read the flagged file at the head via the contents API), then resolve the thread. Thread IDs: F1 `PRRT_kwDOVM-V9860-EUQ`, F4 `PRRT_kwDOVM-V9860-EUT`, F3 `PRRT_kwDOVM-V9860-L_L`, F5 `PRRT_kwDOVM-V9860-L_N`, F2 `PRRT_kwDOVM-V9860-OkS`, F6 `PRRT_kwDOVM-V9860-OkT`. Per-thread dispositions are this fleet's maintainer convention; a blanket "all fixed" comment is not a substitute.

**Final-head Codex gate (merging-gated-prs).** Merging requires, on the FINAL head: headRefOid cross-checked against the branch ref; all CI checks green on that SHA (the repo currently runs 9 — the original 7 plus `actionlint` and `dependency-review`); the full untruncated thread list at zero unresolved; a Codex receipt bound to the final head with `has_any_findings=false` (post an `@codex review` retrigger if the push doesn't auto-review); a ≥5-minute dwell after that review completes, then a re-census at report time; and the merge executed with `--match-head-commit <final-head-sha>` — **only on Pratik's explicit per-PR word**. The PR body must carry the F4 caveat verbatim in substance: Windows job-assignment behaviour is validated by cross-compile and code inspection only; no Windows runtime was available. This plan ships in the PR under `docs/plans/` per the repo's planning-documents rule.

---

## Execution outcome (addendum, 2026-11-08)

All six tasks landed on `feat/cross-platform-go-runtime` as nine commits on top of `dff8e07`:

- `4831a7c` — F1: `fix(platform): terminate the process group when the command context expires`
- `27bde10` — F2: `fix(verifier): refuse success when no checks are discovered`
- `46b9a5f` — F2 test-pin: `test(verifier): pin the verification-root guard's error contract`
- `e52aafb` — F3: `feat(cli): implement the supervisor loop the VM service invokes`
- `c306fa4` — F3 minors: `fix(cli): validate supervisor interval and unify tick failure logging`
- `5eb12f4` — F4: `fix(platform): create Windows processes suspended and assign the job before resuming`
- `1ed08ea` — F5: `fix(build): rebuild distribution binaries when Go inputs change`
- `0a4b847` — F6: `fix(verifier): schedule make test only when a test target is declared`
- `c0f985e` — F6 nits: `test(verifier): pin the make-test target regex colon and correct its parity comment`

Stage 3 whole-branch review of `dff8e07..c0f985e`: **CLEAN**.

Standing residuals:

- **F4 (Windows):** runtime behaviour unverified — validated by cross-compile (`GOOS=windows`) and structural/code inspection only; no Windows runtime exists in this environment.
- **F5:** the `LDFLAGS` git stamp can lag when a commit changes no Go source, and a deleted Go source file drops out of the prerequisite list without triggering a rebuild (outside the finding; recorded in Task 5).
- **F3:** the supervisor's boot-failure path is covered structurally only — no runtime exercise of a failing boot gate in the packaged-service environment.

## Stage 6 fix round (addendum, 2026-11-08)

Codex's review of the first fix head (`9916a0e`) confirmed the six original closures in-tree and raised **two new findings**, both adjudicated REAL and fixed in a second SDD round:

- **N1 (P1, thread `PRRT_kwDOVM-V9860-lSU`) — the VM service had no verification root.** The generated systemd unit set no `WorkingDirectory` and no `--root`; the bundle shipped no tree to verify. Fixed in `e5d6834`: the unit pins root `/usr/local/lib/aep/verify` (WorkingDirectory + `--root`), the bundle gains a `verify/` payload whose Makefile `test:` target is an installed-system self-check (`aep boot`, `aep info`, config readable), `install.sh` installs the payload and warns loudly if `make` is absent, and `user-data.yaml` installs `make` and stages the payload via `/tmp/aep-verify`. Permanent regression test `scripts/tests/test_package_vm.sh` in `084109f`; CI wiring (script-tests enumerates shell tests by name) plus a vacuous-pass guard in `1ab25d0`.
- **N2 (P2, thread `PRRT_kwDOVM-V9860-lSV`) — POSIX group members survived normal leader exit.** A lifecycle census of `internal/platform/process` showed the leak on both POSIX Wait leader-exit paths, while the cancellation path (F1), Windows (job-object close), and Kill are safe. Fixed in `a85087b`: POSIX Wait now terminates remaining group members on leader exit (probe, SIGTERM, bounded grace, SIGKILL), with the contract documented on Wait; fast-path guard test constants tightened in `3a33ee8` so the guard can actually catch a grace-period sleep.

Residuals from this round:

- The payload's `aep boot` leg is the third enforcement of the same 384 MiB floor (ExecStartPre and the supervisor's own per-tick gate are the other two) — defence in depth with identical semantics, kept deliberately.
- The bundle config's `AEP_MEM_PREFLIGHT_MB=512` (amd64) is not consumed by the boot gate, which uses the hard-coded 384 MiB floor (pre-existing, outside N1's scope).
- `setsid` escapees remain outside group cleanup on POSIX (documented on Wait); the Python verifier's adoptee sweep is broader and remains the parity reference.
- The docker-compose route has the same unconfigured-root defect (empty named volume at `/workspace`, no `--root`); filed as issue #126 rather than folded into this PR, as neither thread names it and the fix is a deployment-design choice.

## Stage 6 round 3 (addendum, 2026-11-08)

Codex's review of the Stage 6 head (`c2b6218`, CI 9/9 green) raised **two further findings**, both adjudicated REAL and fixed in a third SDD round:

- **N3 (P2, thread `PRRT_kwDOVM-V9860-ute`) — the Compose route had the same unconfigured-root defect as N1.** A launch-site census (5 sites) found only the Compose/Containerfile route deficient. Fixed in `215bee1` by mirroring N1 from a single source: the Containerfile's builder stage generates the bundle with `scripts/package-vm.sh`, the runtime stage installs `make`, the bundle hardware profile, and the `verify/` payload at the same pinned root, and Compose runs the supervisor with that root as `--root` and `working_dir` (a checkout mounted at `/workspace` remains a documented override). `Dockerfile` is a symlink to `Containerfile`, so the pair cannot drift; the cross-route assertions live in `scripts/tests/test_package_vm.sh` (`b10f200`), and `2297a15` makes the payload/profile modes umask-independent in the image. Issue #126 (filed for this defect before Codex raised it on the PR) is closed by this fix. Container runtime verification remains unavailable in this environment (no Docker; podman not in verified-working config) — the gate is the static plus generation-level test suite.
- **N4 (P2, thread `PRRT_kwDOVM-V9860-uth`) — receipts flattened every nonzero exit code to 1.** Fixed in `24cd595`: a per-platform `process.ExitCode` helper extracts the real status from the Wait error (real code on exit; negative signal number on POSIX signal death, matching the Python verifier's encoding; no-status errors keep the fallback 1), and the runner's non-timeout error branch uses it. The timeout contract (timed_out flag plus exit code 124) is deliberately unchanged and pinned by a test. One evidence-backed correction to the adjudication's check design: GNU make flattens a failing recipe to make's own exit status 2, so a Makefile fixture cannot produce a receipt of 3 under any correct implementation — exact-status tests therefore drive a stub executable directly, with a separate leg pinning the make path at 2.

Residuals from this round:

- Spawn failures still emit no receipt (pre-existing, outside N4's thread) — filed as issue #127.
- The Compose test pins the `--root=<path>` spelling; a future two-token rewrite of the Compose command would false-red the suite (fail-safe direction, recorded deliberately).
