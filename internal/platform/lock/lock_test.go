package lock

import (
	"path/filepath"
	"testing"
)

func TestFileLock_MutualExclusion(t *testing.T) {
	tmpDir := t.TempDir()
	lockPath := filepath.Join(tmpDir, "test.lock")

	l1, err := New(lockPath)
	if err != nil {
		t.Fatalf("New(l1) failed: %v", err)
	}
	defer l1.Close()

	if err := l1.TryLock(); err != nil {
		t.Fatalf("l1.TryLock() failed: %v", err)
	}

	// Second lock on same path should fail with ErrLocked
	l2, err := New(lockPath)
	if err != nil {
		t.Fatalf("New(l2) failed: %v", err)
	}
	defer l2.Close()

	err = l2.TryLock()
	if err != ErrLocked {
		t.Fatalf("expected ErrLocked, got %v", err)
	}

	// Unlock l1
	if err := l1.Unlock(); err != nil {
		t.Fatalf("l1.Unlock() failed: %v", err)
	}

	// l2 should now acquire
	if err := l2.TryLock(); err != nil {
		t.Fatalf("l2.TryLock() after l1.Unlock() failed: %v", err)
	}

	_ = l2.Unlock()
}
