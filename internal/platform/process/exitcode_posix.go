//go:build !windows

package process

import (
	"errors"
	"os/exec"
	"syscall"
)

// ExitCode extracts the exit status from an error returned by Wait,
// using the encoding the verifier's receipt format inherits from its
// Python lineage (scripts/mechanical_verify.py records the raw
// subprocess returncode): the real exit code for a process that exited
// normally, and −signum for a process killed by a signal (e.g. −9 for
// SIGKILL). ok is false when err carries no exit status at all — a nil
// error or a non-ExitError such as the context error Wait returns when
// its bounded drain expires — so callers can apply their own fallback.
func ExitCode(err error) (code int, ok bool) {
	var exitErr *exec.ExitError
	if !errors.As(err, &exitErr) {
		return 0, false
	}
	if exitErr.ProcessState == nil {
		return 0, false
	}
	if exitErr.Exited() {
		return exitErr.ExitCode(), true
	}
	if ws, isWaitStatus := exitErr.ProcessState.Sys().(syscall.WaitStatus); isWaitStatus && ws.Signaled() {
		return -int(ws.Signal()), true
	}
	return 0, false
}
