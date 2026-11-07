# Provenance — vendored elephant-goldfish-model reference snapshot

- **Source (fork):** https://github.com/pratik-saptarshi/elephant-goldfish-model
- **Upstream:** https://github.com/google/elephant-goldfish-model
- **Pinned commit:** `e9e1f06aa4e26e95cd4ed37210a0632202c429e9` ("Harden pr-scope-advisory workflow for pull_request_target policy (#341)")
- **Snapshot date:** 2026-11-07
- **License:** Apache-2.0 (Google). `LICENSE` is preserved verbatim in this tree.
- **Fork note:** the fork is a pure mirror — fork HEAD and upstream HEAD were both verified at `e9e1f06a` immediately before the pin was taken. Source from upstream, not the fork.
- **Excluded from the vendor:** the upstream tree's docs site (`site/`), packaging scripts (`scripts/`), tests (`tests/`), adapters (`adapters/`), and per-host plugin manifests (`.claude-plugin/`, `.codex-plugin/`, `.cursor-plugin/`, `.plugin/`, `distributions/`, `assets/`, `com.github.copilot/`). The vendored subset is the content the skills read at run time: `skills/`, `agents/`, `resources/`, `docs/`, `LICENSE`, `plugin.json`. The source tree contains no symlinks in the vendored subset, so nothing else was excluded.
- **Purpose:** reference snapshot of Google's Elephant-Goldfish Model (EGM) v0.1.1 — a spec-driven development plugin: Elephant (context-holding agent drafts the spec) + Goldfish (reviewers in fresh contexts with zero history) + human approval gates. Studied and built from, not executed from here: the loadable skills live under `skills/egm-*/` as thin wrappers pointing into this tree.

## Updating this snapshot

This tree changes only by re-vendoring: replace it wholesale with a new pinned upstream snapshot and regenerate `.github/vendor-elephant-goldfish-model.sha256` in the same change. Code or dependency edits made in place are closed, not merged: a merged edit would leave the tree matching no upstream commit and falsify the provenance pinned above.
