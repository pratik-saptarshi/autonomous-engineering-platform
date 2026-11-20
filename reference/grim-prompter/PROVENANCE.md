# Provenance — vendored grim-prompter reference snapshot

- **Source (fork):** https://github.com/pratik-saptarshi/grim-prompter
- **Upstream:** https://github.com/jmanico/grim-prompter
- **Pinned commit:** `2a94457c7bc63ffbc4a44ea50ae645ab8cee26bf` ("Explain privacy review workflows in the README (#11)")
- **Snapshot date:** 2026-11-19 (re-vendor; first snapshot 2026-10-28 at `076ec0d`)
- **License:** MIT (copyright 2026 Jim Manico). `LICENSE` is preserved verbatim in this tree. The license was read from the tree itself, not from the GitHub API.
- **Excluded from the vendor:** `.git` (history — the snapshot was produced with `git archive`).
- **Purpose:** reference snapshot of Jim Manico's grim-prompter — a threat-modeling prompt library for AI coding agents. It provides 36 architecture workflows in quick (single-prompt) and deep (six-stage: scope/evidence → system model → threat analysis → challenge/consolidate → treatment/validation → report/handoff) forms, 29 method prompts (STRIDE, PASTA, LINDDUN, STPA, attack trees/graphs, MITRE enrichments, and others), and a portable JSON artifact contract whose evidence records carry repository-relative `path:start-end` locators with explicit coverage/gap accounting. The tree is pure Markdown (339 `.md` files plus `LICENSE` and `logo.svg`): it ships no executable code, no scripts, and no test suite. Studied, not executed from here — the library is designed to be run by an agent from a live checkout, and nothing in this snapshot is installed, linked, or run. A live run would execute from a live checkout of the fork, not from `reference/`, the same treatment as the other vendored trees.

## Updating this snapshot

This tree changes only by re-vendoring: replace it wholesale with a new pinned upstream snapshot and regenerate `.github/vendor-grim-prompter.sha256` in the same change. Code or dependency edits made in place — including dependency-update PRs against this tree — are closed, not merged: a merged bump would leave the tree matching no upstream commit and falsify the provenance pinned above.

Branch note: the fork's default branch is `develop`, while upstream's default is `main`. This snapshot is the fork `develop` head at the pinned commit, which at vendoring time is identical to upstream `main` (fork and upstream heads both verified at `076ec0d` immediately before the pin was taken).

Maturity note: upstream's initial release was 2026-10-28, the same day as this snapshot; the entire upstream history at the pin is 7 commits by a single author. The snapshot is expected to churn early; re-vendoring should be evaluated sooner than for the older vendored trees.

## Secret-scan annotation (2026-10-28)

Clean. A gitleaks scan (v8.24.3, this repo's CI version and config) of the pinned tree and of the full clone history reported no leaks, and a credential-pattern grep over the tree matched nothing. The library's prose discusses credentials, tokens, and tool-poisoning extensively — that is its subject matter — but it contains no credential-shaped values. No `.gitleaks.toml` allowlist entries were needed for this tree.

<!-- vendor-freshness: {"branch": "develop", "decision_date": "2026-11-19", "parent": "jmanico/grim-prompter", "parent_branch": "main", "pin": "2a94457c7bc63ffbc4a44ea50ae645ab8cee26bf", "policy": "repin", "repo": "pratik-saptarshi/grim-prompter", "review_due": "2026-12-19", "tree": "grim-prompter"} -->

## Disposition (2026-11-19 re-vendor)

- Fork `develop` == upstream `jmanico/grim-prompter@main` at this pin. 359 Markdown files + `LICENSE`, no symlinks, no executable code.
- No new instruction surfaces relative to the prior snapshot; `AGENTS.md` is upstream reference data under `reference/`. Secret scan clean.

## Freshness

This file is the single source of truth for this tree's pin. The one-line `vendor-freshness` block above is machine-readable and is parsed by `scripts/vendor_graph.py` and `scripts/vendor_freshness.py`. Every re-vendor updates the block's `pin` in the same PR.

- **Current state:** **repin** — re-vendored at the current fork head on 2026-11-19; next freshness review 2026-12-19.
- **Owner:** the AEP maintainer (repository owner).
- **SLA:** a weekly non-gating detector opens or updates one tracking issue within 7 days of detected drift; it never auto-syncs or auto-merges.
- **Known out-of-scope drift for this lane:** `harness2` (2 behind upstream), `neurostrata` (170 behind, 604 ahead), and `craft-anything` (decision due) are reported by the detector, not fixed by the 2026-11-19 migration.
