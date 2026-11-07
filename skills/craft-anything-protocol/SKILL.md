---
name: craft-anything-protocol
description: Use when a reverse-engineering task requires clean-room posture (the target's inspection rights are not affirmatively established) or the deliverable is a recreation-oriented evidence record. This is the Craft Anything Study-surface discipline and AEP-side claim-verification as a governed protocol over the existing REA/Ghidra bench — a protocol, not a runtime; the engine is not installed. For ordinary analysis of a binary or package you may inspect, use the reverse_engineering skill instead.
fork_of: "storytold/craft-anything — Study tooling surface and evidence-record discipline (via pratik-saptarshi/craft-anything, pin 2e4afc5)"
fork_version: 2
---

# Craft Anything Protocol

## Status — read first

engine not installed in this environment; this protocol governs REA/Ghidra evidence work under clean-room discipline until runtime authorization.

Branch B evaluation note (2026-11-07): the published engine, craft-anything v0.5.0, was evaluated on this VM on 2026-11-07 (report: goals/autonomous-code-defense-factory/files/2026-11-07-craft-anything-runtime-evaluation.html) and returned a verdict of viable-with-conditions. That evaluation install is **not** adoption: no MCP registration, no routing change, and no part of this protocol invokes the engine. The engine's Ghidra Deep locator defect found by the evaluation is filed as pratik-saptarshi/craft-anything#1 and storytold/craft-anything#1084. Status language for this adoption is "protocol adopted; engine not installed" — never "craft-anything adopted."

This skill is not written as if the engine were runnable here. It adopts three things from Craft Anything: the Study tooling surface as a pinned reference, its evidence-record discipline, and its clean-room posture as governed process — executed with the bench AEP already has.

## Routing — which surface answers which question

This table is shared with the `reverse_engineering` skill; the two copies are kept byte-identical so the surfaces cannot drift apart.

| Question shape | Route | Why |
|---|---|---|
| JS / Electron app structure, module graph, evidence record | REA (`npx -y rea-agents@6.5.0`) | Already pinned, verified, and cheapest. Unchanged. (Applies whenever clean-room posture is not required — see the protocol row's disjoint predicate.) |
| Native binary needing disassembly / decompilation / CFG, where inspection rights are established | Ghidra headless, behind the 2026-10-21 gating rule (cheapest-first ladder, heap-capped, bounded `-analysisTimeoutPerFile`) | Installed and verified. The gating rule stands; this protocol does not loosen it. Posture binds to tool: Ghidra on a target without an established inspection right is out-of-protocol (Decision D5). |
| Clean-room posture is required (inspection rights not affirmatively established), or the deliverable is a recreation-oriented evidence record | Craft Anything protocol — Study-surface discipline + AEP-side claim-verification, executed with REA/Ghidra outputs as evidence sources under the posture the routing decision records | The protocol governs the shape of the work and the evidence. Its verification step is AEP-side claim-verification against the evidence records — not upstream's Check, which operates on Build artifacts and is not adopted. |
| Rebuilding / recreating a target | AEP's own loop | Craft Anything's Build harness is explicitly not adopted. |

The protocol row's predicate is deliberately disjoint from the REA and Ghidra rows: this protocol applies **only** when clean-room posture is required, or when the deliverable is a recreation-oriented evidence record — never merely because an evidence record is wanted (that is REA/Ghidra territory).

Overlap is bounded by one dedup rule: **one evidence record per question**. REA is the producer of record for JS/Electron; the protocol consumes records, it does not commission duplicates.

Tool mechanics — the cheapest-first ladder, the Ghidra gating rule, evidence-record reading — live in the `reverse_engineering` skill. This protocol routes by reference to that skill and does not duplicate its ladder.

## Study-surface discipline

Work under this protocol follows the Study surface's shape, as pinned in the reference snapshot:

- **Evidence records are the unit of work.** Every result is an evidence record carrying **confidence, coverage, and limitations**, consumed **summary-first** and paged — never a raw dump treated as a finding. A claim that does not trace to a record is not reported.
- **Coverage is stated, not implied.** Record what was examined against what exists (the evaluation's records state, for example, examined-vs-total counts); partial coverage is a property of the record, not a footnote added later.
- **Limitations travel with the record.** A record's stated limitations (a fallback engine, register-level output, an unexamined region) are quoted wherever its claims are used.
- **Unknowns are listed, not smoothed over.** The Study surface keeps an explicit unknowns list per investigation; this protocol does the same in the work record.

## Posture — clean-room by default, Deep by right (Decision D5)

Decision D5, verbatim (the ruling sentence):

> Clean-room is the protocol's default posture for any target whose inspection rights are not affirmatively established; Deep requires the right to be named in the work record.

Basis requirement (v2 elaboration, ratified at Gate 0 on 2026-11-07): Deep requires the right **and its basis** (ownership, license, or engagement) to be named in the work record, recorded per target **before** Deep work begins. The basis requirement originates from the adoption panel's Risk condition, not from the ruling itself; it is protocol law by ratification, and is never quoted as part of D5.

The mechanism, not just the prose:

- **Posture binds to tool.** Running Ghidra — or engine-Deep, if a runtime is ever authorized — against a target without an established right is out-of-protocol, whatever the question's shape.
- **Clean-room means black-box-only evidence:** behavior observable from outside the target. Internals of a target without an established right are refused, not sampled.
- **The routing decision records the posture** for each target before work starts, and the claim-verification step below enforces it.

Until a mechanical control exists, this protocol's clean-room guarantee is advisory: it binds the agent's conduct, and no tool enforces it.

No surface may claim a stronger guarantee than that sentence states.

## Claim verification (AEP-side — not upstream's Check)

Verification under this protocol is an AEP-side process run against REA/Ghidra evidence. It is **not** upstream's Check step: upstream verification operates on Build artifacts, the Build harness is not adopted, and no step of this protocol invokes it.

Before any load-bearing claim is reported as a finding:

1. **Work-record check.** Confirm the work record names, for this target, the inspection right and its basis (per D5 above). If either is missing, Deep-derived claims do not proceed — the route reverts to clean-room posture or stops.
2. **Independent cross-verification.** Cross-verify the claim against an independent evidence record (REA or Ghidra) — a second surface, not a re-read of the same record.
3. **Limitations attached.** Report the claim with the confidence, coverage, and limitations of the records it rests on.

## Pinned reference

The Study surface this protocol references is pinned in AEP at `reference/craft-anything/` @ `2e4afc5` (≈ v0.3.0 + 73 main commits; full SHA `2e4afc535cebb6ee556c5ea3f6b4e454487853f9`), vendored by PR #106 under the sha256 vendor-integrity regime, with its disposition and staleness record in that tree's `PROVENANCE.md`. The snapshot is data — reference only; nothing in it is executed from there.

## Non-goals

- No Build harness, and no step that recreates a target under Craft Anything's workflow; recreation is AEP's own loop.
- No upstream Check step, in any form.
- No runtime-invocation instructions: nothing here installs, registers, or calls the craft-anything engine, its CLI, or its MCP server. Runtime adoption requires its own plan and authorization. Known-open item, registered for that runtime plan: if runtime adoption is ever authorized, the decompiler choice — the engine's built-in decompiler vs Ghidra — must be decided there; this protocol takes no position on it.

## Exit criteria

This protocol (with the reference snapshot) is removed via a removal PR owned by the AEP lane coordinator when any of these is evidenced: the protocol has no recorded use across two consecutive quarters (a recorded use is a work record — a lane note, a finding-ledger entry, or a PR — that cites this skill as the governing protocol for a piece of reverse-engineering work); upstream changes its license or brand terms in a way the snapshot cannot satisfy; upstream is abandoned (no release or push for 12 months) and the reference has no recorded use in that period; or a runtime-adoption plan supersedes the protocol outright.

## Sync note

Per the skills-governance rule — AEP is the canonical version of record for skills — the live copy of this skill takes effect in this environment on landing and is verified byte-identical to AEP main after merge.
