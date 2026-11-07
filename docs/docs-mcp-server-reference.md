# Docs-mcp-server reference

## What it is

pratik-saptarshi/docs-mcp-server (fork of arabold/docs-mcp-server, default branch `develop`) — "Grounded Docs MCP Server": a TypeScript/Node server that fetches documentation from websites, GitHub repositories, npm, PyPI, and local folders, indexes it (scraping, chunking, embedding, and a document store, with an `openspec/` design record in-tree), and serves version-matched search over the Model Context Protocol, a CLI, and a web UI. The design goal is that a coding assistant answers from the documentation for the library versions actually in use rather than from model memory — an open-source alternative to Context7-style hosted indexes, self-hosted and source-agnostic.

Vendored snapshot: [PROVENANCE.md](../reference/docs-mcp-server/PROVENANCE.md) — fork `https://github.com/pratik-saptarshi/docs-mcp-server`, its `develop` head at `4e35baa7e82c3ec447405c48a301c8a4185e715f` (v3.4.1; snapshot 2026-10-31, MIT). Upstream: `https://github.com/arabold/docs-mcp-server`. The fork follows the fork-first pattern: `develop` is its default branch and the vendoring base, `main` stays a pristine upstream mirror, and at this pin the two are identical.

## Mapping to the AEP loop

| docs-mcp-server | AEP (this environment) |
|---|---|
| version-matched documentation index: answers grounded in the exact library version in use, not the model's memory of any version | evidence discipline: claims grounded in the checked source at the pinned commit, not in a summary or a recollection |
| fetch → scrape → chunk → embed → store pipeline with per-source refresh | vendored snapshots pinned by sha256 manifest; content changes only by re-vendoring to a new pin |
| one index served over MCP, CLI, and web UI from the same store | NeuroStrata as the single memory store behind every lane, with files as the pointer layer |
| `openspec/` change records kept beside the code they describe | plans, ledgers, and review records kept with the work they govern |

## Where it differs from the other vendored trees

Most vendored trees here are method libraries or the memory daemon itself. This one is a working retrieval server for *external* documentation — the complement to NeuroStrata's *internal* memory: NeuroStrata remembers what this environment learned; docs-mcp-server is a reference design for grounding answers in published documentation at a pinned version. It is also, unlike grim-prompter, executable code with a real test suite (`test/`, `tests/`), which makes its pipeline and store design readable as engineering evidence rather than as prompt method.

## What runs on this VM

Nothing executes from the vendored tree. The snapshot is a study reference — the fetch/index/serve pipeline, the version-matching model, and the MCP surface design are the parts AEP borrows. An actual docs-server run would execute from a live checkout of the fork, not from `reference/`.

## Agent-rules caveat

The snapshot carries the source project's own `AGENTS.md` (Node 22 pin, Biome/commitlint gates, test conventions) addressed to agents working *in that repository*. As vendored reference data it does not govern work in this repository; AEP's own `AGENTS.md` does. The snapshot is never installed, linked, or executed from `reference/`.
