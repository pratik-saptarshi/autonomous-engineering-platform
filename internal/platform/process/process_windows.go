//go:build windows

package process

import (
	"fmt"
	"os/exec"
	"time"
	"unsafe"

	"golang.org/x/sys/windows"
)

type windowsProcessGroup struct {
	cmd         *exec.Cmd
	gracePeriod time.Duration
	jobHandle   windows.Handle
}

func newPlatformProcessGroup(cmd *exec.Cmd, grace time.Duration) ProcessGroup {
	return &windowsProcessGroup{
		cmd:         cmd,
		gracePeriod: grace,
		jobHandle:   windows.InvalidHandle,
	}
}

func (p *windowsProcessGroup) Start() error {
	// Create an anonymous Win32 Job Object
	job, err := windows.CreateJobObject(nil, nil)
	if err != nil {
		return fmt.Errorf("CreateJobObject failed: %w", err)
	}

	// Set JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: when the job handle closes (or parent crashes),
	// Windows terminates every process assigned to this job object.
	info := windows.JOBOBJECT_EXTENDED_LIMIT_INFORMATION{
		BasicLimitInformation: windows.JOBOBJECT_BASIC_LIMIT_INFORMATION{
			LimitFlags: windows.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
		},
	}

	_, err = windows.SetInformationJobObject(
		job,
		windows.JobObjectExtendedLimitInformation,
		uintptr(unsafe.Pointer(&info)),
		uint32(unsafe.Sizeof(info)),
	)
	if err != nil {
		_ = windows.CloseHandle(job)
		return fmt.Errorf("SetInformationJobObject failed: %w", err)
	}

	p.jobHandle = job

	if err := p.cmd.Start(); err != nil {
		_ = windows.CloseHandle(p.jobHandle)
		p.jobHandle = windows.InvalidHandle
		return err
	}

	// Assign the child process to the Job Object
	hProcess, err := windows.OpenProcess(windows.PROCESS_SET_QUOTA|windows.PROCESS_TERMINATE, false, uint32(p.cmd.Process.Pid))
	if err != nil {
		_ = p.Kill()
		return fmt.Errorf("OpenProcess failed: %w", err)
	}
	defer windows.CloseHandle(hProcess)

	err = windows.AssignProcessToJobObject(p.jobHandle, hProcess)
	if err != nil {
		_ = p.Kill()
		return fmt.Errorf("AssignProcessToJobObject failed: %w", err)
	}

	return nil
}

func (p *windowsProcessGroup) Wait() error {
	defer func() {
		if p.jobHandle != windows.InvalidHandle {
			_ = windows.CloseHandle(p.jobHandle)
			p.jobHandle = windows.InvalidHandle
		}
	}()
	return p.cmd.Wait()
}

func (p *windowsProcessGroup) Pid() int {
	if p.cmd.Process == nil {
		return 0
	}
	return p.cmd.Process.Pid
}

func (p *windowsProcessGroup) Kill() error {
	if p.jobHandle != windows.InvalidHandle {
		// TerminateJobObject terminates all processes associated with the job object
		_ = windows.TerminateJobObject(p.jobHandle, 1)
		_ = windows.CloseHandle(p.jobHandle)
		p.jobHandle = windows.InvalidHandle
	}
	if p.cmd.Process != nil {
		_ = p.cmd.Process.Kill()
	}
	return nil
}
