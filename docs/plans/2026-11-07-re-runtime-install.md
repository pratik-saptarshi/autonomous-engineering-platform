# RE Runtime Install Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Codify the hand-built reverse-engineering bench (Temurin JDK 25, Ghidra 12.1.4, radare2 6.2.6, REA asserted via pinned `npx`) as one pinned, checksummed, idempotent installer — `scripts/install-re-runtime.sh` — that reproduces the identical bench on a fresh VM under `$HOME` only.

**Architecture:** A single fail-closed bash script in the `boot-gate.sh` mold: a header pin block, a preflight stage, one idempotent install stage per component (probe → skip, or download → checksum → extract/build → re-probe), a marker-guarded shell-environment stage, and a verification stage. Stub-based `--self-test --offline` cases (the `boot-gate.sh`/`lane-coord.sh` precedent) plus one fixture-HOME shell harness give the test surface; CI's existing `shell-lint` (shellcheck + `shfmt -i 2` over `scripts/*.sh`) and `script-tests` jobs cover it once the self-test is wired into `ci.yml`.

**Tech Stack:** Bash (`#!/usr/bin/env bash`, `set -euo pipefail`), `sha256sum`, `curl`, `git`, `gcc`/`make` (radare2 build), shellcheck/shfmt (CI), podman (Task 7 only, if D2 rules it in).

**Spec:** `~/workspace/goals/autonomous-code-defense-factory/hidden_files/plans/2026-11-07-re-runtime-install-plan.html` (draft v1, 2026-11-07; local draft — it does not travel with the PR, so every value an executor needs is copied into this plan). Grounding: `~/TOOLS.md` sections "Go toolchain", "Podman", "Temurin JDK + Ghidra", "pytest", "radare2"; repo survey of `scripts/`, `scripts/tests/`, `.github/workflows/ci.yml` at base (below).

**Base:** `origin/main` @ `49722a3618569ae50804fb43258a0561a9c9fee0` (verified ancestor of this branch, Stage 0).

## Global Constraints

- All GitHub calls go through the gateway: `GHG_ACTOR=<task-slug> ~/go/bin/ghg run -- <gh args>`; pre-flight every publish step with `ghg check` (exit 75 = budget denial: stop, report the stage reached, never bypass). Push and PR-opening each need Pratik's explicit per-action authorization; merging needs his separate per-PR authorization (feature-pr-pipeline Authorization rule).
- **Pins refuse unpinned artifacts (fail closed).** Every fetched or built artifact is declared in the pin block with a full SHA-256 (or, for radare2, tag + full commit). An empty or missing pin field aborts the run; a checksum mismatch aborts before extraction. There is no bypass flag.
- **Install targets only under `$HOME`.** Nothing is written to `/etc`, `/usr/local`, or any root-owned path; nothing requires root. (Those tiers do not survive VM replacement; `$HOME` does.)
- **Staging never uses `/tmp`** (512M tmpfs; the Ghidra zip alone is 543 MiB). All downloads stage under `$HOME/opt/dist/`. Scratch/test dirs are the only `/tmp` use.
- **Memory ceiling:** ~1.6 GiB effective of 7.7 GiB reported (virtio balloon). Build parallelism is hard-capped at `make -j2`; heavy steps (radare2 build, rehearsals) run in isolation, never alongside test suites.
- **Idempotence (pipeline Stage 1 prompt), installer-wide:** running the finished script twice in a row leaves the system byte-identical to one clean run — components probe-pass and skip, the `.bashrc` block is replaced in place between its markers, `~/.profile` is created only if absent. If a run crashes halfway, the next run converges to the same end state: a partial component directory that fails its probe is removed and rebuilt (never patched in place), a partial download fails its checksum and is re-fetched, and the env block is written atomically enough that a torn write is detected by missing end-marker and rewritten whole on the next run. The one accepted difference: staging artifacts in `$HOME/opt/dist/` may remain from the crashed run and are reused only after checksum verification.
- Script conventions (repo-grounded): header comment block stating purpose and contract; first failure prints `INSTALL-RE: <check> FAIL: <reason>` and exits 1 — never warn-and-continue; passing checks print `INSTALL-RE: <name> ok`; a `--self-test --offline` mode with fully self-contained stubs that passes on a stock CI runner (exactly the `boot-gate.sh --self-test --offline` contract).
- CI compatibility: the script must pass `shellcheck scripts/*.sh` and `shfmt -d -i 2 scripts/*.sh`, and its self-test must be added as an explicit step in the `script-tests` job of `.github/workflows/ci.yml` (that job invokes `lane-coord.sh` and `boot-gate.sh` self-tests by name; nothing is auto-discovered for shell scripts). New Python is out of scope; `python3 -m unittest discover -s scripts/tests` must stay green.
- The plan document ships in the PR under `docs/plans/` (Pratik's standing rule, 2026-11-07). Repo files use Markdown; this plan must pass the `docs-lint` job (markdownlint with `.markdownlint.yaml`).
- Out of scope (draft Scope, carried verbatim): installing or vendoring Node, REA itself, Hopper, or IDA; any change to the `reverse_engineering` skill's routing or the 2026-10-21 Ghidra invocation gate; fork-sourcing or apt-sourcing radare2; `@latest` anything.
- Recorded-but-not-encoded quirks (draft is silent; flagged, not invented): `GOTMPDIR=$HOME/.gotmp` matters for Go builds — this script builds no Go, so it neither sets nor checks it. The pytest user-site install and the podman `/etc/containers/` config are non-RE environment pieces; they belong to decision D3 and are not touched by v1 under the recommended default.

## Pin Block (carried verbatim from the draft; full hashes verified 2026-11-07 by `sha256sum` over the staged artifacts in `~/opt/dist/`)

| Component | Version / identity | Source | SHA-256 / commit | Installs to |
|---|---|---|---|---|
| Temurin JDK (LTS) | 25.0.4.1+1 | `github.com/adoptium/temurin25-binaries` release `jdk-25.0.4.1+1`, `OpenJDK25U-jdk_x64_linux_hotspot_25.0.4.1_1.tar.gz` | `dbb698396d478e7fa2b1e50f4103324b2a99b90569ee27c33f2261f9215cf41e` | `~/opt/jdk-25.0.4.1+1` (`JAVA_HOME`) |
| Ghidra | 12.1.4 PUBLIC (2026-09-21) | `github.com/NationalSecurityAgency/ghidra` release `Ghidra_12.1.4_build`, `ghidra_12.1.4_PUBLIC_20260921.zip` (543 MB) | `ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db` | `~/opt/ghidra_12.1.4_PUBLIC` (`GHIDRA_INSTALL_DIR`); `support/` on PATH |
| radare2 | 6.2.6, built from source | `git clone` of upstream `radareorg/radare2` at tag `6.2.6`. Never from Pratik's fork — it carries no tags. Never from apt (stale 5.5.0). | tag = commit `06a7c9d35468676cc3fe6ea299885cf53aa8ad9b`; script asserts HEAD equals this commit after checkout | `~/opt/radare2` via `./configure --prefix=$HOME/opt/radare2 && make -j2 && make install` (~5 min) |
| REA | `rea-agents@6.5.0` | No install. Invoked as `npx -y rea-agents@6.5.0` (pinned; never `@latest`). | — | The script only asserts `node`/`npx` presence and reports absence; it does not install Node. |

## Open Decisions (Pratik's ruling needed at the plan gate)

- **D1 — Script home. Recommended default: `scripts/install-re-runtime.sh`.** Rationale: CI already shellchecks, shfmt-checks, and self-test-wires everything in `scripts/`; a new `runtime/` directory buys a label and costs new CI wiring plus a second convention. (Draft's assumption; this plan is written against it. If D1 flips, Tasks 1–8 move directory and Task 8's CI step changes — nothing else does.)
- **D2 — Container route. Recommended default: in v1, as Task 7 — a separate, independently stoppable final task.** Rationale: the Containerfile is cheap once the script exists and the ESF lessons (CA before downloads; apt list incl. `xz-utils`) are fresh; if the sandbox blocks it, Task 7 stops and records an environmental block without holding Tasks 1–6 or the PR hostage (the PR then notes the deferral).
- **D3 — Scope. Recommended default: RE-only for v1.** Rationale: the stage structure is component-list-driven, so generalizing later (Go, `bd`, pytest, podman config) is an additive PR, not a rewrite; chartering generalization now delays the RE codification behind every other tool on the VM.

## How the Draft's Phases Map onto the Pipeline

- **Draft Phase 0 (planning-wringer, listed-not-run in the draft): NOT skipped and NOT folded into implementation.** It runs as its own gated step after this plan is approved and before Stage 2 (implementation) begins: the wringer panel attacks the pin discipline, the idempotency claims, and the container-route assumptions of this plan, and D1–D3 are surfaced to Pratik with the panel's evidence. This Stages 0–1 run deliberately does not run it (the draft lists it as a separate mandatory gate; a plan-stage agent grading its own plan is the failure mode the wringer exists to prevent). If Pratik waives it in writing at the plan gate, that waiver is recorded in the PR body.
- **Draft Phase 2 (VM rehearsal): becomes Task 6**, executed inside pipeline Stage 2 after the script is green, with its evidence (no-op diff, rebuild log) feeding the PR body per draft Phase 4. Its move-aside step is a rename, not a deletion; deleting the moved-aside dirs after a verified rebuild follows the standing deletion rule (Pratik's explicit confirmation) and is a named step, not an assumption.
- **Draft Phase 3 (container route): becomes Task 7**, conditional on D2.
- **Draft Phase 4 (land in AEP): is pipeline Stages 3–7** (independent review, hygiene, push + PR under per-action authorization, CI/thread gate, merge only on Pratik's word) — not tasks in this plan.

## File Structure

- Create: `scripts/install-re-runtime.sh` — the installer (pin block, preflight, component stages, env stage, verification stage, `--self-test`). One file, per repo convention for gate scripts.
- Create: `scripts/tests/test_install_re_runtime.sh` — fixture-HOME behavioral harness in the `test_watchdog.sh` mold (stub `curl`/`git`/`make`/`unzip` on PATH, real script, scratch HOME). Covers what `--self-test` cannot: end-to-end stage sequencing against a fake `$HOME`.
- Modify: `.github/workflows/ci.yml` — one added step in `script-tests`: `bash scripts/install-re-runtime.sh --self-test --offline`.
- Create (Task 7 only, if D2 = in v1): `Containerfile.re-runtime` at repo root — bake-into-image route; build runs the installer; consumed via one-shot `podman run`.
- Create: `docs/plans/2026-11-07-re-runtime-install.md` — this plan (first commit on the branch).

## Review Focus

- An artifact whose checksum was computed over a truncated download (network cut mid-transfer) — must fail closed at `sha256sum -c`, never extract. Pinned by Task 2's corrupt-fixture self-test.
- A second run on a healthy bench — must be a pure no-op: every probe passes, zero downloads, `.bashrc` byte-identical. Pinned by Task 6 rehearsal (a) and Task 4's duplication self-test.
- A pre-existing hand-written `~/.bashrc` (this VM's actual state: `JAVA_HOME` etc. are exported *outside* any markers by the 2026-10-20 hand install) — the script must not silently grow a second, marker-guarded copy of the same exports. Pinned by Task 4's adoption rule and Task 6 step 1's census.
- A `~/.profile` the user wrote themselves — never overwritten; created only when absent, and the script records in the block header whether it created it (rollback depends on that fact). Pinned by Task 4's clobber self-test.
- radare2 probed *without* `LD_LIBRARY_PATH` — every r2 tool fails with `libr_util.so: cannot open shared object file`, so a naive probe reports a healthy install as broken and rebuilds forever. All radare2 probes run with `LD_LIBRARY_PATH` set. Pinned by Task 3's probe test.
- `$HOME/opt/dist/` is shared staging (it also holds craft-anything artifacts as of 2026-11-07) — the script manages only its own named artifacts and never cleans the directory wholesale. Pinned by Task 2's staging test.

---

### Task 1: Script skeleton — pin block, unpinned-abort guard, preflight, self-test harness

**Files:**

- Create: `scripts/install-re-runtime.sh`
- Test: `--self-test` cases inside the script (stub-based, per `boot-gate.sh` precedent); TDD check `/tmp/re-runtime-checks/t1-skeleton-pins.sh` (RED-verified at plan time: fails, script absent)

**Interfaces:**

- Produces: the script's CLI contract used by every later task — `install-re-runtime.sh [--self-test [--offline]] [--dry-run]`, output prefix `INSTALL-RE:`, helpers `fail <check> <reason>` / `ok <name>` (the `boot-gate.sh` shape), pin variables `TEMURIN_VERSION`, `TEMURIN_TARBALL`, `TEMURIN_URL`, `TEMURIN_SHA256`, `GHIDRA_VERSION`, `GHIDRA_ZIP`, `GHIDRA_URL`, `GHIDRA_SHA256`, `R2_VERSION`, `R2_REPO`, `R2_COMMIT`, `REA_PIN="rea-agents@6.5.0"`, and stage functions `preflight`, `assert_pins` that later tasks extend.

- [ ] **Step 1: Run the task's TDD check, expect RED**

Run: `bash /tmp/re-runtime-checks/t1-skeleton-pins.sh`
Expected: FAIL — `script missing or not executable`.

- [ ] **Step 2: Write the failing self-test cases first**

In the script's `--self-test` block, stub cases asserting: (a) a pin variable emptied in a subshell makes `assert_pins` print `INSTALL-RE: pins FAIL: <name> unpinned` and exit 1; (b) `preflight` with a stub `df` reporting < 4 GiB free under `$HOME` fails closed naming the disk check. Each prints `SELF-TEST: <case> ok` on success (repo precedent).

- [ ] **Step 3: Implement the skeleton**

Header comment (purpose, contract, pin-bump + rollback pointer — full procedure lands in Task 8), the pin block with the exact values from this plan's Pin Block table, `assert_pins` (any empty pin field → `fail pins "<field> unpinned"`), `preflight` (≥ ~4 GiB free under `$HOME`; `gcc`/`make` present for the radare2 stage; free-memory report line; `node`/`npx` presence *reported* for REA, not fatal in preflight — fatal-vs-report is Task 4's call), and the `--self-test [--offline]` / `--dry-run` argument handling. No component stages yet: `main` calls `assert_pins` + `preflight` and prints `INSTALL-RE: stages TODO` — no: fail-closed means an incomplete script must not print success; `main` exits 1 with `INSTALL-RE: main FAIL: stages not yet implemented` until Task 5 completes it. (The skeleton commit is a branch state, never a releasable one.)

- [ ] **Step 4: Run self-test and the TDD check, expect GREEN**

Run: `bash scripts/install-re-runtime.sh --self-test --offline && bash /tmp/re-runtime-checks/t1-skeleton-pins.sh`
Expected: all `SELF-TEST:` lines `ok`; check prints `PASS`.

- [ ] **Step 5: Commit**

```bash
git add scripts/install-re-runtime.sh
git commit -m "feat(scripts): install-re-runtime skeleton — pin block, preflight, self-test harness"
```

### Task 2: Temurin + Ghidra stages — checksum-verified download, extract, probe-skip

**Files:**

- Modify: `scripts/install-re-runtime.sh`
- Test: `--self-test` cases in the script; TDD check `/tmp/re-runtime-checks/t2-download-stages.sh` (RED-verified at plan time)

**Interfaces:**

- Consumes: pin variables, `fail`/`ok`, `preflight` from Task 1.
- Produces: `probe_temurin`, `install_temurin`, `probe_ghidra`, `install_ghidra`, and the staging helper `fetch_and_verify <url> <sha256> <dest>` (download to `$HOME/opt/dist/`, `sha256sum -c` before any extraction; on mismatch: `fail checksum "<file> sha256 mismatch"`). Later tasks rely on the probe convention: probe exits 0 and prints nothing on success.

- [ ] **Step 1: Run the task's TDD check, expect RED**

Run: `bash /tmp/re-runtime-checks/t2-download-stages.sh`
Expected: FAIL — script absent (at plan time) / stage functions missing (at task time).

- [ ] **Step 2: Write the failing self-test cases first**

Stub `curl` on PATH serving fixture tarballs from a local dir. Cases: (a) probe-pass with stub `java -version` printing `openjdk version "25.0.4.1"` → install prints `INSTALL-RE: temurin ok (already installed)` and the stub curl's call log stays empty; (b) fixture tarball with a wrong recorded hash → run aborts at `INSTALL-RE: checksum FAIL`, nothing extracted; (c) truncated/corrupt fixture (hash computed over the real fixture, file served cut in half) → same checksum abort; (d) staging test: a pre-existing unrelated file in the fixture `$HOME/opt/dist/` survives a full run untouched.

- [ ] **Step 3: Implement the two stages**

Per component: probe first (`$HOME/opt/jdk-25.0.4.1+1/bin/java -version` output contains `25.0.4.1`; `$HOME/opt/ghidra_12.1.4_PUBLIC/support/analyzeHeadless` exists and is executable). Probe-pass → `ok` line + skip. Probe-fail → remove the target dir if present (partial installs are rebuilt, never patched — Global Constraints idempotence), `fetch_and_verify`, extract (`tar`/`unzip`) into `$HOME/opt/`, re-probe, fail naming the component if the re-probe fails.

- [ ] **Step 4: Run self-test and the TDD check, expect GREEN**

Run: `bash scripts/install-re-runtime.sh --self-test --offline && bash /tmp/re-runtime-checks/t2-download-stages.sh`
Expected: `SELF-TEST:` all `ok`; `PASS`.

- [ ] **Step 5: Commit**

```bash
git add scripts/install-re-runtime.sh
git commit -m "feat(scripts): checksum-verified Temurin and Ghidra stages with probe-skip"
```

### Task 3: radare2 stage — pinned-commit source build

**Files:**

- Modify: `scripts/install-re-runtime.sh`
- Test: `--self-test` cases in the script; TDD check `/tmp/re-runtime-checks/t3-radare2.sh` (RED-verified at plan time)

**Interfaces:**

- Consumes: pin variables `R2_*`, `fail`/`ok` from Task 1; the probe convention from Task 2.
- Produces: `probe_radare2`, `install_radare2`. Probe contract: runs `$HOME/opt/radare2/bin/r2 -v` **with `LD_LIBRARY_PATH="$HOME/opt/radare2/lib"` set** and requires output containing `6.2.6`.

- [ ] **Step 1: Run the task's TDD check, expect RED**

Run: `bash /tmp/re-runtime-checks/t3-radare2.sh`
Expected: FAIL — stage missing / patterns absent.

- [ ] **Step 2: Write the failing self-test cases first**

Stub `git`, `./configure`, `make` in a fixture source tree. Cases: (a) stub `git rev-parse HEAD` printing a commit ≠ `R2_COMMIT` after checkout → abort `INSTALL-RE: radare2 FAIL: HEAD <got> != pinned 06a7c9d…`; (b) build invocation log shows `make -j2` exactly (never bare `make`, never `-j$(nproc)`); (c) probe case: stub `r2` that exits 1 unless `LD_LIBRARY_PATH` contains the lib dir → probe passes, proving the probe sets it; (d) the script contains no `apt` radare2 path and clones `https://github.com/radareorg/radare2` (upstream), never the fork.

- [ ] **Step 3: Implement the stage**

Probe → skip as Tasks 2. Otherwise: clone upstream into `$HOME/opt/dist/radare2-src` (reuse an existing clone only after `git rev-parse HEAD` matches or a fresh checkout of tag `6.2.6` restores it), `git checkout 6.2.6`, assert `git rev-parse HEAD` = `06a7c9d35468676cc3fe6ea299885cf53aa8ad9b` (mismatch = fail closed), `./configure --prefix=$HOME/opt/radare2`, `make -j2`, `make install`, re-probe.

- [ ] **Step 4: Run self-test and the TDD check, expect GREEN**

Run: `bash scripts/install-re-runtime.sh --self-test --offline && bash /tmp/re-runtime-checks/t3-radare2.sh`
Expected: `SELF-TEST:` all `ok`; `PASS`.

- [ ] **Step 5: Commit**

```bash
git add scripts/install-re-runtime.sh
git commit -m "feat(scripts): radare2 stage — upstream clone, pinned-commit assert, -j2 build"
```

### Task 4: Environment stage — marker-guarded `.bashrc` block, `.profile`, REA assertion

**Files:**

- Modify: `scripts/install-re-runtime.sh`
- Test: `--self-test` cases in the script; TDD check `/tmp/re-runtime-checks/t4-env-block.sh` (RED-verified at plan time)

**Interfaces:**

- Consumes: `fail`/`ok` from Task 1; install dirs from the Pin Block.
- Produces: `install_env_block`, `ensure_profile`, `assert_rea`. The block contract: exactly one block between `# >>> re-runtime >>>` and `# <<< re-runtime <<<` in `~/.bashrc`, exporting `JAVA_HOME=$HOME/opt/jdk-25.0.4.1+1`, `GHIDRA_INSTALL_DIR=$HOME/opt/ghidra_12.1.4_PUBLIC`, `PATH` additions (`$JAVA_HOME/bin`, `$GHIDRA_INSTALL_DIR/support`, `$HOME/opt/radare2/bin`), and `LD_LIBRARY_PATH` including `$HOME/opt/radare2/lib`. The block header records whether the script created `~/.profile` (`# profile: created-by-install-re-runtime` or `# profile: pre-existing`).

- [ ] **Step 1: Run the task's TDD check, expect RED**

Run: `bash /tmp/re-runtime-checks/t4-env-block.sh`
Expected: FAIL — markers/exports absent.

- [ ] **Step 2: Write the failing self-test cases first**

Fixture HOME cases: (a) run `install_env_block` twice → exactly one marker pair, file byte-identical after the second run; (b) fixture `.bashrc` with a pre-existing user `.profile` present → profile content untouched, block header says `pre-existing`; (c) no `.profile` → created sourcing `~/.bashrc`, header says `created-by-install-re-runtime`; (d) torn block (start marker, no end marker — the crash-halfway case) → rewritten whole, exactly one pair; (e) **adoption case:** fixture `.bashrc` already exporting `JAVA_HOME` *outside* markers (the live VM's hand-install state) → the stage prints `INSTALL-RE: env SKIP: unmarked RE exports present — manual adoption required` and changes nothing (adoption is Task 6's supervised step, never a silent duplicate).

- [ ] **Step 3: Implement the stage**

Marker-block replace-or-append per the cases; `ensure_profile` create-only-if-absent; `assert_rea`: `node` and `npx` on PATH → `INSTALL-RE: rea ok (npx -y rea-agents@6.5.0)`; absent → `INSTALL-RE: rea FAIL: node/npx not found — REA unavailable; this script does not install Node` and exit 1 at the main-sequence position Task 5 assigns (after component stages, so a Node-less machine still gets the bench).

- [ ] **Step 4: Run self-test and the TDD check, expect GREEN**

Run: `bash scripts/install-re-runtime.sh --self-test --offline && bash /tmp/re-runtime-checks/t4-env-block.sh`
Expected: `SELF-TEST:` all `ok`; `PASS`.

- [ ] **Step 5: Commit**

```bash
git add scripts/install-re-runtime.sh
git commit -m "feat(scripts): marker-guarded env block, profile guard, REA assertion"
```

### Task 5: Verification stage, `--dry-run`, main sequence, fixture-HOME harness

**Files:**

- Modify: `scripts/install-re-runtime.sh`
- Create: `scripts/tests/test_install_re_runtime.sh`
- Test: TDD checks `/tmp/re-runtime-checks/t5-verify.sh` and `/tmp/re-runtime-checks/t6-dryrun.sh` (both RED-verified at plan time)

**Interfaces:**

- Consumes: all stage functions from Tasks 2–4.
- Produces: `verify_all` and the final `main` sequence (`assert_pins` → `preflight` → component stages → env stage → `assert_rea` → `verify_all`), replacing Task 1's not-implemented exit. `--dry-run` prints the `INSTALL-RE:` plan lines for the current probe state and writes nothing.

- [ ] **Step 1: Run the task's TDD checks, expect RED**

Run: `bash /tmp/re-runtime-checks/t5-verify.sh; bash /tmp/re-runtime-checks/t6-dryrun.sh`
Expected: both FAIL.

- [ ] **Step 2: Write the failing harness first**

`scripts/tests/test_install_re_runtime.sh` in the `test_watchdog.sh` mold (`ok`/`fail`/`check` helpers, fixture HOME under `mktemp -d`, stub bin dir): (a) `--dry-run` against an empty fixture HOME prints install-plan lines for all three components and creates no `opt/`; (b) `--dry-run` against a fixture HOME with probe-passing stubs prints `already installed` for each and still writes nothing (including no `.bashrc` change — hash before/after); (c) a full stubbed run (fixture tarballs + stub build) ends with `verify_all` invoking the stubbed `bash -lc` resolution check.

- [ ] **Step 3: Implement `verify_all` and `main`**

`verify_all` runs the hand-verified checks exactly: `java -version` prints 25.0.4.1; `analyzeHeadless` boots and prints usage; `r2 -v` / `rabin2 -v` print 6.2.6 (with `LD_LIBRARY_PATH` set); `rabin2 -I /bin/ls` identifies ELF64; `radiff2` on two identical files is clean; a fresh `bash -lc` resolves `java`, `analyzeHeadless`, and `r2` from PATH. Any failure: `INSTALL-RE: verify FAIL: <check>` + exit 1.

- [ ] **Step 4: Run everything, expect GREEN**

Run: `bash scripts/install-re-runtime.sh --self-test --offline && bash scripts/tests/test_install_re_runtime.sh && bash /tmp/re-runtime-checks/t5-verify.sh && bash /tmp/re-runtime-checks/t6-dryrun.sh`
Expected: all `ok` / `PASS`.

- [ ] **Step 5: Commit**

```bash
git add scripts/install-re-runtime.sh scripts/tests/test_install_re_runtime.sh
git commit -m "feat(scripts): verification stage, dry-run, fixture-HOME harness"
```

### Task 6: VM rehearsal on this machine (draft Phase 2) — no-op proof, then rebuild

**Files:**

- Create (evidence, not committed): rehearsal logs under the goal's `hidden_files/` (`~/workspace/goals/autonomous-code-defense-factory/hidden_files/re-runtime-rehearsal/`)
- Modify (only if a rehearsal gap sends the script back): `scripts/install-re-runtime.sh`

**Interfaces:**

- Consumes: the finished script from Task 5.
- Produces: rehearsal evidence for the PR body: (a) no-op diff log, (b) rebuild run log with `verify_all` green. This task is execution evidence, not new code — a gap found here returns to the owning task (2–5) as a fix commit, per the draft's stop rule.

- [ ] **Step 1: Census the live bench and `.bashrc`**

Record `java -version`, `r2 -v`, `analyzeHeadless` presence, and a hash of `~/.bashrc`; list the existing *unmarked* RE exports (expected: the 2026-10-20 hand exports). This census is the baseline rehearsal (a) diffs against.

- [ ] **Step 2: Adoption step (supervised, one-time)**

Move the hand-written RE exports in `~/.bashrc` into the marker-guarded block by hand (same export lines, verbatim), hash before/after, and confirm a fresh `bash -lc` still resolves all three tools. This is a local environment edit on this VM only — it is not part of the script and never runs unattended.

- [ ] **Step 3: Rehearsal (a) — pure no-op**

Run: `bash scripts/install-re-runtime.sh`
Expected: every component `already installed`; `~/.bashrc` hash unchanged from Step 2's after-hash; exit 0. Any diff = stop, diagnose, fix in the owning task.

- [ ] **Step 4: Rehearsal (b) — rebuild from the network**

Rename (never delete) the three dirs: `mv ~/opt/jdk-25.0.4.1+1 ~/opt/.rehearsal-aside-jdk` and likewise for Ghidra and radare2. Run the script in isolation (no test suites or lanes concurrently — memory ceiling). Expected: full install from pins, `verify_all` green including the fresh `bash -lc` check, no manual step anywhere. Any hand intervention = stop: restore from the aside dirs, record the gap, return to the owning task (draft Phase 2 stop rule).

- [ ] **Step 5: Close out the aside dirs**

Only after Step 4 verifies: the aside dirs are deleted **only on Pratik's explicit confirmation naming them** (standing deletion rule). Until then they stay. Save both run logs as the task's evidence.

### Task 7: Container route (draft Phase 3) — only if D2 rules it in v1

**Files:**

- Create: `Containerfile.re-runtime`
- Test: TDD check `/tmp/re-runtime-checks/t7-container.sh` (RED-verified at plan time: Containerfile absent); assertions inside the build recipe below

**Interfaces:**

- Consumes: `scripts/install-re-runtime.sh` unchanged — one pin block, two targets.
- Produces: an image whose build runs the installer and whose one-shot smoke run executes the same verification commands (`java -version`, `analyzeHeadless` usage, `rabin2 -I /bin/ls`) inside the image.

- [ ] **Step 1: Run the task's TDD check, expect RED**

Run: `bash /tmp/re-runtime-checks/t7-container.sh`
Expected: FAIL — Containerfile absent.

- [ ] **Step 2: Write the Containerfile with the ESF lessons as assertions**

Bake-into-image only (this sandbox: no `podman exec`, no netns creation — host networking). Ordering constraints, checked by grep-order assertions in the check script's GREEN form: the egress CA installation step precedes every download step; the apt list explicitly includes `xz-utils`, `gcc`, `make`, `git`, `curl`, `unzip`. The build then copies and runs `install-re-runtime.sh` with a build-time HOME.

- [ ] **Step 3: Build and smoke**

Run: `podman build -f Containerfile.re-runtime -t re-runtime:6.2.6 .` from a cold cache, then a one-shot `podman run --rm re-runtime:6.2.6` executing the verification commands.
Expected: build clean; in-image versions match the pin block exactly; smoke checks pass.
Stop: if the sandbox's podman limits block even bake-and-one-shot, stop and record it as an environmental block (draft Phase 3 stop rule) — do not redesign around the sandbox without Pratik's word; Tasks 1–6 stand alone.

- [ ] **Step 4: Commit**

```bash
git add Containerfile.re-runtime
git commit -m "feat(scripts): Containerfile.re-runtime — bake-into-image RE bench"
```

### Task 8: CI wiring, operator documentation, branch-level verification

**Files:**

- Modify: `.github/workflows/ci.yml` (one step in `script-tests`)
- Modify: `scripts/install-re-runtime.sh` (header: operator note completed)
- Test: TDD check `/tmp/re-runtime-checks/t8-ci-docs.sh` (RED-verified at plan time)

**Interfaces:**

- Consumes: the finished script (Tasks 1–5), rehearsal evidence (Task 6), Containerfile if present (Task 7).
- Produces: the branch in its Stage 3 (independent review) input state. Nothing here changes script behavior.

- [ ] **Step 1: Run the task's TDD check, expect RED**

Run: `bash /tmp/re-runtime-checks/t8-ci-docs.sh`
Expected: FAIL — CI step missing.

- [ ] **Step 2: Wire CI**

Add to the `script-tests` job, beside the existing self-test steps: `- run: bash scripts/install-re-runtime.sh --self-test --offline`. Do not add the fixture-HOME harness to CI in v1 (it is a local rehearsal tool; the offline self-test is the CI surface, same split as `boot-gate.sh`).

- [ ] **Step 3: Complete the script header operator note**

How to run; how to bump a pin (pin-only PR; dual-source checksum evidence — upstream-published *and* locally computed; radare2 tag→commit resolution; post-merge run on this VM as acceptance); how to roll back (delete `~/opt/jdk-25.0.4.1+1`, `~/opt/ghidra_12.1.4_PUBLIC`, `~/opt/radare2`, the script's staged artifacts in `~/opt/dist/`; remove the marker block; remove `~/.profile` only if the block header records the script created it). State in the header: there is no pin-bypass flag, by design.

- [ ] **Step 4: Branch-level verification (all must pass)**

Run: `shellcheck scripts/*.sh`, `shfmt -d -i 2 scripts/*.sh` (no diff), `bash scripts/install-re-runtime.sh --self-test --offline`, `bash scripts/tests/test_install_re_runtime.sh`, `python3 -m unittest discover -s scripts/tests` (non-regression), and all eight `/tmp/re-runtime-checks/t*.sh`.
Expected: every command green. (If shellcheck/shfmt are absent locally, note it and rely on the CI `shell-lint` job at Stage 6 — do not claim the check ran.)

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml scripts/install-re-runtime.sh
git commit -m "ci(scripts): wire install-re-runtime self-test; complete operator header"
```

## Verification (how the finished work is proven, end to end)

1. **Fresh-prefix install:** run the script with a scratch HOME (fixture stubs for the fast path in Task 5's harness; a real-network run is Task 6b's shape against an emptied bench). The scratch run must end with all `INSTALL-RE: <name> ok` lines and `verify_all` green.
2. **Version checks:** `java -version` → 25.0.4.1; `analyzeHeadless` usage print; `r2 -v`, `rabin2 -v` → 6.2.6; `rabin2 -I /bin/ls` → ELF64; `radiff2` clean; fresh `bash -lc` resolves all three tools from PATH.
3. **Checksum negative test:** the Task 2 self-test fixtures (wrong recorded hash; truncated download) abort with `INSTALL-RE: checksum FAIL` and extract nothing — plus the unpinned-pin negative test from Task 1. These run offline in CI on every PR via Task 8's wiring.
4. **Idempotence proof:** Task 6 rehearsal (a) — second run on the live bench is a diff-verified no-op; Task 4's self-tests cover block duplication, torn block, profile clobber, and the unmarked-exports adoption case.
5. **CI gates on the PR:** `shell-lint`, `script-tests`, `docs-lint` green (pipeline Stage 6, with the Codex final-head gate as written there).

## Self-Review (writing-plans checklist, run at plan time)

- Spec coverage: draft Scope IN items map to Tasks 1–5 (script + check scripts + header operator note), 6 (rehearsal = draft Phase 2), 7 (container = draft Phase 3, D2-conditional), 8 (CI/docs finish). Draft Phase 0 and Phase 4 are pipeline-level, handled in "How the Draft's Phases Map" above — not silently dropped. Version-bump procedure and rollback (draft standing sections) land in Task 8 Step 3's header note. REA assertion: Task 4. `~/.profile` fix: Task 4.
- RED verification: all eight TDD check scripts in `/tmp/re-runtime-checks/` were run against the unmodified tree at base `49722a3` on 2026-11-07 and all fail (exit 1) — for Tasks 1–6 and 8 because the script is absent (greenfield: the check asserts the script exists and behaves, so absence is the honest RED state), for Task 7 because the Containerfile is absent. None is committed.
- Type/name consistency: stage and probe names (`probe_temurin`, `install_ghidra`, `fetch_and_verify`, `verify_all`, …) are defined in the Interfaces block of the task that creates them and used unchanged later. Output prefix is `INSTALL-RE:` everywhere; the draft's example line matches.
- Draft-vs-repo conflicts found at plan time (flagged, not silently resolved): (1) the draft never mentions editing `ci.yml`, but the repo's `script-tests` job invokes shell self-tests by name — without Task 8's step the self-test would never run in CI; (2) the draft's rehearsal (a) "byte-identical `.bashrc`" claim cannot hold against the live VM's *unmarked* hand exports — Task 4's SKIP rule + Task 6's supervised adoption step close that gap; (3) the draft HTML renders the two SHA-256 pins truncated — the full values above were recovered from the staged artifacts and match the draft's prefixes; (4) `docs/plans/` currently holds the craft-anything plan as `.html`, but the tasking for this run specifies Markdown under the repo's docs-lint convention, which this plan follows.
