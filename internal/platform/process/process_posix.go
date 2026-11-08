//go:build !windows

package process

import (
	"context"
	"errors"
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
		// The leader exited on its own (any exit code). Terminate any
		// group members that outlived it before returning, per Wait's
		// contract: when Wait returns, nothing in the group is running.
		p.terminateRemaining()
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

// terminateRemaining terminates any group members that outlived the
// leader. It claims the terminated flag up front, so a later Kill is a
// no-op (termination has already been handled here). Members that
// escaped the group beforehand (setsid) are out of reach.
func (p *posixProcessGroup) terminateRemaining() {
	if p.cmd.Process == nil {
		return
	}
	if p.terminated.Swap(true) {
		// Termination already handled (e.g. Kill ran): nothing to do.
		return
	}
	pgid := p.cmd.Process.Pid

	// Fast path: probe the group with signal 0. If it is already empty
	// (ESRCH), a well-behaved command pays one syscall and no grace delay.
	if err := unix.Kill(-pgid, 0); errors.Is(err, unix.ESRCH) {
		return
	}

	// SIGTERM the survivors, then poll for the group to empty.
	_ = unix.Kill(-pgid, syscall.SIGTERM)
	deadline := time.Now().Add(p.gracePeriod)
	for time.Now().Before(deadline) {
		if err := unix.Kill(-pgid, 0); errors.Is(err, unix.ESRCH) {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}

	// SIGKILL any stubborn survivors.
	_ = unix.Kill(-pgid, syscall.SIGKILL)
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
