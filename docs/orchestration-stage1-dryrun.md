# Stage 1 acceptance — dry-run record

Acceptance run for the issue-orchestration Stage 1 build (workflow
loader, normalized model, tracker adapters, eligibility engine, dry-run
CLI with demand-observation log). Executed 2026-10-25. The comparison
below is pre-registered: the independent expectation was computed and
recorded in this document **before** the orchestrator's output existed
in it.

## Artifacts

- Spec (operator storage, not committed to this repo — it is
  configuration for the measured track):
  `~/workspace/goals/autonomous-code-defense-factory/hidden_files/orch-stage1/dap.workflow.md`
- Observation log:
  `~/workspace/goals/autonomous-code-defense-factory/hidden_files/orch-stage1/dap-observation.jsonl`
- Tool under test: this repo, branch `feat/orch-stage1` (the dry-run
  CLI lands with this document).

## The spec, as declared before the run

```yaml
tracker: beads
project_root: ~/workspace/repos/document-accessibility-pipeline
assignee: CloudBot Neo-green
active_states: [open]
terminal_states: [closed]
```

Declaration notes:

- **Assignee `CloudBot Neo-green`** is the track's builder identity,
  verified against the live assignee census of the full fetch (82
  records): absent on 65, `CloudBot Neo-green` on 14, `agent` on 3.
- **Active states `[open]`** reflect the track's dispatch reality:
  `in_progress` work is already claimed by the regime that picked it
  up. Terminal states `[closed]`.
- **`managed_by` is deliberately unset.** The builder crons still own
  this track's dispatch; Stage 1 only measures it. The one-dispatcher
  declaration is therefore absent, and preflight's printout shows the
  absence (the declaration's only mechanical foothold at this stage).
- **`issue_types` is omitted** so the loader's materialized default
  allowlist applies; preflight prints the effective list.
- The spec's prompt-template body states honestly that the spec exists
  for Stage 1 dry-run measurement of this track. Nothing is
  dispatched.

Setup fact: the fleet lanes directory (`~/workspace/worktrees/.lanes`,
resolved exactly as lane-coord resolves it) did not exist on this
machine — no lane claim has ever been made here. It was created empty
(the same `mkdir -p` lane-coord performs on its own write paths)
before the run, so the claim view's verdict — zero manifests, zero
active claims — is observed, not assumed. The dry-run itself wrote
nothing there.

## Independent expectation (pre-registered)

Computed from recorded `bd` payloads with hand-applied filters — no
orchestrator code involved. Filters, per the acceptance protocol:
keep a record iff (a) its assignee equals the spec's assignee,
(b) its status maps into the spec's active-state set, (c) its
`issue_type` is in the effective allowlist, and (d) every embedded
`blocks`-edge target is `closed`. Rejection reasons follow the same
manual pass with the engine's documented precedence (terminal →
not-active → not-assigned → blocked). The brief's named route —
filters (a) and (c) over `bd ready --json`, which pre-applies
open + unblocked — was computed as a cross-check and agrees exactly
(same set; the filter-route set is a subset of `bd ready`'s 10
records, as it must be).

Fetched type census (records per `issue_type`, before filtering):
task 49, spike 9, story 6, bug 6, epic 6, decision 5, chore 1 — 82
records fetched, 11 excluded by the allowlist (6 epic + 5 decision),
71 candidates. Status census: closed 40, open 39, in_progress 3.

**Expected would-dispatch list: empty.** Every record assigned to the
builder identity is closed (11) or already in progress (3) — none is
`open` — and every open candidate is assigned to someone else or to
no one. This is a property of the track at run time, recorded as
measured, not adjusted.

Expected rejections (71 candidates):

- `STATE_TERMINAL` (39): dap-5hy.1, dap-5hy.2, dap-5hy.4, dap-5hy.5,
  dap-jo9.1.2, dap-jo9.1.3, dap-jo9.1.5.1, dap-jo9.1.6.1, dap-jo9.1.6.2,
  dap-jo9.10, dap-jo9.11, dap-jo9.12, dap-jo9.13, dap-jo9.15,
  dap-jo9.16, dap-jo9.17, dap-jo9.2.1.1, dap-jo9.2.1.2, dap-jo9.2.3.1,
  dap-jo9.2.3.3, dap-jo9.2.3.4, dap-jo9.2.4.1, dap-jo9.2.5.1,
  dap-jo9.2.5.2, dap-jo9.2.5.3, dap-jo9.2.5.4, dap-jo9.2.5.5,
  dap-jo9.2.5.6, dap-jo9.2.5.7, dap-jo9.2.5.8, dap-jo9.3.1.1,
  dap-jo9.3.3.1, dap-jo9.3.4.1, dap-jo9.4.1.1, dap-jo9.5.1, dap-jo9.6,
  dap-jo9.7, dap-jo9.8, dap-jo9.9 — all `closed`.
- `STATE_NOT_ACTIVE` (3): dap-5hy, dap-jo9.1.1, dap-jo9.1.6.3 — all
  `in_progress`.
- `NOT_ASSIGNED` (29): dap-2dj, dap-5hy.3, dap-5hy.6, dap-jo9.1.5,
  dap-jo9.1.6.4, dap-jo9.14, dap-jo9.2.1, dap-jo9.2.1.3, dap-jo9.2.2,
  dap-jo9.2.3, dap-jo9.2.3.2, dap-jo9.2.4, dap-jo9.2.4.2, dap-jo9.2.5,
  dap-jo9.2.5.9, dap-jo9.3.1, dap-jo9.3.1.2, dap-jo9.3.2, dap-jo9.3.3,
  dap-jo9.3.3.2, dap-jo9.3.3.3, dap-jo9.3.4, dap-jo9.3.4.2,
  dap-jo9.3.4.3, dap-jo9.4.1, dap-jo9.4.1.2, dap-jo9.5, dap-jo9.5.2,
  dap-jo9.5.3 — all `open`, none assigned to the builder identity.
- `BLOCKED` (0): under this spec no candidate reaches the blocker
  check — every open candidate fails assignment first (the documented
  precedence), and no open candidate is assigned to the builder
  identity. The `BLOCKED` path is exercised against recorded payloads
  in the unit suites (the beads fixture's blocked record, the engine
  battery); on this track at this time it has no instance to report.

## Orchestrator output (verbatim)

Preflight:

```
ok: workflow loads (tracker: beads)
ok: tracker tool: bd found at ~/go/bin/bd
ok: lanes directory: resolved as lane-coord resolves it (0 active claims)
ok: issue_types (effective): task, bug, story, spike, chore
ok: managed_by: absent (the one-dispatcher declaration)
ok: repo/remote agreement: n/a (beads tracker)
preflight: PASS
```

Dry-run (with `--log`):

```
dry-run: ~/workspace/goals/autonomous-code-defense-factory/hidden_files/orch-stage1/dap.workflow.md (tracker: beads)
would dispatch (0):
rejected (71):
  dap-2dj NOT_ASSIGNED (assigned_to_worker is false)
  dap-5hy STATE_NOT_ACTIVE (in_progress)
  dap-5hy.1 STATE_TERMINAL (closed)
  dap-5hy.2 STATE_TERMINAL (closed)
  dap-5hy.3 NOT_ASSIGNED (assigned_to_worker is false)
  dap-5hy.4 STATE_TERMINAL (closed)
  dap-5hy.5 STATE_TERMINAL (closed)
  dap-5hy.6 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.1.1 STATE_NOT_ACTIVE (in_progress)
  dap-jo9.1.2 STATE_TERMINAL (closed)
  dap-jo9.1.3 STATE_TERMINAL (closed)
  dap-jo9.1.5 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.1.5.1 STATE_TERMINAL (closed)
  dap-jo9.1.6.1 STATE_TERMINAL (closed)
  dap-jo9.1.6.2 STATE_TERMINAL (closed)
  dap-jo9.1.6.3 STATE_NOT_ACTIVE (in_progress)
  dap-jo9.1.6.4 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.10 STATE_TERMINAL (closed)
  dap-jo9.11 STATE_TERMINAL (closed)
  dap-jo9.12 STATE_TERMINAL (closed)
  dap-jo9.13 STATE_TERMINAL (closed)
  dap-jo9.14 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.15 STATE_TERMINAL (closed)
  dap-jo9.16 STATE_TERMINAL (closed)
  dap-jo9.17 STATE_TERMINAL (closed)
  dap-jo9.2.1 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.2.1.1 STATE_TERMINAL (closed)
  dap-jo9.2.1.2 STATE_TERMINAL (closed)
  dap-jo9.2.1.3 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.2.2 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.2.3 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.2.3.1 STATE_TERMINAL (closed)
  dap-jo9.2.3.2 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.2.3.3 STATE_TERMINAL (closed)
  dap-jo9.2.3.4 STATE_TERMINAL (closed)
  dap-jo9.2.4 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.2.4.1 STATE_TERMINAL (closed)
  dap-jo9.2.4.2 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.2.5 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.2.5.1 STATE_TERMINAL (closed)
  dap-jo9.2.5.2 STATE_TERMINAL (closed)
  dap-jo9.2.5.3 STATE_TERMINAL (closed)
  dap-jo9.2.5.4 STATE_TERMINAL (closed)
  dap-jo9.2.5.5 STATE_TERMINAL (closed)
  dap-jo9.2.5.6 STATE_TERMINAL (closed)
  dap-jo9.2.5.7 STATE_TERMINAL (closed)
  dap-jo9.2.5.8 STATE_TERMINAL (closed)
  dap-jo9.2.5.9 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.3.1 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.3.1.1 STATE_TERMINAL (closed)
  dap-jo9.3.1.2 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.3.2 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.3.3 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.3.3.1 STATE_TERMINAL (closed)
  dap-jo9.3.3.2 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.3.3.3 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.3.4 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.3.4.1 STATE_TERMINAL (closed)
  dap-jo9.3.4.2 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.3.4.3 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.4.1 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.4.1.1 STATE_TERMINAL (closed)
  dap-jo9.4.1.2 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.5 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.5.1 STATE_TERMINAL (closed)
  dap-jo9.5.2 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.5.3 NOT_ASSIGNED (assigned_to_worker is false)
  dap-jo9.6 STATE_TERMINAL (closed)
  dap-jo9.7 STATE_TERMINAL (closed)
  dap-jo9.8 STATE_TERMINAL (closed)
  dap-jo9.9 STATE_TERMINAL (closed)
fetch: 82 records fetched, type-excluded: 11
claim-view warnings: none
stage-1 limits: per-state caps evaluated against this batch only (no store); GitHub blockers reflect label data only; the completed set is empty (no store exists in Stage 1)
observation appended: ~/workspace/goals/autonomous-code-defense-factory/hidden_files/orch-stage1/dap-observation.jsonl
```

`--summarize` over the resulting log (one observation — the
acceptance run's own entry):

```
observations: 1
window span: 0s
ready-set size: min 0, median 0, max 0
mean churn: n/a
ready-wait basis: updated_at_lb (indicative only)
ready-wait: n/a
pickup lag: n/a
non-empty ready fraction: 0/1
```

## Comparison

**Exact match.** The would-dispatch list is empty in both
computations. All 71 rejection identifiers match, and every rejection
reason *and* detail matches the independent expectation — zero
discrepancies, so there is nothing to explain away. The run's fetch
accounting (82 fetched, 11 type-excluded) reproduces the independent
census exactly, and the appended observation is schema-conformant
with basis `updated_at_lb` (indicative only): this track's `bd`
payloads carry no status-history field, so status-entry coverage is
0 and no `status_entry` figure is manufactured.

Two readings of the result, recorded because they are the demand
evidence Stage 1 exists to produce:

- Under the builder-identity lens (assigned to the builder, `open`,
  unblocked), nothing is waiting: the assigned work is closed or
  already in progress. The open pool the current regime actually
  draws from is unassigned — of `bd ready`'s 10 records, the four in
  the type allowlist (dap-2dj, dap-jo9.14, dap-5hy.3, dap-5hy.6) all
  carry no assignee and appear above as `NOT_ASSIGNED`. Whether
  unassigned-ready work *waits* is what the accrual window measures;
  this single tick cannot say.
- `BLOCKED` has no instance under this spec (see the expectation):
  blocked open work on this track is uniformly unassigned, and the
  assignment check precedes the blocker check. The blocker machinery
  is covered by the unit suites against recorded payloads; the
  observation log will show `BLOCKED` rejections the first time an
  assigned record is blocked.

## No tracker writes

Both adapters' write methods still raise
`NotImplementedError("read-only in Stage 1")` — asserted directly
against `BeadsAdapter` and `GitHubAdapter` (`comment` and
`transition`) at acceptance time. The dry-run created no files
outside the observation log (asserted by the CLI suite on a temp
tree), constructed no store, and `bd` was invoked read-only
throughout — `list` for the fetch, and `ready --json` for the
independent cross-check recorded in the expectation section above.

## GitHub section — deferred (Step 5)

The conditional live GitHub section is **deferred**, and the
deferral is recorded here naming both of its gates:

- **G3 (gateway merged): satisfied.** The budgeted gateway is merged
  and installed on this fleet.
- **G2 (label convention decided): not satisfied.** The operator has
  not decided the label convention the repo-hosted track's
  normalization depends on.

With either gate unmet, the live GitHub dry-run does not run and no
live GitHub call was made. The D5 cadence/cap re-pin that the
section would have fed (300 s / 6 calls per poll, from a measured
points cost) is deferred with it; the numbers stand as estimates
until the measurement exists. The beads acceptance above stands
alone.

## Observation accrual (Step 6)

The demand window accrues only if something runs the logger. The
accrual driver is a named cron entry, created by the operator as
this task lands:

- **Name:** `orch-demand-accrual`
- **Schedule:** every 2 hours (the track's existing dispatch
  cadence), for the operator-set window (default one month).
- **Command:** `PYTHONPATH=<AEP repo>/scripts python3 -m orch.cli
  dry-run --workflow ~/workspace/goals/autonomous-code-defense-factory/hidden_files/orch-stage1/dap.workflow.md
  --log ~/workspace/goals/autonomous-code-defense-factory/hidden_files/orch-stage1/dap-observation.jsonl`
  (via a login shell, so the tracker tool resolves as it does
  interactively).
- **Owner:** the operator. Silent on success; failures are reported
  to the AEP lane chat.

Without that driver the window does not accrue and the Election
Gate has nothing to read — stated here, not assumed. **Window-end
review:** when the window closes, the operator runs
`orch dry-run --summarize` over the accrued log and records the
gate metrics and the threshold comparison in this document; that
review is where the Stage 2 election is convened.
