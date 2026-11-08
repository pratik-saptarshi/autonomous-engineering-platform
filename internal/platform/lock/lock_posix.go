//go:build !windows

package lock

import (
	"fmt"
	"os"

	"golang.org/x/sys/unix"
)

type posixFileLock struct {
	path string
	file *os.File
}

// New creates a new FileLock at the specified path.
func New(path string) (FileLock, error) {
	return &posixFileLock{path: path}, nil
}

func (l *posixFileLock) ensureFile() error {
	if l.file != nil {
		return nil
	}
	f, err := os.OpenFile(l.path, os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		return fmt.Errorf("failed to open lock file %s: %w", l.path, err)
	}
	l.file = f
	return nil
}

func (l *posixFileLock) TryLock() error {
	if err := l.ensureFile(); err != nil {
		return err
	}
	err := unix.Flock(int(l.file.Fd()), unix.LOCK_EX|unix.LOCK_NB)
	if err != nil {
		if err == unix.EWOULDBLOCK || err == unix.EAGAIN {
			return ErrLocked
		}
		return fmt.Errorf("flock failed on %s: %w", l.path, err)
	}
	return nil
}

func (l *posixFileLock) Lock() error {
	if err := l.ensureFile(); err != nil {
		return err
	}
	err := unix.Flock(int(l.file.Fd()), unix.LOCK_EX)
	if err != nil {
		return fmt.Errorf("flock failed on %s: %w", l.path, err)
	}
	return nil
}

func (l *posixFileLock) Unlock() error {
	if l.file == nil {
		return nil
	}
	return unix.Flock(int(l.file.Fd()), unix.LOCK_UN)
}

func (l *posixFileLock) Close() error {
	if l.file == nil {
		return nil
	}
	_ = l.Unlock()
	err := l.file.Close()
	l.file = nil
	return err
}
