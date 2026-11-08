package process

import (
	"context"
	"io"
	"os/exec"
	"time"
)

// ProcessGroup wraps an OS command executed with full hierarchy tracking and bounded execution.
type ProcessGroup interface {
	// Start starts the command within an isolated execution boundary (Job Object / PGID).
	Start() error
	// Wait waits for completion or context cancellation.
	Wait() error
	// Kill terminates the entire process tree including any detached children.
	Kill() error
	// Pid returns the leader process PID.
	Pid() int
}

// CommandConfig options for starting a bounded process group.
type CommandConfig struct {
	Dir         string
	Env         []string
	Stdout      io.Writer
	Stderr      io.Writer
	Timeout     time.Duration
	GracePeriod time.Duration
}

// NewCommand prepares a command bounded to a process group across platforms.
func NewCommand(ctx context.Context, name string, args []string, cfg CommandConfig) ProcessGroup {
	cmd := exec.CommandContext(ctx, name, args...)
	if cfg.Dir != "" {
		cmd.Dir = cfg.Dir
	}
	if len(cfg.Env) > 0 {
		cmd.Env = cfg.Env
	}
	cmd.Stdout = cfg.Stdout
	cmd.Stderr = cfg.Stderr

	grace := cfg.GracePeriod
	if grace == 0 {
		grace = 750 * time.Millisecond
	}

	return newPlatformProcessGroup(cmd, grace)
}
