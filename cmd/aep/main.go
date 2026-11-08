package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"runtime"
	"syscall"
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

	case "supervisor":
		runSupervisor(os.Args[2:])

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
  supervisor    Run the execution loop (boot gate + verification ticks)
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

// bootGate runs the boot-gate checks — memory probe, 384 MiB floor,
// platform line — and returns an error instead of exiting, so callers
// (the boot subcommand, the supervisor) decide how a failure is
// handled. The progress lines are printed here because they carry the
// probed values; the caller owns the header, failure, and result lines.
func bootGate() error {
	info, err := memory.GetMemoryInfo()
	if err != nil {
		return err
	}
	fmt.Printf("BOOT-GATE: memory ok (%d MiB available)\n", info.AvailableBytes/(1024*1024))

	// Preflight memory minimum (384 MiB)
	if info.AvailableBytes < 384*1024*1024 {
		return fmt.Errorf("less than 384 MiB available")
	}

	fmt.Printf("BOOT-GATE: platform ok (%s/%s)\n", runtime.GOOS, runtime.GOARCH)
	return nil
}

func runBootGate() {
	fmt.Println("BOOT-GATE: probing platform...")
	if err := bootGate(); err != nil {
		fmt.Printf("BOOT-GATE: memory FAIL: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("BOOT-GATE-RESULT: SYSTEM-OK")
}

// errSupervisorBootGate marks a supervisor tick failure caused by the
// boot gate. It is fatal in every mode: the environment is unfit, and
// systemd's Restart policy owns the retry cadence.
var errSupervisorBootGate = errors.New("boot gate failed")

// supervisorTick runs one supervisor tick: the boot gate followed by
// one bounded verification pass. It returns nil only when the boot
// gate passes and verification passes. A boot-gate failure is wrapped
// in errSupervisorBootGate; a verification failure is logged and
// returned unwrapped, so loop mode can treat it as non-fatal.
func supervisorTick(ctx context.Context, root string, minMemBytes uint64, perCmdTimeout, totalBudget time.Duration) error {
	if err := bootGate(); err != nil {
		fmt.Printf("SUPERVISOR: tick failed: %v\n", err)
		return fmt.Errorf("%w: %v", errSupervisorBootGate, err)
	}
	res, err := runner.RunVerification(ctx, root, minMemBytes, perCmdTimeout, totalBudget)
	if err != nil {
		fmt.Printf("SUPERVISOR: tick failed: %v\n", err)
		return err
	}
	if !res.Pass {
		err := fmt.Errorf("verification failed (%d of %d executed checks failed)", res.Failed, res.Executed)
		fmt.Printf("SUPERVISOR: tick failed: %v\n", err)
		return err
	}
	fmt.Printf("SUPERVISOR: tick ok (discovered=%d executed=%d)\n", res.Discovered, res.Executed)
	return nil
}

// validateSupervisorFlags checks supervisor flag combinations that
// would otherwise fail obscurely at runtime. In loop mode the
// interval drives time.NewTicker, which panics on a non-positive
// duration, so a non-positive interval is rejected here as a usage
// error before any tick runs. Outside loop mode the interval is
// unused and is not validated.
func validateSupervisorFlags(loop bool, interval time.Duration) error {
	if loop && interval <= 0 {
		return fmt.Errorf("invalid --interval %s: must be positive in loop mode", interval)
	}
	return nil
}

func runSupervisor(args []string) {
	fs := flag.NewFlagSet("supervisor", flag.ExitOnError)
	loop := fs.Bool("loop", false, "Run ticks continuously on the interval until signalled")
	// --once names the default behaviour (exactly one tick) explicitly;
	// the flag is parsed for symmetry with the packaged unit's flags.
	_ = fs.Bool("once", false, "Run exactly one tick and exit (the behaviour without --loop)")
	interval := fs.Duration("interval", 2*time.Hour, "Interval between ticks in loop mode")
	root := fs.String("root", ".", "Path to repository root")
	minMemMB := fs.Uint64("min-mem", 384, "Minimum available memory in MiB")
	timeoutSec := fs.Int("timeout", 300, "Per-command timeout in seconds")
	budgetSec := fs.Int("budget", 600, "Total execution budget in seconds")

	_ = fs.Parse(args)

	if err := validateSupervisorFlags(*loop, *interval); err != nil {
		fmt.Fprintf(os.Stderr, "SUPERVISOR: %v\n", err)
		os.Exit(1)
	}

	minMemBytes := *minMemMB * 1024 * 1024
	perCmdTimeout := time.Duration(*timeoutSec) * time.Second
	totalBudget := time.Duration(*budgetSec) * time.Second

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	// tick runs one supervisor tick and reports whether the supervisor
	// must exit, and with failure. A boot-gate failure is fatal in
	// every mode; a verification failure (already logged by the tick)
	// is fatal only outside loop mode, so a failing check cannot
	// crash-loop the service.
	tick := func() (fatal, failed bool) {
		err := supervisorTick(ctx, *root, minMemBytes, perCmdTimeout, totalBudget)
		if err == nil {
			return false, false
		}
		if errors.Is(err, errSupervisorBootGate) {
			return true, true
		}
		return false, true
	}

	if !*loop {
		// --once, or a bare `aep supervisor`: exactly one tick, then
		// exit with the tick's status.
		if _, failed := tick(); failed {
			os.Exit(1)
		}
		return
	}

	// Loop mode: tick immediately, then on the ticker until SIGINT or
	// SIGTERM, then exit 0. Ticks are sequential, so a tick longer
	// than the interval delays the next one; the ticker drops missed
	// beats instead of queueing them, so ticks never overlap.
	if fatal, _ := tick(); fatal {
		os.Exit(1)
	}
	ticker := time.NewTicker(*interval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if fatal, _ := tick(); fatal {
				os.Exit(1)
			}
		}
	}
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

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	res, err := runner.RunVerification(ctx, *root, minMemBytes, perCmdTimeout, totalBudget)
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
			line := fmt.Sprintf("    [%s] exit=%d timed_out=%v duration=%dms stdout_sha=%s",
				r.CommandID, r.ExitCode, r.TimedOut, r.DurationMs, r.StdoutTailSha[:8])
			if r.Error != "" {
				line += fmt.Sprintf(" error=%q", r.Error)
			}
			fmt.Println(line)
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
