# Security-audit protocol — the AEP audit lane

This document is the audit lane's protocol: the verdict vocabulary and
contracts, the environment condition for this VM, the static-proof trace
contract, the run-budget contract, the findings-schema profile the
lane validates against, the coverage ledger and run-artifact layout
that are the system of record for coverage (§7), the verifier
phases with dispatch-recorded distinctness (§9), and the standing
hunter checklists and self-audit targets (§10). It is AEP-owned. The vendored security-audit
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
- Coverage ledger: vendored `RECONNAISSANCE.md`, "Deterministic
  coverage ledger", and the vendored `validate-coverage-ledger.cjs`.
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

- `budget`: the maximum number of agent invocations across all phases
  — a single integer. Reconnaissance, critic, and verifier calls are
  **reserved up front**, before any hunting is assigned, and the
  reserved per-role counts are recorded in the sibling field
  `budget_reserved`. Reserved calls are never spent on hunting.
- `run_status`.
- `spent: {total_agent_invocations}`, updated at run close. Budget
  compliance (AC9) is checked as exactly the recorded
  `spent.total_agent_invocations` versus `budget`, not against prose.
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

## 7. Coverage ledger: the system of record for coverage

The coverage ledger is the coverage claim. An architecture summary, an
agent count, or a generic "auth reviewed" sentence is not coverage
evidence. This section adopts the vendored `RECONNAISSANCE.md` ledger
construction and the vendored `validate-coverage-ledger.cjs` as the
lane's ledger system of record: the deterministic unit set, the
canonical-ID derivation, the status state table, the attempts archive,
and the run-artifact layout every audit run must emit.

### 7.1 Unit derivation

Reconnaissance seeds the ledger deterministically, before any hunting
is assigned: one unit for every material combination of the identity
tuple

> surface × trust boundary × subsystem × attack class + lifecycle

where lifecycle is part of the tuple when it is material (the `deep`
profile adds lifecycle modes; the `quick` profile coarsens the
subsystem dimension to the fixed canonical value
`profile/quick/all-in-scope-subsystems`).

The tuple is the unit's identity, but its axes are not five independent
multipliers. The independent axes are **surface**, **attack class**,
and **lifecycle**: the unit set is the product of the inventoried
surfaces, the applicable attack classes, and the lifecycle modes.
Trust boundary and subsystem are **determined per surface**, not chosen
independently for each combination: a surface's trust boundary is the
source control that defines the boundary for that surface's role, and
its subsystem is the package or directory that contains it. One surface
therefore contributes exactly one boundary and one subsystem to every
unit derived from it, however many attack classes and lifecycles it is
crossed with. The worked derivation of record (Task P0, Q3) is 32
surfaces × 9 attack classes × 2 lifecycles = 576 units; a reproducer
who multiplies five independent axis counts will not reproduce it.

Each dimension carries a human label and a stable, source-derived
value in `canonical_refs`; the same canonical reference names the same
source object across runs even if its display label changes. An
attack-class block reference is `FILE.md#` plus the exact class name as
written in that file — a stable identifier matched against the file
text, not a rendered anchor — and references are never derived by
lowercasing or slugging display labels. Each unit also keeps its
assignment-level blocks: `ordinary_attack_class_block` (null only when
no ordinary block applies), `selected_companion_blocks`, and
`excluded_blocks` with the source fact that excludes each. For a scoped
run, in-scope surfaces are seeded for assignment and discovered
excluded surfaces are retained as `out_of_scope` units, so a later
full run can turn them into current work.

### 7.2 Canonical `coverage_id` derivation

`coverage_id` is derived without lossy slugs:

1. Every canonical reference must be Unicode NFC with valid scalar
   values, visible content, no control, format, line/paragraph
   separator, or default-ignorable code point, and no surrounding
   whitespace.
2. Encode each reference's UTF-8 bytes with RFC 3986 percent encoding:
   leave only `A-Z a-z 0-9 - . _ ~` unescaped and use uppercase `%HH`
   for every other byte.
3. Join the encoded `surface`, `boundary`, `subsystem`, and
   `attack_class` references with `::`; append the encoded `lifecycle`
   reference when present.

Wave number, agent, verdict, severity, and line number are never part
of a reference or an ID. Units are sorted lexicographically by
`coverage_id` before each assignment. Duplicate IDs are fatal: a
duplicate ID whose semantic fields differ is a canonical identity
collision — never merged, never silently overwritten — and the
validator also rejects one semantic tuple represented by different
canonical references.

### 7.3 Status state table

Every unit is in exactly one of eight statuses, with the invariants
below (enforced by the vendored validator exactly):

| Status | Unit `agent_id` | `reviewed_paths` / `local_checks` | `result_fingerprints` | `unresolved` |
|---|---|---|---|---|
| `planned` | null | empty | empty | empty |
| `in_progress` | canonical owner | empty | empty | empty |
| `blocked` | canonical owner | both nonempty owned partial evidence | empty | nonempty blocker |
| `covered` | canonical owner | both nonempty | empty | empty |
| `candidate` | canonical owner | both nonempty | nonempty | optional |
| `deferred` | null | empty | empty | nonempty reason |
| `out_of_scope` | null | empty | empty | nonempty reason |
| `not_applicable` | null | empty | empty | nonempty reason |

Canonical agent IDs match `^[a-z0-9][a-z0-9_-]{0,63}$`, are not Windows
device names, and are lowercase-mandatory, so one ledger cannot contain
case-fold aliases. The unit `agent_id` records the assignment owner.
Every check records its own `agent_id` and nonempty `reviewed_paths`;
the unit-level `reviewed_paths` is exactly the union of its checks'
paths. A source-only check uses `artifact: null`; an artifact-bearing
check must satisfy the artifact-path rule in §7.6.

`prior_status` carries the unit's relationship to prior runs: `new`
marks a surface first seen in this run when compatible prior ledgers
exist; `none` marks a unit seeded when no compatible prior ledger is
available. Prior `deferred`, `blocked`, `out_of_scope`, and
changed-source units initialize as current `planned` work when now in
scope.

### 7.4 Attempts archive

`attempts` is an append-only archive for evidence-bearing assignments
that a coverage critic reopens. Before reassignment, the parent
appends the prior unit's exact `wave`, `status`, `agent_id`,
`reviewed_paths`, `local_checks`, `result_fingerprints`, and
`unresolved`, plus the critic's source-backed `reassignment_reason`.
Only `blocked`, `covered`, and `candidate` states can be archived.
Archived attempts retain the same state and evidence invariants as
live units, use strictly increasing waves, and every archived wave is
below the current wave. The next assignment increments `wave`, uses a
fresh owner, and starts with empty live evidence; an archived owner's
checks or artifacts are never copied into the live state, and an
artifact from an archived attempt cannot be reused by a later check. A
later live terminal state contains only the new attempt's evidence;
the archive remains unchanged. If the profile or budget prevents
another assignment, `wave` increments and the live state is `deferred`
with null owner, empty evidence, and the stop reason in `unresolved`.

### 7.5 Sole writer, and validation cadence

The parent is the ledger's sole writer. The parent initializes
`run-metadata.json`, applies the §4 budget gate, and creates the agent
scratch roots and the shared ledger before hunting; hunters return
structured results, and the parent closes units only from the paths
and checks in a hunter's structured result. No agent writes the ledger
directly.

The parent runs the vendored ledger validator after seeding, after
every parent update, and before the run's final report, and fixes
every error before assigning work or making a coverage claim. The
validator rejects input beyond 5 MiB, 64 nesting levels, 10,000 units,
1,000 entries in a nested collection, or 500,000 traversed values, and
caps reported validation errors at 100; in practice the 5 MiB byte
limit holds roughly 2,000–5,000 realistic units, so it binds before
the 10,000-unit cap.

### 7.6 Run-artifact layout

Runs live outside the target repo by default (the source's
write-isolation rule). The run root is

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
and nothing else at the run root. `run-metadata.json` carries the §4
budget shape, plus the egress inventory: any run that sends task
material to a remote model API records the provider class and the
material classes sent.

A local check's artifact is evidence only under exactly
`agents/<agent_id>/artifacts/` — the vendored ledger validator's
`isOwnedArtifactPath` requires the artifact path, relative to the run
root, to carry the prefix `agents/<check.agent_id>/artifacts/` for the
check's own agent ID. Scratch paths, output-root files, symlinks,
special files, and another check owner's artifacts are not evidence.

An in-repo output directory is permitted only if **both** preconditions
hold: the user selects it, **and** version control ignores the whole
directory.

### 7.7 The `result_fingerprints` join

Only `candidate` units carry `result_fingerprints` (nonempty); every
other status keeps the list empty (§7.3). A unit's `result_fingerprints`
list links a finding to the unit whose owner hunted it — the hunter
anchor Task A3's distinctness checker relies on: the attestation
sidecar's `hunter_agent_id` must equal the `agent_id` of a check
recorded on a ledger unit whose `result_fingerprints` contain the
fingerprint. Verifier identity lives only in the attestation sidecar
and the dispatch log; for fresh candidates the ledger records no
verifier identity anywhere.

### 7.8 The limit, and the coverage-citation rule

**Validator success proves format and ledger consistency only.** It
proves nothing about the truth of a unit's evidence or of any finding;
truthfulness is carried by Task A3's fresh-verifier phases, not by the
validators.

A coverage claim in any AEP report must cite ledger units from a real
run under the external run root (§7.6) — never the examples directory,
and never prose. Accordingly, `scripts/audit/examples/synthetic-ledger.json`
(§8) is a shape reference only: it is excluded from coverage claims by
this rule, and it is not acceptance evidence for anything.

## 8. Validation of the ledger adoption (Task A2, first use)

All runs below were performed in this worktree at the time this
section was written.

**Shipped validator suites** (the suites use `node:test`; there is no
header run command):

```text
$ node --test reference/security-audit-skill/skills/security-audit/validate-findings.test.cjs
tests 34, pass 34, fail 0   (exit 0)
$ node --test reference/security-audit-skill/skills/security-audit/validate-coverage-ledger.test.cjs
tests 31, pass 31, fail 0   (exit 0)
```

Both counts match the adoption analysis (34 and 31).

**Synthetic example.** `scripts/audit/examples/synthetic-ledger.json`
is Task P0's Q3 synthetic ledger — the 576-unit ledger over this
worktree's `scripts/` tree recorded in
`docs/security-audit-spikes-2026-10-26.md` — committed with
`"aep_bookkeeping": {"synthetic": true}` added to every unit (the
source tolerates parent bookkeeping fields on units; a top-level key
would break the array shape and the validator). The source ledger's
units are all `planned` with `agent_id: null`, empty `attempts`, and
empty `local_checks`, so it contains no agent IDs; had any owner or
agent ID appeared, it would have been rewritten under the reserved
`example-*` prefix, consistently, before committing. Validation of the
committed file:

```text
$ node reference/security-audit-skill/skills/security-audit/validate-coverage-ledger.cjs scripts/audit/examples/synthetic-ledger.json
PASS: 576 coverage units valid   (exit 0)
```

Recorded as a shape check only, per §7.8.

**Negative test — duplicated `coverage_id`.** Two scratch copies were
made under `/tmp` (never committed). In the first, unit 1's
`coverage_id` was overwritten with unit 0's, leaving unit 1's semantic
fields intact:

```text
$ node reference/security-audit-skill/skills/security-audit/validate-coverage-ledger.cjs /tmp/a2-duplicate-ledger.json
ERROR: $[1].coverage_id: expected canonical ID "scripts%2Fapply-domain-blocks.sh::scripts%2Fpolicy.data%23operator-invocation-boundary::scripts::ATTACK-CLASSES.md%23Access%20control::lifecycle%2Fsteady-state-operation"
ERROR: $[1].coverage_id: canonical identity collision with different semantic fields at $[0]
FAIL: 2 validation error(s)   (exit 1)
```

In the second, an exact copy of unit 0 was appended as a 577th unit:

```text
$ node reference/security-audit-skill/skills/security-audit/validate-coverage-ledger.cjs /tmp/a2-duplicate-unit-ledger.json
ERROR: $[576].coverage_id: duplicate coverage ID at $[0]
ERROR: $[576].coverage_id: units must be sorted lexicographically
FAIL: 2 validation error(s)   (exit 1)
```

Both duplicated-ID ledgers are **rejected**, as §7.2 requires.

## 9. Verifier phases and dispatch-recorded distinctness

Coverage (§7) records what was hunted; this section records who
verified it, and makes the finder != verifier rule checkable instead
of asserted. It adopts the vendored `VALIDATION-AND-REPORTING.md`
Phases 3 and 5, with identity recorded in the attestation sidecar and
the dispatch log — never inside findings records, which stay
schema-pure (§5; the vendored schema forbids additional properties at
record level). The sidecar and dispatch-log contract is
`scripts/audit/verification-attestations.schema.md`; enforcement is
`scripts/audit/check_verifier_distinctness.cjs`.

### 9.1 Fresh verifier per candidate (Phase 3)

Every unique proposed `audit:confirmed` and `audit:needs_validation`
candidate is validated by a fresh verifier that did not hunt it. The
verifier re-reads every cited source location and independently runs
any decisive check it can reproduce safely, under the environment
condition in §2. A static-proof candidate (§3) stands only when that
verifier has independently re-walked the trace and the re-walk is
recorded as agreed in the sidecar.

### 9.2 Fresh verifier per final record (Phase 5)

Every record retained in `findings.json` is then verified again, as a
final record, by a fresh verifier that did not hunt it and did not
perform its Phase 3 validation. In a `quick` run the source merges
Phases 3+5: the Phase 3 verifier also performs the final-record
checks, so `phase3_verifier_agent_id == phase5_verifier_agent_id` is
required and permitted in that profile, and only hunter-distinctness
is checked between the phases. Every other profile keeps the two
passes separate. Independent review of a confirmed record is never
skipped in any profile.

**Malformed verifier returns are discarded unrepaired.** A verifier
result that is malformed or prose-wrapped — in either phase — is
discarded without repair and re-run with a fresh verifier when the
budget permits; otherwise the candidate remains an unvalidated ledger
candidate under the budget rule in §4, and never enters
`findings.json` under any verdict.

### 9.3 Material replacements: the third-verifier rule

A Phase 5 verifier may return a replacement record instead of
`verified`. Whether that replacement is **material** is mechanical,
decided from recorded inputs only: a replacement is material iff the
sidecar's `superseded_verdict` / `superseded_severity` (the record the
finding replaced) versus the finding's current verdict / overall
severity shows movement toward `confirmed` (verdict rank `rejected` <
`needs_validation` < `confirmed`) or a severity increase (rank
`informational` < `low` < `medium` < `high` < `critical`).

A material replacement is applied only after verification by a third
verifier: an agent distinct from the hunter, the Phase 3 verifier,
the Phase 5 verifier, and the replacement's proposer (the Phase 5
verifier that proposed the replacement). That third verifier is
recorded as the entry's `replacement_verifier_agent_id`. If another
material replacement results, the rule repeats with a fresh verifier.
If budget or independence is unavailable, the disputed record is
removed from `findings.json`, its ledger unit stays an unresolved
candidate, and the run reports `run_status: incomplete`. Non-material
wording or line corrections may be applied directly when they do not
change meaning or evidence.

### 9.4 Dispatch-time recording

Identity is recorded at dispatch, never asserted after the fact:

- The orchestrator appends to the run's `dispatch-log.json` **at each
  dispatch**: `{agent_id, role, session_id, dispatched_at}`, using IDs
  in the ledger's canonical pattern
  (`/^[a-z0-9][a-z0-9_-]{0,63}$/`). A returned payload asserting its
  own identity is ignored.
- The attestation sidecar (`verification-attestations.json`) carries
  exactly one entry per `confirmed` / `needs_validation` fingerprint,
  with the hunter, Phase 3 verifier, Phase 5 verifier (nullable),
  replacement verifier (nullable), `confirmation_basis`,
  `superseded_verdict` + `superseded_severity` (nullable),
  `static_rewalk`, and the freshness hashes `findings_sha256` +
  `ledger_sha256` binding the entry to the artifacts as checked. An
  attestation written against earlier artifacts fails.
- The hunter side anchors in the ledger (§7.7): the sidecar's
  `hunter_agent_id` must equal the `agent_id` owning a check on a
  ledger unit whose `result_fingerprints` contain the fingerprint.
  Verifier identity lives only in the sidecar and the dispatch log.
- IDs under the reserved `example-*` prefix are invalid in real runs;
  they belong only to shape references under `examples/`.

### 9.5 The checker contract, and what it proves

`check_verifier_distinctness.cjs` exits 0 iff every `confirmed` /
`needs_validation` record satisfies all of the rules above:
completeness (exactly one sidecar entry per such fingerprint; absence
is a fail), the hunter anchor, profile-aware distinctness, the
mechanical materiality rule, the static re-walk requirement,
freshness hashes matching the files as checked, and dispatch
resolution plus ordering (every sidecar ID resolves to a dispatch-log
entry in its role; roles carried by different agents carry distinct
`session_id`s; each verifier's `dispatched_at` postdates the hunter's
dispatch for that fingerprint). A nonzero exit names the offending
fingerprints, and the run reports `run_status: incomplete` with its
findings not publishable as verified. The checker reads the four
artifacts, compares identities, anchors, hashes, and dispatch
ordering, and reports; it edits no artifact and judges no finding's
truth.

**What the checker proves, stated honestly:** distinct recorded agent
IDs, recorded at dispatch in the run's dispatch log and
consistency-checked (hunter anchored in the ledger; artifacts
hash-bound). It proves label distinctness over dispatch-recorded
artifacts — fabrication is **detectable** (by sampling dispatch refs
against the runtime's own subagent records, which the parent does not
author; Task A7 samples three attestations), **not impossible**. It
does not prove the sessions' contexts were independent beyond the
dispatch record — that residue is the same fresh-context trust AEP's
SDD already runs on, now made auditable instead of invisible.

### 9.6 Validation of this section (Task A3, first use)

The checker suite was written first and failed for the checker's
absence (10 tests, 0 pass, module not found), then passed against the
implementation:

```text
$ node --test scripts/audit/test/check_verifier_distinctness.test.cjs
tests 10, pass 10, fail 0   (exit 0)
```

The suite's fixtures: (a) hunter == verifier fails naming the
fingerprint; (b) a missing hunter anchor fails; (c) a material
strengthening (superseded `needs_validation` → `confirmed`) with only
two distinct agents fails; (d) a clean two-candidate run passes; (e) a
record with no sidecar entry fails; (f) an `example-*` ID in a run
directory not under `examples/` fails; (g) a static-basis confirmed
record without `static_rewalk: "agreed"` fails; (h) a quick-profile
run with `phase3 == phase5` and a distinct hunter passes; (i) a
freshness-hash mismatch fails; (j) a verifier dispatched before the
hunter for the same fingerprint fails.

**Three-gate integration.** One fixture run (findings + ledger +
sidecar + dispatch log, built under `/tmp`, never committed) was run
through all three gates:

```text
$ node scripts/audit/validate_findings_profile.cjs /tmp/a3-integration-run/findings.json
PASS: 2 findings valid (AEP profile)   (exit 0)
$ node reference/security-audit-skill/skills/security-audit/validate-coverage-ledger.cjs /tmp/a3-integration-run/coverage-ledger.json
PASS: 2 coverage units valid   (exit 0)
$ node scripts/audit/check_verifier_distinctness.cjs /tmp/a3-integration-run
PASS: 2 verified record(s) satisfy finder/verifier distinctness   (exit 0)
```

The fixture (a) variant of the same run (Phase 3 verifier set to the
hunter) still fails the checker, naming `fp-candidate-one` (exit 1).

## 10. Standing hunter checklists and self-audit targets

Sections 1–9 define how an audit run works. This section defines the
two standing hunts the lane runs against AEP itself, so that audit
scheduling does not re-derive its targets each time: Election
E-first-run chooses from the target sets below, and later audit
scheduling cites this section as the standing targets list.

### 10.1 The standing prompt set, cited by path only

The standing prompt set for both checklists is the two vendored class
files, cited by path only:

- `reference/security-audit-skill/skills/security-audit/SUPPLY-CHAIN-AND-RELEASE.md`
- `reference/security-audit-skill/skills/security-audit/AI-AND-LLM.md`

No content is copied out of those files into this protocol. A
re-vendor that moves the pin therefore updates the checklist with
the pin, and the vendored tree itself is never edited by this lane.

A checklist run is an audit run. It emits the same artifacts as any
other run — `coverage-ledger.json`, `findings.json`,
`run-metadata.json`, the attestation sidecar, and the dispatch log —
into the external run root of §7.6, under the §1 verdicts and the §4
budget, with the §9 verifier rule (a fresh, dispatch-recorded
verifier distinct from the hunter) applied to every candidate.

### 10.2 Supply-chain and release: the standing target set

The supply-chain hunt targets AEP's own release path:

- The source publisher — the path by which AEP source is published.
- ghg, the GitHub gateway (`tools/ghg/`) — the counted, capped path
  every GitHub call in this lane takes.
- The vendoring path — the vendor manifests under `.github/` and the
  vendor-integrity job that checks the snapshots under `reference/`
  against them.

Two open residuals are already-tracked inputs to this hunt, named
here so a run treats them as known state, not as rediscoveries:

- Issue #38 — receipt stdout hashing: raw capped bytes for
  `stdout_sha256` on non-UTF-8 output.
- Issue #55 — the fs-digest format change invalidating pre-change fs
  receipts.

Two further items form this hunt's worked set. They are the two P0s
of the 2026-10-26 overseer panel report on main
(`review_panel_report_main_2026-10-26.md`). At Task A4's Step 0
re-check (2026-10-26) both were verified still open on this branch's
tree — the evidence below is the code as read, not the report's
prose — and neither was found in the tracked-issue record (a ghg
read of the repository's issues, all states, returned no issue for
either). Both are verifier evidence-integrity defects in AEP's own
release/verification path, which is why they sit in this class:

- Panel Action Item 1 — the environment-scrub policy is re-read per
  leg from an unbound file. `scripts/mechanical_verify.py:973`
  resolves the policy path from the environment or beside the
  verifier script — never from the verified root and never covered
  by the tree binding, whose fields are exactly root, head, tree
  digest, and mode (`tree_binding`,
  `scripts/mechanical_verify.py:1614`). `run_verification`
  (`scripts/mechanical_verify.py:1140`) builds each leg's
  environment by reading that policy afresh, and `run_all` calls it
  once per command (`scripts/mechanical_verify.py:1283`), while the
  run-start record samples the environment mode only once
  (`scripts/mechanical_verify.py:2263`). A mid-run rewrite of the
  policy file therefore changes what a later leg scrubs, under a
  sealed record that states the run-start mode.
- Panel Action Item 2 (panel item Y1) — fs mode has no between-legs
  tree re-validation. The `between_commands` hook is installed only
  when the binding mode is git
  (`scripts/mechanical_verify.py:2275`), and `binding_excursion`
  returns no excursion for any non-git mode
  (`scripts/mechanical_verify.py:1730`). In fs mode the seal is a
  single final-digest re-comparison
  (`scripts/mechanical_verify.py:2311`), so a between-legs
  swap-and-restore is invisible to the run: a later leg can execute
  on substituted bytes and the run can still seal.

### 10.3 AI and LLM: the standing target set

The AI/LLM hunt targets AEP as an agent system:

- The NeuroStrata inscription surface — what the lane writes into
  persistent memory, and what a later session retrieves from it: the
  persistent-memory poisoning class, where a bad inscription is
  durable, is retrieved as trusted context, and outlives the run
  that produced it.
- Subagent and MCP trust inheritance — what a delegated lane
  inherits from its parent and from the tools it is handed: lane
  delegation, and the scope of the ghg token a delegated agent acts
  under.
- Approval binding — whether an approval binds to the action it was
  given for: merge authorizations, and waiver handling, where a
  waiver recorded for one state must not be read as covering
  another.

### 10.4 Routing rule for findings

Where a finding lands is decided by what it is against (the E-venue
designed default, in force):

- A finding against AEP-owned code files as an AEP issue.
- A finding inside `reference/**` is never filed as an AEP defect
  and is never silently dropped. It routes to fork/upstream
  disposition, and the run records that disposition in the run's
  findings file as a verdict-shaped record — in this protocol's
  prose terms, an `audit:confirmed`, `audit:needs_validation`, or
  `audit:rejected` record as the evidence supports — whose
  disposition names either a filed fork issue or an explicit
  accept-risk note. A snapshot finding with neither name recorded is
  an incomplete run record, not a closed finding.
