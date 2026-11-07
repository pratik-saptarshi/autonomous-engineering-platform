# Provenance — vendored grim-prompter reference snapshot

- **Source (fork):** https://github.com/pratik-saptarshi/grim-prompter
- **Upstream:** https://github.com/jmanico/grim-prompter
- **Pinned commit:** `076ec0d32c9eec0e09bfdee22b57121f49b26022` ("Merge pull request #2 from jmanico/fix/tool-description-poisoning")
- **Snapshot date:** 2026-10-28
- **License:** MIT (copyright 2026 Jim Manico). `LICENSE` is preserved verbatim in this tree. The license was read from the tree itself, not from the GitHub API.
- **Excluded from the vendor:** `.git` (history — the snapshot was produced with `git archive`).
- **Purpose:** reference snapshot of Jim Manico's grim-prompter — a threat-modeling prompt library for AI coding agents. It provides 36 architecture workflows in quick (single-prompt) and deep (six-stage: scope/evidence → system model → threat analysis → challenge/consolidate → treatment/validation → report/handoff) forms, 29 method prompts (STRIDE, PASTA, LINDDUN, STPA, attack trees/graphs, MITRE enrichments, and others), and a portable JSON artifact contract whose evidence records carry repository-relative `path:start-end` locators with explicit coverage/gap accounting. The tree is pure Markdown (339 `.md` files plus `LICENSE` and `logo.svg`): it ships no executable code, no scripts, and no test suite. Studied, not executed from here — the library is designed to be run by an agent from a live checkout, and nothing in this snapshot is installed, linked, or run. A live run would execute from a live checkout of the fork, not from `reference/`, the same treatment as the other vendored trees.

## Updating this snapshot

This tree changes only by re-vendoring: replace it wholesale with a new pinned upstream snapshot and regenerate `.github/vendor-grim-prompter.sha256` in the same change. Code or dependency edits made in place — including dependency-update PRs against this tree — are closed, not merged: a merged bump would leave the tree matching no upstream commit and falsify the provenance pinned above.

Branch note: the fork's default branch is `develop`, while upstream's default is `main`. This snapshot is the fork `develop` head at the pinned commit, which at vendoring time is identical to upstream `main` (fork and upstream heads both verified at `076ec0d` immediately before the pin was taken).

Maturity note: upstream's initial release was 2026-10-28, the same day as this snapshot; the entire upstream history at the pin is 7 commits by a single author. The snapshot is expected to churn early; re-vendoring should be evaluated sooner than for the older vendored trees.

## Secret-scan annotation (2026-10-28)

Clean. A gitleaks scan (v8.24.3, this repo's CI version and config) of the pinned tree and of the full clone history reported no leaks, and a credential-pattern grep over the tree matched nothing. The library's prose discusses credentials, tokens, and tool-poisoning extensively — that is its subject matter — but it contains no credential-shaped values. No `.gitleaks.toml` allowlist entries were needed for this tree.
