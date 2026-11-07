# Provenance — vendored ub-mode reference snapshot

- **Source (fork):** https://github.com/pratik-saptarshi/ub-mode
- **Upstream:** https://github.com/unclebob/ub-mode
- **Pinned commit:** `57a8bdd28e45ed41900ace0bafa2ff76dd9ed70f` ("Remove crap4clj and clj-mutate references from README")
- **Snapshot date:** 2026-10-27
- **License:** NONE. The source tree carries no `LICENSE` file and grants no license — nothing in this tree is licensed for reuse, and the snapshot is held as reference data only. ub-mode's companion gate tools (`unclebob/crapper`, `unclebob/dryer`, `unclebob/mutator`) are separate repositories under their own 0BSD licenses; they are NOT part of this snapshot, and their licenses do not extend to this tree.
- **Excluded from the vendor:** `.git` (history — the snapshot was produced with `git archive`).
- **Purpose:** reference snapshot of Uncle Bob's ub-mode agent skill — a reduced set of engineering principles (First Make it Work, Then Make it Right, Follow Practice) whose "Make it Right" phase prescribes three deterministic quality gates: CRAP score per function under 10 (crapper), structural duplication at 0.8 similarity or above eliminated (dryer), and mutation-testing survivors killed (mutator). The skill itself is a thin orchestration layer — `README.md` + `SKILL.md` only — and its substance, the three gate tools, lives in the separate companion repositories named above, which are not vendored here. Studied, not executed from here, the same treatment as the other vendored trees.

## Updating this snapshot

This tree changes only by re-vendoring: replace it wholesale with a new pinned upstream snapshot and regenerate `.github/vendor-ub-mode.sha256` in the same change. Code or dependency edits made in place — including dependency-update PRs against this tree — are closed, not merged: a merged bump would leave the tree matching no upstream commit and falsify the provenance pinned above.

Branch note: the fork's default branch is `develop`, while upstream's default is `master`. This snapshot is the fork `develop` head at the pinned commit, which at vendoring time is identical to upstream `master` (fork and upstream heads both verified at `57a8bdd` immediately before the pin was taken).

## Secret-scan annotation (2026-10-27)

Clean. A credential-pattern grep over the pinned tree matched nothing, and a gitleaks scan (v8.24.3, this repo's CI version and config) of the tree (~6.2 KB) reported no leaks. The tree is two Markdown files of engineering-practice prose; it contains no credential-shaped values. No `.gitleaks.toml` allowlist entries were needed for this tree.
