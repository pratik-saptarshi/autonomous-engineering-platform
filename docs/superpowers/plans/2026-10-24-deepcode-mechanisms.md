# DeepCode Mechanisms for AEP Implementation Plan — v2 (post-panel rewrite)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import three mechanisms mined from HKUDS/DeepCode into AEP, reshaped by the adversarial panel to fit the dispatch points AEP actually has: (1) **verification receipts** — the mechanical verifier from DeepCode, run by the reviewing/controlling side, whose own output is written as hash-chained receipts; (2) **launch-point controls** — environment sanitization and deny-first sensitive-path checks on a lane's declared working set, executed inside the one real dispatch point AEP has, the lane launcher; (3) a **lane coordinator** — the launcher itself: deterministic worktrees, manifests, capacity, and an OS flock fence held by the launcher process for its lifetime. v1's evidence ledger, completion `check`, and bash command-policy evaluator are **gone** (see Non-Goals and the Panel Disposition appendix) — not kept with caveats, deleted.

**Architecture:** Mechanism 1 is Python 3 stdlib (`scripts/mechanical_verify.py`): canonical-JSON hashing and bounded subprocess execution are data work, and `scripts/scan-gate.sh` already runs `python3` in production, so this adds no runtime dependency. Mechanisms 2+3 are one bash program (`scripts/lane-coord.sh`): the coordinator *is* the launcher, so the launch-point controls (env scrub, declared-path check) live in the same process that creates the worktree, acquires the fence, and spawns the worker — there is no separate policy engine and nothing is "routed through" a gate voluntarily. `scripts/policy.data` holds the pattern data (not code), and `scripts/boot-gate.sh` gains a read-only integrity check over it: the committed git blob is the reference, so policy edits flow through git/PR and the git history **is** the audit trail. Go is rejected as in v1: no first-party Go module exists, CI's go-checks job is scoped to `reference/esf`, and these tools do not justify a new module. **Language the implementer must not upgrade:** receipts are evidence only because the controlling side runs the verifier; fencing protects lanes launched through the coordinator, and only those; the declared-path check bounds the declared set, not everything a worker later touches. Task 9's operator doc pins this wording.

**Tech Stack:** bash (repo gate idiom), Python 3.12.3 stdlib only (no pip dependencies), `git`, `flock` (util-linux, verified at `/usr/bin/flock` on the VM and present on `ubuntu-latest`), `sha256sum`. **Not** `jq` in production paths (`scan-gate.sh` sets the precedent that `python3` is AEP's JSON tool); **not** `npx` at verification time (Risk R11 — the markdownlint check requires a preinstalled binary, see Task 1).

**Spec:** `docs/deepcode-reference.md` (DeepCode reference study; on branch `docs/deepcode-reference`, PR #33, not yet merged at plan time — read it from `~/workspace/worktrees/aep-deepcode-ref/docs/deepcode-reference.md`). Source of record: DeepCode pinned at `49805ef25e5c18b2a58ae797028f599b6aca161b`, local copy at `~/workspace/spikes/deepcode/src/`. Key source files for v2: `core/verification.py` (discovery, bounded execution), `core/harness/permissions.py` (sensitive-path pattern list, lines 69–94), `core/harness/env_sanitize.py` (`SENSITIVE_ENV_PATTERN`, line 64), `core/application/execution_coordinator.py` (capacity default, line 101), `core/application/worktree_service.py` (deterministic worktrees, manifest-validated removal), `core/file_lock.py` (descriptor-held lease), `docs/AUTOMATION_ARCHITECTURE.md`.

## Global Constraints

- **Branch:** work on `feat/deepcode-mechanisms` (already cut from `origin/main` at `7a15219`). Do not push; pushes and PRs need Pratik's per-action authorization.
- **Commits:** Conventional Commit subjects; author `Musebot-Astro <6238157+pratik-saptarshi@users.noreply.github.com>` (pass `-c user.name`/`-c user.email` if unset). Exact-path `git add` only — the repo has **no `.gitignore`**, never `git add -A`.
- **Public repo:** no credentials, tokens, or real generated config in any file, fixture, or test. Test fixtures use obviously synthetic values (`not-a-real-secret`). The gitleaks CI job must stay green.
- **Exact values copied from DeepCode** (each verified against the pinned source by the panel; do not re-derive): verification timeout default **300 s**; verification output tail cap **65536 bytes** per stream; timeout kill sequence SIGTERM → **0.75 s** grace → SIGKILL on the process group; child env adds `CI=1` **and** `PYTHONUNBUFFERED=1`; on timeout the result records the killed process's return code (not `None`); coordinator default capacity **2** (`core/application/execution_coordinator.py:101`); env-scrub pattern alternatives `KEY|PASSWORD|SECRET|TOKEN|CREDENTIAL|AUTH` with DeepCode's AUTH boundary behavior (`core/harness/env_sanitize.py:64`); the sensitive-path pattern list in Task 5 is DeepCode's 25 patterns (lines 69–94) minus its two product-specific entries, plus the `gh` pair (below).
- **Deliberate deviations from DeepCode** (each argued where it lands, all in Task 9's table): AEP discovery order is go → cargo → npm → python → make → markdownlint with per-rule provenance tags (DeepCode's order is python → npm → cargo and it has no go/make/markdownlint rules); receipt fingerprints are full 64-char SHA-256, not DeepCode's 16-char truncation; the verifier stops at the first failure and runs under a total budget (AEP addition, Risk R8); zero discovered commands is a distinct exit (2), not DeepCode's silent proceed and not a hard FAIL; the sensitive-path list drops DeepCode's `*/.deepcode/credentials*` and `*/deepcode_config.json` and adds `*/.config/gh`, `*/.config/gh/*` (this platform's GitHub PAT lives in `~/.config/gh/hosts.yml`, verified present).
- **Skill-copy drift (verified by diff in this rewrite):** the repo `skills/` copies of both skills edited here **already diverge** from the live sources under `~/workspace/custom-skills/` — they are different documents, not copies awaiting a sync. Tasks 3 and 8 therefore edit **both** copies, each against its own current text, with acceptance criteria checking the **live** copy. `~/workspace/custom-skills/` is not a git repository: live edits are direct file edits that take effect for local runs immediately and are never part of the branch diff. There is no post-merge mirror step in v2.
- **No `~/.aep`, no snapshots:** v2 has no runtime state under `$HOME` dotdirs. Lane state lives under `${AEP_LANES_DIR:-$HOME/workspace/worktrees/.lanes}` (created by `mkdir -p` inside the claim transaction — the parent directory exists). The receipts file lives wherever the controller's workspace is (the SDD skill names it). Boot-gate writes nothing.
- **Shell quality bar:** every new or modified `scripts/*.sh` passes `shellcheck` and `shfmt -d -i 2` (the CI shell-lint job runs both over `scripts/*.sh`). **Both tools are absent on this VM** (verified) — local lint steps hedge on the absence of *both*; CI is the authority. Python files are covered in CI only by the script-tests job added in Task 9.
- **Markdown:** new/modified `.md` files pass the docs-lint job (`npx --yes markdownlint-cli2 "**/*.md" "!reference/esf/**/*.md" "!skills/archify/**/*.md"`, config `.markdownlint.yaml`). This applies to the skill files at the paths where they are edited — repo copies via the CI glob, live copies by running the same command against them in Tasks 3 and 8.

## Non-Goals (explicit, with reasons)

- **No-progress loop detection (`observe`) — OUT.** DeepCode's ledger is written by its runner at every tool-call boundary (`core/agent_runtime/runner.py:736`); AEP has no dispatch observer and no equivalent boundary, so observations would be self-reported by the party being gated, with no consumer reading them. Killed by DA Premise 3b / judge's ruling 1.
- **Command-string policy evaluation (`policy-gate.sh check`/`run`) — KILLED, do not resurrect.** No AEP process dispatches lane commands through a script, and a bash whitespace tokenizer is bypassable by quoting, variable indirection, embedded code strings, and symlinks (DA Premise 4). Its denies would be cited as a boundary that does not exist.
- **Policy freeze/snapshots — deleted.** Replaced by git-as-audit-trail: `policy.data` is committed, boot-gate verifies the working tree matches `HEAD` (Task 7). No mode field exists anywhere in v2, so there is no mode to escalate (Risk R7).
- **Cron wiring of boot-gate — NOT this plan.** Cron invocation of `boot-gate.sh` is issue #17's unexecuted scope. This plan lands the script-side policy check only and **must not claim cron enforcement anywhere** — not in the doc, not in commit messages, not in acceptance criteria.
- **Signaling lane processes — never.** Operational code in `lane-coord.sh` signals no process, ever; only the `--self-test` harness signals processes it spawned itself (pinned by Acceptance Criterion 7). Death is proven only by flock acquisition.
- **Sandboxing `verify` — no.** The verifier executes the target repo's test code with the reviewer's full privileges; it is an execution mechanism, not a passive check. The budget and memory preflight in Task 1 are guards against accidents, not a sandbox. Task 9's doc says exactly this.

## Review Focus

- **Receipt chain validation covers the whole file.** `check-receipts` filters by task only *after* recomputing the chain over every line — a validation that skipped other tasks' lines would let an edit hide between them. Pinned by Task 2 tests 6–8.
- **The capacity lock is held only for count + settle + fence + manifest** (bounded wait, exit 5 on timeout); `git worktree add` happens after it is released. A claim that hangs must not serialize every lane on the VM (Risk R13).
- **The launcher never signals any process**, including PIDs recorded in manifests it did not write. `launcher_pid` is operator information only. Pinned by Task 6 case 16 and Acceptance Criterion 7.
- **Declared-path checks canonicalize** (`os.path.realpath`, symlinks resolved, as in DeepCode `permissions.py:180-196`) — but they bound the *declared* set only. A lane can touch undeclared paths after launch; nothing in v2 confines it, and the doc must not say otherwise.
- **Skill insertions are per-copy.** The live and repo SDD documents and the live and repo overnight-lanes documents are four different texts. Each task quotes the exact target text from the file it edits; pasting one insertion into both copies of a skill would corrupt one of them.

---

## File Structure

**Mechanism 1 — verification receipts (Python, `scripts/`):**
- Create `scripts/mechanical_verify.py` — allowlist discovery, bounded/budgeted execution, receipts append + chain validation, CLI subcommands `verify` and `check-receipts`.
- Create `scripts/tests/test_mechanical_verify.py`, `scripts/tests/test_receipts.py` — `unittest` suites (26 tests total, named in Tasks 1–2).
- Modify `skills/subagent-driven-development/SKILL.md` (repo copy) **and** `~/workspace/custom-skills/subagent-driven-development/SKILL.md` (live copy) — the completion step requires controller-run receipts (Task 3).

**Mechanisms 2+3 — lane launcher/coordinator (bash, `scripts/`):**
- Create `scripts/policy.data` — the launch policy data: sensitive-path patterns + env-scrub fragments (Task 5).
- Create `scripts/lane-coord.sh` — `claim` (the launcher: fence, capacity, worktree, controls, worker spawn) / `release` / `reap` / `status`, embedded `--self-test` (Tasks 4–6).
- Modify `scripts/boot-gate.sh` — new read-only `policy` integrity check as the fifth check, two new self-test cases (Task 7).
- Modify `skills/overnight-parallel-lanes/SKILL.md` (repo copy) **and** `~/workspace/custom-skills/overnight-parallel-lanes/SKILL.md` (live copy) — Run Setup step 2 launches lanes through the coordinator (Task 8).

**Cross-cutting (Task 9):**
- Modify `.github/workflows/ci.yml` — add a `script-tests` job (sixth job).
- Create `docs/deepcode-mechanisms.md` — operator doc: contracts, consumers, runbooks, deviations, activation checklist.

**Runtime state (never committed):** lane state at `${AEP_LANES_DIR:-$HOME/workspace/worktrees/.lanes}/`; lane worktrees under `${AEP_WORKTREES_ROOT:-$HOME/workspace/worktrees}/`; receipts files at controller-chosen paths (SDD: `<workspace>/receipts.jsonl`).

---
### Task 1: Mechanical verifier — allowlist discovery, bounded and budgeted execution

**Files:**
- Create: `scripts/mechanical_verify.py`
- Test: `scripts/tests/test_mechanical_verify.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces (names mirror DeepCode `core/verification.py`, verified in source):
  - `VerificationCommand` (frozen dataclass): `id: str`, `label: str`, `argv: tuple[str, ...]`.
  - `VerificationResult` (frozen dataclass): `command`, `exit_code: int | None`, `timed_out: bool`, `duration_ms: int`, `stdout: str`, `stderr: str`, `output_truncated: bool`; property `passed == (exit_code == 0 and not timed_out)`. `exit_code` is `None` only when the process could not be spawned (OSError — the exception text goes to `stderr`, `passed` is False); on timeout it is the killed process's return code.
  - `discover_verification_commands(root: Path) -> tuple[VerificationCommand, ...]` — fixed allowlist, evaluated in this (AEP) order, all matches returned, deduplicated by `id`:
    1. `go.mod` file → `("go-test", "Go tests", ("go", "test", "./..."))` **[AEP addition — DeepCode has no go rule]**
    2. `Cargo.toml` file → `("cargo-test", "Rust tests", ("cargo", "test"))` **[DeepCode]**
    3. `package.json` with a real `scripts.test` string (non-empty, not containing `no test specified`, case-insensitive) → `("npm-test", "Node tests", ("npm", "test"))` **[DeepCode]**
    4. any of `pytest.ini`, `pyproject.toml`, `setup.cfg`, or a `tests` path (**any file type** — DeepCode checks `(root / "tests").exists()`) → `("pytest", "Python tests", ("python3", "-m", "pytest", "-q"))` **[DeepCode]**
    5. root-level `test_*.py` **or `*_test.py`** files whose first 65536 chars are scanned for `import unittest` / `from unittest`: if any file imports unittest → `("unittest", "Python unittest", ("python3", "-m", "unittest", "discover", "-v"))`; else (test files exist, none imports unittest) → the `pytest` command from rule 4 (DeepCode's fallback in `_discover_python_tests`; suppressed if rule 4 already produced it) **[DeepCode, adapted]**
    6. `Makefile` with a line matching `^test:` → `("make-test", "Make tests", ("make", "test"))` **[AEP addition: ESF and AEP-adjacent projects drive tests through make]**
    7. `.markdownlint.yaml` file **and** `shutil.which("markdownlint-cli2") is not None` → `("markdownlint", "Markdown lint", ("markdownlint-cli2", "**/*.md", "!reference/esf/**/*.md", "!skills/archify/**/*.md"))` **[AEP addition: this repo's docs-lint job, with the binary called directly — never `npx --yes`, which is an unpinned network fetch at gate time (Risk R11)].** If the config exists but the binary is absent, discovery omits the command and the CLI prints the SKIPPED line defined below.
  - `run_verification(root: Path, command: VerificationCommand, timeout_seconds: int = 300) -> VerificationResult` — subprocess with `start_new_session=True`, env = parent env + `CI=1` + `PYTHONUNBUFFERED=1`; drains stdout/stderr keeping only the **last 65536 bytes** each (tail cap, `output_truncated` set when exceeded; drain incrementally — reader threads or `selectors` — so a command emitting >64 KiB early cannot block on a full pipe); on timeout, SIGTERM the process group, wait **0.75 s**, SIGKILL the group; `timed_out=True`, `exit_code` = the process's return code.
  - `available_memory_kb() -> int | None` — parses `MemAvailable` from `/proc/meminfo`; `None` when unreadable (non-Linux) — the preflight is skipped then.
  - `run_all(root, commands, *, timeout_seconds=300, budget_seconds=600, mem_available_kb=available_memory_kb, on_result=None) -> int` — the CLI's engine, factored for in-process tests: (a) memory preflight — if `mem_available_kb()` returns a value **< 524288** (512 MiB), print `VERIFY: insufficient memory available (<n> MiB < 512 MiB); refusing to run` and return **3**; (b) before each command, if elapsed ≥ budget, print `VERIFY: budget exhausted (<budget>s); <k> command(s) not run` and stop; each command's effective timeout is `min(timeout_seconds, budget − elapsed)`; (c) run commands in discovery order, invoking `on_result(result)` after each (Task 2's receipts hook); (d) **stop at the first failure** — after a failed or timed-out command, print `VERIFY: stopped at first failure (<id>)` and run no further commands; (e) print `VERIFY: <id> PASS` or `VERIFY: <id> FAIL exit=<exit_code|spawn-error> duration_ms=<n>` per executed command. Return codes: **0** ≥1 command ran and all passed; **1** a command failed/timed out, or the budget stopped the run before any command executed; **2** zero commands discovered (the CLI prints `VERIFY: no verification commands discovered at <root> — no mechanical evidence available` before calling `run_all`); **3** memory refusal.
  - CLI: `python3 scripts/mechanical_verify.py verify --root <dir> --task <id> [--timeout <s, default 300>] [--budget <s, default 600>] [--receipts <file>]`. The `--task`/`--receipts` behavior is Task 2; in this task the flags exist and `--task` is required (receipts are meaningless without it) but no receipts file is written yet — Step 3 implements `verify` without the receipts write, Task 2 adds it. If `.markdownlint.yaml` exists at `<root>` but rule 7 did not fire, print `VERIFY: markdownlint SKIPPED tool missing (markdownlint-cli2 not on PATH)` (does not affect the exit code).

- [ ] **Step 1: Write the failing tests**

Create `scripts/tests/test_mechanical_verify.py`. Header: `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` before importing `mechanical_verify`. Seventeen tests; fixtures are `tempfile.TemporaryDirectory` roots with marker files written by the test:

1. `test_discovers_go_test_from_go_mod` — root with empty `go.mod`: ids == `["go-test"]`, argv `("go", "test", "./...")`.
2. `test_discovers_cargo_test_from_cargo_toml` — ids == `["cargo-test"]`.
3. `test_discovers_npm_test_only_with_real_script` — `package.json` with `{"scripts": {"test": "node --test"}}`: ids == `["npm-test"]`; with `{"scripts": {"test": "echo \"Error: no test specified\" && exit 1"}}`: ids == `[]`.
4. `test_discovers_pytest_from_markers` — root with `pyproject.toml`: `pytest` present; root with only a `tests` directory: `pytest` present.
5. `test_discovers_unittest_from_test_files` — root with `test_x.py` containing `import unittest`, no markers: ids == `["unittest"]`; root with only `y_test.py` containing `from unittest import TestCase`: ids == `["unittest"]`.
6. `test_discovers_pytest_fallback_when_test_files_lack_unittest` — root with `test_x.py` containing only `def test_a(): assert True`, no markers: ids == `["pytest"]`.
7. `test_discovers_make_test_from_makefile_target` — `Makefile` containing `test:\n\ttrue`: ids == `["make-test"]`; a `Makefile` with only a `build:` target: ids == `[]`.
8. `test_discovers_markdownlint_when_tool_on_path` — root with `.markdownlint.yaml`; a stub executable named `markdownlint-cli2` in a temp bin dir prepended to `PATH` (patch `os.environ` for the discovery call): ids == `["markdownlint"]` with the exact argv above.
9. `test_markdownlint_skipped_when_tool_missing` — CLI subprocess run (`sys.executable` on the script, `verify --root <root> --task t`) with `PATH` = a temp bin containing only a `python3` symlink to `sys.executable`, root with `.markdownlint.yaml` and a `Makefile` `test:` target of `true`: stdout contains `VERIFY: markdownlint SKIPPED tool missing`, exit 0 (make-test passed).
10. `test_no_markers_discovers_nothing` — empty root: `()`.
11. `test_run_captures_pass_and_exit_code` — `run_verification(root, VerificationCommand("t", "t", ("true",)))` → `passed`, `exit_code == 0`; with `("false",)` → not passed, `exit_code == 1`. (Direct argv injection at the API level only; the CLI never accepts arbitrary commands.)
12. `test_run_enforces_timeout` — argv `("sleep", "5")`, `timeout_seconds=1` → `timed_out` true, `passed` false, `exit_code` not in `(None, 0)`, `duration_ms < 3000`.
13. `test_run_caps_output_at_65536_bytes` — argv `("python3", "-c", "import sys; sys.stdout.write('x' * 200000)")` → `len(result.stdout.encode()) <= 65536`, `output_truncated` true.
14. `test_verify_stops_at_first_failure` — CLI subprocess on a fixture with `package.json` `{"scripts": {"test": "false"}}` and a `Makefile` with a `test:` target of `true`: stdout contains `VERIFY: npm-test FAIL` and `VERIFY: stopped at first failure (npm-test)`, does **not** contain `VERIFY: make-test`, exit 1.
15. `test_verify_no_commands_exit_2` — CLI subprocess on an empty root: stdout contains `VERIFY: no verification commands discovered`, exit 2.
16. `test_verify_memory_refusal_exit_3` — in-process: patch `mechanical_verify.available_memory_kb` to return `100000`, call `main(["verify", "--root", <root with Makefile test:true>, "--task", "t"])`, expect `SystemExit` code 3 and the refusal line (capture stdout).
17. `test_verify_budget_zero_stops` — in-process: call `run_all` with `budget_seconds=0` on any command tuple: returns 1, prints the `VERIFY: budget exhausted (0s)` line, and `on_result` is never invoked.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/workspace/worktrees/aep-deepcode-impl && python3 -m unittest discover -s scripts/tests -p 'test_mechanical_verify.py' -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mechanical_verify'`.

- [ ] **Step 3: Implement `scripts/mechanical_verify.py`**

Module with the dataclasses, discovery, bounded runner, `run_all`, and a `verify` CLI (receipts flag accepted, writing deferred to Task 2). Stdlib only (`argparse`, `dataclasses`, `json`, `os`, `shutil`, `signal`, `subprocess`, `sys`, `threading`, `time`, `pathlib`). `main(argv) -> int` returns the exit code and the `__main__` guard does `sys.exit(main(sys.argv[1:]))`, so tests can call `main` in-process.

- [ ] **Step 4: Run tests to verify they pass**

Run: same command as Step 2.
Expected: `Ran 17 tests ... OK`.

- [ ] **Step 5: Commit**

```bash
git add scripts/mechanical_verify.py scripts/tests/test_mechanical_verify.py
git commit -m "feat(evidence): allowlist mechanical verifier with bounded, budgeted execution"
```

---

### Task 2: Verification receipts — the verifier writes the evidence, hash-chained

**Files:**
- Modify: `scripts/mechanical_verify.py` (receipts append on `verify`; new `check-receipts` subcommand)
- Test: `scripts/tests/test_receipts.py`

**Interfaces:**
- Consumes: Task 1's `run_all` `on_result` hook, `VerificationResult`, exit codes.
- Produces:
  - **Trust shape (stated here, repeated in Task 9's doc):** a receipt is written only by `mechanical_verify.py` itself, from a result it just produced by executing the command. Receipts are completion evidence **only when the controlling side (reviewer/controller) ran `verify`, or chain-validates a receipts file it generated earlier in the same run.** A receipts file an implementer hands over is an audit artifact, not proof — Task 3's skill text says so verbatim.
  - Receipt line: one JSON object per line (JSONL), exact fields: `{"ts": <ISO-8601 UTC str>, "task": <str>, "command_id": <str>, "argv": [<str>, ...], "exit_code": <int|null>, "timed_out": <bool>, "duration_ms": <int>, "stdout_sha256": <64 lowercase hex of the capped stdout bytes>, "stderr_sha256": <64 lowercase hex>, "chain_sha256": <64 lowercase hex>}`. **Receipts never contain output text** — only hashes of the capped output the verifier actually saw.
  - Chain: let `body` = the receipt dict without `chain_sha256`; `canonical = json.dumps(body, sort_keys=True, ensure_ascii=False)`; `chain_sha256 = sha256((prev_chain + canonical).encode("utf-8")).hexdigest()`, where `prev_chain` is the previous line's `chain_sha256`, or `"0" * 64` for the first line in the file.
  - `append_receipt(receipts_path: Path, task: str, result: VerificationResult) -> None` — opens the file with `os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND)`, takes an exclusive `fcntl.flock` on the fd, reads the current last line to find `prev_chain` (a malformed last line raises), performs a **single `os.write`** of the complete line + `\n`, closes. Wired into the `verify` CLI: when `--receipts <file>` is given, `run_all`'s `on_result` appends one receipt per executed command (commands never executed — after a failure stop or budget stop — get no receipt).
  - CLI: `python3 scripts/mechanical_verify.py check-receipts --receipts <file> --task <id>`. Validation order: (1) parse every line — line `<n>` not valid JSON or missing a required field → print `RECEIPTS: corrupt at line <n>`, exit 1; (2) recompute the chain over **every** line in file order — first line whose stored `chain_sha256` disagrees → print `RECEIPTS: chain broken at line <n>`, exit 1; (3) only then filter by task: no receipts with `task == <id>` → print `RECEIPTS: FAIL task <id>: no receipts`, exit 1; any receipt for the task with `exit_code != 0` or `timed_out` → print `RECEIPTS: FAIL task <id>: receipt failed: <command_id>`, exit 1; otherwise print `RECEIPTS: PASS task <id>: <n> receipts, chain valid`, exit 0.
  - `verify` against a receipts file whose last line is malformed refuses before running anything: print `RECEIPTS: corrupt at line <n> in <file>`, exit 1 (fail closed — a torn receipts file is never appended to blindly).

- [ ] **Step 1: Write the failing tests**

Create `scripts/tests/test_receipts.py` (same `sys.path` header). Nine tests; CLI invocations via subprocess with `sys.executable`; fixtures are temp roots:

1. `test_verify_writes_receipt_with_hashes_not_output` — fixture root with a `Makefile` whose `test:` target runs `printf "MARKER-OUTPUT\n"`; run `verify --root . --task 1 --receipts r.jsonl`: exit 0; `r.jsonl` has exactly 1 line; the line does **not** contain `MARKER-OUTPUT`; its `stdout_sha256` equals the SHA-256 of the `stdout` from a direct `run_verification` call on the discovered make-test command; `command_id == "make-test"`.
2. `test_receipt_chain_links` — fixture root with `package.json` `{"scripts": {"test": "true"}}` and a `Makefile` `test:` target of `true`; `verify` runs both (npm-test, then make-test): 2 receipts; recomputing the chain by hand from the two lines' fields matches both stored `chain_sha256` values.
3. `test_check_receipts_pass` — reuse the case-2 fixture/file: `check-receipts --task 1` exits 0 with `RECEIPTS: PASS task 1: 2 receipts, chain valid`.
4. `test_check_receipts_no_receipts_for_task` — same file: `check-receipts --task 99` exits 1 with `RECEIPTS: FAIL task 99: no receipts`.
5. `test_check_receipts_failed_receipt_fails` — fixture with `Makefile` `test:` target `false`: `verify` exits 1 (one FAIL receipt); `check-receipts --task 1` exits 1 with `RECEIPTS: FAIL task 1: receipt failed: make-test`.
6. `test_check_receipts_detects_tampered_field` — from a valid 2-receipt file, change one hex char of line 1's `stdout_sha256`: `check-receipts` exits 1 with `RECEIPTS: chain broken at line 1`.
7. `test_check_receipts_detects_deleted_line` — from a valid 3-receipt file (three tasks verified into one file, one passing command each), delete line 2: `check-receipts` exits 1 with `RECEIPTS: chain broken at line 2`.
8. `test_check_receipts_corrupt_line` — append the line `not json` to a valid file: `check-receipts` exits 1 with `RECEIPTS: corrupt at line <n>` where `<n>` is the appended line's number.
9. `test_check_receipts_scoped_per_task` — one file holding a passing receipt for task `A` and a failing receipt for task `B` (chain valid): `check-receipts --task A` exits 0; `--task B` exits 1 naming B's failed command.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s scripts/tests -p 'test_receipts.py' -v`
Expected: FAIL — `verify` writes no receipts file / `check-receipts` is not a recognized subcommand.

- [ ] **Step 3: Implement receipts in `scripts/mechanical_verify.py`**

Add `append_receipt`, the chain computation, the `on_result` wiring in the `verify` handler, and the `check-receipts` subcommand, per Interfaces. Additional stdlib: `fcntl`, `hashlib`, `datetime`.

- [ ] **Step 4: Run the full Python suite**

Run: `python3 -m unittest discover -s scripts/tests -v`
Expected: `Ran 26 tests ... OK` (17 from Task 1 + 9 here).

- [ ] **Step 5: Smoke the reviewer-side flow end-to-end**

Run:
```bash
cd /tmp && rm -rf rcptsmoke && mkdir rcptsmoke && cd rcptsmoke
printf 'test:\n\tfalse\n' > Makefile
python3 ~/workspace/worktrees/aep-deepcode-impl/scripts/mechanical_verify.py verify --root . --task smoke --receipts r.jsonl; echo "verify rc=$?"
python3 ~/workspace/worktrees/aep-deepcode-impl/scripts/mechanical_verify.py check-receipts --receipts r.jsonl --task smoke; echo "check rc=$?"
printf 'test:\n\ttrue\n' > Makefile
python3 ~/workspace/worktrees/aep-deepcode-impl/scripts/mechanical_verify.py verify --root . --task smoke2 --receipts r.jsonl; echo "verify2 rc=$?"
python3 ~/workspace/worktrees/aep-deepcode-impl/scripts/mechanical_verify.py check-receipts --receipts r.jsonl --task smoke2; echo "check2 rc=$?"
```
Expected: `VERIFY: make-test FAIL ...`, `verify rc=1`; `RECEIPTS: FAIL task smoke: receipt failed: make-test`, `check rc=1`; then `verify2 rc=0`; `check2 rc=0` with the PASS line (the chain validates across both tasks' receipts in one file). This is the negative control: the evidence flow *vetoes* a failing task, not just records it.

- [ ] **Step 6: Commit**

```bash
git add scripts/mechanical_verify.py scripts/tests/test_receipts.py
git commit -m "feat(evidence): verification receipts with hash chain and validation"
```

---

### Task 3: Wire controller-run receipts into the SDD skill — live copy AND repo copy

**Files:**
- Modify: `~/workspace/custom-skills/subagent-driven-development/SKILL.md` (live copy — the file the runtime loads; not in git, edited in place)
- Modify: `skills/subagent-driven-development/SKILL.md` (repo copy — a *different, condensed* document; edited against its own text)

**Interfaces:**
- Consumes: Task 1/2 CLI contracts (`verify` exit codes 0/1/2/3, `check-receipts` exit codes and lines).
- Produces: the call site — every SDD task completion in an AEP-driven run requires controller-produced mechanical evidence. The two files get **equivalent, not identical** text (their surrounding documents differ); each insertion is pinned against its own file below.

- [ ] **Step 1: Write the failing checks (both copies)**

Run: `grep -o "mechanical_verify.py" ~/workspace/custom-skills/subagent-driven-development/SKILL.md | wc -l; grep -o "mechanical_verify.py" ~/workspace/worktrees/aep-deepcode-impl/skills/subagent-driven-development/SKILL.md | wc -l`
Expected: `0` and `0` (receipts not wired yet in either copy).

- [ ] **Step 2: Edit the LIVE copy**

In `~/workspace/custom-skills/subagent-driven-development/SKILL.md`, section `### 5. Complete the task`, insert the following paragraph immediately **after** the two completion-line bullets (``- `Task <N>: complete (commits <base7>..<head7>, review clean)` `` and the `<K> parked` bullet) and **before** the line `Then mark the todo complete and move on.`:

```markdown
Completion also requires mechanical evidence (AEP verification receipts). Before appending the completion line, the controller — never the implementer — runs the task's verification itself: `python3 <AEP checkout>/scripts/mechanical_verify.py verify --root <task worktree> --task <N> --receipts <workspace>/receipts.jsonl`, and requires exit 0. If a fresh run is impractical, the controller may instead validate receipts it generated earlier in this run: `python3 <AEP checkout>/scripts/mechanical_verify.py check-receipts --receipts <workspace>/receipts.jsonl --task <N>`, exit 0 required. A receipts file the implementer produced is an audit artifact, not evidence — receipts count only when the controlling side ran the verifier or chain-validated its own receipts. Exit 2 from `verify` means the tree has no discoverable verification commands: append `mechanical evidence: none available` next to the completion line in the ledger, so the completion visibly rests on review alone.
```

- [ ] **Step 3: Edit the REPO copy**

In `skills/subagent-driven-development/SKILL.md` (repo copy), immediately after the existing bullet `- Mark the task complete in the ledger only when the review is clean or every open finding is parked with a ruling.` (line 49 at plan time — re-derive by grep, do not trust the number), insert this bullet verbatim:

```markdown
- Completion also requires mechanical evidence (AEP verification receipts). Before writing the `Task <N>: complete` line, the controller — never the implementer — runs `python3 <AEP checkout>/scripts/mechanical_verify.py verify --root <task worktree> --task <N> --receipts <workspace>/receipts.jsonl` and requires exit 0, or validates receipts it generated earlier in this run with `python3 <AEP checkout>/scripts/mechanical_verify.py check-receipts --receipts <workspace>/receipts.jsonl --task <N>` (exit 0 required). An implementer-produced receipts file is an audit artifact, not evidence. Exit 2 from `verify` (no discoverable commands) must be recorded next to the completion line as `mechanical evidence: none available`.
```

- [ ] **Step 4: Verify both wirings and lint both files**

Run: `grep -o "mechanical_verify.py" ~/workspace/custom-skills/subagent-driven-development/SKILL.md | wc -l; grep -o "mechanical_verify.py" skills/subagent-driven-development/SKILL.md | wc -l; npx --yes markdownlint-cli2 "$HOME/workspace/custom-skills/subagent-driven-development/SKILL.md"` — run from the worktree; the live file is linted with the same config by passing its path (if the repo config does not resolve outside the tree, lint it from `~/workspace/custom-skills/` with the repo's `.markdownlint.yaml` copied semantics — concretely: `cd ~/workspace/custom-skills && npx --yes markdownlint-cli2 --config ~/workspace/worktrees/aep-deepcode-impl/.markdownlint.yaml "subagent-driven-development/SKILL.md"`); plus the repo copy under the normal docs-lint glob in Task 9.
Expected: `2` and `2` (one `verify`, one `check-receipts` per copy), markdownlint exits 0 on both.

- [ ] **Step 5: Commit (repo copy only)**

The live copy is not in git — its edit is already effective and there is nothing to commit for it; do not invent a mirror step.

```bash
git add skills/subagent-driven-development/SKILL.md
git commit -m "feat(evidence): require controller-run verification receipts for SDD completion"
```

---

### Task 4: Lane coordinator — the launcher: claim, release, status with manifest and launcher-held fence

**Files:**
- Create: `scripts/lane-coord.sh`

**Interfaces:**
- Consumes: nothing. (Task 5 adds the policy-data load, the declared-path check, and env sanitization to `claim`.)
- Produces:
  - State layout: `LANES_DIR=${AEP_LANES_DIR:-$HOME/workspace/worktrees/.lanes}`, `WT_ROOT=${AEP_WORKTREES_ROOT:-$HOME/workspace/worktrees}`. Per lane `<name>`: manifest `$LANES_DIR/<name>.json`, fence file `$LANES_DIR/<name>.fence`, history log `$LANES_DIR/<name>.log` (append-only, one line per event: `<ISO-8601 UTC> <event> epoch=<n> worker=<id>`).
  - Lane name: `<project>-<lane>`; `project` and `lane` must match `^[a-z0-9][a-z0-9-]*$`, `worker` must match `^[A-Za-z0-9_.-]+$`, branch must pass `git check-ref-format --branch`; violations exit 2. Worktree path is deterministic: `$WT_ROOT/<name>`.
  - Manifest JSON, exact fields: `{"version": 1, "name": str, "repo": <abs path>, "path": <abs path>, "branch": str, "base": <full SHA the worktree was cut from>, "worker": str, "launcher_pid": int, "epoch": int, "state": "claimed"|"released"|"reaped"|"cleaned", "claimed_at": <ISO-8601 UTC>, "updated_at": <ISO-8601 UTC>}`. `launcher_pid` is the lane-coord process that ran the claim — **operator information only; operational code signals no process, ever; only the `--self-test` harness signals processes it spawned itself**. Written with `printf` from validated fields (the charsets above make this sound); read back with `python3 -c` JSON parsing (scan-gate precedent — never `grep` JSON).
  - `lane-coord.sh claim --repo <abs path> --project <slug> --lane <slug> --branch <name> [--base <ref, default origin/main>] --worker <id> [--capacity <n>] [--path <extra> ...] --exec <command...>`
    - **`--exec` is required.** The fence is an `flock` held on an open fd **by the lane-coord process itself** for its whole lifetime; a claim that returns immediately holds nothing. Missing `--exec` → print the usage line `usage: lane-coord.sh claim ... --exec <command...> (the launcher must stay alive for the lane's lifetime — it holds the fence)` and exit 2. Everything after `--exec` is the worker command, not parsed further.
    - Capacity: `--capacity` flag > `$AEP_LANE_CAPACITY` > default **2** (DeepCode's verified default, `core/application/execution_coordinator.py:101` — an operational value, configurable, not a correctness property; `status` prints the pool against it). Capacity counts manifests in `$LANES_DIR` with `state == "claimed"` **after** the auto-settle pass below, across all repos (one global pool, as in DeepCode).
    - The claim transaction runs under one exclusive `flock` on `$LANES_DIR/.capacity.lock` acquired with `flock -w 60`; on timeout print `LANE: lock timeout after 60s waiting for the capacity lock` and exit **5**. Inside the transaction, in order:
      1. **Auto-settle stale claims (Risk R5):** for every manifest with `state == "claimed"` (any lane, including this one), probe its fence with a short-lived `flock -n <fence> true`: if the probe **succeeds**, that claim's launcher is dead — set its manifest `state: "reaped"`, append history event `settled-interrupted`, and do not count it toward capacity. (A post-reboot VM has no live launchers at all, so all stale claims settle on the first claim instead of wedging the pool.)
      2. **Acquire this lane's fence on the launcher's own fd:** open the fence file on fd 8 and `flock -n 8`. If it fails, a live launcher holds this lane: read the existing manifest if present and print `LANE: busy <name> held by worker <worker> epoch <n>` (or `LANE: busy <name> (fence held)` if no manifest parses), exit **3**.
      3. **Post-acquisition fence verification (judge's ruling):** probe the fence with a separate short-lived `flock -n <fence> true`; it **must fail**. If it succeeds, the fence is not actually held — print `LANE: fence verification failed for <name>`, exit 1, write nothing. A claim must never record a fence it does not hold.
      4. **Takeover bookkeeping:** if a manifest for this lane exists (any state), the new claim's epoch is `previous epoch + 1` (monotonic per lane, survives every settlement — DeepCode's claim epoch); if the previous state was `claimed` (its launcher died — step 1 just settled it), print before the claimed line: `LANE: note previous claim on <name> settled interrupted at epoch <n>`, and leave the worktree content exactly as it lies (the new lane inspects it; nothing is replayed or reset).
      5. **Capacity check:** if the post-settle claimed count ≥ capacity, print `LANE: capacity reached (<capacity> active lanes)`, exit **4**.
      6. **Write the manifest** (`state: "claimed"`, `launcher_pid` = this process's PID, temp file + `mv` inside the lock — no torn manifests) and append history event `claimed`. Release the capacity lock.
    - Worktree setup (**after** the capacity lock is released — Risk R13): if `$WT_ROOT/<name>` does not exist, create it: resolve `<base>` to a full SHA, then `git -C <repo> worktree add -b <branch> <path> <base-sha>`, recording the SHA. If `<branch>` already exists in the repo but no worktree is registered for it, refuse: `LANE: refuse <name>: branch <branch> already exists without a registered worktree`, exit 1. If the path exists: adopt it **only** if `git -C <repo> worktree list --porcelain` registers that exact path for this repo **and** the branch checked out there equals `--branch`; otherwise print `LANE: refuse <name>: path exists but is not this lane's registered worktree`, exit 1 — never guess, never delete. On any setup failure after the manifest was written: set the manifest `state: "released"`, append history event `setup-failed`, exit 1.
    - Worker spawn: print `LANE: claimed <name> path=<path> branch=<branch> epoch=<n>`; run the worker command as a **child process** with working directory `<path>` (the launcher does not `exec` — it must survive to do the release bookkeeping), and wait for it. The capacity lock and the claim transaction are long over; the fence fd stays open in the launcher throughout.
    - Worker exit: set manifest `state: "released"`, append history event `released`, print `LANE: released <name> (worker exit <code>)`, and exit with the worker's wait status. If the launcher itself is killed, the fence drops with the launcher process (its fd closes; the worker is spawned with the fence fd closed, so no descendant can hold it open) — that, and only that, is what makes a later takeover provable.
  - `lane-coord.sh release --name <name>` — standalone bookkeeping for a lane whose launcher already exited without completing its bookkeeping. If no manifest: `LANE: refuse release <name>: no manifest`, exit 1. If the fence probes held: `LANE: refuse release <name>: fence held (launcher alive)`, exit 1. If `state != "claimed"`: `LANE: refuse release <name>: state is <state>`, exit 1. Otherwise set `state: "released"`, append history, print `LANE: released <name>`. (Task 6 adds `--clean`.)
  - `lane-coord.sh status [--name <name>]` — one line per manifest (or the named one; no manifest → `LANE: no manifest for <name>`, exit 1): `<name> state=<s> epoch=<n> worker=<w> fence=<held|free> path=<p>` (fence state probed live, never inferred from `launcher_pid`). When listing all, a final summary line: `LANE: pool: <claimed-count> claimed of <capacity>`.
  - `--self-test` with the boot-gate idiom: per-case `SELF-TEST: <case> ok` lines, a final summary line `SELF-TEST: all ok`, non-zero exit on any failure. All `kill` usage in this file is confined to the `self_test` function (the boot-gate layout: one function, defined after the operational code); operational code paths contain no `kill`.
  - **CLI grammar pinned (Feasibility P2-4):** all flags follow the subcommand; global configuration is environment-only. Tests use only this form. Unknown subcommand or missing required flag → usage to stderr, exit 2.

- [ ] **Step 1: Write the failing self-test**

Self-test sets `AEP_LANES_DIR` and `AEP_WORKTREES_ROOT` to a `mktemp -d` tree, builds a fixture repo (`git init`, one commit using `git -c user.name=LaneTest -c user.email=lane@test.invalid`), and **passes `--base HEAD` on every claim** (the fixture has no `origin` remote, so the documented `origin/main` default cannot resolve in it — Feasibility P2-8 / Risk R17). Background claims are launched with a `wait_for_manifest` helper polling up to 5 s for the manifest to appear, use short `sleep` durations, and are reaped by an EXIT trap that kills only the test's own background PIDs. Write cases 1–6 now (Task 5 adds 7–12; Task 6 adds 13–19):

1. `claim-runs-worker-in-worktree` — claim `--exec sh -c "pwd > $FIX/pwd.out"` succeeds (exit 0); the worktree dir exists; `git -C <path> branch --show-current` equals the claimed branch; `$FIX/pwd.out` content equals the worktree path (worker ran with the worktree as cwd); manifest parses with `epoch: 1`, `base` equal to the fixture repo's HEAD SHA, and (after completion) `state: "released"`; stdout contains the `LANE: claimed` line and the `LANE: released <name> (worker exit 0)` line; history log has `claimed` and `released` events.
2. `second-claim-same-name-busy` — background claim with `--exec sleep 10`; a second claim of the same name exits 3 with the `LANE: busy` line naming the first worker and epoch 1.
3. `release-frees-fence` — claim `--exec true` completes; a fresh claim of the same name succeeds with `epoch: 2` (epoch survives release).
4. `stale-claim-auto-settles` — background claim lane A with `--exec sleep 30`; the test kills A's **launcher PID** (the lane-coord process it spawned — simulating launcher death; the tool itself never kills); A's manifest stays `claimed`; a claim for lane B with `--capacity 1` then **succeeds** (exit 0) and A's manifest reads `state: "reaped"` with a `settled-interrupted` history event. Pinning assertion: at the moment lane B's claim succeeds, A's `sleep 30` worker process is **still alive** (checked with `kill -0` in the test) — proving the fence died with the launcher, not with the worker.
5. `capacity-blocks-second-lane` — background claim lane A (`--exec sleep 10`); claiming a *different* lane name with `--capacity 1` exits 4 with the `LANE: capacity reached (1 active lanes)` line.
6. `parallel-claim-race` — two concurrent claims for the same new name, both `--exec sleep 5`: exactly one eventually exits 0, the other exits 3.

Run: `bash scripts/lane-coord.sh --self-test`
Expected at this step: FAIL — file does not exist.

- [ ] **Step 2: Implement claim/release/status**

Follow `boot-gate.sh` conventions: `set -euo pipefail`, a header comment stating the contract (including the operational no-`kill` invariant and the `--exec` lifetime rule), and the PATH append block copied from `boot-gate.sh` lines 17–21 (comment + `export PATH=...`). Use an fd-based `flock` for the capacity lock (`exec 9>"$LANES_DIR/.capacity.lock"; flock -w 60 9`) and fd 8 for the fence. Manifest writes go to a temp file + `mv` inside the lock. JSON reads via `python3 -c` one-liners. Spawn the worker with the fence and capacity fds closed — `"${worker_cmd[@]}" 8>&- 9>&-` (or the equivalent in whatever spawn form is used). Bash children inherit open fds; an inherited fence fd would keep the fence held after the launcher's death and void takeover. This is what makes the port match `FileLease` semantics (Python fds are non-inheritable by default).

- [ ] **Step 3: Run the self-test**

Run: `bash scripts/lane-coord.sh --self-test`
Expected: 6 `SELF-TEST: <case> ok` lines (cases 1–6), then `SELF-TEST: all ok`, exit 0.

- [ ] **Step 4: Lint**

Run: `shellcheck scripts/lane-coord.sh && test -z "$(shfmt -d -i 2 scripts/lane-coord.sh)" && echo LINT-OK`
Expected: `LINT-OK`; if `shellcheck` or `shfmt` is absent locally (both are absent on this VM), note which and rely on the CI shell-lint job — do not install unverified binaries.

- [ ] **Step 5: Commit**

```bash
git add scripts/lane-coord.sh
git commit -m "feat(lanes): lane coordinator — launcher-held fences, capacity, manifests"
```

---

### Task 5: Launch-point controls — policy data, declared-path check, env sanitization

**Files:**
- Create: `scripts/policy.data`
- Modify: `scripts/lane-coord.sh` (policy load at claim; declared-path check; env scrub for the worker)

**Interfaces:**
- Consumes: Task 4's claim flow (the check slots in after the capacity transaction, before worktree setup; the scrub applies at worker spawn).
- Produces:
  - `scripts/policy.data` — the launch policy **data** (the script holds no pattern list). Exact grammar (pinned, Feasibility P2-1 applied to what survives): section headers `[sensitive-paths]` and `[env-scrub]`; one pattern/fragment per line; `#` comments and blank lines ignored; **anything else — unknown section, pattern before any section, empty pattern — is a validation error.** The loader (an embedded `python3` snippet, scan-gate precedent) validates on every claim: a malformed file refuses the claim before anything is created — `LANE: refuse policy data invalid: line <n>: <line>`, exit 1.
  - File location: sibling of the script (`$(dirname "${BASH_SOURCE[0]}")/policy.data`); override `AEP_POLICY_DATA` exists for tests. **There is no other policy state: no snapshot, no freeze, no mode.**
  - `[sensitive-paths]` content — DeepCode's 25 patterns in source order, minus `*/.deepcode/credentials*` and `*/deepcode_config.json`, plus the `gh` pair appended (25 total, exact):
    `*/.ssh`, `*/.ssh/*`, `*/.aws`, `*/.aws/*`, `*/.config/gcloud`, `*/.config/gcloud/*`, `*/.azure`, `*/.azure/*`, `*/.gnupg`, `*/.gnupg/*`, `*/.docker/config.json`, `*/.kube/config`, `*/.netrc`, `*/.npmrc`, `*/.pypirc`, `*/.git-credentials`, `*/secrets.json`, `*/.env`, `*/.env.*`, `*.pem`, `*.key`, `*id_rsa*`, `*id_ed25519*`, `*/.config/gh`, `*/.config/gh/*`.
    (`*/secrets.json` is present — v1 dropped it silently; Feasibility P2-2. It is pinned by self-test case 9.)
  - `[env-scrub]` content — DeepCode's pattern alternatives as fragments (exact): `KEY`, `PASSWORD`, `SECRET`, `TOKEN`, `CREDENTIAL`, `AUTH`.
  - **Declared-path check:** the lane's declared working set = the deterministic worktree path + every `--path <extra>`. Before worktree setup, each path is canonicalized with `python3` `os.path.realpath` (symlinks resolved — a declared symlink into a sensitive directory is the sensitive directory) and matched against `[sensitive-paths]` with `fnmatch.fnmatchcase` (`*` spans `/`, DeepCode's semantics). Any match: print `LANE: refuse <name>: declared path <canonical> matches sensitive pattern <pattern>`, set the manifest `state: "released"` with history event `claim-refused` (the claim transaction already wrote it), exit 1 — no worktree created, no worker spawned. Declared `--path` values must exist at claim time (canonicalizing a nonexistent path's parent chain is guesswork; refuse nonexistent extras with `LANE: refuse <name>: declared path <path> does not exist`, exit 1).
  - **Env sanitization at worker spawn (DeepCode `env_sanitize.py`, adapted to bash):** the worker child — and only the child; the launcher keeps its own environment for its bookkeeping — runs with every variable removed whose **name** contains any `[env-scrub]` fragment as a case-insensitive substring, with the `AUTH` fragment boundary-exempted exactly where DeepCode's lookarounds exempt it: a name is **not** scrubbed for its `AUTH` occurrence when that occurrence is immediately preceded by `SSH_` (spares `SSH_AUTH_SOCK`) or immediately followed by `OR` + (`_` or end-of-name) (spares `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, any `...AUTHOR...`/`...AUTHOR` identity name). `AUTHORITY` is **not** exempt (its `AUTH` is followed by `ORI…`) and **is** scrubbed when it carries no other fragment — pinned by case 10 (Feasibility P3-4: v1's broad `AUTHOR` exemption was wider than DeepCode's; do not reintroduce it, and do not claim equivalence beyond the pinned cases). Other fragments have no exemptions. `PATH`, `HOME`, locale, and proxy variables survive (they match no fragment). Opt-out: `AEP_LANE_FULL_ENV=1` disables the scrub entirely and prints to stderr, on every launch: `LANE: warning AEP_LANE_FULL_ENV=1: worker receives the full environment (credential scrub disabled)` (Risk R14 — the opt-out is loud, never silent). Mirrors `DEEPCODE_BASH_FULL_ENV=1`; there is no partial opt-in in v1.
  - Scrub implementation: iterate `compgen -e` in a subshell wrapping the worker spawn, `unset` the selected names there, then run the worker. Selection logic lives in one bash function `name_is_sensitive <name>` implementing the fragment + AUTH-boundary rules above, shared by the spawn path and nothing else.

`scripts/policy.data` ships with exactly this content:

```
# AEP launch policy data — read by scripts/lane-coord.sh at claim time;
# integrity-verified by scripts/boot-gate.sh against the committed version.
# Grammar: [section] headers, one pattern per line, '#' comments, blank
# lines ignored; anything else is a load-time validation error.
# Change policy by editing this file through git/PR — the committed
# history is the audit trail. There is no other policy state.
[sensitive-paths]
*/.ssh
*/.ssh/*
*/.aws
*/.aws/*
*/.config/gcloud
*/.config/gcloud/*
*/.azure
*/.azure/*
*/.gnupg
*/.gnupg/*
*/.docker/config.json
*/.kube/config
*/.netrc
*/.npmrc
*/.pypirc
*/.git-credentials
*/secrets.json
*/.env
*/.env.*
*.pem
*.key
*id_rsa*
*id_ed25519*
*/.config/gh
*/.config/gh/*
[env-scrub]
KEY
PASSWORD
SECRET
TOKEN
CREDENTIAL
AUTH
```

- [ ] **Step 1: Extend the self-test first (cases 7–10, 12)**

Add to `lane-coord.sh --self-test`, run, and watch the new cases fail. The self-test creates fixture credential dirs under its `mktemp -d` tree (a fake `$FIX/home/.aws` etc. — never the real `$HOME`; case 7 is the single exception: it canonicalizes the real `$HOME/.ssh` read-only — the path must exist for the declared-path check — and creates nothing):

7. `working-set-refuses-sensitive-dir` — claim with `--path "$HOME/.ssh"` → exit 1, line matches `LANE: refuse <name>: declared path */.ssh matches sensitive pattern */.ssh` (canonical path ends in `/.ssh`), and the worktree path was **not** created.
8. `working-set-refuses-symlink-into-sensitive` — fixture symlink `$FIX/link-aws` → `$FIX/home/.aws` (a real dir in the fixture): claim with `--path "$FIX/link-aws"` → exit 1, refusal names the **canonical** path (`$FIX/home/.aws`) and pattern `*/.aws`.
9. `working-set-refuses-secrets-file` — fixture file `$FIX/secrets.json`: claim with `--path "$FIX/secrets.json"` → exit 1, refusal names pattern `*/secrets.json`.
10. `exec-scrubs-credential-env` — with `AEP_TEST_API_KEY=not-a-real-secret`, `AEP_TEST_AUTHORITY=not-a-real-secret`, `SSH_AUTH_SOCK=/tmp/fake.sock`, and `GIT_AUTHOR_NAME=Lane Test` exported in the test shell, claim `--exec sh -c 'printf "%s|%s|%s|%s" "${AEP_TEST_API_KEY:-unset}" "${SSH_AUTH_SOCK:-unset}" "${GIT_AUTHOR_NAME:-unset}" "${AEP_TEST_AUTHORITY:-unset}"'` prints exactly `unset|/tmp/fake.sock|Lane Test|unset` in the worker's output.
12. `policy-data-malformed-refuses` — `AEP_POLICY_DATA` pointed at a fixture file whose line 3 is `bogus line here` (after a comment and the `[sensitive-paths]` header): claim → exit 1 with `LANE: refuse policy data invalid: line 3: bogus line here`; nothing created.

Run: `bash scripts/lane-coord.sh --self-test`
Expected at this step: the 5 new cases FAIL; cases 1–6 still pass.

- [ ] **Step 2: Create `scripts/policy.data` and implement the load, check, and scrub**

Per Interfaces. The loader emits the two lists (e.g. as newline-joined strings the check/scrub functions consume); validation happens once per claim, before the capacity transaction's manifest write is relied on — concretely: load and validate first thing in `claim`, so a malformed file refuses before any state changes.

- [ ] **Step 3: Add the full-env opt-out self-test case (11) and run the suite**

11. `full-env-opt-out-warns` — case 10's setup plus `AEP_LANE_FULL_ENV=1`: the worker prints `not-a-real-secret` in the first field (the value is visible, proving the opt-out is deliberate and total), and the claim's stderr contains the `LANE: warning AEP_LANE_FULL_ENV=1` line.

Run: `bash scripts/lane-coord.sh --self-test`
Expected: 12 `SELF-TEST: <case> ok` lines (cases 1–12), then `SELF-TEST: all ok`, exit 0.

- [ ] **Step 4: Lint**

Run: `shellcheck scripts/lane-coord.sh && test -z "$(shfmt -d -i 2 scripts/lane-coord.sh)" && echo LINT-OK`
Expected: `LINT-OK` (or the noted local absence from Task 4).

- [ ] **Step 5: Commit**

```bash
git add scripts/policy.data scripts/lane-coord.sh
git commit -m "feat(lanes): launch-point controls — policy data, declared-path check, env scrub"
```

---

### Task 6: Lane takeover, reap, and validated cleanup

**Files:**
- Modify: `scripts/lane-coord.sh` (takeover note in `claim` is Task 4's step 4 — here: `reap`, `release --clean`)

**Interfaces:**
- Consumes: Task 4's manifest schema, fence semantics, exit codes; Task 5's refusal conventions.
- Produces:
  - `lane-coord.sh reap --name <name>` — settles a claim whose launcher is gone. If the fence probes **held**: print `LANE: reap refused <name>: fence held (launcher alive)`, exit 1. If no manifest: `LANE: refuse reap <name>: no manifest`, exit 1. If `state != "claimed"`: `LANE: refuse reap <name>: state is <state>`, exit 1. Otherwise set `state: "reaped"`, append history events `settled-interrupted` and `reaped`, print `LANE: reaped <name> (claim settled interrupted at epoch <n>)`, exit 0. **Reap signals nothing** — a manifest naming a live innocent PID in `launcher_pid` is settled as bookkeeping while that process runs on untouched (pinned by case 16).
  - `lane-coord.sh release --name <name> --clean [--force-dirty]` — Task 4's `release` preconditions (manifest exists, fence free, state `claimed` or — for an already-released lane whose worktree remains — `released`), plus worktree removal **only after all four ownership signals validate** (DeepCode's cleanup rule): (1) manifest exists and its `repo`/`path`/`branch` name this lane; (2) `git -C <repo> worktree list --porcelain` registers the path; (3) the branch checked out at the path equals the manifest branch; (4) the path is exactly `$WT_ROOT/<name>` (the deterministic managed location). Any mismatch: print `LANE: refuse clean <name>: <which signal failed>`, exit 1, remove nothing. Then: if `git -C <path> status --porcelain` is non-empty and `--force-dirty` was not given, print `LANE: refuse clean <name>: worktree dirty (use --force-dirty)`, exit 1. With `--force-dirty`, **first** archive the work (Risk R16): write `git -C <path> status --porcelain` output followed by `git -C <path> diff HEAD` into `$LANES_DIR/<name>.final-diff.patch`, then remove with `git -C <repo> worktree remove --force <path>` (without the flag, plain `worktree remove` after the clean check). Set `state: "cleaned"`, append history, print `LANE: cleaned <name>`.
  - Takeover is Task 4's claim step 4 (settle-interrupted note + epoch increment + worktree left as it lies) — this task's case 13 pins it end-to-end.

- [ ] **Step 1: Extend the self-test first (cases 13–19)**

Add to `--self-test`, run, watch them fail:

13. `takeover-after-launcher-death` — background claim (`--exec sleep 30`); the test kills the launcher PID; claim the same name again (`--exec true`) → exit 0, stdout contains `LANE: note previous claim on <name> settled interrupted at epoch 1`, new manifest `epoch: 2`.
14. `reap-refuses-live-fence` — background claim; `reap` → exit 1 with the `fence held (launcher alive)` line; the manifest stays `claimed`.
15. `reap-settles-dead-claim` — background claim; kill the launcher; `reap` → exit 0 with the `LANE: reaped` line; manifest `state: "reaped"`; a subsequent claim succeeds.
16. `reap-never-signals` — start an innocent `sleep 60` in the test; hand-write a manifest for a fresh lane name with `launcher_pid` = that sleep's PID, `state: "claimed"`, and no live fence; `reap` → exit 0; afterwards `kill -0 <sleep pid>` still succeeds (the process was never signaled — the assertion is on the process, run by the *test*, not the tool).
17. `clean-refuses-dirty` — claim `--exec true` completes; create an untracked file in the worktree; `release --clean` → exit 1 `worktree dirty`, worktree still on disk.
18. `clean-force-dirty-archives-and-removes` — continuing a dirty lane: `release --clean --force-dirty` → exit 0, path gone, `git worktree list` no longer shows it, manifest `state: "cleaned"`, and `$LANES_DIR/<name>.final-diff.patch` exists and contains the untracked file's name (from the archived porcelain status).
19. `clean-refuses-foreign-path` — hand-write a manifest whose `repo` names a *different* fixture repo while the path holds the first repo's worktree: `release --clean` → exit 1 naming the failed signal, directory intact, nothing removed.

Run: `bash scripts/lane-coord.sh --self-test`
Expected at this step: the 7 new cases FAIL; the 12 from Tasks 4–5 pass.

- [ ] **Step 2: Implement reap and validated cleanup**

Per Interfaces. Signal-check order in `release --clean` is exactly 1→4 as listed, and the refusal names the first failing signal.

- [ ] **Step 3: Run the self-test**

Run: `bash scripts/lane-coord.sh --self-test`
Expected: 19 `SELF-TEST: <case> ok` lines, then `SELF-TEST: all ok`, exit 0.

- [ ] **Step 4: Lint**

Run: `shellcheck scripts/lane-coord.sh && test -z "$(shfmt -d -i 2 scripts/lane-coord.sh)" && echo LINT-OK`
Expected: `LINT-OK` (or the noted local absence from Task 4).

- [ ] **Step 5: Commit**

```bash
git add scripts/lane-coord.sh
git commit -m "feat(lanes): takeover settlement, reap, validated cleanup"
```

---

### Task 7: Boot-gate policy integrity check — committed data is the policy

**Files:**
- Modify: `scripts/boot-gate.sh` (add `check_policy` + two self-test cases)

**Interfaces:**
- Consumes: Task 5's `scripts/policy.data` (committed in Task 5, so `HEAD:scripts/policy.data` exists on this branch).
- Produces:
  - A fifth check, run last, after `check_gh_auth`. It is **read-only**: it creates nothing, copies nothing, freezes nothing (contrast v1's freeze — deleted, see Non-Goals).
    ```bash
    check_policy() {
      local gate_dir policy ref_sha work_sha
      gate_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
      policy="${AEP_POLICY_DATA:-$gate_dir/policy.data}"
      if [ ! -f "$policy" ]; then
        echo "BOOT-GATE: policy SKIP: no policy data at $policy (launch-policy integrity inactive)"
        return 0
      fi
      ref_sha=$(git -C "$gate_dir" show HEAD:scripts/policy.data 2>/dev/null | sha256sum | cut -d' ' -f1)
      [ -n "$ref_sha" ] || fail policy "cannot read committed scripts/policy.data via git"
      work_sha=$(sha256sum "$policy" | cut -d' ' -f1)
      [ "$work_sha" = "$ref_sha" ] ||
        fail policy "policy.data differs from the committed version (unreviewed edit?) — policy changes land via git/PR"
      ok policy
    }
    ```
    Behavior contract: absent policy file → the named **SKIP** line above, loudly printed, and the gate proceeds (boot-gate has no prior SKIP convention — verified against the current script, whose contract is `BOOT-GATE: <name> ok` / `BOOT-GATE: <name> FAIL: <reason>`; the SKIP line follows that naming shape and never prints `ok` for a check that did not run; a SKIP means "mechanism not installed here", not "passed"). Present but different from the committed blob → FAIL (an unreviewed edit is never ratified by running the gate — Risk R7). Present and identical → `BOOT-GATE: policy ok`. If git cannot produce the committed blob → FAIL with the stated reason (fail closed).
  - **Scope statement (binding for this task's code comments, commit message, and Task 9's doc):** this wires the check into `boot-gate.sh` only. Whether and when anything invokes `boot-gate.sh` is issue #17's unexecuted scope; nothing here claims cron enforcement.

- [ ] **Step 1: Extend the boot-gate self-test first (cases `policy-mismatch`, `policy-skip`)**

Add two cases to `boot-gate.sh --self-test`, run, watch them fail. Both run the gate **without** the stubdir on PATH (so the real `neurostrata-mcp` and `gh` serve the first four checks and the run reaches `policy`), and both **assert on captured output, not exit code alone** (Feasibility P2-6 — an exit-code-only assertion passes vacuously when an earlier check fails):

- `policy-mismatch` — write a temp file containing the shipped `policy.data` plus one extra pattern line; run `AEP_POLICY_DATA=<temp> bash "$gate"`, capture output and exit code: expect non-zero exit **and** output contains `BOOT-GATE: policy FAIL:`. If the run fails at an earlier check on an unhealthy machine, this case reports FAIL loudly rather than `ok` — that is intended (the suite is local-only; CI has no daemon).
- `policy-skip` — run `AEP_POLICY_DATA=<a nonexistent temp path> bash "$gate"`: expect exit 0 **and** output contains `BOOT-GATE: policy SKIP:`.

Run: `bash scripts/boot-gate.sh --self-test`
Expected at this step: the 2 new cases FAIL (`policy` check does not exist yet; the mismatch run exits 0 with four `ok` lines, the skip run prints no SKIP line).

- [ ] **Step 2: Implement `check_policy`**

Add the exact function from Interfaces and call it after `check_gh_auth` in the no-argument path. Update the header contract comment to list the fifth check and the SKIP line's meaning. Existing checks, order of the first four, and the `fail`/`ok` contract are otherwise unchanged. The `real-environment` self-test case is unaffected in shape — it exercises the full gate including the new check against the real committed `policy.data`, and (unlike v1's freeze design) mutates nothing.

- [ ] **Step 3: Run the boot-gate self-test**

Run: `bash scripts/boot-gate.sh --self-test`
Expected: 7 `SELF-TEST: ... ok` lines (the pre-existing daemon-down, zero-guards, missing-destructive-rule, gh-auth-fail, real-environment, plus `policy-mismatch` and `policy-skip`), then `SELF-TEST: all ok`, exit 0.

- [ ] **Step 4: Verify a normal run and the tamper behavior in the worktree**

Run: `bash scripts/boot-gate.sh; echo "rc=$?"` → expect `BOOT-GATE: policy ok` as the fifth line, `rc=0`.
Then: append one comment line to `scripts/policy.data`, re-run → expect exit 1 with `BOOT-GATE: policy FAIL:`; restore with `git checkout -- scripts/policy.data`.

- [ ] **Step 5: Lint**

Run: `shellcheck scripts/boot-gate.sh && test -z "$(shfmt -d -i 2 scripts/boot-gate.sh)" && echo LINT-OK`
Expected: `LINT-OK` (or the noted local absence from Task 4).

- [ ] **Step 6: Commit**

```bash
git add scripts/boot-gate.sh
git commit -m "feat(policy): boot-gate verifies committed policy data integrity"
```

---

### Task 8: Wire overnight-parallel-lanes through the coordinator — live copy AND repo copy

**Files:**
- Modify: `~/workspace/custom-skills/overnight-parallel-lanes/SKILL.md` (live copy — not in git, edited in place)
- Modify: `skills/overnight-parallel-lanes/SKILL.md` (repo copy — its step 2 is a longer, different text than the live one)

**Interfaces:**
- Consumes: Task 4–6 `lane-coord.sh` CLI contract and exit codes (3 busy, 4 capacity, 5 lock timeout).
- Produces: the call site — unattended lane runs launch through the coordinator, from the skill text the runtime actually reads (live) and the published copy (repo), each edited against its own current text.

- [ ] **Step 1: Write the failing checks (both copies)**

Run: `grep -o "lane-coord.sh" ~/workspace/custom-skills/overnight-parallel-lanes/SKILL.md | wc -l; grep -o "lane-coord.sh" ~/workspace/worktrees/aep-deepcode-impl/skills/overnight-parallel-lanes/SKILL.md | wc -l`
Expected: `0` and `0`.

- [ ] **Step 2: Edit the LIVE copy**

In `~/workspace/custom-skills/overnight-parallel-lanes/SKILL.md`, Run Setup step 2 currently reads (verified verbatim at plan time — re-derive by grep before editing): "**2. One lane, one worktree, one branch.** Cut every lane worktree from the same base commit. Verify each worktree's ignore/safety per `using-git-worktrees`. Never let parallel workers share a working copy."

Keep the bold lead and the closing sentence verbatim. Replace the two middle sentences with:

"Cut every lane worktree from the same base commit, through the lane coordinator — never by hand: from the AEP checkout, run `scripts/lane-coord.sh claim --repo <repo> --project <slug> --lane <lane-id> --branch <type/scope-name> --base <base-ref> --worker <agent-id> --exec <worker command>` and keep that launcher process alive for the lane's whole life — it holds the lane's fence, creates the worktree, scrubs credential-shaped variables from the worker's environment, and refuses the claim if any declared path (`--path <extra>`, repeatable) canonicalizes into a sensitive location. A non-zero claim exit (3 = workspace busy, 4 = capacity reached, 5 = lock timeout) means the lane does not start. Inspect lanes with `scripts/lane-coord.sh status`; if a lane's launcher has died, settle the claim with `scripts/lane-coord.sh reap --name <project>-<lane-id>` (or let the next claim auto-settle it) — never remove a worktree the coordinator did not create, and never signal a lane's processes by hand. Verify each worktree's ignore/safety per `using-git-worktrees`."

- [ ] **Step 3: Edit the REPO copy**

In `skills/overnight-parallel-lanes/SKILL.md` (repo copy), step 2 is the long form (verified at plan time): "**2. One lane, one worktree, one branch.** Cut every lane worktree from the same base commit. Before creating a worktree, confirm you are not already inside one: compare `git rev-parse --git-dir` against `git rev-parse --git-common-dir` — different paths (and no output from `git rev-parse --show-superproject-working-tree`, which would mean a submodule, not a worktree) means you are already isolated, so do not nest another. Verify each new worktree sits on its own branch, is clean at cut time, and that no two lanes share a working copy. Never let parallel workers share a working copy."

Replace **only the two mechanics sentences** — "Cut every lane worktree from the same base commit." and "Verify each new worktree sits on its own branch, is clean at cut time, and that no two lanes share a working copy." — leaving the `git rev-parse` check sentence in place between them, untouched (Feasibility P3-3: v1's replace-span would have deleted it). The first mechanics sentence is replaced by the coordinator paragraph from Step 2 (same text, minus its final `using-git-worktrees` sentence — this copy does not route through that skill); the second is replaced by: "The coordinator's manifest is the record of who owns which worktree; a lane whose launcher has died is settled by `scripts/lane-coord.sh reap --name <project>-<lane-id>`, never by hand-signaling its processes."

- [ ] **Step 4: Verify wiring and lint**

Run: `grep -o "lane-coord.sh" ~/workspace/custom-skills/overnight-parallel-lanes/SKILL.md | wc -l; grep -o "lane-coord.sh" skills/overnight-parallel-lanes/SKILL.md | wc -l; grep -c "git rev-parse --git-common-dir" skills/overnight-parallel-lanes/SKILL.md` plus markdownlint on both files (live file linted as in Task 3 Step 4; repo copy under the docs-lint glob).
Expected: live count `3` (claim, status, reap); repo count `3` (claim, reap, and the coordinator paragraph's `scripts/lane-coord.sh` occurrences total ≥ 3 — assert `>= 3` by `test "$(grep -o "lane-coord.sh" skills/overnight-parallel-lanes/SKILL.md | wc -l)" -ge 3`); the rev-parse sentence still present (count `1`); markdownlint exits 0 on both.

- [ ] **Step 5: Commit (repo copy only)**

```bash
git add skills/overnight-parallel-lanes/SKILL.md
git commit -m "feat(lanes): wire overnight-parallel-lanes through the coordinator"
```

---

### Task 9: CI script-tests job and operator documentation

**Files:**
- Modify: `.github/workflows/ci.yml` (add a sixth job)
- Create: `docs/deepcode-mechanisms.md`

**Interfaces:**
- Consumes: Task 1–2 unittest suites, Task 4–6 `lane-coord.sh --self-test` (both environment-independent by design — no daemon, no network, no real `$HOME` state; fixtures use `mktemp -d` plus the `AEP_*` env overrides).
- Produces: CI coverage for everything this plan built, and the operator doc.

- [ ] **Step 1: Add the `script-tests` job to `.github/workflows/ci.yml`**

Insert after the `shell-lint` job, exactly:

```yaml
  script-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 -m unittest discover -s scripts/tests -v
      - run: bash scripts/lane-coord.sh --self-test
```

(Not `boot-gate.sh --self-test`: its real-environment and policy cases require the live daemon, guards, and gh auth, which CI does not have — it stays a local check, as the pre-existing cases already were.)

- [ ] **Step 2: Verify CI YAML and local equivalents**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))" 2>/dev/null || python3 -c "import sys; print('pyyaml absent — verify by eye')"; python3 -m unittest discover -s scripts/tests 2>&1 | tail -1; bash scripts/lane-coord.sh --self-test | tail -1`
Expected: YAML parses (or the noted fallback), `OK` from unittest, `SELF-TEST: all ok` from lane-coord.

- [ ] **Step 3: Write `docs/deepcode-mechanisms.md`**

Sections, in order: (1) purpose + provenance (DeepCode pinned commit `49805ef`, link to `deepcode-reference.md`, note that no DeepCode code is copied — mechanisms re-implemented in AEP idiom); (2) Mechanism 1 — the verifier and receipts: discovery table with provenance tags, exit codes 0/1/2/3 and what each means, the receipts format and chain, **the trust shape in plain words** (receipts are evidence when the controlling side ran the verifier or chain-validated its own receipts; an implementer-produced receipts file is an audit artifact, not proof; `verify` executes the target repo's test code with the reviewer's full privileges — the budget and memory preflight are accident guards, not a sandbox); (3) Mechanism 2 — launch-point controls: `policy.data` grammar, the scrub semantics + `AEP_LANE_FULL_ENV=1` opt-out (loud warning), the declared-path check and its exact limit (it bounds the declared set; it does not confine a running worker), the boot-gate integrity check incl. SKIP semantics, and the plain scope statement: *this check runs whenever an operator or a cron invokes `boot-gate.sh`; wiring boot-gate into crons is issue #17 and is not delivered here*; runbook "change policy safely" = edit `policy.data` → PR → merge (the git history is the audit trail; an uncommitted edit makes boot-gate FAIL, by design); (4) Mechanism 3 — the coordinator as launcher: subcommands and exit codes 0/1/2/3/4/5, manifest fields, capacity (default 2, operational, inherited from DeepCode), fence semantics stated exactly (the fence is an `flock` held by the launcher process; its death frees the lock, and acquiring the lock is the only proof of death the tool accepts; the tool signals no process, ever), what is *not* fenced (any lane not launched through the coordinator); runbook "unstick a lane" = `status` → fence free → `reap` or re-claim (auto-settles); fence held → the lane is owned, hands off; (5) activation checklist (Risk R9): both skill copies were edited by Tasks 3 and 8 — verify with the Acceptance Criterion 6 greps against the live files; run one real `bash scripts/boot-gate.sh` and confirm the fifth line; run one real claim (`--exec true` against a scratch repo) and confirm the claimed/released lines; (6) deviations-from-DeepCode table (receipts-with-chain vs in-process ledger writes; no no-progress detection — see Non-Goals; stop-at-first-failure + budget; zero-discovery exit 2; full-length fingerprints; AEP discovery order + go/make/markdownlint rules; sensitive list delta (`gh` pair added, two product patterns dropped, `*/secrets.json` kept); capacity is a manifest count over coordinator-launched lanes, where DeepCode's 2 bounds executing turns).

- [ ] **Step 4: Lint the doc and run the full local gate suite**

Run: `npx --yes markdownlint-cli2 "docs/deepcode-mechanisms.md" "docs/superpowers/plans/2026-10-24-deepcode-mechanisms.md" && shellcheck scripts/*.sh && test -z "$(shfmt -d -i 2 scripts/*.sh)" && echo ALL-OK`
Expected: markdownlint exit 0 on both files, `ALL-OK` (or, locally, the noted absence of shellcheck/shfmt with CI as the authority — the markdownlint half still runs).

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml docs/deepcode-mechanisms.md
git commit -m "ci(scripts): run script test suites in CI; document DeepCode mechanisms"
```

---

## Test Plan

Four suites, all runnable locally and (except the boot-gate's) in CI. Every test named here is defined in its task with exact assertions.

**Unit — Python (Tasks 1–2), `python3 -m unittest discover -s scripts/tests -v` → 26 tests:**
- Verifier (17): discovery for each of the 7 allowlist rules including the negative cases (npm placeholder script, Makefile without `test:`, markdownlint config without the binary → SKIPPED line at CLI level); `*_test.py` globbing; the pytest fallback when test files import no unittest; empty root discovers nothing; `run_verification` pass/fail capture; 1 s timeout against `sleep 5` (killed return code recorded); output capped at 65536 bytes with `output_truncated`; stop-at-first-failure at the CLI; zero-discovery exit 2; memory-refusal exit 3; budget-zero stop.
- Receipts (9): receipt contains hashes, never output text; chain links across two commands; `check-receipts` PASS / no-receipts / failed-receipt verdicts; tampered field detected at its line; deleted middle line detected at the following line; malformed line reported as corrupt; per-task scoping over one shared chain-valid file.

**Self-test — lane coordinator (Tasks 4–6), `bash scripts/lane-coord.sh --self-test` → 19 cases:**
Claim runs the worker in the worktree and completes the manifest lifecycle; busy exit 3; release frees and epoch survives; stale claims auto-settle inside a later claim's capacity pass; capacity exit 4; parallel-claim race yields exactly one winner; declared-path refusals (sensitive dir, symlink-into-sensitive, `secrets.json` file); env scrub (credential var and non-exempt `AUTHORITY` gone, `SSH_AUTH_SOCK` and `GIT_AUTHOR_NAME` survive); full-env opt-out is total and loud; malformed policy data refuses; takeover after proven launcher death (epoch increments, old claim settled interrupted, content untouched); reap refuses a live fence, settles a dead one, and never signals the innocent PID a crafted manifest names; dirty cleanup refused, `--force-dirty` archives the diff then removes; foreign-path cleanup refused with the directory intact.

**Self-test — boot-gate (Task 7), `bash scripts/boot-gate.sh --self-test` → 7 cases:**
The pre-existing daemon-down, zero-guards, missing-destructive-rule, gh-auth-fail, and real-environment cases, plus `policy-mismatch` (output-asserted FAIL line) and `policy-skip` (output-asserted SKIP line, exit 0). Local only; CI lacks the daemon.

**End-to-end smoke (Task 2 Step 5):** a failing Makefile fixture proves the receipts flow *vetoes* — reviewer-side `verify` exits 1, `check-receipts` exits 1 naming the failed command; a passing fixture then extends the same chain and validates. A flow that only ever passes is not tested; this is the negative control.

**CI (Task 9):** the new `script-tests` job runs the Python suite and the lane-coord self-test on `ubuntu-latest`; the existing five jobs (docs-lint, shell-lint, go-checks, security/gitleaks, vendor-integrity) must remain green on the branch.

## Acceptance Criteria

Each criterion is checkable by running the stated command on the finished branch (criteria 4–6 are behavioral, against the real environment and the live skill files — no grep counts standing in for wiring):

1. `python3 -m unittest discover -s scripts/tests` exits 0 and reports `Ran 26 tests`.
2. `bash scripts/lane-coord.sh --self-test` exits 0 with 19 `SELF-TEST: <case> ok` lines, a final `SELF-TEST: all ok`, and no `FAIL` line.
3. `bash scripts/boot-gate.sh --self-test` exits 0 with 7 `SELF-TEST: ... ok` lines including `policy-mismatch` and `policy-skip`, then `SELF-TEST: all ok`.
4. Boot-gate behavior in the worktree: `bash scripts/boot-gate.sh` prints `BOOT-GATE: policy ok` as its fifth check line and exits 0; after appending one line to `scripts/policy.data` (uncommitted), it exits 1 printing `BOOT-GATE: policy FAIL:`; after `git checkout -- scripts/policy.data`, with `AEP_POLICY_DATA=/nonexistent` it prints `BOOT-GATE: policy SKIP:` and exits 0.
5. Receipts behavior: the Task 2 Step 5 smoke sequence reproduces exactly — failing fixture: `verify` rc=1, `check-receipts` rc=1 naming `make-test`; passing fixture in the same receipts file: `verify` rc=0, `check-receipts` rc=0.
6. Skill wiring, checked against the **live** copies the runtime loads: `grep -o "mechanical_verify.py" ~/workspace/custom-skills/subagent-driven-development/SKILL.md | wc -l` = 2; `grep -o "lane-coord.sh" ~/workspace/custom-skills/overnight-parallel-lanes/SKILL.md | wc -l` = 3; the same greps on the repo copies return 2 and ≥ 3 respectively, and `grep -c "git rev-parse --git-common-dir" skills/overnight-parallel-lanes/SKILL.md` = 1 (the isolation check sentence survived the repo-copy edit).
7. No-kill invariant (operational code): `sed -e '/^self_test() {/,/^}/d' scripts/lane-coord.sh | grep -nE '(^|[[:space:];])kill([[:space:]]|$)'` returns no lines — the self-test section is deleted before grepping (delimiter lines adjusted to the implemented function boundaries; all `kill` usage is confined to `self_test`).
8. `shellcheck scripts/*.sh` and `shfmt -d -i 2 scripts/*.sh` are clean (CI shell-lint is the authority where the local tools are absent); `npx --yes markdownlint-cli2 "**/*.md" "!reference/esf/**/*.md" "!skills/archify/**/*.md"` exits 0.
9. On the PR (when authorized): all six CI jobs green — docs-lint, shell-lint, go-checks, security (gitleaks finds no secrets, including in test fixtures), vendor-integrity, script-tests.
10. `git log --oneline origin/main..HEAD` shows 9 commits with Conventional Commit subjects, authored as `Musebot-Astro <6238157+pratik-saptarshi@users.noreply.github.com>`, and `git diff --stat origin/main..HEAD` touches only the files listed in this plan's File Structure plus this plan file. (The live skill edits are outside the repo by design; Criterion 6, not the diff, is their verification.)

---

## Appendix: Panel Disposition

Every P1/HIGH finding and every Devil's Advocate kill from the Phase-2 panel, mapped to its resolution in this rewrite. P2/P3 and MED/LOW findings are included where they changed the design; anything not listed here was checked by the panel and verified correct in v1 (exact DeepCode values, integration points, counts) and carries over unchanged unless a ruling above says otherwise.

**Kills and reshapes (judge's rulings 1–3):**
- **DA Premise 1/2a, Risk R4 (policy engine enforces nothing; boot-gate calls only validate+freeze):** the bash command-policy evaluator is **deleted** — script, rules grammar, modes, `check`/`run`/`validate`/`freeze`, snapshot semantics, all of it. What survives of Mechanism 2 is launch-point controls inside the lane launcher (Task 5), which execute on every coordinator launch by construction. `policy.rules` became `policy.data` (patterns + scrub fragments only; no rules, no mode).
- **DA Premise 3a, Risk R2 (ledger `check` is self-attestation):** the evidence ledger and its completion `check` are **deleted**. Mechanism 1 is verification receipts (Tasks 1–2): the verifier itself writes hash-chained receipts from executions it performed, and Task 3's skill text requires the *controller* to run it (or chain-validate its own receipts) — an implementer-written receipts file is explicitly not evidence.
- **DA Premise 3b (no-progress detection is self-reported and unread):** `observe` and the whole no-progress subsystem are **out of scope** (Non-Goals) — AEP has no dispatch observer. Fingerprinting survives only inside receipts, where the verifier hashes output it captured itself.
- **DA Premise 4 (bash tokenizer is unsound as a policy boundary):** no command string is evaluated anywhere in v2. Path canonicalization (`realpath` + `fnmatch`, the parts of DeepCode's design that required a real path library) survives in Python, applied to declared paths at claim time — the one place AEP actually holds the values.
- **DA Premise 5 (capacity 4 invented; lease proves the wrong death):** capacity default is DeepCode's verified **2**, labeled operational. The detached `sleep infinity` fence holder is **deleted**: the launcher process holds the `flock` on its own fd for its lifetime, so the lock's release *is* the launcher's death (Task 4). The plan and doc state the fence claim in exactly those terms.

**Feasibility:**
- **P1-1 (fence lock leaks to `flock`'s forked `sleep` child; killing `holder_pid` never frees it):** moot by redesign — there is no spawned holder and no forked command; the claiming process holds the fd itself. Ruling-mandated post-acquisition fence verification is Task 4 transaction step 3. The v1 case-4 silent-void path (release) is impossible in v2: a failed fence acquisition exits 3/1 before any manifest is written.
- **P2-1 (rules grammar didn't pin rest-of-line globs):** the rules grammar is deleted with the evaluator. The surviving data grammar (`policy.data`) is pinned exactly in Task 5, with a load-validation refusal (case 12).
- **P2-2 (`*/secrets.json` dropped silently):** restored; the Task 5 list is DeepCode's 25 minus the two product-specific patterns plus the `gh` pair, and case 9 pins `*/secrets.json` behaviorally.
- **P2-3 (discovery "verbatim" overclaims):** rules are provenance-tagged; `*_test.py` added to rule 5; DeepCode's pytest fallback adopted; `tests` matches DeepCode's `.exists()` (any file type).
- **P2-4 (flag order the grammar didn't admit):** the offending CLI is deleted; lane-coord's grammar is pinned (all flags after the subcommand) in Task 4.
- **P2-5 (`run` self-test cases lacked fixtures):** the cases are deleted with `run`; the surviving exec-path cases (10, 11) state their fixtures (exported vars, expected printf output) explicitly.
- **P2-6 (boot-gate policy case could pass vacuously):** Task 7's cases assert on captured output (`BOOT-GATE: policy FAIL:` / `SKIP:` lines), and a run that never reaches the policy check fails the case loudly instead of passing.
- **P2-7 (a named command had no call site):** call-site audit for every surviving command — `verify`/`check-receipts` ← SDD skill completion step (Task 3, live + repo); `claim --exec` ← overnight-parallel-lanes Run Setup (Task 8, live + repo); `status` ← the same skill text + Task 9 runbook; `reap` ← the same skill text + claim's auto-settle (same code path); standalone `release`/`release --clean` ← Task 9's operator runbook (lane-end and cleanup are operator actions by design); boot-gate `policy` check ← boot-gate's own normal path. No other commands exist.
- **P2-8 / Risk R17 (fixture `--base` unresolvable):** every self-test claim passes `--base HEAD`, stated in Task 4 Step 1.
- **P3-1:** `PYTHONUNBUFFERED=1` adopted; timeout records the killed process's return code — both now match DeepCode and are no longer deviations.
- **P3-2:** the PATH block is cited as `boot-gate.sh` lines 17–21.
- **P3-3:** Task 8 Step 3 replaces only the two mechanics sentences in the repo overnight copy; the `git rev-parse` check sentence stays verbatim between them (Acceptance Criterion 6 counts it).
- **P3-4:** the AUTH exemption is implemented at DeepCode's boundary; `AUTHORITY` is scrubbed, pinned by case 10; no equivalence beyond the pinned cases is claimed.
- **P3-5:** `SELF-TEST: all ok` summary line is pinned for `lane-coord.sh` (Task 4 Interfaces).
- **P3-6:** lint steps hedge on the absence of both `shellcheck` and `shfmt`.

**Risk:**
- **R1 (unverified `holder_pid` kill):** the kill path is deleted, not guarded — operational code in `lane-coord.sh` contains no `kill` invocation (Acceptance Criterion 7, its grep scoped outside the `self_test` function), and case 16 proves a crafted manifest's innocent PID is never signaled.
- **R3 (`~/.aep` doesn't exist; freeze non-atomic):** freeze, snapshots, and `~/.aep` are deleted. Boot-gate's check is read-only hashing of two byte streams (working tree vs `git show HEAD:`); no directory is created and there is no torn-pair window. Absent file → named SKIP line, never a wedge.
- **R5 (stale claims exhaust capacity forever):** claim's transaction auto-settles every provably-dead claim before counting (Task 4 step 1; case 5).
- **R6 (asynchronous holder race):** no asynchronous holder exists; the claiming process acquires the fence synchronously inside the transaction and verifies it before writing the manifest (Task 4 steps 2–3).
- **R7 (boot-gate ratifies agent-edited policy; no audit trail):** boot-gate FAILs on any working-tree `policy.data` that differs from the committed blob; policy changes are git/PR changes, and the git history is the audit trail. There is no mode to escalate.
- **R8 (verify can OOM/starve the VM):** `run_all` gains a 600 s total budget with stop-at-first-failure, per-command effective timeouts, and a `MemAvailable` preflight (< 512 MiB → exit 3). Task 9's doc states verify executes target test code with the reviewer's privileges.
- **R9 (merged ≠ activated):** Tasks 3 and 8 edit the live skill files in-task; Acceptance Criterion 6 greps the live copies; Task 9's doc carries the activation checklist (real boot-gate run, real claim) — the commit-body mirror note is gone.
- **R10 (false denies erode the gate):** v2 contains no command denies, so there is no false-deny wedge and no relief-valve pressure; the pattern list is data changed via PR. DeepCode's public-file allowance is deliberately not ported: v2 checks declared working paths, not per-file reads.
- **R11 (`npx --yes` at gate time):** discovery rule 7 requires a preinstalled `markdownlint-cli2` and otherwise emits a named SKIPPED line (Task 1, test 9). No network fetch occurs in any verification path.
- **R12 (boot-gate self-test mutates production):** `check_policy` is read-only; the mismatch case points `AEP_POLICY_DATA` at a temp file. The self-test freezes nothing because freezing no longer exists.
- **R13 (capacity lock held across `git worktree add`, unbounded):** the lock wait is bounded (`flock -w 60`, exit 5) and worktree creation happens after the lock is released.
- **R14 (env overrides silently replace the gate):** the gate-override variable is deleted with the evaluator; the one surviving security-relevant override, `AEP_LANE_FULL_ENV=1`, prints a loud stderr warning on every launch (case 11). Remaining `AEP_*` overrides select state locations and data files for tests; they do not change verdicts.
- **R15 (non-atomic appends; malformed-line behavior unspecified):** receipt append is a single `os.write` under `flock` on an `O_APPEND` fd; malformed lines have specified outputs (`RECEIPTS: corrupt at line <n>`) in both `verify` and `check-receipts`, pinned by test 8.
- **R16 (`--force-dirty` destroys uncommitted work):** `--force-dirty` first archives porcelain status + `git diff HEAD` to `$LANES_DIR/<name>.final-diff.patch` (Task 6; case 18 asserts the archive).

**Devil's Advocate, remaining items:**
- **Premise 2b (boot-gate itself has no caller):** acknowledged, not fixable inside this plan — cron invocation of boot-gate is issue #17's unexecuted scope. Task 7 and Task 9 state this plainly; no acceptance criterion claims cron enforcement (Criterion 4 is a behavioral check of the script, and says so by its form). The DA's sequencing condition (execute or drop #17 first) is noted for the handoff decision; the judge's ruling 4 governs: this plan proceeds without #17 and claims nothing from it.
- **Premise 2c (skill wiring in unread copies):** verified by diff during this rewrite — both repo copies diverge from live, and the live overnight step 2 is three sentences routing through `using-git-worktrees`, none of which matches v1's quoted text. Tasks 3 and 8 quote and edit each file's actual current text.
- **Premise 3c (fail-closed zero-discovery manufactures forgery):** zero-discovery is exit **2**, a named "no mechanical evidence available" state that Task 3's skill text records openly in the ledger — neither a FAIL to route around nor a PASS.
- **Premise 6 (fixture-only evidence; undecided values as decided; mechanical ≠ substantive; superstructure before substrate):** the receipts and coordinator criteria include behavioral checks against the real environment and live files (Criteria 4–6); the one invented operational value (capacity) now inherits DeepCode's verified default and is labeled operational; grep counts survive only as content checks on the skill files themselves, never as stand-ins for wiring.

---

**Execution handoff:** This is v2 — the adversarial panel pass is complete and recorded in the Appendix above. Execution method (subagent-driven vs native) is chosen at the handoff, per the wringer flow; the live-skill edits in Tasks 3 and 8 take effect the moment they are made, so those tasks must not be reordered ahead of the mechanisms they reference (Tasks 1–2 before Task 3; Tasks 4–6 before Task 8).
