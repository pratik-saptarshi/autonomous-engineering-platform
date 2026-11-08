package runner

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/pratik-saptarshi/autonomous-engineering-platform/internal/platform/memory"
	"github.com/pratik-saptarshi/autonomous-engineering-platform/internal/platform/process"
)

const (
	DefaultTailCapBytes   = 65536             // 64 KiB
	DefaultTimeoutSeconds = 300               // 5 minutes
	DefaultBudgetSeconds  = 600               // 10 minutes
	DefaultMinMemoryBytes = 512 * 1024 * 1024 // 512 MiB
)

// CommandReceipt records hash-chained execution proof for a single verification command.
type CommandReceipt struct {
	CommandID      string `json:"command_id"`
	ExitCode       int    `json:"exit_code"`
	TimedOut       bool   `json:"timed_out"`
	DurationMs     int64  `json:"duration_ms"`
	StdoutTailSha  string `json:"stdout_tail_sha256"`
	StderrTailSha  string `json:"stderr_tail_sha256"`
	ExecutionProof string `json:"execution_proof,omitempty"`
}

// VerificationResult summarizes the execution of all discovered verification checks.
type VerificationResult struct {
	Pass          bool             `json:"pass"`
	Discovered    int              `json:"discovered"`
	Executed      int              `json:"executed"`
	Failed        int              `json:"failed"`
	Receipts      []CommandReceipt `json:"receipts"`
	TotalDuration time.Duration    `json:"total_duration"`
}

// TailCappedBuffer maintains only the trailing N bytes of an incoming stream.
type TailCappedBuffer struct {
	mu  sync.Mutex
	cap int
	buf []byte
}

func NewTailCappedBuffer(maxBytes int) *TailCappedBuffer {
	return &TailCappedBuffer{
		cap: maxBytes,
		buf: make([]byte, 0, maxBytes),
	}
}

func (b *TailCappedBuffer) Write(p []byte) (n int, err error) {
	b.mu.Lock()
	defer b.mu.Unlock()

	n = len(p)
	if len(p) >= b.cap {
		b.buf = append(b.buf[:0], p[len(p)-b.cap:]...)
		return n, nil
	}

	space := b.cap - len(b.buf)
	if len(p) <= space {
		b.buf = append(b.buf, p...)
		return n, nil
	}

	overflow := len(p) - space
	b.buf = append(b.buf[overflow:], p...)
	return n, nil
}

func (b *TailCappedBuffer) Bytes() []byte {
	b.mu.Lock()
	defer b.mu.Unlock()
	res := make([]byte, len(b.buf))
	copy(res, b.buf)
	return res
}

func (b *TailCappedBuffer) Sha256Hex() string {
	bytes := b.Bytes()
	h := sha256.Sum256(bytes)
	return hex.EncodeToString(h[:])
}

// DiscoveredCommand represents a detected verification command.
type DiscoveredCommand struct {
	ID   string
	Name string
	Args []string
}

// DiscoverCommands discovers project verification commands from project markers.
func DiscoverCommands(repoRoot string) ([]DiscoveredCommand, error) {
	var cmds []DiscoveredCommand

	// 1. go test (go.mod)
	if fileExists(filepath.Join(repoRoot, "go.mod")) {
		cmds = append(cmds, DiscoveredCommand{
			ID:   "go-test",
			Name: "go",
			Args: []string{"test", "./..."},
		})
	}

	// 2. cargo test (Cargo.toml)
	if fileExists(filepath.Join(repoRoot, "Cargo.toml")) {
		cmds = append(cmds, DiscoveredCommand{
			ID:   "cargo-test",
			Name: "cargo",
			Args: []string{"test"},
		})
	}

	// 3. npm test (package.json)
	pkgJSONPath := filepath.Join(repoRoot, "package.json")
	if fileExists(pkgJSONPath) {
		if hasNPMTestScript(pkgJSONPath) {
			cmds = append(cmds, DiscoveredCommand{
				ID:   "npm-test",
				Name: "npm",
				Args: []string{"test"},
			})
		}
	}

	// 4. pytest / python test markers
	if fileExists(filepath.Join(repoRoot, "pytest.ini")) ||
		fileExists(filepath.Join(repoRoot, "pyproject.toml")) ||
		fileExists(filepath.Join(repoRoot, "setup.cfg")) {
		cmds = append(cmds, DiscoveredCommand{
			ID:   "pytest",
			Name: "python3",
			Args: []string{"-m", "pytest", "-v"},
		})
	}

	// 5. make test (Makefile with a declared test target)
	makefilePath := filepath.Join(repoRoot, "Makefile")
	if fileExists(makefilePath) && hasMakeTestTarget(makefilePath) {
		cmds = append(cmds, DiscoveredCommand{
			ID:   "make-test",
			Name: "make",
			Args: []string{"test"},
		})
	}

	return cmds, nil
}

// RunVerification executes all discovered commands under bounded memory, time budget, and tail caps.
func RunVerification(ctx context.Context, repoRoot string, minMemBytes uint64, perCmdTimeout, totalBudget time.Duration) (*VerificationResult, error) {
	// Preflight 1: Memory check
	availMem, err := memory.GetAvailableMemory()
	if err == nil && availMem < minMemBytes {
		return nil, fmt.Errorf("preflight memory refusal: %d bytes available, minimum %d bytes required", availMem, minMemBytes)
	}

	info, err := os.Stat(repoRoot)
	if err != nil || !info.IsDir() {
		return nil, fmt.Errorf("verification root %q does not exist or is not a directory", repoRoot)
	}

	cmds, err := DiscoverCommands(repoRoot)
	if err != nil {
		return nil, fmt.Errorf("failed to discover verification commands: %w", err)
	}

	result := &VerificationResult{
		Pass:       true,
		Discovered: len(cmds),
	}

	if len(cmds) == 0 {
		result.Pass = false
		return result, fmt.Errorf("no verification checks discovered at %q: refusing to report success without mechanical evidence", repoRoot)
	}

	startTime := time.Now()
	ctxBudget, cancelBudget := context.WithTimeout(ctx, totalBudget)
	defer cancelBudget()

	for _, cmd := range cmds {
		// Check budget
		if ctxBudget.Err() != nil {
			result.Pass = false
			return result, fmt.Errorf("overall verification budget exceeded")
		}

		cmdCtx, cancelCmd := context.WithTimeout(ctxBudget, perCmdTimeout)
		stdoutTail := NewTailCappedBuffer(DefaultTailCapBytes)
		stderrTail := NewTailCappedBuffer(DefaultTailCapBytes)

		pg := process.NewCommand(cmdCtx, cmd.Name, cmd.Args, process.CommandConfig{
			Dir:         repoRoot,
			Stdout:      stdoutTail,
			Stderr:      stderrTail,
			GracePeriod: 750 * time.Millisecond,
		})

		cmdStart := time.Now()
		startErr := pg.Start()
		var exitCode int
		var timedOut bool

		if startErr != nil {
			exitCode = 127
			result.Pass = false
			result.Failed++
		} else {
			waitErr := pg.Wait()
			cmdDuration := time.Since(cmdStart)

			if cmdCtx.Err() == context.DeadlineExceeded {
				timedOut = true
				exitCode = 124
				_ = pg.Kill()
			} else if waitErr != nil {
				if code, ok := process.ExitCode(waitErr); ok {
					exitCode = code
				} else {
					exitCode = 1
				}
			}

			receipt := CommandReceipt{
				CommandID:     cmd.ID,
				ExitCode:      exitCode,
				TimedOut:      timedOut,
				DurationMs:    cmdDuration.Milliseconds(),
				StdoutTailSha: stdoutTail.Sha256Hex(),
				StderrTailSha: stderrTail.StderrTailSha(),
			}

			result.Receipts = append(result.Receipts, receipt)
			result.Executed++

			if exitCode != 0 {
				result.Pass = false
				result.Failed++
				cancelCmd()
				break
			}
		}

		cancelCmd()
	}

	result.TotalDuration = time.Since(startTime)
	return result, nil
}

func (b *TailCappedBuffer) StderrTailSha() string {
	return b.Sha256Hex()
}

func fileExists(path string) bool {
	info, err := os.Stat(path)
	if err != nil {
		return false
	}
	return !info.IsDir()
}

var makeTestTargetRe = regexp.MustCompile(`(?m)^test:`)

// hasMakeTestTarget reports whether the Makefile declares a test target.
// The check is deliberately byte-parity with scripts/mechanical_verify.py,
// which requires a line matching ^test: before scheduling make test: a
// `test :` line (with a space) does not count, and neither does a
// commented-out `# test:` line, which does not begin with test:. A line
// that does begin with test: matches in both implementations even when
// it is not a real rule — e.g. inside a define block — and matching the
// Python verifier's behaviour is the point.
func hasMakeTestTarget(makefilePath string) bool {
	data, err := os.ReadFile(makefilePath)
	if err != nil {
		return false
	}
	return makeTestTargetRe.Match(data)
}

func hasNPMTestScript(pkgJSONPath string) bool {
	data, err := os.ReadFile(pkgJSONPath)
	if err != nil {
		return false
	}
	var pkg struct {
		Scripts map[string]string `json:"scripts"`
	}
	if err := json.Unmarshal(data, &pkg); err != nil {
		return false
	}
	testScript, exists := pkg.Scripts["test"]
	if !exists || strings.TrimSpace(testScript) == "" || strings.Contains(testScript, "no test specified") {
		return false
	}
	return true
}
