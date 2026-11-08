package runner

import (
	"context"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
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
