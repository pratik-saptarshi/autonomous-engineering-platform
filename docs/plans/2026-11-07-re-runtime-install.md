# RE Runtime Install Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Codify the hand-built reverse-engineering bench (Temurin JDK 25, Ghidra 12.1.4, radare2 6.2.6, REA asserted via pinned `npx`) as one pinned, checksummed, idempotent installer — `scripts/install-re-runtime.sh` — that installs those exact toolchain versions plus their shell-environment block under `$HOME` only, on any machine meeting the declared prerequisites (POSIX userland tools in preflight; Node/npx for REA, which the script asserts but does not install). What this insures against, stated plainly: loss of the home volume, or provisioning a new machine where only this repo survives. A VM replacement is *not* that disaster — `$HOME` survives replacement, and TOOLS.md plus the retained artifacts in `~/opt/dist/` already cover a hand rebuild; the script's value is making the rebuild mechanical and verified rather than prose-driven. Task 6 provides same-VM rebuild evidence; no task in this plan proves a from-scratch fresh-VM provisioning, and the PR body must not claim one.

**Architecture:** A single fail-closed bash script in the `boot-gate.sh` mold: a header pin block, a preflight stage, one idempotent install stage per component (probe → skip, or download → checksum → extract/build → re-probe), a marker-guarded shell-environment stage, and a verification stage. Stub-based `--self-test --offline` cases (the `boot-gate.sh` precedent — `lane-coord.sh` has a `--self-test` but no `--offline` mode) plus one fixture-HOME shell harness give the test surface; CI's existing `shell-lint` (shellcheck + `shfmt -i 2` over `scripts/*.sh` — a glob that does *not* reach `scripts/tests/`) and `script-tests` jobs cover it once the self-test *and* the harness are wired into `ci.yml` by name (Task 7).

**Tech Stack:** Bash (`#!/usr/bin/env bash`, `set -euo pipefail`), `sha256sum`, `curl`, `git`, `gcc`/`make` (radare2 build), shellcheck/shfmt (CI). (Podman belonged to the container route, deferred out of v1 — see D2.)

**Spec:** `~/workspace/goals/autonomous-code-defense-factory/hidden_files/plans/2026-11-07-re-runtime-install-plan.html` (draft v1, 2026-11-07; local draft — it does not travel with the PR, so every value an executor needs is copied into this plan). Grounding: `~/TOOLS.md` sections "Go toolchain", "Podman", "Temurin JDK + Ghidra", "pytest", "radare2"; repo survey of `scripts/`, `scripts/tests/`, `.github/workflows/ci.yml` at base (below).

**Base:** `origin/main` @ `49722a3618569ae50804fb43258a0561a9c9fee0` (verified ancestor of this branch, Stage 0).

## Global Constraints

- All GitHub calls go through the gateway: `GHG_ACTOR=<task-slug> ~/go/bin/ghg run -- <gh args>`; pre-flight every publish step with `ghg check` (exit 75 = budget denial: stop, report the stage reached, never bypass). Push and PR-opening each need Pratik's explicit per-action authorization; merging needs his separate per-PR authorization (feature-pr-pipeline Authorization rule).
- **Pins refuse unpinned artifacts (fail closed).** Every fetched or built artifact is declared in the pin block with a full SHA-256 (or, for radare2, tag + full commit). An empty or missing pin field aborts the run; a checksum mismatch aborts before extraction. There is no bypass flag.
- **Install targets only under `$HOME`.** Nothing is written to `/etc`, `/usr/local`, or any root-owned path; nothing requires root. (Those tiers do not survive VM replacement; `$HOME` does.)
- **Staging never uses `/tmp`** (512M tmpfs; the Ghidra zip alone is 543 MiB). All downloads stage under `$HOME/opt/dist/`. Scratch/test dirs are the only `/tmp` use.
- **Memory ceiling:** ~1.6 GiB effective of 7.7 GiB reported (virtio balloon). Build parallelism is hard-capped at `make -j2`; heavy steps (radare2 build, rehearsals) run in isolation, never alongside test suites.
- **Idempotence (pipeline Stage 1 prompt), installer-wide:** running the finished script twice in a row leaves the system byte-identical to one clean run — components probe-pass and skip, the `.bashrc` block is replaced in place between its markers, `~/.profile` is created only if absent. If a run crashes halfway, the next run converges to the same end state, by three mechanisms an executor must not weaken: (1) **probes verify completeness, not presence** — each probe checks the files a partial install most plausibly lacks (Task 2/3 probe contracts), so a half-extracted or half-built tree fails its probe, is removed, and is rebuilt (never patched in place); (2) **verification failure is a recovery trigger, not a dead end** — if `verify_all` fails for a component whose stage skipped, `main` removes that component's directory, re-runs its install stage once, and re-verifies before exiting 1 (Task 5); (3) **downloads are crash-clean** — transfers land in `<dest>.part` and are renamed to `<dest>` only after `sha256sum -c` passes; a mismatch deletes the partial and fails the run, so the next run re-fetches rather than re-verifying a stale partial forever. The env block is written by temp-file-in-the-same-directory + atomic rename (Task 4), so a crash leaves either the old or the new `.bashrc`, never a torn one. The one accepted difference: verified staging artifacts in `$HOME/opt/dist/` may remain from the crashed run and are reused only after checksum verification. A single-instance lock (Task 1 preflight) prevents two concurrent runs from interleaving these mechanisms.
- Script conventions (repo-grounded): header comment block stating purpose and contract; first failure prints `INSTALL-RE: <check> FAIL: <reason>` and exits 1 — never warn-and-continue; passing checks print `INSTALL-RE: <name> ok`; a `--self-test --offline` mode with fully self-contained stubs that passes on a stock CI runner (exactly the `boot-gate.sh --self-test --offline` contract).
- CI compatibility: the script must pass `shellcheck scripts/*.sh` and `shfmt -d -i 2 scripts/*.sh`, and both its self-test and its fixture-HOME harness must be added as explicit steps in the `script-tests` job of `.github/workflows/ci.yml` (that job invokes `lane-coord.sh`/`boot-gate.sh` self-tests and `test_watchdog.sh` by name; nothing is auto-discovered for shell scripts). New Python is out of scope; `python3 -m unittest discover -s scripts/tests` must stay green.
- The plan document ships in the PR under `docs/plans/` (Pratik's standing rule, 2026-11-07). Repo files use Markdown; this plan must pass the `docs-lint` job (markdownlint with `.markdownlint.yaml`).
- Out of scope (draft Scope, carried verbatim): installing or vendoring Node, REA itself, Hopper, or IDA; any change to the `reverse_engineering` skill's routing or the 2026-10-21 Ghidra invocation gate; fork-sourcing or apt-sourcing radare2; `@latest` anything.
- Recorded-but-not-encoded quirks (draft is silent; flagged, not invented): `GOTMPDIR=$HOME/.gotmp` matters for Go builds — this script builds no Go, so it neither sets nor checks it. The pytest user-site install and the podman `/etc/containers/` config are non-RE environment pieces; they belong to decision D3 and are not touched by v1 under the recommended default.

## Pin Block (carried verbatim from the draft; provenance dual-sourced at the Phase 0 wringer, 2026-11-07)

Pin provenance, recorded so the inaugural pins meet the same dual-source standard Task 7 imposes on future bumps: each hash below was (a) computed locally by `sha256sum` over the staged artifact in `~/opt/dist/`, and (b) matched against the upstream-published value fetched independently — Temurin's `OpenJDK25U-jdk_x64_linux_hotspot_25.0.4.1_1.tar.gz.sha256.txt` release asset, and the SHA-256 printed in the Ghidra `Ghidra_12.1.4_build` release notes. Honest scope of the mechanism: a checksum checked against a pin committed through a reviewed PR is an *integrity* control against a tampered or truncated download, not an *authenticity* proof — Ghidra publishes no signature, and Temurin's published `.sig` is deliberately not verified at runtime (in-script key management adds failure modes disproportionate to the gain; the reviewed pin is the control — the same sha256-only shape as the `ci.yml` security job's gitleaks install).

| Component | Version / identity | Source | SHA-256 / commit | Installs to |
|---|---|---|---|---|
| Temurin JDK (LTS) | 25.0.4.1+1 | `https://github.com/adoptium/temurin25-binaries/releases/download/jdk-25.0.4.1+1/OpenJDK25U-jdk_x64_linux_hotspot_25.0.4.1_1.tar.gz` | `dbb698396d478e7fa2b1e50f4103324b2a99b90569ee27c33f2261f9215cf41e` | `~/opt/jdk-25.0.4.1+1` (`JAVA_HOME`) |
| Ghidra | 12.1.4 PUBLIC (2026-09-21) | `https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.4_build/ghidra_12.1.4_PUBLIC_20260921.zip` (543 MB) | `ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db` | `~/opt/ghidra_12.1.4_PUBLIC` (`GHIDRA_INSTALL_DIR`); `support/` on PATH |
| radare2 | 6.2.6, built from source | `git clone https://github.com/radareorg/radare2` at tag `6.2.6`. Never from Pratik's fork — it carries no tags. Never from apt (stale 5.5.0). | tag = commit `06a7c9d35468676cc3fe6ea299885cf53aa8ad9b`; script asserts HEAD equals this commit after checkout | `~/opt/radare2` via `./configure --prefix=$HOME/opt/radare2 && make -j2 && make install` (~5 min) |
| REA | `rea-agents@6.5.0` | No install. Invoked as `npx -y rea-agents@6.5.0` (pinned; never `@latest`). | — | The script only asserts `node`/`npx` presence and reports absence (SKIP, never a run failure — Task 4); it does not install Node, and Node itself is unversioned, image-provided state outside the script's control. |

## Decisions (ruled by Pratik at the plan gate, 2026-11-07 — the defaults below were adopted; all tasks are written against them)

- **D1 — Script home: `scripts/install-re-runtime.sh`.** Rationale: CI already shellchecks, shfmt-checks, and self-test-wires everything in `scripts/`; a new `runtime/` directory buys a label and costs new CI wiring plus a second convention.
- **D2 — Container route: DEFERRED out of v1 (re-ruled by Pratik, 2026-11-07).** As first ruled, the container route was in v1 as a separate, independently stoppable final task. The Phase 0 wringer panel's majority preferred deferral (see Wringer Record item 10); on re-ruling, Pratik adopted that position. Grounds: podman is absent — not merely unconfigured — on the target VM, and restoring it (apt install + `/etc/containers/` rewrites) violates this plan's own Global Constraints (`$HOME`-only, no root). Effect: the former Task 7 (container route) is deleted, the former Task 8 renumbers to Task 7, and the deleted task's design text is preserved in this document's git history at the wringer commits (`b3d98b1`, `69aa6f0`). The container route may return as a follow-up once podman legitimately exists on the target machine.
- **D3 — Scope: RE-only for v1.** Rationale: the stage structure is component-list-driven, so generalizing later (Go, `bd`, pytest, podman config) is an additive PR, not a rewrite; chartering generalization now delays the RE codification behind every other tool on the VM.

## How the Draft's Phases Map onto the Pipeline

- **Draft Phase 0 (planning-wringer): RAN 2026-11-07**, after Pratik approved the plan + defaults and directed the wringer run (no waiver). Panel verdicts: Feasibility FEASIBLE-WITH-CHANGES, Risk Assessor P1s led by the probe/verify recovery deadlock, Devil's Advocate SPARE-WITH-CHANGES (kill reserved for Task 7-as-written or the unbounded Goal claim — both amended/flagged). Amendments were folded into this document before implementation; see the Wringer Record immediately below. Stage 2 implements from this amended text.
- **Draft Phase 2 (VM rehearsal): becomes Task 6**, executed inside pipeline Stage 2 after the script is green, with its evidence (no-op diff, rebuild log) feeding the PR body per draft Phase 4. Its move-aside step is a rename, not a deletion; deleting the moved-aside dirs after a verified rebuild follows the standing deletion rule in full (Pratik's explicit confirmation naming the dirs, a 1-hour enforced delay, and his reconfirmation) and is a named step, not an assumption.
- **Draft Phase 3 (container route): DEFERRED out of v1** per the D2 re-ruling (2026-11-07) — see Decisions (D2) and the Deferred note before Task 7; its design text is preserved in git history at the wringer commits.
- **Draft Phase 4 (land in AEP): is pipeline Stages 3–7** (independent review, hygiene, push + PR under per-action authorization, CI/thread gate, merge only on Pratik's word) — not tasks in this plan.

## Wringer Record (Phase 0, 2026-11-07 — amendments applied to this document)

Panel: Feasibility Analyst, Risk Assessor, Devil's Advocate — each verified claims with tools against the worktree, the live VM, and the GitHub API. Consensus verdict: **adopt-with-changes**. What the panel proved, and what changed here:

1. **Convergence was false as specified** (Risk P1-1, the panel's top finding): the original probes checked presence, and concrete probe-passing-but-broken partial installs exist for all three components (Ghidra extracted to 99% but missing `support/launch.sh`; radare2 `make install` interrupted after `binr` — `r2 -v` passes with data files and `r2sdb` absent, experimentally confirmed; a JDK tar interrupted after `lib/modules` but before `cacerts`). `verify_all` failure had no recovery path — a deterministic fail loop. Fixed in Global Constraints + Tasks 2/3/5: completeness probes, per-component partial-install healing self-tests, and verify-failure as a rebuild trigger.
2. **The `.bashrc` write had no mechanism** (Risk P1-2): "replace-or-append" named no atomicity, and tear-detection covered only tears inside the block. Fixed in Task 4: temp-file-in-same-directory + atomic rename, one-time backup, tear-before-the-marker self-test.
3. **`fetch_and_verify` contradicted the idempotence paragraph** (Risk P1-3): fail-on-mismatch vs re-fetch, destination filenames unstated, no `.part` discipline — a stale partial could fail every future run. Fixed in Task 2: full contract (asset-name destinations, `.part` + rename-on-pass, mismatch deletes and fails, verified-file reuse rule, `curl --fail`). Full URLs are now stated in the Pin Block (Feasibility verified both resolve).
4. **REA's fatal-at-end shape was the worst of both** (Risk P1-4, Devil's Advocate trace): a Node-less machine installed everything, never verified, and could never exit 0. Fixed in Task 4 per the `boot-gate.sh` precedent: absence prints `INSTALL-RE: rea SKIP: …` and the run proceeds to `verify_all`.
5. **`verify_all` would have failed a healthy bench** (Feasibility P1): `analyzeHeadless` in a non-login shell finds no Java — the env stage writes `.bashrc` but cannot mutate the running process. Fixed in Task 5: `verify_all` exports `JAVA_HOME`/PATH itself and caps the headless heap (`MAXMEM=1G`) against the balloon (Risk P2-8). Task 1 preflight also gained the full tool list (`curl git gcc make unzip sha256sum tar pkg-config`, plus `flock`/`df` per Phase 4 — radare2's `configure` hard-requires `pkg-config`, which the original preflight and Task 7's apt list both missed), a memory floor, staging-writability, and the single-instance lock (Risk P2-6).
6. **Task 5's harness case (c) was vacuous** (Feasibility P1): a stubbed `bash` intercepts the harness's own launch in the `test_watchdog.sh` mold, and a stubbed `bash -lc` proves only that the words were invoked. Rewritten: absolute-path launch, real `/bin/bash -lc` against the fixture HOME.
7. **Task 8's CI rationale contradicted its own precedent** (Feasibility P2): `test_watchdog.sh` *is* wired into `script-tests` by name (`ci.yml:42`), so the fixture-HOME harness is now wired the same way; the `shell-lint` glob's blindness to `scripts/tests/` is named, with the harness linted explicitly in Task 8's local verification.
8. **Goal overclaim + wrong-disaster framing** (Devil's Advocate P1-3/P1-4): "identical bench on a fresh VM" is now the bounded claim in the Goal, with the insured disaster stated and Task 6 honestly labeled same-VM rebuild evidence. Task 6 also gained: downloads before renames (minimal outage window), a spelled-out restore procedure that handles already-recreated partial dirs, and the standing deletion rule stated in full (explicit confirmation + 1-hour delay + reconfirmation) where the aside dirs' deletion is named (Risk P2-5).
9. **Pin provenance recorded** (Risk P2-7, Devil's Advocate P2-1): dual-source evidence for the inaugural pins is in the Pin Block, with the integrity-not-authenticity scope stated and Temurin's `.sig` declined on the record. Adjudicated down: the Risk Assessor's mechanical CI check of bump evidence was judged disproportionate for v1 — Task 8 instead names the Stage 3 reviewer as the human gate who verifies a bump PR's dual-source quotes.
10. **Task 7 reshaped, D2 flagged**: as written it could never go green — podman is absent (not merely unconfigured) and restoring it violates this plan's own constraints; the image build would also have died at the formerly-fatal `assert_rea` (no Node in its apt list, Node out of scope) and no base image was specified. Task 7 now opens with a Step 0 podman preflight that stops-and-records (on today's VM it stops there), and its build design is completable when podman legitimately exists (digest-pinned base image, `pkg-config` in the apt list, `bash -lc` smoke). **Flagged for Pratik's re-ruling, not applied:** the panel's majority preference to defer the container route out of v1 entirely (a D2 change). The wringer kept D2 as ruled and made its stop honest and early; if Pratik prefers deferral, Task 7 is deleted and Task 8 renumbers — nothing else moves.

Executor note: the `/tmp/re-runtime-checks/t*.sh` TDD scripts were RED-verified against the *pre-wringer* task text; the Stage 2 executor regenerates t1 (preflight list), t4 (REA token, write mechanism), and t5 (harness case (c)) against this amended text before starting their tasks.

**Phase 4 addendum (independent review of the amended plan, 2026-11-07): APPROVED-WITH-CHANGES** — the reviewer re-verified every pin, URL, CI claim, and probe path independently (all correct; markdownlint on this document: 0 issues) and required 4 FATAL + 9 MINOR fixes, all folded in above: the memory floor is now an exact 384 MiB (the reviewer's live measurement of 407–455 MiB typical proved the wringer's 768 MiB floor would fail the script on its own target VM; Tasks 5/6 gained the daemon-shutdown memory discipline and preflight gained its missing memory/staging self-tests); Task 8 Step 4 states the `t7` N/A rule for a Step-0-stopped Task 7; Task 7's base image (`ubuntu:24.04`, digest-pinned procedurally), Step 0 smoke command, and `--no-cache` are named rather than left to invention; `verify_all`'s Ghidra check is explicitly output-based (`analyzeHeadless` exits 1 while printing usage); preflight enumerates `flock`/`df` and `--dry-run`/`--self-test` short-circuit before any creation or lock (the lock moved to `$HOME/.install-re-runtime.lock`); the env-stage verify failure has a rebuild-cycle mapping; Task 6's scratch dir, artifact asides, and log filenames are named; Verification §1 enumerates the expected stage lines and the REA pass condition. No Phase 4 item touched D1/D3 or the plan's scope; D2's shape is unchanged (Step 0 stop + completable build), with the deferral preference still flagged below for Pratik.

**Post-wringer re-ruling (Pratik, 2026-11-07):** the deferral preference flagged in item 10 was adopted — the container route is deferred out of v1 (a D2 change; see Decisions), the former Task 7 is deleted, and the former Task 8 renumbers to Task 7. Task-number references inside this Record (and in the phase map's Phase 0 summary) are as they stood at wringer time.

## File Structure

- Create: `scripts/install-re-runtime.sh` — the installer (pin block, preflight, component stages, env stage, verification stage, `--self-test`). One file, per repo convention for gate scripts.
- Create: `scripts/tests/test_install_re_runtime.sh` — fixture-HOME behavioral harness in the `test_watchdog.sh` mold (stub `curl`/`git`/`make`/`unzip` on PATH, real script, scratch HOME). Covers what `--self-test` cannot: end-to-end stage sequencing against a fake `$HOME`.
- Modify: `.github/workflows/ci.yml` — two added steps in `script-tests`: `bash scripts/install-re-runtime.sh --self-test --offline` and `bash scripts/tests/test_install_re_runtime.sh`.
- Deferred (not created in v1): `Containerfile.re-runtime` — the container route, per the D2 re-ruling; design preserved in git history (see the Deferred note before Task 7).
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

In the script's `--self-test` block, stub cases asserting: (a) a pin variable emptied in a subshell makes `assert_pins` print `INSTALL-RE: pins FAIL: <name> unpinned` and exit 1; (b) `preflight` with a stub `df` reporting < 4 GiB free under `$HOME` fails closed naming the disk check; (c) `preflight` with one required tool removed from the stub PATH (case per tool group) fails closed naming the missing tool; (d) a second invocation while a first holds the lock fails closed naming the lock; (e) `preflight` with a stubbed `MemAvailable` below the floor (the meminfo source is overridable for the self-test — executor's seam) fails closed naming the memory check; (f) `preflight` against a fixture `$HOME` whose staging path is unwritable fails closed naming staging. Each prints `SELF-TEST: <case> ok` on success (repo precedent).

- [ ] **Step 3: Implement the skeleton**

Header comment (purpose, contract, pin-bump + rollback pointer — full procedure lands in Task 7), the pin block with the exact values from this plan's Pin Block table (URLs written out in full; `TEMURIN_TARBALL="OpenJDK25U-jdk_x64_linux_hotspot_25.0.4.1_1.tar.gz"`, `GHIDRA_ZIP="ghidra_12.1.4_PUBLIC_20260921.zip"` — the upstream asset names are the staging destination names), `assert_pins` (any empty pin field → `fail pins "<field> unpinned"`), `preflight`, and the `--self-test [--offline]` / `--dry-run` argument handling. `preflight` fails closed, each check named, on: free space under `$HOME` **< 4 GiB** (exact threshold, matching self-test (b)); every tool the stages *and the script itself* require — `curl git gcc make unzip sha256sum tar pkg-config flock df` (`pkg-config` is a hard requirement of radare2's `configure`; `flock`/`df` serve the lock and the disk check — the original draft of this plan missed tools of both kinds, which is why preflight enumerates instead of assuming); `MemAvailable` **< 384 MiB** → `fail preflight "memory below 384 MiB floor"` (floor set by Phase 4 evidence: this VM's *typical* available memory is 0.4–0.6 GiB and the reviewer measured 407–455 MiB live, so a higher floor makes the script fail on its own target machine — the floor exists to avoid starting a run the OOM killer decapitates mid-extraction, and Tasks 5/6 carry the rest of the memory discipline); `$HOME/opt` and `$HOME/opt/dist` existing-or-creatable *and writable* — a creatability test only: **preflight creates nothing**, and `--dry-run`/`--self-test` short-circuit before even the lock; and, on real runs only, acquisition of a single-instance lock (`flock` on `$HOME/.install-re-runtime.lock` — under `$HOME`, not in `dist/`, so locking never forces a directory creation; a held lock → `fail preflight "another install-re-runtime run holds the lock"`). `node`/`npx` presence is *reported* in preflight for operator visibility and is never fatal anywhere (Task 4's SKIP rule). No component stages yet: `main` calls `assert_pins` + `preflight` and prints `INSTALL-RE: stages TODO` — no: fail-closed means an incomplete script must not print success; `main` exits 1 with `INSTALL-RE: main FAIL: stages not yet implemented` until Task 5 completes it. (The skeleton commit is a branch state, never a releasable one.)

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
- Produces: `probe_temurin`, `install_temurin`, `probe_ghidra`, `install_ghidra`, and the staging helper `fetch_and_verify <url> <sha256> <dest-name>`, whose contract is exact: if `$HOME/opt/dist/<dest-name>` exists, verify it — pass → reuse it (no download); fail → delete it and download fresh. Download with `curl --fail` to `$HOME/opt/dist/<dest-name>.part`; `sha256sum -c` the `.part`; on mismatch delete the `.part` and `fail checksum "<file> sha256 mismatch"` (the run fails, and the *next* run re-fetches — no state survives that can fail twice); on pass, rename `.part` → `<dest-name>` and return its path. Extraction always consumes the path `fetch_and_verify` returned in this run, under the Task 1 lock. Later tasks rely on the probe convention: probe exits 0 and prints nothing on success — and probes check *completeness* (Step 3), not presence.

- [ ] **Step 1: Run the task's TDD check, expect RED**

Run: `bash /tmp/re-runtime-checks/t2-download-stages.sh`
Expected: FAIL — script absent (at plan time) / stage functions missing (at task time).

- [ ] **Step 2: Write the failing self-test cases first**

Stub `curl` on PATH serving fixture tarballs from a local dir. Cases: (a) probe-pass (complete fixture install tree) → install prints `INSTALL-RE: temurin ok (already installed)` and the stub curl's call log stays empty; (b) fixture tarball with a wrong recorded hash → run aborts at `INSTALL-RE: checksum FAIL`, nothing extracted, and no `.part` or dest file remains (the next run can succeed); (c) truncated/corrupt fixture (hash computed over the real fixture, file served cut in half) → same checksum abort and clean staging; (d) staging test: a pre-existing unrelated file in the fixture `$HOME/opt/dist/` survives a full run untouched; (e) **partial-install healing, per component:** a fixture Temurin tree whose `java -version` prints the right version but with `lib/security/cacerts` removed → probe must FAIL and the stage must rebuild, not skip; a fixture Ghidra tree with `support/analyzeHeadless` present but `support/launch.sh` removed → probe must FAIL and the stage must rebuild. (These are the panel-proven deadlock states; a self-test that cannot distinguish them from healthy installs is the defect this task exists to prevent.)

- [ ] **Step 3: Implement the two stages**

Per component: probe first. Temurin probe: `$HOME/opt/jdk-25.0.4.1+1/bin/java -version` output contains `25.0.4.1`, **and** `bin/javac` is executable, **and** `lib/security/cacerts` exists (a bare `java -version` passes on a tar interrupted before the trust store — proven at the wringer). Ghidra probe: `$HOME/opt/ghidra_12.1.4_PUBLIC/support/analyzeHeadless` exists and is executable, **and** `support/launch.sh` exists (it sits ~24 zip entries after `analyzeHeadless`; an extraction killed in that window otherwise leaves a probe-passing Ghidra that cannot boot). Probe-pass → `ok` line + skip. Probe-fail → remove the target dir if present (partial installs are rebuilt, never patched — Global Constraints idempotence), `fetch_and_verify` (dest names are the upstream asset names from the Pin Block — note for Task 6: the artifacts staged on this VM today are named `temurin25.tar.gz`/`ghidra.zip` and are therefore *not* reused), extract (`tar`/`unzip`) into `$HOME/opt/`, re-probe, fail naming the component if the re-probe fails.

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
- Produces: `probe_radare2`, `install_radare2`. Probe contract: runs `$HOME/opt/radare2/bin/r2 -v` **with `LD_LIBRARY_PATH="$HOME/opt/radare2/lib"` set** and requires output containing `6.2.6`, **and** requires `bin/r2sdb` executable **and** the versioned data tree present (`share/radare2/6.2.6/` with its `fcnsign` and `syscall` data). Rationale (wringer-proven): upstream's `install` target lays down `libr` → `binr` → `shlr` → data dirs, with `r2sdb` last — a build killed after `binr` leaves an `r2 -v`-passing tree with no data files, and the original `verify_all` surface (version + `rabin2 -I` + `radiff2`) passes on it too, experimentally confirmed against a bin+lib-only tree. Version alone is not a probe.

- [ ] **Step 1: Run the task's TDD check, expect RED**

Run: `bash /tmp/re-runtime-checks/t3-radare2.sh`
Expected: FAIL — stage missing / patterns absent.

- [ ] **Step 2: Write the failing self-test cases first**

Stub `git`, `./configure`, `make` in a fixture source tree. Cases: (a) stub `git rev-parse HEAD` printing a commit ≠ `R2_COMMIT` after checkout → abort `INSTALL-RE: radare2 FAIL: HEAD <got> != pinned 06a7c9d…`; (b) build invocation log shows `make -j2` exactly (never bare `make`, never `-j$(nproc)`); (c) probe case: stub `r2` that exits 1 unless `LD_LIBRARY_PATH` contains the lib dir → probe passes, proving the probe sets it; (d) the script contains no `apt` radare2 path and clones `https://github.com/radareorg/radare2` (upstream), never the fork; (e) **partial-install healing:** a fixture radare2 tree with working `r2 -v` but `bin/r2sdb` and `share/` removed → probe must FAIL and the stage must rebuild, not skip (the wringer's bin+lib-only experiment, as a fixture).

- [ ] **Step 3: Implement the stage**

Probe → skip as Task 2. Otherwise: clone upstream into `$HOME/opt/dist/radare2-src` (reuse an existing clone only if `git rev-parse HEAD` succeeds there and a checkout of tag `6.2.6` restores the pinned state; a clone dir that exists but is corrupt or partial — `git` errors, HEAD unresolvable — is removed and re-cloned, so a crashed clone cannot fail every future run), `git checkout 6.2.6`, assert `git rev-parse HEAD` = `06a7c9d35468676cc3fe6ea299885cf53aa8ad9b` (mismatch = fail closed), `./configure --prefix=$HOME/opt/radare2`, `make -j2`, `make install`, re-probe.

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

Fixture HOME cases: (a) run `install_env_block` twice → exactly one marker pair, file byte-identical after the second run; (b) fixture `.bashrc` with a pre-existing user `.profile` present → profile content untouched, block header says `pre-existing`; (c) no `.profile` → created sourcing `~/.bashrc`, header says `created-by-install-re-runtime`; (d) torn block (start marker, no end marker — the crash-halfway case) → rewritten whole, exactly one pair; (e) **adoption case:** fixture `.bashrc` already exporting `JAVA_HOME` *outside* markers (the live VM's hand-install state) → the stage prints `INSTALL-RE: env SKIP: unmarked RE exports present — manual adoption required` and changes nothing (adoption is Task 6's supervised step, never a silent duplicate); (f) **damage outside the block:** fixture `.bashrc` truncated mid-line *before* any marker (unterminated quote, no markers at all) → the stage must not append blindly: the run fails naming the file and the one-time backup path (Step 3), because the atomic write mechanism below makes this state unreachable *from the script's own writes* — its presence means an outside writer tore the file, and silently "repairing" it would bury lost user content; (g) `assert_rea` with `node`/`npx` absent from the stub PATH → prints the SKIP line and returns 0 (the run must still reach `verify_all`).

- [ ] **Step 3: Implement the stage**

**Write mechanism (mandatory, wringer amendment):** the new `.bashrc` content is composed in a temp file *in the same directory* (`~/.bashrc.install-re-runtime.tmp`), `fsync`ed, then installed by atomic `mv` over `~/.bashrc` — a crash leaves the old or the new file, never a torn one, and non-block content is carried through verbatim. `install_env_block` begins — before any inspection or modification — by ensuring the one-time backup `~/.bashrc.install-re-runtime.bak` exists, copying the `.bashrc` *as found* (damaged or not) if the backup is absent; creating it is not a modification of `.bashrc`, so case (f)'s fail-naming-the-backup always has a real path to name and the as-found state is preserved even when the stage then refuses to proceed. Torn-block detection (missing end marker, case (d)) still applies to blocks left by pre-amendment writes or hand edits. Marker-block replace-or-append per the cases; `ensure_profile` create-only-if-absent (grounding note: on the live VM `~/.profile` already exists — created 2026-11-01, sourcing `.bashrc` — so `pre-existing` is the expected path there; the draft's "this VM ships with no ~/.profile" is stale). `assert_rea`: `node` and `npx` on PATH → `INSTALL-RE: rea ok (npx -y rea-agents@6.5.0)` (record `node --version` in the line — Node is unversioned image state, and the record is the honest trace of that); absent → `INSTALL-RE: rea SKIP: node/npx not found — REA unavailable; this script does not install Node` and **return 0** — the `boot-gate.sh` precedent (`BOOT-GATE: policy SKIP`: mechanism not installed ≠ failure). REA absence never fails the run and never blocks `verify_all`; the original fatal-at-end shape would have left a Node-less machine installed-but-never-verified and permanently red.

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
- Produces: `verify_all` and the final `main` sequence (`assert_pins` → `preflight` → component stages → env stage → `assert_rea` → `verify_all` with the rebuild cycle below), replacing Task 1's not-implemented exit. `--dry-run` prints the `INSTALL-RE:` plan lines for the current probe state and writes nothing.

- [ ] **Step 1: Run the task's TDD checks, expect RED**

Run: `bash /tmp/re-runtime-checks/t5-verify.sh; bash /tmp/re-runtime-checks/t6-dryrun.sh`
Expected: both FAIL.

- [ ] **Step 2: Write the failing harness first**

`scripts/tests/test_install_re_runtime.sh` in the `test_watchdog.sh` mold (`ok`/`fail`/`check` helpers, fixture HOME under `mktemp -d`, stub bin dir). Two harness rules (wringer amendment): the script under test is launched by absolute path (`/bin/bash <script>`), never via a stub-PATH `bash` — in this mold a stub `bash` intercepts the launch itself; and **no `bash` stub is ever placed on the fixture PATH**, because a stubbed `bash -lc` proves only that the words were invoked. Cases: (a) `--dry-run` against an empty fixture HOME prints install-plan lines for all three components and creates no `opt/`; (b) `--dry-run` against a fixture HOME with probe-passing stubs prints `already installed` for each and still writes nothing (including no `.bashrc` change — hash before/after); (c) a full stubbed run (fixture tarballs + stub build) ends with `verify_all`'s login-shell resolution check executed by the **real** `/bin/bash -lc` with the fixture HOME — the env stage has written the fixture `.bashrc`/`.profile`, the fixture `opt/` holds stub tools that print the pinned versions, and the check genuinely resolves them through the login-shell path. This is the one harness case that proves wiring rather than words.

- [ ] **Step 3: Implement `verify_all` and `main`**

`verify_all` first **exports the bench environment into its own process** — `JAVA_HOME`, PATH prepended with `$JAVA_HOME/bin`, `$GHIDRA_INSTALL_DIR/support`, `$HOME/opt/radare2/bin`, and `LD_LIBRARY_PATH` including `$HOME/opt/radare2/lib`. (Writing the `.bashrc` block does not mutate the running shell; without this, `analyzeHeadless` in a non-login invocation finds no Java and a healthy bench fails verification — Feasibility demonstrated both directions on this VM.) It then runs the hand-verified checks exactly: `java -version` prints 25.0.4.1; `analyzeHeadless` **output** contains the Headless Analyzer usage text, run **with the headless heap capped (`MAXMEM=1G` in the invocation environment)** so the verification boot cannot OOM against the balloon — this check is output-based by contract: `analyzeHeadless` with no arguments **exits 1 while printing the usage** (Phase 4 verified live), so the exit code is ignored and only the output decides; `r2 -v` / `rabin2 -v` print 6.2.6; `rabin2 -I /bin/ls` identifies ELF64; `radiff2` on two identical files is clean; a fresh `bash -lc` resolves `java`, `analyzeHeadless`, and `r2` from PATH. Any failure: `INSTALL-RE: verify FAIL: <check>` + the component it belongs to. **Rebuild cycle (in `main`, wringer amendment):** if `verify_all` fails on a component whose install stage *skipped* in this run, `main` removes that component's directory, re-runs its install stage once, and re-runs that component's verify checks; only a second failure exits 1. A failure in a component installed fresh this run exits 1 immediately (its re-probe already failed-closed). A failure attributed to the *env stage* (the `bash -lc` resolution check) re-runs `install_env_block` once and re-verifies — unless the env stage answers with its SKIP (unmarked exports) or its case-(f) damage refusal, which exit 1 immediately, naming the state for manual adoption/repair. This cycle is what makes the Global Constraints convergence claim true for probe-passing-but-broken states the strengthened probes still miss.

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

- Create (evidence, not committed): rehearsal logs under the goal's `hidden_files/` (`~/workspace/goals/autonomous-code-defense-factory/hidden_files/re-runtime-rehearsal/rehearsal-a-noop.log` and `…/rehearsal-b-rebuild.log`)
- Modify (only if a rehearsal gap sends the script back): `scripts/install-re-runtime.sh`

**Interfaces:**

- Consumes: the finished script from Task 5.
- Produces: rehearsal evidence for the PR body: (a) no-op diff log, (b) rebuild run log with `verify_all` green. This task is execution evidence, not new code — a gap found here returns to the owning task (2–5) as a fix commit, per the draft's stop rule.

- [ ] **Step 1: Census the live bench and `.bashrc`**

Record `java -version`, `r2 -v`, `analyzeHeadless` presence, a hash of `~/.bashrc`, and `MemAvailable`; list the existing *unmarked* RE exports (expected: the 2026-10-20 hand exports). This census is the baseline rehearsal (a) diffs against. Memory discipline (Phase 4 amendment): if the census shows `MemAvailable` < 512 MiB, shut the NeuroStrata daemon down before any script run in this task (its documented ~800 MB RSS is the VM's largest reclaimable holder; the idle-reaper/runbook procedure in `~/workspace/neurostrata/` governs) and re-census — do not start a rehearsal run against a balloon-squeezed machine and call the resulting OOM a script defect.

- [ ] **Step 2: Adoption step (supervised, one-time)**

Back up `~/.bashrc` first (a timestamped copy beside it — the same one-time-backup discipline Task 4 mandates for the script). Then move the hand-written RE exports in `~/.bashrc` into the marker-guarded block by hand (same export lines, verbatim), hash before/after, and confirm a fresh `bash -lc` still resolves all three tools. This is a local environment edit on this VM only — it is not part of the script and never runs unattended.

- [ ] **Step 3: Rehearsal (a) — pure no-op**

Run: `bash scripts/install-re-runtime.sh`
Expected: every component `already installed`; `~/.bashrc` hash unchanged from Step 2's after-hash; exit 0. Any diff = stop, diagnose, fix in the owning task.

- [ ] **Step 4: Rehearsal (b) — rebuild**

Order matters (wringer amendment — downloads first, outage window last): (4a) fetch both artifacts fresh from their Pin Block URLs into the scratch dir `$HOME/opt/dist/.rehearsal-scratch/` and verify each against its pin *and* against the previously staged artifact's hash (this is the run's network-path proof); then rename the pre-existing staged artifacts aside — `temurin25.tar.gz` → `temurin25.tar.gz.rehearsal-aside`, `ghidra.zip` → `ghidra.zip.rehearsal-aside` — and move the fresh downloads into `$HOME/opt/dist/` under the asset names the script reuses. (4b) Only now rename (never delete) the three install dirs: `mv ~/opt/jdk-25.0.4.1+1 ~/opt/.rehearsal-aside-jdk` and likewise for Ghidra and radare2. (4c) Run the script in isolation (no test suites or lanes concurrently — memory ceiling; other lanes' RE routing is dead from this point until the run ends, which is why 4a precedes 4b). Expected: full install from pins, `verify_all` green including the fresh `bash -lc` check, no manual step anywhere. Any hand intervention = stop and restore, per this exact procedure: for each component the failed run recreated, remove the partial target dir (it is this run's own output, created after the rename — removing it is not deleting the bench), then `mv` the aside dir back to its original name, in reverse order (radare2, Ghidra, JDK); re-run the Step 1 census to prove the original bench is intact; record the gap and return to the owning task (draft Phase 2 stop rule). State the evidence honestly in the PR body: this is a same-VM rebuild from checksum-verified artifacts plus a fresh radare2 clone/build — not a fresh-VM provisioning proof (Goal).

- [ ] **Step 5: Close out the aside dirs**

Only after Step 4 verifies: all **five** asides — the three install dirs (`.rehearsal-aside-jdk`, `-ghidra`, `-radare2`) and the two staged artifacts (`temurin25.tar.gz.rehearsal-aside`, `ghidra.zip.rehearsal-aside`) — are deleted **only through the standing deletion rule in full — Pratik's explicit confirmation naming them, a 1-hour enforced delay, and his reconfirmation** (an earlier draft of this plan stated only the first element; the rule has all three). Until then they stay; the empty `.rehearsal-scratch/` dir may simply be removed (it holds nothing the rule protects — its contents were moved out in 4a). Save both run logs (`rehearsal-a-noop.log`, `rehearsal-b-rebuild.log`) as the task's evidence.

### Deferred: container route (draft Phase 3) — out of v1 per the D2 re-ruling

The Containerfile route (the former Task 7) is deferred out of v1 on Pratik's 2026-11-07 re-ruling (see Decisions, D2). Its full design text — Step 0 podman preflight, digest-pinned `ubuntu:24.04` base image, ESF bake-into-image constraints, the completed apt list — is preserved in this file's git history at the wringer commits `b3d98b1` and `69aa6f0`. Nothing in Tasks 1–7 depends on it; it may return as a follow-up once podman legitimately exists on the target machine.

### Task 7: CI wiring, operator documentation, branch-level verification

**Files:**

- Modify: `.github/workflows/ci.yml` (one step in `script-tests`)
- Modify: `scripts/install-re-runtime.sh` (header: operator note completed)
- Test: TDD check `/tmp/re-runtime-checks/t7-ci-docs.sh` (RED-verified at plan time; renumbered from t8-ci-docs.sh at the D2 re-ruling)

**Interfaces:**

- Consumes: the finished script (Tasks 1–5), rehearsal evidence (Task 6).
- Produces: the branch in its Stage 3 (independent review) input state. Nothing here changes script behavior.

- [ ] **Step 1: Run the task's TDD check, expect RED**

Run: `bash /tmp/re-runtime-checks/t7-ci-docs.sh`
Expected: FAIL — CI step missing.

- [ ] **Step 2: Wire CI**

Add to the `script-tests` job, beside the existing by-name steps, **both**: `- run: bash scripts/install-re-runtime.sh --self-test --offline` **and** `- run: bash scripts/tests/test_install_re_runtime.sh`. (Wringer amendment: an earlier draft of this plan excluded the harness citing "the same split as `boot-gate.sh`" — but the harness's own mold, `test_watchdog.sh`, *is* wired into `script-tests` by name at `ci.yml:42`; the harness is the plan's only end-to-end test and belongs in CI. Note honestly: the `shell-lint` glob `scripts/*.sh` does not reach `scripts/tests/`, so the harness is not shellcheck/shfmt-covered by CI — Step 4 lints it explicitly locally, and widening the CI glob is out of v1 scope because it would newly lint `test_watchdog.sh` too.)

- [ ] **Step 3: Complete the script header operator note**

How to run; how to bump a pin (pin-only PR; dual-source checksum evidence — upstream-published *and* locally computed, both quoted in the PR body; radare2 tag→commit resolution; post-merge run on this VM as acceptance). The dual-source rule is prose, so its gate is named: the pipeline Stage 3 independent reviewer verifies a bump PR's two quoted sources against the pin block before the PR proceeds — a bump whose evidence is single-source does not pass review. How to roll back (delete `~/opt/jdk-25.0.4.1+1`, `~/opt/ghidra_12.1.4_PUBLIC`, `~/opt/radare2`, the script's staged artifacts in `~/opt/dist/` — named individually, never the directory wholesale, it is shared; remove the marker block; remove `~/.profile` only if the block header records the script created it; the one-time `~/.bashrc.install-re-runtime.bak` may be restored if the env stage's state is in doubt). State in the header: there is no pin-bypass flag, by design.

- [ ] **Step 4: Branch-level verification (all must pass)**

Run: `shellcheck scripts/*.sh`, `shfmt -d -i 2 scripts/*.sh` (no diff), `shellcheck scripts/tests/test_install_re_runtime.sh` and `shfmt -d -i 2 scripts/tests/test_install_re_runtime.sh` (explicit — the CI glob does not cover this file), `bash scripts/install-re-runtime.sh --self-test --offline`, `bash scripts/tests/test_install_re_runtime.sh`, `python3 -m unittest discover -s scripts/tests` (non-regression), and the `/tmp/re-runtime-checks/t*.sh` set (t1–t7; t1/t4/t5 regenerated against the amended plan — Wringer Record executor note; the former t7-container check was retired and t8-ci-docs renumbered to t7-ci-docs at the D2 re-ruling).
Expected: every command green. (If shellcheck/shfmt are absent locally, note it and rely on the CI `shell-lint` job at Stage 6 — do not claim the check ran.)

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml scripts/install-re-runtime.sh
git commit -m "ci(scripts): wire install-re-runtime self-test; complete operator header"
```

## Verification (how the finished work is proven, end to end)

1. **Fresh-prefix install (fixture-bounded claim):** run the script with a scratch HOME (fixture stubs for the fast path in Task 5's harness; a real-network run is Task 6 Step 4's shape — rehearsal (b) — against an emptied bench). The scratch run must end with `verify_all` green and exactly these stage lines: `INSTALL-RE: temurin ok`, `INSTALL-RE: ghidra ok`, `INSTALL-RE: radare2 ok`, `INSTALL-RE: env ok`, and an REA line that is either `INSTALL-RE: rea ok …` or `INSTALL-RE: rea SKIP: …` — both are a pass (absence of Node is a SKIP state, never a failure). This proves the script installs the pinned toolchain into an empty HOME against stubbed downloads — it does not prove a fresh-VM provisioning (Goal), and the PR body words it that way.
2. **Version checks:** `java -version` → 25.0.4.1; `analyzeHeadless` usage text in output (output-based; its no-argument exit code is 1 and is ignored — Task 5 Step 3); `r2 -v`, `rabin2 -v` → 6.2.6; `rabin2 -I /bin/ls` → ELF64; `radiff2` clean; fresh `bash -lc` resolves all three tools from PATH.
3. **Checksum negative test:** the Task 2 self-test fixtures (wrong recorded hash; truncated download) abort with `INSTALL-RE: checksum FAIL`, extract nothing, and leave staging clean for the next run — plus the unpinned-pin negative test from Task 1. These run offline in CI on every PR via Task 7's wiring (self-test *and* harness).
4. **Idempotence proof:** Task 6 rehearsal (a) — second run on the live bench is a diff-verified no-op; Task 4's self-tests cover block duplication, torn block, damage-before-the-marker, profile clobber, and the unmarked-exports adoption case; Tasks 2/3's healing self-tests cover the probe-passing partial installs (missing `cacerts`, missing `launch.sh`, missing `r2sdb`/share data), and Task 5's rebuild cycle covers the residue the probes still miss. Every convergence claim in Global Constraints has at least one named test here — a claim without one does not ship.
5. **CI gates on the PR:** `shell-lint`, `script-tests`, `docs-lint` green (pipeline Stage 6, with the Codex final-head gate as written there).

## Self-Review (writing-plans checklist, run at plan time)

- Spec coverage: draft Scope IN items map to Tasks 1–5 (script + check scripts + header operator note), 6 (rehearsal = draft Phase 2), 7 (CI/docs finish). The container route (draft Phase 3) is deferred out of v1 per the D2 re-ruling — see Decisions. Draft Phase 0 ran as the wringer (record above); Phase 4 is pipeline-level, handled in "How the Draft's Phases Map" above — not silently dropped. Version-bump procedure and rollback (draft standing sections) land in Task 7 Step 3's header note. REA assertion: Task 4 (SKIP semantics per the wringer). `~/.profile` fix: Task 4.
- RED verification: all eight TDD check scripts in `/tmp/re-runtime-checks/` were run against the unmodified tree at base `49722a3` on 2026-11-07 and all fail (exit 1) — for Tasks 1–6 and 8 because the script is absent (greenfield: the check asserts the script exists and behaves, so absence is the honest RED state), for Task 7 because the Containerfile is absent. None is committed. (Post-re-ruling addendum, 2026-11-07: the container check was retired, the CI check renumbered to `t7-ci-docs.sh`, and t1/t4/t5/t7 were regenerated against the amended text and re-verified RED by the Stage 2 executor before implementation.)
- Type/name consistency: stage and probe names (`probe_temurin`, `install_ghidra`, `fetch_and_verify`, `verify_all`, …) are defined in the Interfaces block of the task that creates them and used unchanged later. Output prefix is `INSTALL-RE:` everywhere; the draft's example line matches.
- Draft-vs-repo conflicts found at plan time (flagged, not silently resolved): (1) the draft never mentions editing `ci.yml`, but the repo's `script-tests` job invokes shell self-tests by name — without the CI-wiring task's step (Task 8 at plan time; Task 7 after the re-ruling) the self-test would never run in CI; (2) the draft's rehearsal (a) "byte-identical `.bashrc`" claim cannot hold against the live VM's *unmarked* hand exports — Task 4's SKIP rule + Task 6's supervised adoption step close that gap; (3) the draft HTML renders the two SHA-256 pins truncated — the full values above were recovered from the staged artifacts and match the draft's prefixes; (4) `docs/plans/` currently holds the craft-anything plan as `.html`, but the tasking for this run specifies Markdown under the repo's docs-lint convention, which this plan follows.
