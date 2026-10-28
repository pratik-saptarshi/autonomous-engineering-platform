# Grim-prompter reference

## What it is

jmanico/grim-prompter (vendored from the pratik-saptarshi fork) — a threat-modeling prompt library for AI coding agents. Point a coding agent at a repository and it produces a threat model traced to the code: 36 architecture workflows, each in a quick (single-prompt) form and a deep six-stage form (scope and evidence, system model, threat analysis, challenge and consolidation, treatment and validation, report and handoff), plus 29 method prompts (STRIDE per element/interaction, PASTA, LINDDUN GO/PRO, STPA(-Sec), attack trees and graphs, MITRE ATT&CK/CAPEC/ATLAS enrichment, CVSS, DREAD, and others). A single runbook is the operating contract for every prompt: read-only inspection under a hardened Git invocation, writes only inside a per-run folder, and stage handoffs through a cumulative JSON envelope with a Markdown companion. The tree is pure Markdown — no executable code, no scripts, no test suite.

Vendored snapshot: [PROVENANCE.md](../reference/grim-prompter/PROVENANCE.md) — fork `https://github.com/pratik-saptarshi/grim-prompter` at `076ec0d32c9eec0e09bfdee22b57121f49b26022` (2026-10-28, MIT). Upstream: `https://github.com/jmanico/grim-prompter`.

## Mapping to the AEP loop

| grim-prompter | AEP (this environment) |
|---|---|
| evidence records typed by kind, each with a `path:start-end` locator; unknowns carried as explicit gaps | findings and claims grounded in file/line evidence; no silent gaps |
| every collection at every handoff carries records or an explicit coverage disposition (`assessed` / `not_applicable` / `not_assessed`) | deterministic coverage gates; no silent skips |
| a threat stays a design hypothesis until an implementation or execution observation supports more; treatments stay proposed, verification stays `not_run` | verdict discipline from the audit-adoption work: no severity or confirmation on unvalidated records |
| stage 03 challenges and consolidates the stage 02 analysis before treatment is planned | independent reviewer / challenger pass before anything ships |

## Where it differs from the vendored security-audit skill

The security-audit skill hunts implementation vulnerabilities in code and ships two Node validators with tests. Grim-prompter works one layer up: design-level threats against an architecture, with conformance enforced by the prompts alone — no validator ships in the tree, so a structurally valid artifact is not proof a claim is true (its artifact contract says so itself). Its `deep/agentic-ai` chain and tool/credential-boundary reference model MCP tool-to-credential mapping, shared-token blast radius, and tool-description poisoning — a lens none of the other vendored trees provide.

## Maturity note

Upstream's initial release was 2026-10-28, the day this snapshot was taken; the whole history at the pin is 7 commits by a single author, with no releases. Expect early churn and evaluate re-vendoring sooner than for the older snapshots.

## What runs on this VM

Nothing executes from the vendored tree. The snapshot is a study reference for threat-modeling method — the architecture workflows, the method library, the evidence/coverage discipline, and the agentic-AI credential-boundary modeling are the parts AEP borrows. An actual threat-model run would execute from a live checkout of the fork, not from `reference/`.

## Agent-rules caveat

The snapshot is an instruction library addressed to whatever agent runs it, and its `skills/threat-model/SKILL.md` is an agent skill. As vendored reference data it does not govern work in this repository; AEP's own `AGENTS.md` does. The snapshot is never installed, linked into an agent's skill directory, or executed from `reference/`.
