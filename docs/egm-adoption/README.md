# EGM adoption — pilot artifacts

Pilot artifacts for the Elephant-Goldfish Model (EGM) adoption into this
repo: the adoption strategy document plus three rounds of Goldfish review
of that document.

- `adoption-strategy.md` — the EGM adoption strategy for AEP (dual
  environment: general-purpose Linux VM + current Muse environment), as
  revised through round 3 of review (443 lines).
- `goldfish-review-r1.md`, `goldfish-review-r2.md`, `goldfish-review-r3.md`
  — the three Goldfish review rounds: 5 fresh-context reviewers each
  (design_critic, structural, implementation_readiness, comprehension,
  zoom_out) auditing the strategy doc against EGM standards.
- `goldfish-resolve-r1.md`, `goldfish-resolve-r2.md`, `goldfish-resolve-r3.md`
  — the per-round resolutions: each finding categorized as CONTEST,
  ESCALATE, PROPOSE FIX, or DECLINE, with precise proposed edits.

## Loop status

3 rounds run; **0 of the 2 consecutive clean rounds needed for
convergence**. All three rounds were NOT CLEAN. The loop was stopped by an
owner redirect before convergence (round 4 was dispatched and then
abandoned) so the vendor PR could be built from the current state. The
strategy doc as vendored here reflects rounds 1–3 fixes.

## Still open

- **zoom_out-1-1 ESCALATE (Environment A scope)** — the round-1 reviewer
  questioned designing Environment A in full with no identified user. The
  resolver escalated it: the dual-environment scope was the owner's
  explicit instruction, recorded in the requesting conversation, not in any
  file the reviewers could read. It needs the owner's ruling (keep fully
  designed, demote to appendix, or drop) and is carried as settled in
  later rounds, not re-decided.
- Convergence: rounds 4–5 of the 5-round cap remain if the loop resumes.

These files are reference material, not vendored skills: they live under
`docs/` and are intentionally outside the skills manifest scope.
