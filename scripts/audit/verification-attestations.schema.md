# Verification attestations: sidecar and dispatch-log contract

This document is the contract for the two AEP-owned run artifacts that
carry role identity for the audit lane: the attestation sidecar
(`verification-attestations.json`) and the dispatch log
(`dispatch-log.json`), both in the run root beside `findings.json` and
`coverage-ledger.json` (see `docs/security-audit-protocol.md` §7.6).
The checker is `scripts/audit/check_verifier_distinctness.cjs`
(network posture: none; it reads only the local artifacts named on its
command line, edits nothing, and judges no finding's truth):

```text
node scripts/audit/check_verifier_distinctness.cjs <run-dir>
node scripts/audit/check_verifier_distinctness.cjs <findings.json> <coverage-ledger.json> <verification-attestations.json> <dispatch-log.json> [--profile quick|standard|deep]
```

Findings records stay schema-pure: role identity lives only in the
sidecar, the dispatch log, and the ledger's per-check `agent_id`. No
identity field is ever added inside a findings record (the vendored
schema forbids additional properties at record level).

## The attestation sidecar

Top-level shape: a JSON object keyed by finding `fingerprint`. Exactly
one entry per `confirmed` or `needs_validation` finding; an absent
entry is a failure, and an entry naming no such finding is a failure.

Each entry carries exactly these fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `hunter_agent_id` | string | The agent that hunted the candidate. Must anchor in the ledger (below). |
| `phase3_verifier_agent_id` | string | The fresh Phase 3 verifier for the candidate. |
| `phase5_verifier_agent_id` | string or null | The fresh Phase 5 verifier for the final record; null when no Phase 5 pass is recorded for the entry. |
| `replacement_verifier_agent_id` | string or null | The third verifier for a material Phase 5 replacement; null when no replacement was verified. |
| `confirmation_basis` | `"static"` or `"execution"` | How the record was confirmed, so a static-proof record is classifiable from the sidecar alone. |
| `superseded_verdict` | string or null | The verdict of the record this entry's finding replaced; null when it replaced none. |
| `superseded_severity` | string or null | The overall severity of the replaced record; null when it replaced none or carried none. |
| `static_rewalk` | `"agreed"`, `"rebutted"`, or null | The fresh verifier's independent re-walk result for a static proof; null when no static re-walk applies. |
| `findings_sha256` | string (hex) | SHA-256 of the findings file this attestation was written against. |
| `ledger_sha256` | string (hex) | SHA-256 of the coverage-ledger file this attestation was written against. |

## The dispatch log

Top-level shape: a JSON array, one object per dispatch, appended by
the orchestrator **at dispatch time**:

| Field | Type | Meaning |
| --- | --- | --- |
| `agent_id` | string | The dispatched agent's canonical ID. |
| `role` | string | One of `hunter`, `phase3_verifier`, `phase5_verifier`, `replacement_verifier`. |
| `session_id` | string | The dispatch session's ID, as recorded by the runtime. |
| `dispatched_at` | string | ISO 8601 timestamp of the dispatch. |

## Rules the checker enforces

- **IDs are dispatch-recorded, never payload-asserted.** The
  orchestrator appends to the dispatch log at each dispatch, using IDs
  in the ledger's canonical pattern `/^[a-z0-9][a-z0-9_-]{0,63}$/`. A
  returned payload asserting its own identity is ignored. Every sidecar
  ID must resolve to a dispatch-log entry with the matching `agent_id`
  and the role for its field.
- **Reserved `example-*` prefix.** IDs under the reserved `example-*`
  prefix are invalid in real runs. They are permitted only in run
  directories under an `examples/` path (shape references, never
  coverage evidence); the checker rejects them anywhere else.
- **Hunter anchor.** The sidecar's `hunter_agent_id` must equal the
  `agent_id` owning a check on a ledger unit whose
  `result_fingerprints` contain the fingerprint (protocol §7.7). The
  verifier side lives only in the sidecar and the dispatch log: for
  fresh candidates the ledger records no verifier identity, and no
  checker predicate requires one there.
- **Distinctness is profile-aware.** `hunter != phase3_verifier`, and
  `hunter != phase5_verifier` when a Phase 5 verifier is present. In
  the `quick` profile the source merges Phases 3+5, so
  `phase3_verifier_agent_id == phase5_verifier_agent_id` is **required
  and permitted** there, and only hunter-distinctness is checked
  between the phases; in every other profile a present Phase 5 verifier
  must differ from the Phase 3 verifier. The profile is read from the
  run's `run-metadata.json` (or `--profile` in the four-file form).
- **Sessions and ordering.** The roles for one fingerprint that are
  carried by different agents carry distinct `session_id`s in the
  dispatch log, and each verifier's `dispatched_at` postdates the
  hunter's dispatch for that fingerprint.
- **Material replacements are mechanical.** A replacement is material
  iff the sidecar's `superseded_verdict` / `superseded_severity` versus
  the finding's current verdict / overall severity shows movement
  toward `confirmed` (verdict rank `rejected` < `needs_validation` <
  `confirmed`) or a severity increase (rank `informational` < `low` <
  `medium` < `high` < `critical`). A material replacement requires
  `replacement_verifier_agent_id` present and distinct from the
  hunter, the Phase 3 verifier, the Phase 5 verifier, and the
  replacement's proposer (the Phase 5 verifier that proposed the
  replacement). Whenever a replacement verifier is recorded, the same
  distinctness is required of it.
- **Static re-walk.** Every `confirmed` entry with
  `confirmation_basis: "static"` requires `static_rewalk: "agreed"`.
  An execution-basis record is distinguishable by the same field.
- **Freshness binding.** Each entry's `findings_sha256` and
  `ledger_sha256` must equal the SHA-256 of the findings and ledger
  files as checked; an attestation written against earlier artifacts
  fails.

## Checker contract

Exit 0 means every `confirmed` / `needs_validation` record satisfies
all rules above: completeness (exactly one sidecar entry per such
fingerprint), the hunter anchor, distinctness, materiality, the static
re-walk, freshness hashes matching the files as checked, and dispatch
resolution plus ordering. A nonzero exit names the offending
fingerprints, and the run reports `run_status: incomplete` with its
findings not publishable as verified.

## What the checker proves, stated honestly

The checker proves distinct recorded agent IDs, recorded at dispatch
in the run's dispatch log and consistency-checked (hunter anchored in
the ledger; artifacts hash-bound). It proves label distinctness over
dispatch-recorded artifacts — fabrication is **detectable** (by
sampling dispatch refs against the runtime's own subagent records,
which the parent does not author), **not impossible**. It does not
prove the sessions' contexts were independent beyond the dispatch
record — that residue is the same fresh-context trust AEP's SDD
already runs on, now made auditable instead of invisible.
