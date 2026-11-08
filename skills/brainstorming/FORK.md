# FORK — brainstorming

This copy is a **locally modified fork** of an upstream skill. It is not the upstream original.

- **Source origin:** obra/superpowers — https://github.com/obra/superpowers (MIT), `skills/brainstorming`
- **Origin version / pin:** Imported 2026-10-13 (per skill.yaml). Diff baseline: local clone ~/workspace/repos/superpowers at bb92a77 (release v7.0.0). No per-skill upstream version exists; 7.0.0 is the library release.
- **Fork version:** 1 (first marked fork version, 2026-11-04)
- **Internal marker:** `fork_of` + `fork_version: 1` in SKILL.md frontmatter and skill.yaml.

## Local changes

- 2026-11-04 — Fork marking added (this file + `fork_of`/`fork_version` markers); no content change in this step.
- (pre-marking) SKILL.md is verbatim upstream. Local changes are in scripts/: scripts/start-server.sh carries a local fix (PROJECT_DIR normalized to an absolute path before session paths are derived from it) and scripts/helper.js differs by one line in the choice-event payload. Both differences present at the 2026-11-04 inventory; their exact edit dates were not recorded when made.

Bump `fork_version` and append a dated line here whenever this copy is edited locally.
