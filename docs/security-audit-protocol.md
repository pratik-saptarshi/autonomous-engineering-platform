# Security-audit protocol — the AEP audit lane

This document is the audit lane's protocol: the verdict vocabulary and
contracts, the environment condition for this VM, the static-proof trace
contract, the run-budget contract, and the findings-schema profile the
lane validates against. It is AEP-owned. The vendored security-audit
skill under `reference/security-audit-skill/` (pin `c1c8a8c`) is the
source the contracts below are adopted from; vendored files are data and
are never edited by this lane.

Vocabulary: in this protocol's prose, verdicts are written namespaced —
`audit:confirmed`, `audit:needs_validation`, `audit:rejected` — because
the bare words carry other meanings elsewhere in AEP. Inside the schema
definitions, the profile section, and quoted source text, the verdict
names appear as the schema's field values, since that is what they are
there.

Sources:

- Verdict contracts: vendored `VALIDATION-AND-REPORTING.md` (Phases 3–4).
- Run budget: vendored `SKILL.md`, "Cost budget".
- Findings schema: vendored `report-schema.json`, as profiled by
  `docs/security-audit-schema-profile.json` (see §5).
- Distortion record forcing the profile: Task P0, Q2, in
  `docs/security-audit-spikes-2026-10-26.md`.
- Capability ledger and claim table: hardening analysis G2 §3
  (`2026-10-26-gap-repairs-hardening.md`); this protocol carries its
  decisive rows in §2.

## 1. Verdict vocabulary and contracts

There are exactly three verdicts. Each record carries a stable
`fingerprint`, a `title`, a `description`, and repository-relative
source paths in its `trace` and `evidence`. The three branches are
mutually exclusive in shape; a record must not carry another branch's
fields.

### `audit:confirmed`

Schema branch fields: `root_cause`, `intended_behavior`, `trace`,
`evidence`, `conditions`, `execution`, `remediation`, `severity`, and
`confidence`. A record in this branch must not use
`claimed_root_cause`, `blockers`, `validation_plan`, or `reason`.

Only a record in this branch receives severity. Likelihood and impact
reflect only the demonstrated conditions and result, and overall
severity must not exceed demonstrated impact.

The environment condition in §2 scopes what may carry this verdict in
this VM; the schema branch alone does not entitle a record to it.

### `audit:needs_validation`

Schema branch fields: `claimed_root_cause`, `trace`, `evidence`,
`blockers`, and `validation_plan`. The `validation_plan` must carry at
least one nonempty field: `local` (a bounded local plan) or
`deployment` (an owner-observed fact to obtain); include both only when
both contexts can resolve distinct facts.

A record in this branch carries no severity, no `execution`, and no
`remediation` — and no confirmed `root_cause`: the root cause stays
*claimed* until validation resolves it.

### `audit:rejected`

Schema branch fields: `claimed_root_cause`, `trace`, `evidence`, and
`reason`. A record in this branch carries no severity, no `execution`,
no `remediation`, no `blockers`, and no `validation_plan`. Rejected
records are retained so a future run does not repeat the unsupported
claim without changed evidence; they are never reported as findings.

### Validation discipline

Every candidate is validated by a fresh verifier that did not hunt it.
The verifier re-reads every cited source location and independently
runs any decisive check it can reproduce safely, under the environment
condition in §2. A malformed or prose-wrapped verifier result is
discarded without repair and re-run with a fresh verifier when the
budget permits; otherwise the candidate remains an unvalidated ledger
candidate under the budget rule in §4, and never enters `findings.json`
under any verdict.

## 2. Environment condition for this VM

### 2.1 The scoping rule (verbatim)

The plan's Global Constraints scope the top verdict for this
environment, verbatim:

> Environment condition (P4): network-namespace creation is denied on
> this VM (netavark setns denied; podman exec denied —
> outer-environment block). A `confirmed` verdict may be carried only
> by (a) a static proof (recorded trace citing code path by file:line,
> constructed input, invariant violated; a fresh verifier independently
> re-walks it before the verdict stands — a profile-defined
> confirmation basis under Election E-verdict's designed default, never
> presented as the source schema's `confirmed` unqualified, since the
> verbatim schema requires an `execution` object) or (b) execution
> under a control set meeting the skill's universal-safety bar in an
> environment that can enforce it. One-shot containers do not meet that
> bar here (host networking; target code shares host loopback, can
> reach the NeuroStrata daemon on 127.0.0.1:34343) — they upgrade no
> verdict, and the phrase "sandboxed reproduction" is banned for them.
> Everywhere else the verdict is `needs_validation` with the missing
> capability as the named blocker.

Corrected podman state, recorded in Task P0: podman 4.9.3 is installed
via apt, but the `/etc/containers/` runbook configs were never
rewritten, so podman is not in its verified-working state, and the
network-isolation probe remains un-run under Pratik's explicit ruling.
No task in this lane runs that probe.

### 2.2 Demotion, and what `audit:needs_validation` is not

- **Demotion rule** (vendored `VALIDATION-AND-REPORTING.md`, Phase 3):
  demote a proposed confirmation to `audit:needs_validation` when a
  specific deployment or runtime fact remains unknown and decisive.
- **Not a parking place** (same source): `audit:needs_validation` is
  never a parking place for a speculative idea. A candidate enters this
  branch only as a specific, source-grounded boundary hypothesis whose
  decisive fact is genuinely outside source/local observation. If
  source refutes the trace, the verdict is `audit:rejected`.

### 2.3 Capability ledger for this VM (decisive rows)

The source's execution bar is a control *set*, not a single mechanism.
Each control below is marked for this VM as **enforceable**, **not
enforceable**, or **degraded**, per hardening G2 §3. The decisive rows:

| Control (vendored `SKILL.md`, universal execution safety) | This VM |
| --- | --- |
| OS-enforced isolation of target code from the host | **Not enforceable** — execution into a running container is denied by the outer environment; one-shot container runs are not the skill's control set |
| No external network; isolated loopback only, when a loopback is needed | **Not enforceable** — network-namespace creation is denied; containers here run with host networking, so target code shares the host loopback and LAN and can egress |
| Never expose sockets or shared services to target code | **Not enforceable** — with host loopback shared, target code can reach shared services on 127.0.0.1, including the NeuroStrata daemon on 127.0.0.1:34343 when it is running |
| Empty allowlist environment plus a scratch `HOME` | **Degraded** — achievable in a one-shot container's run configuration (environment fully settable per run, home unmounted), but host execution's posture is a denylist scrub, not an allowlist; not a standing host control |
| Read-only target and toolchain, with writes only in `scratch/` | **Degraded** — achievable in a one-shot container (read-only mount plus a scratch volume), not enforceable for host execution |
| Explicit CPU / memory / process / disk / wall-clock limits | **Degraded** — cgroup delegation fails in this sandbox; limits can be requested (and timeouts exist) but are not proven enforced |

The ledger is re-derived per environment, never assumed. The standing
canary (Part 2, Outline H3's precondition) is the re-derivation
instrument: a future environment that can enforce more of the set earns
its own ledger rows by that instrument, not by analogy to this table.

### 2.4 Claim table

Keyed to the ledger in §2.3, an audit pass in this environment:

**May claim**

- `audit:rejected` on source evidence alone — the rejected branch
  requires trace, evidence, and reason, and no execution.
- `audit:needs_validation` for every candidate whose decisive fact
  requires execution, with blockers naming the specific missing control
  (§2.5) and a `validation_plan` naming an environment that could run
  it.
- `audit:confirmed` only under the profile in §5, restricted to defect
  classes demonstrated without executing target code: the target
  contributes data only to trusted tooling — a digest recomputed by
  parent-side trusted code over target bytes, a target data file
  consumed by the vendored validators, or a constructed input trace
  walked over source by the verifier (the static-proof contract, §3).

**Must never claim**

- `audit:confirmed`, presented as the source schema's verdict, from any
  execution on this VM — host or one-shot container.
- Severity on any execution-blocked record (the schema already forbids
  severity outside the top branch; this lane restates it so the rule
  survives profile edits).
- The banned phrase of §2.1, or any synonym, for one-shot container
  runs here: with host loopback shared, the phrase is false, not
  optimistic.
- Coverage of any attack class whose decisive check was
  execution-blocked, beyond `audit:needs_validation` entries in the
  ledger. The ledger records the block; prose must not round it up.

One-shot container runs upgrade no verdict class in this lane.

### 2.5 The blocker rule

A blocker in an `audit:needs_validation` record names the **specific
missing control**, never a generic label for the whole control set.
Conforming example: "no network-namespace isolation on this VM; target
code would share host loopback and reach shared services". A blocker
that names only the generic control set, without the specific missing
control and its consequence, does not satisfy this protocol.

## 3. Static-proof trace contract

A static proof is a confirmation whose entire basis is a recorded
trace: no target code is executed. In this VM it is the primary
confirmation basis (§2.1, route (a)).

A static-proof `audit:confirmed` record must satisfy all of the
following:

- Its `trace` contains the code path cited by file:line, the
  constructed input, and the invariant the input violates.
- Its `evidence` states that no target code was executed for the
  record.
- It does not stand until a fresh verifier has independently re-walked
  the trace and recorded agreement or rebuttal. Enforcement is via
  Task A3's sidecar: the record's sidecar entry carries
  `confirmation_basis` and a `static_rewalk` field, and a static-basis
  record requires the re-walk to be recorded as agreed.

How a static-proof record populates the schema's `execution` object —
under the profile (§5), the data-only demonstration shape:

- `instructions` carries the constructed-trace steps: the re-walk a
  verifier performs over source.
- `observed_result` carries the invariant violation as walked — the
  conclusion the trace compels — not a result of running anything.
- `payloads` carries the constructed input.

In this shape the target contributes data only; trusted tooling and
the verifier do the walking. A no-execution confirmation is a profile
decision, never the source's contract, and is never presented as
source-conformant. (Under a verbatim adoption — the branch Q2 did not
take — such candidates would have stayed `audit:needs_validation` with
the blocker "no schema home for no-execution confirmation — profile
not adopted".)

## 4. Run-budget contract

Adopted from vendored `SKILL.md`, "Cost budget", with the lane's caps
made concrete.

Each run writes `run-metadata.json` carrying:

- `budget`: the maximum number of agent invocations across all phases,
  with reconnaissance, critic, and verifier calls **reserved up
  front**, before any hunting is assigned. Reserved calls are never
  spent on hunting.
- `run_status`.
- `spent: {total_agent_invocations}`, updated at run close. Budget
  compliance is checked against the recorded `spent` versus `budget`,
  not against prose.
- `cap_override_approved_by`, required whenever a run's cap exceeds
  the profile cap below: the higher cap is valid only with Pratik's
  approval recorded in this field.

Caps are total agent invocations, reserved calls included:

| Profile | Cap (total agent invocations) |
| --- | --- |
| quick | ≤ 20 |
| standard | ≤ 40 |
| deep | ≤ 60 |

A run may set a lower cap than its profile's. 

**Budget-exhaustion rule.** If the remaining budget cannot validate
every candidate, the run ends with `run_status: incomplete` and
`incomplete_reason: validation_budget_exhausted`. Unvalidated
candidates remain in the coverage ledger only — never relabelled,
never entered in `findings.json` under any verdict, and never reported
as a completed pass. A partial report is permitted only if its first
section states that candidate validation is incomplete and lists the
affected fingerprints and ledger units.

**Worked fixture.** `scripts/audit/examples/budget-exhaustion.json` is
a `run-metadata.json` at its cap (quick profile, `spent` at 20 of 20)
with one unvalidated candidate, and
`scripts/audit/examples/budget-exhaustion.expected.json`, beside it,
records its expected terminal state: `incomplete` /
`validation_budget_exhausted`, candidate unlabelled. The fixture was
checked against its expected state in this task's verification (§6).

## 5. Findings schema: the AEP profile

### 5.1 Branch taken

P0 Q2 recorded distortion, so the verbatim-adoption line is **not**
written: this lane does not adopt the vendored schema verbatim.
Instead, `docs/security-audit-schema-profile.json` is a
machine-consumable JSON Schema — the vendored `report-schema.json` at
pin `c1c8a8c` with exactly the deltas below and no others — and
`scripts/audit/validate_findings_profile.cjs` is the lane's validation
route for findings. The vendored validator hardcodes its schema load
and can never validate a profile, which is why the profile route is
AEP-owned code.

### 5.2 The deltas, and the distortion forcing each

One delta per recorded Q2 distortion. Q2 recorded, for Artifact 1
(execution-based), framing distortion in `execution.attacker_perspective`,
in `execution.payloads`, and in the `trace` shape; and, for Artifact 2
(static-proof), that the `execution` object cannot be populated as
designed without fabricating an `observed_result` — its distortions sit
in `execution.attacker_perspective` (framing),
`execution.payloads` (forced), `execution.instructions` (partial), and
`execution.observed_result` (forced). Because the two artifacts distort
the same two `execution` fields, those fields take one delta each,
answering both artifacts.

| Delta | Profile change | Forcing Q2 distortion |
| --- | --- | --- |
| P1 | `execution.attacker_perspective` is optional, not required, in the confirmed branch; when present it names the position occupying that role, which need not be an attacker | Artifact 1: no external attacker exists — the position is a same-uid process, or in the honest path no adversary at all. Artifact 2: no attacker; the position is an operator or cron, and the field also had to assert the non-execution to stay truthful |
| P2 | `execution.payloads` semantics: the constructed input(s) or supplied state changes contributed as data for the demonstration — not necessarily payloads delivered by an attacker to a target interface | Artifact 1: the entries are post-seal tree mutations, recorded under the payloads label only because the schema required the field. Artifact 2: no payload exists when nothing is executed; the field had to be populated with a statement of that fact |
| P3 | `trace` entry `kind` gains `composition`: an entry that composes components — including a non-code, documentation-sanctioned decision point — rather than a code entrypoint, propagation, or sink step | Artifact 1: the schema's trace is a linear entrypoint-to-propagation-to-sink source path, but the defect is a composition across the validator, a shipped skill's completion gate, and process lifetime; its final entry is a sanctioned completion decision, not a code sink — faithful in content, forced in shape |
| P4 | Static-proof `execution` semantics: `instructions` are the constructed-trace re-walk steps and `observed_result` is the invariant violation as walked (the §3 population contract), not steps and a result of an execution | Artifact 2: `observed_result` as designed requires a nonempty factual result of an execution — nothing was executed, so a faithful population would fabricate one; `instructions` described a static reading procedure, not a reproduction execution |

P1 and P3 are structural: a profile record omitting
`attacker_perspective`, or using a `composition` trace entry, is
invalid under the vendored schema and valid under the profile. P2 and
P4 are semantic, carried in the profile schema's field descriptions:
no structural validator can detect them, because — as Q2 itself
showed — validator success proves format and consistency only.

No other differences from the vendored schema exist. In particular,
the profile does not relax any requirement of the other two branches:
an `audit:needs_validation` record still requires `blockers`, and an
`audit:rejected` record still requires `reason`.

### 5.3 The profile validation route

`node scripts/audit/validate_findings_profile.cjs <findings.json>`
loads `docs/security-audit-schema-profile.json`, validates a findings
file the same way the vendored validator does (top-level array), and
exits 0 on pass or nonzero with each violation named. It reuses the
vendored validator's exported document validation, so schema
interpretation and finding-level semantic checks are identical; the
sole adjustment is delta P3, under which a trace-ordering error naming
a `composition` entry is not a profile error. Tasks A2, A3, and A7
invoke this route wherever the vendored validator would otherwise be
named.

## 6. Validation of this protocol (Task A1, first use)

All runs below were performed in this worktree at the time this
protocol was written. The Q2 artifacts' profile forms were rebuilt
under `/tmp` from the final forms embedded in the spike record:
Artifact 1 with `attacker_perspective` omitted and its final trace
entry re-kinded as `composition`; Artifact 2 with
`attacker_perspective` omitted, `payloads` carrying its constructed
input, `observed_result` carrying the invariant violation as walked,
and its `evidence` stating that no target code was executed.

**Paired result — profile route versus vendored route:**

```text
$ node scripts/audit/validate_findings_profile.cjs /tmp/a1-profile-artifact1.json
PASS: 1 findings valid (AEP profile)   (exit 0)
$ node scripts/audit/validate_findings_profile.cjs /tmp/a1-profile-artifact2.json
PASS: 1 findings valid (AEP profile)   (exit 0)

$ node reference/security-audit-skill/skills/security-audit/validate-findings.cjs /tmp/a1-profile-artifact1.json
ERROR: $[0]: must match exactly one schema in oneOf; matched 0
ERROR: $[0].trace[2].kind: invalid value "composition" (expected one of "entrypoint", "propagation", "sink")
ERROR: $[0].execution: missing required field "attacker_perspective"
ERROR: $[0].trace[2].kind: must be "sink", got "composition"
FAIL: 4 validation error(s)   (exit 1)

$ node reference/security-audit-skill/skills/security-audit/validate-findings.cjs /tmp/a1-profile-artifact2.json
ERROR: $[0]: must match exactly one schema in oneOf; matched 0
ERROR: $[0].execution: missing required field "attacker_perspective"
FAIL: 2 validation error(s)   (exit 1)
```

Every vendored error above names a recorded Q2 distortion field —
`trace` and `execution.attacker_perspective` for Artifact 1,
`execution.attacker_perspective` for Artifact 2 — and no vendored error
names any other field. The divergence is the profile's justification:
the same records the profile route passes, the vendored route rejects
on exactly the fields Q2 recorded as distorted. (P2 and P4 are
description-level deltas and, as §5.2 notes, produce no structural
error on either route.) For reference, the artifacts' original Q2 forms
still pass the vendored validator, as the spike record recorded — that
pass, on semantically distorted records, is the distortion evidence
itself.

**Negative test — `audit:needs_validation` without `blockers`:**

```text
$ node scripts/audit/validate_findings_profile.cjs /tmp/a1-negative-needs-validation-no-blockers.json
ERROR: $[0]: must match exactly one schema in oneOf; matched 0
ERROR: $[0]: missing required field "blockers"
FAIL: 2 validation error(s)   (exit 1)
```

A hand-built `audit:needs_validation` record that is otherwise
well-formed but omits `blockers` **fails** the adopted profile route,
as this protocol's §1 contract requires.

**Budget fixture check:** `scripts/audit/examples/budget-exhaustion.json`
was checked field-by-field against
`scripts/audit/examples/budget-exhaustion.expected.json`: `run_status`,
`incomplete_reason`, `spent`, and the cap all match the recorded
expected terminal state (`incomplete` / `validation_budget_exhausted`,
candidate unlabelled). Result: match.
