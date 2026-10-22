# Provenance — vendored ESF reference snapshot

- **Upstream:** https://github.com/mitkox/esf
- **Pinned commit:** `804fb461068972a707628b0a3243e4db09cafb0c` ("Add qualification-gated Harness2 improvement for OpenCode2 factory runs (#43)")
- **Snapshot date:** 2026-10-21
- **License:** MIT (copyright 2026 Owain Lewis; fork by mitkox — see `docs/upstream.md`). `LICENSE` is preserved verbatim in this tree.
- **Excluded from the vendor:** `.git` (history) and `bin/` (local build output).
- **Purpose:** reference implementation for the AEP factory lane — studied and built from, not executed from here.

Note: `bin/` build output is NOT vendored. The factory binaries were built locally from the previous pin (d41535d) during the install phase (plan Task 2) and live outside the repo at `~/workspace/repos/esf/bin/` — rebuild from the new pin before executing.

## Update history

- 2026-10-21: re-vendored at `804fb46` (#43 — qualification-gated Harness2 improvement for OpenCode2 factory runs). 505 files in manifest (was 478). Secret-scan: same single synthetic fixture in `redact_test.go`, no new hits.

## Secret-scan annotation (2026-10-18)

The credential-pattern grep gate flags exactly one file: `internal/factory/redact_test.go`
(`TestRedactorScrubsPatterns` — a security unit test proving captured agent output is
scrubbed before durable storage). Both hits verified as synthetic fixtures, not real
secrets: a `ghp_` token built from a sequential alphabet+digits string, and the AWS
documentation example key `AKIAIOSFODNN7EXAMPLE`. Each appears as both the `input`
and the `mustNotSee` value of its test case (self-consistent fixture), and the file
carries a `gitleaks:allow -- synthetic redaction fixture` annotation. No other files
in the vendored tree match the credential patterns.
