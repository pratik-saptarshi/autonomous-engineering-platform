//go:build darwin

package memory

import (
	"fmt"

	"golang.org/x/sys/unix"
)

// GetMemoryInfo queries Darwin host memory via sysctl
func GetMemoryInfo() (*MemoryInfo, error) {
	total, err := unix.SysctlUint64("hw.memsize")
	if err != nil {
		return nil, fmt.Errorf("failed to query hw.memsize: %w", err)
	}

	pageSizeVal, err := unix.SysctlUint32("hw.pagesize")
	if err != nil || pageSizeVal == 0 {
		pageSizeVal = 4096
	}
	pageSize := uint64(pageSizeVal)

	freePages, errFree := unix.SysctlUint32("vm.page_free_count")
	specPages, _ := unix.SysctlUint32("vm.page_speculative_count")

	var avail uint64
	if errFree == nil && freePages > 0 {
		avail = uint64(freePages+specPages) * pageSize
	} else {
		// Fallback conservative estimation: at least 25% of total
		avail = total / 4
	}

	return &MemoryInfo{
		TotalBytes:     total,
		AvailableBytes: avail,
	}, nil
}
