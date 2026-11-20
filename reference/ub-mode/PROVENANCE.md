# Provenance — vendored ub-mode reference snapshot

- **Source (fork):** https://github.com/pratik-saptarshi/ub-mode
- **Upstream:** https://github.com/unclebob/ub-mode
- **Pinned commit:** `3da62bf3fcfd2034de41f30d920d2739e566171f` ("Add MIT license")
- **Snapshot date:** 2026-11-19 (re-vendor; first snapshot 2026-10-27 at `57a8bdd`)
- **License:** MIT (Copyright (c) 2026 Robert C. Martin). The new pin adds a `LICENSE` file at the tree root, preserved verbatim; the previous pin carried no license and this note has been corrected rather than left stale. Companion gate tools (`unclebob/crapper`, `unclebob/dryer`, `unclebob/mutator`) remain separate repositories under their own 0BSD licenses and are NOT part of this snapshot.
- **Excluded from the vendor:** `.git` (history — the snapshot was produced with `git archive`).
- **Purpose:** reference snapshot of Uncle Bob's ub-mode agent skill — a reduced set of engineering principles (First Make it Work, Then Make it Right, Follow Practice) whose "Make it Right" phase prescribes three deterministic quality gates: CRAP score per function under 10 (crapper), structural duplication at 0.8 similarity or above eliminated (dryer), and mutation-testing survivors killed (mutator). The skill itself is a thin orchestration layer — `README.md` + `SKILL.md` only — and its substance, the three gate tools, lives in the separate companion repositories named above, which are not vendored here. Studied, not executed from here, the same treatment as the other vendored trees.

## Updating this snapshot

This tree changes only by re-vendoring: replace it wholesale with a new pinned upstream snapshot and regenerate `.github/vendor-ub-mode.sha256` in the same change. Code or dependency edits made in place — including dependency-update PRs against this tree — are closed, not merged: a merged bump would leave the tree matching no upstream commit and falsify the provenance pinned above.

Branch note: the fork's default branch is `develop`, while upstream's default is `master`. This snapshot is the fork `develop` head at the pinned commit, which at vendoring time is identical to upstream `master` (fork and upstream heads both verified at `57a8bdd` immediately before the pin was taken).

## Secret-scan annotation (2026-10-27)

Clean. A credential-pattern grep over the pinned tree matched nothing, and a gitleaks scan (v8.24.3, this repo's CI version and config) of the tree (~6.2 KB) reported no leaks. The tree is two Markdown files of engineering-practice prose; it contains no credential-shaped values. No `.gitleaks.toml` allowlist entries were needed for this tree.

<!-- vendor-freshness: {"branch": "develop", "decision_date": "2026-11-19", "parent": "unclebob/ub-mode", "parent_branch": "master", "pin": "3da62bf3fcfd2034de41f30d920d2739e566171f", "policy": "repin", "repo": "pratik-saptarshi/ub-mode", "review_due": "2026-12-19", "tree": "ub-mode"} -->

## Disposition (2026-11-19 re-vendor)

- Fork `develop` == upstream `unclebob/ub-mode@master` at this pin. Three files: `README.md`, `SKILL.md`, `LICENSE`.
- License note corrected to MIT per the new `LICENSE` file (the plan required reporting rather than leaving the old "License: NONE" note stale; correction is byte-grounded in the pinned tree).
- No instruction surfaces beyond upstream `SKILL.md`; secret scan clean.
