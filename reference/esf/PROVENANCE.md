# Provenance — vendored ESF reference snapshot

- **Upstream:** https://github.com/pratik-saptarshi/esf
- **Pinned commit:** `705808f11a670357646e76be1032873267e14ef9` ("chore(deps): bump certifi in uv.lock to 2026.10.23 (Dependabot) (#6)")
- **Snapshot date:** 2026-10-26
- **License:** MIT (copyright 2026 Owain Lewis; fork by mitkox — see `docs/upstream.md`). `LICENSE` is preserved verbatim in this tree.
- **Excluded from the vendor:** `.git` (history) and `bin/` (local build output).
- **Purpose:** reference implementation for the AEP factory lane — studied and built from, not executed from here.

## Updating this snapshot

This tree changes only by re-vendoring: replace it wholesale with a new pinned upstream snapshot and regenerate `.github/vendor-esf.sha256` in the same change. Code or dependency edits made in place — including dependency-update PRs against this tree — are closed, not merged: a merged bump would leave the tree matching no upstream commit and falsify the provenance pinned above.

Note: `bin/` build output is NOT vendored. The factory binaries were built locally from the previous pin (d41535d) during the install phase (plan Task 2) and live outside the repo at `~/workspace/repos/esf/bin/` — rebuild from the new pin before executing.

## Update history

- 2026-10-21: re-vendored at `804fb46` (#43 — qualification-gated Harness2 improvement for OpenCode2 factory runs). 505 files in manifest (was 478). Secret-scan: same single synthetic fixture in `redact_test.go`, no new hits.
- 2026-10-26: re-vendored at `705808f`. Two upstream changes over the previous pin (`3f6430b`): fork PR #5 bumps the controlplane web dependencies (vite 8.3.4 → 8.3.5 in `internal/controlplane/web/package.json`; undici → 8.12.3 in `package-lock.json`), and fork PR #6 bumps certifi in `uv.lock` to 2026.10.23. The `uv.lock` change also repairs a provenance divergence: the previous snapshot carried certifi 2026.10.19 from AEP PR #29's in-place Dependabot merge, which matched no fork commit; the snapshot now carries the fork's 2026.10.23, an upgrade, and the tree once again matches a single upstream commit byte-for-byte. Content delta vs the previous snapshot: exactly 3 files (`internal/controlplane/web/package.json`, `internal/controlplane/web/package-lock.json`, `uv.lock`). 506 files in manifest. Secret-scan (gitleaks, repo CI configuration): no leaks; the only credential-pattern fixtures remain the allowlisted synthetic ones in `internal/factory/redact_test.go` and `internal/factory/evidence_test.go`, both unchanged.

## Secret-scan annotation (2026-10-18)

The credential-pattern grep gate flags exactly one file: `internal/factory/redact_test.go`
(`TestRedactorScrubsPatterns` — a security unit test proving captured agent output is
scrubbed before durable storage). Both hits verified as synthetic fixtures, not real
secrets: a `ghp_` token built from a sequential alphabet+digits string, and the AWS
documentation example key `AKIAIOSFODNN7EXAMPLE`. Each appears as both the `input`
and the `mustNotSee` value of its test case (self-consistent fixture), and the file
carries a `gitleaks:allow -- synthetic redaction fixture` annotation. No other files
in the vendored tree match the credential patterns.
