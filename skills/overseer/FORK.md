# FORK — overseer

This copy is a **locally modified fork** of a third-party skill. It is not the upstream original.

- **Source origin:** pratik-saptarshi/opencode-rountable-review, `skills/overseer` (upstream author: wan-huiyan)
- **Origin version / pin:** Imported 2026-10-13. Diff baseline: local clone ~/workspace/repos/opencode-rountable-review at b91f263. Origin `version: 3.2.0` in SKILL.md is the upstream version and is kept unchanged.
- **Fork version:** 1 (first marked fork version, 2026-11-04)
- **Internal marker:** `fork_of` + `fork_version: 1` in SKILL.md frontmatter and skill.yaml.

## Local changes

- PR #84 round 2 (2026-11) — `{skill_dir}` definition corrected to the skill root; Phase 15.3 section in references/prompt-templates.md pointed at SKILL.md's section (read in full + faithful summary).
- PR #84 round 6 (2026-11) — Phase 13.5 gate: conditional annotation making `phase_11_severity_verification.md` required only when Phase 11 ran (SKILL.md:956–960 in the shipped copy).
- 2026-11-04 — Panel-P1 fix pass, Task 4 (D6): per-phase required-section lists for the Phase 13.5 gate added to references/prompt-templates.md (the file the gate points to), with match semantics (operative noun phrase, case-insensitive) and explicit non-coverage; Phase 5's list is derived thin because its sources mandate content, not headers — a literal gate run false-fails honest Phase 5 files, recorded in PR #84's panel-P1 addendum.
- 2026-11-04 — Fork marking added (this file + `fork_of`/`fork_version` markers); no content change in this step.

Bump `fork_version` and append a dated line here whenever this copy is edited locally.
