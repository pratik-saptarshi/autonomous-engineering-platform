# ghg drift check — cron specification

This document is the **specification** for the scheduled ghg drift
check. It is not an installed job: installing the cron is an
operator step at handoff, gated on Pratik's explicit schedule word
like any recurring job. Nothing in the ghg build creates it.

## Schedule

- **Cadence:** hourly.
- **Owner:** goal-owned by environment-maintenance
  (`environment-maintenance-daemon-watchdog-backups`).

## Command

Run, in order, from the AEP platform repository checkout (entry
point `tools/ghg/bin/ghg`; runtime state resolves from
`$GHG_STATE_DIR`, default `~/workspace/ghg-state/`):

```sh
tools/ghg/bin/ghg status --json
tools/ghg/bin/ghg prune
```

- `ghg status --json` reports, per bucket, the cap, rolling ledger
  spend, in-flight reservations, and GitHub's own figures from the
  cached `rate_limit` snapshot; the top 5 actors by spend; bypass
  counts; `ungated_error` counts; and core drift (GitHub `used`
  minus seed-adjusted ledger spend, with interactive and
  connector-path use named as confounders). It also appends the
  run's drift figures to `$GHG_STATE_DIR/drift.jsonl`, so drift
  history survives window rolls.
- `ghg prune` deletes `calls` rows older than 30 days, bounding the
  ledger the status run reads.

## Report rule

Deliver a report to the **main chat only** when at least one of
these holds for the window since the last check:

- core drift **> 50** in the window, or
- **any** bypass (`GHG_BYPASS=1`) call occurred, or
- `ungated_error` rows exist since the last check (gateway-internal
  failures that passed calls through ungated).

Otherwise the run is silent — no report. Drift without a consumer
decays into a norm; this rule is the consumer, and its silence on
healthy windows is deliberate.
