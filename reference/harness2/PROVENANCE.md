# Provenance — vendored Harness² reference snapshot

- **Upstream:** https://github.com/pratik-saptarshi/harness2
- **Pinned commit:** `1cfe254e8d25b15f37048c3730134686abe60335` ("Fix arXiv link")
- **Snapshot date:** 2026-10-26
- **License:** Apache License 2.0 (copyright the Harness² authors — see `LICENSE`). `LICENSE` is preserved verbatim in this tree; `third_party/` carries its own per-component licenses (`third_party/licenses/` and per-runner `LICENSE` files), also preserved verbatim.
- **Excluded from the vendor:** `.git` (history — the snapshot was produced with `git archive`). Nothing else: the pinned tree contains no build output, caches, virtualenvs, or credential files.
- **Purpose:** reference snapshot of the owner's Harness² recursive agent-harnessing framework (task-level Propose–Probe–Compose refinement plus a persistent improvement harness) — studied and built from, not executed from here.

## Updating this snapshot

This tree changes only by re-vendoring: replace it wholesale with a new pinned upstream snapshot and regenerate `.github/vendor-harness2.sha256` in the same change. Code or dependency edits made in place — including dependency-update PRs against this tree — are closed, not merged: a merged bump would leave the tree matching no upstream commit and falsify the provenance pinned above.

Branch note: the source repo's default branch is `develop`; at the pinned commit, `develop` and `main` share the same head, so this snapshot is the `develop` head at the pinned commit.

## Secret-scan annotation (2026-10-26)

Secret scan (gitleaks v8.24.3, default rules — the same configuration the repo CI security job runs — over the full pinned tree, ~3.84 MB scanned): **no leaks found**. A supplementary credential-pattern grep (GitHub/AWS token shapes, private-key headers, `sk-` keys, password/key assignments) also found no hits. No `.env` or credential-shaped files exist in the tree (the source carries no `.env.example` either). Nothing in this snapshot is allowlisted in `.gitleaks.toml`; no allowlist change was needed.
