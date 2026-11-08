package memory

// MemoryInfo provides unified memory statistics.
type MemoryInfo struct {
	TotalBytes     uint64
	AvailableBytes uint64
}

// GetAvailableMemory returns the available memory in bytes across supported platforms.
func GetAvailableMemory() (uint64, error) {
	info, err := GetMemoryInfo()
	if err != nil {
		return 0, err
	}
	return info.AvailableBytes, nil
}
