package memory

import "testing"

func TestGetMemoryInfo(t *testing.T) {
	info, err := GetMemoryInfo()
	if err != nil {
		t.Fatalf("GetMemoryInfo failed: %v", err)
	}

	if info.TotalBytes == 0 {
		t.Errorf("TotalBytes should be > 0, got %d", info.TotalBytes)
	}
	if info.AvailableBytes == 0 {
		t.Errorf("AvailableBytes should be > 0, got %d", info.AvailableBytes)
	}
	if info.AvailableBytes > info.TotalBytes {
		t.Errorf("AvailableBytes (%d) exceeds TotalBytes (%d)", info.AvailableBytes, info.TotalBytes)
	}
}
