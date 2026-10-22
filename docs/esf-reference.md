# ESF reference

## What it is

pratik-saptarshi/esf — Engineering Software Factory: a self-hosted factory that runs coding agents in isolated CubeSandbox microVMs and verifies their changes. Pipeline: task → Temporal durable workflow → CubeSandbox microVM → coding agent → deterministic verification → patch + evidence. Deterministic gates decide factory success; agent success alone is not enough.

Vendored snapshot: [PROVENANCE.md](../reference/esf/PROVENANCE.md) — upstream `https://github.com/pratik-saptarshi/esf` at `804fb461068972a707628b0a3243e4db09cafb0c` (2026-10-21, MIT).

## Mapping to the AEP loop

| ESF | AEP (README) |
|---|---|
| factory runs — bounded, durable, cancellable | ralph-loop lane — bounded iterations, 3-strike stop |
| deterministic verification gates | TDD + review gates before anything ships |
| patch + evidence artifacts | build ledger + per-run records |

## What runs on this VM

Built and verified 2026-10-18 from the pinned commit (plan Tasks 1–3): `make build` (Go 1.27.2) and `make test-unit` (20/20) — green. `make lint` — Go portions (gofmt, `go vet ./...`) clean; the shellcheck step is blocked on this VM (no verifiable shellcheck source), so `make lint` as a whole stays red here. `factory init` / `config validate` / `doctor` exercised in scratch against placeholder endpoints.

Not available here: Temporal, a CubeSandbox deployment, Docker, PostgreSQL — so `make test-integration`, `make temporal-up`, and any live `factory run` are out of scope. The web UI was not built on this VM (Node 24.20.0 installed; the frontend build requires Node 26.12.0).

## Fail-closed caveat (Task 4 finding)

`factory init` ships `hardening.acknowledge_open_egress = true` — fresh installs start with open egress acknowledged, so the documented fail-closed posture is opt-out, not opt-in (`doctor` reports it as WARN, not FAIL). A production install must explicitly set `acknowledge_open_egress = false` with every `[egress]` policy at `allow_internet = false`; the factory then refuses to start unless the boundary is actually closed.

`factory config validate` is schema-only: it passes on placeholder endpoints. Reachability is `factory doctor`'s job — "valid" does not mean "reachable".

## Design records

7 ADRs (0001–0007; the directory holds two `0001` files) at [reference/esf/docs/adr/](../reference/esf/docs/adr/): CubeSandbox as execution fabric, Temporal for durable workflows, agent-harness abstraction, deterministic verification, artifact model, control-plane security boundary, defense-in-depth.
