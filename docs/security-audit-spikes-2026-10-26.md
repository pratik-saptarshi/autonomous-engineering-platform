# Security-audit adoption spikes — 2026-10-26 (Task P0)

Spike record for Part 1 of the deeper-integration adoption plan. Execution
base: worktree `feat/audit-adoption` at `e312e8e`. One section per step;
each section ends with a stated decision input and nothing beyond it.
Outside the schema JSON artifacts embedded below, verdict terms are
written namespaced (for example `audit:confirmed`).

## Step 0: Read-back gate

Command (fetch first): `git fetch origin`, then the checks below.

Check 1 — PR #69 state (ghg read-back):

```text
$ GHG_ACTOR=audit-adoption-exec ~/go/bin/ghg run -- pr view 69 --repo pratik-saptarshi/autonomous-engineering-platform --json state,mergedAt,mergeCommit
{"mergeCommit":{"oid":"e312e8e08de296e8062eb8e2381361c8b3c8bfb6"},"mergedAt":"2026-10-27T03:19:04Z","state":"MERGED"}
```

Observed: state `MERGED`; merge commit
`e312e8e08de296e8062eb8e2381361c8b3c8bfb6`; merged at
`2026-10-27T03:19:04Z`.

Check 2 — vendored skill tree present in this worktree:

```text
$ ls -ld reference/security-audit-skill/skills/security-audit/
drwxrws--- 1 root nogroup 928 Oct 27 03:54 reference/security-audit-skill/skills/security-audit/
```

Observed: directory present.

Check 3 — both validators present at the brief's paths:

```text
$ ls -l reference/security-audit-skill/skills/security-audit/validate-findings.cjs reference/security-audit-skill/skills/security-audit/validate-coverage-ledger.cjs reference/security-audit-skill/skills/security-audit/report-schema.json
-rw-rw---- 1 root nogroup 14494 Oct 27 03:54 reference/security-audit-skill/skills/security-audit/report-schema.json
-rwxrwx--- 1 root nogroup 33522 Oct 27 03:54 reference/security-audit-skill/skills/security-audit/validate-coverage-ledger.cjs
-rwxrwx--- 1 root nogroup 28806 Oct 27 03:54 reference/security-audit-skill/skills/security-audit/validate-findings.cjs
```

Observed: `validate-findings.cjs` (28806 bytes) and
`validate-coverage-ledger.cjs` (33522 bytes) both present, with
`report-schema.json` (14494 bytes). Node: `v24.22.1`.

Check 4 — HEAD at or descended from `e312e8e`:

```text
$ git rev-parse HEAD
e312e8e08de296e8062eb8e2381361c8b3c8bfb6
$ git merge-base --is-ancestor e312e8e08de296e8062eb8e2381361c8b3c8bfb6 HEAD && echo DESCENDED_OR_EQUAL
DESCENDED_OR_EQUAL
```

Observed: HEAD is exactly
`e312e8e08de296e8062eb8e2381361c8b3c8bfb6`
(`chore(vendor): vendor security-audit-skill at c1c8a8c into reference/security-audit-skill (#69)`).

All four checks pass.

Decision input: input to Part 1 execution — the read-back gate passes;
execution proceeds on this base.

## Step 1: Recorded basis for the sandbox question (analysis Q1 — settled by record, no spike)

Factual basis, cited to `~/TOOLS.md`, Podman section (installed
2026-10-24): network-namespace creation is an outer-environment hard
block (netavark `setns` denied, so host networking only), and
`podman exec` into a running container is also an outer-environment hard
block (`setns mnt` denied). Those denials, not any measurement in this
task, are the factual basis for the environment condition.

Corrected current state, recorded per the controller's R3 ruling from
`~/TOOLS.md` as updated 2026-10-26 (the brief's Step 1 sentence stating
podman is not installed on the current VM is stale and is NOT recorded
here): podman 4.9.3 IS installed via apt, but the `/etc/containers/`
runbook configs were never rewritten — the package default config is in
place, so the surviving storage tree under
`~/.local/share/containers/` is not wired in and podman is NOT in its
verified-working state. The `--network none` isolation probe remains
UN-RUN under Pratik's explicit ruling of 2026-10-26 ("leave podman
installed, no probe"). No probe was run in this task.

Any future environment seeking execution-based confirmation
re-provisions podman per `~/TOOLS.md` and re-probes as its own
precondition.

Decision input: input to Election E-verdict — Q1 is settled by this
record; re-probing belongs to that election, not to this plan.

## Step 2: Q2 schema re-expression

Method: two separate artifacts, each a top-level JSON array holding one
`audit:confirmed` record, each run separately through the vendored
findings validator. Panel-era source locations cite the tree the panel
reviewed (commit `37f0406`, the pre-remediation head in
`review_panel_report.md`); both findings were remediated after the
panel, which is noted inside each record. Validator success proves
format and consistency only (vendored
`VALIDATION-AND-REPORTING.md`, Phase 4); the distortion verdicts below
are the semantic record the validator cannot give.

### Artifact 1 — execution-based re-expression of the 2026-10-24 panel P0

Subject: the panel P0 "a sealed receipts PASS binds a label, not a
tree" (`~/workspace/goals/autonomous-code-defense-factory/files/review_panel_report.md`,
finding P0-1; remediation was PR #42).

Command and outcome (verbatim):

```text
$ node reference/security-audit-skill/skills/security-audit/validate-findings.cjs /tmp/p0-spikes/q2-artifact1-execution-based.json
PASS: 1 findings valid
exit=0
```

Validator verdict (Artifact 1): PASS (exit 0, `PASS: 1 findings valid`).

Distortion fields (Artifact 1):

- `execution.attacker_perspective` — distortion (framing): there is no
  external attacker in this defect. The position the field names is
  occupied by a same-uid process able to write the worktree after
  sealing, and in the honest path by no adversary at all (an operator
  resuming across sessions, or a detached descendant of the verified
  run). The field forces an adversarial label onto a stale-evidence
  defect.
- `execution.payloads` — distortion (framing): the entries are
  post-seal tree mutations (a Makefile target rewrite; a detached
  descendant's mutation), not attacker payloads delivered to a target
  interface. They are recorded under the `payloads` label because the
  schema requires the field.
- `trace` — distortion (shape): the schema's trace is a linear
  entrypoint-to-propagation-to-sink source path. This defect is a
  composition across the validator, a shipped skill's completion gate,
  and process lifetime; the sink entry is a documentation-sanctioned
  completion decision (`SKILL.md`), not a code sink. The mapping is
  faithful in content and forced in shape.
- All other fields — none: `fingerprint`, `title`, `description`,
  `root_cause`, `intended_behavior`, `evidence`, `conditions`
  (`timing_dependency` and `data_state` fit exactly),
  `execution.instructions`, `execution.observed_result`,
  `remediation`, `severity`, and `confidence` each carry the finding
  without distortion.

Execution-object fit answer (Artifact 1): YES — the required
`execution` object fits without fabricating its factual content. The
record's confirmation basis is a panel reproduction, not target-code
execution by the hunting auditor, but that reproduction was run through
the target's native interface (the real `mechanical_verify.py` CLI):
`instructions` describe exactly that reproduction and
`observed_result` is the result actually observed (`RECEIPTS: PASS`,
rc 0, on a tree whose test target had been made to fail), reproduced
independently three times. The distortion in this artifact is confined
to the `attacker_perspective` and `payloads` framing above; the
execution facts themselves are undistorted.

Final form (Artifact 1, `/tmp/p0-spikes/q2-artifact1-execution-based.json`):

```json
[
  {
    "verdict": "confirmed",
    "fingerprint": "aep.receipts.sealed-pass-binds-label-not-tree",
    "title": "Sealed verification-receipts PASS binds a label, not the tree it gates",
    "description": "In the panel-era tree (37f0406), check_receipts validates a receipts file's internal chain and per-task exit codes only. It takes no root, HEAD, tree-digest, or time input and no receipt field records any of them, so a segment sealed against one tree state returns PASS when consulted against a different, now-failing tree state. The shipped subagent-driven-development skill sanctions completion through this check-only path, and a setsid-detached descendant can mutate the tree after a successful verify seals, making the gap attacker-timed. Historical finding: remediated after the panel by PR #42, which binds receipts to (root, HEAD, tree digest).",
    "root_cause": "Receipts bind a label, not an artifact: the run-start, command, and completion records identify a task and a self-consistent hash chain, but record nothing about the root, HEAD, or tree digest they were produced from, and the checker has no corresponding input to compare against.",
    "intended_behavior": "A receipts PASS describes a specific tree: check-receipts refuses or reports stale any segment whose recorded (root, HEAD, tree digest) does not match the tree it is asked to vouch for, so a PASS sealed against an earlier tree state cannot complete a task on a changed tree.",
    "trace": [
      {
        "kind": "entrypoint",
        "file": "scripts/mechanical_verify.py",
        "line": 529,
        "scope": "check_receipts",
        "description": "Panel-era check_receipts(receipts_path, task) entry point: its only inputs are the receipts file path and the task id; it accepts no root, HEAD, tree digest, or time."
      },
      {
        "kind": "propagation",
        "file": "scripts/mechanical_verify.py",
        "line": 363,
        "scope": "RECEIPT_FIELDS",
        "description": "Receipt records carry ts, task, command_id, argv, exit_code, timed_out, duration_ms, stdout_sha256, stderr_sha256, and chain_sha256; none records root, HEAD, or tree digest, and ts is never consulted during validation."
      },
      {
        "kind": "sink",
        "file": "skills/subagent-driven-development/SKILL.md",
        "line": 51,
        "scope": "completion gate",
        "description": "The shipped SDD skill sanctions marking a task complete by validating receipts generated earlier in the run with check-receipts instead of running a fresh verify, so the unbound PASS is consumed as completion evidence, including across sessions that resume trusting the workspace receipts file."
      }
    ],
    "evidence": [
      {
        "file": "scripts/mechanical_verify.py",
        "line": 529,
        "description": "Panel Phase 10 EXP1, through the real CLI: verify on a Makefile tree with test target @true sealed with rc 0; the Makefile was rewritten to @false; check-receipts still returned rc 0 and printed RECEIPTS: PASS. Independently reproduced three times (Hawk Phase 3 probe, Security Phase 5 real-CLI repro, Phase 10 EXP1)."
      },
      {
        "file": "scripts/mechanical_verify.py",
        "line": 363,
        "description": "Panel Phase 10 EXP4: a setsid-detached descendant survived a successful verify, mutated the tree after sealing, and the stale check then validated, closing the fresh-verify defence."
      }
    ],
    "conditions": [
      {
        "kind": "timing_dependency",
        "description": "The tree mutates after verify seals the segment and before check-receipts is consulted, including mutation by a setsid-detached descendant that survives the successful verify."
      },
      {
        "kind": "data_state",
        "description": "The receipts file remains internally self-consistent while the worktree content it purports to describe has changed; no malicious mutation is required - an honest cross-session resume occupies the same position."
      }
    ],
    "execution": {
      "attacker_perspective": "A same-uid process able to write the worktree after sealing occupies the attacker position; in the honest path no attacker is required, because an operator resuming across sessions or a detached descendant of the verified run occupies the same position.",
      "payloads": [
        "Makefile test target rewritten from @true to @false after the segment was sealed",
        "A setsid-detached descendant that mutates the worktree after a successful verify exits"
      ],
      "instructions": [
        "Create a scratch tree whose Makefile test target is @true and run verify through the real CLI; observe rc 0 and a sealed segment.",
        "Rewrite the Makefile test target to @false without re-running verify.",
        "Run check-receipts for the task through the real CLI and observe the verdict.",
        "Repeat with a setsid-detached descendant mutating the tree after a successful verify, as in panel Phase 10 EXP4."
      ],
      "observed_result": "check-receipts printed RECEIPTS: PASS with rc 0 for a tree whose test target now fails; the stale-PASS result was reproduced independently three times through the real CLI."
    },
    "remediation": {
      "strategy": "Bind receipts to the artifact: run-start and completion records carry (root, HEAD, tree digest), check-receipts gains the corresponding inputs and refuses a segment whose binding does not match the tree it is asked to vouch for, and the process group is reaped on every exit path (panel recommendation R1; landed after the panel by PR #42).",
      "code_changes": [
        {
          "file_name": "scripts/mechanical_verify.py",
          "fixed_code": "Record a binding {root, head, tree_digest} on the run-start and run-complete records; check_receipts recomputes the digest for the recorded head (git mode) or the live tree (fs mode) and returns a stale/refusal verdict on mismatch instead of PASS."
        }
      ]
    },
    "severity": {
      "likelihood": {
        "score": "medium",
        "reason": "Exploitation needs post-seal write access to the worktree or a surviving detached descendant, but the honest cross-session resume path reaches the same stale PASS with no adversary at all."
      },
      "impact": {
        "score": "high",
        "reason": "The platform's flagship guarantee - mechanical evidence gating completion - is void along its sanctioned check-only path: a failing tree can be marked complete on evidence about a different tree."
      },
      "overall_severity": "high"
    },
    "confidence": {
      "score": "high",
      "reason": "Three independent reproductions through the real CLI plus panel Phase 10 verification (rows 1 and 2, both CONFIRMED)."
    }
  }
]
```

### Artifact 2 — static-proof record (confirmation by trace only)

Subject: panel finding P1-6, the repo watchdog broken on its common
path (panel report, finding P1-6; Phase 10 row 13, `audit:confirmed` by
decisive code read). The record is an `audit:confirmed` whose entire
confirmation is a static trace of one file: call order, the
`set -euo pipefail` header, and bash function-definition semantics. No
target code was executed for this record — the confirmation type this
plan treats as primary in this VM.

Command and outcome (verbatim):

```text
$ node reference/security-audit-skill/skills/security-audit/validate-findings.cjs /tmp/p0-spikes/q2-artifact2-static-proof.json
PASS: 1 findings valid
exit=0
```

Validator verdict (Artifact 2): PASS (exit 0, `PASS: 1 findings valid`).

Distortion fields (Artifact 2):

- `execution.observed_result` — distortion (forced): the field as
  designed requires a nonempty factual result of an execution. Nothing
  was executed, so the field is populated with an explicit statement
  that no execution result was observed and that the claimed result is
  inferred from the trace alone. The validator passes it (visible
  text), but semantically the field carries a disclaimer, not a
  result. Populating it as designed — an observed exit 127 — would
  fabricate an execution result.
- `execution.payloads` — distortion (forced): no payload exists when
  nothing is executed and no input is supplied; the field is populated
  with a statement of that fact because the schema requires at least
  one entry.
- `execution.attacker_perspective` — distortion (framing): there is no
  attacker; the field carries the operator/cron position and must
  additionally assert the non-execution to stay truthful.
- `execution.instructions` — distortion (partial): the entries describe
  a static reading procedure, not a bounded reproduction execution;
  they are instructions for re-walking the trace, which is the only
  honest instruction set this record has.
- All other fields — none: `fingerprint`, `title`, `description`,
  `root_cause`, `intended_behavior`, `trace`, `evidence`,
  `conditions`, `remediation`, `severity`, and `confidence` each carry
  the finding without distortion.

Execution-object fit answer (Artifact 2): NO — the verbatim schema's
required `execution` object (`report-schema.json`, the `audit:confirmed`
branch: `attacker_perspective`, `payloads`, `instructions`,
`observed_result`) cannot be populated as designed when nothing was
executed. The only validator-passing population re-purposes the fields
as disclaimers, which is itself the distortion recorded above; a
population faithful to the fields' designed meaning would require
fabricating an `observed_result`. This forces the profile branch for
static-proof records specifically.

Final form (Artifact 2, `/tmp/p0-spikes/q2-artifact2-static-proof.json`):

```json
[
  {
    "verdict": "confirmed",
    "fingerprint": "aep.watchdog.stop-daemon-called-before-definition",
    "title": "Watchdog DB-unchanged path calls stop_daemon before its definition, so the steady-state path dies with exit 127",
    "description": "In the panel-era tree (37f0406), scripts/watchdog-backup.sh executes top-down under set -euo pipefail. Its DB-unchanged branch - the steady-state path - calls stop_daemon at line 204, while the function is not defined until line 212. At the call site no such function exists, so the branch fails with command-not-found (exit 127) and the watchdog is broken on its common path. Confirmation is by static trace only: file order, the set -euo pipefail header, and bash function-definition semantics decide the claim; no target code was executed for this record. Historical finding: panel P1-6, confirmed by decisive code read (Phase 10 row 13).",
    "root_cause": "Function definition order: the stop_daemon call in the DB-unchanged branch textually and executionally precedes the stop_daemon() definition later in the same file, so the name is unresolved when the branch runs.",
    "intended_behavior": "Every function is defined before any call site that can execute it, so the DB-unchanged steady-state path runs drive catch-up, pruning, and the daemon stop to completion instead of dying on an unresolved function name.",
    "trace": [
      {
        "kind": "entrypoint",
        "file": "scripts/watchdog-backup.sh",
        "line": 204,
        "scope": "DB-unchanged branch",
        "description": "When the current DB checksum equals the last backed-up checksum, the branch runs drive catch-up and pruning and then calls stop_daemon."
      },
      {
        "kind": "propagation",
        "file": "scripts/watchdog-backup.sh",
        "line": 28,
        "scope": "script header",
        "description": "The script runs under set -euo pipefail, so an unresolved function call terminates the script instead of being skipped."
      },
      {
        "kind": "sink",
        "file": "scripts/watchdog-backup.sh",
        "line": 212,
        "scope": "stop_daemon definition",
        "description": "stop_daemon() is defined here, after the line-204 call site; under bash top-down execution the definition has not been evaluated when the DB-unchanged branch calls the name, yielding command-not-found and exit 127."
      }
    ],
    "evidence": [
      {
        "file": "scripts/watchdog-backup.sh",
        "line": 204,
        "description": "Call site of stop_daemon in the DB-unchanged branch, as read in the panel-era source."
      },
      {
        "file": "scripts/watchdog-backup.sh",
        "line": 212,
        "description": "Definition of stop_daemon() eight lines after its first call site, as read in the panel-era source; the panel's Phase 10 verdict for this finding was CONFIRMED by decisive code read."
      }
    ],
    "conditions": [
      {
        "kind": "data_state",
        "description": "The database is unchanged since the last backup, which selects the branch containing the early call; that is the steady-state condition, not an edge case."
      },
      {
        "kind": "system_configuration",
        "description": "The script is executed directly by bash as shipped; nothing sourced earlier defines stop_daemon."
      }
    ],
    "execution": {
      "attacker_perspective": "No attacker and no execution: the position is an operator or cron invoking the watchdog on its steady-state path. This field carries that operator perspective because the schema requires the field; this record's confirmation is a static trace, not an execution.",
      "payloads": [
        "No payload exists for this record: no target code was executed and no input was supplied. This entry is a schema-required field populated with that statement of fact."
      ],
      "instructions": [
        "Static trace only - do not execute: read scripts/watchdog-backup.sh in the panel-era tree (37f0406) in file order.",
        "Observe set -euo pipefail at line 28, the stop_daemon call at line 204 in the DB-unchanged branch, and the stop_daemon() definition at line 212.",
        "Conclude from bash top-down function-definition semantics that the call resolves to no defined function on that path."
      ],
      "observed_result": "No execution result was observed for this record. The claimed result is inferred solely from the static trace (call at line 204 precedes definition at line 212 under set -euo pipefail at line 28, yielding command-not-found exit 127 on that path); writing an observed exit code here as if it had been run would fabricate an execution result."
    },
    "remediation": {
      "strategy": "Move the stop_daemon() definition above its first call site (or restructure so all function definitions precede all executable statements) in scripts/watchdog-backup.sh, so every branch calls only already-defined functions.",
      "code_changes": [
        {
          "file_name": "scripts/watchdog-backup.sh",
          "fixed_code": "Define stop_daemon() with the other function definitions before the DB-checksum branch that calls it at the former line 204."
        }
      ]
    },
    "severity": {
      "likelihood": {
        "score": "high",
        "reason": "The DB-unchanged branch is the steady-state path, so ordinary repeated watchdog runs reach the defective call site."
      },
      "impact": {
        "score": "medium",
        "reason": "The watchdog dies on its common path, breaking the backup/restart cycle it exists to perform until the ordering is fixed."
      },
      "overall_severity": "medium"
    },
    "confidence": {
      "score": "high",
      "reason": "The static trace is complete within one file: call order, definition order, and set -euo pipefail are all source-visible, and the panel confirmed the finding by decisive code read."
    }
  }
]
```

Decision input: input to Task A1 — per-artifact distortion records
above (Artifact 1: framing distortion in two `execution` fields and the
`trace` shape only, execution facts undistorted; Artifact 2: the
`execution` object cannot be populated as designed for a static-proof
record).

## Step 3: Q3 ledger scale test

Inventory: the full `scripts/` tree of this worktree, enumerated with
`find scripts -type f` — 32 files: `scripts/apply-domain-blocks.sh`,
`scripts/boot-gate.sh`, `scripts/lane-coord.sh`,
`scripts/mechanical_verify.py`, `scripts/policy.data`,
`scripts/scan-gate.sh`, `scripts/watchdog-backup.sh`, the ten
`scripts/orch/*.py` modules (`__init__`, `adapters_beads`,
`adapters_fixture`, `adapters_github`, `claims`, `cli`, `engine`,
`model`, `observe`, `workflow`), `scripts/tests/survivor_driver.py`,
the nine `scripts/tests/test_*.py` / `test_watchdog.sh` files, and the
four `scripts/tests/fixtures/orch/*.json` files.

Derivation (full canonical tuple, per Task A2 Step 2 of the plan and
vendored `RECONNAISSANCE.md`): one unit for every combination of
surface (each inventoried file) x trust boundary (assigned by file
role: operator invocation of a shipped script; external tracker and CLI
input to the orchestration package; test harness execution boundary;
fixture input to the test harness) x subsystem (the file's directory)
x attack class (all nine ordinary classes in vendored
`ATTACK-CLASSES.md`: Injection; Access control; Resource and file
handling; Cryptography and secrets; Business logic; Feature abuse and
data leakage; Chained vulnerabilities and trust boundaries; Wildcard;
Obvious things) x lifecycle (Initial review; Steady-state operation).
Each unit carries `canonical_refs` with all five references and a
`coverage_id` derived by the vendored rule (RFC 3986 percent-encoding,
uppercase `%HH`, joined with `::`). All units are `planned`
(`agent_id: null`, empty evidence), `wave: 1`, `prior_status: "none"`,
sorted lexicographically by `coverage_id`.

Counts: 32 surfaces x 9 attack classes x 2 lifecycles = 576 units.

Command and outcome (verbatim):

```text
$ node reference/security-audit-skill/skills/security-audit/validate-coverage-ledger.cjs /tmp/p0-spikes/q3-synthetic-ledger.json
PASS: 576 coverage units valid
exit=0
```

Validator verdict (Q3): PASS (exit 0, `PASS: 576 coverage units valid`).

File size vs cap: the ledger file is 664535 bytes. The validator cap
is 5 MiB = 5242880 bytes; the synthetic ledger uses 12.7% of the cap.
Mean unit size is 1154 bytes, at which the cap holds about 4545 units —
inside the vendored estimate of roughly 2000-5000 realistic units per
5 MiB (`RECONNAISSANCE.md`).

Final form (Q3, `/tmp/p0-spikes/q3-synthetic-ledger.json`):

```json
[
  {
    "coverage_id": "scripts%2Fapply-domain-blocks.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/apply-domain-blocks.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/apply-domain-blocks.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/apply-domain-blocks.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fapply-domain-blocks.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/apply-domain-blocks.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/apply-domain-blocks.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/apply-domain-blocks.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fapply-domain-blocks.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/apply-domain-blocks.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/apply-domain-blocks.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/apply-domain-blocks.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fapply-domain-blocks.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/apply-domain-blocks.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/apply-domain-blocks.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/apply-domain-blocks.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fapply-domain-blocks.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/apply-domain-blocks.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/apply-domain-blocks.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/apply-domain-blocks.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fapply-domain-blocks.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/apply-domain-blocks.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/apply-domain-blocks.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/apply-domain-blocks.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fapply-domain-blocks.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/apply-domain-blocks.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/apply-domain-blocks.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/apply-domain-blocks.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fapply-domain-blocks.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/apply-domain-blocks.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/apply-domain-blocks.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/apply-domain-blocks.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fapply-domain-blocks.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/apply-domain-blocks.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/apply-domain-blocks.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/apply-domain-blocks.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fapply-domain-blocks.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/apply-domain-blocks.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/apply-domain-blocks.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/apply-domain-blocks.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fapply-domain-blocks.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/apply-domain-blocks.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/apply-domain-blocks.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/apply-domain-blocks.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fapply-domain-blocks.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/apply-domain-blocks.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/apply-domain-blocks.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/apply-domain-blocks.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fapply-domain-blocks.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/apply-domain-blocks.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/apply-domain-blocks.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/apply-domain-blocks.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fapply-domain-blocks.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/apply-domain-blocks.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/apply-domain-blocks.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/apply-domain-blocks.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fapply-domain-blocks.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/apply-domain-blocks.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/apply-domain-blocks.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/apply-domain-blocks.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fapply-domain-blocks.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/apply-domain-blocks.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/apply-domain-blocks.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/apply-domain-blocks.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fapply-domain-blocks.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/apply-domain-blocks.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/apply-domain-blocks.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/apply-domain-blocks.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fapply-domain-blocks.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/apply-domain-blocks.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/apply-domain-blocks.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/apply-domain-blocks.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fboot-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/boot-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/boot-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/boot-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fboot-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/boot-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/boot-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/boot-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fboot-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/boot-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/boot-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/boot-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fboot-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/boot-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/boot-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/boot-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fboot-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/boot-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/boot-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/boot-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fboot-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/boot-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/boot-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/boot-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fboot-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/boot-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/boot-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/boot-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fboot-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/boot-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/boot-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/boot-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fboot-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/boot-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/boot-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/boot-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fboot-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/boot-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/boot-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/boot-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fboot-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/boot-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/boot-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/boot-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fboot-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/boot-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/boot-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/boot-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fboot-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/boot-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/boot-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/boot-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fboot-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/boot-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/boot-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/boot-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fboot-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/boot-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/boot-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/boot-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fboot-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/boot-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/boot-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/boot-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fboot-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/boot-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/boot-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/boot-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fboot-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/boot-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/boot-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/boot-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Flane-coord.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/lane-coord.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/lane-coord.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/lane-coord.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Flane-coord.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/lane-coord.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/lane-coord.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/lane-coord.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Flane-coord.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/lane-coord.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/lane-coord.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/lane-coord.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Flane-coord.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/lane-coord.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/lane-coord.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/lane-coord.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Flane-coord.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/lane-coord.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/lane-coord.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/lane-coord.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Flane-coord.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/lane-coord.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/lane-coord.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/lane-coord.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Flane-coord.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/lane-coord.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/lane-coord.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/lane-coord.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Flane-coord.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/lane-coord.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/lane-coord.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/lane-coord.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Flane-coord.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/lane-coord.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/lane-coord.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/lane-coord.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Flane-coord.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/lane-coord.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/lane-coord.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/lane-coord.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Flane-coord.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/lane-coord.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/lane-coord.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/lane-coord.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Flane-coord.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/lane-coord.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/lane-coord.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/lane-coord.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Flane-coord.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/lane-coord.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/lane-coord.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/lane-coord.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Flane-coord.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/lane-coord.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/lane-coord.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/lane-coord.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Flane-coord.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/lane-coord.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/lane-coord.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/lane-coord.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Flane-coord.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/lane-coord.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/lane-coord.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/lane-coord.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Flane-coord.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/lane-coord.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/lane-coord.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/lane-coord.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Flane-coord.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/lane-coord.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/lane-coord.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/lane-coord.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fmechanical_verify.py::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/mechanical_verify.py",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/mechanical_verify.py",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fmechanical_verify.py::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/mechanical_verify.py",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/mechanical_verify.py",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fmechanical_verify.py::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/mechanical_verify.py",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/mechanical_verify.py",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fmechanical_verify.py::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/mechanical_verify.py",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/mechanical_verify.py",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fmechanical_verify.py::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/mechanical_verify.py",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/mechanical_verify.py",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fmechanical_verify.py::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/mechanical_verify.py",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/mechanical_verify.py",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fmechanical_verify.py::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/mechanical_verify.py",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/mechanical_verify.py",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fmechanical_verify.py::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/mechanical_verify.py",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/mechanical_verify.py",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fmechanical_verify.py::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/mechanical_verify.py",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/mechanical_verify.py",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fmechanical_verify.py::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/mechanical_verify.py",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/mechanical_verify.py",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fmechanical_verify.py::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/mechanical_verify.py",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/mechanical_verify.py",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fmechanical_verify.py::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/mechanical_verify.py",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/mechanical_verify.py",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fmechanical_verify.py::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/mechanical_verify.py",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/mechanical_verify.py",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fmechanical_verify.py::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/mechanical_verify.py",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/mechanical_verify.py",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fmechanical_verify.py::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/mechanical_verify.py",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/mechanical_verify.py",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fmechanical_verify.py::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/mechanical_verify.py",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/mechanical_verify.py",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fmechanical_verify.py::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/mechanical_verify.py",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/mechanical_verify.py",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fmechanical_verify.py::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/mechanical_verify.py",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/mechanical_verify.py",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2F__init__.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/__init__.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/__init__.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/__init__.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2F__init__.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/__init__.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/__init__.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/__init__.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2F__init__.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/__init__.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/__init__.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/__init__.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2F__init__.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/__init__.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/__init__.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/__init__.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2F__init__.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/__init__.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/__init__.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/__init__.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2F__init__.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/__init__.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/__init__.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/__init__.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2F__init__.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/__init__.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/__init__.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/__init__.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2F__init__.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/__init__.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/__init__.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/__init__.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2F__init__.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/__init__.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/__init__.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/__init__.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2F__init__.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/__init__.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/__init__.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/__init__.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2F__init__.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/__init__.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/__init__.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/__init__.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2F__init__.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/__init__.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/__init__.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/__init__.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2F__init__.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/__init__.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/__init__.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/__init__.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2F__init__.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/__init__.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/__init__.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/__init__.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2F__init__.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/__init__.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/__init__.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/__init__.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2F__init__.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/__init__.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/__init__.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/__init__.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2F__init__.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/__init__.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/__init__.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/__init__.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2F__init__.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/__init__.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/__init__.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/__init__.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_beads.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_beads.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_beads.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_beads.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_beads.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_beads.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_beads.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_beads.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_beads.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_beads.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_beads.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_beads.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_beads.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_beads.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_beads.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_beads.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_beads.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_beads.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_beads.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_beads.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_beads.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_beads.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_beads.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_beads.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_beads.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_beads.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_beads.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_beads.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_beads.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_beads.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_beads.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_beads.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_beads.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_beads.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_beads.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_beads.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_beads.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_beads.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_beads.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_beads.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_beads.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_beads.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_beads.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_beads.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_beads.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_beads.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_beads.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_beads.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_beads.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_beads.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_beads.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_beads.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_beads.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_beads.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_fixture.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_fixture.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_fixture.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_fixture.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_fixture.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_fixture.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_fixture.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_fixture.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_fixture.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_fixture.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_fixture.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_fixture.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_fixture.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_fixture.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_fixture.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_fixture.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_fixture.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_fixture.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_fixture.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_fixture.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_fixture.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_fixture.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_fixture.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_fixture.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_fixture.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_fixture.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_fixture.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_fixture.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_fixture.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_fixture.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_fixture.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_fixture.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_fixture.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_fixture.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_fixture.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_fixture.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_fixture.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_fixture.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_fixture.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_fixture.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_fixture.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_fixture.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_fixture.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_fixture.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_fixture.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_fixture.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_fixture.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_fixture.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_fixture.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_fixture.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_fixture.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_fixture.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_fixture.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_fixture.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_fixture.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_fixture.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_fixture.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_fixture.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_fixture.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_fixture.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_fixture.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_fixture.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_fixture.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_fixture.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_fixture.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_fixture.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_fixture.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_fixture.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_fixture.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_fixture.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_fixture.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_fixture.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_github.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_github.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_github.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_github.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_github.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_github.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_github.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_github.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_github.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_github.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_github.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_github.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_github.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_github.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_github.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_github.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_github.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_github.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_github.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_github.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_github.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_github.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_github.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_github.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_github.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_github.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_github.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_github.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_github.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_github.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_github.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_github.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_github.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_github.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_github.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_github.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_github.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_github.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_github.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_github.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_github.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_github.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_github.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_github.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_github.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_github.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_github.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_github.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_github.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_github.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/adapters_github.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/adapters_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fadapters_github.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/adapters_github.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/adapters_github.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/adapters_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fclaims.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/claims.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/claims.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/claims.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fclaims.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/claims.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/claims.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/claims.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fclaims.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/claims.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/claims.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/claims.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fclaims.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/claims.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/claims.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/claims.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fclaims.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/claims.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/claims.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/claims.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fclaims.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/claims.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/claims.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/claims.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fclaims.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/claims.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/claims.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/claims.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fclaims.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/claims.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/claims.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/claims.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fclaims.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/claims.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/claims.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/claims.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fclaims.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/claims.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/claims.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/claims.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fclaims.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/claims.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/claims.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/claims.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fclaims.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/claims.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/claims.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/claims.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fclaims.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/claims.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/claims.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/claims.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fclaims.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/claims.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/claims.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/claims.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fclaims.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/claims.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/claims.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/claims.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fclaims.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/claims.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/claims.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/claims.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fclaims.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/claims.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/claims.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/claims.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fclaims.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/claims.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/claims.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/claims.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fcli.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/cli.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/cli.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fcli.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/cli.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/cli.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fcli.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/cli.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/cli.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fcli.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/cli.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/cli.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fcli.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/cli.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/cli.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fcli.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/cli.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/cli.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fcli.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/cli.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/cli.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fcli.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/cli.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/cli.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fcli.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/cli.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/cli.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fcli.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/cli.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/cli.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fcli.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/cli.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/cli.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fcli.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/cli.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/cli.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fcli.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/cli.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/cli.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fcli.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/cli.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/cli.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fcli.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/cli.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/cli.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fcli.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/cli.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/cli.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fcli.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/cli.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/cli.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fcli.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/cli.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/cli.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fengine.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/engine.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/engine.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fengine.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/engine.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/engine.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fengine.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/engine.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/engine.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fengine.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/engine.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/engine.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fengine.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/engine.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/engine.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fengine.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/engine.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/engine.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fengine.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/engine.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/engine.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fengine.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/engine.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/engine.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fengine.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/engine.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/engine.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fengine.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/engine.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/engine.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fengine.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/engine.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/engine.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fengine.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/engine.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/engine.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fengine.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/engine.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/engine.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fengine.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/engine.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/engine.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fengine.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/engine.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/engine.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fengine.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/engine.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/engine.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fengine.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/engine.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/engine.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fengine.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/engine.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/engine.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fmodel.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/model.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/model.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fmodel.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/model.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/model.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fmodel.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/model.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/model.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fmodel.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/model.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/model.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fmodel.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/model.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/model.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fmodel.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/model.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/model.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fmodel.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/model.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/model.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fmodel.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/model.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/model.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fmodel.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/model.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/model.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fmodel.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/model.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/model.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fmodel.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/model.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/model.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fmodel.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/model.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/model.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fmodel.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/model.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/model.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fmodel.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/model.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/model.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fmodel.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/model.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/model.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fmodel.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/model.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/model.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fmodel.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/model.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/model.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fmodel.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/model.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/model.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fobserve.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/observe.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/observe.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fobserve.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/observe.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/observe.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fobserve.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/observe.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/observe.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fobserve.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/observe.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/observe.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fobserve.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/observe.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/observe.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fobserve.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/observe.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/observe.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fobserve.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/observe.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/observe.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fobserve.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/observe.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/observe.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fobserve.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/observe.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/observe.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fobserve.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/observe.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/observe.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fobserve.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/observe.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/observe.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fobserve.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/observe.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/observe.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fobserve.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/observe.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/observe.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fobserve.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/observe.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/observe.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fobserve.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/observe.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/observe.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fobserve.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/observe.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/observe.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fobserve.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/observe.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/observe.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fobserve.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/observe.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/observe.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fworkflow.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/workflow.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/workflow.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fworkflow.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/workflow.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/workflow.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fworkflow.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/workflow.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/workflow.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fworkflow.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/workflow.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/workflow.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fworkflow.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/workflow.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/workflow.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fworkflow.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/workflow.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/workflow.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fworkflow.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/workflow.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/workflow.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fworkflow.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/workflow.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/workflow.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fworkflow.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/workflow.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/workflow.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fworkflow.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/workflow.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/workflow.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fworkflow.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/workflow.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/workflow.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fworkflow.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/workflow.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/workflow.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fworkflow.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/workflow.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/workflow.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fworkflow.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/workflow.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/workflow.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fworkflow.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/workflow.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/workflow.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fworkflow.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/workflow.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/workflow.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fworkflow.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/orch/workflow.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/orch/workflow.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/orch/workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Forch%2Fworkflow.py::scripts%2Forch%2Fcli.py%23external-input-boundary::scripts%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/orch/workflow.py",
      "boundary": "scripts/orch/cli.py#external-input-boundary",
      "subsystem": "scripts/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/orch/workflow.py",
    "boundary": "External tracker and CLI input to the orchestration package",
    "subsystem": "scripts/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/orch/workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fpolicy.data::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/policy.data",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/policy.data",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/policy.data"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fpolicy.data::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/policy.data",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/policy.data",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/policy.data"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fpolicy.data::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/policy.data",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/policy.data",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/policy.data"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fpolicy.data::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/policy.data",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/policy.data",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/policy.data"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fpolicy.data::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/policy.data",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/policy.data",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/policy.data"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fpolicy.data::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/policy.data",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/policy.data",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/policy.data"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fpolicy.data::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/policy.data",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/policy.data",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/policy.data"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fpolicy.data::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/policy.data",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/policy.data",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/policy.data"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fpolicy.data::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/policy.data",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/policy.data",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/policy.data"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fpolicy.data::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/policy.data",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/policy.data",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/policy.data"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fpolicy.data::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/policy.data",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/policy.data",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/policy.data"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fpolicy.data::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/policy.data",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/policy.data",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/policy.data"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fpolicy.data::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/policy.data",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/policy.data",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/policy.data"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fpolicy.data::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/policy.data",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/policy.data",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/policy.data"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fpolicy.data::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/policy.data",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/policy.data",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/policy.data"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fpolicy.data::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/policy.data",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/policy.data",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/policy.data"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fpolicy.data::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/policy.data",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/policy.data",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/policy.data"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fpolicy.data::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/policy.data",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/policy.data",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/policy.data"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fscan-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/scan-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/scan-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/scan-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fscan-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/scan-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/scan-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/scan-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fscan-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/scan-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/scan-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/scan-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fscan-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/scan-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/scan-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/scan-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fscan-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/scan-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/scan-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/scan-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fscan-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/scan-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/scan-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/scan-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fscan-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/scan-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/scan-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/scan-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fscan-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/scan-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/scan-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/scan-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fscan-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/scan-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/scan-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/scan-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fscan-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/scan-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/scan-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/scan-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fscan-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/scan-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/scan-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/scan-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fscan-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/scan-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/scan-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/scan-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fscan-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/scan-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/scan-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/scan-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fscan-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/scan-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/scan-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/scan-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fscan-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/scan-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/scan-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/scan-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fscan-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/scan-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/scan-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/scan-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fscan-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/scan-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/scan-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/scan-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fscan-gate.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/scan-gate.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/scan-gate.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/scan-gate.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-list.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-list.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/beads-list.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-list.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-list.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-list.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/beads-list.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-list.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-list.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-list.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/beads-list.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-list.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-list.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-list.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/beads-list.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-list.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-list.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-list.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/beads-list.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-list.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-list.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-list.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/beads-list.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-list.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-list.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-list.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/beads-list.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-list.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-list.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-list.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/beads-list.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-list.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-list.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-list.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/beads-list.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-list.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-list.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-list.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/beads-list.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-list.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-list.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-list.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/beads-list.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-list.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-list.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-list.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/beads-list.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-list.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-list.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-list.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/beads-list.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-list.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-list.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-list.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/beads-list.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-list.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-list.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-list.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/beads-list.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-list.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-list.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-list.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/beads-list.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-list.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-list.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-list.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/beads-list.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-list.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-list.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-list.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/beads-list.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-list.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-show.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-show.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/beads-show.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-show.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-show.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-show.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/beads-show.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-show.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-show.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-show.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/beads-show.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-show.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-show.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-show.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/beads-show.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-show.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-show.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-show.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/beads-show.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-show.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-show.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-show.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/beads-show.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-show.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-show.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-show.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/beads-show.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-show.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-show.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-show.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/beads-show.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-show.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-show.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-show.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/beads-show.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-show.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-show.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-show.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/beads-show.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-show.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-show.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-show.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/beads-show.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-show.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-show.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-show.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/beads-show.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-show.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-show.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-show.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/beads-show.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-show.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-show.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-show.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/beads-show.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-show.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-show.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-show.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/beads-show.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-show.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-show.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-show.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/beads-show.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-show.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-show.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-show.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/beads-show.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-show.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fbeads-show.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/beads-show.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/beads-show.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/beads-show.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issue-42.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issue-42.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issue-42.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issue-42.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issue-42.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issue-42.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issue-42.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issue-42.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issue-42.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issue-42.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issue-42.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issue-42.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issue-42.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issue-42.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issue-42.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issue-42.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issue-42.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issue-42.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issue-42.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issue-42.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issue-42.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issue-42.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issue-42.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issue-42.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issue-42.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issue-42.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issue-42.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issue-42.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issue-42.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issue-42.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issue-42.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issue-42.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issue-42.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issue-42.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issue-42.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/github-issue-42.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issue-42.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issues.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issues.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/github-issues.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issues.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issues.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issues.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/github-issues.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issues.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issues.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issues.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/github-issues.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issues.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issues.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issues.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/github-issues.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issues.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issues.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issues.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/github-issues.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issues.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issues.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issues.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/github-issues.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issues.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issues.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issues.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/github-issues.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issues.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issues.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issues.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/github-issues.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issues.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issues.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issues.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/github-issues.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issues.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issues.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issues.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/github-issues.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issues.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issues.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issues.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/github-issues.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issues.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issues.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issues.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/github-issues.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issues.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issues.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issues.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/github-issues.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issues.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issues.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issues.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/github-issues.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issues.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issues.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issues.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/github-issues.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issues.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issues.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issues.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/github-issues.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issues.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issues.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issues.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/fixtures/orch/github-issues.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issues.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ffixtures%2Forch%2Fgithub-issues.json::scripts%2Ftests%23fixture-input-boundary::scripts%2Ftests%2Ffixtures%2Forch::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/fixtures/orch/github-issues.json",
      "boundary": "scripts/tests#fixture-input-boundary",
      "subsystem": "scripts/tests/fixtures/orch",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/fixtures/orch/github-issues.json",
    "boundary": "Fixture input to the test harness",
    "subsystem": "scripts/tests/fixtures/orch",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/fixtures/orch/github-issues.json"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Fsurvivor_driver.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/survivor_driver.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/survivor_driver.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/survivor_driver.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Fsurvivor_driver.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/survivor_driver.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/survivor_driver.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/survivor_driver.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Fsurvivor_driver.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/survivor_driver.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/survivor_driver.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/survivor_driver.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Fsurvivor_driver.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/survivor_driver.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/survivor_driver.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/survivor_driver.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Fsurvivor_driver.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/survivor_driver.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/survivor_driver.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/survivor_driver.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Fsurvivor_driver.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/survivor_driver.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/survivor_driver.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/survivor_driver.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Fsurvivor_driver.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/survivor_driver.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/survivor_driver.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/survivor_driver.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Fsurvivor_driver.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/survivor_driver.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/survivor_driver.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/survivor_driver.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Fsurvivor_driver.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/survivor_driver.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/survivor_driver.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/survivor_driver.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Fsurvivor_driver.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/survivor_driver.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/survivor_driver.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/survivor_driver.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Fsurvivor_driver.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/survivor_driver.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/survivor_driver.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/survivor_driver.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Fsurvivor_driver.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/survivor_driver.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/survivor_driver.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/survivor_driver.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Fsurvivor_driver.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/survivor_driver.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/survivor_driver.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/survivor_driver.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Fsurvivor_driver.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/survivor_driver.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/survivor_driver.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/survivor_driver.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Fsurvivor_driver.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/survivor_driver.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/survivor_driver.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/survivor_driver.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Fsurvivor_driver.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/survivor_driver.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/survivor_driver.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/survivor_driver.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Fsurvivor_driver.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/survivor_driver.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/survivor_driver.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/survivor_driver.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Fsurvivor_driver.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/survivor_driver.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/survivor_driver.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/survivor_driver.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_mechanical_verify.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_mechanical_verify.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_mechanical_verify.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_mechanical_verify.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_mechanical_verify.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_mechanical_verify.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_mechanical_verify.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_mechanical_verify.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_mechanical_verify.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_mechanical_verify.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_mechanical_verify.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_mechanical_verify.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_mechanical_verify.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_mechanical_verify.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_mechanical_verify.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_mechanical_verify.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_mechanical_verify.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_mechanical_verify.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_mechanical_verify.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_mechanical_verify.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_mechanical_verify.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_mechanical_verify.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_mechanical_verify.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_mechanical_verify.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_mechanical_verify.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_mechanical_verify.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_mechanical_verify.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_mechanical_verify.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_mechanical_verify.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_mechanical_verify.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_mechanical_verify.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_mechanical_verify.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_mechanical_verify.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_mechanical_verify.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_mechanical_verify.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_mechanical_verify.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_mechanical_verify.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_mechanical_verify.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_mechanical_verify.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_mechanical_verify.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_mechanical_verify.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_mechanical_verify.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_mechanical_verify.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_mechanical_verify.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_mechanical_verify.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_mechanical_verify.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_mechanical_verify.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_mechanical_verify.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_mechanical_verify.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_mechanical_verify.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_mechanical_verify.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_mechanical_verify.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_mechanical_verify.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_mechanical_verify.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_mechanical_verify.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_beads.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_beads.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_beads.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_beads.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_beads.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_beads.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_beads.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_beads.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_beads.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_beads.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_beads.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_beads.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_beads.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_beads.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_beads.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_beads.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_beads.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_beads.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_beads.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_beads.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_beads.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_beads.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_beads.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_beads.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_beads.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_beads.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_beads.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_beads.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_beads.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_beads.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_beads.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_beads.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_beads.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_beads.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_beads.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_beads.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_beads.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_beads.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_beads.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_beads.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_beads.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_beads.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_beads.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_beads.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_beads.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_beads.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_beads.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_beads.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_beads.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_beads.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_beads.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_beads.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_beads.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_beads.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_beads.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_cli.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_cli.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_cli.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_cli.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_cli.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_cli.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_cli.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_cli.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_cli.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_cli.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_cli.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_cli.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_cli.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_cli.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_cli.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_cli.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_cli.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_cli.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_cli.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_cli.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_cli.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_cli.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_cli.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_cli.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_cli.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_cli.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_cli.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_cli.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_cli.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_cli.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_cli.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_cli.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_cli.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_cli.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_cli.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_cli.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_cli.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_cli.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_cli.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_cli.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_cli.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_cli.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_cli.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_cli.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_cli.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_cli.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_cli.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_cli.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_cli.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_cli.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_cli.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_cli.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_cli.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_cli.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_cli.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_engine.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_engine.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_engine.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_engine.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_engine.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_engine.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_engine.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_engine.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_engine.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_engine.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_engine.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_engine.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_engine.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_engine.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_engine.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_engine.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_engine.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_engine.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_engine.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_engine.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_engine.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_engine.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_engine.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_engine.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_engine.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_engine.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_engine.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_engine.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_engine.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_engine.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_engine.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_engine.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_engine.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_engine.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_engine.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_engine.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_engine.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_engine.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_engine.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_engine.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_engine.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_engine.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_engine.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_engine.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_engine.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_engine.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_engine.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_engine.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_engine.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_engine.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_engine.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_engine.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_engine.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_engine.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_engine.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_github.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_github.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_github.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_github.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_github.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_github.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_github.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_github.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_github.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_github.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_github.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_github.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_github.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_github.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_github.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_github.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_github.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_github.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_github.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_github.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_github.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_github.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_github.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_github.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_github.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_github.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_github.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_github.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_github.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_github.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_github.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_github.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_github.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_github.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_github.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_github.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_github.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_github.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_github.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_github.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_github.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_github.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_github.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_github.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_github.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_github.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_github.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_github.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_github.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_github.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_github.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_github.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_github.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_github.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_github.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_model.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_model.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_model.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_model.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_model.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_model.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_model.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_model.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_model.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_model.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_model.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_model.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_model.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_model.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_model.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_model.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_model.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_model.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_model.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_model.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_model.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_model.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_model.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_model.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_model.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_model.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_model.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_model.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_model.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_model.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_model.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_model.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_model.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_model.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_model.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_model.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_model.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_model.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_model.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_model.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_model.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_model.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_model.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_model.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_model.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_model.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_model.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_model.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_model.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_model.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_model.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_model.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_model.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_model.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_model.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_observe.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_observe.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_observe.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_observe.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_observe.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_observe.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_observe.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_observe.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_observe.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_observe.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_observe.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_observe.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_observe.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_observe.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_observe.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_observe.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_observe.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_observe.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_observe.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_observe.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_observe.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_observe.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_observe.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_observe.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_observe.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_observe.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_observe.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_observe.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_observe.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_observe.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_observe.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_observe.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_observe.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_observe.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_observe.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_observe.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_observe.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_observe.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_observe.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_observe.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_observe.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_observe.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_observe.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_observe.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_observe.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_observe.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_observe.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_observe.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_observe.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_observe.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_observe.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_observe.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_observe.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_observe.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_observe.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_workflow.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_workflow.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_workflow.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_workflow.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_workflow.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_workflow.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_workflow.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_workflow.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_workflow.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_workflow.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_workflow.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_workflow.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_workflow.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_workflow.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_workflow.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_workflow.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_workflow.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_workflow.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_workflow.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_workflow.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_workflow.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_workflow.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_workflow.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_workflow.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_workflow.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_workflow.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_workflow.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_workflow.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_workflow.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_workflow.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_workflow.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_workflow.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_workflow.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_workflow.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_workflow.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_workflow.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_workflow.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_workflow.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_workflow.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_workflow.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_workflow.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_workflow.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_workflow.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_workflow.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_workflow.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_workflow.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_workflow.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_workflow.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_workflow.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_workflow.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_orch_workflow.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_orch_workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_orch_workflow.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_orch_workflow.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_orch_workflow.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_orch_workflow.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_receipts.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_receipts.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_receipts.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_receipts.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_receipts.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_receipts.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_receipts.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_receipts.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_receipts.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_receipts.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_receipts.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_receipts.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_receipts.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_receipts.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_receipts.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_receipts.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_receipts.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_receipts.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_receipts.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_receipts.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_receipts.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_receipts.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_receipts.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_receipts.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_receipts.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_receipts.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_receipts.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_receipts.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_receipts.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_receipts.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_receipts.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_receipts.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_receipts.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_receipts.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_receipts.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_receipts.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_receipts.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_receipts.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_receipts.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_receipts.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_receipts.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_receipts.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_receipts.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_receipts.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_receipts.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_receipts.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_receipts.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_receipts.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_receipts.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_receipts.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_receipts.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_receipts.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_receipts.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_receipts.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_receipts.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_receipts.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_receipts.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_receipts.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_receipts.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_receipts.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_receipts.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_receipts.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_receipts.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_receipts.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_receipts.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_receipts.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_receipts.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_receipts.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_receipts.py::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_receipts.py",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_receipts.py",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_receipts.py"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_watchdog.sh::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_watchdog.sh",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_watchdog.sh",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_watchdog.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_watchdog.sh::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_watchdog.sh",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_watchdog.sh",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_watchdog.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_watchdog.sh::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_watchdog.sh",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_watchdog.sh",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_watchdog.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_watchdog.sh::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_watchdog.sh",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_watchdog.sh",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_watchdog.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_watchdog.sh::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_watchdog.sh",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_watchdog.sh",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_watchdog.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_watchdog.sh::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_watchdog.sh",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_watchdog.sh",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_watchdog.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_watchdog.sh::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_watchdog.sh",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_watchdog.sh",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_watchdog.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_watchdog.sh::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_watchdog.sh",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_watchdog.sh",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_watchdog.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_watchdog.sh::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_watchdog.sh",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_watchdog.sh",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_watchdog.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_watchdog.sh::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_watchdog.sh",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_watchdog.sh",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_watchdog.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_watchdog.sh::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_watchdog.sh",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_watchdog.sh",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_watchdog.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_watchdog.sh::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_watchdog.sh",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_watchdog.sh",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_watchdog.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_watchdog.sh::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_watchdog.sh",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_watchdog.sh",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_watchdog.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_watchdog.sh::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_watchdog.sh",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_watchdog.sh",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_watchdog.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_watchdog.sh::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_watchdog.sh",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_watchdog.sh",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_watchdog.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_watchdog.sh::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_watchdog.sh",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_watchdog.sh",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_watchdog.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_watchdog.sh::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/tests/test_watchdog.sh",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/tests/test_watchdog.sh",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/tests/test_watchdog.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Ftests%2Ftest_watchdog.sh::scripts%2Ftests%23test-harness-boundary::scripts%2Ftests::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/tests/test_watchdog.sh",
      "boundary": "scripts/tests#test-harness-boundary",
      "subsystem": "scripts/tests",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/tests/test_watchdog.sh",
    "boundary": "Test harness execution boundary",
    "subsystem": "scripts/tests",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/tests/test_watchdog.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fwatchdog-backup.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/watchdog-backup.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/watchdog-backup.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Access control",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/watchdog-backup.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fwatchdog-backup.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/watchdog-backup.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Access control",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/watchdog-backup.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Access control",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/watchdog-backup.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Access control",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fwatchdog-backup.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/watchdog-backup.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/watchdog-backup.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Business logic",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/watchdog-backup.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fwatchdog-backup.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Business%20logic::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/watchdog-backup.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Business logic",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/watchdog-backup.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Business logic",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/watchdog-backup.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Business logic",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fwatchdog-backup.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/watchdog-backup.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/watchdog-backup.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/watchdog-backup.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fwatchdog-backup.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Chained%20vulnerabilities%20and%20trust%20boundaries::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/watchdog-backup.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/watchdog-backup.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Chained vulnerabilities and trust boundaries",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/watchdog-backup.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Chained vulnerabilities and trust boundaries",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fwatchdog-backup.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/watchdog-backup.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/watchdog-backup.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/watchdog-backup.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fwatchdog-backup.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Cryptography%20and%20secrets::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/watchdog-backup.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Cryptography and secrets",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/watchdog-backup.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Cryptography and secrets",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/watchdog-backup.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Cryptography and secrets",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fwatchdog-backup.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/watchdog-backup.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/watchdog-backup.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/watchdog-backup.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fwatchdog-backup.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Feature%20abuse%20and%20data%20leakage::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/watchdog-backup.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Feature abuse and data leakage",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/watchdog-backup.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Feature abuse and data leakage",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/watchdog-backup.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Feature abuse and data leakage",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fwatchdog-backup.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Injection::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/watchdog-backup.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/watchdog-backup.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Injection",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/watchdog-backup.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fwatchdog-backup.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Injection::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/watchdog-backup.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Injection",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/watchdog-backup.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Injection",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/watchdog-backup.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Injection",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fwatchdog-backup.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/watchdog-backup.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/watchdog-backup.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Obvious things",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/watchdog-backup.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fwatchdog-backup.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Obvious%20things::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/watchdog-backup.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Obvious things",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/watchdog-backup.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Obvious things",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/watchdog-backup.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Obvious things",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fwatchdog-backup.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/watchdog-backup.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/watchdog-backup.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Resource and file handling",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/watchdog-backup.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fwatchdog-backup.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Resource%20and%20file%20handling::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/watchdog-backup.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Resource and file handling",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/watchdog-backup.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Resource and file handling",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/watchdog-backup.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Resource and file handling",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fwatchdog-backup.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Finitial-review",
    "canonical_refs": {
      "surface": "scripts/watchdog-backup.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/initial-review"
    },
    "surface": "scripts/watchdog-backup.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Wildcard",
    "lifecycle": "Initial review",
    "starting_paths": [
      "scripts/watchdog-backup.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  },
  {
    "coverage_id": "scripts%2Fwatchdog-backup.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Wildcard::lifecycle%2Fsteady-state-operation",
    "canonical_refs": {
      "surface": "scripts/watchdog-backup.sh",
      "boundary": "scripts/policy.data#operator-invocation-boundary",
      "subsystem": "scripts",
      "attack_class": "ATTACK-CLASSES.md#Wildcard",
      "lifecycle": "lifecycle/steady-state-operation"
    },
    "surface": "scripts/watchdog-backup.sh",
    "boundary": "Operator invocation of a shipped script",
    "subsystem": "scripts",
    "attack_class": "Wildcard",
    "lifecycle": "Steady-state operation",
    "starting_paths": [
      "scripts/watchdog-backup.sh"
    ],
    "ordinary_attack_class_block": "ATTACK-CLASSES.md#Wildcard",
    "selected_companion_blocks": [],
    "excluded_blocks": [],
    "prior_status": "none",
    "attempts": [],
    "wave": 1,
    "status": "planned",
    "agent_id": null,
    "reviewed_paths": [],
    "local_checks": [],
    "result_fingerprints": [],
    "unresolved": []
  }
]
```

Decision input: input to Task A2 — a lane-sized unit set derived with
the full canonical tuple validates at 576 units and 12.7% of the
validator's 5 MiB cap.

## Step 4: Q4 inscription miss rate (aggregate only)

Command (login shell):

```text
$ bash -lc 'neurostrata-mcp list aep'
Found 21 memories in namespace 'aep'
```

Scoring rubric (from the brief): an entry passes only with all three —
**cue:** a stated situation that should trigger recall; **lesson:** a
transferable claim, not a bare event log; **evidence:** a named source
pointer (file, issue, PR, or record). Operationalization applied
uniformly by the single scorer: cue passes when the entry names a
recurring activity, condition, pattern, or decision scope that would
trigger recall (a date or topic label alone does not; an entry whose
dominant form is a dated event record does not); lesson passes when the
entry contains a transferable claim, rule, method verdict, or a durable
standing fact stated in general terms; evidence passes when the entry
names a file path, an issue, a PR, or a named record such as a charter,
memo, or report.

Aggregate results only:

- Entries scored: 21
- Entries passing all three fields: 15
- Entries failing at least one field: 6
- Missing cue: 5
- Missing lesson: 2
- Missing evidence: 1
- Miss rate: 6 / 21 = 28.6%

No inscription contents are recorded in this file or in the repo. The
failing entries' IDs only were written to
`~/workspace/goals/autonomous-code-defense-factory/hidden_files/inscription-miss-ids-2026-10-26.txt`
(6 IDs), outside the repo.

Decision input: input to Task A5 — miss rate 28.6% under the rubric
above, with the failing-ID work set in the companion hidden file named
above.

## Step 5: Commit

This record is committed with subject
`docs: record security-audit adoption evidence gates (P0)`. The results
above are recorded verbatim (commands and outcomes); no conclusions are
stated beyond the per-section decision inputs to Task A1, Task A2,
Task A5, and Election E-verdict.
