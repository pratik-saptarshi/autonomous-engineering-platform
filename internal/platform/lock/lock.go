package lock

import (
	"errors"
	"io"
)

var (
	// ErrLocked is returned when a non-blocking lock cannot be acquired because another process holds it.
	ErrLocked = errors.New("file is already locked")
)

// FileLock represents an exclusive lock on a file.
type FileLock interface {
	io.Closer
	// TryLock attempts to acquire the lock non-blockingly.
	TryLock() error
	// Lock blocks until the lock is acquired.
	Lock() error
	// Unlock releases the held lock.
	Unlock() error
}
