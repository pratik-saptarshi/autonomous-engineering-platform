package main

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"
)

// TestSupervisorTick_Pass: a tick over a root whose only check passes
// (a Makefile test target that succeeds) must return nil — the boot gate
// passes on a healthy host and verification passes.
func TestSupervisorTick_Pass(t *testing.T) {
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "Makefile"), []byte("test:\n\t@true\n"), 0o644); err != nil {
		t.Fatalf("write Makefile fixture: %v", err)
	}
	if err := supervisorTick(context.Background(), dir, 0, 5*time.Second, 10*time.Second); err != nil {
		t.Fatalf("supervisorTick on passing fixture returned error: %v", err)
	}
}

// TestSupervisorTick_EmptyRootFails: a tick over an empty root discovers
// zero checks; verification refuses success without mechanical evidence,
// so the tick must return a non-nil error.
func TestSupervisorTick_EmptyRootFails(t *testing.T) {
	dir := t.TempDir()
	if err := supervisorTick(context.Background(), dir, 0, 5*time.Second, 10*time.Second); err == nil {
		t.Fatal("supervisorTick on empty root returned nil, want non-nil error")
	}
}
