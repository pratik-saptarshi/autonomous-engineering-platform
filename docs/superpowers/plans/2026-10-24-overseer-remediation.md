# Overseer Remediation Implementation Plan (v-final, wringer-refined)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the overseer panel's P0 and P1 findings (and the cheap P2/P3 tail) in the autonomous-engineering-platform's first-party scripts, so every signal the platform emits — a receipts PASS, a policy check, a lane claim, a backup exit code — binds to the state it claims to describe.

**Architecture:** Receipts bind to a commit: a segment records (root, HEAD, tree digest) where the digest is recomputed from git objects at the recorded HEAD, so evidence validates against the tree it describes — never against whatever the working tree happens to hold later. Coordinator state moves out of the worktrees tree with a fail-closed migration rule, and claim verifies the policy file against its committed blob. The remaining fixes compose controls that already exist (process-group reap, env scrub) into the paths that lacked them, and make the watchdog's body match the contract its header (and the deployed adaptation) already promise.

**Tech Stack:** Python 3 stdlib only (`scripts/mechanical_verify.py` + unittest suites), bash (`lane-coord.sh`, `boot-gate.sh`, `watchdog-backup.sh` + self-tests), GitHub Actions YAML.

**Spec:** `review_panel_report.md` — the overseer panel report on main @ 37f0406 (workspace/goals/autonomous-code-defense-factory/files/review_panel_report.md; verification record in `~/workspace/worktrees/aep-overseer/.overseer/state/`). Findings cited as P0-1, P1-1…P1-7, P2-n, P3-n; recommendations as R1…R8. This plan was refined through a planning-wringer panel; the adjudication record is `.superpowers/sdd/2026-10-24-overseer-remediation/wringer-synthesis.md` and is part of the spec — where this plan and a reviewer's memory of the panel report disagree, the synthesis rules.

## Global Constraints

- Worktree branch `fix/overseer-remediation` off origin/main (37f0406). Conventional Commits, author `Musebot-Astro <6238157+pratik-saptarshi@users.noreply.github.com>`. Exact-path `git add` only (repo has no `.gitignore`).
- Every behavior change is TDD: failing test first (the panel's repro fixture where one exists), then minimal implementation, then the full affected suite green. No task is done on a red or unrun suite.
- Fail closed on format changes: pre-change receipts segments and state layouts are refused with a clear message, never silently reinterpreted (precedent: PR #40 round 3).
- The verifier stays stdlib-only; the coordinator stays dependency-free bash + python3-stdlib helpers.
- Suites that must stay green throughout: the Python suite under `scripts/tests/` (with `~/.venvs/pytest-verify` on PATH for mixed fixtures), `bash scripts/lane-coord.sh --self-test`, `bash scripts/boot-gate.sh --self-test`, the watchdog test (Task 7), shellcheck + `shfmt -i 2` clean on every touched `.sh`, markdownlint clean on touched docs.
- The verifier's 512 MiB memory preflight fails closed on this VM when memory is squeezed; a suite failure at the preflight is environmental — rerun when MemAvailable recovers, never "fix" it by weakening the preflight.
- Do not touch `reference/**` or vendored skill trees. Live skill copies under `~/workspace/custom-skills/` sync by hand after merge (operator step, listed in the execution ledger — not part of this branch, and no acceptance criterion claims it).
- **Evidence rule for this execution itself:** tasks are verified with the verifier as it exists when the task runs. Task 1 changes the CLI + the repo skill text together; from Task 1's merge onward the controller invokes `check-receipts --root <task worktree>` per the NEW skill text, and exit 2 means UNBOUND/UNVERIFIABLE only. The ledger records which verifier version produced each task's evidence.
- Independent review milestones (operator requirement): M1 after Task 2, M2 after Task 6, M3 whole-branch after Task 9. A milestone reviewer is a fresh agent that implemented nothing in its group. Milestones have no waiver language: a fixture that cannot run is a failed milestone, not a re-scope.

## Review Focus

1. A segment checked long after sealing (cross-session resume): must validate as evidence about its recorded HEAD, and must NOT pass a completion gate for a moved HEAD. (Task 1 `--historical` vs default modes.)
2. The workflow's own bookkeeping — the receipts file, `.superpowers/**` — changes inside the root constantly; neither the cleanliness gate nor any digest may treat it as tree mutation. (Task 1 tests.)
3. A worker process that outlives its verification command and is NOT the verifier's descendant (spawned by the harness, a daemon, another session): the Task 2 sweep must never kill it. (Task 2 snapshot-diff test.)
4. A module whose tests are all skipped: collected > 0, executed 0 — ruled a PASS by design (skip is the author's signal); the ruling is pinned by a test so it is a decision, not an accident. (Task 4.)
5. An operator mid-incident edits `policy.data` and needs lanes NOW: the claim refusal must name the exact remedy (commit the file, or set the override and have it recorded in the manifest). (Task 6 messages + manifest fields.)
6. The watchdog runs while the daemon is mid-shutdown by the idle reaper (marker present): it must not resurrect it; marker absent + daemon down: it must restart it. (Task 7 cases both ways.)

---

### Task 1: Receipts bind to the commit (R1, first half — closes P0-1)

**Files:**
- Modify: `scripts/mechanical_verify.py` — `append_run_start` (:487, called from `main()` ~:695), `append_completion` (called from `main()` on rc 0), `check_receipts` (:529), the run-start/completion field sets (near :363–:388), `main()` (:635) CLI.
- Modify: `skills/subagent-driven-development/SKILL.md` (repo copy) — the receipts completion paragraph and the `check-receipts` invocation (:51 region).
- Modify: `docs/deepcode-mechanisms.md` — receipts section (binding semantics as implemented here).
- Test: `scripts/tests/test_receipts.py`, `scripts/tests/test_mechanical_verify.py`.

**Interfaces:**
- Produces: `tree_binding(root: Path) -> dict` → `{"root": str (Path.resolve() of root), "head": str | None, "tree_digest": str, "mode": "git" | "fs"}`.
  - **git mode** (root is inside a git worktree): `head` = `git -C root rev-parse HEAD`; `tree_digest` = sha256 over, for each entry of `git ls-tree -r -z <head>` (NUL-terminated, raw path bytes — immune to `core.quotePath` config drift), the bytes `mode + " " + blob_sha + " " + path + "\n"` in ls-tree's own order. Computable from git objects at any later time; working-tree content is never read.
  - **fs mode** (no git): `head` = None; `tree_digest` = sha256 over sorted relative paths of `relpath + "\0" + sha256(bytes) + "\0"` (symlinks: target string, not followed), excluding any path component in `{".git", "__pycache__", ".pytest_cache", ".mypy_cache", "target", "node_modules", "coverage", "htmlcov", "dist", "build", ".tox", ".venv"}` and the receipts file itself.
- Produces: cleanliness predicate `tree_clean(root, receipts_path) -> bool` — git mode only: `git status --porcelain` is empty after dropping (i) entries whose path is the receipts file (when inside root) or under `.superpowers/`, and (ii) untracked entries (`??`) whose path has a component in the fs-mode exclusion dir set (tool caches and build outputs the run itself creates — a Python run leaves `__pycache__/` behind and must still be able to seal). Modified or staged TRACKED entries always count as dirty; the exclusions never hide a tracked change. (The two bookkeeping exclusions are the workflow's own state, never tree evidence.)
- Run flow (hooks in `main()`/`run_all`, NOT in the per-command executor): before the first command, compute the binding; git mode + not clean → the run's verdict is FAIL with message `tree not clean at HEAD — commit or stash before verifying` and NO completion record is appended (an incomplete segment is the existing fail verdict). After the last command, git mode: re-check cleanliness — dirtied during the run → no completion record. fs mode: recompute the digest — changed → no completion record. Otherwise `append_completion` records the binding from run start.
- `check_receipts(receipts_path, task, root, historical: bool) -> int`:
  - Segment with no binding (pre-change format) → exit 2, `RECEIPTS: UNBOUND`.
  - git mode: recompute the ls-tree digest at the recorded head. Commit unreadable → exit 2, `RECEIPTS: UNVERIFIABLE`. Digest mismatch → exit 1, `RECEIPTS: STALE`.
  - fs mode: recompute the live-tree digest; mismatch → exit 1 `RECEIPTS: STALE`.
  - Default (completion) mode additionally requires: root's current HEAD == recorded head (else exit 1, `RECEIPTS: HEAD-MOVED`) and `tree_clean(...)` (else exit 1, `RECEIPTS: DIRTY`). `--historical` skips only these two current-state requirements — it validates the segment as evidence about its own head.
  - CLI: `check-receipts --receipts P --task T --root R [--historical]`; `--root` is required.
- Skill text (repo copy): the invocation gains `--root <task worktree>`; the completion paragraph states the rule — completion requires a default-mode PASS (bound head == branch head, clean tree); `--historical` validates evidence on resume but never completes a task by itself; exit 2 from `check-receipts` means UNBOUND/UNVERIFIABLE (the old "no evidence" meaning is restated to attach to `verify` only).

- [ ] **Step 1: Write the failing tests.** (a) Panel stale-PASS repro, git form: fixture git repo, verify on a passing tree (committed), commit a breaking change, `check-receipts` (default) → exit 1 `HEAD-MOVED`; with `--historical` → exit 0 (the segment honestly describes its own head); a hand-forged completion record whose `tree_digest` is altered → `--historical` → exit 1 `STALE`. (b) Uncommitted mutation after verify → default check exit 1 `DIRTY`; `--historical` exit 0. (c) Dirty-at-verify: modify without committing → verify FAILS `tree not clean`, no completion record. (d) Bookkeeping immunity: writes to `.superpowers/ledger.md` and appends to the receipts file between verify and check → default check still passes. (e) Legacy segment (no binding) → exit 2 `UNBOUND`. (f) fs mode: non-git fixture, mutate after verify → check exit 1 `STALE`.
- [ ] **Step 2: Run; confirm the new tests fail** (today: no binding exists; (a)'s historical/STALE distinctions are unexpressible).
- [ ] **Step 3: Implement** per Interfaces: `tree_binding`, `tree_clean`, the `main()`/`run_all` hooks, `check_receipts` modes + CLI. Root is canonicalized with `Path.resolve()` wherever recorded or compared. **Field-set pin (RC3):** the writers add `binding` to the run-start and completion records, but the required-field tuples (`RECEIPT_FIELDS`/`RUN_START_FIELDS`/`COMPLETION_FIELDS`, :363–:395) do NOT gain it — `check_receipts` reads `binding` directly, and its absence routes to the UNBOUND branch (exit 2) BEFORE any required-field or type validation can call the segment corrupt.
- [ ] **Step 4: Update the skill text + docs section** in the same commit range; grep-pin the skill's literal `check-receipts` invocation in a test or the task review checklist (the command string in SKILL.md must match the CLI the code accepts).
- [ ] **Step 5: Run the full Python suite.** Pre-existing tests that construct segments by hand gain a binding computed via `tree_binding` on their fixture repos (never a hard-coded digest); any test asserting the old check-receipts CLI shape is updated to pass `--root`.
- [ ] **Step 6: Commit** — `feat(verify): bind receipts segments to the tree at their recorded HEAD` (split into two commits — code, then skill+docs — if the diff is unwieldy).

### Task 2: Reap detached descendants on every exit path (R1, second half — closes P1-5; completes P0-1)

**Files:**
- Modify: `scripts/mechanical_verify.py` — the per-command executor `run_verification(root, command, timeout_seconds) -> VerificationResult` (:220–:296), `VerificationResult` (gains a field), `main()` (subreaper setup), the receipt body writer.
- Test: `scripts/tests/test_mechanical_verify.py` — Task 2's new tests run the verifier through a SUBPROCESS harness (a small driver script under `scripts/tests/`) so subreaper state never touches the test-runner process.

**Interfaces:**
- Produces: `VerificationResult.survivors_killed: tuple[int, ...]` (default empty), written into the command's receipt record when non-empty.
- Subreaper: set ONCE in `main()` before `append_run_start`: `ctypes.CDLL(None).prctl(36, 1)` (PR_SET_CHILD_SUBREAPER), Linux + try/except; the run-start record carries `"subreaper": true|false`. Library/in-process callers do NOT set the flag; the sweep below is snapshot-scoped so it is safe either way.
- Sweep (runs strictly AFTER the command leader's `proc.wait()` has returned and BEFORE any next command spawns — never concurrently with a live Popen; this ordering is a stated invariant, because a stray reap of a live Popen child corrupts its reported exit code): iterate until no adoptees remain or 2 s elapse: (1) scan `/proc` for processes with `ppid == os.getpid()` that were NOT in the pre-spawn snapshot (the snapshot is taken immediately before this command's Popen) — these are adoptees of this command; (2) for each, read `(pid, start_time)` from `/proc/<pid>/stat`, re-read immediately before signalling, SIGKILL only on an exact `(pid, start_time)` match (the repo's pid-identity discipline); (3) reap killed adoptees with `waitpid(pid, WNOHANG)` per pid. Also SIGKILL any remaining members of the leader's process group (pgid probe), with the same start-time verification. Processes that existed before the snapshot (harness helpers, the test runner's own children) are NEVER signalled. If adoptees still remain when the 2 s bound expires, the command's verdict is FAIL (`survivors remain after reap bound`) — the bound may never silently pass a live survivor.

- [ ] **Step 1: Write the failing tests** (subprocess harness): (a) success-path `setsid` sleeper-writer → after the driver returns, the writer is dead and its marker file is size-stable across 1 s; the receipt records `survivors_killed`. (b) timeout-path detached survivor → killed. (c) bystander safety: the harness spawns its OWN long-lived helper BEFORE invoking the verifier; the helper is alive and unharmed after the run. (d) the PR #40 round-2 regression (`test_timeout_kills_sigterm_ignoring_descendant`) still passes.
- [ ] **Step 2: Run; confirm (a)/(b) fail today** (survivor lives), (c)/(d) pass.
- [ ] **Step 3: Implement** per Interfaces. Timeout semantics unchanged (SIGTERM → the existing `TERM_GRACE_SECONDS` 0.75 s grace → SIGKILL of the group); the sweep is additive after either path.
- [ ] **Step 4: Run the full Python suite.**
- [ ] **Step 5: Commit** — `fix(verify): reap detached descendants on every exit path`.

**MILESTONE REVIEW M1 (after Task 2):** fresh independent reviewer: (i) re-runs Tasks 1–2 fixtures; (ii) runs Task 2's fixtures 3× (flake smoke); (iii) cross-version control — runs the panel's stale-PASS fixture using a PRISTINE origin/main checkout's verifier against the branch tree, and the branch's verifier against the same fixture; a disagreement between the two is itself a finding; (iv) confirms the repo skill's literal verify/check-receipts commands parse against the new CLI. Verdict recorded in the ledger before Task 3 starts.

### Task 3: Coordinator state leaves the worktrees tree (R2 — closes P1-4 to the extent placement can; residual stated in AC 6)

**Files:**
- Modify: `scripts/lane-coord.sh` — `LANES_DIR` default (:51), claim/release/reap/status entry points, `--self-test` (new cases), header comment.
- Modify: `docs/deepcode-mechanisms.md` — state location, migration rule, and the residual-risk paragraph.
- Test: lane self-test cases (in-script).

**Interfaces:**
- Produces: default `LANES_DIR="${AEP_LANES_DIR:-$HOME/.local/state/aep/lanes}"`, created on demand (mkdir -p, then chmod 700 if this run created it). `AEP_LANES_DIR` override behavior unchanged.
- Produces: the legacy rule. `LEGACY_LANES_DIR="$HOME/workspace/worktrees/.lanes"`. When `AEP_LANES_DIR` is unset AND the legacy dir contains any `*.json`: `claim`, `release`, and `reap` refuse (exit 1) with one shared message naming the legacy path, the new default, and the two remedies (move the directory's contents to the new default — inspect them first; or set `AEP_LANES_DIR` to the legacy path to keep operating there deliberately). `status` still lists legacy lanes read-only, marked `legacy`. No code path reads or writes legacy state for any mutating operation — there is no dual-dir threading (a lane is settled only after migration, under the normal gates).

- [ ] **Step 1: Write failing self-test cases.** Case 23: fixture HOME with a legacy manifest planted → `claim` exits 1 with the migration message and creates nothing anywhere. Case 24: same fixture → `release` and `reap` on the legacy lane refuse identically; `status` lists it as legacy. Case 25: after moving the legacy dir's contents to the new default (the test performs the documented remedy), the lane settles normally through the existing gates.
- [ ] **Step 2: Run the self-test; confirm the new cases fail** (today the default IS the legacy location).
- [ ] **Step 3: Implement** per Interfaces; update the header comment and the operator doc (location, migration rule, plus two operator notes: retire stale worktree copies of lane-coord.sh before first post-merge use — an old copy still defaults to the legacy dir and will trip the refusal — and lane state now lives under `~/.local/state`, outside the old backup path lists).
- [ ] **Step 4: Run the full lane self-test** (normal + `env -i` scrubbed), shellcheck, `shfmt -i 2 -d` clean.
- [ ] **Step 5: Commit** — `fix(lanes): move coordinator state out of the worktrees root`.

### Task 4: Rule 5 proves execution, not routing (R3 — closes P1-1)

**Files:**
- Modify: `scripts/mechanical_verify.py` — classification inside `discover_verification_commands` (:64; the partition region :135–:160), command construction, and outcome evaluation in the run flow.
- Test: `scripts/tests/test_mechanical_verify.py`.

**Interfaces:**
- Classification is per-module, by AST, and follows the RUNNERS' collection semantics:
  - **unittest leg** iff the module defines a class whose bases include a dotted name ending in `TestCase` (direct `unittest.TestCase`, `TestCase` imported from unittest, or an alias of either). **Imports alone never create the leg** — `import unittest.mock` by itself creates NO leg here.
  - **pytest leg (module triggers the pytest command)** iff the module defines module-level (or async) `test_*` functions, OR classes named `Test*` containing `test_*` methods that are NOT TestCase subclasses, OR the module has no leg at all (default). A module whose only collectable content is TestCase subclasses does NOT by itself trigger the pytest command (RC2 — pure-unittest trees keep byte-identical argv); when the bare pytest command exists for other reasons it collects those modules too, which is how mixed trees get full coverage.
  - An AST parse failure falls back to today's substring classification for that module (discovery never crashes).
- Commands: the unittest leg, when non-empty, produces the unittest command over exactly its modules (argv as today). The pytest leg produces the EXISTING shared bare command (`python3 -m pytest -q`) whenever at least one module triggers it — argv and command id unchanged (pinned by the existing mixed-suite test). Single-style trees (pure TestCase, pure functions) produce byte-identical argv to today. **Named exception:** the existing `test_discovers_unittest_from_test_files` expectations for import-only stubs change — a stub that merely imports unittest no longer discovers a unittest command; Task 4 updates that test's stubs to define real TestCase subclasses where its intent is unittest discovery (the test's purpose — discovery from test files — is preserved; bare-import modules fall to the pytest default).
- Collected-count proof: each Python command's receipt records `"tests_collected"`, and the verdict is carried on `VerificationResult` (a `tests_collected` field, consulted by `run_all` exactly like Task 2's `survivors_killed`) so a zero-count command FAILS even when its exit code is 0. unittest: parse `Ran (\d+) tests?` from the command's stdout+stderr combined; 0 or unparseable → FAIL (`zero tests collected`). pytest: collected = the sum of all outcome groups in the summary line (passed+failed+skipped+deselected+errors+xfailed+xpassed); `no tests ran` → 0. A leg's count of 0 fails that command. **Ruling (deliberate):** skips count as collected — the guarantee is "routed to a runner that collects the test"; whether a collected test skips is the test author's signal, not a routing failure.

- [ ] **Step 1: Write failing tests.** (a) Panel decoy fixture end-to-end: passing `TestCase` + failing module-level function in one module → verify FAILS (today: PASS). (b) `import unittest.mock` only + plain functions → pytest leg only; a failing function FAILS verify. (c) `Test*`-class-only module with a failing method → executed under pytest, FAILS. (d) All-skipped module → verify PASSES with `tests_collected` > 0 (pins the skip ruling). (e) Collection-error module (import-time exception) → verify FAILS with no parseable count treated as failure. (f) The PR #40 round-3 regressions BY NAME: `test_discovers_mixed_styles_partitioned_by_runner`, `test_mixed_suite_failing_pytest_function_fails_verification`, `test_mixed_suite_all_passing_runs_both_runners` — run and keep green. (g) A unittest module that collects 0 (TestCase with no test methods) → FAIL `zero tests collected`.
- [ ] **Step 2: Run; confirm (a)–(c), (g) fail today.**
- [ ] **Step 3: Implement** per Interfaces.
- [ ] **Step 4: Run the full Python suite** (pytest venv on PATH).
- [ ] **Step 5: Commit** — `fix(verify): classify test modules by runner collection semantics; require collected-test proof`.

### Task 5: Compose the env scrub into the verifier (R4 — closes P1-2)

**Files:**
- Modify: `scripts/mechanical_verify.py` — env construction in the executor (:225), plus a new policy reader.
- Test: `scripts/tests/test_mechanical_verify.py`.

**Interfaces:**
- Produces: `policy_env_scrub(policy_path) -> tuple[str, ...]` — a NEW Python reader for the `[env-scrub]` section of `policy.data`. (A section parser exists embedded in lane-coord's `load_policy` as a python3 heredoc, `lane-coord.sh:301–338`, but it is not importable from `mechanical_verify.py`; the new reader ports its semantics.) Match semantics mirror `lane-coord.sh`'s `auth_occurrence_is_sensitive` (:386–:401) + `name_is_sensitive` (:408–:420) EXACTLY: case-insensitive substring match of each fragment against the variable NAME, with lane-coord's AUTH boundary exemptions (names whose sensitive occurrence is only the spared AUTH contexts — `SSH_AUTH_SOCK`, `GIT_AUTHOR_*` — are NOT scrubbed; `AUTHORITY` IS). The implementer ports lane-coord's truth table; tests pin every row of it.
- Produces: `build_run_env(policy_path) -> dict` = `os.environ` minus scrubbed names, unless `AEP_VERIFY_FULL_ENV=1` (full env; mirrors `AEP_LANE_FULL_ENV`). The run-start record states the mode in all cases: `"env": "scrubbed" | "full (AEP_VERIFY_FULL_ENV)" | "unscrubbed (no policy)"` — the record never claims a scrub that did not happen. Policy path: `${AEP_POLICY_DATA}` else `policy.data` beside the script; missing file → no fragments, mode `unscrubbed (no policy)`.

- [ ] **Step 1: Write failing tests.** Sentinel: choose a variable name containing a fragment READ FROM the repo's policy.data at test time (fragments are not hard-coded — the first fragment is `KEY`); tree code prints its environ; assert the sentinel is absent by default, present with `AEP_VERIFY_FULL_ENV=1`. Exemption rows: `SSH_AUTH_SOCK` and `GIT_AUTHOR_NAME` survive the scrub; `AEP_TEST_AUTHORITY` does not. Lowercase variant of a fragment name is scrubbed (case-insensitivity). Missing-policy case records `unscrubbed (no policy)`.
- [ ] **Step 2: Run; confirm failures** (sentinel leaks today; exemptions unimplemented).
- [ ] **Step 3: Implement** per Interfaces; every command the verifier runs uses `build_run_env`.
- [ ] **Step 4: Run the full Python suite.**
- [ ] **Step 5: Commit** — `fix(verify): apply the policy env scrub to verification runs`.

### Task 6: Bind the policy at the enforcement point (R5 — closes P1-3)

**Files:**
- Modify: `scripts/lane-coord.sh` — `load_policy` (:299–:360; its path resolution at :300 is a plain `dirname "${BASH_SOURCE[0]}"` today — switching it to the existing `canonical_path()` helper (:363) is a design instruction of this task, not current behavior), claim path (:600), manifest writer.
- Modify: `scripts/boot-gate.sh` — the policy result line (SKIP distinguishability, output token only).
- Test: lane self-test cases (new fixture-repo harness), boot-gate self-test (token assertion).

**Interfaces:**
- Claim-side integrity (in `load_policy`'s caller on the claim path only — release/reap act on already-claimed state and do not re-check):
  - Resolve the policy file as today (`${AEP_POLICY_DATA}` else `policy.data` beside the script, script dir via `canonical_path()`). All git probes in this task run as `git -C <canonical script dir> …` so a linked worktree's OWN HEAD is what resolves (RC7) — never the parent repo's.
  - "Set" means non-empty throughout: `AEP_POLICY_DATA` participates via the `${VAR:-}` idiom, so `AEP_POLICY_DATA=""` is UNSET (N5).
  - If `AEP_POLICY_DATA` is SET: no blob check; the claim proceeds; the manifest records `"policy_integrity": "operator-override"` + the file's sha256 + resolved path.
  - If unset: let `repo` = `git -C <script dir> rev-parse --show-toplevel`. If `git -C <script dir> cat-file -e HEAD:scripts/policy.data` succeeds, the loaded file's sha256 MUST equal the committed blob's — computed by STREAMING (`git -C <script dir> show HEAD:scripts/policy.data | sha256sum`; never capture the blob in a shell variable — command substitution strips the trailing newline and would mismatch every claim). Mismatch → claim refuses (exit 1, message naming the remedy: commit the policy change, or set `AEP_POLICY_DATA` and be recorded as an override). Manifest records `"policy_integrity": "verified"`.
  - If the cat-file probe fails (not a repo / repo without the path — the installed-copy case): no check; manifest records `"policy_integrity": "not-applicable"` + sha256 + path. Every claim manifest thus carries which of the three outcomes applied — the override is durable evidence, not a console line.
  - **Manifest threading (N4):** `policy_integrity`, the resolved policy path, and its digest are written by `write_manifest`'s fixed field list AND preserved by both `update_manifest_state` / `update_manifest_worker` reconstructions — a post-claim state rewrite must not drop them (the panel's P3-6 trap). Cases 27/28 assert the fields survive a worker-update rewrite.
- Single-source discharge: gate and claim keep their own one-line resolution (identical rule), and a lane self-test case asserts both scripts resolve the same default path and digest under the same environment — divergence becomes a test failure, not a design hope. boot-gate's policy output line gains the resolved path + short digest so the comparison is inspectable.
- boot-gate SKIP: `check_policy`'s exit contract is UNCHANGED (SKIP still exits 0 — mechanism-inactive semantics are the gate's design). The gate's output gains a final machine-readable token line: `BOOT-GATE-RESULT: POLICY-OK` when the policy check passed, `BOOT-GATE-RESULT: POLICY-INACTIVE` when it skipped. Distinguishability is by output token; the plan does not claim an exit-code distinction.

- [ ] **Step 1: Write failing tests.** Lane self-test gains a fixture-repo harness (RC6-complete: copy `lane-coord.sh`, `boot-gate.sh`, AND `policy.data` into a temp git repo under `scripts/`; fixture commits use `git -c user.name=… -c user.email=…`; the claim cases run with fixture `HOME`, `AEP_LANES_DIR`, and `AEP_WORKTREES_ROOT` pointed inside the fixture; commit a DIFFERENT policy blob at `scripts/policy.data`, then restore the working-tree policy to the original): Case 26 — claim refuses with the integrity message (working tree ≠ committed blob). Case 27 — commit the working-tree policy in the fixture repo → claim succeeds, manifest shows `"policy_integrity": "verified"`, and the fields survive a worker-update manifest rewrite. Case 28 — claim with `AEP_POLICY_DATA` at a modified file succeeds; manifest shows `"operator-override"` + digest, surviving the same rewrite. Case 29 — cross-check: boot-gate and lane-coord (both fixture copies) resolve the same default policy path+digest under the same env. Boot-gate self-test: the policy-skip case additionally asserts the `POLICY-INACTIVE` token; a policy-pass case asserts `POLICY-OK`.
- [ ] **Step 2: Run both self-tests; confirm the new cases fail.**
- [ ] **Step 3: Implement** per Interfaces.
- [ ] **Step 4: Run both self-tests fully** (lane: normal + scrubbed env), shellcheck, shfmt clean.
- [ ] **Step 5: Commit** — `fix(lanes): verify policy integrity at claim and record the outcome in the manifest`.

**MILESTONE REVIEW M2 (after Task 6):** fresh independent reviewer: re-runs the forged-manifest repro against a lane claimed under the NEW default state dir (the four-signal gates must refuse while the worker lives; after the worker dies, settlement proceeds — and the reviewer confirms AC 6's reworded claim is exactly what holds, no more); the dirty-policy and override claim cases; the legacy-refusal cases; both self-tests in full. Verdict in the ledger before Task 7 starts.

### Task 7: Watchdog — make the body keep the header's promises (R6 — closes P1-6; P1-7's repo half)

**Files:**
- Modify: `scripts/watchdog-backup.sh` — definition order (call :204, `stop_daemon` :212), change-path `stop_daemon || exit 0` (:235), `start_daemon` (:51, currently callerless), the main flow (:194ff).
- Create: `scripts/tests/test_watchdog.sh`.
- Modify: `docs/deepcode-mechanisms.md` or a watchdog note in `docs/operations.md` — the reference↔adaptation delta mapping (see Step 4).

**Interfaces:**
- Structure: every function defined before the main flow (move the flow below the last function definition — the prologue globals/lock stay at top; the reorder changes nothing else).
- Lifecycle (portable form of the deployed contract — the repo header at :5 and :12–13 already promises restart-if-down and restart-after-backup; the body is what changes). **Composition with the script's existing early gates (RC4) — the decision order is pinned:**
  1. The daemon-ACTIVE gate (:176–183 — a session is in flight) survives verbatim and runs first among the daemon-state checks: the run defers exactly as today.
  2. Hashes are computed (`NOW_SHA` vs `LAST_SHA`) BEFORE any stop/restart decision (the deployed copy's ordering).
  3. The daemon-DOWN early exit (:166–171) is REPLACED by the lifecycle decision: daemon down + leave-down marker present (`WATCHDOG_LEAVE_DOWN_MARKER` names a file; present = down is intentional, e.g. an idle-reaper shutdown in an adapted deployment) → log + exit 0, whatever the DB state. Daemon down + no marker + DB unchanged → restart it (`start_daemon` gains this caller), exit 0. Daemon down + no marker + DB changed → do NOT restart yet; fall through to the change path (its stop is a no-op on a down daemon; the copy is consistent because the daemon is down) and restart after the copy per the change path.
  4. Unchanged DB, daemon up: NO stop. Drive catch-up, exit 0.
  5. Changed DB, daemon up: stop (failure → exit 1, never `|| exit 0`), copy, hash-verify, then RESTART and health-poll (`$BIN status` loop, timeout from `WATCHDOG_HEALTH_TIMEOUT` default 60 — the deployed copy's hard-won value for a 547 MB model cold start). An EXIT trap restarts the daemon if this run stopped it and exits before the restart step, unless the marker says the down state is intentional.
  - `stop_daemon` failure on the unchanged path's (now removed) stop — n/a; any remaining stop failure anywhere exits 1.
- The header is then TRUE line for line; wording changes only where the marker mechanism needs naming.

- [ ] **Step 1: Write the failing test.** `test_watchdog.sh` with a fixture HOME (all daemon paths are `$HOME`-relative — verified): a stub `neurostrata-mcp` under the fixture HOME answering `status`; for stop scenarios, a REAL long-lived stub daemon process whose cmdline matches `pgrep -f '[n]eurostrata-mcp daemon'` (real pgrep, no scripted pgrep); `sleep` stubbed via PATH to compress poll loops; Drive left unconfigured (no folder-id file) in every case. Cases: (a) unchanged DB with daemon up → exit 0, daemon never signalled; (b) unchanged DB, daemon down, no marker → daemon restarted; (c) unchanged DB, daemon down, marker present → left down, exit 0; (d) changed DB, daemon up → stop, copy, restart, health OK, exit 0; (e) changed DB with a daemon that never exits → exit 1; (f) today's defects as regression pins: no 127 anywhere; stop failure never exits 0; (g) changed DB, daemon down, no marker → copy taken while down, daemon restarted after, exit 0; (h) daemon-active gate: with the stub reporting an active session, the run defers with today's exit behavior and touches nothing.
- [ ] **Step 2: Run; confirm (a)–(e) fail against the current script** for the expected reasons (127 on the unchanged path; stop-and-leave-down on change; no restart-if-down).
- [ ] **Step 3: Implement** per Interfaces.
- [ ] **Step 4: Record the delta mapping** (docs note): which deployed behaviors are now IN the reference (the lifecycle above), which remain environment deltas (binary/log paths, Drive optionality mechanics, the reaper-state file AS the marker's content in this VM's adaptation) — in the doc, not a commit body.
- [ ] **Step 5: Run** the watchdog test, shellcheck, shfmt.
- [ ] **Step 6: Commit** — `fix(watchdog): keep the lifecycle the header promises; fail loudly when the daemon will not stop`.

*P1-7's other half — a standing reconciliation process between the reference and its adaptations — remains an operations decision for the operator. This plan delivers a reference worth syncing from and the written delta mapping; no acceptance criterion claims the process exists.*

### Task 8: The bundle, repaired (R7 — closes P2-1 (residue), P3-1, P2-7, P2-8, P2-9)

**Files:**
- Modify: `scripts/mechanical_verify.py` — `main()` (:635) receipts placement; `check_receipts` validation (:529–:565); `MARKDOWNLINT_ARGV` (:34).
- Modify: `scripts/boot-gate.sh` — self-test gains `--offline` mode.
- Modify: `.github/workflows/ci.yml` — docs-lint `npx` line (:13), `uses:` pins, permissions, checkout options, script-tests job.
- Test: `scripts/tests/test_receipts.py`, `scripts/tests/test_mechanical_verify.py`.

**Interfaces:**
- (a) Receipts placement: `verify` refuses (exit 2) when the receipts path is inside the root AND that file is tracked by git. Path computation pinned (N2): resolve the receipts path absolutely; take its path relative to the git toplevel of the root; run `git -C <toplevel> ls-files --error-unmatch -- <relpath>` — success means tracked → refuse. (This form is correct for root-as-repo, root-as-subdirectory, and symlinked receipts paths.) Untracked receipts inside the root — the SDD layout — are explicitly allowed. Non-git roots: no placement rule (fs-mode binding excludes the receipts file from its digest, Task 1).
- (b) Strict field types in `check_receipts`, scoped to the SELECTED segment only (a historical oddity elsewhere in the file must not poison later segments). The type map is ENUMERATED IN CODE as an explicit table covering every field the writers can emit across the three record kinds AS EXTENDED by Tasks 1/2/4/5 (RC3b) — including `binding` (dict), `subreaper` (bool), `timed_out` (bool), `env` (str), `argv` (list), `survivors_killed` (list of int), `tests_collected` (int), and the pre-existing scalar fields. Known numeric fields validate with `type(v) is int` — EXCEPT `exit_code`, which may be `int` or `None` (a spawn-error receipt legitimately records null); known string fields with `type(v) is str`; bool/list/dict fields with their exact types. Unknown fields are IGNORED (forward compatibility — the schema must not freeze against issue #38 / P2-2 follow-ups). A violation → the segment is corrupt (exit 1), naming the field. A test produces a REAL bound segment via a fixture verify run and asserts it validates clean under this validation — the plan's own new records can never read as corrupt.
- (c) CI supply chain: `markdownlint-cli2` pinned to an exact version in the `npx` invocation; every `uses:` pinned to a full-length commit SHA (resolve SHAs for the currently-used tags at implementation time via `gh api repos/<owner>/<repo>/git/ref/tags/<tag>` — never from memory); top-level `permissions: contents: read`; `persist-credentials: false` on every `actions/checkout`. Scope note (N8): the `apt-get install shellcheck` line is distro-pinned by the runner image and OUT of scope; the `go install …@v3.10.0` shfmt line is already an exact version and stands.
- (d) boot-gate offline self-test + CI: `boot-gate.sh --self-test --offline` skips the real-environment case and stubs the first four checks (binaries/daemon/guards) for the policy cases, so it passes on a stock runner with no daemon and no gh auth; the full `--self-test` keeps today's behavior for this VM. CI's script-tests job gains `bash scripts/boot-gate.sh --self-test --offline` and `bash scripts/tests/test_watchdog.sh`.
- (e) `MARKDOWNLINT_ARGV` gains `!reference/neurostrata/**/*.md`, matching CI's exclusion set exactly.

- [ ] **Step 1: Write failing tests** — (a) git fixture with a TRACKED receipts file inside the root → verify exit 2; untracked → proceeds. (b) The panel EXP5 fixture, in the selected segment: `"exit_code": false`, `"duration_ms": true`, `"command_count": true` → corrupt; a segment with `"exit_code": null` (spawn error) followed by a valid retry segment → the retry validates. An unknown extra field → ignored, validates. (e) unit assertion on `MARKDOWNLINT_ARGV`. (d) run `boot-gate.sh --self-test --offline` in a stripped env (no daemon, minimal PATH) → must pass; today the mode doesn't exist. (c) is verified by the CI run at M3 + grep assertions in the task review.
- [ ] **Step 2: Run; confirm failures.**
- [ ] **Step 3: Implement (a), (b), (e)** in Python; **(d)** in boot-gate.sh; **(c), (d-CI)** in ci.yml.
- [ ] **Step 4: Run the full Python suite + lane self-test + boot-gate self-test (both modes) + watchdog test;** shellcheck/shfmt; markdownlint the touched docs.
- [ ] **Step 5: Commit** — `fix(scripts): tracked-receipts refusal, strict receipt types, CI pinning, offline gate test` (split Python vs CI/boot-gate if the diff exceeds ~200 lines).

### Task 9: Documentation verification (no new prose obligations)

**Files:**
- Verify (edit only on a failed check): `docs/deepcode-mechanisms.md`, `docs/daemon-lifecycle-contract.md`, `docs/operations.md`, `skills/subagent-driven-development/SKILL.md`.

- [ ] **Step 1:** For every doc the earlier tasks touched, re-read the FINAL code and confirm each behavioral claim (binding modes, state location + migration, scrub semantics + exemptions, policy outcomes, SKIP token, watchdog lifecycle + marker). Fix any claim the code doesn't keep. This step is also where Task 3's two operator notes live or die: assert the stale-lane-coord-copies warning and the `~/.local/state` backup-path note are present in the operator doc, or strike them from Task 3's definition of done in the ledger (N10).
- [ ] **Step 2:** Grep all first-party docs for numerals claiming test/case counts; verify each against the branch's actual suites; correct or de-numeralize. Check `daemon-lifecycle-contract.md`'s line citations against the post-Task-7 watchdog and note corrections.
- [ ] **Step 3: Commit** — `docs: verification pass over mechanism claims and counts` (skip the commit if Step 1–2 found nothing — an empty docs task is a valid outcome; record it in the ledger).

**MILESTONE REVIEW M3 (after Task 9):** whole-branch independent review — fresh reviewer, full diff vs origin/main; all suites re-run; the panel's complete repro-fixture set re-executed against the branch (stale PASS in both mutation forms, decoy TestCase, env sentinel + exemptions, forged manifest under the new default, dirty policy, bool/int receipts, watchdog lifecycle cases); the repo SDD skill's literal `verify`/`check-receipts` commands executed against a fixture tree; every ci.yml job's commands run locally (the real CI verdict comes after push and is reported before any merge); acceptance criteria checked one by one. APPROVED required before the branch is offered for push.

## Test Plan

- Per task: the failing-test steps above ARE the test plan; fixtures derive from the panel's verified repros (report §2 + `phase_10_verification.md`), so the panel's evidence becomes the regression suite (R8).
- Suite level, at every milestone and at M3: Python suite (pytest venv on PATH), lane self-test (normal + `env -i`), boot-gate self-test (full on this VM; `--offline` for CI parity), watchdog test, shellcheck + `shfmt -i 2 -d` on all touched shell, markdownlint on touched docs.
- Negative space: every refusal path (UNBOUND, UNVERIFIABLE, STALE, HEAD-MOVED, DIRTY, unclean-at-verify, migration refusal, integrity refusal, zero-collected, tracked-receipts refusal) has a test asserting exit code AND message.

## Acceptance Criteria

1. A bound segment validates against the tree at its recorded HEAD forever (git mode): post-seal working-tree mutation fails the completion check as DIRTY, a later commit fails it as HEAD-MOVED, and `--historical` still validates the segment as evidence about its own head — failing as UNVERIFIABLE when the recorded commit no longer exists, and as STALE when a record's stated digest does not match its stated head (the forged-record case; in fs mode, STALE is the live-digest mismatch). (P0-1)
2. On the CLI path, a `setsid`-detached process spawned by test code is dead after the verifier returns, on success and timeout paths (a survivor outliving the reap bound fails the command instead of passing silently — AC scope is the CLI path, where the subreaper is set; in-process callers get the snapshot-scoped sweep without the subreaper guarantee, as the Task 2 interface discloses); bystander processes predating the run are never signalled. (P1-5; completes P0-1)
3. The decoy-TestCase fixture FAILS verify; `unittest.mock`-only and `Test*`-class-only modules execute under the right runner; zero-collection on any leg FAILS; single-style argv is byte-identical to before; the named round-3 regressions stay green. (P1-1)
4. A scrub-fragment sentinel env var never reaches tree code by default, with lane-coord's exemption rows preserved (`SSH_AUTH_SOCK`, `GIT_AUTHOR_*` survive; `AUTHORITY` doesn't); the run-start record truthfully states the env mode in all three cases. (P1-2)
5. Claim refuses on a working-tree policy that differs from the committed blob (default path), with the remedy named; the override and not-applicable outcomes are recorded in the claim manifest with path + digest; gate and claim resolution cross-checked by test; SKIP is output-token distinguishable (`POLICY-INACTIVE`) with the gate's exit contract unchanged. (P1-3)
6. Coordinator state defaults outside the worktrees tree; legacy state blocks claim/release/reap with a migration instruction and remains visible read-only; after the documented migration the panel's forged-manifest repro fails against the lane under the normal gates. **Scope honesty:** placement removes the state from every tree a worker is tasked to operate in and closes the panel's repro; it is not a write boundary against a determined same-uid process, and that residual is documented in the operator doc rather than claimed away. (P1-4)
7. Watchdog: unchanged DB never stops the daemon; unexpectedly-down is restarted, intentionally-down (marker) is left; changed DB stops, copies, restarts, health-polls; stop failure exits 1 on every path; no 127; header matches body. The reference↔adaptation delta mapping is written in the docs. (P1-6; P1-7 repo half — the standing reconciliation PROCESS remains the operator's open decision, explicitly not claimed.)
8. Bundle: tracked receipts inside the root refused (untracked SDD layout unaffected); bool/int-confused fields in the selected segment are corrupt while `exit_code: null` and unknown fields validate; CI pins exact versions/SHAs with `permissions: contents: read` and no persisted credentials; CI runs the boot-gate offline self-test + watchdog test; verifier and CI lint gates identical. (P2-1 residue, P3-1, P2-7, P2-8, P2-9)
9. All suites green at M3; the repo skill's literal commands execute against the new CLIs; docs describe the implemented behavior with verified numerals.
10. NOT claimed by this plan: P2-2 (host-dependent evidence sets), P2-3 / issue #38 (lossy tail hashing — Task 8b is explicitly forward-compatible with it), P2-4/P2-10/P2-11/P2-12, P3-2…P3-6, P3-8, the Dependabot specifics, the P1-7 process decision, and the live-environment skill sync (operator step after merge). They remain open for separate triage.
