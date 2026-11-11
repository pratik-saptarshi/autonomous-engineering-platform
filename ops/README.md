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
`ops/bin/WATCHDOG-DELTAS.md`) plus the documented lint/format delta
set recorded there. Re-baselined 2026-11-11 against the current
live script: the 2026-11-04 build's header-rewrite and dead-code
deltas were NOT re-applied (live's model changed under them), the
definition-move delta is moot, and the shellcheck/shfmt delta was
re-applied with filename-ordered find pipelines. Every deviation
from the live script is recorded in `ops/bin/WATCHDOG-DELTAS.md`;
no other difference exists.

## What is legacy, and what is a snapshot

- `scripts/watchdog-backup.sh` (repo root) is the **legacy
  always-on-era copy**, kept with its test
  (`scripts/tests/test_watchdog.sh`). It is NOT the canonical source.
  Its marker-based leave-down behavior is a different lineage; the
  canonical copy's direct-restart behavior (including its EXIT
  trap) comes from the current live script, not from this file.
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

## Allowlisted absolute path

One absolute path is carried over from the live script, allowlisted
here with its justification: `/opt/hatch/bin/hatch_gws_cli` is the
runtime binary the watchdog invokes for the Drive upload tier. It is
the only absolute path in the canonical script, and it is required:
without it there is no Drive tier. No value is embedded alongside
it — no folder id, no credential, no account identifier appears in
`ops/`. Every other path in the kit uses `~/workspace/…` tilde form.

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

`ops/` → live deployment **remains manual** until a deploy task
exists. This plan provides detection (the gated drift check, Task 10,
NOT created by this PR) and the live → `ops/` backport direction
only. Nothing in this PR deploys, and nothing here claims `ops/` is
deployed. Until a deploy step runs, the live script and `ops/` can
drift apart; the drift check, when enabled, is what catches that.

## Contents

| Path | What it is |
| --- | --- |
| `ops/bin/watchdog-backup.sh` | Canonical watchdog (current live base + documented lint/format deltas; re-baselined 2026-11-11) |
| `ops/bin/WATCHDOG-DELTAS.md` | Delta record: 2026-11-11 re-baseline dispositions + the superseded 2026-11-04 build record |
| `ops/tests/test_watchdog_ops.sh` | Behavioral test, per daemon state, with PID-namespace isolation guard |
| `ops/bin/idle-reaper.sh` | Standalone idle reaper — live component; ops copy re-baselined from the live script 2026-11-11 |
| `ops/bin/RETIRED.md` | Reaper retirement record — REVERSED 2026-11-11, with the reversal evidence |
| `ops/crons/watchdog-cron-record.md` | Dated scheduler record, derived from the live cron body only |
| `ops/crons/CRONS.md` | Current scheduler reality: watchdog every 2h; reaper every 15m; export retired |
| `ops/runbooks/OPERATIONS.md` | Kit-era operations runbook, preserved with an era banner |
| `ops/runbooks/IDLE-REAPER.md` | Kit-era reaper runbook, preserved with an era banner |
| `ops/runbooks/ERA-NOTE.md` | Delta table for the preserved documents + named stale facts |
| `ops/model-switch/MODEL-SWITCH-BGESMALLQ-PLAN.md` | Kit-era executed model-switch plan, preserved with an era banner |
