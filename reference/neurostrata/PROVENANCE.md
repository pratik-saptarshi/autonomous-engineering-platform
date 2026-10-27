# Provenance — vendored NeuroStrata reference snapshot

- **Source (fork):** https://github.com/pratik-saptarshi/NeuroStrata
- **Upstream:** https://github.com/Cognilogical/NeuroStrata
- **Pinned commit:** `67c90c7021759de8e5e72c4697561051497b8706` ("chore(web-ui): bump vite to 8.3.5 and source-map-js to 1.2.2 (Dependabot) (#18)")
- **Snapshot date:** 2026-10-26
- **License:** MIT (copyright 2026 Kenton). `LICENSE` is preserved verbatim in this tree.
- **Excluded from the vendor:** `.git` (history — the snapshot was produced with `git archive`) and `web-ui/public/graph.json` (a symlink whose target, `../../.NeuroStrata/graph/graph.json`, is a runtime artifact outside the source repo; the symlink is broken in any vendored copy and would fail the CI symlink check).
- **Purpose:** reference snapshot of the Rust MCP memory daemon — the local memory layer (SynapticGraph graph/vector memory, task gate, behavioral-rule guard) that this environment's agents run on. Studied and built from, not executed from here.

## Updating this snapshot

This tree changes only by re-vendoring: replace it wholesale with a new pinned upstream snapshot and regenerate `.github/vendor-neurostrata.sha256` in the same change. Code or dependency edits made in place — including dependency-update PRs against this tree — are closed, not merged: a merged bump would leave the tree matching no upstream commit and falsify the provenance pinned above.

Branch note: the fork's default branch is `develop`, while upstream's default is `main`. This snapshot is the fork `develop` head at the pinned commit.

Version note: this snapshot's `Cargo.toml` declares version **1.13.0**. The daemon actually deployed on this VM is 1.9.0, installed separately (see `docs/neurostrata-reference.md`) — do not confuse the snapshot version with the deployed version.

## Update history

- 2026-10-26: re-vendored at `67c90c7`. The web-ui security bumps — vite
  `^8.3.0` → `^8.3.5` (lockfile resolves 8.3.5) and source-map-js 1.2.1 →
  1.2.2 — landed in the fork via pratik-saptarshi/NeuroStrata PR #18 because
  AEP PR #50 (Dependabot) was closed rather than merged into the prior
  snapshot. This re-vendor also fast-forwards the snapshot from 1.11.0 across
  upstream 1.12/1.13 and the fork's remediation program. Manifest:
  `.github/vendor-neurostrata.sha256`, 294 files.

## Secret-scan annotation (2026-10-26)

The credential-pattern grep gate flags exactly two files: `src/secrets.rs` and
`src/buffer.rs`. Both are the `#[cfg(test)]` suites of NeuroStrata's own
secret-redaction engine — the module that scrubs credentials out of stored
memory — so their fixtures are token-shaped by design: a `ghp_` token built
from a sequential alphabet+digits string, and the AWS documentation example
keys (one line is annotated `// official AWS example`). Both files are
allowlisted in `.gitleaks.toml`, mirroring the ESF `redact_test.go`
precedent. The committed LanceDB store under `.neurostrata/` was included in
the scan: no credential patterns. No other files in the vendored tree match
the credential patterns.
