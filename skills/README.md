# Skills

Executable methodology for the autonomous engineering platform. These are the skill definitions the agent loads to perform structured work — debugging, planning, review, research, and the Ralph autonomous loop.

## Environment

Skills assume the workspace layout under `~/workspace/` (e.g. `~/workspace/ralph/backlog.md`, `~/workspace/custom-connectors/`). Paths are environment conventions, not hardcoded secrets.

## Skills

| Skill | Source | License | Notes |
|---|---|---|---|
| agent_operations | humanlayer/12-factor-agents | CC BY-SA 4.0 | |
| brainstorming | obra/superpowers | MIT | |
| code_explorer | Jakevin/fastcontext-agent-tools | MIT | Methodology only; upstream package uninstallable |
| delegate_code_review | alibaba/open-code-review | Apache-2.0 | Delegation mode; needs LLM key for full review |
| dispatching-parallel-agents | obra/superpowers | MIT | |
| executing-plans | obra/superpowers | MIT | Extended locally with git-conventions bullet |
| grilling | mattpocock/skills | MIT | |
| neurogenesis_teams | Cognilogical/NeuroGenesis | — | |
| neurostrata_memory | Distilled locally from NeuroStrata docs | — | Custom wiring: retrieval before / inscription after loop iterations |
| plan_review_integrator | pratik-saptarshi/opencode-rountable-review | MIT | |
| product-refinement-loop | Created locally | — | Distilled from 2026-10-18 profile-decisions refinement |
| prototype | mattpocock/skills | MIT | |
| ralph_loop | zomars/ralph, heavily refined locally | MIT | Added: Conventional Commits conventions, on-demand daemon lifecycle, independent verifier rule |
| receiving-review | obra/superpowers | MIT | |
| recurring-workflows | mattpocock/skills | MIT | |
| requesting-review | obra/superpowers | MIT | |
| research | mattpocock/skills | MIT | |
| reverse_engineering | morluto/rea | MIT | |
| roundtable_review | pratik-saptarshi/opencode-rountable-review | MIT | |
| self_test_gym | Cognilogical/NeuroPlasticity | — | Native binary not built (needs cargo + Podman) |
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
