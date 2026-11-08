package process

import (
	"context"
	"testing"
	"time"
)

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
