# Audit-lane run artifacts and validators

This directory holds the AEP-owned audit tooling and examples. The
protocol is `docs/security-audit-protocol.md`; the vendored
security-audit skill under `reference/security-audit-skill/` is data
and is never edited. All commands below run from the repository root;
each validator takes exactly one file argument.

## Run layout

Runs live outside the target repo by default (the source's
write-isolation rule; protocol §7.6). The run root is:

```text
~/workspace/goals/autonomous-code-defense-factory/audit-runs/<run-id>/
```

and contains exactly:

```text
coverage-ledger.json
findings.json
run-metadata.json
verification-attestations.json      (the attestation sidecar, Task A3)
dispatch-log.json                   (the dispatch log, Task A3)
agents/<agent-id>/scratch/
agents/<agent-id>/artifacts/
```

with one `agents/<agent-id>/` pair of directories per dispatched agent
and nothing else at the run root.

An in-repo output directory is permitted only if **both** preconditions
hold:

1. the user selects it, **and**
2. version control ignores the whole directory.

### Artifact paths in the ledger

A local check's artifact is evidence only under exactly
`agents/<agent_id>/artifacts/`: the artifact path recorded in the
ledger, relative to the run root, must carry the prefix
`agents/<check.agent_id>/artifacts/` for the check's own agent ID (the
vendored ledger validator's `isOwnedArtifactPath` requirement).
Scratch paths, output-root files, symlinks, special files, and another
check owner's artifacts are not evidence.

### `run-metadata.json` contents

Per protocol §4, every run's `run-metadata.json` carries:

- `run_id` and `profile` (`quick`, `standard`, or `deep`);
- `run_status` (and `incomplete_reason` when incomplete);
- `budget`: the maximum number of agent invocations across all
  phases — a single integer;
- `budget_reserved`: the per-role counts (reconnaissance, critics,
  verifiers) reserved up front, before any hunting is assigned —
  reserved calls are never spent on hunting;
- `spent: {total_agent_invocations}`, updated at run close;
- `cap_override_approved_by`, required whenever a run's cap exceeds
  its profile cap (quick ≤ 20, standard ≤ 40, deep ≤ 60 total agent
  invocations, reserved calls included);
- the egress inventory: any run that sends task material to a remote
  model API records the provider class and the material classes sent.

## Validator invocations

Coverage ledger (vendored validator):

```text
node reference/security-audit-skill/skills/security-audit/validate-coverage-ledger.cjs <run-root>/coverage-ledger.json
```

Findings (vendored validator):

```text
node reference/security-audit-skill/skills/security-audit/validate-findings.cjs <run-root>/findings.json
```

Findings (the AEP profile route, protocol §5.3 — invoked wherever the
vendored findings validator would otherwise be named):

```text
node scripts/audit/validate_findings_profile.cjs <run-root>/findings.json
```

Each exits 0 on pass and nonzero with each violation named. Run the
ledger validator after seeding, after every parent update, and before
the run's final report (protocol §7.5). Validator success proves
format and ledger consistency only (protocol §7.8).

## Shipped validator suites

The vendored validators ship `node:test` suites (there is no header
run command). Expected at the current pin: 34 tests and 31 tests, all
passing.

```text
node --test reference/security-audit-skill/skills/security-audit/validate-findings.test.cjs
node --test reference/security-audit-skill/skills/security-audit/validate-coverage-ledger.test.cjs
```

## Examples

`examples/` holds shape references only — never coverage evidence
(protocol §7.8). A coverage claim in any AEP report must cite ledger
units from a real run under the external run root, never this
directory and never prose.

- `synthetic-ledger.json` — Task P0's Q3 synthetic ledger (576 units),
  watermarked with `"aep_bookkeeping": {"synthetic": true}` on every
  unit; every agent ID is under the reserved `example-*` prefix (the
  source ledger's units are all unassigned, so no IDs appear). It
  passes the vendored ledger validator as a shape check:
  `node reference/security-audit-skill/skills/security-audit/validate-coverage-ledger.cjs scripts/audit/examples/synthetic-ledger.json`
- `budget-exhaustion.json` / `budget-exhaustion.expected.json` — the
  §4 budget-exhaustion fixture pair (Task A1).
