# FORK — avoid-ai-writing

This copy is a **locally modified fork** of a third-party skill. It is not the upstream original.

- **Source origin:** conorbronsdon/avoid-ai-writing — <https://github.com/conorbronsdon/avoid-ai-writing>
- **Origin version / pin:** v3.39.0, commit cd5573a185f3ab468b094fc2cf2fa193fcaeaf53 (imported 2026-11-23 with full upstream history). Origin `version: 3.39.0` in SKILL.md frontmatter is the upstream version and is kept unchanged.
- **Fork version:** 2
- **Internal marker:** `fork_of` + `fork_version: 2` in SKILL.md frontmatter.
- **License:** MIT (see LICENSE in this directory). Upstream attribution (badges, homepage, npm metadata pointing at conorbronsdon/avoid-ai-writing, NOTICE) is kept intact.

## Branch model

- `main` is the pristine upstream mirror — no fork commits land on it.
- `develop` is the fork's working and default branch; it carries the amendments below and is what gets vendored into AEP (`reference/avoid-ai-writing/`).

## Local changes

- 2026-11-23 — Mirror established from upstream v3.39.0 at the pin above; `develop` branch created from `main` and set as the default branch to carry the fork amendments. Evaluation: 2026-11-23 avoid-ai-writing vs humanizers skill-adoption evaluation (AEP vendored-repo maintenance lane), verdict adopt-scoped-alongside as detect-only tooling.
- 2026-11-23 — Amendment 1 (detect-only scoping): rewrote the SKILL.md frontmatter description to the detect/audit intent, so this skill cannot trigger on generic rewrite or humanize requests — those belong to the separate `humanizer` skill, and ASD-STE100 / Simplified Technical English requests to `ste80-humanizer`. Added a "Local scope" section after the introduction that disables the `rewrite` and `edit` modes in this fork (detect is the only enabled mode and the default), carries over the evidence-bearing-artifact exclusion from the incumbent forks (receipts and sealed records, reviewer/verification reports, decision records, NeuroStrata inscriptions — no skill applies to those), and annotates the Modes and Invocation sections accordingly. The deterministic detector (`detector/`), the gate CLI (`bin/`), and the eval suites are untouched and remain fully functional; generated artifacts were regenerated with the repo's own sync scripts so no derived copy drifts from the amended SKILL.md.
- 2026-11-23 — Amendment 2 (cursor-rules trigger fix): independent review of the first vendoring found that the generated Cursor rule's frontmatter description — hard-coded in `scripts/sync-cursor-rules.sh`, not derived from SKILL.md — still carried the upstream rewrite trigger ("Audit and rewrite content… Activate whenever editing prose-heavy files"). Rewrote that generator string to the same detect-only wording (audit/report, never rewrite or edit) and regenerated the rule. No other surface carried the un-amended description; README's quoted frontmatter snippet is upstream documentation prose, not an activation surface, and is left as-is. fork_version 2.

Bump `fork_version` and append a dated line here whenever this copy is edited locally.
