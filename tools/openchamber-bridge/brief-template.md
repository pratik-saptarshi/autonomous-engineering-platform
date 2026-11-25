# PILOT BRIEF TEMPLATE — scoped re-review through the OpenCode–OpenChamber bridge

Fill every <SLOT> before dispatch. The controller (Muse side) verifies the
finding text below is quoted VERBATIM from its source before dispatching —
grep-check it against the source thread/report. Do not paraphrase a charge.

## Task

Scoped re-review of replay-core PR #7, wave <WAVE>, commits <BASE>..<HEAD>.
You are a re-reviewer, not an implementer. Your verdict is either right or
wrong against the diff; the controller will independently re-check your red
reproductions (pilot-only dual verification).

## Title (dispatcher --title)

replay-core PR7 · W<WAVE> re-review · <BASE_SHORT>..<HEAD_SHORT>

## Working directory (dispatcher --workdir)

<SCRATCH_WORKTREE>   (a scratch worktree at <HEAD>; the main tree is read-only to you)

## Model (dispatcher --model)

<MODEL>   (allowlist ONLY — Pratik's rule 2026-11-20, expanded 2026-11-21: see
           ALLOWED_MODELS in dispatch.py; the dispatcher refuses anything else.
           Within the allowlist: a DIFFERENT model family from the implementer
           under review.)

## Report path (dispatcher --report)

<SDD_WORKSPACE>/wave<WAVE>-rereview-report.md

## The charge (verbatim)

<CHARGE_VERBATIM — the wave's findings / fix commits under review, quoted exactly>

## What to do

1. Reproduce first: for each finding/fix under review, construct the red case
   in the scratch worktree BEFORE reading the fix as correct. Record the exact
   commands and outputs.
2. Account for EVERY removed or changed test line in the diff <BASE>..<HEAD> —
   list each one in the report and say what replaces its coverage, or flag it.
3. Run the charged gate in the worktree: <GATE_COMMAND> (e.g. the Phase 2 gate
   script), plus package suites / race / gofmt / vet as the charge specifies.
4. Verdict per finding: ACCEPTED / REJECTED / INSUFFICIENT-EVIDENCE, each with
   the red evidence behind it. No verdict without a reproduction or an explicit
   statement of why none was possible.

## Stop conditions

- If the scratch worktree is not at <HEAD>, stop and report.
- If a reproduction contradicts the charge, stop on that finding, report the
  contradiction with evidence, and continue with the remaining findings.
- If you need anything outside the scratch worktree or the report file, stop
  and report the need instead of reaching for it.

(The standard footer — report contract, no-push/no-post, worktree-only,
environment, hygiene — is appended automatically by dispatch.py.)
