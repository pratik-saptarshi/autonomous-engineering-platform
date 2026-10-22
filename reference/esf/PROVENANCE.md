# Provenance — vendored ESF reference snapshot

- **Upstream:** https://github.com/pratik-saptarshi/esf
- **Pinned commit:** `d41535d86a13e55fe2357d9e0a108566d68ce1b9` ("Add durable sf turn executor with Cube checkpoints and permissions (#40)")
- **Snapshot date:** 2026-10-18
- **License:** MIT (copyright 2026 Owain Lewis; fork by mitkox — see `docs/upstream.md`). `LICENSE` is preserved verbatim in this tree.
- **Excluded from the vendor:** `.git` (history) and `bin/` (local build output).
- **Purpose:** reference implementation for the AEP factory lane — studied and built from, not executed from here.

Note: `bin/` build output is NOT vendored. The factory binaries were built locally from this exact commit during the install phase (plan Task 2) and live outside the repo at `~/workspace/repos/esf/bin/`.

## Secret-scan annotation (2026-10-18)

The credential-pattern grep gate flags exactly one file: `internal/factory/redact_test.go`
(`TestRedactorScrubsPatterns` — a security unit test proving captured agent output is
scrubbed before durable storage). Both hits verified as synthetic fixtures, not real
secrets: a `ghp_` token built from a sequential alphabet+digits string, and the AWS
documentation example key `AKIAIOSFODNN7EXAMPLE`. Each appears as both the `input`
and the `mustNotSee` value of its test case (self-consistent fixture), and the file
carries a `gitleaks:allow -- synthetic redaction fixture` annotation. No other files
in the vendored tree match the credential patterns.
