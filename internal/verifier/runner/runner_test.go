package runner

import (
	"context"
	"os"
	"path/filepath"
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
