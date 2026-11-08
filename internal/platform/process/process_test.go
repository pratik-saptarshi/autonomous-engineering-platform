package process

import (
	"bytes"
	"context"
	"runtime"
	"sync"
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
