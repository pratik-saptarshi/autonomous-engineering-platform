# Provenance — vendored Harness² reference snapshot

- **Upstream:** https://github.com/pratik-saptarshi/harness2
- **Pinned commit:** `e5cda48c48d1072f6d855ff4cb88eabdc2ede147` ("Merge pull request #2 from pratik-saptarshi/chore/deps-litellm-1.108.3")
- **Snapshot date:** 2026-11-09 (re-vendor; first snapshot 2026-10-26 at `1cfe254e8d25b15f37048c3730134686abe60335`)
- **License:** Apache License 2.0 (copyright the Harness² authors — see `LICENSE`). `LICENSE` is preserved verbatim in this tree; `third_party/` carries its own per-component licenses (`third_party/licenses/` and per-runner `LICENSE` files), also preserved verbatim.
- **Excluded from the vendor:** `.git` (history — the snapshot was produced with `git archive`). Nothing else: the source's own `.env.example` template (empty placeholder values only) is part of the faithful snapshot and is kept.
- **Purpose:** reference snapshot of the owner's Harness² recursive agent-harnessing framework (task-level Propose–Probe–Compose refinement plus a persistent improvement harness) — studied and built from, not executed from here.

## Updating this snapshot

This tree changes only by re-vendoring: replace it wholesale with a new pinned upstream snapshot and regenerate `.github/vendor-harness2.sha256` in the same change. Code or dependency edits made in place — including dependency-update PRs against this tree — are closed, not merged: a merged bump would leave the tree matching no upstream commit and falsify the provenance pinned above.

Branch note: the source repo's default branch is `develop`; this snapshot is the `develop` head at the pinned commit. (`main` remains at `6868817` — the head both branches shared at the previous pin; the litellm merge landed on `develop` only.)

## Secret-scan annotation (2026-11-09)

Secret scan (gitleaks v8.24.3, default rules — the same configuration the repo CI security job runs — over the full pinned tree, ~4.03 MB scanned): **no leaks found**. A supplementary credential-pattern grep (GitHub/AWS token shapes, private-key headers, `sk-` keys, password/key assignments) also found no hits. No credential files exist in the tree; the only env-shaped file is the source's `.env.example` template with empty placeholder values. Nothing in this snapshot is allowlisted in `.gitleaks.toml`; no allowlist change was needed.
