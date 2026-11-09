# PR #133 Open-Finding Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the seven open P2 findings on PR #133 by making the Tier-2 capability model, zero-egress lane I/O, admission arithmetic, and receipt semantics internally consistent across the four design documents, with mechanically checkable acceptance criteria that prevent recurrence.

**Architecture:** Treat `docs/plan/aep-lld-v1.1.html` §4.1 and §7 as the canonical capability model. Derive `Tier2Supported` from the resolved sandbox backend and carry an explicit `IsolationClass` (hardware microVM > user-space kernel > remote). Add a host-mediated `model.sock` relay beside the existing `memory.sock` and `ghg.sock` relays. Make re-verification use the same-or-stronger isolation class as the original run. Fix the unsigned subtraction and the total-vs-available RAM criteria, bind test-output digests into a signed receipt, and add one small consistency script to CI.

**Tech Stack:** HTML design docs, Chromium headless PDF rendering, Go interface sketches (design-only where packages do not exist yet), Bash + ripgrep for invariant checks, GitHub Actions `docs-lint` job.

**Spec:** `docs/plan/aep-hld-v1.1.html`, `docs/plan/aep-lld-v1.1.html`, `docs/plan/aep-backlog-v1.1.html`, `docs/draft-proposal.html`; PR #133 review findings C6-C12.

## Global Constraints

- Do not weaken an isolation guarantee to resolve a contradiction. Choose the stronger implementable rule and record it.
- One fact lives in one place. The LLD §4.1/§7 model is canonical; HLD, backlog, and draft proposal reference it instead of restating a different rule.
- Lanes have no direct network egress and no provider, GitHub, or memory credentials. All cross-boundary traffic is host-mediated over a Unix socket (Tier 1) or vsock/outbox (Tier 2).
- A task's re-verification isolation class MUST be at least as strong as its execution isolation class. Never re-verify weaker.
- Unknown or unavailable capability fails closed: quarantine before execution, never silent downgrade.
- Keep HTML well-formed. Re-render the committed PDFs from the same HTML with Chromium headless.
- Conventional Commits, one commit per task. Use `docs(plan): ...` for doc-only tasks and `test(docs): ...` for the invariant check.
- Do not resolve review threads until the fixing commit is pushed and CI is green.

## Review Focus

- A KVM-free host with gVisor must not be told Tier 2 is unsupported while §7 admits it, and must not be admitted for hardware-only re-verification.
- A `--network none` lane must still be able to infer, read memory, use GitHub, inspect its branch, and commit without credentials.
- Admission must reject, not admit, when available memory is below the request.
- A receipt must change when test output changes, and an unsigned receipt must not verify.
- A busy but correctly sized host must not be rejected by the minimum-hardware check.

---

### Task 1: Canonicalize the sandbox capability model (C9)

**Files:**
- Modify: `docs/plan/aep-lld-v1.1.html` §4.1 (line ~79), §7 (line ~239), §10 (line ~325)
- Modify: `docs/plan/aep-hld-v1.1.html` §6 table (line ~142), §9 invariant (line ~176), §11 risk row (line ~204)
- Modify: `docs/plan/aep-backlog-v1.1.html` CAP-02/AC-02, CAP-07/AC-07, CAP-08/AC-08
- Test: `scripts/check-design-invariants.sh` (created in Task 8)

**Interfaces:**
- Produces: `SandboxBackend`, `IsolationClass`, `Profile.KVMProbe`, `Profile.Tier2Supported`, `Profile.ResolveSandboxBackend()`, `Profile.CanReverify(original IsolationClass) bool`.

- [ ] **Step 1: Write the failing check**

Add these assertions to the Task 8 script now, or run them ad hoc:

```bash
! rg -n 'Tier2Supported\s+bool\s+// true iff /dev/kvm' docs/plan/aep-lld-v1.1.html
rg -n 'Tier2Supported.*ResolveSandboxBackend|ResolveSandboxBackend.*Tier2Supported' docs/plan/aep-lld-v1.1.html
rg -n 'IsolationClass' docs/plan/aep-lld-v1.1.html docs/plan/aep-hld-v1.1.html
```

Expected: the first command fails today because line 93 still defines `Tier2Supported` from `/dev/kvm`.

- [ ] **Step 2: Replace the profile struct in LLD §4.1**

```go
type IsolationClass string

const (
    IsolationNone          IsolationClass = ""
    IsolationHardwareVM    IsolationClass = "hardware-microvm"
    IsolationUserSpace     IsolationClass = "user-space-kernel"
    IsolationRemote        IsolationClass = "remote"
)

type Profile struct {
    // ... existing sizing fields ...
    KVMProbe        bool           // /dev/kvm probe result; never the capability definition
    SandboxBackend  SandboxBackend // resolved at boot; BackendNone when none available
    IsolationClass  IsolationClass // class of SandboxBackend
    Tier2Supported  bool           // == (SandboxBackend != BackendNone)
}

func (p Profile) ResolveSandboxBackend() SandboxBackend // cube-kvm -> libkrun -> gvisor -> remote if configured
func (p Profile) CanReverify(original IsolationClass) bool // verification class >= original class
```

Add `BackendNone SandboxBackend = ""` to the backend constants next to `BackendCubeKVM`, `BackendLibkrun`, `BackendGVisor`, `BackendRemote`.

- [ ] **Step 3: Rewrite the host-family rule in LLD §4.1**

Replace "`Tier2Supported` iff `/dev/kvm` probes present" with:

> `Tier2Supported` is derived from `ResolveSandboxBackend()`, never from `/dev/kvm` alone. The KVM probe is recorded in `KVMProbe` and only selects the `cube-kvm` candidate. macOS may resolve `libkrun` without nested KVM; KVM-free Linux may resolve `gvisor`; `remote-api` counts only when a remote endpoint is explicitly configured.

- [ ] **Step 4: Update the HLD risk row and invariant**

In HLD §11, replace "set `Tier2Supported` from the result [of the `/dev/kvm` probe]" with "set `KVMProbe` from the result; set `Tier2Supported` from `ResolveSandboxBackend()`". In HLD §9, add:

> Tier-2 support is a function of the resolved backend, not host family or KVM alone. A KVM-free host with `runsc` is Tier-2 capable; a host with no local backend and no configured remote endpoint quarantines.

- [ ] **Step 5: Align the backlog acceptance criteria**

Update AC-02.1.1.1 to require `ResolveBackend` for all three local backends, and AC-07.1.1.1/AC-08 to state that `Tier2Supported` is true when gVisor resolves. Add a negative AC: GIVEN no local backend and no remote endpoint, THEN `Tier2Supported=false` and Tier-2 tasks quarantine.

- [ ] **Step 6: Run the check and commit**

```bash
bash scripts/check-design-invariants.sh
git add docs/plan/aep-lld-v1.1.html docs/plan/aep-hld-v1.1.html docs/plan/aep-backlog-v1.1.html
git commit -m "docs(plan): derive tier-2 capability from resolved sandbox backend"
```

---

### Task 2: Make re-verification isolation-aware (C8)

**Files:**
- Modify: `docs/plan/aep-hld-v1.1.html` §9 invariant
- Modify: `docs/plan/aep-lld-v1.1.html` §10 failure matrix, §12 T11, §11 test plan
- Modify: `docs/plan/aep-backlog-v1.1.html` CAP-11 / AC-11.1.1
- Test: `scripts/check-design-invariants.sh`

**Interfaces:**
- Consumes: `IsolationClass`, `CanReverify` from Task 1.
- Produces: `VerifyResult.IsolationClass` and the policy that verification class >= execution class.

- [ ] **Step 1: Write the failing check**

```bash
! rg -n 'must execute inside a fresh hardware-isolated microVM' docs/plan/aep-hld-v1.1.html
rg -n 'same or stronger isolation|CanReverify|IsolationClass' docs/plan/aep-hld-v1.1.html docs/plan/aep-lld-v1.1.html
```

Expected: fails today because HLD §9 still requires a hardware microVM unconditionally.

- [ ] **Step 2: Rewrite the invariant**

Replace the unconditional sentence with:

> Independent re-verification of a Tier-2 patch MUST execute in a fresh, disposable sandbox whose `IsolationClass` is at least as strong as the class used for the original run. Hardware microVM is required when the original run used hardware isolation; gVisor is acceptable only for gVisor-origin work. A host that cannot provide the required class quarantines before execution. Tier 1 still performs static analysis only.

- [ ] **Step 3: Update the failure matrix and T11**

Add a row: "Re-verification class unavailable" -> `CanReverify` false -> `quarantine: blocked:reverify-isolation-unavailable`. Update T11 acceptance criteria to record `isolation_class` in `VerifyResult` and to reject a weaker class.

- [ ] **Step 4: Update backlog CAP-11**

Change "inside fresh, disposable hardware microVMs or gVisor sandboxes" to the class-ordered rule. Add AC-11.1.1.3: GIVEN a gVisor-origin run on a KVM-free host, WHEN re-verification runs, THEN it uses a fresh gVisor sandbox and records `isolation_class=user-space-kernel`; GIVEN a hardware-microVM-origin run, THEN a gVisor-only host quarantines before re-verification.

- [ ] **Step 5: Run the check and commit**

```bash
bash scripts/check-design-invariants.sh
git add docs/plan/aep-hld-v1.1.html docs/plan/aep-lld-v1.1.html docs/plan/aep-backlog-v1.1.html
git commit -m "docs(plan): require same-or-stronger isolation for re-verification"
```

---

### Task 3: Add the model relay to zero-egress lanes (C7)

**Files:**
- Modify: `docs/plan/aep-lld-v1.1.html` §4.5 or new §4.10, §9.2 compose, §9.3 run spec, §10 failure matrix
- Modify: `docs/plan/aep-hld-v1.1.html` §5.1 services, §9 invariant, §11 risk
- Modify: `docs/plan/aep-backlog-v1.1.html` Domain 2 relay CAP and ACs
- Modify: `docs/draft-proposal.html` core-services table and lane lifecycle
- Test: `scripts/check-design-invariants.sh`

**Interfaces:**
- Produces: `internal/modeld` (`aep modeld`), `model.sock`, request/response schema, `ModelRelayPolicy`.

- [ ] **Step 1: Write the failing check**

```bash
rg -n 'model\.sock|aep modeld|model relay' docs/plan/aep-lld-v1.1.html docs/plan/aep-hld-v1.1.html
```

Expected: no matches today; the only services are `memory.sock` and `ghg.sock`.

- [ ] **Step 2: Specify the relay**

Add to LLD §4.5 (or §4.10):

> `aep modeld` is a host-side relay that holds provider credentials and serves `model.sock` to lanes. It accepts a bounded JSON request (`model`, `messages`, `max_tokens`, `tools`, `request_id`), forwards only to an allowlisted provider endpoint, streams the response, and writes an audit record with prompt/response digests and token counts. It strips arbitrary headers, enforces request/response size caps, and never exposes provider keys to the lane. A rejected model or endpoint returns a typed policy error.

- [ ] **Step 3: Update the run spec and compose file**

Add to the LLD §9.2 substrate compose services: `modeld` with the provider secret mounted on the host side only. Add to §9.3:

```bash
-v "$AEP_SOCKETS/model.sock:/run/aep/model.sock:rw" \
--env AEP_MODEL_SOCKET=/run/aep/model.sock \
# no provider key in --env-file
```

The lane client must connect to the socket; `--network none` remains unchanged.

- [ ] **Step 4: Add the failure mode and invariants**

Failure matrix: "Model relay down or policy-denied" -> pause the lane and retry with backoff; after the bounded retry, quarantine `blocked:model-relay-unavailable`; never fall back to direct provider network. HLD §9 add: "Lanes hold no model credentials and reach inference only through `aep modeld`." Draft proposal adds model relay to the core-services list and the lane lifecycle.

- [ ] **Step 5: Add backlog ACs**

AC: GIVEN a lane with `--network none`, WHEN it requests inference, THEN the request reaches `model.sock` and no provider credential exists in the lane. GIVEN a non-allowlisted model, THEN the relay rejects it. GIVEN the relay is down, THEN the lane does not open direct egress.

- [ ] **Step 6: Run the check and commit**

```bash
bash scripts/check-design-invariants.sh
git add docs/plan/aep-lld-v1.1.html docs/plan/aep-hld-v1.1.html docs/plan/aep-backlog-v1.1.html docs/draft-proposal.html
git commit -m "docs(plan): add host-mediated model relay for zero-egress lanes"
```

---

### Task 4: Mount linked-worktree Git metadata into lanes (C10)

**Files:**
- Modify: `docs/plan/aep-lld-v1.1.html` §8.1 manifest, §9.3 run spec, §11 test plan
- Modify: `docs/plan/aep-backlog-v1.1.html` lane lifecycle CAP/AC
- Test: `scripts/check-design-invariants.sh`

**Interfaces:**
- Produces: a container-visible Git layout: worktree at `/workspace`, repository metadata at the same absolute path as the host, writable only for `.git/worktrees/<laneId>`.

- [ ] **Step 1: Write the failing check**

```bash
rg -n '\.git/worktrees|relative-paths|independent clone' docs/plan/aep-lld-v1.1.html
```

Expected: no matches today; §9.3 mounts only `<worktree>:/workspace`.

- [ ] **Step 2: Add the mount layout**

Use relative-path worktrees where Git supports it, otherwise bind-mount at identical absolute paths:

```bash
# Preferred: create with relative paths so the .git file is self-contained
git -C "$repo" worktree add --relative-paths -b "$branch" "$wt_path" "$base_sha"

# Fallback: expose the repo metadata at the same absolute path inside the lane
-v "$repo/.git:$repo/.git:ro" \
-v "$repo/.git/worktrees/$lane_id:$repo/.git/worktrees/$lane_id:rw" \
-v "$wt_path:/workspace" -w /workspace
```

For Tier 2 microVMs, use an independent clone or a read-only metadata mount; never give a Tier-2 guest writable host Git metadata.

- [ ] **Step 3: Add the lane verification step**

Add to §11 Test Plan and the lane lifecycle AC:

```bash
git -C /workspace rev-parse --git-dir
git -C /workspace status --porcelain
git -C /workspace commit --allow-empty -m "lane smoke"
git -C /workspace log -1 --format=%H
```

Expected: all succeed inside the lane, and the commit appears on the lane branch in the host repository.

- [ ] **Step 4: Run the check and commit**

```bash
bash scripts/check-design-invariants.sh
git add docs/plan/aep-lld-v1.1.html docs/plan/aep-backlog-v1.1.html
git commit -m "docs(plan): expose linked-worktree metadata to lanes"
```

---

### Task 5: Fix the admission underflow (C6)

**Files:**
- Modify: `docs/plan/aep-lld-v1.1.html` §6 admission algorithm, §11 test plan
- Modify: `docs/plan/aep-backlog-v1.1.html` CAP-08 ACs
- Test: `scripts/check-design-invariants.sh`

**Interfaces:**
- Produces: an underflow-safe admission predicate with explicit overflow rejection.

- [ ] **Step 1: Write the failing check**

```bash
! rg -n 'host\s*-\s*req\.MemMiB\*MiB\s*<' docs/plan/aep-lld-v1.1.html
rg -n 'host\s*<\s*req\.MemMiB\*MiB|budget\s*-\s*used' docs/plan/aep-lld-v1.1.html
```

Expected: fails today because §6 still subtracts before comparing.

- [ ] **Step 2: Replace the predicate**

```text
reqBytes := req.MemMiB * MiB
if req.MemMiB != 0 && reqBytes/MiB != req.MemMiB -> ErrInvalidRequest("memory overflow")
if host < reqBytes                              -> ErrNoCapacity("host floor")
if host - reqBytes < profile.MemFloorMiB*MiB    -> ErrNoCapacity("host floor")
if used > budget || req.MemMiB > budget - used  -> ErrNoCapacity("tier memory budget")
```

Keep the existing ceiling and reservation logic unchanged.

- [ ] **Step 3: Add the admission test table**

Add to LLD §11 and CAP-08 AC:

| Available | Request | Floor | Expected |
|---|---|---|---|
| 1 GiB | 2 GiB | 384 MiB | reject (`host floor`) |
| 2.5 GiB | 2 GiB | 384 MiB | admit |
| 2.375 GiB | 2 GiB | 384 MiB | reject (below floor) |
| 8 GiB | `math.MaxUint64` | 384 MiB | reject (`invalid request`) |
| used=budget | 1 MiB | 384 MiB | reject (`tier memory budget`) |

- [ ] **Step 4: Run the check and commit**

```bash
bash scripts/check-design-invariants.sh
git add docs/plan/aep-lld-v1.1.html docs/plan/aep-backlog-v1.1.html
git commit -m "docs(plan): make admission memory check underflow-safe"
```

---

### Task 6: Validate minimum host size against total RAM (C11)

**Files:**
- Modify: `docs/plan/aep-backlog-v1.1.html` AC-07.1.1.3
- Modify: `docs/plan/aep-hld-v1.1.html` §6 profile table note
- Test: `scripts/check-design-invariants.sh`

- [ ] **Step 1: Write the failing check**

```bash
! rg -n 'less than 8 GB available RAM|with < 8 GB available RAM' docs/plan/aep-backlog-v1.1.html
rg -n 'total RAM' docs/plan/aep-backlog-v1.1.html
```

- [ ] **Step 2: Rewrite the AC**

> **AC-07.1.1.3 (Minimum Hardware):** GIVEN a host with less than 8 GB of **total** RAM, WHEN `profile.Validate` runs, THEN it returns an error and refuses to start the substrate. Available RAM is not a minimum-hardware signal.

Add AC-07.1.1.4:

> **AC-07.1.1.4 (Busy Host Admission):** GIVEN a correctly sized host whose current available RAM is below 8 GB because other workloads are running, WHEN the supervisor restarts, THEN `profile.Validate` succeeds and admission alone decides lane capacity using `AvailableBytes`, the request, and `MemFloorMiB`.

- [ ] **Step 3: Add the HLD note**

In HLD §6, add: "Profile selection uses total RAM; admission uses available RAM. A busy host is not a mis-sized host."

- [ ] **Step 4: Run the check and commit**

```bash
bash scripts/check-design-invariants.sh
git add docs/plan/aep-backlog-v1.1.html docs/plan/aep-hld-v1.1.html
git commit -m "docs(plan): validate minimum hardware against total RAM"
```

---

### Task 7: Bind test output into signed receipts (C12)

**Files:**
- Modify: `docs/plan/aep-backlog-v1.1.html` CAP-12 struct/functions/ACs
- Modify: `docs/plan/aep-lld-v1.1.html` receipt interface, if present, and §11 test plan
- Modify: `docs/plan/aep-hld-v1.1.html` §9 invariant
- Test: `scripts/check-design-invariants.sh`

**Interfaces:**
- Produces: `Receipt.StdoutDigest`, `Receipt.StderrDigest`, `Receipt.TailDigest`, `Receipt.MemoryDigest`, `Receipt.Signature`; `Generate` and `VerifyReceipt`.

- [ ] **Step 1: Write the failing check**

```bash
rg -n 'stdout_digest|stderr_digest|tail_digest' docs/plan/aep-backlog-v1.1.html
rg -n 'signature|HMAC' docs/plan/aep-backlog-v1.1.html
```

Expected: `tail_digest` exists as a field but is absent from the AC formula; no signature field exists.

- [ ] **Step 2: Replace the receipt definition**

```go
type Receipt struct {
    IssueID       string `json:"issue_id"`
    CommitSHA     string `json:"commit_sha"`
    PatchDigest   string `json:"patch_digest"`
    EgressProof   string `json:"egress_proof"`
    StdoutDigest  string `json:"stdout_digest"`
    StderrDigest  string `json:"stderr_digest"`
    TailDigest    string `json:"tail_digest"`
    MemoryDigest  string `json:"memory_digest"`
    Signature     string `json:"signature"`
}
```

`Generate` canonicalizes all fields except `Signature`, computes SHA-256 for `TailDigest`, then HMAC-SHA256 signs the canonical bytes with a host-held key. `VerifyReceipt` recomputes the digest and verifies the HMAC in constant time.

- [ ] **Step 3: Rewrite the acceptance criteria**

> **AC-12.1.1.1 (Output-Bound Digest):** GIVEN a completed task, WHEN `Generate` runs, THEN the digest covers `commit_sha`, `patch_digest`, `egress_proof`, `stdout_digest`, `stderr_digest`, and `memory_digest`. Two runs with identical commit/patch/egress but different test output MUST produce different receipts.

> **AC-12.1.1.3 (Signature Required):** GIVEN a receipt with a missing, altered, or wrong-key signature, WHEN `VerifyReceipt` runs, THEN it returns false and `CloseWithReceipt` refuses the close.

- [ ] **Step 4: Add the negative tests**

List in LLD §11 / CAP-12: altered stdout -> verify false; altered stderr -> verify false; changed commit -> verify false; replayed receipt with old signature -> verify false; valid receipt -> verify true.

- [ ] **Step 5: Run the check and commit**

```bash
bash scripts/check-design-invariants.sh
git add docs/plan/aep-backlog-v1.1.html docs/plan/aep-lld-v1.1.html docs/plan/aep-hld-v1.1.html
git commit -m "docs(plan): bind test output into signed run receipts"
```

---

### Task 8: Add the design-invariant check to CI

**Files:**
- Create: `scripts/check-design-invariants.sh`
- Modify: `.github/workflows/ci.yml` docs-lint job
- Test: run locally, then introduce one regression and confirm it fails

- [ ] **Step 1: Write the script**

The script must fail on:

1. `Tier2Supported` defined from `/dev/kvm` in LLD/HLD.
2. Missing `ResolveSandboxBackend` in LLD §4.1 and §7.
3. Missing `IsolationClass` in LLD and HLD.
4. `host - req.MemMiB*MiB <` in LLD §6.
5. Missing `model.sock` / `aep modeld` in LLD and HLD.
6. Missing `.git/worktrees` or `relative-paths` in LLD §9.3.
7. `< 8 GB available RAM` in backlog.
8. Receipt AC that omits `stdout_digest` or `stderr_digest`.
9. Receipt `Signature` field missing.

Use `rg -q` and print one line per failure; exit non-zero on any.

- [ ] **Step 2: Wire it into CI**

In `.github/workflows/ci.yml`, add a step to the `docs-lint` job:

```yaml
- name: Check design invariants
  run: bash scripts/check-design-invariants.sh
```

- [ ] **Step 3: Verify the guard catches drift**

```bash
bash scripts/check-design-invariants.sh          # expect pass
# temporarily revert one fix, e.g. reintroduce the /dev/kvm definition
bash scripts/check-design-invariants.sh          # expect fail
git checkout -- docs/plan/aep-lld-v1.1.html
bash scripts/check-design-invariants.sh          # expect pass
```

- [ ] **Step 4: Commit**

```bash
git add scripts/check-design-invariants.sh .github/workflows/ci.yml
git commit -m "test(docs): guard PR #133 design invariants in CI"
```

---

### Task 9: Resolve threads and regenerate artifacts

**Files:**
- Modify: `docs/plan/*.pdf` (regenerated), review threads (GitHub)
- Test: CI + thread state

- [ ] **Step 1: Re-render the PDFs**

```bash
for f in docs/plan/aep-hld-v1.1 docs/plan/aep-lld-v1.1 docs/plan/aep-backlog-v1.1; do
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --headless --disable-gpu --no-pdf-header-footer \
    --print-to-pdf="$f.pdf" "file://$PWD/$f.html"
done
```

Verify each PDF opens, has the expected page count, and reports `Producer: Skia/PDF` (Chromium).

- [ ] **Step 2: Run the full local gate**

```bash
bash scripts/check-design-invariants.sh
git diff --check
npx --yes markdownlint-cli2@0.24.0 "docs/superpowers/plans/2026-11-09-pr133-open-findings-remediation.md"
```

- [ ] **Step 3: Reply to and resolve the five outdated threads**

For each of C1-C5, reply with the fixing commit SHA and a one-line statement of what changed, then resolve the thread. Do not resolve C6-C12 until their checks pass.

- [ ] **Step 4: Push and request re-review**

```bash
git push
gh pr checks 133 --repo pratik-saptarshi/autonomous-engineering-platform
```

Do not mark the PR ready or merge it until CI is green and the bot/ human reviewer has re-reviewed.

---

## Test Plan

| Check | Command | Expected |
|---|---|---|
| Capability model | `bash scripts/check-design-invariants.sh` | pass |
| Admission underflow | grep check from Task 5 | no unchecked subtraction |
| Total-vs-available RAM | grep check from Task 6 | only total RAM gates minimum size |
| Model relay | grep `model.sock`/`aep modeld` | present in LLD and HLD |
| Worktree metadata | grep `.git/worktrees`/`relative-paths` | present in LLD §9.3 |
| Receipt binding | grep `stdout_digest`/`stderr_digest`/`Signature` | present in CAP-12 |
| HTML validity | `npx html-validate docs/plan/*.html` (if available) or browser open | no parse errors |
| PDFs | open each PDF; check page count and Creator | Chromium-rendered, non-empty |
| CI | `gh pr checks 133` | all green |

## Acceptance Criteria

- C6: admission pseudocode uses an underflow-safe comparison and includes the five-case test table.
- C7: `model.sock` / `aep modeld` is specified in LLD and HLD; lanes remain `--network none`; no provider credential enters the lane; relay failure quarantines.
- C8: re-verification requires the same-or-stronger `IsolationClass`; gVisor-only hosts can re-verify gVisor-origin work and quarantine hardware-origin work.
- C9: `Tier2Supported` is derived from `ResolveSandboxBackend()` in LLD, HLD, and backlog; `/dev/kvm` is only `KVMProbe`.
- C10: lane run spec exposes linked-worktree metadata; the lane can run `git rev-parse`, `git status`, and a smoke commit.
- C11: minimum hardware is validated against total RAM; a separate AC covers busy-host admission.
- C12: receipt digest includes stdout/stderr/tail/memory digests; HMAC signature is required and verified; negative tests are listed.
- C1-C5: each outdated thread has a reply with the fixing commit and is resolved.
- CI is green; PDFs are regenerated; no unresolved P2 thread remains.
