# Remediation Plan — PRs with CI Issues & Codex Findings

**Status:** Panel-validated (overseer + paperthin + ub lenses), independent review APPROVED-WITH-CHANGES applied.
**Scope:** AEP #133, esf #4, docs-mcp-server #2/#6, NeuroStrata #38 (merged), Cognilogical #72 (closed).
**Method:** Spec-driven, TDD (failing test first), sub-agent execution per task (one agent per task, verifiable unit).

---

## Verified ground truth (2026-11-09)

| PR | State | Findings | Checks |
|---|---|---|---|
| AEP #133 | OPEN CLEAN | 24/24 threads **resolved**, fixes through `4c3b917` (LLD §9.2 runtime socket guarded) | all 11 pass |
| esf #4 | OPEN BEHIND | 10 findings: 9 fixed, **1 unfixed** (`sandbox.go:228` host-written file ownership) | 2 pass, 2 fail (Linux checks, check) |
| docs-mcp #2 | OPEN BLOCKED | Dependabot duplicate, Lint FAIL (superseded by #6) | fail |
| docs-mcp #6 | OPEN CLEAN | 0 | all 8 pass |
| NeuroStrata #38 | MERGED | 0 | hard green; report-only = baseline noise (no develop CI by design) |
| Cognilogical #72 | CLOSED | killed (1,566-file fork divergence) | — |

## Task list (each = one sub-agent, TDD, exact acceptance)

### T1 — esf #4 P1: stale exit-file removal follows `/run` symlink (BLOCKER)
- **Spec:** `Execute()` must resolve the exit-file *parent* via `resolveInRootfs` before unlinking the final component (mirror `readExitFile`).
- **TDD:** failing test first — plant `/run` → symlink to host marker dir, assert next `Execute` does NOT delete host `esf-exit`. See it fail, then fix.
- **Acceptance:** `go test ./internal/sandbox/podman/ -run TestExecuteStaleExitFile -count=1` passes; `grep -n resolveInRootfs sandbox.go` covers both paths.

### T2 — esf #4 P2: tmp image export never closed (BLOCKER)
- **Spec:** `defer tmp.Close()` immediately after successful `CreateTemp`.
- **TDD:** test asserting close on success + error paths (fd count / close hook).
- **Acceptance:** `grep -n "tmp.Close" provider.go` non-empty; existing `TestExtractRootfs*` suite green.

### T3 — esf #4 ownership: fail-closed + escape hatch
- **Spec:** `Create()` hard-errors (`ErrInvalidSpec`) when `[podman] user` set + `euid != 0`; `user=""` documented escape hatch (rootless runs with known-degraded ownership, explicit not silent).
- **TDD:** unit test: `user="esf"` + non-root → `ErrInvalidSpec`; `user=""` + non-root → passes. Integration: `go test ./internal/sandbox/podman/ -run TestIntegration -count=1` writes `$HOME` as uid 1000, `t.Skip` when podman unavailable.
- **Acceptance:** both tests green; deployment matrix clarified in `templates/podman/README.md`.

### T4 — esf CI: make the gate real
- **Spec:** trigger `on.push.branches` covers `develop` (currently `master` only); add minimal `pr-go-gate.yml` (`go vet` + `go test -race` + `gofmt` check, ~1 min); protect `develop` with required checks.
- **TDD:** trigger PR with a deliberate `go vet` failure → gate goes red; revert → green.
- **Acceptance:** `gh pr checks 4` reports the new gate; branch protection shows required contexts.

### T5 — docs-mcp #2: close, never merge
- **Spec:** close PR #2 with superseded-by-#6 rationale (signed `Terminator3000-DarkCrouton`).
- **Acceptance:** PR#2 state CLOSED; issue #5 updated noting #2's lockfile-drift root cause.

### T6 — AEP #133: verify-and-merge
- **Spec:** re-run `scripts/check_design_invariants.py --self-test` + `--check` (both exit 0, guarding LLD §9.2 runtime socket and C1-C12 invariants); confirm 24/24 threads resolved; commit the AGENTS.md signature rule; mark/delete the stale remediation plan (`SUPERSEDED` banner or remove).
- **Acceptance:** PR #133 `mergeStateStatus: CLEAN`, all 11 checks pass, zero unresolved threads → merge per AGENTS.md (conversation resolution satisfied).

### T7 — docs-mcp #6: glob/nested-minimatch completion
- **Spec:** amend branch: `npm update @fastify/static` (10.1.7→10.1.10 in-range, lifts glob→14.0.4, clears nested minimatch under `glob/` + `readdir-glob/`).
- **TDD:** lockfile assertions — `glob 14.x`; query Dependabot alerts for `npm-run-all`/`npm` nested copies (file tracking issue if flagged, else close).
- **Acceptance:** `npm run lint` + `typecheck` clean; `patternMatcher.test.ts` 8/8; full suite failures limited to Playwright-missing e2e (pre-existing).

### T8 — Residual caps: accepted-risk record
- **Spec:** update AEP #134 (diskcache, undici-npm, glib, web-ui minimatch — all parent-capped, verified) + arabold #611 (glob fixable via T7).
- **Acceptance:** both issues updated with residual list + re-check triggers (tauri gtk bump, eslint minimatch bump, diskcache release).

## Execution order (dependencies)
T1+T2 (parallel) → T3 → T4 → (PR#4 merge) → T5+T7 (parallel) → T6 → T8.
T1–T4 unblock esf #4; T5–T7 are independent; T6 is verify-only.

## Test plan (global)
- Unit: new regression tests per task run with `-count=1`, fail-before/pass-after demonstrated.
- Integration: podman/uid-1000 test skipped (not failed) when runtime unavailable.
- CI: T4 gate must go red on a deliberate break before it is trusted.

## Acceptance criteria (global)
- Zero unresolved review threads on AEP #133 and esf #4.
- Zero CI-red mergeable PRs (except pre-existing Playwright e2e env failures, documented).
- Every merged fix traces to a failing-then-passing test.

---

— Terminator3000-DarkCrouton
