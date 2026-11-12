//go:build windows

package process

import (
	"errors"
	"os/exec"
)

// ExitCode extracts the exit status from an error returned by Wait:
// the real exit code for a process that exited. Windows has no
// signal-death encoding — a terminated process reports a termination
// code as its exit code — so the −signum leg of the POSIX encoding
// never arises. ok is false when err carries no exit status at all —
// a nil error or a non-ExitError such as the context error Wait
// returns when its bounded drain expires — so callers can apply
// their own fallback.
func ExitCode(err error) (code int, ok bool) {
	var exitErr *exec.ExitError
	if !errors.As(err, &exitErr) {
		return 0, false
	}
	if exitErr.ProcessState == nil {
		return 0, false
	}
	return exitErr.ExitCode(), true
}
