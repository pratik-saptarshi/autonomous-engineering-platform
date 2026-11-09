# Adoption plan — ORAS + OpenTelemetry (AEP)

Authorized by Pratik 2026-11-09 ("Proceed with adoption recommendations")
on the CNCF fit analysis
(goal files/2026-11-09-cncf-tools-aep-fit-analysis.html). The two Adopt
candidates only; Temporal, Cedar, ko remain Evaluate-later at their named
triggers. Both tracks run the feature-pr-pipeline, PRs target develop, and
stop at merge-ready — merges are gated (CI green on the final head, Codex
clean on that head, zero unresolved threads) and executed by the parent
under the adoption instruction; a Codex no-show is a decision item, never
absorbed.

## Pinned decisions

- **D1 — Registry:** GHCR. Artifacts under
  `ghcr.io/pratik-saptarshi/aep-oci-context` and
  `ghcr.io/pratik-saptarshi/aep-oci-image`. Tags are immutable: tag = the
  dist build's git stamp (short SHA fallback); a pre-push existence check
  refuses to overwrite an existing tag (published-records rule).
- **D2 — ORAS interface:** the `oras` CLI, pinned and checksum-verified at
  install (mirroring CI's gitleaks pattern), driven by a new
  `scripts/distribute-oci.sh` plus a Makefile target.
  `scripts/package-oci.sh` and its no-builder tarball fallback stay
  untouched — distribution failure must never block packaging.
- **D3 — OTel SDK language (corrects the analysis):** Python. Both named
  targets are Python — ghg is `tools/ghg/ghg.py`, the accrual is
  `scripts/orch/`. The Go SDK for cmd/aep is out of scope for this
  adoption.
- **D4 — Telemetry shape:** off by default; enabled by env var naming a
  JSONL file (`GHG_OTEL_FILE`, `ORCH_OTEL_FILE`); a small in-tree JSONL
  span exporter; no collector, no server. Receipts and logs remain the
  system of record — telemetry supplements, never replaces.
- **D5 — Dependency:** `opentelemetry-api` + `opentelemetry-sdk`, exactly
  pinned in `tools/ghg/requirements-otel.txt`; imports guarded so the
  tools run unchanged (no-op tracer) when the SDK is absent.
- **D6 — Attribute discipline:** spans carry operation, actor, exit code,
  duration, budget/gate verdict only — never argv, never resolved env
  values, never tokens (mirrors the orchestration loader's absolute
  no-print rule for resolved $ENV).

## Track A — ORAS distribution

- `scripts/distribute-oci.sh`: pushes `dist/oci/aep-oci-context.tar.gz`
  (always available) and `dist/oci/aep-oci.tar` (when a builder produced
  it) to GHCR per D1/D2; `--dry-run` prints the exact oras invocations
  without pushing; refuses when the target tag already exists; auth via
  `oras login` with a token from the environment (never printed, never
  logged).
- Makefile: a `dist-publish` target depending on `dist/oci` with ALL
  inputs declared as prerequisites (the PR #124 N6 lesson — every dist
  target names its inputs, including both scripts).
- Tests (mutation-proven, per the PR #124 retrospective): shell tests
  under `scripts/tests/` with a stub `oras` on PATH — no network. Cases:
  context artifact pushed with the stamped tag; image tar pushed when
  present, skipped when absent; existing-tag refusal (stub reports the
  tag → non-zero, no push attempted); dry-run performs zero stub push
  calls. Each test must go red under a named mutation (e.g. deleting the
  existence check turns the refusal test red).
- Install: pin the oras CLI version + sha256 in the script's companion
  docs (README section in the PR) and install it locally (~/opt or
  ~/go/bin) with checksum verification as part of execution; the first
  live GHCR push is a post-merge step by the parent, reported separately.
- Docs: a short section in the repo README or scripts docs naming the
  distribution flow, the immutability rule, and the fallback's survival.

## Track B — OpenTelemetry for ghg + orchestration accrual

- ghg (`tools/ghg/ghg.py`): spans around the run / check / watch
  operations per D4–D6, created through a tiny in-tree helper module
  (`tools/ghg/telemetry.py`) that owns provider setup, the JSONL
  exporter, and the no-op path. Existing ghg tests must pass unchanged
  with telemetry off and with the SDK absent.
- Orchestration (`scripts/orch/`): one span per accrual/dry-run tick in
  the observe path, same helper pattern (a parallel small module is
  acceptable; do not cross-import between tools/ghg and scripts/orch).
- Tests (mutation-proven): with the env unset, byte-identical CLI
  output/behaviour and no telemetry file created; with the env set, the
  JSONL file contains the expected span names and D6 attributes — and a
  canary test proves a resolved env value / token-shaped string in the
  environment never appears in the telemetry output (delete the attribute
  filter → canary goes red).
- `tools/ghg/requirements-otel.txt` with exact pins; a README note that
  the dependency is optional.

## Non-goals

- No Temporal, Cedar, ko, Prometheus, or Grafana work — Evaluate-later
  verdicts stand until their triggers fire.
- No changes to package-oci.sh's behaviour, the VM bundle, or ghg's
  gating semantics; telemetry must not alter any ghg exit code or output
  on any path.
- No live GHCR push inside either PR's test suite; no new servers or
  collectors anywhere.

## Gates (both tracks)

- TDD: failing test first per behaviour; every gate mutation-proven
  before the PR is called ready.
- Whole-branch independent review before push; hygiene per the
  feature-pr-pipeline.
- This plan ships in each PR under `docs/plans/`.
- PR target: develop. All GitHub calls through ghg (GHG_ACTOR=oras-adoption
  / otel-adoption). Stop at merge-ready with a full census (head SHA, CI
  state, Codex receipt state, thread count) reported to the parent.
