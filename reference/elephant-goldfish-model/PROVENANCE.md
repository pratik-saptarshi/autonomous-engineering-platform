# Provenance — vendored elephant-goldfish-model reference snapshot

- **Source (fork):** https://github.com/pratik-saptarshi/elephant-goldfish-model
- **Upstream:** https://github.com/google/elephant-goldfish-model
- **Pinned commit:** `70406c4d22cc7ea8299637c2c5b44625c48b3f08` ("feat(skills): implement EGM Lite rapid engineering protocol (Stage 2) (#438)")
- **Snapshot date:** 2026-11-19 (re-vendor; first snapshot 2026-11-07 at `e9e1f06a`)
- **License:** Apache-2.0 (Google). `LICENSE` is preserved verbatim in this tree.
- **Fork note:** the fork is a pure mirror — fork HEAD and upstream HEAD were both verified at `e9e1f06a` immediately before the pin was taken. Source from upstream, not the fork.
- **Excluded from the vendor:** the upstream tree's docs site (`site/`), packaging scripts (`scripts/`), tests (`tests/`), adapters (`adapters/`), and per-host plugin manifests (`.claude-plugin/`, `.codex-plugin/`, `.cursor-plugin/`, `.plugin/`, `distributions/`, `assets/`, `com.github.copilot/`). The vendored subset is the content the skills read at run time: `skills/`, `agents/`, `resources/`, `docs/`, `LICENSE`, `plugin.json`. The source tree contains no symlinks in the vendored subset, so nothing else was excluded.
- **Purpose:** reference snapshot of Google's Elephant-Goldfish Model (EGM) v0.1.1 — a spec-driven development plugin: Elephant (context-holding agent drafts the spec) + Goldfish (reviewers in fresh contexts with zero history) + human approval gates. Studied and built from, not executed from here: the loadable skills live under `skills/egm-*/` as thin wrappers pointing into this tree.

## Updating this snapshot

This tree changes only by re-vendoring: replace it wholesale with a new pinned upstream snapshot and regenerate `.github/vendor-elephant-goldfish-model.sha256` in the same change. Code or dependency edits made in place are closed, not merged: a merged edit would leave the tree matching no upstream commit and falsify the provenance pinned above.

<!-- vendor-freshness: {"branch": "develop", "decision_date": "2026-11-19", "parent": "google/elephant-goldfish-model", "parent_branch": "main", "pin": "70406c4d22cc7ea8299637c2c5b44625c48b3f08", "policy": "repin", "repo": "pratik-saptarshi/elephant-goldfish-model", "review_due": "2026-12-19", "tree": "elephant-goldfish-model"} -->

## Disposition (2026-11-19 re-vendor)

- Fork `develop` == upstream `google/elephant-goldfish-model@main` at this pin (pure mirror still true).
- Vendored subset unchanged in shape: `skills/`, `agents/`, `resources/`, `docs/`, `LICENSE`, `plugin.json` — 110 files (was 90; EGM Lite adds 20). No symlinks in subset.
- No new instruction surfaces beyond the upstream skill content already under `reference/`. Secret scan clean.

## Freshness

This file is the single source of truth for this tree's pin. The one-line `vendor-freshness` block above is machine-readable and is parsed by `scripts/vendor_graph.py` and `scripts/vendor_freshness.py`. Every re-vendor updates the block's `pin` in the same PR.

- **Current state:** **repin** — re-vendored at the current fork head on 2026-11-19; next freshness review 2026-12-19.
- **Owner:** the AEP maintainer (repository owner).
- **SLA:** a weekly non-gating detector opens or updates one tracking issue within 7 days of detected drift; it never auto-syncs or auto-merges.
- **Known out-of-scope drift for this lane:** `harness2` (2 behind upstream), `neurostrata` (170 behind, 604 ahead), and `craft-anything` (decision due) are reported by the detector, not fixed by the 2026-11-19 migration.
