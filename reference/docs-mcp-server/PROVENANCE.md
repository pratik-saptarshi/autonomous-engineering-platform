# Provenance — vendored docs-mcp-server reference snapshot

- **Source (fork):** https://github.com/pratik-saptarshi/docs-mcp-server
- **Upstream:** https://github.com/arabold/docs-mcp-server
- **Pinned commit:** `5e1ce52` ("Merge upstream main into develop (vendor sync 2026-11-19)")
- **Snapshot date:** 2026-11-19 (re-vendor; previous pin 2026-11-16 at `506f27b`; earlier 2026-11-09 at `0b6bbee`, first 2026-10-31 at `4e35baa`)
- **License:** MIT (copyright 2025 Andre Rabold). `LICENSE` is preserved verbatim in this tree. The license was read from the tree itself, not from the GitHub API.
- **Excluded from the vendor:** `.git` (history — the snapshot was produced with `git archive`). The source tree contains no symlinks, so nothing else was excluded. Upstream's own `.env.example` template is part of the faithful snapshot and is kept.
- **Purpose:** reference snapshot of Andre Rabold's docs-mcp-server ("Grounded Docs MCP Server", version 3.4.1 per its `package.json`) — a TypeScript/Node MCP server that fetches documentation from websites, GitHub repositories, npm, PyPI, and local folders, indexes it, and serves version-matched search over MCP, a CLI, and a web UI, so an assistant answers from the documentation for the library versions in use instead of from memory. Studied and built from, not executed from here: nothing in this snapshot is installed, linked, or run, and a live run would execute from a live checkout of the fork, not from `reference/`, the same treatment as the other vendored trees.

## Updating this snapshot

This tree changes only by re-vendoring: replace it wholesale with a new pinned upstream snapshot and regenerate `.github/vendor-docs-mcp-server.sha256` in the same change. Code or dependency edits made in place — including dependency-update PRs against this tree — are closed, not merged: a merged bump would leave the tree matching no upstream commit and falsify the provenance pinned above.

Branch note: the fork's default branch is `develop` (created for this vendoring, per the fork-first pattern used for the NeuroStrata and ESF forks), while upstream's default is `main`. The fork's `main` is a pristine upstream mirror — upstream updates are pulled in there (`gh repo sync --branch main`) and merged forward into `develop`, where the fork's own incremental changes live. At the first snapshot (2026-10-31) `develop` was identical to upstream `main` at `4e35baa`. This pin is no longer identical to upstream: on top of upstream `main` at `aa8b5b7` (two upstream commits past `4e35baa`, including the husky commit-msg fix), `develop` carries the fork's security-baseline commits from the AEP vendored-repo maintenance pilot (2026-11-07): a Dependabot config and a CI trigger fix (fork PR #3), and the first fork-first alert fixes (fork PR #4) — follow-redirects 1.16.1 → 1.16.2 (GHSA-mrwp-f3q8-3g9p), a stale lockfile root version repaired (3.3.0 → 3.4.1), and vitest `^4.1.12` → `^5.1.0`. The 2026-11-09 pin added fork PR #6: the minimatch 11 upgrade (GHSA-g3hv-75wg-m249) that the previous pin deliberately deferred — minimatch `^10.2.6` → `^11.0.5`, with `src/scraper/utils/patternMatcher.ts` ported off the `makeRe` API minimatch 11 removed (plus its test).

This pin (2026-11-16, `506f27b`) is four fork commits past `0b6bbee`: fork PR #7 adds direct-API and proxy endpoint support for embeddings without an API key (config, `EmbeddingFactory`, `DocumentStore`, `DocumentPipeline`, the CLI, README and the embedding/configuration guides, plus the fork-local remediation plan `docs/superpowers/plans/2026-11-09-docs-mcp-pr7-remediation.md`, kept because the snapshot stays faithful); fork PRs #11 and #12 take the Dependabot npm-production group (27 updates) and npm-development group (5 updates); fork PR #15 takes `@hono/node-server` 2.1.5 → 2.1.8, the alert the AEP side was closed over rather than merged in place. Content delta vs the previous snapshot: 18 files (17 modified, 1 added). 918 files in manifest. Still open on the fork at this pin and deferred to a later re-vendor: minimatch 11.0.6, hono 4.13.18, and the next npm-development and npm-production group updates.

<!-- vendor-freshness: {"branch": "develop", "decision_date": "2026-11-19", "parent": "arabold/docs-mcp-server", "parent_branch": "main", "pin": "5e1ce5268f6dd84e2aeee1738d6ac2bac51896fb", "policy": "sync-then-repin", "repo": "pratik-saptarshi/docs-mcp-server", "review_due": "2026-12-19", "tree": "docs-mcp-server"} -->

## Disposition (2026-11-19 re-vendor)

- Fork `main` was already identical to upstream `arabold/docs-mcp-server@main`; the forward merge into `develop` is the sync (10 fork-only commits preserved, upstream head ancestor).
- 919 upstream files + `PROVENANCE.md`; 2 new source files (`src/store/openDatabase.ts` and its test), 17 changed files. No new instruction surfaces (`.claude/` count unchanged at 15) and no new lifecycle scripts.
- Dependency floor check passed on `develop`: follow-redirects 1.16.2, minimatch 11.0.5, lockfile root 3.4.1, `patternMatcher.ts` ported off `makeRe`. No downgrade.
- Secret scan: clean; no allowlist entries needed.
