# Provenance — vendored security-audit-skill reference snapshot

- **Source (fork):** https://github.com/pratik-saptarshi/security-audit-skill
- **Upstream:** https://github.com/cloudflare/security-audit-skill
- **Pinned commit:** `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8` ("Clarify guidance and full audit modes")
- **Snapshot date:** 2026-10-26
- **License:** MIT (copyright 2025-2026 Cloudflare, Inc.). `LICENSE` is preserved verbatim in this tree.
- **Excluded from the vendor:** `.git` (history — the snapshot was produced with `git archive`).
- **Purpose:** reference snapshot of Cloudflare's security-audit agent skill — the single-repo skill that seeded Cloudflare's vulnerability discovery harness. It runs a six-phase audit (reconnaissance, coverage-led hunting, candidate validation, structured findings against `report-schema.json`, independent record verification, target-neutral reporting) with per-surface topic guides and two Node validators (`validate-coverage-ledger.cjs`, `validate-findings.cjs`) whose tests ship in the tree. Studied and built from, not executed from here: the validators' tests are part of the byte-identical snapshot and are not wired into this repo's CI, the same treatment as the other vendored trees.

## Updating this snapshot

This tree changes only by re-vendoring: replace it wholesale with a new pinned upstream snapshot and regenerate `.github/vendor-security-audit-skill.sha256` in the same change. Code or dependency edits made in place — including dependency-update PRs against this tree — are closed, not merged: a merged bump would leave the tree matching no upstream commit and falsify the provenance pinned above.

Branch note: the fork's default branch is `develop`, while upstream's default is `main`. This snapshot is the fork `develop` head at the pinned commit, which at vendoring time is identical to upstream `main` (the fork was synced to upstream immediately before the pin was taken).

## Secret-scan annotation (2026-10-26)

Clean. A credential-pattern grep over the pinned tree matched nothing, and a gitleaks scan of the tree (~323 KB) reported no leaks. The skill's prose discusses credentials, tokens, and attack classes extensively — that is its subject matter — but it contains no credential-shaped values, fixtures included. No `.gitleaks.toml` allowlist entries were needed for this tree.
