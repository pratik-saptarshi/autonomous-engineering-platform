---
name: adopting-external-skills
description: Use when the owner directs adopting or adapting a third-party skill into this library — installing, amending, validating, and landing a named external skill. A review-only ask (analyze it, should we use it) does not start a run; answer it as a review. Not for libraries, frameworks, or vendored reference trees, and not for locally authored skills.
---

# Adopting External Skills

This skill is the standard procedure for adopting a third-party skill into
the live library: the procedure itself, plus the answers the first full run
preserved — the two-gate landing model, the stop conditions, the
anti-patterns. Judgment is not codified here; it is delegated to the
planning-wringer panel this workflow invokes at Phase 2. The checklist does
not replace the cognition that produced it.

A run starts when the owner directs adoption or adaptation work. Everything
below assumes that direction exists; the owner's earlier review-only
questions were answered as reviews, outside this workflow.

## Boundaries

**Skills only.** Libraries, frameworks, and vendored reference trees follow
the vendoring and adoption flows already in lane practice, not this one.

**First adoption only.** Re-adoption of a materially new upstream version of
an already-adopted skill is not a run of this workflow.

A locally authored skill is not a candidate (authoring one is the
`writing-skills` skill's territory). A candidate that would replace or
override NeuroStrata is barred at intake, without proceeding.

## Tiers

**Full** is the default tier: every phase below, no exceptions taken on the
executing agent's own say-so.

**Light** is an exception with a burden of proof, available only when ALL of
the following hold — classified by the candidate's directive surface (what
its text tells an agent to do), never by its medium:

1. The candidate is installed byte-verbatim at the recorded pin.
2. The tree inventory shows no executable files.
3. A quoted text scan finds no imperative directives to run commands, use
   tools, access the network, write files, or alter records or workflows.
4. A fresh reviewer — not the executing agent — confirms the classification
   from that evidence.
5. A one-page tier record (criterion plus evidence per criterion) is written
   to the run's working folder.
6. The tier and its evidence are a line item at the owner decision gate
   (Phase 3).

Any amendment — at intake or discovered later — escalates to a Full review
of that amendment before it is applied.

Cautionary case: humanizer was installed verbatim at intake on 2026-11-04,
then amended the same day (its FORK.md records two amendments) because
upstream text would have stripped load-bearing hedging from this
environment's records; it landed via PR #96. Under a medium-based test it
passed every criterion while being exactly the dangerous case: nothing in
it executed code, and its instructions were the blast radius.
diagnosing-superpowers makes the same point from the other side — prose
only, and it carried two P1 findings. Medium is not a safety property.

## Decisions that are always the owner's

The workflow must never take these, even under a general "proceed":

1. **The adoption verdict** (adopt / adopt dormant / fold-in / reject) and
   the execution mode.
2. **Every merge** — scope PR, sync/inclusion PR, and any PR the execution
   produces. Per-PR, on the exact head; conditional instructions are read
   narrowly.
3. **Deletions** of anything (branch, file, repo) — the standing deletion
   rule (named target, confirmation, 1-hour delay, reconfirmation) applies
   unchanged.
4. **Exceptions to standing rules** — e.g. rewriting a candidate's
   frontmatter description, or treating pre-publication corrections as the
   same fork version.
5. **The first production target and its owning lane**, and any transfer of
   the production run between lanes.
6. **Filings on external repos** (issues/PRs against the candidate's
   upstream) — per the issue venue rule, and per-action.
7. **Accepting a known residual risk** the process surfaces (e.g. a Codex
   no-show on a merge head, an unenforced frontmatter key) — recorded as
   accepted, never silently absorbed.

## Derivation

This workflow is derived from one full run — the untangle-codebase adoption
of 2026-11-05 (firsthand review, wringer panel, SDD execution, judged
seeded dogfood, two-gate landing) — and cites that run as its worked
example. One run is a thin base: where a candidate's execution surface
exceeds the worked example's (scripts, binaries, multi-file trees), scale
the verification design up, never down.

## Phase 0 — Intake and firsthand review

Open the run's working folder first — a dedicated folder in the sponsoring
goal's `hidden_files/` — where the run's records (this review, the tier
record, the plan, the decision log) live. Fetch the candidate from its
origin at a pin; record the pin. Read the full
skill text firsthand, never a summary, and read the LICENSE from the tree.
Inventory the tree: companion files, executable files, and a directive scan
of what the text tells an agent to do. Check name collision and overlap
against the live library — is the claimed gap real? Scan for standing-rule
conflicts: a candidate whose text directs violating a standing rule is
flagged here, in the review. Produce the review in this shape: verdict
(adopt verbatim / adopt amended / principles-only / reject), what is
genuinely good, where it breaks against this environment's workflow, the
recommended adoption shape.

**Gate:** the LICENSE is present and permissive — otherwise the run
converts to principles-only adoption (no copying) or ends — and no standing
rule bars the candidate outright.

## Phase 1 — Adoption plan v0

Draft the plan with the `writing-plans` skill. Where the owner's ask leaves
the adoption's scope or success criteria unsettled, run a `brainstorming`
pass first and write the plan against the resulting spec. The amendment
list is the fidelity contract: each amendment numbered, naming the exact
upstream text it replaces, with what stays verbatim stated alongside. The
verification design scales to the candidate's execution surface: a text
harness over prose regions for prose; behavioral tests of the code itself,
RED→GREEN on behavior, for code-bearing candidates — a text harness alone
does not verify code. Acceptance criteria are stated in the plan.

**Gate:** the self-consistency check passes — tasks, verification design,
and acceptance criteria agree with each other, and every check the plan
will run traces to a task that produces its evidence. (The worked example's
v0 failed exactly here: its harness demanded a string its task list never
authorized editing.)

## Phase 2 — Planning-wringer

Invoke the `planning-wringer` skill as-is; do not re-implement it. Panel
composition is the wringer's minimum plus candidate-shaped specialists —
license/provenance for multi-file trees, security for code-executing
candidates. The refined plan is a clean rewrite, not a patch: panel-killed
elements are removed, not caveated.

**Gate:** the independent reviewer returns APPROVED or
APPROVED-WITH-CHANGES with the changes applied. A sustained panel KILL with
no reshape the owner accepts ends the run as an evidenced non-adoption — a
completable outcome; Phase 6 records still apply.

## Phase 3 — Owner decision

Present the refined plan with the panel verdicts and the alternatives the
panel preserved. The owner chooses: adopt (execution mode named here;
subagent-driven development is the standing default), adopt dormant,
fold-in, or reject. For a Light run, the tier and its evidence are a line
item at this gate. The first production target and its owning lane are
named here, or dormancy is chosen here — "adopt dormant" is an owner option
presented at this gate, not a record the executing agent drafts afterward.
Scope rulings the panel produced are stated in this handoff, not discovered
later.

**Gate:** the owner rules. No execution starts before this gate, and
silence is not consent. A standing-rule conflict flagged at Phase 0
proceeds past this gate only with the owner's explicit exception, recorded.

## Phase 4 — SDD execution

Execute per the refined plan under the `subagent-driven-development` skill
and the `feature-pr-pipeline` discipline — referenced, not restated here:
implementer plus fresh reviewer per task. Install into the live tree at the
recorded pin, LICENSE alongside; the installed text byte-matches the
wringer-reviewed draft, or every deviation is a recorded, dated line in the
fork record. If locally modified, apply the fork-versioning scheme from
AGENTS.md: a FORK.md record (origin, pin, fork version, dated amendment
list copied from the plan) plus additive fork_of: / fork_version:
frontmatter; the origin version: stays untouched; no directory renames.
Verbatim imports stay unmarked. Verify every prose edit landed by grepping
the artifact — a patch against hard-wrapped text can apply and change
nothing.

Verification, in order. Harness: RED against the pristine candidate first
(recorded), then GREEN against the installed text; whitespace-normalized
comparisons using upstream's exact phrasings; a check is never weakened to
make it pass — a harness bug may be fixed only when the corrected check
also passes against pristine upstream. Probe: if the candidate relies on a
runtime frontmatter key or harness behavior, probe whether this runtime
honors it and record the result with its caveat; the probe never upgrades
itself to a pass, and the in-text rule is the operative control. Dogfood:
seed a fixture whose ground truth is recorded before the run (for a prose
candidate, an artifact with planted defects of the class the candidate
addresses); apply the candidate for real, executing at least one unit of
its output through its real downstream path where the domain allows; a
fresh judge who did not author the run scores recall, correct
classification, and false positives against the pre-recorded ground truth.

**Gate:** harness GREEN with the RED run recorded; dogfood judged PASS by
the fresh judge; every task reviewer-approved.

## Phase 5 — Governance landing

Two gates, named separately — conflating them was the worked example's
plan-v0 error, and it claimed a delivery route that could never fire.

Gate (a), scope membership: the skill must be listed in the skills-sync
scope file on AEP main. If absent, open a scope-membership PR — one line,
alphabetical position.

Gate (b), sync plus first inclusion: after membership, the daily
skill-sync carries files live→repo. If the sync's drift guard as it stands
at run time fail-safe-excludes first-inclusion files (files with no
touching commit on main), they land via an owner-ruled amendment carrying
the sync commit subject, so later drift classifies live-ahead (the PR
#97/#99 pattern). If the guard's behavior changes, that workaround retires
with it — never apply it by rote.

Every merge follows the merge-readiness census: CI green on the exact
head, a full untruncated thread census, and the Codex state on that head,
established before any merge is reported ready. Merges happen only under a
per-PR owner tap or a conditional per-landing grant from the owner. A
Codex no-show on a merge head is an owner decision item, reported as such —
never absorbed by the green-CI condition. All GitHub calls go through ghg;
all work happens in worktrees, never in the parked main checkout.

**Gate:** the skill's files are present on AEP main, verified by read-back
— or the owner's explicit deferral of the landing is recorded.

## Phase 6 — Records and handoff

Write the records: a lane MEMORY entry and a goal timeline entry (what was
adopted, pin, amendment count, harness and dogfood results, landing PRs
and merge commits, the owner's Phase 3 decision in substance, any accepted
residual risks); a NeuroStrata inscription in the lane namespace, in
pointer form (cue, lesson, evidence), verified retrievable; a
fork-versioning inventory note when the adopted skill is marked. If a first
production target was named at Phase 3, hand off to that lane: the
production run is theirs, and the handoff states the validation-gate state
and the governing artifacts. Production use itself is out of this
workflow. A non-adoption gets the same records, stating why.

**Gate:** every record is written and verified; nothing about the adoption
lives only in chat.

## Stop conditions

Stop the run, report the stage reached and the evidence, and do not route
around the stop:

- License absent or non-permissive: stop copying; convert to
  principles-only adoption or end the run.
- Pin unverifiable (repo moved, history rewritten, tree does not match the
  reviewed copy): stop; re-review from a fresh copy of record.
- A standing-rule conflict without the owner's explicit exception: park at
  Phase 3.
- ghg returns exit 75 (budget denial) on any gated step: stop at that exact
  stage; never retry around the gate, never set GHG_BYPASS=1.
- The sync classifies a file the run would copy as repo-ahead: exclude it
  and surface it as a pull candidate for the owner's ruling; never copy
  over.
- A sustained panel KILL with no reshape the owner accepts: end as a
  non-adoption, records still written.
- A harness or dogfood failure unremediated: the skill does not proceed to
  landing; a check is never weakened to make it pass.
- An unanswered owner gate: the run parks. Silence is not consent at any
  owner gate.

## Volatile facts — verify at runtime

This skill names machinery that changes. Verify each of these at run time;
never treat the values current at this writing as constants:

- The skills-sync scope file's path and its current membership.
- The CI check count on AEP.
- The sync commit subject.
- The parked main checkout's path.
- The memory namespace inscriptions go to.

Any change to the sync or scope machinery is a dated trigger to re-review
this skill's text.
