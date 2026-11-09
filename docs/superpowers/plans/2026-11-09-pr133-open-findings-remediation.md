# PR #133 Open-Finding Remediation Implementation Plan (v4, final)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the open P2 findings on PR #133 (C6-C12) and re-audit the earlier fixes (C1-C5, with C4/C5 reopened) by making the capability model, lane boundaries, admission arithmetic, and receipt semantics internally consistent and structurally checkable at head `080e28b`.

**Architecture:** One attested capability value type replaces the stored `Tier2Supported` boolean and the unranked `IsolationClass` string. A task's risk class sets an immutable `Requirement`; re-verification must meet it, and the re-verification target is probed before the original run. Model inference moves to the trusted host harness; the lane exposes an `exec.sock` command relay. Git control moves to a host-side `git.sock` relay; the lane's `.git` file is masked. Memory uses typed units and a checked predicate. Receipts hash full output streams and carry a nonce, ledger sequence, and Ed25519 signature. A structural HTML checker, written first, guards each claim by section, not by global substring.

**Tech Stack:** HTML design docs; Python 3.9 stdlib (`html.parser`) invariant checker with good/bad fixtures; Go 1.27 interface sketches; Docker or CI Chromium for PDF rendering; GitHub Actions `docs-lint` job.

**Spec:** `docs/plan/aep-hld-v1.1.html`, `docs/plan/aep-lld-v1.1.html`, `docs/plan/aep-backlog-v1.1.html`, `docs/draft-proposal.html`; PR #133 findings C1-C12.

**Baseline:** spec docs at `080e28b` (unchanged through current HEAD `a84bcae`; only the plan file changed). The backlog is 525 lines and only CAP-01/02/07 remain. The C11 physical-floor sub-finding is already fixed in AC-07.1 (`TotalRAM >= 7.5 GiB`); Task 4 adds the admission wording and busy-host AC. C12 retargets to `internal/verifier/runner` and PR-11b. PR #133 is docs-only; code changes are follow-up slices, not part of this PR.

## Decision Log

- **D1: Capability is a value, not a field.** `Profile.Backend` carries kind, isolation, provenance, and probe evidence. `Tier2Supported()` is a method; `KVMProbe` is evidence only. Constructors reject invalid kind/isolation pairs.
- **D2: Requirements are immutable to the task and lane, risk-derived, and override-only.** A task carries `Requirement{kind}` from its risk class, or an explicit `NoFloor`. Only an authenticated operator reassessment may change it, and the change is recorded. The origin run never changes the floor; origin is audit data only. An unset requirement fails closed.
- **D3: The model runs outside the lane.** The trusted host harness performs inference and selects the model tier; the lane exposes `exec.sock` for argv-level allowlisted commands. No `model.sock`, no provider credential, no lane-originated model request.
- **D4: Git control runs on the host.** Tier 1 mounts the worktree with `/workspace/.git` masked and uses `git.sock` for status/diff/commit. Tier 2 uses an independent clone and the host fetches the tested tree after verification.
- **D5: Receipts are signed and full-stream.** `StdoutSha`/`StderrSha` hash every byte; tails are display-only. `Nonce`, `IssuedAt`, `LedgerSeq`, and `KeyID` make replay detectable. Ed25519 lets an external auditor verify without the host key.

## Global Constraints

- Fail closed: an unknown backend, unattested isolation, missing relay, or unmet requirement quarantines or refuses, never silently degrades.
- One fact lives in one place: LLD §4.1/§4.9 defines the capability types; HLD, backlog, and draft link to that anchor and do not restate a different enum.
- No lane has direct network egress, provider credentials, GitHub credentials, or host Git metadata.
- Units are explicit: `MiB` and `Bytes` are distinct types; profile minimum uses total RAM, admission uses available RAM.
- Re-verification isolation must meet the task requirement. It is never origin-relative.
- No stored derived booleans. If a value can disagree with its source, derive it.
- Write the failing structural check first; run it after every task.
- Conventional Commits, one commit per task. Doc tasks use `docs(plan):`; checker tasks use `test(docs):`; CI tasks use `ci(docs):`.
- Do not resolve C4 or C5 until all four documents agree. Do not resolve any thread before its fixing commit is pushed and CI is green.
- PR #133 stays docs-only. Do not commit Go code under a `docs(plan):` commit; put code in the follow-up slices named at the end.

## Review Focus

- A KVM-free gVisor host must run gVisor-eligible work and quarantine hardware-floor work **before** the original execution, not after re-verification fails.
- A `--network none` lane must execute tests and commit through host relays, with no model or Git credential in the lane and no usable `.git` (the mask contains no `gitdir:` pointer).
- Available memory below the request must reject, not wrap; exact floor admits; a busy host passes profile detection and fails only admission.
- A receipt must change when any output byte changes, and a replayed receipt must fail even after a verifier restart.
- `nano-8g` must fit the 7.5 GiB floor and have one Tier-2 story across all four docs.

---

### Task 0: Write the structural checker first

**Files:**
- Create: `scripts/check_design_invariants.py`
- Create: `scripts/tests/fixtures/design-invariants/good/*.html`
- Create: `scripts/tests/fixtures/design-invariants/bad/*.html`
- Test: the checker's self-test; expected to fail on current docs

**Interfaces:**
- Produces: `check_design_invariants.py --check` and `--self-test`.

- [ ] **Step 1: Write a section-aware checker**

Use Python 3.9 `html.parser` to extract headings, `<pre>` blocks, table rows, and item cards. Bind each assertion to a section, not the whole file. For table/card checks, locate the `<tr>` containing the key (`nano-8g`, `PR-11b`, `AC-07`) and parse its cells; for run-spec checks, locate the `<pre>` under `<h3>9.3` and parse the exact lines. Each assertion gets its own good/bad fixture pair; a check with five assertions gets five bad fixtures, not one.

| Check | Section | Assertion |
|---|---|---|
| C9-1 | LLD `<h3>4.1` + `<h3>4.9` | `Requirement`, `Backend`, `Isolation`, `NewBackend` exist; no `Tier2Supported bool` field; `Tier2Supported()` is a method; no duplicate `SandboxBackend string` enum |
| C9-2 | HLD §9 + §11 | `Tier2Supported` is derived from `Backend`; `/dev/kvm` is only `KVMProbe` |
| C6 | LLD §6 `<pre>` | no `host - req.MemMiB`; `host < reqBytes`; zero and overflow rejected |
| C7 | LLD §9.3 run-spec `<pre>`, HLD §4 line 114, HLD §5.2 | `exec.sock` present; `model.sock` absent; no provider key; no "engine/harness runs in the lane" text |
| C10 | LLD §9.3 run-spec `<pre>`, backlog AC-01.2/line 457 | `git.sock` present; `/workspace/.git` mask present; no host `.git` mount; no lane-local `GIT_INDEX_FILE` |
| C11 | backlog AC-07 cards only | `TotalRAM >= 7.5 GiB`; admission uses available + floor; no minimum against available |
| C12 | backlog PR-11b, HLD §9, LLD §3/§11, draft line 367 | fields `StdoutSha`, `StderrSha`, `Nonce`, `IssuedAt`, `LedgerSeq`, `KeyID`, `Signature`; AC binds full output; no "tail digest" claim |
| C8/C4 | HLD §9 + §5.2, LLD T11, draft C4 card | `Requirement`/`MinIsolation`; no unconditional microVM-only re-verification |
| C5 | HLD §6 nano row, LLD §4.1 + §9.1, draft profile matrix lines 306-311/407 | 2560/3584/1536 MiB; `MaxTier1Lanes=1`; no nano "Tier 2 disabled/off" (the generic all-backends-unavailable sentence at draft line 346 is legitimate); budget sum <= 7680 MiB; `Tier1Budget >= MaxTier1Lanes*Tier1Lane` and same for Tier 2 |
| C1 | LLD §4.9 | `VerifyEgressProbe` checks the SHA-256 digest of probe evidence |
| C2 | HLD §9, LLD §7, LLD §8.2, draft C2 card | no silent downgrade; explicit authenticated override recorded in the decision record |
| C3 | LLD §4.4/§4.5/§9.2 | `memory.sock` and `ghg.sock` use the same `relay.Handler` anchor |

- [ ] **Step 2: Build good and bad fixtures**

Each check gets a `good/<check>.html` that must pass and a `bad/<check>.html` that must fail. The bad fixture contains either the forbidden text in the checked section or the negation of the required text. Add a `bad/missing-section.html` fixture to prove the checker fails on a missing file or section (never fail-open).

- [ ] **Step 3: Run the failing check**

```bash
python3 scripts/check_design_invariants.py --self-test   # expected: pass
python3 scripts/check_design_invariants.py --check       # expected: fail, listing C5-C12/C1-C3
```

Do not wire `--check` into CI until Task 7.

- [ ] **Step 4: Commit**

```bash
git add scripts/check_design_invariants.py scripts/tests/fixtures/design-invariants
git commit -m "test(docs): add section-aware invariant checker for PR #133"
```

---

### Task 1: Replace the capability model and set the requirement floor (C9, C8, C4, C5)

**Files:**
- Modify: `docs/plan/aep-lld-v1.1.html` §4.1, §4.9, §7, §10, §12 T4/T10/T11
- Modify: `docs/plan/aep-hld-v1.1.html` §4 SVG (lines 114, 116), §5.2 (line 138), §6, §8 (line 172), §9, §11, §12
- Modify: `docs/plan/aep-backlog-v1.1.html` CAP-02, CAP-07, PR-10/PR-11
- Modify: `docs/draft-proposal.html` profile matrix (lines 306-311, 407) and C4 card (399-403)
- Test: `check_design_invariants.py`

**Interfaces:**
- Produces: `BackendKind`, `IsolationKind`, `Provenance`, `Backend`, `Isolation`, `Requirement`, `NoFloor`, `NewBackend`, `Profile.Backend`, `Profile.KVMProbe`, `Profile.Tier2Supported()`, `Profile.Tier2Admissible()`.

- [ ] **Step 1: Run the failing checks**

```bash
python3 scripts/check_design_invariants.py --check
```

Expected: C9-1, C9-2, C5, C8/C4 fail.

- [ ] **Step 2: Define the value types**

```go
type BackendKind uint8

const (
    BackendNone BackendKind = iota
    BackendCubeKVM
    BackendLibkrun
    BackendGVisor
    BackendRemote
)

type IsolationKind uint8

const (
    IsolationNone IsolationKind = iota
    IsolationUserSpaceKernel
    IsolationHardwareMicroVM
)

type Provenance uint8

const (
    ProvenanceLocal Provenance = iota
    ProvenanceRemote
)

type Isolation struct {
    kind     IsolationKind
    evidence [32]byte
}

func (i Isolation) Valid() bool { return i.kind != IsolationNone && i.evidence != ([32]byte{}) }

// Requirement is what a task needs; it has no evidence.
type Requirement struct {
    kind IsolationKind
    set  bool
}

func NoFloor() Requirement { return Requirement{kind: IsolationNone, set: true} }
func AtLeast(kind IsolationKind) Requirement { return Requirement{kind: kind, set: true} }
func RequirementForRiskClass(class string) (Requirement, error) // missing/unknown class -> error

func (r Requirement) MetBy(i Isolation) bool {
    if !r.set { return false } // unset requirement fails closed
    if r.kind == IsolationNone { return true }
    return i.Valid() && i.kind >= r.kind
}

type Backend struct {
    kind       BackendKind
    isolation  Isolation
    provenance Provenance
}

type ProbeResult struct {
    Present bool
    Digest  [32]byte
}

func NewBackend(kind BackendKind, isolation Isolation, provenance Provenance) (Backend, error) {
    // Pair kind -> isolation kind; reject gVisor+hardware, cube-kvm+user-space,
    // remote without attestation, and zero evidence.
}

func (b Backend) Usable() bool
func (b Backend) Isolation() Isolation

type Profile struct {
    // ... sizing fields ...
    Backend  Backend
    KVMProbe ProbeResult
}

func (p Profile) Tier2Supported() bool { return p.Backend.Usable() }
func (p Profile) Tier2Admissible(laneMiB memory.MiB, active int) error
```

`Requirement` has no evidence, so a floor is not invalidated by `Valid()`. `NoFloor` admits Tier 1 only when explicitly set; an unset zero-value requirement fails closed. `NewBackend` enforces the kind/isolation pairing. `Provenance` is not a strength; a remote hardware VM must carry attestation evidence. Replace the existing `type SandboxBackend string` enum in LLD §4.9 with `BackendKind`, and replace the backlog CAP-02 `BackendProbe` use of `SandboxBackend` with `BackendKind`; do not keep two backend enums. Replace the backlog CAP-07 `ReservationReq` with the existing `Request`; do not introduce a parallel request type.

- [ ] **Step 3: Separate capability from capacity**

Update the LLD failure matrix and dispatch table:

- No usable backend -> `blocked:unsupported-tier2-no-sandbox`.
- Usable backend but `MaxTier2Lanes == 0` or budget below `Tier2LaneMiB` -> `blocked:tier2-capacity-exhausted` (terminal; do not wait forever).
- `Tier2Supported()` is capability; `Tier2Admissible()` is capacity.
- Define typed errors: `ErrNoCapacity{Reason}` and `ErrTier2Unsupported{Reason}`.

Set profile-specific values. For `nano-8g`, use a preset that fits the 7.5 GiB floor:

```text
SubstrateMiB=2560 (2.5 GiB), Tier1BudgetMiB=3584 (3.5 GiB),
Tier1LaneMiB=2048, MaxTier1Lanes=1,
Tier2BudgetMiB=1536 (1.5 GiB), Tier2LaneMiB=1536, MaxTier2Lanes=1.
sum = 7680 MiB.
```

Update HLD §6 (Tier 1 4.0 GB -> 3584 MiB / 3.5 GiB; one 2 GiB lane plus 1.5 GiB headroom), LLD §4.1 (lines 87/88/89/90/91/92/100), draft lines 306-311/407, and backlog AC-07. Set `MaxTier1Lanes=1` for nano; `2 * 2048 = 4096 > 3584`, so the old ceiling is over-committed. Use "2560 MiB (2.5 GiB)", "1536 MiB (1.5 GiB)", and "3584 MiB (3.5 GiB)" everywhere; do not mix decimal GB with binary MiB. Add a checker assertion that `Tier1BudgetMiB >= MaxTier1Lanes * Tier1LaneMiB` and the same for Tier 2. Note that 1536 MiB includes gVisor sentry overhead and is a measured assumption; add a risk test to validate peak RSS.

- [ ] **Step 4: Define the requirement and re-verification target**

Extend the existing `Issue` type in LLD §4.3 rather than adding a parallel `Task` type:

```go
type Issue struct {
    // ... existing fields ...
    MinIsolation Requirement // from immutable risk class; NoFloor for Tier 1
}
```

Rules:

- `tier:factory` with untrusted native code -> `AtLeast(IsolationHardwareMicroVM)`.
- Explicitly gVisor-eligible task -> `AtLeast(IsolationUserSpaceKernel)`, only via an authenticated operator reassessment recorded in the decision ledger.
- Every issue path must set `MinIsolation` explicitly (`NoFloor()` for Tier 1, `AtLeast(...)` for Tier 2). A zero-value `Requirement{}` fails closed, so a missing risk class quarantines rather than admitting.
- A lane cannot set or lower its own `MinIsolation`; only the operator override can, and it must record `--reason` plus the operator identity in the decision record.
- The dispatcher probes the re-verification target at dispatch and pins it for the run. If it cannot meet `MinIsolation`, quarantine **before** the original run. Do not discover the mismatch after the patch exists.
- Origin is audit data only. A hardware-origin run does not force a higher floor; the immutable risk class does. This removes the origin-relative inversion.
- `VerifyResult` records the actual `Isolation` and `BackendEvidence`; the post-run value is audit data, not the gate.

Update HLD §4 line 116, §5.2 line 138, §8 line 172, §9 line 183, LLD T11, draft lines 367/402, and backlog PR-11.

- [ ] **Step 5: Restore the C1 sentence and fix stale claims**

In LLD §4.9, restore: "`VerifyEgressProbe` checks the SHA-256 digest of the in-VM probe evidence; a missing or mismatched digest rejects the run." In HLD §11 (line 207), replace "set `Tier2Supported` from the result [of the `/dev/kvm` probe]" with "set `KVMProbe` from the result; derive `Tier2Supported` from `Backend`." In HLD §12, stop claiming C1/C4 were remediated until they are. In HLD D8 (line 57), require the explicit authenticated override, not a "fenced local lane with escalated review."

- [ ] **Step 6: Run the check and commit**

```bash
python3 scripts/check_design_invariants.py --check
git add docs/plan/aep-lld-v1.1.html docs/plan/aep-hld-v1.1.html docs/plan/aep-backlog-v1.1.html docs/draft-proposal.html
git commit -m "docs(plan): model capability as an attested value and gate re-verification by risk"
```

---

### Task 2: Move model execution outside the lane (C7)

**Files:**
- Modify: `docs/plan/aep-lld-v1.1.html` §4.4/§4.5, §9.2, §9.3, §10
- Modify: `docs/plan/aep-hld-v1.1.html` §4 (line 114), §5.2, §9, §11 (add the model-boundary risk row)
- Modify: `docs/plan/aep-backlog-v1.1.html` CAP-01, PR-06/PR-07
- Modify: `docs/draft-proposal.html` line 264 and lane lifecycle
- Test: `check_design_invariants.py`

**Interfaces:**
- Produces: `internal/execd` (`exec.sock`), `ExecRequest{Argv, Cwd, Timeout, Env}`, `ExecPolicy`, and one `relay.Handler` used by `memoryd`/`gwd`/`execd`/`gitd`.

- [ ] **Step 1: Run the failing check**

```bash
python3 scripts/check_design_invariants.py --check
```

Expected: C7 fails.

- [ ] **Step 2: Write the boundary decision**

In HLD §5.2 and LLD §9.3:

> The trusted host harness runs the agent loop and all model inference. A lane is a tool executor: it receives argv-level allowlisted commands over `exec.sock`, runs them under its cgroup and `--network none`, and returns structured stdout/stderr/exit status. Lanes hold no provider key and cannot originate a model request. The host harness selects the model tier (standard/measured for Ralph, frontier/thorough for factory) before dispatching commands. Lane output is untrusted tool data; the harness never interpolates raw lane output into a system prompt.

Update HLD line 114 (remove "engine: opencode2/Claude Code/Codex/Pi harness" from the lane), draft line 264 ("agents inside CubeSandbox" -> "host harness executes; sandbox runs tools"), and the lifecycle text.

- [ ] **Step 3: Define the relay contract and policy**

```go
type relay.Handler interface { Serve(ctx context.Context, conn net.Conn) error }

type ExecRequest struct {
    LaneID  string
    Argv    []string // no shell interpolation
    Cwd     string
    Timeout time.Duration
    Env     map[string]string // allowlisted keys only
}

type ExecPolicy interface {
    Allow(laneID string, argv []string) error
    ScrubEnv(env map[string]string) map[string]string
}
```

Authenticate with `SO_PEERCRED` on Linux and `LOCAL_PEERCRED` or a per-lane token on macOS. Reject path traversal and non-allowlisted binaries; no `sh -c`, `python -c`, or `make` with arbitrary targets. Cap displayed output, but hash the full stream before truncation (see Task 5). Use the same `relay.Handler` for `memoryd`, `gwd`, `execd`, and `gitd`; do not create four protocols.

- [ ] **Step 4: Update the run spec and failure matrix**

```bash
--network none \
-v "$AEP_LANE_SOCKETS:/run/aep:rw" \
--env AEP_EXEC_SOCKET=/run/aep/exec.sock \
--env-file <scrubbed.env>   # no provider or GitHub keys
```

Failure: `exec.sock` down -> pause with a bounded retry, then quarantine `blocked:exec-relay-unavailable`; no model fallback in the lane. HLD §9: "Model inference occurs outside the lane; lanes have no model credential."

- [ ] **Step 5: Add ACs and prompt-injection controls**

CAP-01 AC: GIVEN a `--network none` lane, WHEN it attempts a provider call, THEN it fails with `ENETUNREACH`; WHEN it runs an allowlisted command via `exec.sock`, THEN it succeeds. A lane cannot originate a model request; the host harness treats lane output as untrusted data. Add a follow-up prompt-injection test to the host harness slice.

- [ ] **Step 6: Run the check and commit**

```bash
python3 scripts/check_design_invariants.py --check
git add docs/plan/aep-lld-v1.1.html docs/plan/aep-hld-v1.1.html docs/plan/aep-backlog-v1.1.html docs/draft-proposal.html
git commit -m "docs(plan): run model inference outside zero-egress lanes"
```

---

### Task 3: Move Git control to a host relay and mask `.git` (C10)

**Files:**
- Modify: `docs/plan/aep-lld-v1.1.html` §8.1, §9.3, §11
- Modify: `docs/plan/aep-backlog-v1.1.html` CAP-01 (line 175), AC-01.2, PR-07
- Modify: `docs/plan/aep-hld-v1.1.html` §5.2, §9
- Test: `check_design_invariants.py`

**Interfaces:**
- Produces: `internal/gitd` (`git.sock`), `GitRequest{Op, Paths, Message, Branch}`, `GitPolicy`; `/workspace/.git` mask.

- [ ] **Step 1: Run the failing check**

```bash
python3 scripts/check_design_invariants.py --check
```

Expected: C10 fails because `git.sock` and the `.git` mask are absent.

- [ ] **Step 2: Mask `.git` and remove host Git metadata**

A bind mount of a linked worktree includes its `.git` file, which points at the host repository. Mask it explicitly:

```bash
-v "$worktree:/workspace:rw" \
-v "$AEP_STATE_DIR/empty-git-file:/workspace/.git:ro" \
-v "$AEP_LANE_SOCKETS:/run/aep:rw" \
--env AEP_GIT_SOCKET=/run/aep/git.sock
```

The lane sees no usable `.git`. All Git operations go through `git.sock`: `status`, `diff`, `add`, `commit`, `log`, `branch`. The host runs them in the real worktree with `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_SYSTEM=/dev/null`, `GIT_OPTIONAL_LOCKS=0`, hooks disabled or host-controlled, and a host commit identity. Reject `.git/` paths, `-C`, `--no-verify`, and hook injection.

- [ ] **Step 3: Define build-tool behavior**

`GOFLAGS=-buildvcs=false` is sufficient for Go. For Cargo/npm/Make scripts that call `git`, provide a read-only `git` shim on `PATH` that proxies only `rev-parse`, `describe`, and `status` to `git.sock`; writes still require an explicit relay operation. Document the shim path and the unsupported commands. Do not claim every build script works without it.

- [ ] **Step 4: Update the backlog and Tier-2 path**

Rewrite `aep-backlog-v1.1.html:175` and AC-01.2: remove lane-local `GIT_INDEX_FILE=/tmp/index` and concurrent lane commits; state that commits are serialized by `git.sock`. Tier 2 uses an independent clone; the host fetches the patch or branch after verification. The receipt records a host-side `TestedTreeDigest` and base commit, not a guest-local SHA.

- [ ] **Step 5: Address push**

`git.sock` does not expose `push`. Pushes go through the host supervisor after PR creation; if `git.sock push` is kept, document the `ghg` API-cap exemption, cap it separately, and audit it. Do not let a lane push with host credentials silently.

- [ ] **Step 6: Add ACs and run the check**

CAP-01 AC: GIVEN a lane with a host worktree, WHEN it commits through `git.sock`, THEN the commit appears on the lane branch in the host repository, `/workspace/.git` contains no `gitdir:` pointer, and `git -C /workspace rev-parse` fails. Add negative tests for path traversal, `.git/` paths, and hook injection.

```bash
python3 scripts/check_design_invariants.py --check
git add docs/plan/aep-lld-v1.1.html docs/plan/aep-hld-v1.1.html docs/plan/aep-backlog-v1.1.html
git commit -m "docs(plan): commit through a host git relay and mask .git in lanes"
```

---

### Task 4: Fix memory semantics and admission (C6, C11)

**Files:**
- Modify: `docs/plan/aep-lld-v1.1.html` §4.1, §6, §11
- Modify: `docs/plan/aep-backlog-v1.1.html` CAP-07, AC-07
- Modify: `docs/plan/aep-hld-v1.1.html` §6 note
- Test: `check_design_invariants.py`

**Interfaces:**
- Produces: `MiB`, `Bytes`, `MemoryView{Total, Available, Limit}`, `Validate(total Bytes)`, `Admit(req) error`.

- [ ] **Step 1: Run the failing checks**

```bash
python3 scripts/check_design_invariants.py --check
```

Expected: C6 fails. C11's physical-floor assertion is already green at head; the admission-wording and busy-host assertions are new and fail until Step 4/5.

- [ ] **Step 2: Introduce typed units and one vantage point**

```go
type MiB uint64
type Bytes uint64

func (m MiB) Bytes() (Bytes, error) // rejects overflow
type MemoryView struct {
    Total     Bytes // profile minimum
    Available Bytes // admission
    Limit     Bytes // cgroup or VM limit; zero means none
}
```

`Profile.Validate(total memory.Bytes)` compares the preset sum to the detected total, not `VMMemoryMiB` alone. `Profile` takes `memory.MiB`/`memory.Bytes` and primitives, never `internal/admission.Request`, so there is no profile→admission→profile import cycle. Use the existing `Request` type from LLD §4.6 for `Admit`; do not introduce a parallel `ReservationReq`. State the vantage: `aep boot` runs on the host; profile minimum uses host total; on `mac-colima-vz` the VM budget comes from the Colima config; inside a container, admission uses cgroup `memory.max`/`memory.current`. A 4 GB container on a 64 GB host must not pass an 8 GB profile check by reading host total. Clarify that the existing `aep boot` 384 MiB `AvailableBytes` check is an admission preflight, not the profile minimum.

- [ ] **Step 3: Replace the predicate**

```text
reqBytes, err := req.MemMiB.Bytes()
if err != nil || req.MemMiB == 0 -> ErrInvalidRequest
if host < reqBytes -> ErrNoCapacity("host floor")
if host-reqBytes < floorBytes -> ErrNoCapacity("host floor")
if used > budget || req.MemMiB > budget-used -> ErrNoCapacity("tier memory budget")
```

The subtraction is safe only after the `host < reqBytes` guard; state that explicitly so a reader does not reintroduce the underflow. Keep the ceiling check. Reservation/start ordering: write reservation, start container, mark active; `aep lane reap` garbage-collects a reservation with no container.

- [ ] **Step 4: Replace the test table**

| Available | Request | Floor | Used/Budget | Expected |
|---|---|---|---|---|
| 1 GiB | 2 GiB | 384 MiB | 0 / 4 GiB | reject (`host floor`) |
| 2.375 GiB | 2 GiB | 384 MiB | 0 / 4 GiB | admit (exact floor) |
| 2.374 GiB | 2 GiB | 384 MiB | 0 / 4 GiB | reject (below floor) |
| 8 GiB | 0 | 384 MiB | 0 / 4 GiB | reject (`invalid request`) |
| 8 GiB | `math.MaxUint64` MiB | 384 MiB | 0 / 4 GiB | reject (`invalid request`) |
| 8 GiB | 1 MiB | 384 MiB | 4 GiB / 4 GiB | reject (`tier memory budget`) |

- [ ] **Step 5: Add the busy-host AC**

> **AC-07.3 (Busy Host):** GIVEN an 8 GB physical host with only 1 GB currently available, WHEN `aep profile detect` runs, THEN it selects `nano-8g` (total >= 7.5 GiB); WHEN a 2 GB lane is admitted, THEN it receives `ErrNoCapacity` from admission, not a profile error.

- [ ] **Step 6: Run the check and commit**

```bash
python3 scripts/check_design_invariants.py --check
git add docs/plan/aep-lld-v1.1.html docs/plan/aep-hld-v1.1.html docs/plan/aep-backlog-v1.1.html
git commit -m "docs(plan): use typed memory and checked admission arithmetic"
```

---

### Task 5: Specify full-stream signed receipts (C12)

**Files:**
- Modify: `docs/plan/aep-lld-v1.1.html` §3, §11
- Modify: `docs/plan/aep-backlog-v1.1.html` PR-11b
- Modify: `docs/plan/aep-hld-v1.1.html` §9
- Modify: `docs/draft-proposal.html` line 367 ("tail digests" -> full-stream) and the receipt card
- Follow-up slice (not this PR): `internal/verifier/runner` full-stream hashing; `internal/ledger` receipt sequence
- Test: `check_design_invariants.py`; future Go/Python tests

**Interfaces:**
- Produces: `CommandReceipt.StdoutSha`, `CommandReceipt.StderrSha`, `RunReceipt{Nonce, IssuedAt, LedgerSeq, KeyID, Signature}`, `HashingWriter`.

- [ ] **Step 1: Run the failing check**

```bash
python3 scripts/check_design_invariants.py --check
```

Expected: C12 fails; the runner has only 64 KiB tail hashes.

- [ ] **Step 2: Specify full-stream hashing**

`TailCappedBuffer` keeps the tail for display. Add a `HashingWriter` that hashes every byte and retains the tail:

```go
type HashingWriter struct {
    h    hash.Hash
    tail *TailCappedBuffer
}
func (w *HashingWriter) Write(p []byte) (int, error) // hash + tail
func (w *HashingWriter) Sum() string                 // full-stream SHA-256
```

`CommandReceipt` gains `StdoutSha`, `StderrSha`; tails remain display-only. A byte-0 change in a 128 KiB stream must change `StdoutSha`. The exec relay may cap displayed output, but hashing happens before truncation. Replace the draft line 367 phrase "SHA-256 tail digests" with "SHA-256 full-stream digests"; the C12 checker must bind draft line 367 and LLD §3/§11 as well as backlog PR-11b and HLD §9.

- [ ] **Step 3: Define the signed receipt**

```go
type RunReceipt struct {
    IssueID                 string
    CommitSHA               string
    BaseSHA                 string
    TestedTreeDigest        string // digest of the tree actually tested
    PatchDigest             string
    EgressProof             string
    Commands                []CommandReceipt
    MemoryInscriptionDigest string
    Nonce                   string
    IssuedAt                string // RFC 3339, fixed precision
    LedgerSeq               uint64
    KeyID                   string
    Signature               string
}
```

- `StdoutSha`/`StderrSha` at run level are removed; the per-command digests are canonical. If a run-level digest is needed, define it as SHA-256 of the concatenated command stdout digests in execution order.
- `MemoryInscriptionDigest = SHA-256(canonical({issue_id, commit_sha, patch_digest, ledger_seq, inscription_ids}))`, excluding receipt fields. A stale digest (issue/commit mismatch or older `LedgerSeq`) refuses close.
- `Nonce` is 16-32 random bytes, durably recorded. `LedgerSeq` is allocated atomically in `$AEP_STATE_DIR/receipts.seq` with `lock.FileLock` (the repo's cross-platform lock), not raw `flock`. Replay fails after a verifier restart or against a second verifier.
- `IssuedAt` is a fixed RFC 3339 string. Use one canonical encoding for the signed bytes: length-prefixed UTF-8 fields in sorted name order (name length, name, value length, value), implemented identically in Go and Python. Do not use Python `json.dumps(sort_keys=True)` and call it JCS. The signed payload is the canonical encoding of every field except `Signature`.
- Sign with Ed25519. The public key is distributed out-of-band (release key or config pin); the private key stays in the host keyring. `KeyID` selects the key and supports rotation.

- [ ] **Step 4: Replace the acceptance criteria**

> **AC-12.1:** GIVEN two runs with the same base/commit, patch, and egress proof but different test output, WHEN receipts are generated, THEN the receipts differ in `Commands[].StdoutSha`/`Commands[].StderrSha` and `Signature`.
>
> **AC-12.2:** GIVEN a valid receipt replayed with an old nonce or ledger sequence, WHEN `VerifyReceipt` runs after a verifier restart, THEN it returns false.
>
> **AC-12.3:** GIVEN a receipt with an altered output byte, wrong key, missing signature, or stale memory inscription, WHEN verified, THEN it returns false.

- [ ] **Step 5: Reconcile the Python verifier**

`scripts/mechanical_verify.py` already has `stdout_sha256`, `stderr_sha256`, and `chain_sha256`, but hashes capped output and has no signature. Declare the Go `RunReceipt` canonical and mark the Python receipts legacy read-only, or add the signature/nonce/sequence fields in a follow-up. Do not leave two formats with the same field names and different meanings.

- [ ] **Step 6: Add the checker and commit**

The checker asserts the fields and the full-output AC. The follow-up slice adds the Go/Python tests listed at the end.

```bash
python3 scripts/check_design_invariants.py --check
git add docs/plan/aep-lld-v1.1.html docs/plan/aep-hld-v1.1.html docs/plan/aep-backlog-v1.1.html docs/draft-proposal.html
git commit -m "docs(plan): bind full test output into signed run receipts"
```

---

### Task 6: Re-audit C1-C5 and align all four documents

**Files:**
- Modify: whichever of the four docs still carries a stale statement (Task 1 sets the rule; this task audits for residual copies)
- Test: `check_design_invariants.py`

- [ ] **Step 1: Run the check**

```bash
python3 scripts/check_design_invariants.py --check
```

Expected: C1-C5 checks fail where the docs still disagree.

- [ ] **Step 2: Fix C1 and C3**

- C1: LLD §4.9 has the `VerifyEgressProbe` digest sentence; HLD §9 and draft C1 card agree.
- C2: HLD §9, LLD §7, and draft C2 card state the explicit override; LLD §8.2's decision record includes the override, reason, operator identity, and timestamp.
- C3: define one `relay.Handler` in LLD §4.4/§4.5/§9.2 and link `memory.sock`/`ghg.sock` to it. No separate `RelayServer`/`GHGRelay` protocols.

- [ ] **Step 3: Fix C4 and C5, do not resolve them early**

- C4: replace every unconditional microVM-only re-verification sentence: HLD lines 116, 138, 172, 183; LLD T11; draft lines 264, 367, 402; backlog PR-11. Use the `Requirement` rule.
- C5: make nano consistent: HLD 3584 MiB (3.5 GiB) Tier 1 + 1536 MiB (1.5 GiB) Tier 2; LLD 3584 + 1536 = 7680; draft matrix; backlog AC. Remove "Tier 2 disabled" and "Tier 2 off". Also fix LLD line 285: macOS has no local gVisor fallback, so the sentence must not claim one.
- HLD §12: remove stale claims that C1/C4 are remediated.
- HLD D8 line 57: require the explicit authenticated override.

- [ ] **Step 4: Add cross-document anchors**

Link HLD/backlog/draft to the LLD capability anchor. Do not duplicate the enum. The checker asserts one definition site and section-bound references.

- [ ] **Step 5: Run the check and commit**

```bash
python3 scripts/check_design_invariants.py --check
git add docs/plan/aep-lld-v1.1.html docs/plan/aep-hld-v1.1.html docs/plan/aep-backlog-v1.1.html docs/draft-proposal.html
git commit -m "docs(plan): align C1-C5 and cross-document capability references"
```

---

### Task 7: Wire the guard, render artifacts, and close threads

**Files:**
- Modify: `.github/workflows/ci.yml` docs-lint job
- Modify: `docs/plan/*.pdf` if rendered
- GitHub review threads

- [ ] **Step 1: Wire the checker into CI**

Add to `docs-lint`:

```yaml
- name: Design invariants
  run: |
    python3 scripts/check_design_invariants.py --self-test
    python3 scripts/check_design_invariants.py --check
```

The self-test fails every bad fixture; the check passes only after Tasks 1-6.

- [ ] **Step 2: Run the full local gate**

```bash
python3 scripts/check_design_invariants.py --self-test
python3 scripts/check_design_invariants.py --check
# CI/Linux: go test ./...
# macOS: go test ./internal/platform/... (the runner fallback test needs setsid and is known-red locally)
gofmt -l cmd internal
git diff --check
```

- [ ] **Step 3: Render PDFs with a pinned renderer**

Do not hardcode `/Applications/Google Chrome.app`. Use a pinned Chromium image by digest or a CI render job:

```bash
docker run --rm -v "$PWD:/work" -w /work \
  zenika/alpine-chrome@sha256:<digest> \
  --headless --disable-gpu --no-sandbox \
  --print-to-pdf=docs/plan/aep-hld-v1.1.pdf \
  file:///work/docs/plan/aep-hld-v1.1.html
```

Repeat for the LLD and backlog. Verify `Creator (Chromium)` and the page counts (9/14/5 at head; assert them or update them deliberately):

```bash
strings docs/plan/aep-hld-v1.1.pdf | grep -m1 'Creator (Chromium)'
# macOS:
mdls -name kMDItemNumberOfPages docs/plan/aep-hld-v1.1.pdf
# CI/Linux fallback:
python3 - <<'PY'
import re
data = open("docs/plan/aep-hld-v1.1.pdf", "rb").read()
print("pages:", len(re.findall(rb"/Type\s*/Page\b", data)))
PY
```

If no pinned renderer is available, do not merge with stale PDFs. Either render in CI or remove the PDFs from this PR and record a follow-up. Do not both claim "no stale PDF" and "leave the PDF unchanged."

- [ ] **Step 4: Commit the CI and PDF changes**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(docs): gate design invariants"
git add docs/plan/*.pdf
git commit -m "docs(plan): regenerate PDF artifacts"
```

If the PDFs are deferred, omit the second commit and state the follow-up in the PR body.

- [ ] **Step 5: Push before resolving**

```bash
git push
gh pr checks 133 --repo pratik-saptarshi/autonomous-engineering-platform
```

Do not resolve any thread until the fixing commit is on the branch and CI is green. Reply to C1-C3 with the fixing SHA; reply to C4-C12 only after their checks pass. Resolve C4/C5 last, after all four documents agree.

- [ ] **Step 6: Request re-review**

Do not mark the PR ready or merge. Post a summary mapping each C-ID to its commit and check, then request a fresh Codex/human review.

---

## Follow-Up Implementation Slices (Out of Scope for PR #133)

These are named so the code does not hide inside a docs PR. Each is a separate PR with tests:

- **Slice A: `internal/profile`** — `TestIsolationRequirement` (`NoFloor` admits; an unset zero-value requirement fails closed; user-space floor rejects hardware-unattested; hardware floor rejects gVisor; exact kind passes), `TestBackendKindIsolationPairing` (gVisor+hardware and cube-kvm+user-space rejected by `NewBackend`), `TestNanoValidateAt7_5GiB` (sum 7680 <= 7680), `TestNanoTier2Admission` (1536 admits; 2048 `ErrNoCapacity`), `TestNanoTier2PeakRSS` (measured peak RSS <= 1536 MiB including gVisor sentry).
- **Slice B: `internal/admission`** — `TestAdmitMemoryTable` with explicit `MemoryView`, `used`, `budget`, `req` for the six rows; `TestAdmitUnderflow` (`req=MaxUint64 MiB`, host 8 GiB -> `ErrInvalidRequest`); `TestAdmissionCrashRecovery`.
- **Slice C: `internal/execd`/`internal/gitd`** — `TestLaneCannotInfer` (`ENETUNREACH`); `TestExecPolicyAllowlist` (argv, no shell); `TestGitRelayCommit` (commit on host; `test -f /workspace/.git`, no `gitdir:` pointer, and `git -C /workspace rev-parse` fails); `TestGitRelayRejectsGitPath`; `TestGitRelayRejectsTraversal`.
- **Slice D: `internal/verifier/runner` + `internal/ledger`** — `TestReceiptFullStream` (128 KiB, byte 0 changed); `TestReceiptSignature`; `TestReceiptReplay` (after ledger restart); `TestMemoryInscriptionDigestStale`; Python receipt migration or legacy marker.
- **Slice E: host harness prompt-injection controls** — `TestLaneOutputIsUntrusted` (canary in lane output is not interpolated into the system prompt; tool results are structured).

## Test Plan

**In this PR (docs + checker):**

| Check | Command | Expected |
|---|---|---|
| Checker self-test | `python3 scripts/check_design_invariants.py --self-test` | pass; every bad fixture fails |
| Checker on docs | `python3 scripts/check_design_invariants.py --check` | pass after Tasks 1-6 |
| Existing Go tests | `go test ./...` (CI/Linux) or `go test ./internal/platform/...` (macOS; runner fallback needs `setsid`) | pass, with the known macOS runner exception stated |
| Format | `gofmt -l cmd internal` | no output |
| Diff hygiene | `git diff --check` | no output |
| PDF | `strings` + `mdls` (macOS) or Python page count (Linux) | Chromium creator; page counts 9/14/5 or deliberately updated |
| CI | `gh pr checks 133` | green |

**Follow-up slices:** the named tests in the section above. They are not claimed as passing in this PR.

## Acceptance Criteria

- C6 (checker C6 + Slice B): admission has no unsigned subtraction; zero, overflow, exact floor, below floor, and full-budget cases pass the table.
- C7 (checker C7 + Slice C): model execution is outside the lane; `exec.sock` is the only tool channel; no `model.sock`; no provider credential in the lane; no lane-originated model request.
- C8 (checker C8 + Slice A): re-verification uses the immutable `Requirement`; the target is probed before the original run; gVisor-only hosts quarantine hardware-floor work before execution; gVisor-eligible work re-verifies in gVisor.
- C9 (checker C9-1/C9-2 + Slice A): `Tier2Supported()` is derived from an attested `Backend`; `/dev/kvm` is only `KVMProbe`; capability and capacity have distinct failure reasons.
- C10 (checker C10 + Slice C): `/workspace/.git` is masked; `git.sock` commit appears on the host branch; Tier 2 uses an independent clone and a host-side `TestedTreeDigest`.
- C11 (checker C11 + Slice B): profile minimum uses `TotalRAM >= 7.5 GiB`; admission uses available RAM and floor; busy-host AC passes.
- C12 (checker C12 + Slice D): full stdout/stderr digests, nonce, ledger sequence, and Ed25519 signature are specified; altered output and replay fail verification.
- C1/C3 (checker C1/C3): restored in Tasks 1/6; C2 (checker C2) is verified at head; C4/C5 (checker C8/C5) are reopened, fixed, and only then resolved.
- `nano-8g` (checker C5): fits 7680 MiB and has one Tier-2 story across all four docs.
- CI green; PDFs consistent or explicitly deferred; no unresolved P2 thread remains.

## Scope Rulings

- **PR #133 remains docs-only.** The checker is the only new executable artifact. Go code moves to the named follow-up slices.
- **C4/C5 are reopened.** Do not claim they were closed by `6287a93`; later commits changed the surrounding facts.
- **No new `internal/receipt` package.** Receipts live with the existing runner and ledger primitives.
- **No `model.sock`.** The model boundary is the host harness; the lane gets `exec.sock`.
- **No host `.git` mount.** Git control is a host relay; `/workspace/.git` is masked; Tier 2 uses an independent clone.
