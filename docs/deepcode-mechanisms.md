# DeepCode Mechanisms in AEP

## Purpose and provenance

This document is the operator reference for three mechanisms AEP adapted from [HKUDS/DeepCode](https://github.com/HKUDS/DeepCode) (pinned commit `49805ef`; see [deepcode-reference.md](deepcode-reference.md) for the study that selected them). No DeepCode code is copied: each mechanism was re-implemented in AEP idiom — a Python stdlib tool, a bash launcher, and data files — and reshaped where DeepCode's design depended on a dispatch point AEP does not have. The [deviations table](#deviations-from-deepcode) at the end records every deliberate difference.

The three mechanisms:

1. **Mechanical verification and receipts** — `scripts/mechanical_verify.py`: runs a target repo's own test commands under bounds and budgets, and writes hash-chained receipts for what it executed.
2. **Launch-point controls** — `scripts/policy.data` plus checks inside the lane launcher and `scripts/boot-gate.sh`: policy enforced at the one place AEP actually starts work, not by evaluating command strings after the fact.
3. **The lane coordinator** — `scripts/lane-coord.sh`: a launcher that claims fenced, capacity-bounded worktree lanes for parallel workers.

## Mechanism 1: the verifier and receipts

### What it does

`mechanical_verify.py verify --root <repo> --task <id>` discovers verification commands from a fixed allowlist of project markers, then executes them in discovery order, stopping at the first failure. Each command runs with a per-command timeout (default 300 s, `--timeout`), the whole run has a wall-clock budget (default 600 s, `--budget`), captured stdout/stderr are tail-capped at 65536 bytes, and a timed-out command is sent SIGTERM, given a 0.75 s grace, then SIGKILL — the killed process's return code is what gets recorded. Before running anything, a memory preflight refuses to start when the machine reports less than 512 MiB available (`MemAvailable`); like the budget, it is an accident guard against starving the host, not a security boundary.

### Discovery allowlist

| # | Command id | Marker at the repo root | Runs | Provenance |
| --- | --- | --- | --- | --- |
| 1 | `go-test` | `go.mod` | `go test ./...` | AEP addition |
| 2 | `cargo-test` | `Cargo.toml` | `cargo test` | DeepCode |
| 3 | `npm-test` | `package.json` with a real `scripts.test` string (non-empty, not npm's "no test specified" placeholder) | `npm test` | DeepCode |
| 4 | `pytest` | `pytest.ini`, `pyproject.toml`, `setup.cfg`, or a `tests` entry | `python3 -m pytest -q` | DeepCode |
| 5 | `unittest` (or `pytest` fallback) | root-level `test_*.py` or `*_test.py` files | `python3 -m unittest -v` with the discovered modules named explicitly (their file stems) if any file imports `unittest`, else the rule-4 pytest command | DeepCode, adapted |
| 6 | `make-test` | `Makefile` with a `test:` target | `make test` | AEP addition |
| 7 | `markdownlint` | `.markdownlint.yaml` present **and** `markdownlint-cli2` on PATH | `markdownlint-cli2 "**/*.md" "!reference/esf/**/*.md" "!skills/archify/**/*.md"` | AEP addition |

Discovery is deduplicated by command id and capped at the first match per rule. Rule 7 calls the binary directly — nothing in any verification path fetches from the network (no `npx --yes` at gate time). If the config file exists but the binary is missing, the run prints a named `VERIFY: markdownlint SKIPPED tool missing` line instead of discovering the command.

### Exit codes

`verify`:

| Code | Meaning |
| --- | --- |
| 0 | Every discovered command executed and passed. |
| 1 | A command failed (the run stops at the first failure), the budget was exhausted with commands unrun, or `verify` refused to append to a receipts file whose last line is malformed. |
| 2 | Zero commands discovered — a named "no mechanical evidence available" state (`VERIFY: no verification commands discovered ...`). It is neither a pass nor a failure; callers record it openly. |
| 3 | Memory preflight refusal: less than 512 MiB available; nothing was run. |

`check-receipts --receipts <file> --task <id>`:

| Code | Meaning |
| --- | --- |
| 0 | The whole file's chain validates, every receipt in the task's latest run records `exit_code` 0 with no timeout, and that run ends in a run-completion record matching its command receipts (`RECEIPTS: PASS`). |
| 1 | The file is corrupt at a named line, the chain is broken at a named line, the task has no receipts, one of the latest run's receipts records a failure, or the task's latest run has no matching run-completion record — the partial receipt set of a run that stopped early is rejected (`RECEIPTS: FAIL` / `RECEIPTS: corrupt` / `RECEIPTS: chain broken`). |

### Receipts format and chain

With `--receipts <file>`, `verify` first appends a run-start record (`kind: run-start`) carrying a unique `run_id` for the run; it then appends one JSON line per executed command, and each receipt carries the same `run_id`. A receipt contains hashes, never output text. When — and only when — every discovered command has executed and passed, `verify` appends a final run-completion record (`kind: run-complete`, same `run_id`) carrying the run's command count and a SHA-256 digest of the ordered command ids; a run that stops early writes no such record. `check-receipts` validates only the task's latest run segment (from its run-start record to its completion record); earlier segments in the same file remain audit history, so an interrupted run cannot poison a later successful retry. The command-receipt fields:

| Field | Content |
| --- | --- |
| `ts` | UTC timestamp of the execution |
| `task` | the `--task` value the run was scoped to |
| `run_id` | the run's unique id, shared by its run-start record, receipts, and completion record |
| `command_id` | the discovery rule id (e.g. `make-test`) |
| `argv` | the exact argument vector executed |
| `exit_code` | the process return code (the killed code, on timeout) |
| `timed_out` | whether the per-command timeout fired |
| `duration_ms` | wall-clock duration of the command |
| `stdout_sha256` | SHA-256 of the captured (tail-capped) stdout |
| `stderr_sha256` | SHA-256 of the captured (tail-capped) stderr |
| `chain_sha256` | SHA-256 of the previous receipt's `chain_sha256` concatenated with the canonical JSON of this receipt's other fields |

The genesis link is 64 zero characters. Appends are a single `os.write` under `flock` on an `O_APPEND` descriptor, so concurrent runs cannot interleave a line. `check-receipts` validates the chain over the **whole file** before filtering to the requested task, so per-task verdicts over one shared file stay meaningful, and a deleted line is detected at the following line, while a tampered line is detected at the tampered line itself.

### The trust shape, in plain words

Receipts are evidence when the controlling side ran the verifier itself, or chain-validates receipts from its own runs. An implementer-produced receipts file is an audit artifact, not proof: the file format cannot distinguish who ran the verifier, and nothing here pretends otherwise. That is why the SDD completion step requires the *controller* to run `verify` fresh (or chain-validate its own receipts) before a task may be marked complete.

And the symmetrical warning: `verify` executes the target repo's test code with the reviewer's full privileges. The timeout, budget, output cap, and memory preflight are accident guards against runaway test suites — they are not a sandbox, and they do not make an untrusted repo safe to verify.

## Mechanism 2: launch-point controls

There is no command-string policy evaluator in AEP. Policy lives at the launch point: `scripts/lane-coord.sh` loads and validates `scripts/policy.data` on every claim, applies its controls to the lane it is about to start, and `scripts/boot-gate.sh` verifies the policy file itself has not been edited outside git.

### `policy.data` grammar

Two sections, one pattern or fragment per line; `#` comments and blank lines are ignored; anything else — an unknown section, a pattern before any section, a token containing whitespace, an empty section, an unreadable file — is a load-time validation error and the claim is refused before any state is created.

- `[sensitive-paths]` — `fnmatch` patterns (`*` spans `/`) matched against canonicalized declared paths. The shipped list is DeepCode's 25 patterns minus its two product-specific ones (`*/.deepcode/credentials*`, `*/deepcode_config.json`), plus the GitHub CLI pair (`*/.config/gh`, `*/.config/gh/*`); `*/secrets.json` is kept.
- `[env-scrub]` — name fragments (`KEY`, `PASSWORD`, `SECRET`, `TOKEN`, `CREDENTIAL`, `AUTH`) matched case-insensitively against environment variable names.

### Env scrub semantics

The worker child — and only the child — runs with every environment variable whose name contains a scrub fragment unset. The launcher keeps its own environment for its bookkeeping; the scrub runs in the subshell that spawns the worker. The `AUTH` fragment applies DeepCode's boundary exemptions: an occurrence immediately preceded by `SSH_` is exempt (so `SSH_AUTH_SOCK` survives, which git-over-SSH needs), and an occurrence immediately followed by `OR` plus `_` or end-of-name is exempt (so `GIT_AUTHOR_NAME` survives). `AUTHORITY` is **not** exempt and is scrubbed.

Opt-out: `AEP_LANE_FULL_ENV=1` disables the scrub entirely, and does so loudly — every launch prints `LANE: warning AEP_LANE_FULL_ENV=1: worker receives the full environment (credential scrub disabled)` to stderr. There is no quiet way to disable the scrub.

### The declared-path check, and its exact limit

A claim declares a working set: the lane's worktree path plus every `--path <extra>`. Each path is canonicalized (`realpath`, symlinks resolved — a declared symlink into a sensitive directory **is** the sensitive directory) and matched against `[sensitive-paths]` after the claim transaction, before worktree setup; a match refuses the claim (exit 1, claim settled as a refusal).

The limit, stated plainly: this check bounds the **declared** set. It does not confine a running worker, which can still open any path its own permissions allow. It exists to catch a lane being *aimed* at a credential store by declaration or by symlink — not to sandbox the worker.

### Boot-gate policy integrity check

`boot-gate.sh` runs `check_policy` as its fifth check. It hashes the working-tree policy file (`AEP_POLICY_DATA`, defaulting to the `policy.data` beside the script) and the committed blob (`git show HEAD:scripts/policy.data`) and compares them byte-exact:

- Match → `BOOT-GATE: policy ok`.
- Differ, or the committed blob cannot be read → `BOOT-GATE: policy FAIL: ...` and the gate exits non-zero. An uncommitted policy edit fails the gate **by design**.
- No policy file at the configured path → `BOOT-GATE: policy SKIP: no policy data at ... (launch-policy integrity inactive)` and the gate proceeds (exit unaffected). SKIP means the integrity check is inactive, not that policy passed.

Scope statement: this check runs whenever an operator or a cron invokes `boot-gate.sh`. Wiring boot-gate into crons is issue #17 and is **not** delivered here — nothing in this mechanism claims cron enforcement.

### Runbook: change policy safely

1. Edit `scripts/policy.data` on a branch.
2. Open a PR; the diff is the review of the policy change.
3. Merge. The git history is the audit trail — there is no other policy state, no snapshot, and no mode to escalate.
4. Never edit `policy.data` in a live working tree to "fix" a running system: boot-gate will FAIL on the uncommitted edit, and lane claims read the file as-is.

## Mechanism 3: the coordinator as launcher

`lane-coord.sh` is a launcher, not a bookkeeping tool: a claim is held by the `lane-coord.sh claim ... --exec <command...>` process for the lane's whole lifetime, and the worker runs as its child inside the claimed worktree. State lives in `$AEP_LANES_DIR` (default `~/workspace/worktrees/.lanes`); worktrees are created at the deterministic path `$AEP_WORKTREES_ROOT/<name>` (default root `~/workspace/worktrees`).

### Subcommands

| Subcommand | Purpose |
| --- | --- |
| `claim --repo <abs path> --project <slug> --lane <slug> --branch <name> [--base <ref>] --worker <id> [--capacity <n>] [--path <extra> ...] --exec <command...>` | Claim a lane and run the worker in it. Prints `LANE: claimed <name> path=... branch=... epoch=...`; when the worker exits, prints `LANE: released <name> (worker exit <n>)` and exits with the worker's status. |
| `release --name <name> [--clean [--force-dirty]]` | The normal teardown path (see below). Without `--clean`, settles the claim and leaves the worktree in place. |
| `reap --name <name>` | Settle a claim whose launcher is provably dead, without touching the worktree. Refuses while the fence is held. |
| `status [--name <name>] [--capacity <n>]` | Show each lane's state, epoch, worker, fence state, and path, plus the pool line (`LANE: pool: <n> claimed of <capacity>`). |
| `--self-test` | The built-in 21-case suite (also run in CI by the `script-tests` job). |

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success. For `claim`, once the worker has run, the exit code is the worker's own status. |
| 1 | Refusal or failure: policy data invalid, declared path refused, fence verification failed, unresolvable base, worktree setup failure, reap/clean refusal. |
| 2 | Usage or validation error (missing/unknown flags, bad slug or branch name). |
| 3 | Busy: the lane's fence is held by a live launcher (`LANE: busy ...`). |
| 4 | Capacity reached: the post-settle claimed count is at capacity (`LANE: capacity reached ...`). |
| 5 | Timed out after 60 s waiting for the capacity lock. |

### Manifest

Each lane has one JSON manifest, `<name>.json` in the lanes directory, written atomically (temp file + rename) with fields serialized by a JSON encoder, so paths containing quotes or backslashes round-trip exactly: the claim-time write happens inside the capacity lock, as do reap/release updates; only the launcher's post-worker `released` update runs outside the lock (still temp file + rename, so atomicity is unaffected):

| Field | Content |
| --- | --- |
| `version` | manifest schema version (1) |
| `name` | lane name (`<project>-<lane>`) |
| `repo` | absolute path of the source repo |
| `path` | the worktree path |
| `branch` | the lane branch |
| `base` | the base ref resolved to a full commit SHA at claim time |
| `worker` | the `--worker` id |
| `launcher_pid` | the claiming process's PID — operator information only; nothing ever signals it |
| `epoch` | claim generation: starts at 1, increments monotonically per lane across takeovers |
| `state` | `claimed`, `released`, `reaped`, or `cleaned` (set by `release --clean` once the validated worktree removal completes) |
| `claimed_at`, `updated_at` | UTC timestamps |

A per-lane history records claim, release, and settled-interrupted events with their epoch and worker.

### Capacity

At most **2** lanes may be in `claimed` state at once (default; `--capacity <n>` overrides per claim). The value is DeepCode's verified default, inherited deliberately; it is an operational knob, not a correctness property. The count is over manifests for coordinator-launched lanes, evaluated *after* the claim transaction auto-settles every provably-dead claim — a dead lane never holds capacity hostage.

### Fence semantics, stated exactly

The fence is an `flock` held by the launcher process on its own open file descriptor, for its lifetime. The worker is spawned with the fence (and capacity-lock) descriptors closed, so no descendant can keep the fence alive after the launcher dies. Therefore: the launcher's death frees the lock, and **acquiring the lock is the only proof of death the tool accepts** — a later claim whose fence probe succeeds auto-settles the previous claim as interrupted (epoch increments; the worktree's contents are left exactly as they lie). The tool signals no process, ever: `launcher_pid` is never killed, and a crafted manifest naming an innocent PID changes nothing.

What is **not** fenced: any lane, worktree, or process not launched through the coordinator. The coordinator's guarantees cover coordinator-launched lanes only.

### Runbook: end a lane normally

`release` is the normal teardown path — not `reap`, and not manual worktree removal:

1. `bash scripts/lane-coord.sh release --name <name>` — settles the claim (state `released`, capacity freed). Refused while the fence is held: a lane whose launcher is still running is owned; hands off.
2. When the worktree itself should go away: `release --name <name> --clean`. Cleanup validates four ownership signals, in order, and removes nothing on any mismatch: (1) the manifest exists and names this lane's repo/path/branch; (2) the repo's worktree list registers the path; (3) the branch checked out at the path is the manifest's branch; (4) the path is exactly the deterministic managed location. A dirty worktree is refused; `--clean --force-dirty` first archives the porcelain status and `git diff HEAD` to `$AEP_LANES_DIR/<name>.final-diff.patch`, then removes.

### Runbook: unstick a lane

1. `bash scripts/lane-coord.sh status --name <name>` — look at the fence state.
2. Fence **held** → the lane is owned by a live launcher. Hands off; there is nothing to unstick.
3. Fence **free** → the launcher is dead (that is what the free fence proves). Either `reap --name <name>` to settle the claim and leave the worktree, or simply make the next `claim` for the lane — it auto-settles the stale claim, increments the epoch, and proceeds.
4. Never delete a manifest or a fence file by hand to force a lane free; that destroys the epoch history the next claim relies on.

## Activation checklist

Merging code is not activation. After this branch lands, verify each item against the **live** environment:

- [ ] Both skill copies carry the wiring (Tasks 3 and 8 edited the repo copies in `skills/` and the live copies the runtime loads in `~/workspace/custom-skills/`). Check with the Acceptance Criterion 6 greps against the live files: `mechanical_verify.py` appears 2× in the live SDD skill; `lane-coord.sh` appears 3× in the live overnight-parallel-lanes skill.
- [ ] Run one real `bash scripts/boot-gate.sh` and confirm the fifth check line is `BOOT-GATE: policy ok` (or an understood SKIP).
- [ ] Run one real claim against a scratch repo — `lane-coord.sh claim ... --exec true` — and confirm the `LANE: claimed ...` line on launch and the `LANE: released ... (worker exit 0)` line when it finishes.
- [ ] Confirm the `script-tests` CI job is green on the merge PR (docs-lint, shell-lint, go-checks, security, vendor-integrity, script-tests — six jobs).

## Deviations from DeepCode

| DeepCode | AEP | Why |
| --- | --- | --- |
| Evidence ledger written in-process by the runtime | Hash-chained receipts appended by the verifier's own executions; the controller runs the verifier or validates its own chain | AEP has no runtime intercepting the implementer's calls, so implementer-written evidence would be self-attestation. Receipts make the executing side the writing side. |
| No-progress (loop) detection over fingerprinted tool calls | Not implemented (see the plan's Non-Goals) | There is no dispatch observer in AEP to feed it observations; a self-reported observation stream would be ceremony. |
| Verifier runs to completion, collecting results | Stop at first failure, plus a 600 s total budget and a memory preflight | AEP's consumer is an unattended review gate on a small shared VM; bounded, fail-fast runs are the point. |
| Zero discovered commands is an ordinary empty result | Zero discovery is exit 2, a named "no mechanical evidence available" state recorded openly in the SDD ledger | Fail-closed zero-discovery would manufacture pressure to forge evidence; a silent pass would hide the absence. A named third state avoids both. |
| Ledger fingerprints are truncated hashes | Receipts carry full-length SHA-256 fingerprints | Receipts are audit artifacts meant to be re-validated later; truncation buys nothing at this scale. |
| Discovery: cargo, npm, pytest-family, make-family equivalents in its own order | AEP order (go, cargo, npm, python markers, root python files, make, markdownlint) plus three AEP-only rules (`go-test`, `make-test`, `markdownlint`) | The allowlist follows the repos AEP actually verifies, in a deterministic order. |
| Sensitive-path list of 25, including its own product paths | 25 patterns: the two DeepCode-product patterns dropped, the `gh` CLI pair added, `*/secrets.json` kept | The list protects this operator's credential stores, not DeepCode's. |
| Capacity 2 bounds concurrently executing turns, counted by the runtime | Capacity 2 (default) counts `claimed` manifests over coordinator-launched lanes | AEP has no turn runtime; the manifest pool is the countable thing, and the inherited default is labeled operational, not derived. |
