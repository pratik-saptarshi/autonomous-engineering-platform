# Verifier of Record

## Status

Accepted.

## Decision

The canonical verifier for this repository is `scripts/mechanical_verify.py`.

## Rationale

Single entry point for mechanical verification keeps every workflow citing the same check.

## Non-Canonical Alternative

`internal/verifier/runner/runner.go` is not canonical and must not be cited as the verifier of record.

## References

- `scripts/mechanical_verify.py`
- `internal/verifier/runner/runner.go` (non-canonical)
