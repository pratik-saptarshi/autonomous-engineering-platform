# G-P7 — ESF credential post-run replay probe: findings

Gate (plan §2, pre-registered): take a credential used by a completed ESF run
and attempt reuse after the run ends; inventory the last 10 ESF runs for
credential scope and expiry. **Pass:** any finished-run credential still works,
or any run received broader credentials than its harness needed. **Kill:**
credentials already die with the run and are already minimal.

## Leg 1 — run inventory: zero runs exist to probe

Executed checks (2026-11-13, this VM):

- No `/dev/kvm`; no CubeSandbox deployment; no Temporal server (nothing
  listening on 7233/7243, no temporal/cube/esf/factory processes).
- No ESF state anywhere: `/var/lib/esf` (the configured default `data_dir`)
  absent, `~/.config/esf` and `~/.local/share/esf` absent, `/run/credentials`
  empty, `podman ps -a` shows no containers, no `factory.toml` in use in the
  fork clone (only the example config).
- The vendored snapshot's sandbox providers are `cube` and `fake` only — the
  fork's podman provider (fork PR #4) is not in the vendored pin, so the
  vendored ESF cannot execute a workload in this environment at all.

**The inventory of "the last 10 ESF runs" returns 0 runs.** No ESF run has
ever completed in this environment, so there is no finished-run credential
to replay. This leg could not be executed as specified, and the gate's
premise — that ESF runs are a live credential surface here today — is
false in this environment. (Stated plainly per the no-quiet-redefinition
rule; the mechanism probe below is a substitute, not a reinterpretation.)

## Leg 2 — mechanism probe, executed against the vendored snapshot

The snapshot has exactly two credential modes (`internal/factory/config.go`:
`credential_mode must be environment or cube_egress`; unset = environment
behaviour). The credential path was executed via the snapshot's own test
suites in a scratch copy (`~/workspace/worktrees/esf-phase0-probe/src`,
Go 1.27.2, `-p 1 -count=1`):

- `go test ./internal/agentharness/ -run TestNativeCLI` — **PASS** (all 4).
  - `TestNativeCLIPromptAndCredentialIsolation`: with `cube_egress`, the
    sandbox command env carries the literal string
    `cube-egress-managed-placeholder` — even when the task env offers a
    real key, it is discarded.
  - `TestNativeCLIResolvedEndpointsArePerSandbox`: with `environment`
    mode, the sandbox command env carries the **real key value**
    (`ANTHROPIC_API_KEY` / `ESF_CODEX_API_KEY` = the resolved secret).
- `go test ./internal/factory/ -run 'TestRuntimeNetwork|TestCubeEgress|
  TestOpenCode|TestApplyRuntimeNetwork'` — **PASS**. The cube_egress
  secret is resolved only inside the activity worker and "never becomes
  workflow input, sandbox environment, or durable evidence"
  (`internal/factory/credential_policy.go`).
- `go test ./internal/sandbox/cube/ -run TestCubeNetworkRules` — **PASS**.
  Injection is bound to exact scheme/host/SNI/method/paths rules.
- Code-level facts (read in the snapshot): in `environment` mode the key
  placed in the run is the operator's **standing** provider key, taken
  from the task env or the worker's own process env
  (`internal/agentharness/native_cli.go`: `key = task.Env[...]` /
  `h.lookupEnv(...)`). A grep for `rotat|revok|expire|expiry` across the
  credential path (`credential_policy.go`, `native_cli.go`, `config.go`)
  returns **zero** hits: nothing scopes, rotates, revokes, or expires it
  at run end — it is the same long-lived key before, during, and after
  every run.

### What this means for the gate's two pass conditions

- *"Any finished-run credential still works"* — untestable (no finished
  runs), but in `environment` mode it is true **by construction** for any
  run that ever executes: the credential is the standing key, valid
  independent of the run. In `cube_egress` mode it is false by
  construction: the run never holds a credential.
- *"Any run received broader credentials than its harness needed"* — in
  `environment` mode, yes by construction: the run receives the operator's
  full standing provider key (whole-account scope) for a single task. In
  `cube_egress` mode, no: injection is scoped to the model's exact
  endpoints.

## Premise correction (material for Phase 2a)

The panel priced P7 as a build (per-run scoped credentials, reusing ghg
lease machinery, 3–6 days). The snapshot shows ESF **already built the
scoping**: `cube_egress` is brokered injection at the egress layer — the
run holds a placeholder, the secret never enters the sandbox, injection
is endpoint-scoped. The residual gap is not missing machinery; it is that
`environment` mode exists, is the legacy default when `credential_mode`
is unset, and places the standing key inside the run. If ESF ever
executes here, the AEP-shaped fix is a configuration/policy enforcement
(make `cube_egress` mandatory in AEP's ESF configs; refuse or alarm on
`environment` mode), not new credential machinery. Note also that
`cube_egress` requires the Cube provider, which cannot run in this VM —
the entire question is dormant until an ESF-capable host exists.

## Verdict: **COULD-NOT-EXECUTE as specified** (premise void here)

The replay leg has no object: zero completed ESF runs exist in this
environment. The executed mechanism probe is decisive about the
underlying question — the exposure is real in `environment` mode and
already closed in `cube_egress` mode — and it **re-scopes** Phase 2a
from "build per-run scoping" to "mandate the mode ESF already ships".
Whether Phase 2a proceeds in that reduced form, or waits for an
ESF-capable host, is a decision for the plan's owner; the gate itself
neither passes (no finished-run credential was replayed) nor kills
(the exposure it targeted demonstrably exists in one of two modes).
