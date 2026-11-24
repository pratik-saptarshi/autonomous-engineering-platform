# Provenance — vendored avoid-ai-writing reference snapshot

- **Source (fork):** https://github.com/pratik-saptarshi/avoid-ai-writing
- **Upstream:** https://github.com/conorbronsdon/avoid-ai-writing
- **Pinned commit:** `fad13da` ("fix(fork): close the cursor-rules rewrite trigger (fork_version 2)") — the fork's `develop` head: upstream v3.39.0 at `cd5573a` plus the fork's two detect-only amendment commits (fork_version 2; see `FORK.md` in this tree).
- **Snapshot date:** 2026-11-23 (first vendor of this tree)
- **License:** MIT (copyright Conor Bronsdon). `LICENSE` and `NOTICE.md` are preserved verbatim in this tree. Upstream attribution (badges, homepage, npm metadata pointing at conorbronsdon/avoid-ai-writing) is kept intact.
- **Excluded from the vendor:** `.git` (history — the snapshot was produced with `git archive`). The source tree contains no symlinks, so nothing else was excluded.
- **Purpose:** detect-only prose-audit tooling for the AEP / Neuro documentation surfaces: a zero-dependency deterministic detector (54 issue types, including stylometric and AI-tool-fingerprint signals), a preservation validator, and a gate CLI (`bin/avoid-ai-writing-gate.js`) for CI use. Adopted scoped, per the 2026-11-23 skill-adoption evaluation (verdict: adopt-scoped-alongside): this tree's skill is **detect-only** — its rewrite/edit modes are disabled by the fork amendment — because the `humanizer` skill remains the default prose pass and `ste80-humanizer` the STE tool. Studied and built from, not executed from here: machine runs of the detector/gate execute from a live checkout of the fork, not from `reference/`, the same treatment as the other vendored trees.

## Updating this snapshot

This tree changes only by re-vendoring: replace it wholesale with a new pinned fork snapshot and regenerate `.github/vendor-avoid-ai-writing.sha256` in the same change. Code or dependency edits made in place — including dependency-update PRs against this tree — are closed, not merged: a merged bump would leave the tree matching no fork commit and falsify the provenance pinned above.

Branch note: the fork's default branch is `develop` (created for this vendoring, per the fork-first pattern used for the docs-mcp-server, NeuroStrata and ESF forks), while upstream's default is `main`. The fork's `main` is a pristine upstream mirror — upstream updates are pulled in there and merged forward into `develop`, where the fork's own amendments live. Every re-pin review includes a frontmatter diff check on `SKILL.md`, so an upstream description change cannot silently re-claim the rewrite triggers this fork disabled.

<!-- vendor-freshness: {"branch": "develop", "decision_date": "2026-11-23", "parent": "conorbronsdon/avoid-ai-writing", "parent_branch": "main", "pin": "fad13daa564f5499bb9bce573040e263614ba012", "policy": "sync-then-repin", "repo": "pratik-saptarshi/avoid-ai-writing", "review_due": "2026-12-23", "tree": "avoid-ai-writing"} -->

## Freshness

This file is the single source of truth for this tree's pin. The one-line `vendor-freshness` block above is machine-readable and is parsed by `scripts/vendor_graph.py` and `scripts/vendor_freshness.py`. Every re-vendor updates the block's `pin` in the same PR.

- **Current state:** **sync-then-repin** — first vendored at the fork's `develop` head on 2026-11-23; next freshness review 2026-12-23.
- **Owner:** the AEP maintainer (repository owner).
- **SLA:** a weekly non-gating detector opens or updates one tracking issue within 7 days of detected drift; it never auto-syncs or auto-merges.
