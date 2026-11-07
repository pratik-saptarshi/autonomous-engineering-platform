# EGM adoption — pilot artifacts

Pilot artifacts for the Elephant-Goldfish Model (EGM) adoption into this
repo: the adoption strategy document plus four rounds of Goldfish review
of that document.

- `adoption-strategy.md` — the EGM adoption strategy for AEP (dual
  environment: general-purpose Linux VM + current Muse environment), as
  revised through round 4 of review (457 lines).
- `goldfish-review-r1.md`, `goldfish-review-r2.md`, `goldfish-review-r3.md`,
  `goldfish-review-r4.md`
  — the four Goldfish review rounds: 5 fresh-context reviewers each
  (design_critic, structural, implementation_readiness, comprehension,
  zoom_out) auditing the strategy doc against EGM standards.
- `goldfish-resolve-r1.md`, `goldfish-resolve-r2.md`, `goldfish-resolve-r3.md`,
  `goldfish-resolve-r4.md`
  — the per-round resolutions: each finding categorized as CONTEST,
  ESCALATE, PROPOSE FIX, or DECLINE, with precise proposed edits.

## Loop status

4 rounds run; **0 of the 2 consecutive clean rounds needed for
convergence**. All four rounds were NOT CLEAN. The loop was stopped by an
owner redirect before convergence so the vendor PR could be built from
the round-3 state; round 4 was then restarted in a parallel lane by the
owner. Round 4 is complete: review (56 findings: 3 Blockers, 44 Majors,
9 Nits), resolve (52 PROPOSE FIX, 1 CONTEST, 2 DECLINE, 1 SETTLED, 0 new
ESCALATE), and all 52 fixes applied — the strategy doc as vendored here
reflects rounds 1–4 fixes (457 lines).

## Still open

- **zoom_out-1-1 ESCALATE (Environment A scope)** — the round-1 reviewer
  questioned designing Environment A in full with no identified user. The
  resolver escalated it: the dual-environment scope was the owner's
  explicit instruction, recorded in the requesting conversation, not in any
  file the reviewers could read. It needs the owner's ruling (keep fully
  designed, demote to appendix, or drop) and is carried as settled in
  later rounds, not re-decided.
- Convergence: round 5 of the 5-round cap remains, not run.

These files are reference material, not vendored skills: they live under
`docs/` and are intentionally outside the skills manifest scope.
