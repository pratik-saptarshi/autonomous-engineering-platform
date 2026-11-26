# NeuroStrata lifecycle kit — canonical source

This directory holds the canonical lifecycle kit for the NeuroStrata
daemon: the watchdog, its scheduler record, and the preserved kit-era
documents that explain how the lifecycle got here. It is a source of
truth for the scripts, not a deployment: nothing in this directory is
live until it is deployed by hand (see Deployment below).

## Canonical source

`ops/bin/watchdog-backup.sh` is the **canonical SOURCE** for the
watchdog. It is the live deployed watchdog (base:
`~/workspace/neurostrata/bin/watchdog-backup.sh`, sha256 recorded in
`ops/bin/WATCHDOG-DELTAS.md`) plus exactly eight documented deltas:
a corrected header block, removal of the dead `start_daemon`
definition, the `stop_daemon` definition moved above its first
use, shellcheck fixes plus a full `shfmt -i 2` reformat (fix
round 2), a stop failure that exits 1 instead of exiting 0
(PR #163), crash evidence capture with pre-restart log
preservation (issue #21), binary SSOT resolution with
best-effort guarded state writes (Delta G), and the activity-aware
idle gate with evidence-retry hardening (Delta H). Every deviation from the live script is recorded in
`ops/bin/WATCHDOG-DELTAS.md`; no other difference exists.

## What is legacy, and what is a snapshot

- `scripts/watchdog-backup.sh` (repo root) is the **legacy
  always-on-era copy**, kept with its test
  (`scripts/tests/test_watchdog.sh`). It is NOT the canonical source.
  Do not treat its always-on behavior (restart promises, EXIT trap)
  as current practice.
- `reference/neurostrata-ops/` is the **dated Oct 26 snapshot** of the
  operator's live ops directory, vendored under its manifest. It is
  untouched by this PR and is not a source for new work — it is the
  record the preserved documents below were copied from.

## Deployed governs runtime

On any disagreement, the **DEPLOYED script governs runtime** — that
rule from `docs/daemon-lifecycle-contract.md` is preserved unchanged
by this PR. This PR adds the canonical-source rule alongside it: when
a plan or a reader needs the watchdog, cite `ops/`; when behavior at
runtime is in question, the deployed script is the authority. The two
rules do not conflict because they answer different questions (what
to cite vs. what actually runs).

## Allowlisted absolute path and binary resolution

One absolute path is carried over from the live script, allowlisted
here with its justification: `/opt/hatch/bin/hatch_gws_cli` is the
runtime binary the watchdog invokes for the Drive upload tier. It is
the only absolute path in the canonical script, and it is required:
without it there is no Drive tier. No value is embedded alongside
it — no folder id, no credential, no account identifier appears in
`ops/`.

For `neurostrata-mcp`, the canonical watchdog resolves `AEP_MCP_BIN` if
set, else `~/go/bin/neurostrata-mcp` (matching `docs/runbook.md`), else
`~/workspace/neurostrata/bin/neurostrata-mcp`, else `PATH`, and exits 1
loudly if none is executable. All other state and staging paths use
`$HOME/workspace/neurostrata/` and `$HOME/.config/NeuroStrata/`.

## Validated runtime scope

This kit is validated against the **v1.14.3-patch** daemon — the
version currently running on the VM. A runtime upgrade re-opens
validation: on any daemon upgrade, re-run the behavioral test
(`ops/tests/test_watchdog_ops.sh`) and re-check the documented
deltas against the new live script before treating `ops/` as
current. That trigger includes the v1.15.0 direction of NeuroStrata
PR #23, which is a separate, unmerged effort and does not change
anything in this directory until it lands and is re-validated.

## Deployment

`ops/bin/deploy-watchdog.sh` is the deployment process. The source is always
`ops/bin/watchdog-backup.sh`, and the target is `DEPLOY_TARGET` (default
`~/workspace/neurostrata/bin/watchdog-backup.sh`). Running it is still a
manual operator act. Nothing in CI or in a cron deploys, and nothing in this
directory claims the live script matches `ops/` until `--check` says so.

```bash
ops/bin/deploy-watchdog.sh --check      # SHA-256 drift check, exit 0 only when in sync
ops/bin/deploy-watchdog.sh --dry-run    # show what --apply would do, write nothing
ops/bin/deploy-watchdog.sh --apply      # bash -n, behavioral suite, backup, atomic deploy, receipt
```

- `--check` exits 1 on drift and when the target is missing, and prints both
  hashes. Run it on the host before trusting any claim about live behavior.
- `--apply` runs `bash -n` and `ops/tests/test_watchdog_ops.sh` first and
  aborts on a failure. `--skip-tests` skips the suite and prints a warning.
  The suite needs Linux with `/proc` and PID namespaces.
- A drifted target is saved as `<target>.bak.<UTC timestamp>` before it is
  replaced. To roll back, copy that file over the target.
- The new file is staged beside the target, set to mode 755, hash-verified,
  and moved into place with `mv`. A watchdog run in progress keeps reading
  its old inode, so a deploy never corrupts a running script.
- `.watchdog-deploy-receipt.json` is written beside the target (override with
  `DEPLOY_RECEIPT`). It records the UTC time, the git commit of the source,
  whether the source file had uncommitted changes, the SHA-256, the target,
  and the backup path.
- An in-sync target is a no-op, so running `--apply` twice is safe.

The deployed watchdog governs runtime, so after a deploy run
`ops/bin/deploy-watchdog.sh --check` once more and keep the receipt.

## Contents

| Path | What it is |
| --- | --- |
| `ops/bin/watchdog-backup.sh` | Canonical watchdog (live base + 8 documented deltas + reformat) |
| `ops/bin/WATCHDOG-DELTAS.md` | Delta table: header rewrite, dead-code removal, definition move, shellcheck fixes + reformat, stop-failure exit 1, crash evidence capture, binary SSOT + best-effort hardening, activity-aware idle gate + evidence retry |
| `ops/tests/test_watchdog_ops.sh` | Behavioral test, per daemon state, with PID-namespace isolation guard |
| `ops/bin/deploy-watchdog.sh` | Deploys the canonical watchdog to the live path: `--check` drift, `--dry-run`, `--apply` with backup and receipt |
| `ops/tests/test_deploy_watchdog.sh` | Test for the deploy script, run against a throwaway fixture repo and target |
| `ops/bin/cron-with-boot-gate.sh` | Wrapper that runs `scripts/boot-gate.sh` before a scheduled job and aborts the job when the gate fails |
| `ops/tests/test_cron_boot_gate.sh` | Test for the wrapper: pass-through, abort, missing gate, usage errors |
| `ops/bin/idle-reaper.sh` | Retired standalone reaper, preserved with an in-file retirement banner |
| `ops/bin/RETIRED.md` | Retirement evidence: standalone reaper retired, idle-stop behavior absorbed into the watchdog |
| `ops/crons/watchdog-cron-record.md` | Dated scheduler record, derived from the live cron body only |
| `ops/crons/CRONS.md` | Current scheduler reality: watchdog every 2h; reaper and export retired |
| `ops/runbooks/OPERATIONS.md` | Kit-era operations runbook, preserved with an era banner |
| `ops/runbooks/IDLE-REAPER.md` | Kit-era reaper runbook, preserved with an era banner |
| `ops/runbooks/ERA-NOTE.md` | Delta table for the preserved documents + named stale facts |
| `ops/model-switch/MODEL-SWITCH-BGESMALLQ-PLAN.md` | Kit-era executed model-switch plan, preserved with an era banner |
