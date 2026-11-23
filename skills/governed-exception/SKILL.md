---
name: governed-exception
version: 1.0.0
author: pratik-saptarshi
description: >-
  Govern an exception to a finding that has no fix route — a bare
  ignore is never allowed: every governed exception carries a
  cohort-aligned review_by date, a multi-limb exit condition, a
  renewal evidentiary bar, a blast-radius hunt result, and, for
  deferrals, a bounded version range plus a hard re-rule deadline on
  a tracked issue. Use when proposing, writing, or renewing an
  ignore, suppression, deferral, or accepted advisory.
---

# Governed Exception

**Announce at start:** "I'm using the governed-exception skill to govern this exception."

## The rule's home — and its actual status

This rule was drafted as a postulate for AGENTS.md, and that
adoption did not happen. The record is specific: at this item's
build, the drafted wording **failed its independent H8 wording
check**, the wording was **not inserted** into AGENTS.md, and the
item was stopped pending the owner's re-ruling. The postulate is
therefore not a standing rule in AGENTS.md, and this skill does not
rest on it as an authority.

Until the owner re-rules and an adopted text exists, this skill's
procedures stand as the programme record's proposed pattern:
provisional guidance, applied as this skill states them — not as
an adopted standing rule, and never cited as one. This skill is
the thin companion to that record: it carries the two procedures
the drafted postulate names — the blast-radius hunt and the
renewal review. If an adopted postulate later appears and this
skill disagrees with it, the adopted text wins and the
disagreement is reported.

## When to use

A finding — an advisory, a denied licence, a failing check, or an
equivalent — has no upgrade or fix route, and someone proposes to
live with it: ignore it, suppress it, accept it, or defer it. That
proposal is an exception, and it is governed or it is refused.

Do NOT use for: a finding with a working fix route (fix it), a
temporary local workaround that never enters a record or a gate
configuration, or re-litigating an exception an owner has already
ruled on without new evidence.

## The five elements — no bare ignore

An exception is **refused** unless the written exception carries
all five elements:

1. **Cohort-aligned `review_by`.** The date equals the `review_by`
   of an existing governed-exception cohort in the same repo, so
   renewals batch and are reviewed together. If cohort members
   disagree on `review_by`, there is no cohort; a set with no
   shared date is not a cohort. Where no cohort exists, the
   founding ruling must itself state a date — that date founds the
   cohort.
2. **Multi-limb exit condition.** More than one named limb. The
   exception ends when a limb is met, not merely when the date
   arrives; the date triggers review, the limbs govern exit.
3. **Renewal evidentiary bar.** The exception states, at founding,
   what evidence a renewal must present (see the renewal review
   below). A renewal that does not clear the bar fails.
4. **Blast-radius hunt result.** The hunt in the procedure below
   has been run and its result recorded in the exception.
5. **Deferral shape, where the exception is a deferral.** A bounded
   version range (the versions or window the deferral covers, with
   an end) plus a hard re-rule deadline carried on a tracked issue
   — not only in prose. An open-ended deferral is refused.

The written exception names its exit limbs and **the ruling's own
`review_by`**. It never copies a date from a prior incident: dates
from earlier exceptions are worked-example values, not defaults
and not the rule.

## Procedure 1 — blast-radius hunt

Before the exception is written:

1. State the finding's mechanism in one sentence: what is wrong,
   and what would have to be true for the same defect to appear
   elsewhere.
2. Hunt for sibling sites sharing that mechanism: the same
   dependency, advisory, licence, or pattern in other trees,
   modules, or repos in scope; and other findings already excepted
   for the same mechanism.
3. Record the result in the exception: what was searched, and
   either the sibling sites found (each is fixed, excepted on its
   own governed terms, or named as accepted exposure) or an
   explicit "none found".
4. An exception with no recorded hunt result is incomplete and is
   refused under element 4.

## Procedure 2 — renewal review

When an exception reaches its `review_by`:

1. The renewal presents evidence against the bar stated at
   founding: the state of each exit limb, whether a fix route now
   exists, and the blast-radius result refreshed or re-affirmed.
2. **A bare date bump is a failed review.** A renewal supported
   only by moving the date forward — no new evidence on the limbs,
   the fix route, or the blast radius — fails, and the exception
   lapses or is re-ruled; it is not renewed.
3. A passing renewal records the evidence, keeps or re-aligns the
   `review_by` with its cohort, and restates the exit limbs
   unchanged or as re-ruled.

## Honest-evidence note — the contested limb

The renewal evidentiary bar (element 3, and procedure 2's failed
review rule) is **contested**: it rests on two instances from a
single programme, both ruled on the same day. The other elements
are the shape those same rulings gave their exceptions, stated
here as the pattern to test, not as a long-settled convention.
Treat the bar as this skill states it — provisional guidance
under the status recorded in "The rule's home" above, not an
adopted standing rule — and record any case that strains it
rather than silently widening or dropping it.

## Worked examples (values, not the rule)

- An unmaintained-dependency exception whose ruling stated three
  exit limbs — a maintained replacement or fork is adopted, the
  dependency is removed, an upstream release restores maintenance
  — and that ruling's own `review_by` of 2027-02-05. The limbs and
  the date are that ruling's; a new exception states its own.
- A deferral closed with a bounded ignore and a hard re-rule
  deadline of 2027-01-15 carried on a tracked issue. The deadline
  is that ruling's; a new deferral carries its own bounded range
  and its own tracked deadline.

## Stop conditions

- Any of the five elements missing: the exception is refused, not
  written in weaker form.
- A renewal supported only by a date bump: the renewal fails.
- A proposed `review_by` copied from a prior incident instead of
  the current ruling: stop and obtain the ruling's own date.

## Related

- `rust-pre-pr-gate` — carries accepted audit ignores as gate
  configuration; this skill governs how any such exception is
  founded and renewed, the gate skill governs the gate itself.
- `preregistered-pilot` — adjacent governance for pilots: frozen
  bars judged strictly; this skill governs exceptions to findings.
