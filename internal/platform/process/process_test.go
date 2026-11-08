package process

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"testing"
	"time"
)

// lockedBuffer is a goroutine-safe io.Writer: the stdout/stderr copy
// goroutines write concurrently, so a plain bytes.Buffer is not safe.
type lockedBuffer struct {
	mu  sync.Mutex
	buf bytes.Buffer
}

func (b *lockedBuffer) Write(p []byte) (int, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.Write(p)
}

func TestProcessGroup_ExecutionAndKill(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	// Launch a sleep command
	pg := NewCommand(ctx, "sleep", []string{"10"}, CommandConfig{
		GracePeriod: 100 * time.Millisecond,
	})

	if err := pg.Start(); err != nil {
		t.Fatalf("pg.Start() failed: %v", err)
	}

	if pg.Pid() <= 0 {
		t.Fatalf("expected positive PID, got %d", pg.Pid())
	}

	// Immediately kill the process group
	if err := pg.Kill(); err != nil {
		t.Fatalf("pg.Kill() failed: %v", err)
	}

	_ = pg.Wait()
}

// TestProcessGroup_WaitTerminatesGroupOnTimeout pins the F1 contract: when
// the command context expires, Wait must terminate the whole process group
// and return promptly — even when a surviving child holds the output pipes
// open (a non-file writer forces the copy goroutines that used to deadlock
// cmd.Wait on pipe EOF).
func TestProcessGroup_WaitTerminatesGroupOnTimeout(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("process-group pipe semantics are POSIX-specific")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 500*time.Millisecond)
	defer cancel()

	var out lockedBuffer
	pg := NewCommand(ctx, "sh", []string{"-c", "sleep 30 & wait"}, CommandConfig{
		Stdout:      &out,
		Stderr:      &out,
		GracePeriod: 100 * time.Millisecond,
	})

	if err := pg.Start(); err != nil {
		t.Fatalf("pg.Start() failed: %v", err)
	}

	done := make(chan error, 1)
	start := time.Now()
	go func() { done <- pg.Wait() }()

	select {
	case err := <-done:
		if elapsed := time.Since(start); elapsed >= 5*time.Second {
			t.Fatalf("Wait() took %v after the 500ms context timeout; want < 5s", elapsed)
		}
		if err == nil {
			t.Fatal("Wait() returned a nil error after the context timeout; want non-nil")
		}
	case <-time.After(5 * time.Second):
		_ = pg.Kill() // cleanup: do not leak the fixture's sleep
		t.Fatal("Wait() did not return within 5s of the 500ms context timeout")
	}
}

// pidExists reports whether pid names a live process, via the signal-0
// probe: Signal(0) delivers no signal; on POSIX it succeeds while the
// process exists and fails with ESRCH once the process is gone.
func pidExists(pid int) bool {
	proc, err := os.FindProcess(pid)
	if err != nil {
		return false
	}
	return proc.Signal(syscall.Signal(0)) == nil
}

func readPidfile(path string) (int, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return 0, err
	}
	return strconv.Atoi(strings.TrimSpace(string(data)))
}

// spawnSurvivor starts a shell that backgrounds a detached-output sleep,
// records the sleep's PID in a pidfile, and exits with exitCode. It waits
// for the pidfile and confirms the child is running before returning its
// PID — the check must happen before Wait, because a correct Wait
// terminates the child before it returns. A test cleanup kills the
// recorded child either way, so even a failing run never leaks a stray
// sleep.
func spawnSurvivor(t *testing.T, exitCode int) (ProcessGroup, int) {
	t.Helper()

	pidfile := filepath.Join(t.TempDir(), "child.pid")
	t.Cleanup(func() {
		if pid, err := readPidfile(pidfile); err == nil {
			if proc, err := os.FindProcess(pid); err == nil {
				_ = proc.Kill()
			}
		}
	})

	script := fmt.Sprintf("sleep 30 >/dev/null 2>&1 & echo $! > '%s'; exit %d", pidfile, exitCode)
	pg := NewCommand(context.Background(), "sh", []string{"-c", script}, CommandConfig{
		GracePeriod: 100 * time.Millisecond,
	})
	if err := pg.Start(); err != nil {
		t.Fatalf("pg.Start() failed: %v", err)
	}

	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if pid, err := readPidfile(pidfile); err == nil {
			if !pidExists(pid) {
				t.Fatalf("background child %d is not running; fixture is broken", pid)
			}
			return pg, pid
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatal("child pidfile did not appear within 2s of Start")
	return pg, 0
}

// waitForPidGone polls until pid no longer exists (kill(pid, 0) → ESRCH).
func waitForPidGone(t *testing.T, pid int) {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if !pidExists(pid) {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("background child %d still alive 2s after Wait returned; Wait must terminate surviving group members", pid)
}

// TestProcessGroup_WaitCleansUpSurvivorsOnNormalExit pins the N2 contract:
// when the leader exits normally while background group members survive
// (output redirected, so no pipe keeps cmd.Wait alive), Wait must
// terminate the survivors before returning.
func TestProcessGroup_WaitCleansUpSurvivorsOnNormalExit(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("process-group survivor cleanup is POSIX-specific")
	}

	pg, pid := spawnSurvivor(t, 0)
	if err := pg.Wait(); err != nil {
		t.Fatalf("Wait() = %v, want nil for a leader exit of 0", err)
	}
	waitForPidGone(t, pid)
}

// TestProcessGroup_WaitCleansUpSurvivorsOnErrorExit pins the same N2
// cleanup on the nonzero-exit path: Wait returns the leader's ExitError
// and the surviving group member is still terminated.
func TestProcessGroup_WaitCleansUpSurvivorsOnErrorExit(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("process-group survivor cleanup is POSIX-specific")
	}

	pg, pid := spawnSurvivor(t, 3)
	err := pg.Wait()
	var exitErr *exec.ExitError
	if !errors.As(err, &exitErr) {
		t.Fatalf("Wait() = %v, want an *exec.ExitError for a leader exit of 3", err)
	}
	if exitErr.ExitCode() != 3 {
		t.Fatalf("Wait() exit code = %d, want 3", exitErr.ExitCode())
	}
	waitForPidGone(t, pid)
}

// TestProcessGroup_WaitFastWhenGroupEmpty guards the fast path: a
// well-behaved command with an empty group pays no grace delay in Wait.
// The configured grace (2s) is deliberately far above the 750ms elapsed
// threshold: if the ESRCH fast path regressed into an unconditional
// one-grace sleep, Wait would take the full 2s and this test would fail.
func TestProcessGroup_WaitFastWhenGroupEmpty(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("process-group survivor cleanup is POSIX-specific")
	}

	pg := NewCommand(context.Background(), "sh", []string{"-c", "exit 0"}, CommandConfig{
		GracePeriod: 2 * time.Second,
	})
	if err := pg.Start(); err != nil {
		t.Fatalf("pg.Start() failed: %v", err)
	}

	start := time.Now()
	if err := pg.Wait(); err != nil {
		t.Fatalf("Wait() = %v, want nil", err)
	}
	if elapsed := time.Since(start); elapsed >= 750*time.Millisecond {
		t.Fatalf("Wait() took %v for a command with an empty group; want < 750ms (fast path)", elapsed)
	}
}
