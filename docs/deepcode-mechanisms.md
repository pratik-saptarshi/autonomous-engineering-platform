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

Python commands must also prove execution, not just routing: each `pytest`/`unittest` receipt records `tests_collected` (for unittest, the `Ran N` line parsed from stdout+stderr; for pytest, the number of `<testcase>` elements in the junitxml report the same run writes to a tempfile outside the tree, cross-checked against the transcript summary's outcome groups — when a summary exists the two must agree or the count is 0, and when no report was written the count is unproven, the leg fails the count gate, and its receipt carries no `tests_collected` field (the summary is never believed on its own); that composition is what makes the count independent of terminal verbosity. Skips count as collected, deliberately: whether a collected test skips is the test author's signal, not a routing failure). A Python command that collects zero tests, or whose count cannot be proven, fails the run even when the runner itself exits 0.

The count's trust level, in plain words: both evidence channels are produced inside the runner process, so the plugins loaded into that environment are trusted the way the interpreter itself is trusted — a reporter-replacing plugin (e.g. pytest-sugar) that changes or omits the summary line included. What that trust costs depends on which channels a run produced. When both are present, they must agree: a forged or mangled single channel contradicts the other and yields 0, so the run is rejected rather than passed on an inflated number — and in that configuration, defeating the count takes forging both channels to the same number in the same run. When the report was not written at all, the count is unproven and the leg fails the count gate: suppression is self-defeating, because the tree's bound config can switch the report channel off with a passive `addopts = -p no:junitxml` line, so the forgeable transcript is never believed on its own. When verbosity suppressed the summary instead, the count rests on the report alone, and a tree whose own code overwrites that report file defeats it. That last case is the in-tree-code exposure, not a channel defect: the forging code is inside the sealed tree, bound by the tree digest like everything else the run executes from the bound set (the whole tree minus the receipts file and the residue directories named under *Tree binding*) — the same class as a conftest monkeypatching assertions, and the reason the statement is scoped by configuration rather than given as one blanket guarantee.

Verification commands do not inherit the caller's environment untouched. Each command runs with `os.environ` minus every name the `[env-scrub]` fragments of `scripts/policy.data` (resolved from `$AEP_POLICY_DATA`, else the `policy.data` beside the script) mark sensitive — the same fragments and the same `AUTH` boundary exemptions as the lane scrub under Mechanism 2. `AEP_VERIFY_FULL_ENV=1` opts out and passes the full environment through. The run-start record states the mode in all cases as `env`: `scrubbed`, `full (AEP_VERIFY_FULL_ENV)`, or `unscrubbed (no policy)` — the last when no policy file exists, so the record never claims a scrub that did not happen. The scrub matches variable *names* only: a variable whose name carries no sensitive fragment — `PYTHONPATH` is the load-bearing case — passes through verbatim, so executed code can also arrive via the caller's own environment, a channel no tree binding covers. The recorded mode states whether the scrub ran, never what a passed-through path variable points at.

### Discovery allowlist

| # | Command id | Marker at the repo root | Runs | Provenance |
| --- | --- | --- | --- | --- |
| 1 | `go-test` | `go.mod` | `go test ./...` | AEP addition |
| 2 | `cargo-test` | `Cargo.toml` | `cargo test` | DeepCode |
| 3 | `npm-test` | `package.json` with a real `scripts.test` string (non-empty, not npm's "no test specified" placeholder) | `npm test` | DeepCode |
| 4 | `pytest` | `pytest.ini`, `pyproject.toml`, `setup.cfg`, or a `tests` entry | `python3 -m pytest -v` | DeepCode |
| 5 | `unittest` and/or `pytest` | root-level `test_*.py` or `*_test.py` files | partitioned by AST classification: `python3 -m unittest -v` naming the modules that define a `TestCase` subclass (their file stems), plus the rule-4 pytest command when any module triggers it — module-level `test_*` functions, `Test*` classes with `test_*` methods that are not `TestCase` subclasses, or a module with no leg at all. A module whose only collectable content is `TestCase` subclasses does not by itself trigger the pytest command; imports alone never create the unittest leg; a module that fails to parse falls back to substring classification — a mixed suite runs both runners, a single-style suite runs only its own | DeepCode, adapted |
| 6 | `make-test` | `Makefile` with a `test:` target | `make test` | AEP addition |
| 7 | `markdownlint` | `.markdownlint.yaml` present **and** `markdownlint-cli2` on PATH | `markdownlint-cli2 "**/*.md" "!reference/esf/**/*.md" "!reference/neurostrata/**/*.md" "!skills/archify/**/*.md"` | AEP addition |

Discovery is deduplicated by command id and capped at the first match per rule. Rule 7 calls the binary directly — nothing in any verification path fetches from the network (no `npx --yes` at gate time). If the config file exists but the binary is missing, the run prints a named `VERIFY: markdownlint SKIPPED tool missing` line instead of discovering the command.

### Exit codes

`verify`:

| Code | Meaning |
| --- | --- |
| 0 | Every discovered command executed and passed. |
| 1 | A command failed (the run stops at the first failure), the budget was exhausted with commands unrun, `verify` refused to append to a receipts file whose last line is malformed, a receipts run's tree was not clean at HEAD (git roots — see *Tree binding*), or the tree changed during the run so no completion record was written. |
| 2 | Zero commands discovered — a named "no mechanical evidence available" state (`VERIFY: no verification commands discovered ...`). It is neither a pass nor a failure; callers record it openly. Also exit 2: `verify` refused to write receipts to a file tracked by git inside the root — evidence must not be part of the artifact it describes (untracked receipts inside the root, the SDD layout, are allowed). |
| 3 | Memory preflight refusal: less than 512 MiB available; nothing was run. |

`check-receipts --receipts <file> --task <id> --root <repo> [--historical]` (`--root` is required):

| Code | Meaning |
| --- | --- |
| 0 | The whole file's chain validates, every receipt in the task's latest run records `exit_code` 0 with no timeout — or carries one of the two count-gate acceptances the runtime itself seals: a deferred-zero unittest receipt (the no-tests exit code over a clean zero collection, excused when a later Python leg in the segment collected tests and passed; #56) or a speculative-zero receipt (a leg sealed with the speculative mark whose clean zero another Python leg's pass excused; #51) — that run ends in a run-completion record matching its command receipts, and the segment's tree binding validates (`RECEIPTS: PASS`). In default mode the binding check also requires the worktree's current HEAD to equal the bound head and the tree to be clean. |
| 1 | The file is corrupt at a named line, the chain is broken at a named line, the task has no receipts, one of the latest run's receipts records a failure, or the task's latest run has no matching run-completion record — the partial receipt set of a run that stopped early is rejected (`RECEIPTS: FAIL` / `RECEIPTS: corrupt` / `RECEIPTS: chain broken`). Also exit 1: the segment's stated digest does not match its stated head or the live fs tree (`RECEIPTS: STALE`), the worktree's HEAD has moved past the bound head (`RECEIPTS: HEAD-MOVED`), the working tree is dirty (default mode, `RECEIPTS: DIRTY`), or the segment is bound to a different root than `--root` names (`RECEIPTS: FAIL ... segment is bound to root ..., not ...`). |
| 2 | The segment carries no tree binding — it predates binding (`RECEIPTS: UNBOUND`) — or its recorded commit can no longer be read (`RECEIPTS: UNVERIFIABLE`). Exit 2 is never evidence. |

### Receipts format and chain

With `--receipts <file>`, `verify` first appends a run-start record (`kind: run-start`) carrying a unique `run_id` for the run, the run's `env` mode (see *What it does*), and — on the CLI path — `subreaper`, whether the child-subreaper flag was set for the survivor sweep; it then appends one JSON line per executed command, and each receipt carries the same `run_id`. A receipt contains hashes, never output text. When — and only when — every discovered command has executed and passed, `verify` appends a final run-completion record (`kind: run-complete`, same `run_id`) carrying the run's command count and a SHA-256 digest of the ordered command ids; a run that stops early writes no such record. `check-receipts` validates only the task's latest run segment (from its run-start record to its completion record); earlier segments in the same file remain audit history, so an interrupted run cannot poison a later successful retry. The command-receipt fields:

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
| `tests_collected` | collected-test count — `pytest`/`unittest` receipts only (see *What it does*) |
| `survivors_killed` | pids of detached descendants the post-command sweep killed — present only when non-empty |
| `chain_sha256` | SHA-256 of the previous receipt's `chain_sha256` concatenated with the canonical JSON of this receipt's other fields |

The genesis link is 64 zero characters. Appends are a single `os.write` under `flock` on an `O_APPEND` descriptor, so concurrent runs cannot interleave a line. `check-receipts` validates the chain over the **whole file** before filtering to the requested task, so per-task verdicts over one shared file stay meaningful, and a deleted line is detected at the following line, while a tampered line is detected at the tampered line itself.

### Tree binding

A receipts segment must describe a tree, not just a run. A receipts run computes a **binding** before its first command and records it on both the run-start and the run-completion record as a `binding` object: `{root, head, tree_digest, mode}` (`root` is the canonicalized `--root` path). The `binding` field is deliberately absent from the records' required-field sets: `check-receipts` reads it directly, and its absence is the `UNBOUND` verdict (exit 2), never corruption and never a silent pass — pre-binding segments are refused, not reinterpreted.

- **Git mode** (the root is inside a git worktree): `head` is `git rev-parse HEAD` and `tree_digest` is a SHA-256 over the entries of `git ls-tree -r -z <head>` — computed from git objects, never from working-tree content, so it can be recomputed at any later time while the commit exists. A receipts run in git mode refuses a dirty tree up front (`tree not clean at HEAD — commit or stash before verifying`, no completion record): `git status` must be empty after dropping the receipts file itself, anything under `.superpowers/`, and untracked entries under the four residue directory names (`.git`, `__pycache__`, `.pytest_cache`, `.mypy_cache`) — the workflow's own bookkeeping and the caches a run itself creates. Untracked content under any other directory name counts as dirty exactly like untracked content anywhere else: a `node_modules`, `build`, or `.venv` tree a run could execute from must be committed (which binds it, via the ls-tree digest) or removed before the tree can seal. Modified or staged tracked files always count as dirty. If the tree is dirtied during the run, no completion record is written. Two limits are part of git mode's contract, stated rather than implied: content git is configured to ignore never appears in `git status`, so ignored files are outside git mode's binding anywhere in the tree — a `.gitignore`d dependency tree is the standing example — and inside a submodule, untracked content surfaces as the submodule's own dirtiness under git's default settings, but in practice a submodule tree seals only with `submodule.<name>.ignore=untracked` set (the run's own cache residue inside the submodule otherwise dirties it between the two cleanliness checks), and under that setting untracked content inside the submodule, under any directory name, is invisible to the superproject and unbound; tracked content inside the submodule stays bound by the gitlink.
- **Fs mode** (no git): `head` is null and `tree_digest` is a SHA-256 over the tree's entries (relative path + git-style mode string + content hash; the mode string is the file type plus, for regular files, the executable bit — `100644` vs `100755`, `120000` for a symlink — and symlinks contribute their target string, never the target's content), excluding the receipts file and the four residue directory names (`.git`, `__pycache__`, `.pytest_cache`, `.mypy_cache`) at any depth. Every other directory is bound: dependency, virtualenv, and build-output trees (`node_modules`, `.venv`, `.tox`, `target`, `build`, `dist`, `coverage`, `htmlcov`) digest like any other directory, so content a run executes from them cannot change under a standing seal. The residue exclusion carries one named residual: cache bytes are not bound, and a bytecode-cache entry actively forged to match its source file's recorded mtime and size is executed by the interpreter without the source changing. That is an active forgery — the family of authoring a receipts segment wholesale — not a mutation of executed content: editing the source itself moves this digest and invalidates the cache in the same act. The caches cannot simply be bound instead, because the verifier's own runs create them mid-run (a pytest leg writes `.pytest_cache` and `__pycache__` from cold), so a Python tree's seal would abort on the run's own residue. If the digest changes during the run, no completion record is written. The mode string has been part of the fs format since the tree-binding change (PR #42), which makes that change a format boundary: fs receipts sealed before it record a digest no post-change tree can reproduce, so `check-receipts` reports them `STALE` even when nothing on disk changed. That is intended behaviour, and no migration is provided — fs receipts are short-lived run evidence, re-created by re-running `verify`, not archives to convert. The bound-set change that brought the eight content directories into the fs digest is a boundary of the same kind for any tree containing them, with the same disposition. Git-mode digests are unaffected: `ls-tree` entries carried the mode all along.

`check-receipts` validates the binding after the chain and segment structure. A segment whose recorded `root` differs from the canonicalized `--root` is refused first (`RECEIPTS: FAIL`, exit 1) — a segment is evidence about the tree it was bound to, and is checked only against that tree. A stated digest that does not match its stated head (git) or the live tree (fs) is `STALE` (exit 1); a recorded commit that no longer exists is `UNVERIFIABLE` (exit 2). Default mode — the completion gate — additionally requires the worktree's current HEAD to equal the bound head (`HEAD-MOVED`) and the tree to be clean (`DIRTY`). `--historical` skips only those two current-state requirements: it validates the segment as evidence about its own recorded head, which is what a cross-session resume needs — it never completes a task by itself.

### The trust shape, in plain words

Receipts are evidence when the controlling side ran the verifier itself, or validates receipts from its own runs with `check-receipts` against the tree the segment is bound to. An implementer-produced receipts file is an audit artifact, not proof: the file format cannot distinguish who ran the verifier, and nothing here pretends otherwise. That is why the SDD completion step requires the *controller* to run `verify` fresh (or validate its own receipts, in default mode, against the bound tree) before a task may be marked complete.

And the symmetrical warning: `verify` executes the target repo's test code with the reviewer's full privileges. The timeout, budget, output cap, and memory preflight are accident guards against runaway test suites — they are not a sandbox, and they do not make an untrusted repo safe to verify.

## Mechanism 2: launch-point controls

There is no command-string policy evaluator in AEP. Policy lives at the launch point: `scripts/lane-coord.sh` loads and validates `scripts/policy.data` on every claim, binds it to its committed source (see *Claim-time policy integrity*), applies its controls to the lane it is about to start, and `scripts/boot-gate.sh` verifies the policy file itself has not been edited outside git.

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

### Claim-time policy integrity

Loading a valid policy file is not the same as loading the *committed* one. On the claim path only (release/reap act on already-claimed state and never re-check), `lane-coord.sh` binds the loaded policy to its source and records the outcome in the lane manifest:

- `AEP_POLICY_DATA` set (non-empty): no blob check. Outcome `operator-override` — the override is durable evidence in the manifest, not a console line.
- Unset, and `HEAD` of the script's own repo carries `scripts/policy.data`: the loaded file's SHA-256 must equal the committed blob's (the blob is streamed into the hash — never captured in a shell variable, whose trailing-newline stripping would mismatch every claim). A mismatch refuses the claim (exit 1) with the remedy named: commit the policy change, or set `AEP_POLICY_DATA` and be recorded as an override. Outcome `verified`.
- Unset, and the probe fails (not a repo, or the repo has no such path — the installed-copy case): no check. Outcome `not-applicable`.

Every claim manifest records the outcome as `policy_integrity`, with `policy_path` and `policy_sha256` (see *Manifest*).

### Boot-gate policy integrity check

`boot-gate.sh` runs `check_policy` as its fifth check. It hashes the working-tree policy file (`AEP_POLICY_DATA`, defaulting to the `policy.data` beside the script) and the committed blob (`git show HEAD:scripts/policy.data`) and compares them byte-exact:

- Match → `BOOT-GATE: policy ok: <path> (sha256 <digest prefix>)`, followed by the token line `BOOT-GATE-RESULT: POLICY-OK`.
- Differ, or the committed blob cannot be read → `BOOT-GATE: policy FAIL: ...` and the gate exits non-zero (no token line). An uncommitted policy edit fails the gate **by design**.
- No policy file at the configured path → `BOOT-GATE: policy SKIP: no policy data at ... (launch-policy integrity inactive)`, followed by `BOOT-GATE-RESULT: POLICY-INACTIVE`, and the gate proceeds (exit unaffected). SKIP means the integrity check is inactive, not that policy passed.

The token line is the machine-readable form of the outcome — a SKIP is distinguishable from a pass without parsing prose. The gate's exit contract is unchanged: SKIP still exits 0.

Scope statement: this check runs whenever an operator or a cron invokes `boot-gate.sh`. Wiring boot-gate into crons is issue #17 and is **not** delivered here — nothing in this mechanism claims cron enforcement.

### Runbook: change policy safely

1. Edit `scripts/policy.data` on a branch.
2. Open a PR; the diff is the review of the policy change.
3. Merge. The git history is the audit trail — there is no other policy state, no snapshot, and no mode to escalate.
4. Never edit `policy.data` in a live working tree to "fix" a running system: boot-gate will FAIL on the uncommitted edit, and lane claims read the file as-is.

## Mechanism 3: the coordinator as launcher

`lane-coord.sh` is a launcher, not a bookkeeping tool: a claim is held by the `lane-coord.sh claim ... --exec <command...>` process for the lane's whole lifetime, and the worker runs as its child inside the claimed worktree. State lives in `$AEP_LANES_DIR` (default `~/.local/state/aep/lanes` — outside the worktrees tree; see *State location, migration, and the residual risk*); worktrees are created at the deterministic path `$AEP_WORKTREES_ROOT/<name>` (default root `~/workspace/worktrees`).

### State location, migration, and the residual risk

The state directory used to default to `~/workspace/worktrees/.lanes` — inside the worktrees tree, which is the one tree every lane worker is tasked to operate in. That placement is what made the overseer panel's P1-4 repro possible: a worker could rewrite a manifest in the state directory, and one forged field (`worker_pid`, with `worker_start`) made `release --clean` delete another lane's live worktree. The default is now `~/.local/state/aep/lanes`, created on demand (mode 700 when the tool creates it). `AEP_LANES_DIR` overrides the location exactly as before.

**Scope honesty.** Placement removes the state from every tree a worker is tasked to operate in, and it closes the panel's repro. It is **not** a write boundary against a determined same-uid process: lane workers run unsandboxed as the operator's own uid, and that uid can write the new location too if a worker deliberately aims at it (the mode 700 binds other uids only). The residual risk is accepted and recorded here rather than claimed away: the coordinator's guarantees hold against workers that stay inside their tasked tree, including accidental and content-driven writes; a worker actively attacking the coordinator's state is outside this mechanism's threat model.

**Migration rule.** While any `*.json` manifest remains at the legacy location (`~/workspace/worktrees/.lanes`) and `AEP_LANES_DIR` is unset, `claim`, `release`, and `reap` refuse (exit 1) with one shared message naming the legacy path, the new default, and the two remedies:

1. Inspect the manifests at the legacy location, then run `lane-coord.sh migrate` to move them to the new default.
2. Or set `AEP_LANES_DIR` to the legacy path to keep operating there deliberately.

`status` is the exception: it still lists legacy lanes read-only, each line marked `legacy`, so an operator can see what is waiting on migration. No code path reads or settles legacy state for a mutating command — there is no dual-directory operation.

**Migration requires a quiescent legacy pool.** A live legacy launcher holds its lane's fence inside the legacy directory; moving the manifest without the fence would disconnect the two, letting the next claim settle the lane as interrupted while its worker still runs (and escapes capacity accounting). `migrate` therefore probes every legacy lane's fence first and refuses — naming the held lane — while any is held.

**Migrated lanes are quarantined.** Migration imports a manifest from a worker-writable tree, so its provenance is untrusted: moving it into the trusted state directory must not launder a planted manifest into ownership proof (the migration path itself was the follow-up panel's P1-3 repro — the four `release --clean` ownership signals are sound against *stale* manifests but cannot distinguish *planted* ones). `migrate` therefore stamps each imported lane with a marker under `$AEP_LANES_DIR/.quarantine/` (outside the manifest set). While the marker exists, `release --clean` and `reap` refuse for that lane; `status` marks the line `quarantined`; read paths and plain `release` work normally. The quarantine clears only per lane, by one of:

- `lane-coord.sh trust --name <name>` — the operator's confirmation after inspecting that lane's manifest, recorded as an `operator-trusted` entry in the lane's history log (outside the manifest itself); or
- a fresh `claim` of the same name that creates the worktree itself, re-stamping the manifest natively. A claim that instead *adopts* an existing worktree named by the migrated manifest does **not** discharge the marker: the claim's ownership gates passed on that manifest's own say-so, so adoption is not provenance (Codex P1 on the original fix).

**Operator notes.**

- Retire stale worktree copies of `lane-coord.sh` before first post-merge use. An old copy still defaults to the legacy location: one claim from it plants a legacy manifest, and the new copy will then refuse all claims until the migration above is performed.
- Lane state now lives under `~/.local/state`, outside the old backup path lists (which covered `~/workspace/worktrees`). Add `~/.local/state/aep` to any backup set that is expected to preserve lane history across a machine replacement.

### Subcommands

| Subcommand | Purpose |
| --- | --- |
| `claim --repo <abs path> --project <slug> --lane <slug> --branch <name> [--base <ref>] --worker <id> [--capacity <n>] [--path <extra> ...] --exec <command...>` | Claim a lane and run the worker in it. Prints `LANE: claimed <name> path=... branch=... epoch=...`; when the worker exits, prints `LANE: released <name> (worker exit <n>)` and exits with the worker's status. |
| `release --name <name> [--clean [--force-dirty]]` | The normal teardown path (see below). Without `--clean`, settles the claim and leaves the worktree in place. |
| `reap --name <name>` | Settle a claim whose launcher is provably dead, without touching the worktree. Refuses while the fence is held. |
| `status [--name <name>] [--capacity <n>]` | Show each lane's state, epoch, worker, fence state, and path, plus the pool line (`LANE: pool: <n> claimed of <capacity>`). |
| `migrate` | Move legacy-location manifests into the state dir, quarantining each imported lane (see *Migrated lanes are quarantined*). |
| `trust --name <name>` | Record the operator's per-lane confirmation for a quarantined migrated lane, clearing its quarantine marker. |
| `--self-test` | The built-in 30-case suite (also run in CI by the `script-tests` job). |

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

Each lane has one JSON manifest, `<name>.json` in the lanes directory, written atomically (temp file + rename) with fields serialized by a JSON encoder, so paths containing quotes or backslashes round-trip exactly: the claim-time write happens inside the capacity lock, as do reap/release updates; the launcher's worker-identity record (written just after the spawn) and its post-worker `released` update run outside the lock (still temp file + rename, so atomicity is unaffected):

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
| `worker_pid` | the spawned worker's PID, recorded by the launcher just after the spawn (0 until then); probed for liveness — never signalled — by takeover claims and `release --clean` |
| `worker_start` | the worker's `/proc` start time; pid + start time together identify the exact process across pid recycling (0 when the worker exited before it could be read) |
| `epoch` | claim generation: starts at 1, increments monotonically per lane across takeovers |
| `policy_integrity`, `policy_path`, `policy_sha256` | the claim-time policy outcome (`verified` / `operator-override` / `not-applicable`), the resolved policy path, and its SHA-256 (see *Claim-time policy integrity*) |
| `state` | `claimed`, `released`, `reaped`, or `cleaned` (set by `release --clean` once the validated worktree removal completes) |
| `claimed_at`, `updated_at` | UTC timestamps |

A per-lane history records claim, release, and settled-interrupted events with their epoch and worker.

### Capacity

At most **2** lanes may be in `claimed` state at once (default; `--capacity <n>` overrides per claim). The value is DeepCode's verified default, inherited deliberately; it is an operational knob, not a correctness property. The count is over manifests for coordinator-launched lanes, evaluated *after* the claim transaction auto-settles every provably-dead claim — a dead lane never holds capacity hostage.

### Fence semantics, stated exactly

The fence is an `flock` held by the launcher process on its own open file descriptor, for its lifetime. The worker is spawned with the fence (and capacity-lock) descriptors closed, so no descendant can keep the fence alive after the launcher dies. Therefore: the launcher's death frees the lock, and **acquiring the lock is the only proof of the launcher's death the tool accepts** — a later claim whose fence probe succeeds auto-settles the previous claim as interrupted (epoch increments; the worktree's contents are left exactly as they lie). The free fence does **not** prove the previous worker stopped: the worker runs with the fence closed precisely so nothing keeps the fence alive, and it can outlive its launcher. So a takeover claim — and `release --clean` — additionally require the manifest's recorded worker to be gone: if that exact process (pid + `/proc` start time) is still running, both refuse and name the pid; a pid recycled by an unrelated process (different start time) and a zombie both count as gone; an interrupted claim that recorded no worker cannot prove its worker stopped, and both refuse it conservatively. The tool signals no process, ever: no pid named in a manifest is ever killed — at most, a live recorded `worker_pid` makes takeover and cleanup refuse (fail closed), and a crafted manifest naming an innocent PID changes nothing else.

What is **not** fenced: any lane, worktree, or process not launched through the coordinator. The coordinator's guarantees cover coordinator-launched lanes only.

### Runbook: end a lane normally

`release` is the normal teardown path — not `reap`, and not manual worktree removal:

1. `bash scripts/lane-coord.sh release --name <name>` — settles the claim (state `released`, capacity freed). Refused while the fence is held: a lane whose launcher is still running is owned; hands off.
2. When the worktree itself should go away: `release --name <name> --clean`. Cleanup first requires the fence free and the manifest's recorded worker gone (see *Fence semantics, stated exactly*); then it validates four ownership signals, in order, and removes nothing on any mismatch: (1) the manifest exists and names this lane's repo/path/branch; (2) the repo's worktree list registers the path; (3) the branch checked out at the path is the manifest's branch; (4) the path is exactly the deterministic managed location. A dirty worktree is refused; `--clean --force-dirty` first archives the porcelain status and `git diff HEAD` to `$AEP_LANES_DIR/<name>.final-diff.patch`, then removes.

### Runbook: unstick a lane

1. `bash scripts/lane-coord.sh status --name <name>` — look at the fence state.
2. Fence **held** → the lane is owned by a live launcher. Hands off; there is nothing to unstick.
3. Fence **free** → the launcher is dead (that is what the free fence proves). Either `reap --name <name>` to settle the claim and leave the worktree, or simply make the next `claim` for the lane — it auto-settles the stale claim, increments the epoch, and proceeds, provided the previous worker has also exited. If that worker is still running, the claim (and `release --clean`) refuses and names its pid: the worker belongs to the previous claim's owner, who stops it by their own means — the coordinator never signals it. Once it has exited, retry.
4. Never delete a manifest or a fence file by hand to force a lane free; that destroys the epoch history the next claim relies on.

## Activation checklist

Merging code is not activation. After this branch lands, verify each item against the **live** environment:

- [ ] Both skill copies carry the wiring (Tasks 3 and 8 edited the repo copies in `skills/` and the live copies the runtime loads in `~/workspace/custom-skills/`). Check with the Acceptance Criterion 6 greps against the live files: `mechanical_verify.py` appears 2× in the live SDD skill; `lane-coord.sh` appears 3× in the live overnight-parallel-lanes skill.
- [ ] Run one real `bash scripts/boot-gate.sh` and confirm the fifth check line is `BOOT-GATE: policy ok: ...` (or an understood SKIP).
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
