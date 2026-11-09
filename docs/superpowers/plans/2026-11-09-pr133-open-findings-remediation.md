# PR #133 Open-Finding Remediation Implementation Plan (v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the open P2 findings on PR #133 (C6-C12) and re-audit the earlier fixes (C1-C5, with C4/C5 reopened) by making the Tier-2 capability model, lane boundaries, admission arithmetic, and receipt semantics internally consistent and mechanically checkable at head `080e28b`.

**Architecture:** One attested capability value type replaces the stored `Tier2Supported` boolean and the unranked `IsolationClass` string. Re-verification is gated by a task risk floor, not by the origin run's class. Model execution moves outside the lane; the lane exposes an `exec.sock` tool relay instead of a model relay. Git control moves to a host-side `git.sock` relay; no host `.git` directory is mounted into a lane. Memory arithmetic uses typed units and a checked predicate. Receipts hash full output streams and carry a nonce, ledger sequence, and Ed25519 signature. A structural invariant checker, written before the fixes, guards every claim.

**Tech Stack:** HTML design docs; Python 3.9 stdlib invariant checker with negative fixtures; Go 1.27 interface sketches and tests; Docker or CI Chromium for PDF rendering; GitHub Actions `docs-lint` job.

**Spec:** `docs/plan/aep-hld-v1.1.html`, `docs/plan/aep-lld-v1.1.html`, `docs/plan/aep-backlog-v1.1.html`, `docs/draft-proposal.html`; PR #133 findings C1-C12.

**Baseline:** `080e28b` (`docs/plan/aep-backlog-v1.1.html` is 525 lines; CAP-08/11/12 no longer exist; C11 is already fixed in AC-07.1; C12 must be retargeted to `internal/verifier/runner` and PR-11b/PR-12).

## Decision Log

- **D1: Capability is a value, not a field.** `Profile.Backend` carries kind, isolation, provenance, and probe evidence. `Tier2Supported()` is a method; `KVMProbe` is evidence only. This makes `Tier2Supported=true` with no backend unrepresentable.
- **D2: Re-verification uses a risk floor.** A task's `MinIsolation` is set by its risk class (`tier:factory` untrusted -> hardware microVM; explicitly gVisor-eligible -> user-space kernel). The origin run never lowers the floor. If the floor is unavailable, quarantine before execution.
- **D3: The model runs outside the lane.** The trusted host harness performs inference and selects the model tier; the lane exposes `exec.sock` for allowlisted commands. No `model.sock`, no provider credential, no arbitrary prompt channel.
- **D4: Git control runs on the host.** Tier 1 lanes use `git.sock` for status/diff/commit/push; the worktree is mounted without `.git`. Tier 2 uses an independent clone and the host fetches the patch after verification.
- **D5: Receipts are signed and full-stream.** `StdoutSha`/`StderrSha` hash every byte; tails are display-only. `Nonce`, `IssuedAt`, `LedgerSeq`, and `KeyID` make replay detectable. Ed25519 is used so an external auditor can verify without the host key.

## Global Constraints

- Fail closed: an unknown backend, unattested isolation, missing model boundary, or missing Git relay must quarantine or refuse, never silently degrade.
- One fact lives in one place: LLD §4.1/§4.9 defines the capability types; HLD, backlog, and draft reference that anchor. Do not restate a different enum or table.
- No lane has direct network egress, provider credentials, GitHub credentials, or host Git metadata.
- Units are explicit: `MiB` and `Bytes` are distinct types; profile minimum uses total RAM, admission uses available RAM.
- Re-verification isolation must meet the task's `MinIsolation`; it is never origin-relative.
- No stored derived booleans. If a value can disagree with its source, derive it.
- Write the failing invariant check first; run it after every task.
- Conventional Commits, one commit per task. Prefix doc tasks with `docs(plan):` and checker tasks with `test(docs):`.
- Do not resolve C4 or C5 until the four documents agree. Do not resolve any thread before its fixing commit is pushed and CI is green.
- Do not commit a stale PDF. Render from the same HTML or leave the PDF unchanged and record a follow-up.

## Review Focus

- A KVM-free host with gVisor must be admitted for gVisor-eligible work and must quarantine hardware-floor work before execution, not after.
- A `--network none` lane must still execute tests and commit through host relays, with no model or Git credential in the lane.
- Available memory below the request must reject, not wrap.
- A receipt must change when any test-output byte changes, and a replayed receipt must fail.
- A busy but correctly sized host must pass profile detection and fail only admission.
- `nano-8g` must have one coherent Tier-2 story across HLD, LLD, backlog, and draft.

---

### Task 0: Write the failing invariant checker first

**Files:**
- Create: `scripts/check_design_invariants.py`
- Create: `scripts/tests/fixtures/design-invariants/*.html`
- Test: the checker's own fixtures; expected to fail on current docs

**Interfaces:**
- Produces: `check_design_invariants.py --check` and `--self-test`.

- [ ] **Step 1: Write the checker**

Use Python 3.9 stdlib only. Read the four docs as text and assert:

1. **C9:** LLD defines `type Backend struct`, `type Isolation struct`, and `AtLeast`; no `Tier2Supported bool` field; `Tier2Supported()` is a method; `KVMProbe` is separate.
2. **C9:** no sentence equating `Tier2Supported` with `/dev/kvm`; HLD references the LLD anchor.
3. **C6:** no `host - req.MemMiB` subtraction; a `host < reqBytes` comparison exists; zero and overflow requests are rejected.
4. **C7:** `exec.sock` appears in the run spec; `model.sock` does not; HLD says model execution is outside the lane; no provider key in the lane env.
5. **C10:** `git.sock` appears in the run spec; no `-v .../.git:` mount; the lane test plan includes a relay commit.
6. **C11:** `TotalRAM >= 7.5 GiB` is present; `< 8 GB available RAM` is absent; admission uses available RAM plus floor.
7. **C12:** receipt fields include `StdoutSha`, `StderrSha`, `Nonce`, `IssuedAt`, `LedgerSeq`, `KeyID`, `Signature`; the AC binds full output, not only tails.
8. **C8/C4:** no unconditional "hardware-isolated microVM" rule for all re-verification; `MinIsolation` appears in LLD and HLD; gVisor is allowed only for gVisor-eligible tasks.
9. **C5:** no "Tier 2 disabled" for `nano-8g`; nano's lane size matches the HLD 1.5 GB budget.
10. **C1:** LLD §4.9 contains the `VerifyEgressProbe` digest sentence.

- [ ] **Step 2: Add negative fixtures**

For each check, add one `bad-<n>.html` fixture containing the negation ("we do not use X") and one deletion fixture. The self-test must fail every bad fixture and pass every good fixture. This is the first nail: a presence-only grep is not acceptable.

- [ ] **Step 3: Run the failing check**

```bash
python3 scripts/check_design_invariants.py --self-test   # expected: pass
python3 scripts/check_design_invariants.py --check       # expected: fail, listing C5-C12/C1
```

Do not wire `--check` into CI yet; it is red until Task 7.

- [ ] **Step 4: Commit**

```bash
git add scripts/check_design_invariants.py scripts/tests/fixtures/design-invariants
git commit -m "test(docs): add failing structural invariant checker for PR #133"
```

---

### Task 1: Replace the capability model and set the re-verification floor (C9, C8, C4, C5)

**Files:**
- Modify: `docs/plan/aep-lld-v1.1.html` §4.1, §4.9, §7, §10, §12 T4/T10/T11
- Modify: `docs/plan/aep-hld-v1.1.html` §6, §9, §11
- Modify: `docs/plan/aep-backlog-v1.1.html` CAP-02, CAP-07, PR-10/PR-11
- Modify: `docs/draft-proposal.html` profile matrix and C4/C5 cards
- Test: `check_design_invariants.py`

**Interfaces:**
- Produces: `BackendKind`, `IsolationKind`, `Provenance`, `Backend`, `Isolation`, `Isolation.AtLeast`, `Profile.Backend`, `Profile.KVMProbe`, `Profile.Tier2Supported()`, `Task.MinIsolation`.

- [ ] **Step 1: Run the failing checks**

```bash
python3 scripts/check_design_invariants.py --check
```

Expected: checks 1, 2, 8, and 9 fail.

- [ ] **Step 2: Define the value types in LLD §4.1/§4.9**

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
    evidence [32]byte // probe or attestation digest; zero means unusable
}

func (i Isolation) Valid() bool { return i.kind != IsolationNone && i.evidence != ([32]byte{}) }
func (i Isolation) AtLeast(min Isolation) bool {
    return i.Valid() && min.Valid() && i.kind >= min.kind
}

type Backend struct {
    kind       BackendKind
    isolation  Isolation
    provenance Provenance
    evidence   [32]byte
}

func (b Backend) Usable() bool { return b.kind != BackendNone && b.isolation.Valid() && b.evidence != ([32]byte{}) }
func (b Backend) Isolation() Isolation { return b.isolation }

type Profile struct {
    // ... existing sizing fields ...
    Backend  Backend     // zero value means no backend
    KVMProbe ProbeResult // evidence only; never the capability definition
}

func (p Profile) Tier2Supported() bool { return p.Backend.Usable() }
func (p Profile) Tier2Admissible(req ReservationReq) error
```

`Tier2Supported` is not a field. `Provenance` is not a strength. A remote hardware VM must carry attestation evidence; a remote user-space backend does not become hardware because it is remote.

- [ ] **Step 3: Separate capability from capacity**

Update the LLD failure matrix and dispatch table:

- No usable backend -> `blocked:unsupported-tier2-no-sandbox`.
- Usable backend but `MaxTier2Lanes == 0` or budget below `Tier2LaneMiB` -> `blocked:tier2-capacity-exhausted` (terminal for this profile; do not wait forever).
- `Tier2Supported()` is capability only; `Tier2Admissible()` is capacity.

Set profile-specific Tier-2 values. For `nano-8g`, choose the documented one-lane gVisor story:

```text
nano-8g: Tier2BudgetMiB=1536, Tier2LaneMiB=1536, MaxTier2Lanes=1
```

Remove "Tier 2 disabled" from `docs/draft-proposal.html` and update LLD line 90/92 so the default is not a global 4096-6144 reservation. Add AC: `Admit(Tier2, nano, 1536)` succeeds; a 2048 request returns `ErrNoCapacity` with the capacity reason.

- [ ] **Step 4: Gate dispatch and re-verification on `MinIsolation`**

Add to the task model:

```go
type Task struct {
    // ...
    MinIsolation Isolation // risk-derived, not origin-derived
}
```

Rules:

- `tier:factory` with untrusted native code -> `IsolationHardwareMicroVM`.
- Explicitly gVisor-eligible task (recorded risk reassessment) -> `IsolationUserSpaceKernel`.
- A hardware-origin run never lowers its floor; it must re-verify in hardware isolation.
- If the resolved backend cannot meet `MinIsolation`, quarantine before execution.
- `VerifyResult` records the actual `Isolation` and `BackendEvidence`; the post-run value is audit data, not the gate.

Update HLD §5.2 line 172, §9 line 183, LLD T11, draft lines 367/402, and backlog PR-11. Replace every unconditional "hardware-isolated microVM" sentence with the floor rule.

- [ ] **Step 5: Restore the C1 egress sentence**

In LLD §4.9, restore: "`VerifyEgressProbe` checks the SHA-256 digest of the in-VM probe evidence; a missing or mismatched digest rejects the run." Keep the acknowledgement guard as a separate check.

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
- Modify: `docs/plan/aep-hld-v1.1.html` §5.2, §9, §11
- Modify: `docs/plan/aep-backlog-v1.1.html` CAP-01, PR-06/PR-07
- Modify: `docs/draft-proposal.html` core services and lane lifecycle
- Test: `check_design_invariants.py`

**Interfaces:**
- Produces: `internal/execd` (`exec.sock`), `ExecRequest{Argv, Cwd, Timeout, Env}`, `ExecPolicy`, and a common relay contract shared with `memoryd`/`gwd`/`gitd`.

- [ ] **Step 1: Run the failing check**

```bash
python3 scripts/check_design_invariants.py --check
```

Expected: check 4 fails because the docs have no model path and no `exec.sock`.

- [ ] **Step 2: Make the boundary decision explicit**

Write in HLD §5.2 and LLD §9.3:

> The trusted host harness runs the agent loop and all model inference. A lane is a tool executor: it receives allowlisted commands over `exec.sock`, runs them under its cgroup and `--network none`, and returns stdout/stderr/exit status. Lanes hold no provider key and cannot make model requests. The host harness selects the model tier (standard/measured for Ralph, frontier/thorough for factory) before dispatching commands.

If offline lane autonomy is a hard requirement, that is a separate ADR; it is not implemented here. Do not reintroduce `model.sock` as a caveat.

- [ ] **Step 3: Define the exec relay**

Add to LLD:

```go
type ExecRequest struct {
    LaneID  string
    Argv    []string
    Cwd     string
    Timeout time.Duration
    Env     map[string]string // allowlisted keys only
}

type ExecPolicy interface {
    Allow(laneID string, argv []string) error
    ScrubEnv(env map[string]string) map[string]string
}
```

The relay authenticates the lane with `SO_PEERCRED` or a per-lane token, rejects path traversal and non-allowlisted binaries, caps output, and writes an audit record. It is one implementation of the common `relay.Handler` contract; do not create a fourth ad-hoc protocol.

- [ ] **Step 4: Update the run spec and failure matrix**

Replace the model/credentials assumption in LLD §9.3:

```bash
--network none \
-v "$AEP_LANE_SOCKETS:/run/aep:rw" \
--env AEP_EXEC_SOCKET=/run/aep/exec.sock \
--env-file <scrubbed.env>   # no provider or GitHub keys
```

Failure: `exec.sock` down -> pause and retry with a bound, then quarantine `blocked:exec-relay-unavailable`; no model fallback in the lane. Update HLD §9: "Model inference occurs outside the lane; lanes have no model credential."

- [ ] **Step 5: Update the backlog and draft**

Add an AC to CAP-01: GIVEN a `--network none` lane, WHEN it attempts a provider call, THEN it fails with `ENETUNREACH`; WHEN it runs an allowlisted command via `exec.sock`, THEN it succeeds. Add a canary test: a file containing `CANARY-<random>` cannot appear in any model request because the lane cannot make one.

- [ ] **Step 6: Run the check and commit**

```bash
python3 scripts/check_design_invariants.py --check
git add docs/plan/aep-lld-v1.1.html docs/plan/aep-hld-v1.1.html docs/plan/aep-backlog-v1.1.html docs/draft-proposal.html
git commit -m "docs(plan): run model inference outside zero-egress lanes"
```

---

### Task 3: Move Git control to a host relay (C10)

**Files:**
- Modify: `docs/plan/aep-lld-v1.1.html` §8.1, §9.3, §11
- Modify: `docs/plan/aep-backlog-v1.1.html` CAP-01, PR-07
- Modify: `docs/plan/aep-hld-v1.1.html` §5.2, §9
- Test: `check_design_invariants.py`

**Interfaces:**
- Produces: `internal/gitd` (`git.sock`), `GitRequest{Op, Paths, Message, Branch}`, `GitPolicy`.

- [ ] **Step 1: Run the failing check**

```bash
python3 scripts/check_design_invariants.py --check
```

Expected: check 5 fails because only `<worktree>:/workspace` is mounted.

- [ ] **Step 2: Remove the `.git` mount**

Do not mount the host `.git` directory. Mount the worktree read-write at `/workspace`; the lane has no `.git`. All Git operations go through `git.sock`:

```text
status, diff, add, commit, log, branch, push
```

The host runs the operation in the lane's worktree with `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_SYSTEM=/dev/null`, `GIT_OPTIONAL_LOCKS=0`, and hooks disabled or host-controlled. The relay rejects paths outside the lane worktree, rejects `-C` and arbitrary config, and keeps credentials on the host. Build tools that need VCS metadata run with `GOFLAGS=-buildvcs=false` or receive a read-only generated stamp.

- [ ] **Step 3: Define the Tier-2 path**

Tier 2 uses an independent clone inside the guest. The host fetches the patch or branch after verification; the guest never sees host `.git`. The receipt records the host-side commit SHA, not a guest-local SHA.

- [ ] **Step 4: Update the manifest and run spec**

Replace the `worktree`-only assumption in LLD §8.1 with `worktree` plus `git_relay: /run/aep/git.sock`. Add the `git.sock` mount to §9.3. Add the lane test:

```bash
# Through the relay, not the lane shell:
git.sock status --porcelain
git.sock commit -m "lane smoke"
# Host verification:
git -C "$AEP_REPO" log -1 --format=%H -- "$worktree"
```

Expected: the commit exists on the host branch; no `.git` is visible in `/workspace`; a direct `git` invocation in the lane fails or is absent.

- [ ] **Step 5: Update CAP-01 and PR-07**

Add AC: GIVEN a lane with a host worktree, WHEN it commits through `git.sock`, THEN the commit appears on the lane branch in the host repository and no host `.git` directory is mounted. Add a negative test: a path traversal or hook injection is rejected.

- [ ] **Step 6: Run the check and commit**

```bash
python3 scripts/check_design_invariants.py --check
git add docs/plan/aep-lld-v1.1.html docs/plan/aep-hld-v1.1.html docs/plan/aep-backlog-v1.1.html
git commit -m "docs(plan): commit through a host git relay without mounting .git"
```

---

### Task 4: Fix memory semantics and admission (C6, C11)

**Files:**
- Modify: `docs/plan/aep-lld-v1.1.html` §4.1, §6, §11
- Modify: `docs/plan/aep-backlog-v1.1.html` CAP-07, AC-07
- Modify: `docs/plan/aep-hld-v1.1.html` §6 note
- Test: `check_design_invariants.py`

**Interfaces:**
- Produces: `MiB`, `Bytes`, `MemoryView{Total, Available, Limit}`, `Admit(req) error`.

- [ ] **Step 1: Run the failing checks**

```bash
python3 scripts/check_design_invariants.py --check
```

Expected: checks 3 and 6 fail; the backlog AC-07.1 is already fixed but the LLD predicate is not.

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

State the vantage explicitly: `aep boot` runs on the host; profile minimum uses host total; on `mac-colima-vz` the VM budget comes from the Colima config; inside a container, admission uses the cgroup `memory.max`/`memory.current` view. A 4 GB container on a 64 GB host must not pass an 8 GB profile check by reading host total.

- [ ] **Step 3: Replace the predicate**

```text
reqBytes, ok := req.MemMiB.Bytes()
if !ok || req.MemMiB == 0 -> ErrInvalidRequest
if host < reqBytes -> ErrNoCapacity("host floor")
if host-reqBytes < floorBytes -> ErrNoCapacity("host floor")
if used > budget || req.MemMiB > budget-used -> ErrNoCapacity("tier memory budget")
```

Remove the subtraction. Keep the ceiling check. Define reservation/start ordering: write the reservation, start the container, then mark it active; a crash between steps is reaped by `aep lane reap` (reservation without a container is garbage-collected).

- [ ] **Step 4: Replace the test table**

| Available | Request | Floor | Expected |
|---|---|---|---|
| 1 GiB | 2 GiB | 384 MiB | reject (`host floor`) |
| 2.375 GiB | 2 GiB | 384 MiB | admit (exact floor) |
| 2.374 GiB | 2 GiB | 384 MiB | reject (below floor) |
| 0 | 0 | 384 MiB | reject (`invalid request`) |
| 8 GiB | `math.MaxUint64` MiB | 384 MiB | reject (`invalid request`) |
| used=budget | 1 MiB | 384 MiB | reject (`tier memory budget`) |

- [ ] **Step 5: Add the busy-host AC**

In CAP-07:

> **AC-07.3 (Busy Host):** GIVEN an 8 GB physical host with only 1 GB currently available, WHEN `aep profile detect` runs, THEN it selects `nano-8g` (total >= 7.5 GiB); WHEN a 2 GB lane is admitted, THEN it receives `ErrNoCapacity` from admission, not a profile error.

- [ ] **Step 6: Run the check and commit**

```bash
python3 scripts/check_design_invariants.py --check
git add docs/plan/aep-lld-v1.1.html docs/plan/aep-hld-v1.1.html docs/plan/aep-backlog-v1.1.html
git commit -m "docs(plan): use typed memory and checked admission arithmetic"
```

---

### Task 5: Bind full output into signed receipts (C12)

**Files:**
- Modify: `docs/plan/aep-lld-v1.1.html` §3, §11
- Modify: `docs/plan/aep-backlog-v1.1.html` PR-11b, PR-12
- Modify: `docs/plan/aep-hld-v1.1.html` §9
- Modify: `docs/draft-proposal.html` receipt card
- Modify: `internal/verifier/runner/runner.go` (follow-up implementation slice)
- Test: `check_design_invariants.py` plus future Go tests

**Interfaces:**
- Produces: `CommandReceipt.StdoutSha`, `CommandReceipt.StderrSha`, `RunReceipt{Nonce, IssuedAt, LedgerSeq, KeyID, Signature}`, `HashingWriter`.

- [ ] **Step 1: Run the failing check**

```bash
python3 scripts/check_design_invariants.py --check
```

Expected: check 7 fails; the current runner has only 64 KiB tail hashes.

- [ ] **Step 2: Add full-stream hashing**

`TailCappedBuffer` keeps the tail for display. Add a `HashingWriter` that hashes every byte and retains the tail:

```go
type HashingWriter struct {
    h   hash.Hash
    tail *TailCappedBuffer
}
func (w *HashingWriter) Write(p []byte) (int, error) // hash + tail
func (w *HashingWriter) Sum() string                 // full-stream SHA-256
```

`CommandReceipt` gains `StdoutSha` and `StderrSha`; `StdoutTailSha`/`StderrTailSha` remain display-only. A difference at byte 0 of a 128 KiB stream must change `StdoutSha`.

- [ ] **Step 3: Define the signed receipt**

```go
type RunReceipt struct {
    IssueID                 string
    CommitSHA               string
    PatchDigest             string
    EgressProof             string
    Commands                []CommandReceipt
    StdoutSha               string
    StderrSha               string
    MemoryInscriptionDigest string
    Nonce                   string
    IssuedAt                time.Time
    LedgerSeq               uint64
    KeyID                   string
    Signature               string
}
```

Sign RFC 8785 canonical JSON of all fields except `Signature` with Ed25519. The public key is distributed in the repo/config; the private key stays in the host keyring. `VerifyReceipt` checks the signature, the `Nonce`, and a monotonic `LedgerSeq` against ledger state. A missing or stale `MemoryInscriptionDigest` refuses `CloseWithReceipt`.

- [ ] **Step 4: Replace the acceptance criteria**

> **AC-12.1:** GIVEN two runs with the same commit, patch, and egress proof but different test output, WHEN receipts are generated, THEN the receipts differ in `StdoutSha`/`StderrSha` and `Signature`.
>
> **AC-12.2:** GIVEN a valid receipt replayed with an old nonce or ledger sequence, WHEN `VerifyReceipt` runs, THEN it returns false.
>
> **AC-12.3:** GIVEN a receipt with an altered output byte, wrong key, or missing signature, WHEN verified, THEN it returns false.

- [ ] **Step 5: Add negative tests**

List: altered byte 0 of a 128 KiB stdout, altered stderr, replayed nonce, wrong `KeyID`, missing signature, non-monotonic `LedgerSeq`, missing memory inscription. Each must fail verification; the valid case must pass.

- [ ] **Step 6: Run the check and commit**

```bash
python3 scripts/check_design_invariants.py --check
git add docs/plan/aep-lld-v1.1.html docs/plan/aep-hld-v1.1.html docs/plan/aep-backlog-v1.1.html docs/draft-proposal.html internal/verifier/runner/runner.go
git commit -m "docs(plan): bind full test output into signed run receipts"
```

---

### Task 6: Re-audit C1-C5 at head and align all four documents

**Files:**
- Modify: whichever of the four docs still carries a stale statement
- Test: `check_design_invariants.py`

- [ ] **Step 1: Run the check**

```bash
python3 scripts/check_design_invariants.py --check
```

Expected: all checks pass except any stale C1-C5 wording.

- [ ] **Step 2: Verify C1-C3**

- C1: LLD §4.9 has the `VerifyEgressProbe` digest sentence; HLD §9 and draft C1 card agree.
- C2: no automatic Tier-1 downgrade; the override is explicit and audited.
- C3: `memory.sock`/`ghg.sock` use the common relay contract; no host loopback from a lane.

- [ ] **Step 3: Fix C4 and C5, do not resolve them early**

- C4: replace every unconditional microVM-only re-verification sentence in HLD 172/183, LLD T11, draft 367/402, and backlog PR-11 with the `MinIsolation` rule.
- C5: make the nano-8g Tier-2 story consistent: HLD 1.5 GB / 1 lane, LLD 1536 MiB / 1 lane, draft no "Tier 2 disabled", backlog AC matches.

- [ ] **Step 4: Add cross-document anchors**

Link HLD/backlog/draft to the LLD capability anchor. Do not duplicate the enum. The checker asserts a single definition site.

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
- Modify: `docs/plan/*.pdf` only if rendered successfully
- GitHub review threads

- [ ] **Step 1: Wire the checker into CI**

Add to the `docs-lint` job:

```yaml
- name: Design invariants
  run: |
    python3 scripts/check_design_invariants.py --self-test
    python3 scripts/check_design_invariants.py --check
```

The self-test must fail on the negative fixtures and pass on the good ones. The check must fail on the pre-fix docs; it is expected to pass only after Tasks 1-6.

- [ ] **Step 2: Run the full local gate**

```bash
python3 scripts/check_design_invariants.py --self-test
python3 scripts/check_design_invariants.py --check
go test ./...
git diff --check
```

- [ ] **Step 3: Render PDFs with a pinned renderer**

Do not hardcode `/Applications/Google Chrome.app`. Use a pinned Chromium container or the CI render job. Example, only if the image is available:

```bash
docker run --rm -v "$PWD:/work" -w /work zenika/alpine-chrome:with-puppeteer \
  --headless --disable-gpu --no-sandbox \
  --print-to-pdf=docs/plan/aep-hld-v1.1.pdf \
  file:///work/docs/plan/aep-hld-v1.1.html
```

Repeat for the LLD and backlog. Verify `Creator (Chromium)` and a non-zero page count:

```bash
strings docs/plan/aep-hld-v1.1.pdf | grep -m1 'Creator (Chromium)'
mdls -name kMDItemNumberOfPages docs/plan/aep-hld-v1.1.pdf
```

If no pinned renderer is available, leave the PDF unchanged and record a follow-up. Do not commit a PDF from a different renderer without checking the visual diff.

- [ ] **Step 4: Push before resolving**

```bash
git push
gh pr checks 133 --repo pratik-saptarshi/autonomous-engineering-platform
```

Do not resolve any thread until the fixing commit is on the branch and CI is green. Reply to C1-C3 with the fixing SHA; reply to C4-C12 only after their specific checks pass. Resolve C4/C5 last, after the four documents agree.

- [ ] **Step 5: Request re-review**

Do not mark the PR ready or merge. Post a summary mapping each C-ID to its commit and check, then request a fresh Codex/human review.

---

## Test Plan

| Check | Command | Expected |
|---|---|---|
| Checker self-test | `python3 scripts/check_design_invariants.py --self-test` | pass; every negative fixture fails |
| Checker on docs | `python3 scripts/check_design_invariants.py --check` | pass after Tasks 1-6 |
| Go tests | `go test ./...` | pass |
| Capability rank | `TestIsolationAtLeast` | none < user-space < hardware; remote is provenance, not strength |
| Nano capacity | `TestTier2AdmissionNano` | 1536 MiB admits; 2048 returns capacity error; no backend quarantines |
| Re-verification floor | `TestMinIsolationQuarantine` | hardware floor on gVisor-only host quarantines before execution |
| Admission | `TestAdmitMemoryTable` | six rows above pass |
| Receipt output | `TestReceiptFullStream` | byte 0 difference changes `StdoutSha` |
| Receipt replay | `TestReceiptReplay` | old nonce/sequence fails |
| Git relay | `TestGitRelayCommit` | commit visible on host; no `.git` in lane |
| Model boundary | `TestLaneCannotInfer` | provider call fails; `exec.sock` command succeeds |
| PDF | `strings` + `mdls` | Chromium creator; expected page count |
| CI | `gh pr checks 133` | green |

## Acceptance Criteria

- C6: admission has no unsigned subtraction; zero, overflow, exact floor, below floor, and full-budget cases pass the table.
- C7: model execution is outside the lane; `exec.sock` is the only tool channel; no `model.sock`; no provider credential in the lane; canary test passes.
- C8: re-verification uses `MinIsolation`; gVisor-only hosts quarantine hardware-floor work before execution; gVisor-eligible work re-verifies in gVisor.
- C9: `Tier2Supported()` is derived from an attested `Backend`; `/dev/kvm` is only `KVMProbe`; capability and capacity have distinct failure reasons.
- C10: no host `.git` mount; `git.sock` commit appears on the host branch; Tier 2 uses an independent clone.
- C11: profile minimum uses `TotalRAM >= 7.5 GiB`; admission uses available RAM and floor; busy-host AC passes.
- C12: full stdout/stderr digests, nonce, ledger sequence, and Ed25519 signature are present; altered output and replay fail verification.
- C1-C3 remain fixed; C4/C5 are fixed and only then resolved.
- `nano-8g` has one Tier-2 story across all four docs.
- CI green; PDFs consistent or explicitly deferred; no unresolved P2 thread remains.

## Scope Rulings

- **Delivers the fixes but does not merge the PR.** The implementation plan changes docs and one code slice; merge still waits on re-review.
- **C4/C5 are reopened.** Do not claim they were closed by `6287a93`; later commits changed the surrounding facts.
- **No new `internal/receipt` package.** Receipts live with the existing runner and ledger primitives.
- **No new `model.sock`.** The model boundary is the host harness; the lane gets `exec.sock`.
- **No `.git` mount.** Git control is a host relay; Tier 2 uses an independent clone.
