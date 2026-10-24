# NeuroStrata reference

## What it is

Cognilogical/NeuroStrata (vendored from the pratik-saptarshi fork) — a local-first MCP memory server for coding agents, written in Rust. One daemon (`neurostrata-mcp`, 127.0.0.1:34343) serves a hierarchical graph/vector memory (SynapticGraph over an embedded LadybugDB store: dense-embedding distance ranking with a capped usage/provenance boost, then bounded graph expansion), a task subsystem with a completion gate (a task reaches `done` only with an extracted memory), and a behavioral-rule guard that validates state-mutating actions before they land.

Vendored snapshot: [PROVENANCE.md](../reference/neurostrata/PROVENANCE.md) — fork `https://github.com/pratik-saptarshi/NeuroStrata` at `219e47de604a283c6fb8d4249db77b9824e35188` (2026-10-24, MIT). Upstream: `https://github.com/Cognilogical/NeuroStrata`.

## Mapping to the AEP loop

| NeuroStrata | AEP (this environment) |
|---|---|
| persistent graph memory across sessions | the memory layer every agent session boots against |
| task gate — `done` requires an extracted lesson | per-task evidence + review gates before anything ships |
| behavioral rules enforced pre-action | standing rules (deletion rule, push authorization) in agent instructions |
| watchdog + idle-reaper lifecycle around the daemon | `scripts/watchdog-backup.sh` + the environment-maintenance crons |

## What runs on this VM

The deployed daemon is **1.9.0**, installed 2026-10-16 from the release tarball (SHA256-verified) to `~/go/bin/neurostrata-mcp`, with its store under `~/.config/NeuroStrata/data/` and the daemon on 127.0.0.1:34343. The vendored snapshot is **1.11.0** — newer than the deployed daemon. The snapshot is a study/build reference; nothing in AEP executes from `reference/neurostrata/`, and vendoring it does not upgrade the daemon.

## Version-skew caveat

Snapshot (1.11.0) ≠ deployed (1.9.0). Anything written against the snapshot's schemas, vocabulary (v6), or CLI surface must be re-checked against the 1.9.0 binary before it is run against the live store.

## Agent-rules caveat

The snapshot carries NeuroStrata's own `AGENTS.md` at its root — operating rules addressed to agents working *on NeuroStrata itself* (its task-tool workflow, its push gate). It is part of the byte-identical snapshot and does not govern work in this repository; AEP's own `AGENTS.md` does.

## Design records

Cognitive architecture: [reference/neurostrata/docs/COGNITIVE_ARCHITECTURE.md](../reference/neurostrata/docs/COGNITIVE_ARCHITECTURE.md). Design notes and verdicts: [reference/neurostrata/docs/designs/](../reference/neurostrata/docs/designs/) and `docs/design-*.md` in the snapshot. The retrieval description in the snapshot README is the corrected one — the CHANGELOG erratum at [reference/neurostrata/CHANGELOG.md](../reference/neurostrata/CHANGELOG.md) records that search is pure vector distance plus evidence boosting, with no BM25/keyword track.
