# Skills

Executable methodology for the autonomous engineering platform. These are the skill definitions the agent loads to perform structured work — debugging, planning, review, research, and the Ralph autonomous loop.

## Environment

Skills assume the workspace layout under `~/workspace/` (e.g. `~/workspace/ralph/backlog.md`, `~/workspace/custom-connectors/`). Paths are environment conventions, not hardcoded secrets.

Repository conventions take precedence: where a skill's workflow conflicts with the repo's `AGENTS.md` — branch naming (`type/scope-short-description`), the protected pull-request flow, required conversation resolution, Conventional Commits — `AGENTS.md` wins. Skills are vendored for their reusable mechanics, not their upstream repo's release or merge rituals.

The 28 paperthin skills are distributed under the upstream MIT license; its copyright and permission notices are vendored alongside them in `skills/paperthin/` (`LICENSE`, `NOTICE`).

The Source column names pratik-saptarshi forks (default branch `develop`) wherever a fork exists; each fork mirrors its upstream, and the original upstream license and attribution remain in the skill's own `LICENSE`/`NOTICE` files.

## Skills

| Skill | Source | License | Notes |
|---|---|---|---|
| agent_operations | pratik-saptarshi/12-factor-agents | CC BY-SA 4.0 | |
| aim | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| archify | pratik-saptarshi/archify | MIT | Vendored verbatim (25cf370); needs ARCHIFY_CHROME env for browser-check gate |
| autobahn | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| brainstorming | pratik-saptarshi/superpowers | MIT | |
| catchup | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| code_explorer | pratik-saptarshi/fastcontext-agent-tools | MIT | Methodology only; upstream package uninstallable |
| debloat | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| dedash | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| delegate_code_review | pratik-saptarshi/open-code-review | Apache-2.0 | Delegation mode; needs LLM key for full review |
| detool | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| dispatching-parallel-agents | pratik-saptarshi/superpowers | MIT | |
| egm-bootstrap | pratik-saptarshi/elephant-goldfish-model | Apache-2.0 | Vendored as bundle (e9e1f06a); wrapper with repo-relative paths |
| egm-brainstorm | pratik-saptarshi/elephant-goldfish-model | Apache-2.0 | Vendored as bundle (e9e1f06a); wrapper with repo-relative paths |
| egm-draft | pratik-saptarshi/elephant-goldfish-model | Apache-2.0 | Vendored as bundle (e9e1f06a); wrapper with repo-relative paths |
| egm-drift-report | pratik-saptarshi/elephant-goldfish-model | Apache-2.0 | Vendored as bundle (e9e1f06a); wrapper with repo-relative paths |
| egm-resolve | pratik-saptarshi/elephant-goldfish-model | Apache-2.0 | Vendored as bundle (e9e1f06a); wrapper with repo-relative paths |
| egm-review | pratik-saptarshi/elephant-goldfish-model | Apache-2.0 | Vendored as bundle (e9e1f06a); wrapper with repo-relative paths |
| egm-review-loop | pratik-saptarshi/elephant-goldfish-model | Apache-2.0 | Vendored as bundle (e9e1f06a); wrapper with repo-relative paths |
| executing-plans | pratik-saptarshi/superpowers | MIT | Extended locally with git-conventions bullet |
| factchk | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| feature-pr-pipeline | Authored locally | MIT | Standard feature-to-PR workflow: plan, subagent-driven TDD, independent review, hygiene, PR with CI and review-comment gating |
| feynman | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| grilling | pratik-saptarshi/skills | MIT | |
| hate | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| macrothink | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| mandela | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| modelchk | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| nba | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| neurogenesis_teams | pratik-saptarshi/NeuroGenesis | — | |
| neurostrata_memory | Distilled locally from NeuroStrata docs | MIT | Custom wiring: retrieval before / inscription after loop iterations |
| overnight-parallel-lanes | Authored locally | MIT | Unattended parallel-run setup: isolated worktree per lane, parallel workers, independent reviewers, explicit stop conditions |
| plan_review_integrator | pratik-saptarshi/opencode-rountable-review | MIT | |
| plannotator-gate | Authored locally | MIT | Mechanical plan-approval gate over the pinned Plannotator tool: owner reviews and annotates plans, decision archive preserved; pattern in ops/tool-adoption/ |
| plannotator-inbox | Authored locally | MIT | Asynchronous owner decision queue over the Plannotator Inbox: batched rulings routed back to the asking session; pattern in ops/tool-adoption/ |
| prism | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| product-refinement-loop | Created locally | MIT | Distilled from 2026-10-18 profile-decisions refinement |
| prototype | pratik-saptarshi/skills | MIT | |
| ralph_loop | pratik-saptarshi/ralph, heavily refined locally | MIT | Added: Conventional Commits conventions, on-demand daemon lifecycle, independent verifier rule |
| re0 | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| re0-git | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| re0-loop | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| re0-memo | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| re0-merge | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| re0-plan | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| re0-release | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62); upstream paperthin release workflow — requires paperthin repo surfaces (plugin.json, docs/readme/, scripts/catalog.cjs, package.json), not directly runnable here |
| re0-work | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| readchk | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| receiving-review | pratik-saptarshi/superpowers | MIT | |
| recurring-workflows | pratik-saptarshi/skills | MIT | |
| reorder | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| requesting-review | pratik-saptarshi/superpowers | MIT | |
| research | pratik-saptarshi/skills | MIT | |
| reverse_engineering | pratik-saptarshi/rea | MIT | |
| roundtable_review | pratik-saptarshi/opencode-rountable-review | MIT | |
| scrubbing-public-tree | Authored locally | MIT | Pre-publish hygiene for agent-built trees: relocate process docs, scrub machine paths and identities |
| self_test_gym | pratik-saptarshi/NeuroPlasticity | — | Native binary not built (needs cargo + Podman) |
| shower | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| sip | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| ssotize | pratik-saptarshi/paperthin | MIT | Vendored verbatim (7d5dc62) |
| subagent-driven-development | pratik-saptarshi/superpowers | MIT | |
| systematic-debugging | pratik-saptarshi/superpowers | MIT | Extended locally: inscribes root causes to NeuroStrata |
| teach | pratik-saptarshi/skills | MIT | |
| test-driven-development | pratik-saptarshi/superpowers | MIT | |
| to-questionnaire | pratik-saptarshi/skills | MIT | |
| verification-before-completion | pratik-saptarshi/superpowers | MIT | |
| writing-articles | pratik-saptarshi/skills | MIT | |
| writing-for-agents | pratik-saptarshi/skills | MIT | |
| writing-plans | pratik-saptarshi/superpowers | MIT | |
| writing-skills | pratik-saptarshi/superpowers | MIT | |

"—" means no upstream license file was found at install time; treat as all-rights-reserved upstream until verified.
