# FORK — ste80-humanizer

This copy is a **locally modified fork** of a third-party skill. It is not the upstream original.

- **Source origin:** Dodaios/ste80-humanizer — <https://github.com/Dodaios/ste80-humanizer>
- **Origin version / pin:** v4.0.0, commit ace4484da2d81dda97861e004c37c0a2e93896d1 (2026-11-18). Origin `metadata.version: "4.0.0"` in SKILL.md is the upstream version and is kept unchanged.
- **Fork version:** 2
- **Internal marker:** `fork_of` + `fork_version: 2` in SKILL.md frontmatter.
- **License:** MIT (see LICENSE in this directory).

## Local changes

- 2026-11-19 — Fork taken verbatim from upstream v4.0.0 at the pin above; `develop` branch established as the fork's working and default branch to carry the AEP inclusion amendments below. Evaluation: 2026-11-19 ste80-humanizer AEP inclusion evaluation (AEP vendored-repo maintenance lane).
- 2026-11-19 — Amendment 1 (scope exclusion): added a "Local scope" section after the introduction excluding evidence-bearing artifacts (receipts and sealed records, reviewer/verification reports, decision records, NeuroStrata inscriptions), ported from the blader/humanizer fork's Amendment 1 — several patterns (§9, §25) and Pass 2 structure rules (S1/S2 sentence splitting, S9 modal handling) would strip load-bearing hedging, signposting, and proof structure from those texts. The section explicitly subordinates Pass 2 to the exclusion. The File mode paragraph also gains the blader fork's Amendment 2 rule (read the file's current contents in full before editing; report section coverage afterward).
- 2026-11-19 — Amendment 2 (trigger narrowing): rewrote the frontmatter description to target the STE/plain-structure intent (ASD-STE100, Simplified Technical English, plain structured technical text) and to defer generic humanize/de-AI requests to the separate `humanizer` skill, so the two skills do not compete for the same trigger phrases.
- 2026-11-19 — Correction: removed a machine-specific file path from this FORK.md's evaluation citation before first publication; no skill content changed.
- 2026-11-19 — Amendment 3 (AEP markdownlint accommodations): whitespace/table-style fixes, angle-bracket URLs, and scoped MD024 disable comments so the skill passes AEP's repo-wide markdownlint; no wording or rule content changed. fork_version 2.

Bump `fork_version` and append a dated line here whenever this copy is edited locally.
