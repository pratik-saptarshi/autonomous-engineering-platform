//go:build !windows

package process

import (
	"os/exec"
	"syscall"
	"time"

	"golang.org/x/sys/unix"
)

type posixProcessGroup struct {
	cmd         *exec.Cmd
	gracePeriod time.Duration
}

func newPlatformProcessGroup(cmd *exec.Cmd, grace time.Duration) ProcessGroup {
	if cmd.SysProcAttr == nil {
		cmd.SysProcAttr = &syscall.SysProcAttr{}
	}
	// Setpgid: true ensures the spawned process becomes leader of a new process group.
	cmd.SysProcAttr.Setpgid = true

	return &posixProcessGroup{
		cmd:         cmd,
		gracePeriod: grace,
	}
}

func (p *posixProcessGroup) Start() error {
	return p.cmd.Start()
}

func (p *posixProcessGroup) Wait() error {
	return p.cmd.Wait()
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
