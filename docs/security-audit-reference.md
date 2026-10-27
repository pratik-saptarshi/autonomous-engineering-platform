# Security-audit skill reference

## What it is

cloudflare/security-audit-skill (vendored from the pratik-saptarshi fork) — a coding-agent skill that turns an agent into a security auditor. It orchestrates isolated agents through a six-phase audit: reconnaissance, coverage-led hunting, candidate validation, structured findings, independent record verification, and target-neutral reporting. Per-surface topic guides (web protocol and auth, client-side, cloud and deployment, supply chain and release, AI and LLM, memory safety, protocols/RPC/messaging, data isolation, resource exhaustion, desktop/mobile and local IPC) sit alongside the core `SKILL.md`, a JSON report schema (`report-schema.json`), and two Node validators. This is the skill that seeded Cloudflare's vulnerability discovery harness.

Vendored snapshot: [PROVENANCE.md](../reference/security-audit-skill/PROVENANCE.md) — fork `https://github.com/pratik-saptarshi/security-audit-skill` at `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8` (2026-10-26, MIT). Upstream: `https://github.com/cloudflare/security-audit-skill`.

## Mapping to the AEP loop

| security-audit | AEP (this environment) |
|---|---|
| coverage ledger — every surface hunted or explicitly accounted for | deterministic coverage gates; no silent skips |
| every candidate goes to a fresh verifier that tries to disprove it | independent reviewer per task; findings confirmed or refuted on evidence |
| findings validated against `report-schema.json` before reporting | sealed receipts + mechanical verification before anything ships |
| target-neutral report derived from the verified records | reports generated from the build ledger, not from agent prose |

## What runs on this VM

Nothing executes from the vendored tree. The snapshot is a study reference for audit methodology — the hunting classes and the validate-before-report discipline are the parts AEP borrows. The two validators (`validate-coverage-ledger.cjs`, `validate-findings.cjs`) and their tests (`validate-*.test.cjs`) ship in the tree byte-identical but are not wired into this repo's CI, the same treatment as the other vendored trees. An actual audit run would execute from a live checkout of the fork, not from `reference/`.

## Agent-rules caveat

The snapshot's `SKILL.md` is an agent skill addressed to whatever agent loads it to run an audit. As vendored reference data it does not govern work in this repository; AEP's own `AGENTS.md` does.
