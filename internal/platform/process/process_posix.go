//go:build !windows

package process

import (
	"context"
	"os/exec"
	"sync/atomic"
	"syscall"
	"time"

	"golang.org/x/sys/unix"
)

type posixProcessGroup struct {
	cmd         *exec.Cmd
	gracePeriod time.Duration
	ctx         context.Context
	terminated  atomic.Bool
}

func newPlatformProcessGroup(cmd *exec.Cmd, grace time.Duration, ctx context.Context) ProcessGroup {
	if cmd.SysProcAttr == nil {
		cmd.SysProcAttr = &syscall.SysProcAttr{}
	}
	// Setpgid: true ensures the spawned process becomes leader of a new process group.
	cmd.SysProcAttr.Setpgid = true

	return &posixProcessGroup{
		cmd:         cmd,
		gracePeriod: grace,
		ctx:         ctx,
	}
}

func (p *posixProcessGroup) Start() error {
	return p.cmd.Start()
}

func (p *posixProcessGroup) Wait() error {
	done := make(chan error, 1)
	go func() { done <- p.cmd.Wait() }()
	select {
	case err := <-done:
		return err
	case <-p.ctx.Done():
		_ = p.Kill()
		select {
		case err := <-done:
			return err
		case <-time.After(p.gracePeriod + 2*time.Second):
			// Bounded drain: a group escapee may hold the pipes open past
			// the group kill; do not block forever waiting for EOF.
			return p.ctx.Err()
		}
	}
}

func (p *posixProcessGroup) Pid() int {
	if p.cmd.Process == nil {
		return 0
	}
	return p.cmd.Process.Pid
}

func (p *posixProcessGroup) Kill() error {
	if p.cmd.Process == nil {
		return nil
	}
	if p.terminated.Swap(true) {
		// Already terminated: idempotent no-op.
		return nil
	}
	pid := p.cmd.Process.Pid
	// Signal negative PID to terminate the entire process group (leader + children)
	pgid := pid

	// Step 1: SIGTERM the whole process group
	_ = unix.Kill(-pgid, syscall.SIGTERM)

	// Step 2: Grace period
	time.Sleep(p.gracePeriod)

	// Step 3: SIGKILL any stubborn survivors
	_ = unix.Kill(-pgid, syscall.SIGKILL)

	return nil
}
