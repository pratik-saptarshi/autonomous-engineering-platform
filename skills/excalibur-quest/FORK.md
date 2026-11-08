# FORK — excalibur-quest

This copy is a **locally modified fork** of an upstream skill. It is not the upstream original.

- **Source origin:** pratik-saptarshi/opencode-rountable-review (MIT), `skills/excalibur-quest`
- **Origin version / pin:** Imported 2026-10-13 (per skill.yaml). Diff baseline: local clone ~/workspace/repos/opencode-rountable-review at b91f263. No upstream version number.
- **Fork version:** 1 (first marked fork version, 2026-11-04)
- **Internal marker:** `fork_of` + `fork_version: 1` in SKILL.md frontmatter and skill.yaml.

## Local changes

- 2026-11-04 — Fork marking added (this file + `fork_of`/`fork_version` markers); no content change in this step.
- (pre-marking) scripts/quest_helper.js extensively modified locally (PR #84 fix rounds 1-9, 2026-11-03/04): shell-injection fix (argv-array execution), atomic JSON store publication with permission preservation, seat reclaim/locking, sync/close TOCTOU re-validation, empty-review fabrication fix. SKILL.md unchanged vs origin at inventory.

Bump `fork_version` and append a dated line here whenever this copy is edited locally.
