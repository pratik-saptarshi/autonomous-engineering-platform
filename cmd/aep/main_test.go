package main

import (
	"context"
	"os"
	"path/filepath"
	"strings"
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

// TestValidateSupervisorFlags: in loop mode a non-positive interval
// must be rejected (time.NewTicker would panic on it); outside loop
// mode the interval is unused and must not be rejected.
func TestValidateSupervisorFlags(t *testing.T) {
	cases := []struct {
		name     string
		loop     bool
		interval time.Duration
		wantErr  bool
	}{
		{"loop zero interval", true, 0, true},
		{"loop negative interval", true, -time.Second, true},
		{"loop positive interval", true, time.Second, false},
		{"once zero interval", false, 0, false},
		{"once negative interval", false, -time.Second, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			err := validateSupervisorFlags(tc.loop, tc.interval)
			if tc.wantErr && err == nil {
				t.Fatalf("validateSupervisorFlags(%v, %v) = nil, want error", tc.loop, tc.interval)
			}
			if !tc.wantErr && err != nil {
				t.Fatalf("validateSupervisorFlags(%v, %v) = %v, want nil", tc.loop, tc.interval, err)
			}
			if tc.wantErr && !strings.Contains(err.Error(), tc.interval.String()) {
				t.Fatalf("error %q does not name the interval %q", err, tc.interval)
			}
		})
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
