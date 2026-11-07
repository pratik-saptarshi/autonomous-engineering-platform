# EGM adoption — pilot artifacts

Pilot artifacts for the Elephant-Goldfish Model (EGM) adoption into this
repo: the adoption strategy document plus five rounds of Goldfish review
of that document.

- `adoption-strategy.md` — the EGM adoption strategy for AEP (dual
  environment: general-purpose Linux VM + current Muse environment), as
  revised through round 5 of review (546 lines).
- `goldfish-review-r1.md`, `goldfish-review-r2.md`, `goldfish-review-r3.md`,
  `goldfish-review-r4.md`, `goldfish-review-r5.md`
  — the five Goldfish review rounds: 5 fresh-context reviewers each
  (design_critic, structural, implementation_readiness, comprehension,
  zoom_out) auditing the strategy doc against EGM standards.
- `goldfish-resolve-r1.md`, `goldfish-resolve-r2.md`, `goldfish-resolve-r3.md`,
  `goldfish-resolve-r4.md`, `goldfish-resolve-r5.md`
  — the per-round resolutions: each finding categorized as CONTEST,
  ESCALATE, PROPOSE FIX, or DECLINE, with precise proposed edits.

## Loop status

5 rounds run; **0 of the 2 consecutive clean rounds needed for
convergence**. All five rounds were NOT CLEAN — convergence was not
achieved and the 5-round cap is reached; the loop is complete. The loop
was stopped by an owner redirect before convergence so the vendor PR
could be built from the round-3 state; rounds 4 and 5 were then run in
parallel lanes by the owner. Round 5 is complete: review (72 findings:
4 Blockers, 40 Majors, 28 Nits), resolve (71 PROPOSE FIX, 1 DECLINE,
0 new ESCALATE), and all 51 shared fixes applied — the strategy doc as
vendored here reflects rounds 1–5 fixes (546 lines). Note:
`goldfish-review-r5.md` was reconstructed from the round-5 resolve
report (see its header) because the original consolidated review file
was never written to disk.

## Still open

- **zoom_out-1-1 ESCALATE (Environment A scope)** — the round-1 reviewer
  questioned designing Environment A in full with no identified user. The
  resolver escalated it: the dual-environment scope was the owner's
  explicit instruction, recorded in the requesting conversation, not in any
  file the reviewers could read. It needs the owner's ruling (keep fully
  designed, demote to appendix, or drop) and is carried as settled in
  later rounds, not re-decided.
- Convergence: not achieved — 0 of 2 clean rounds across all 5 rounds;
  the cap is reached and the loop is complete.

These files are reference material, not vendored skills: they live under
`docs/` and are intentionally outside the skills manifest scope.
