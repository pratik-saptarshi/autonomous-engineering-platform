# Provenance — vendored humanizer reference snapshot

- **Source (fork):** https://github.com/pratik-saptarshi/humanizer
- **Upstream:** https://github.com/blader/humanizer
- **Pinned commit:** `a32f24407364c74c812b43c15926d638bee1e072` ("Merge pull request #344 from kelsey-fecho/patch-1")
- **Snapshot date:** 2026-11-19 (re-vendor; first snapshot 2026-11-04 at `0ef9fe5`)
- **License:** MIT. The tree carries a `LICENSE` file (© 2025 Siqi Chen) and the skill frontmatter declares `license: MIT`, so reuse is permitted under the MIT terms — unlike the ub-mode snapshot, which carries no license. The working copy in `skills/humanizer/` keeps the `LICENSE` file alongside for the same reason.
- **Excluded from the vendor:** `.git` (history — the snapshot was produced with `git archive`).
- **Purpose:** reference snapshot of the humanizer agent skill (upstream v3.1.0) — a single-file skill (`SKILL.md`) that rewrites AI-sounding prose to remove 26 numbered writing patterns drawn from Wikipedia's "Signs of AI writing", plus its plugin packaging (`.claude-plugin/`, `.cursor-plugin/`, `agents/openai.yaml`) and a package validator (`scripts/validate-package.py`). This tree is the pristine upstream baseline. The copy AEP actually works from is `skills/humanizer/`, which carries two local amendments (a scope note and a file-mode verification rule) marked as fork version 1; the same amendments live on the fork's `feat/scope-and-file-mode-amendments` branch. Studied and diffed against, not executed from here — the same treatment as the other vendored trees.

## Updating this snapshot

This tree changes only by re-vendoring: replace it wholesale with a new pinned snapshot and regenerate `.github/vendor-humanizer.sha256` in the same change. Code or dependency edits made in place — including dependency-update PRs against this tree — are closed, not merged: a merged bump would leave the tree matching no upstream commit and falsify the provenance pinned above. Local amendments never land here; they belong on the fork and in `skills/humanizer/`.

Branch note: the fork's default branch is `develop`, while upstream's default is `main`. This snapshot is the fork `develop` head at the pinned commit, which at vendoring time is identical to upstream `main` (the fork was created 2026-11-04 from upstream `main` at `0ef9fe5`, and `develop` was created at that head with no fork-only commits).

## Secret-scan annotation (2026-11-04)

Clean. A credential-pattern grep over the pinned tree matched nothing. The tree is Markdown prose, plugin JSON manifests, issue templates, and one stdlib-only Python validator; it contains no credential-shaped values. No `.gitleaks.toml` allowlist entries were needed for this tree.

<!-- vendor-freshness: {"branch": "develop", "decision_date": "2026-11-19", "parent": "blader/humanizer", "parent_branch": "main", "pin": "a32f24407364c74c812b43c15926d638bee1e072", "policy": "repin", "repo": "pratik-saptarshi/humanizer", "review_due": "2026-12-19", "tree": "humanizer"} -->

## Disposition (2026-11-19 re-vendor)

- 15 upstream files; no symlinks. New file `package.json` is part of the faithful snapshot.
- Instruction surfaces (`AGENTS.md`, `.claude-plugin/`, `.cursor-plugin/`) are retained as inert reference data under `reference/` — they are not at any active AEP path. AEP is governed by its own root `AGENTS.md`.
- Secret scan: clean; no allowlist entries needed.
