# FORK — plan-review-integrator

This copy is a **locally modified fork** of a third-party skill. It is not the upstream original.

- **Source origin:** pratik-saptarshi/opencode-rountable-review, `skills/plan-review-integrator` (author credit in SKILL.md: nemesis — inspired and updated from wan-huiyan's work)
- **Origin version / pin:** Imported 2026-10-13. Diff baseline: local clone ~/workspace/repos/opencode-rountable-review at b91f263. Origin `version: 2.1.0` in SKILL.md is kept unchanged.
- **Fork version:** 1 (first marked fork version, 2026-11-04)
- **Internal marker:** `fork_of` + `fork_version: 1` in SKILL.md frontmatter and skill.yaml.

## Local changes

- 2026-11-04 — Panel-P1 fix pass, Task 3 (D5a): specialist launch timing reconciled to one timeline — the initiation rule added to the Orchestration Contract (spawns initiate only in contract batches after Phase 5.5 coverage + Phase 6 classification); the Step 4 phase-gate timing grant deleted and replaced with a pointer to the contract; Phase 4 agent-verification re-scoped (flag during Phase 4, verify via post-classification batch); Phase 6.5 pointed at the contract by name and its mini-votes explicitly scoped as a separate mechanism with their own budget; Phase 7's pre-edit batch preserved as a contract batch; Phase 8 re-pointed to consume remaining cap via the contract.
- 2026-11-04 — Fork marking added (this file + `fork_of`/`fork_version` markers); no content change in this step.

Bump `fork_version` and append a dated line here whenever this copy is edited locally.
