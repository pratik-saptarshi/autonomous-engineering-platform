# EGM adoption — pilot artifacts

Pilot artifacts for the Elephant-Goldfish Model (EGM) adoption into this
repo: the adoption strategy document plus five rounds of Goldfish review
of that document.

- `adoption-strategy.md` — the EGM adoption strategy for AEP (dual
  environment: general-purpose Linux VM + current Muse environment), as
  revised through round 5 of review (547 lines).
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
vendored here reflects rounds 1–5 fixes (547 lines). Note:
`goldfish-review-r5.md` was reconstructed from the round-5 resolve
report (see its header) because the original consolidated review file
was never written to disk.

## Still open

- **zoom_out-1-1 ESCALATE (Environment A scope) — RULED 2026-11-07,
  closed.** The owner ruled to keep Environment A fully designed as §9
  of the strategy doc (no appendix move, not dropped). The headless
  (Path 2) shape was validated the same day in an emulated fresh-VM
  rootfs — §9.1 provisioning, §10.6 checks (48/48 references), gate
  scans, D6 snapshot, and §9.5 step 2 packaging tests (342 tests,
  0 failures) all pass; the Path 1 (muse-cli) E2E shape remains
  documented-but-unexecuted. Ruling and gate record: strategy doc
  §14 decision 3 and §11.
- Convergence: not achieved — 0 of 2 clean rounds across all 5 rounds;
  the cap is reached and the loop is complete.

These files are reference material, not vendored skills: they live under
`docs/` and are intentionally outside the skills manifest scope.
