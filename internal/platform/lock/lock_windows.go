//go:build windows

package lock

import (
	"fmt"

	"golang.org/x/sys/windows"
)

type windowsFileLock struct {
	path   string
	handle windows.Handle
}

// New creates a new FileLock at the specified path.
func New(path string) (FileLock, error) {
	return &windowsFileLock{path: path, handle: windows.InvalidHandle}, nil
}

func (l *windowsFileLock) ensureHandle() error {
	if l.handle != windows.InvalidHandle {
		return nil
	}
	p, err := windows.UTF16PtrFromString(l.path)
	if err != nil {
		return err
	}
	h, err := windows.CreateFile(
		p,
		windows.GENERIC_READ|windows.GENERIC_WRITE,
		windows.FILE_SHARE_READ|windows.FILE_SHARE_WRITE,
		nil,
		windows.OPEN_ALWAYS,
		windows.FILE_ATTRIBUTE_NORMAL,
		0,
	)
	if err != nil {
		return fmt.Errorf("failed to open lock file %s: %w", l.path, err)
	}
	l.handle = h
	return nil
}

func (l *windowsFileLock) TryLock() error {
	if err := l.ensureHandle(); err != nil {
		return err
	}
	var ol windows.Overlapped
	err := windows.LockFileEx(l.handle, windows.LOCKFILE_EXCLUSIVE_LOCK|windows.LOCKFILE_FAIL_IMMEDIATELY, 0, 1, 0, &ol)
	if err != nil {
		if err == windows.ERROR_LOCK_VIOLATION {
			return ErrLocked
		}
		return fmt.Errorf("LockFileEx failed on %s: %w", l.path, err)
	}
	return nil
}

func (l *windowsFileLock) Lock() error {
	if err := l.ensureHandle(); err != nil {
		return err
	}
	var ol windows.Overlapped
	err := windows.LockFileEx(l.handle, windows.LOCKFILE_EXCLUSIVE_LOCK, 0, 1, 0, &ol)
	if err != nil {
		return fmt.Errorf("LockFileEx failed on %s: %w", l.path, err)
	}
	return nil
}

func (l *windowsFileLock) Unlock() error {
	if l.handle == windows.InvalidHandle {
		return nil
	}
	var ol windows.Overlapped
	return windows.UnlockFileEx(l.handle, 0, 1, 0, &ol)
}

func (l *windowsFileLock) Close() error {
	if l.handle == windows.InvalidHandle {
		return nil
	}
	_ = l.Unlock()
	err := windows.CloseHandle(l.handle)
	l.handle = windows.InvalidHandle
	return err
}
