//go:build linux

package memory

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
)

// GetMemoryInfo parses /proc/meminfo on Linux
func GetMemoryInfo() (*MemoryInfo, error) {
	f, err := os.Open("/proc/meminfo")
	if err != nil {
		return nil, fmt.Errorf("failed to open /proc/meminfo: %w", err)
	}
	defer f.Close()

	var total, avail uint64
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		fields := strings.Fields(line)
		if len(fields) < 2 {
			continue
		}
		key := strings.TrimSuffix(fields[0], ":")
		val, err := strconv.ParseUint(fields[1], 10, 64)
		if err != nil {
			continue
		}
		// /proc/meminfo values are in kB (kibibytes)
		switch key {
		case "MemTotal":
			total = val * 1024
		case "MemAvailable":
			avail = val * 1024
		}
	}

	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("error reading /proc/meminfo: %w", err)
	}

	if total == 0 {
		return nil, fmt.Errorf("unable to determine MemTotal from /proc/meminfo")
	}

	// Fallback if MemAvailable wasn't provided (older kernels)
	if avail == 0 {
		avail = total / 2
	}

	return &MemoryInfo{
		TotalBytes:     total,
		AvailableBytes: avail,
	}, nil
}
