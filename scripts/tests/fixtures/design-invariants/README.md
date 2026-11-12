# Design invariant fixtures

`scripts/check_design_invariants.py --self-test` runs a negative mutation
corpus against the real documents: each check's load-bearing token is removed
or negated, and the check must fail. This is the primary guard against a
presence-only grep.

The files in `bad/` are illustrative minimal cases for humans reviewing the
checker:

- `negation.html` contains both a denial and the forbidden token; a check that
  treats either as satisfaction is wrong.
- `missing-section.html` is intentionally empty; every section-bound check
  must fail closed.
