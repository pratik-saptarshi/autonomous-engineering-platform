package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"runtime"
	"time"

	"github.com/pratik-saptarshi/autonomous-engineering-platform/internal/platform/lock"
	"github.com/pratik-saptarshi/autonomous-engineering-platform/internal/platform/memory"
	"github.com/pratik-saptarshi/autonomous-engineering-platform/internal/verifier/runner"
)

var (
	version = "1.0.0"
)

func main() {
	if len(os.Args) < 2 {
		printUsage()
		os.Exit(1)
	}

	command := os.Args[1]
	switch command {
	case "version":
		fmt.Printf("aep version %s (%s/%s)\n", version, runtime.GOOS, runtime.GOARCH)

	case "info":
		runInfo()

	case "boot":
		runBootGate()

	case "verify":
		runVerify(os.Args[2:])

	case "lock-test":
		runLockTest(os.Args[2:])

	default:
		fmt.Fprintf(os.Stderr, "Unknown command: %s\n\n", command)
		printUsage()
		os.Exit(1)
	}
}

func printUsage() {
	fmt.Printf(`AEP - Autonomous Engineering Platform CLI (%s)

Usage:
  aep <command> [arguments]

Commands:
  version       Display AEP version and architecture
  info          Display system metrics, memory, and hardware tier
  boot          Execute preflight sanity and environment gate
  verify        Run bounded allowlist mechanical verification with hash receipts
  lock-test     Test cross-platform file locking on a path
`, version)
}

func runInfo() {
	info, err := memory.GetMemoryInfo()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error probing memory: %v\n", err)
		os.Exit(1)
	}

	totalMB := info.TotalBytes / (1024 * 1024)
	availMB := info.AvailableBytes / (1024 * 1024)

	tier := "workstation"
	if totalMB <= 8192 {
		tier = "muse-embedded-8gb"
	}

	fmt.Printf("OS/Arch:         %s/%s\n", runtime.GOOS, runtime.GOARCH)
	fmt.Printf("CPUs:            %d\n", runtime.NumCPU())
	fmt.Printf("Total Memory:    %d MiB\n", totalMB)
	fmt.Printf("Avail Memory:    %d MiB\n", availMB)
	fmt.Printf("Hardware Tier:   %s\n", tier)
}

func runBootGate() {
	fmt.Println("BOOT-GATE: probing platform...")
	info, err := memory.GetMemoryInfo()
	if err != nil {
		fmt.Printf("BOOT-GATE: memory FAIL: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("BOOT-GATE: memory ok (%d MiB available)\n", info.AvailableBytes/(1024*1024))

	// Preflight memory minimum (384 MiB)
	if info.AvailableBytes < 384*1024*1024 {
		fmt.Printf("BOOT-GATE: memory FAIL: less than 384 MiB available\n")
		os.Exit(1)
	}

	fmt.Printf("BOOT-GATE: platform ok (%s/%s)\n", runtime.GOOS, runtime.GOARCH)
	fmt.Println("BOOT-GATE-RESULT: SYSTEM-OK")
}

func runVerify(args []string) {
	fs := flag.NewFlagSet("verify", flag.ExitOnError)
	root := fs.String("root", ".", "Path to repository root")
	minMemMB := fs.Uint64("min-mem", 384, "Minimum available memory in MiB")
	timeoutSec := fs.Int("timeout", 300, "Per-command timeout in seconds")
	budgetSec := fs.Int("budget", 600, "Total execution budget in seconds")
	jsonOut := fs.Bool("json", false, "Output verification results as JSON")

	_ = fs.Parse(args)

	minMemBytes := *minMemMB * 1024 * 1024
	perCmdTimeout := time.Duration(*timeoutSec) * time.Second
	totalBudget := time.Duration(*budgetSec) * time.Second

	res, err := runner.RunVerification(context.Background(), *root, minMemBytes, perCmdTimeout, totalBudget)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Verification failed: %v\n", err)
		os.Exit(1)
	}

	if *jsonOut {
		data, _ := json.MarshalIndent(res, "", "  ")
		fmt.Println(string(data))
	} else {
		fmt.Printf("Verification Summary:\n")
		fmt.Printf("  Discovered: %d\n", res.Discovered)
		fmt.Printf("  Executed:   %d\n", res.Executed)
		fmt.Printf("  Failed:     %d\n", res.Failed)
		fmt.Printf("  Status:     %s\n", map[bool]string{true: "PASS", false: "FAIL"}[res.Pass])
		for _, r := range res.Receipts {
			fmt.Printf("    [%s] exit=%d timed_out=%v duration=%dms stdout_sha=%s\n",
				r.CommandID, r.ExitCode, r.TimedOut, r.DurationMs, r.StdoutTailSha[:8])
		}
	}

	if !res.Pass {
		os.Exit(1)
	}
}

func runLockTest(args []string) {
	if len(args) < 1 {
		fmt.Fprintf(os.Stderr, "Usage: aep lock-test <lock-file-path>\n")
		os.Exit(1)
	}
	path := args[0]
	fl, err := lock.New(path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to initialize lock: %v\n", err)
		os.Exit(1)
	}
	defer fl.Close()

	if err := fl.TryLock(); err != nil {
		fmt.Printf("Lock status: HELD by another process (%v)\n", err)
		return
	}
	fmt.Printf("Lock status: ACQUIRED successfully on %s\n", path)
	_ = fl.Unlock()
}
