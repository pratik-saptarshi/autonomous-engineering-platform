package runner

import (
	"context"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"testing"
	"time"
)

func TestTailCappedBuffer(t *testing.T) {
	buf := NewTailCappedBuffer(10)
	_, _ = buf.Write([]byte("12345"))
	if string(buf.Bytes()) != "12345" {
		t.Fatalf("expected '12345', got '%s'", string(buf.Bytes()))
	}

	_, _ = buf.Write([]byte("67890ABCDE"))
	if string(buf.Bytes()) != "67890ABCDE" {
		t.Fatalf("expected '67890ABCDE', got '%s'", string(buf.Bytes()))
	}

	_, _ = buf.Write([]byte("XYZ"))
	if string(buf.Bytes()) != "90ABCDEXYZ" {
		t.Fatalf("expected '90ABCDEXYZ', got '%s'", string(buf.Bytes()))
	}
}

func TestDiscoverCommands(t *testing.T) {
	tmpDir := t.TempDir()

	// Initially empty: 0 commands discovered
	cmds, err := DiscoverCommands(tmpDir)
	if err != nil {
		t.Fatalf("DiscoverCommands failed: %v", err)
	}
	if len(cmds) != 0 {
		t.Fatalf("expected 0 commands, got %d", len(cmds))
	}

	// Create go.mod
	_ = os.WriteFile(filepath.Join(tmpDir, "go.mod"), []byte("module test\n"), 0644)
	cmds, err = DiscoverCommands(tmpDir)
	if err != nil {
		t.Fatalf("DiscoverCommands failed: %v", err)
	}
	if len(cmds) != 1 || cmds[0].ID != "go-test" {
		t.Fatalf("expected go-test command, got %+v", cmds)
	}
}

func TestDiscoverCommands_MakeTarget(t *testing.T) {
	hasMakeTest := func(cmds []DiscoveredCommand) bool {
		for _, c := range cmds {
			if c.ID == "make-test" {
				return true
			}
		}
		return false
	}

	// (a) Makefile with only a build target: make-test must NOT be scheduled.
	buildOnly := t.TempDir()
	_ = os.WriteFile(filepath.Join(buildOnly, "Makefile"), []byte("build:\n\t@true\n"), 0644)
	cmds, err := DiscoverCommands(buildOnly)
	if err != nil {
		t.Fatalf("DiscoverCommands failed: %v", err)
	}
	if hasMakeTest(cmds) {
		t.Fatalf("expected no make-test for a build-only Makefile, got %+v", cmds)
	}

	// (b) Makefile with a test target: make-test must be scheduled.
	withTest := t.TempDir()
	_ = os.WriteFile(filepath.Join(withTest, "Makefile"), []byte("test:\n\t@true\n"), 0644)
	cmds, err = DiscoverCommands(withTest)
	if err != nil {
		t.Fatalf("DiscoverCommands failed: %v", err)
	}
	if !hasMakeTest(cmds) {
		t.Fatalf("expected make-test for a Makefile with a test target, got %+v", cmds)
	}

	// (c) Makefile whose only test-like line is a testify: target (plus a
	// normal build target): the regex's colon pins the match to a real
	// test: target, so make-test must NOT be scheduled.
	testifyOnly := t.TempDir()
	_ = os.WriteFile(filepath.Join(testifyOnly, "Makefile"), []byte("build:\n\t@true\n\ntestify:\n\t@true\n"), 0644)
	cmds, err = DiscoverCommands(testifyOnly)
	if err != nil {
		t.Fatalf("DiscoverCommands failed: %v", err)
	}
	if hasMakeTest(cmds) {
		t.Fatalf("expected no make-test for a Makefile with only a testify: target, got %+v", cmds)
	}
}

func TestRunVerification_Pass(t *testing.T) {
	tmpDir := t.TempDir()
	// Create a dummy Makefile with a passing test target
	makefile := "test:\n\t@echo 'all tests pass'\n"
	_ = os.WriteFile(filepath.Join(tmpDir, "Makefile"), []byte(makefile), 0644)

	res, err := RunVerification(context.Background(), tmpDir, 0, 5*time.Second, 10*time.Second)
	if err != nil {
		t.Fatalf("RunVerification failed: %v", err)
	}
	if !res.Pass {
		t.Fatalf("expected verification to pass, got %+v", res)
	}
	if len(res.Receipts) != 1 {
		t.Fatalf("expected 1 receipt, got %d", len(res.Receipts))
	}
	if res.Receipts[0].ExitCode != 0 {
		t.Fatalf("expected exit code 0, got %d", res.Receipts[0].ExitCode)
	}
}

// TestRunVerification_PreservesExitCode pins the N4 contract: a check
// command exiting with a nonzero status other than 1 must have that
// actual status recorded in its receipt, not a flattened 1 — consumers
// of the receipt distinguish e.g. pytest's exit 2 (collection error)
// from an ordinary test failure. A stub python3 whose exit status the
// test controls stands in for the discovered pytest command: the stub
// IS the executed command, so its status is what the receipt must
// record. (A make fixture cannot serve here — GNU make flattens any
// failing recipe to make's own exit status 2; see the next test.)
func TestRunVerification_PreservesExitCode(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("fixture uses a POSIX shell stub for python3")
	}

	stubDir := t.TempDir()
	stub := "#!/bin/sh\nexit \"$AEP_STUB_EXIT\"\n"
	if err := os.WriteFile(filepath.Join(stubDir, "python3"), []byte(stub), 0o755); err != nil {
		t.Fatalf("failed to write python3 stub: %v", err)
	}
	t.Setenv("PATH", stubDir+string(os.PathListSeparator)+os.Getenv("PATH"))

	for _, want := range []int{2, 3} {
		t.Setenv("AEP_STUB_EXIT", strconv.Itoa(want))
		tmpDir := t.TempDir()
		if err := os.WriteFile(filepath.Join(tmpDir, "pyproject.toml"), []byte("[project]\nname = \"fixture\"\n"), 0o644); err != nil {
			t.Fatalf("failed to write fixture: %v", err)
		}

		res, err := RunVerification(context.Background(), tmpDir, 0, 5*time.Second, 10*time.Second)
		if err != nil {
			t.Fatalf("exit %d: RunVerification failed: %v", want, err)
		}
		if res.Pass {
			t.Fatalf("exit %d: expected verification to fail, got %+v", want, res)
		}
		if len(res.Receipts) != 1 {
			t.Fatalf("exit %d: expected 1 receipt, got %d", want, len(res.Receipts))
		}
		if res.Receipts[0].ExitCode != want {
			t.Fatalf("exit %d: expected receipt exit code %d, got %d", want, want, res.Receipts[0].ExitCode)
		}
		if res.Receipts[0].TimedOut {
			t.Fatalf("exit %d: expected receipt TimedOut=false, got %+v", want, res.Receipts[0])
		}
	}
}

// TestRunVerification_MakeFailureRecordsMakeStatus pins the receipt
// contract on the make-test path: the receipt records the executed
// command's real status. A recipe exiting 3 makes GNU make itself exit
// 2 — make flattens recipe failures to its own status — so the receipt
// is 2 (before the N4 fix it was a further-flattened 1). Preservation
// of a direct command's exact status is pinned by
// TestRunVerification_PreservesExitCode above and by the process
// package's TestExitCode_NormalExit.
func TestRunVerification_MakeFailureRecordsMakeStatus(t *testing.T) {
	tmpDir := t.TempDir()
	_ = os.WriteFile(filepath.Join(tmpDir, "Makefile"), []byte("test:\n\t@exit 3\n"), 0644)

	res, err := RunVerification(context.Background(), tmpDir, 0, 5*time.Second, 10*time.Second)
	if err != nil {
		t.Fatalf("RunVerification failed: %v", err)
	}
	if res.Pass {
		t.Fatalf("expected verification to fail, got %+v", res)
	}
	if len(res.Receipts) != 1 {
		t.Fatalf("expected 1 receipt, got %d", len(res.Receipts))
	}
	if res.Receipts[0].ExitCode != 2 {
		t.Fatalf("expected receipt exit code 2 (GNU make's status for a failed recipe), got %d", res.Receipts[0].ExitCode)
	}
}

// TestRunVerification_TimeoutContract pins the timeout branch the N4
// fix must not disturb: a command killed by the per-command deadline
// records TimedOut=true and the conventional exit code 124, never the
// kill signal's status.
func TestRunVerification_TimeoutContract(t *testing.T) {
	tmpDir := t.TempDir()
	_ = os.WriteFile(filepath.Join(tmpDir, "Makefile"), []byte("test:\n\t@sleep 5\n"), 0644)

	res, err := RunVerification(context.Background(), tmpDir, 0, 300*time.Millisecond, 10*time.Second)
	if err != nil {
		t.Fatalf("RunVerification failed: %v", err)
	}
	if res.Pass {
		t.Fatalf("expected verification to fail on timeout, got %+v", res)
	}
	if len(res.Receipts) != 1 {
		t.Fatalf("expected 1 receipt, got %d", len(res.Receipts))
	}
	if !res.Receipts[0].TimedOut {
		t.Fatalf("expected receipt TimedOut=true, got %+v", res.Receipts[0])
	}
	if res.Receipts[0].ExitCode != 124 {
		t.Fatalf("expected receipt exit code 124 for a timeout, got %d", res.Receipts[0].ExitCode)
	}
}

func TestRunVerification_NonexistentRoot(t *testing.T) {
	root := filepath.Join(t.TempDir(), "does-not-exist")
	res, err := RunVerification(context.Background(), root, 0, 5*time.Second, 10*time.Second)
	if err == nil {
		t.Fatalf("expected error for nonexistent root, got nil")
	}
	if res != nil {
		t.Fatalf("expected nil result for nonexistent root, got %+v", res)
	}
	if !strings.Contains(err.Error(), "does not exist or is not a directory") {
		t.Fatalf("expected root-guard error for nonexistent root, got: %v", err)
	}
}

func TestRunVerification_FileRoot(t *testing.T) {
	root := filepath.Join(t.TempDir(), "a-regular-file")
	if err := os.WriteFile(root, []byte("not a directory\n"), 0o644); err != nil {
		t.Fatalf("failed to write fixture: %v", err)
	}
	res, err := RunVerification(context.Background(), root, 0, 5*time.Second, 10*time.Second)
	if err == nil {
		t.Fatalf("expected error for regular-file root, got nil")
	}
	if res != nil {
		t.Fatalf("expected nil result for regular-file root, got %+v", res)
	}
	if !strings.Contains(err.Error(), "does not exist or is not a directory") {
		t.Fatalf("expected root-guard error for regular-file root, got: %v", err)
	}
}

func TestRunVerification_EmptyDirNoChecks(t *testing.T) {
	res, err := RunVerification(context.Background(), t.TempDir(), 0, 5*time.Second, 10*time.Second)
	if err == nil {
		t.Fatalf("expected error when zero checks are discovered, got nil")
	}
	if res != nil && res.Pass {
		t.Fatalf("expected Pass=false when zero checks are discovered, got Pass=true")
	}
}

func TestRunVerification_UnsupportedProject(t *testing.T) {
	tmpDir := t.TempDir()
	if err := os.WriteFile(filepath.Join(tmpDir, "README.md"), []byte("# nothing to verify\n"), 0o644); err != nil {
		t.Fatalf("failed to write fixture: %v", err)
	}
	res, err := RunVerification(context.Background(), tmpDir, 0, 5*time.Second, 10*time.Second)
	if err == nil {
		t.Fatalf("expected error for unsupported project with zero checks, got nil")
	}
	if res != nil && res.Pass {
		t.Fatalf("expected Pass=false for unsupported project, got Pass=true")
	}
}

// TestRunVerification_SpawnFailureRecordsReceipt pins the N7 contract:
// a discovered command that cannot be STARTED (here: cargo, made
// unfindable on any host by shadowing PATH with an empty directory)
// must still produce a receipt — exit code 127 with the launch error
// preserved — and must count as executed, so Executed == len(Receipts)
// holds and a missing tool is diagnosable from the receipts. Before
// the fix this yielded discovered=1 executed=0 failed=1 receipts=0.
// RunVerification's error stays nil: a failed check is (result, nil),
// like every other check failure.
func TestRunVerification_SpawnFailureRecordsReceipt(t *testing.T) {
	tmpDir := t.TempDir()
	cargoToml := "[package]\nname = \"fixture\"\nversion = \"0.1.0\"\nedition = \"2021\"\n"
	if err := os.WriteFile(filepath.Join(tmpDir, "Cargo.toml"), []byte(cargoToml), 0o644); err != nil {
		t.Fatalf("failed to write fixture: %v", err)
	}
	t.Setenv("PATH", t.TempDir()) // empty: cargo unfindable even where installed

	res, err := RunVerification(context.Background(), tmpDir, 0, 5*time.Second, 10*time.Second)
	if err != nil {
		t.Fatalf("RunVerification failed: %v", err)
	}
	if res.Pass {
		t.Fatalf("expected verification to fail, got %+v", res)
	}
	if res.Discovered != 1 || res.Executed != 1 || res.Failed != 1 {
		t.Fatalf("expected discovered=1 executed=1 failed=1, got discovered=%d executed=%d failed=%d",
			res.Discovered, res.Executed, res.Failed)
	}
	if len(res.Receipts) != 1 {
		t.Fatalf("expected 1 receipt, got %d", len(res.Receipts))
	}
	r := res.Receipts[0]
	if r.CommandID != "cargo-test" {
		t.Fatalf("expected receipt for cargo-test, got %q", r.CommandID)
	}
	if r.ExitCode != 127 {
		t.Fatalf("expected receipt exit code 127 for a launch failure, got %d", r.ExitCode)
	}
	if r.TimedOut {
		t.Fatalf("expected receipt TimedOut=false, got %+v", r)
	}
	if r.Error == "" || !strings.Contains(r.Error, "cargo") {
		t.Fatalf("expected receipt Error to preserve the launch error mentioning cargo, got %q", r.Error)
	}
}

// TestRunVerification_SpawnFailureStopsRun pins the second half of the
// N7 contract: a launch failure stops the run, like every other check
// failure — later discovered commands are not attempted. Discovery
// order relied on (DiscoverCommands' pinned order): cargo-test (from
// Cargo.toml, step 2) precedes make-test (from a Makefile test target,
// step 5), so with both markers present cargo is attempted first; the
// single receipt proves make-test never ran.
func TestRunVerification_SpawnFailureStopsRun(t *testing.T) {
	tmpDir := t.TempDir()
	cargoToml := "[package]\nname = \"fixture\"\nversion = \"0.1.0\"\nedition = \"2021\"\n"
	if err := os.WriteFile(filepath.Join(tmpDir, "Cargo.toml"), []byte(cargoToml), 0o644); err != nil {
		t.Fatalf("failed to write fixture: %v", err)
	}
	if err := os.WriteFile(filepath.Join(tmpDir, "Makefile"), []byte("test:\n\t@echo 'all tests pass'\n"), 0o644); err != nil {
		t.Fatalf("failed to write fixture: %v", err)
	}
	t.Setenv("PATH", t.TempDir()) // empty: cargo unfindable even where installed

	res, err := RunVerification(context.Background(), tmpDir, 0, 5*time.Second, 10*time.Second)
	if err != nil {
		t.Fatalf("RunVerification failed: %v", err)
	}
	if res.Discovered != 2 {
		t.Fatalf("expected 2 discovered commands, got %d", res.Discovered)
	}
	if res.Executed != 1 || res.Failed != 1 {
		t.Fatalf("expected executed=1 failed=1 (run stopped at the launch failure), got executed=%d failed=%d",
			res.Executed, res.Failed)
	}
	if len(res.Receipts) != 1 || res.Receipts[0].CommandID != "cargo-test" {
		t.Fatalf("expected exactly the cargo-test receipt, got %+v", res.Receipts)
	}
}

// TestRunVerification_FallbackReceiptRecordsWaitError pins the
// error-text half of the N4 fallback: when Wait returns an error that
// carries no exit status, the runner records exit code 1 AND preserves
// the error's text in the receipt's Error field (the N7 receipt
// contract — a failure with no record of its cause is not
// diagnosable).
//
// Reaching that fallback through the public surface requires care,
// because the per-command timeout branch claims most Wait errors
// first. The route used here:
//
//   - The PARENT context is canceled (250ms in), not the per-command
//     deadline, so cmdCtx.Err() is context.Canceled and the timeout
//     branch's DeadlineExceeded check cannot intercept. The generous
//     per-command timeout (30s) and total budget (60s) likewise stay
//     out of the way.
//   - The fixture's recipe backgrounds a setsid sleeper. setsid puts
//     it in a new session, out of reach of the process-group kill,
//     and it inherits the command's output pipes — so after the group
//     is killed, cmd.Wait still blocks on the pipes until Wait's
//     bounded drain (750ms kill grace + 2s) expires and Wait returns
//     the context error itself: a non-ExitError, which is exactly
//     what process.ExitCode reports as (0, false), selecting the
//     fallback.
//
// The ~3.75s wall time is inherent to that route (250ms to the
// cancel, then the drain) and is paid once. Cancellation timing is
// not racy: the cancel lands long after process start and long
// before drain expiry.
func TestRunVerification_FallbackReceiptRecordsWaitError(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("fixture relies on POSIX setsid and output-pipe semantics")
	}

	tmpDir := t.TempDir()
	makefile := "test:\n\t@setsid sleep 8 & sleep 8\n"
	if err := os.WriteFile(filepath.Join(tmpDir, "Makefile"), []byte(makefile), 0o644); err != nil {
		t.Fatalf("failed to write fixture: %v", err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	time.AfterFunc(250*time.Millisecond, cancel)

	res, err := RunVerification(ctx, tmpDir, 0, 30*time.Second, 60*time.Second)
	if err != nil {
		t.Fatalf("RunVerification failed: %v", err)
	}
	if res.Pass {
		t.Fatalf("expected verification to fail, got %+v", res)
	}
	if res.Discovered != 1 || res.Executed != 1 || res.Failed != 1 {
		t.Fatalf("expected discovered=1 executed=1 failed=1, got discovered=%d executed=%d failed=%d",
			res.Discovered, res.Executed, res.Failed)
	}
	if len(res.Receipts) != 1 {
		t.Fatalf("expected 1 receipt, got %d", len(res.Receipts))
	}
	r := res.Receipts[0]
	if r.CommandID != "make-test" {
		t.Fatalf("expected receipt for make-test, got %q", r.CommandID)
	}
	if r.ExitCode != 1 {
		t.Fatalf("expected receipt exit code 1 (no-status fallback), got %d", r.ExitCode)
	}
	if r.TimedOut {
		t.Fatalf("expected receipt TimedOut=false (parent cancellation is not the per-command deadline), got %+v", r)
	}
	if r.Error != "context canceled" {
		t.Fatalf("expected receipt Error to preserve the Wait error text, got %q", r.Error)
	}
}

// pidAlive reports whether pid names a live process, via the
// signal-0 probe: Signal(0) delivers no signal and succeeds while
// the process exists.
func pidAlive(pid int) bool {
	return pid > 0 && syscall.Kill(pid, 0) == nil
}

// cancelDuringDrain runs RunVerification against a Makefile fixture
// whose recipe backgrounds a 30s sleeper in the command's own
// process group (so the sleeper inherits — and holds open — the
// command's output pipes) and then exits with the given status. It
// waits for the recipe to start, confirms the run is still blocked
// in Wait's drain with the pipe-holder alive, then cancels the
// parent context and returns the finished result and the holder's
// PID.
//
// The drain window is the sleeper's full 30s and the cancel lands
// 300ms after the recipe's ready flag appears — the leader exits
// microseconds after the flag — so the cancel lands deep inside the
// window on both sides and cannot race the drain's natural end. The
// per-command timeout (60s) and total budget (120s) are set far
// beyond the window so no timer can impersonate the cancel. Every
// fixture failure is a loud t.Fatal, never a vacuous pass.
func cancelDuringDrain(t *testing.T, recipeExit int) (*VerificationResult, error, int) {
	t.Helper()

	tmpDir := t.TempDir()
	makefile := "test:\n\t@touch ready.flag; sleep 30 & echo $$! > holder.pid; exit " +
		strconv.Itoa(recipeExit) + "\n"
	if err := os.WriteFile(filepath.Join(tmpDir, "Makefile"), []byte(makefile), 0o644); err != nil {
		t.Fatalf("failed to write fixture: %v", err)
	}

	holderPid := func() int {
		data, err := os.ReadFile(filepath.Join(tmpDir, "holder.pid"))
		if err != nil {
			return 0
		}
		pid, err := strconv.Atoi(strings.TrimSpace(string(data)))
		if err != nil {
			return 0
		}
		return pid
	}
	// Never leak the 30s sleeper, whatever the test outcome. The
	// production group kill is expected to reap it; this is the
	// backstop, by exact PID.
	t.Cleanup(func() {
		if pid := holderPid(); pidAlive(pid) {
			_ = syscall.Kill(pid, syscall.SIGKILL)
		}
	})

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	type outcome struct {
		res *VerificationResult
		err error
	}
	done := make(chan outcome, 1)
	go func() {
		res, err := RunVerification(ctx, tmpDir, 0, 60*time.Second, 120*time.Second)
		done <- outcome{res, err}
	}()

	deadline := time.Now().Add(5 * time.Second)
	for {
		if _, err := os.Stat(filepath.Join(tmpDir, "ready.flag")); err == nil {
			break
		}
		select {
		case out := <-done:
			t.Fatalf("RunVerification returned before the fixture started: res=%+v err=%v", out.res, out.err)
		default:
		}
		if time.Now().After(deadline) {
			t.Fatal("fixture recipe never started (ready.flag missing after 5s); probe could not run")
		}
		time.Sleep(10 * time.Millisecond)
	}
	time.Sleep(300 * time.Millisecond)

	select {
	case out := <-done:
		t.Fatalf("RunVerification returned before cancellation (res=%+v err=%v); the drain was not in progress, so this test would prove nothing", out.res, out.err)
	default:
	}
	if pid := holderPid(); !pidAlive(pid) {
		t.Fatalf("pipe-holding child (pid %d) is not alive before cancel; fixture is broken", pid)
	}

	cancel()
	select {
	case out := <-done:
		return out.res, out.err, holderPid()
	case <-time.After(15 * time.Second):
		t.Fatal("RunVerification did not return within 15s of cancellation")
		return nil, nil, 0
	}
}

// assertHolderDead polls briefly for the pipe-holder to disappear:
// the cancellation's process-group kill must have reaped it before
// Wait returned, so anything beyond a short reap lag is a leak.
func assertHolderDead(t *testing.T, pid int) {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for pidAlive(pid) {
		if time.Now().After(deadline) {
			t.Fatalf("pipe-holding child %d still alive after the run returned; the group kill did not reap it", pid)
		}
		time.Sleep(10 * time.Millisecond)
	}
}

// TestRunVerification_CancelDuringDrainRecordsFailure pins N10: a
// command whose leader exits 0 while an in-group background child
// holds the output pipes must NOT record a successful receipt when
// the parent context is canceled during Wait's drain.
//
// The route: the leader is reaped with exit 0 before the cancel
// lands, so the stdlib injects no context error into cmd.Wait —
// once the cancellation's group kill reaps the pipe-holder and the
// pipes reach EOF, Wait returns nil. Without a dedicated arm, the
// runner's receipt logic sees waitErr == nil on a non-deadline
// context and falls through to a success receipt, and an
// interrupted `aep verify` reports PASS. The deadline-during-drain
// control case has always recorded 124; explicit cancellation must
// record the same no-status failure shape the bounded-drain
// fallback produces for the setsid case: exit 1, TimedOut=false,
// Error "context canceled".
func TestRunVerification_CancelDuringDrainRecordsFailure(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("fixture relies on POSIX process-group and output-pipe semantics")
	}

	res, err, holder := cancelDuringDrain(t, 0)
	if err != nil {
		t.Fatalf("RunVerification failed: %v (a failed check is a result, not an error)", err)
	}
	if res == nil {
		t.Fatal("RunVerification returned a nil result")
	}
	if res.Pass {
		t.Fatalf("expected verification to fail when cancellation ends the drain, got PASS: %+v", res)
	}
	if res.Discovered != 1 || res.Executed != 1 || res.Failed != 1 {
		t.Fatalf("expected discovered=1 executed=1 failed=1, got discovered=%d executed=%d failed=%d",
			res.Discovered, res.Executed, res.Failed)
	}
	if len(res.Receipts) != 1 {
		t.Fatalf("expected 1 receipt, got %d", len(res.Receipts))
	}
	r := res.Receipts[0]
	if r.CommandID != "make-test" {
		t.Fatalf("expected receipt for make-test, got %q", r.CommandID)
	}
	if r.ExitCode != 1 {
		t.Fatalf("expected receipt exit code 1 (cancellation failure), got %d", r.ExitCode)
	}
	if r.TimedOut {
		t.Fatalf("expected receipt TimedOut=false (parent cancellation is not the per-command deadline), got %+v", r)
	}
	if r.Error != "context canceled" {
		t.Fatalf("expected receipt Error \"context canceled\", got %q", r.Error)
	}
	assertHolderDead(t, holder)
}

// TestRunVerification_CancelDuringDrainKeepsRealExitCode pins the
// ordering around the N10 arm: cancellation must guard ONLY the
// success-shaped path. When the command's leader exits nonzero on
// its own (the recipe exits 3; GNU make flattens its own failures
// to exit status 2, and make is the executed command) and a cancel
// lands during the same drain, the receipt keeps the real exit
// code with no error text — the N4 contract — instead of being
// rewritten to the cancellation failure. The run still fails.
func TestRunVerification_CancelDuringDrainKeepsRealExitCode(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("fixture relies on POSIX process-group and output-pipe semantics")
	}

	res, err, holder := cancelDuringDrain(t, 3)
	if err != nil {
		t.Fatalf("RunVerification failed: %v (a failed check is a result, not an error)", err)
	}
	if res == nil {
		t.Fatal("RunVerification returned a nil result")
	}
	if res.Pass {
		t.Fatalf("expected verification to fail, got PASS: %+v", res)
	}
	if res.Discovered != 1 || res.Executed != 1 || res.Failed != 1 {
		t.Fatalf("expected discovered=1 executed=1 failed=1, got discovered=%d executed=%d failed=%d",
			res.Discovered, res.Executed, res.Failed)
	}
	if len(res.Receipts) != 1 {
		t.Fatalf("expected 1 receipt, got %d", len(res.Receipts))
	}
	r := res.Receipts[0]
	if r.CommandID != "make-test" {
		t.Fatalf("expected receipt for make-test, got %q", r.CommandID)
	}
	if r.ExitCode != 2 {
		t.Fatalf("expected receipt exit code 2 (make's own failure status, preserved), got %d", r.ExitCode)
	}
	if r.TimedOut {
		t.Fatalf("expected receipt TimedOut=false, got %+v", r)
	}
	if r.Error != "" {
		t.Fatalf("expected receipt Error to stay empty for a real exit status, got %q", r.Error)
	}
	assertHolderDead(t, holder)
}
