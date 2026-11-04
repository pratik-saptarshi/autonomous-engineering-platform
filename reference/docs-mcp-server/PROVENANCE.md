# Provenance — vendored docs-mcp-server reference snapshot

- **Source (fork):** https://github.com/pratik-saptarshi/docs-mcp-server
- **Upstream:** https://github.com/arabold/docs-mcp-server
- **Pinned commit:** `4e35baa7e82c3ec447405c48a301c8a4185e715f` ("chore(release): 3.4.1 [skip ci]")
- **Snapshot date:** 2026-10-31
- **License:** MIT (copyright 2025 Andre Rabold). `LICENSE` is preserved verbatim in this tree. The license was read from the tree itself, not from the GitHub API.
- **Excluded from the vendor:** `.git` (history — the snapshot was produced with `git archive`). The source tree contains no symlinks, so nothing else was excluded. Upstream's own `.env.example` template is part of the faithful snapshot and is kept.
- **Purpose:** reference snapshot of Andre Rabold's docs-mcp-server ("Grounded Docs MCP Server", version 3.4.1 per its `package.json`) — a TypeScript/Node MCP server that fetches documentation from websites, GitHub repositories, npm, PyPI, and local folders, indexes it, and serves version-matched search over MCP, a CLI, and a web UI, so an assistant answers from the documentation for the library versions in use instead of from memory. Studied and built from, not executed from here: nothing in this snapshot is installed, linked, or run, and a live run would execute from a live checkout of the fork, not from `reference/`, the same treatment as the other vendored trees.

## Updating this snapshot

This tree changes only by re-vendoring: replace it wholesale with a new pinned upstream snapshot and regenerate `.github/vendor-docs-mcp-server.sha256` in the same change. Code or dependency edits made in place — including dependency-update PRs against this tree — are closed, not merged: a merged bump would leave the tree matching no upstream commit and falsify the provenance pinned above.

Branch note: the fork's default branch is `develop` (created for this vendoring, per the fork-first pattern used for the NeuroStrata and ESF forks), while upstream's default is `main`. The fork's `main` is a pristine upstream mirror — future upstream updates are pulled in there (`gh repo sync --branch main`) and merged forward into `develop`, where any of the fork's own incremental changes live. This snapshot is the fork `develop` head at the pinned commit, which at vendoring time is identical to upstream `main` (fork `develop`, fork `main`, and upstream heads all verified at `4e35baa` immediately before the pin was taken).
