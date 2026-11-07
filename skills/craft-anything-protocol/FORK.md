# FORK — craft-anything-protocol

This skill's **structure** is adapted from a third-party source. Its text is AEP-authored; it is not the upstream project's skill (Craft Anything ships no protocol skill) and no upstream text is copied into it.

- **Source origin:** storytold/craft-anything — the Study tooling surface (tool taxonomy) and evidence-record discipline (confidence / coverage / limitations, summary-first consumption), taken from the project's docs and tool surface.
- **Origin version / pin:** pin `2e4afc535cebb6ee556c5ea3f6b4e454487853f9` of pratik-saptarshi/craft-anything (≈ v0.3.0 + 73 main commits; upstream latest release at adoption: v0.5.0, 2026-11-06). The pinned tree is vendored in AEP as `reference/craft-anything/` (PR #106), which is the citable source for the adapted structure.
- **Fork version:** 3 (v1: first marked fork version, 2026-11-07; v2: claim-verification amendment, 2026-11-07; v3: Phase 3 routing-consistency edit, 2026-11-07)
- **Internal marker:** `fork_of` + `fork_version: 3` in SKILL.md frontmatter.

## Local changes

- 2026-11-07 — **Fork adoption (adoption plan v2.1, Phase 2; Gate 0 ruled Branch B):** original protocol text written for AEP around the adapted structure. What is adapted: the Study surface's taxonomy as a routing/reference frame, and the evidence-record shape (confidence, coverage, limitations; summary-first, paged). What is AEP-side construction, not upstream: the routing table's disjoint protocol predicate, the clean-room/Deep posture mechanism (Decision D5 — ruling sentence plus the Gate-0-ratified basis requirement), the AEP-side claim-verification step (explicitly not upstream's Check, which is Build-coupled and not adopted), the advisory-honesty sentence, and the exit criteria.
- 2026-11-07 — **Claim-verification amendment (Codex P2, PR #108):** claim-verification step 2 amended — cross-verification surfaces are now posture-keyed; under clean-room posture, independently collected black-box behavioral records qualify, and internals records (REA/Ghidra) must not be produced to satisfy verification. Fork version bumped to 2.

- 2026-11-07 — **Phase 3 routing consistency (adoption plan v2.1):** the Routing section now states that its table is shared byte-identical with the `reverse_engineering` skill, which gains the same table plus the disjoint-predicate and dedup statements; no protocol substance changed. `fork_version` bumped to 3 per the fork-versioning scheme.
