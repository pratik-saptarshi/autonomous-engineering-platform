package runner

import (
	"context"
	"os"
	"path/filepath"
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
