package process

import "strings"

// batchWrap rewrites a launch of a Windows batch file (.cmd/.bat) into a
// launch of the command interpreter running that file. CreateProcess can
// only load native executables, so a batch target named directly fails to
// start: on a standard Node.js install, `npm` resolves through PATHEXT to
// npm.cmd, and exec resolved cmd.Path to that shim before handing it
// here. Routing through `cmd /c` keeps the logical command intact — the
// interpreter exits with the batch file's exit code — while giving the
// platform layer a real executable to create. path is the already
// resolved executable path and args are the arguments that followed the
// program name. When path is not a batch file, the inputs are returned
// unchanged with wrapped=false; in particular a missing tool leaves
// cmd.Path extensionless, so the existing spawn error is preserved.
//
// The helper is platform-free (only the Windows launch path calls it) so
// the transformation is unit-testable on every platform.
func batchWrap(path string, args []string) (string, []string, bool) {
	ext := batchExt(path)
	if !strings.EqualFold(ext, ".cmd") && !strings.EqualFold(ext, ".bat") {
		return path, args, false
	}
	wrapped := make([]string, 0, len(args)+2)
	wrapped = append(wrapped, "/c", path)
	wrapped = append(wrapped, args...)
	return "cmd", wrapped, true
}

// batchExt returns the extension of the final element of path. Both
// Windows and POSIX separators are recognized so the helper behaves
// identically wherever it runs.
func batchExt(path string) string {
	if i := strings.LastIndexAny(path, `\/`); i >= 0 {
		path = path[i+1:]
	}
	if i := strings.LastIndexByte(path, '.'); i >= 0 {
		return path[i:]
	}
	return ""
}
