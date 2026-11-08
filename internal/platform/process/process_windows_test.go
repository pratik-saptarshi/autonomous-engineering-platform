//go:build windows

package process

import (
	"context"
	"os/exec"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"

	"golang.org/x/sys/windows"
)

// TestNewPlatformProcessGroup_BatchWrapWiring pins the constructor half
// of the N9 contract: newPlatformProcessGroup must route a batch-file
// target (.cmd/.bat) through the command interpreter before Start, so
// CreateProcess is handed cmd.exe instead of the shim. TestBatchWrap
// covers the pure transformation on every platform; this test covers
// the wiring — that the Windows constructor actually applies it to the
// *exec.Cmd it was given. Without it, deleting the constructor hook
// would leave every Linux-runnable gate green while Windows launches
// of npm (npm.cmd) silently broke again.
//
// The *exec.Cmd values are built by hand rather than via exec.Command
// so the fixture does not depend on the host's Node.js install or
// PATHEXT resolution. The constructor is a safe seam for this: it only
// reads cmd.Path/cmd.Args and sets cmd.SysProcAttr — the job object is
// created in Start, which this test never calls, so no process is
// started and no handle is created.
func TestNewPlatformProcessGroup_BatchWrapWiring(t *testing.T) {
	const npmCmd = `C:\Program Files\nodejs\npm.cmd`
	tests := []struct {
		name     string
		path     string
		args     []string
		wantPath string   // exact expectation when wantWrap is false
		wantArgs []string // exact expectation in all cases
		wantWrap bool
	}{
		{
			name:     "cmd shim is routed through the interpreter",
			path:     npmCmd,
			args:     []string{"npm", "test"},
			wantArgs: []string{"cmd", "/c", npmCmd, "test"},
			wantWrap: true,
		},
		{
			name:     "bat shim is routed through the interpreter",
			path:     `C:\tools\build.bat`,
			args:     []string{"build", "a", "b"},
			wantArgs: []string{"cmd", "/c", `C:\tools\build.bat`, "a", "b"},
			wantWrap: true,
		},
		{
			name:     "native exe passes through unchanged",
			path:     `C:\Program Files\nodejs\node.exe`,
			args:     []string{"node", "--version"},
			wantPath: `C:\Program Files\nodejs\node.exe`,
			wantArgs: []string{"node", "--version"},
			wantWrap: false,
		},
		{
			name:     "extensionless target passes through unchanged",
			path:     `C:\Program Files\nodejs\npm`,
			args:     []string{"npm", "test"},
			wantPath: `C:\Program Files\nodejs\npm`,
			wantArgs: []string{"npm", "test"},
			wantWrap: false,
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			cmd := &exec.Cmd{Path: tc.path, Args: append([]string(nil), tc.args...)}

			_ = newPlatformProcessGroup(cmd, time.Second, context.Background())

			// Prove the constructor actually ran on this cmd: it always
			// marks the child CREATE_SUSPENDED (the F4 contract), in
			// both the wrapped and pass-through cases.
			if cmd.SysProcAttr == nil || cmd.SysProcAttr.CreationFlags&windows.CREATE_SUSPENDED == 0 {
				t.Fatalf("constructor did not run: SysProcAttr = %+v, want CREATE_SUSPENDED set", cmd.SysProcAttr)
			}
			if !reflect.DeepEqual(cmd.Args, tc.wantArgs) {
				t.Fatalf("cmd.Args = %v, want %v", cmd.Args, tc.wantArgs)
			}
			if tc.wantWrap {
				// The constructor replaces the batch path with the
				// interpreter: "cmd" itself, or its LookPath resolution
				// (C:\Windows\System32\cmd.exe on a standard host).
				if cmd.Path == tc.path {
					t.Fatalf("cmd.Path = %q, want the command interpreter, not the batch shim", cmd.Path)
				}
				if cmd.Path != "cmd" && !strings.EqualFold(filepath.Base(cmd.Path), "cmd.exe") {
					t.Fatalf("cmd.Path = %q, want \"cmd\" or a path ending in cmd.exe", cmd.Path)
				}
			} else if cmd.Path != tc.wantPath {
				t.Fatalf("cmd.Path = %q, want unchanged %q", cmd.Path, tc.wantPath)
			}
		})
	}
}
