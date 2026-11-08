//go:build windows

package process

import (
	"context"
	"fmt"
	"os/exec"
	"syscall"
	"time"
	"unsafe"

	"golang.org/x/sys/windows"
)

type windowsProcessGroup struct {
	cmd         *exec.Cmd
	gracePeriod time.Duration
	ctx         context.Context
	jobHandle   windows.Handle
}

func newPlatformProcessGroup(cmd *exec.Cmd, grace time.Duration, ctx context.Context) ProcessGroup {
	if cmd.SysProcAttr == nil {
		cmd.SysProcAttr = &syscall.SysProcAttr{}
	}
	// CREATE_SUSPENDED: the child's main thread is created suspended, so no
	// child code runs until Start has assigned the process to the job
	// object and resumed it — nothing the child spawns can escape the job.
	cmd.SysProcAttr.CreationFlags |= windows.CREATE_SUSPENDED

	return &windowsProcessGroup{
		cmd:         cmd,
		gracePeriod: grace,
		ctx:         ctx,
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

	// The child was created suspended (see the constructor), so no child
	// code could run before the assignment above. Now that the process is
	// inside the job, resume its main thread. If the resume fails, fail
	// closed: Kill terminates the still-suspended child via the job and
	// closes the job handle, so a suspended process is never left behind.
	if err := resumeMainThread(uint32(p.cmd.Process.Pid)); err != nil {
		_ = p.Kill()
		return fmt.Errorf("resuming the main thread failed: %w", err)
	}

	return nil
}

// resumeMainThread resumes the main thread of a process created with
// CREATE_SUSPENDED. A freshly created process has exactly one thread; it
// is located via a Toolhelp thread snapshot.
func resumeMainThread(pid uint32) error {
	snap, err := windows.CreateToolhelp32Snapshot(windows.TH32CS_SNAPTHREAD, 0)
	if err != nil {
		return fmt.Errorf("CreateToolhelp32Snapshot failed: %w", err)
	}
	if snap == windows.InvalidHandle {
		return fmt.Errorf("CreateToolhelp32Snapshot returned an invalid handle")
	}
	defer windows.CloseHandle(snap)

	var entry windows.ThreadEntry32
	entry.Size = uint32(unsafe.Sizeof(entry))
	var tid uint32
	found := false
	for err := windows.Thread32First(snap, &entry); err == nil; err = windows.Thread32Next(snap, &entry) {
		if entry.OwnerProcessID == pid {
			tid = entry.ThreadID
			found = true
			break
		}
		entry.Size = uint32(unsafe.Sizeof(entry))
	}
	if !found {
		return fmt.Errorf("no thread found for process %d", pid)
	}

	hThread, err := windows.OpenThread(windows.THREAD_SUSPEND_RESUME, false, tid)
	if err != nil {
		return fmt.Errorf("OpenThread failed: %w", err)
	}
	defer windows.CloseHandle(hThread)

	// ResumeThread reports the thread's previous suspend count; the
	// thread runs once a call reports a count of 1 (or 0 if it was not
	// suspended). Loop, bounded, in case it was suspended more than once.
	for i := 0; i < 32; i++ {
		prev, err := windows.ResumeThread(hThread)
		if err != nil {
			return fmt.Errorf("ResumeThread failed: %w", err)
		}
		if prev <= 1 {
			return nil
		}
	}
	return fmt.Errorf("thread %d still suspended after 32 resume attempts", tid)
}

func (p *windowsProcessGroup) Wait() error {
	// The deferred job-handle close is Wait's normal-completion cleanup mechanism: KILL_ON_JOB_CLOSE reaps any job members that outlived the leader.
	defer func() {
		if p.jobHandle != windows.InvalidHandle {
			_ = windows.CloseHandle(p.jobHandle)
			p.jobHandle = windows.InvalidHandle
		}
	}()
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
			// Bounded drain: a job escapee may hold the pipes open past
			// the job termination; do not block forever waiting for EOF.
			return p.ctx.Err()
		}
	}
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
