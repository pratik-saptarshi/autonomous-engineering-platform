# Provenance — vendored NeuroStrata reference snapshot

- **Source (fork):** https://github.com/pratik-saptarshi/NeuroStrata
- **Upstream:** https://github.com/Cognilogical/NeuroStrata
- **Pinned commit:** `219e47de604a283c6fb8d4249db77b9824e35188` ("Task 8: trainer.rs, calibration.rs, evaluator.rs")
- **Snapshot date:** 2026-10-24
- **License:** MIT (copyright 2026 Kenton). `LICENSE` is preserved verbatim in this tree.
- **Excluded from the vendor:** `.git` (history — the snapshot was produced with `git archive`) and `web-ui/public/graph.json` (a symlink whose target, `../../.NeuroStrata/graph/graph.json`, is a runtime artifact outside the source repo; the symlink is broken in any vendored copy and would fail the CI symlink check).
- **Purpose:** reference snapshot of the Rust MCP memory daemon — the local memory layer (SynapticGraph graph/vector memory, task gate, behavioral-rule guard) that this environment's agents run on. Studied and built from, not executed from here.

Branch note: the fork's default branch is `develop`, while upstream's default is `main`. At snapshot time both fork branches pointed at the pinned commit, so the snapshot is the shared `main`/`develop` head.

Version note: this snapshot's `Cargo.toml` declares version **1.11.0** (2026-10-22). The daemon actually deployed on this VM is 1.9.0, installed separately (see `docs/neurostrata-reference.md`) — do not confuse the snapshot version with the deployed version.

## Secret-scan annotation (2026-10-24)

The credential-pattern grep gate flags exactly two files: `src/secrets.rs` and
`src/buffer.rs`. Both are the `#[cfg(test)]` suites of NeuroStrata's own
secret-redaction engine — the module that scrubs credentials out of stored
memory — so their fixtures are token-shaped by design: a `ghp_` token built
from a sequential alphabet+digits string, and the AWS documentation example
keys (one line is annotated `// official AWS example`). Gitleaks (v8.24.3,
checksum-verified, run with this repo's `.gitleaks.toml`) reports 12 findings,
all inside those two files' test modules (rules `github-pat` and
`generic-api-key`); both files are allowlisted in `.gitleaks.toml`, mirroring
the ESF `redact_test.go` precedent. The committed LanceDB store under
`.neurostrata/` was strings-scanned: no credential patterns. No other files
in the vendored tree match the credential patterns.
