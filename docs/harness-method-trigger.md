# Harness²-method trigger definition

## Purpose and status

This document defines the checkable condition that decides whether the
election for Part 2's Harness²-method outline (Outline H1, the contrast-probe
protocol for lane prompt/skill tuning) is due. It is Part 1, Task A6 of the
deeper-integration adoption plan (2026-10-26).

Writing this definition is committed scope. Satisfying it is not: nothing in
this document schedules, starts, or pre-approves the method itself. The
trigger exists so a future session can evaluate a bounded record corpus
against a fixed condition instead of deciding from impression whether
"systematic tuning" has begun.

## The candidate set (the five P7 deltas, complete)

The trigger guards the Harness²-method candidate set identified as premise
P7 in the Stage 1 analysis. That set is exactly five narrow mechanisms —
this is the complete candidate set; there is no sixth delta waiting behind
the trigger:

1. **Same-task contrastive rollouts** — the same task executed under two or
   more variant harnesses, with the contrast recorded.
2. **Anonymized selection** — candidate selection over a pool stripped of
   variant identity / provenance.
3. **Gated lesson schema** — lessons admitted to the durable store only
   when they carry the required fields (cue, lesson, evidence).
4. **Retrieval-by-construction** — retrieval made structural in the lane's
   pickup path rather than left to habit.
5. **Candidate-diversity measurement** — the diversity of the candidate
   pool measured and recorded as part of a tuning exercise.

Where each delta lives:

- Deltas **1, 2, and 5** are carried by **Outline H1** (Part 2) and are the
  deltas this trigger gates, through the H1 election below.
- Delta **3** (gated lesson schema) is **not** Part 2 work: it is committed
  in Part 1, Task A5, and does not wait for this trigger.
- Delta **4** (retrieval-by-construction) is **Outline H4** (Part 2). It is
  gated on pain evidence — a recorded lane failure traced to a skipped
  knowledge search — plus Pratik's election, **not** on this trigger.

## Named record corpus (bounded)

The trigger arms are evaluated over this corpus only:

- the AEP goal timeline and goal records under
  `~/workspace/goals/autonomous-code-defense-factory/`;
- lane side-chat `MEMORY.md` files under `~/side-chats/`;
- change history of `~/workspace/custom-skills/`;
- NeuroStrata lane namespaces (`aep` plus the other lane namespaces).

The arms are checkable from these named record sets. They are not
mechanically decidable over all records everywhere, and a record outside
this corpus does not count toward any arm until it is recorded inside the
corpus.

## The trigger: a three-way OR

The trigger fires when **any one** of the three arms fires.

### T1 — Directed program

Pratik directs a systematic lane prompt/skill tuning program in any record
in the corpus.

**Check:** cite the record that carries the direction.

### T2 — Variant practice

Any single recorded exercise evaluates ≥2 candidate variants of the same
prompt/skill artifact against the same task set.

**Check:** the record names ≥2 variants and one shared task set.

### T3 — Repeated ad-hoc tuning

≥3 ad-hoc prompt/skill tuning exercises are recorded in the corpus in a
rolling 90-day window.

**Check:** three dated records, each a tuning exercise as defined below,
all inside one 90-day window.

### "Tuning exercise" — definition

A **tuning exercise** (this definition applies to T3 and to the
non-triggers below) is a record in the corpus that:

- states a **tuning intent**, **and**
- records a **before/after evaluation** of the change.

A prompt edit with neither element is a one-off edit, never an exercise,
however numerous such edits are.

## Non-triggers

The following never fire the trigger, however numerous they become:

- **one-off prompt edits** — edits with no stated tuning intent and no
  before/after evaluation (see the definition above);
- **single-variant fixes** — a change to one variant of an artifact,
  however well evaluated; variant practice (T2) requires ≥2 variants of
  the same artifact against one shared task set in a single recorded
  exercise;
- **ordinary SDD task work** — the normal subagent-driven development of
  features, fixes, and docs, including the prompt and skill edits that work
  incidentally produces.

## Evaluator and cadence

The trigger is evaluated **at every AEP lane close-out**. The closing
session:

1. checks the three arms over the named corpus above;
2. logs the result — **fired or not fired, with the per-arm readings** —
   in the close-out.

An unlogged evaluation is an unevaluated trigger: a close-out that does not
record the arm readings has not evaluated the trigger, whatever checking
was done informally along the way.

## Election procedure

When any arm fires, the next step is **Pratik's election on Part 2's
Outline H1**. The trigger firing schedules the *question*, never the
adoption:

- a fired trigger puts the H1 election question to Pratik;
- it does not adopt H1, does not schedule H1 work, and does not commit any
  of the H1-carried deltas (1, 2, 5);
- H1 work begins only if Pratik elects it, with full planning at election
  time.

**Outline H2 is not trigger-gated.** Anonymized adjudication for disputed
panel findings (Outline H2, delta 2 applied to panels) has its own gate —
a recorded adjudication dispute where provenance plausibly moved the
outcome — and its own election. No arm of this trigger fires, schedules,
or substitutes for H2's gate.
