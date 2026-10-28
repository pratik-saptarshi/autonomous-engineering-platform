# Skills

Executable methodology for the autonomous engineering platform. These are the skill definitions the agent loads to perform structured work — debugging, planning, review, research, and the Ralph autonomous loop.

## Environment

Skills assume the workspace layout under `~/workspace/` (e.g. `~/workspace/ralph/backlog.md`, `~/workspace/custom-connectors/`). Paths are environment conventions, not hardcoded secrets.

Repository conventions take precedence: where a skill's workflow conflicts with the repo's `AGENTS.md` — branch naming (`type/scope-short-description`), the protected pull-request flow, required conversation resolution, Conventional Commits — `AGENTS.md` wins. Skills are vendored for their reusable mechanics, not their upstream repo's release or merge rituals.

The 28 paperthin skills are distributed under the upstream MIT license; its copyright and permission notices are vendored alongside them in `skills/paperthin/` (`LICENSE`, `NOTICE`).

## Skills

| Skill | Source | License | Notes |
|---|---|---|---|
| agent_operations | humanlayer/12-factor-agents | CC BY-SA 4.0 | |
| aim | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| archify | tt-a1i/archify | MIT | Vendored verbatim (25cf370); needs ARCHIFY_CHROME env for browser-check gate |
| autobahn | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| brainstorming | obra/superpowers | MIT | |
| catchup | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| code_explorer | Jakevin/fastcontext-agent-tools | MIT | Methodology only; upstream package uninstallable |
| debloat | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| dedash | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| delegate_code_review | alibaba/open-code-review | Apache-2.0 | Delegation mode; needs LLM key for full review |
| detool | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| dispatching-parallel-agents | obra/superpowers | MIT | |
| executing-plans | obra/superpowers | MIT | Extended locally with git-conventions bullet |
| factchk | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| feature-pr-pipeline | Authored locally | MIT | Standard feature-to-PR workflow: plan, subagent-driven TDD, independent review, hygiene, PR with CI and review-comment gating |
| feynman | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| grilling | mattpocock/skills | MIT | |
| hate | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| macrothink | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| mandela | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| modelchk | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| nba | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| neurogenesis_teams | Cognilogical/NeuroGenesis | — | |
| neurostrata_memory | Distilled locally from NeuroStrata docs | MIT | Custom wiring: retrieval before / inscription after loop iterations |
| overnight-parallel-lanes | Authored locally | MIT | Unattended parallel-run setup: isolated worktree per lane, parallel workers, independent reviewers, explicit stop conditions |
| plan_review_integrator | pratik-saptarshi/opencode-rountable-review | MIT | |
| prism | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| product-refinement-loop | Created locally | MIT | Distilled from 2026-10-18 profile-decisions refinement |
| prototype | mattpocock/skills | MIT | |
| ralph_loop | zomars/ralph, heavily refined locally | MIT | Added: Conventional Commits conventions, on-demand daemon lifecycle, independent verifier rule |
| re0 | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| re0-git | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| re0-loop | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| re0-memo | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| re0-merge | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| re0-plan | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| re0-release | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62); upstream paperthin release workflow — requires paperthin repo surfaces (plugin.json, docs/readme/, scripts/catalog.cjs, package.json), not directly runnable here |
| re0-upgrade | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62); npx-skills-CLI upgrade flow targets the npm skills CLI, not this repo |
| re0-work | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| readchk | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| receiving-review | obra/superpowers | MIT | |
| recurring-workflows | mattpocock/skills | MIT | |
| reorder | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| requesting-review | obra/superpowers | MIT | |
| research | mattpocock/skills | MIT | |
| reverse_engineering | morluto/rea | MIT | |
| roundtable_review | pratik-saptarshi/opencode-rountable-review | MIT | |
| scrubbing-public-tree | Authored locally | MIT | Pre-publish hygiene for agent-built trees: relocate process docs, scrub machine paths and identities |
| self_test_gym | Cognilogical/NeuroPlasticity | — | Native binary not built (needs cargo + Podman) |
| shower | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| sip | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| skill_ingestion_gate | Authored locally | MIT | Screen third-party skills through the fail-closed security gate before install; decide from full JSON findings, never from layout inference. |
| ssotize | LilMGenius/paperthin | MIT | Vendored verbatim (7d5dc62) |
| subagent-driven-development | obra/superpowers | MIT | |
| systematic-debugging | obra/superpowers | MIT | Extended locally: inscribes root causes to NeuroStrata |
| teach | mattpocock/skills | MIT | |
| test-driven-development | obra/superpowers | MIT | |
| to-questionnaire | mattpocock/skills | MIT | |
| verification-before-completion | obra/superpowers | MIT | |
| writing-articles | mattpocock/skills | MIT | |
| writing-for-agents | mattpocock/skills | MIT | |
| writing-plans | obra/superpowers | MIT | |
| writing-skills | obra/superpowers | MIT | |

"—" means no upstream license file was found at install time; treat as all-rights-reserved upstream until verified.
