# AEP Authority Index — hand-built prototype (Phase 0, G-P11)

*Descriptive, not authoritative — the surfaces listed are the authority; this
page is a map. Extracted 2026-11-13. [GEN] = mechanically generatable from
the named source; [PTR] = pointer only (source is prose, runtime state, or
settings UI — a generator lists the pointer, never a paraphrase).*

| # | Surface | Governs | Owner / change path | Source | Kind |
|---|---|---|---|---|---|
| 1 | Branch protection — `develop` | 8 required checks (docs-lint, shell-lint, script-tests, vendor-integrity, skills-freshness, security, go-checks, skills-routing-check), conversation resolution, enforce_admins ON, no force-push/deletions. **No required approving reviews at extraction time.** | Repo admin (owner) via GitHub settings | GitHub API `branches/develop/protection` | GEN |
| 2 | Branch protection — `main` | Same 8 checks; enforce_admins OFF (promotion merges by the owner); no required approving reviews at extraction time | Repo admin via GitHub settings; main changes only by manual promotion from develop | GitHub API `branches/main/protection` | GEN |
| 3 | Ruleset `aep-default-branch-guard` (default branch) | Branch deletion + force-push blocked on develop | Repo admin via GitHub rulesets | GitHub API `rulesets/26571395` | GEN |
| 4 | Ruleset `default-set` (default branch) | Deletion + force-push blocked; CodeQL code-scanning gate (errors / security high+); code-quality gate (errors); strict required status checks; required linear history | Repo admin via GitHub rulesets | GitHub API `rulesets/26916648` | GEN |
| 5 | CI workflows | `ci.yml` (the 8 checks), `dependency-review.yml`, `secret-scan.yml`, `actionlint.yml` | PR to develop | `.github/workflows/` | GEN |
| 6 | ghg gateway policy | Per-bucket caps: core 3500/h, graphql 3500/h, search 20/min, code_search 9/min, content 40/min + 300/h; mutating-call classification sets; per-actor budget ledger. Runtime override: `GHG_LIMITS_JSON` env / state dir | PR to develop for `tools/ghg/ghg.py`; override is operator runtime state | `tools/ghg/ghg.py` (AST) + runtime state | GEN + PTR (override) |
| 7 | Launch policy `policy.data` | 25 sensitive-path deny patterns + 6 env-scrub tokens binding lane launches; hash-bound to the committed blob at claim time by lane-coord.sh | PR to develop | `scripts/policy.data` | GEN |
| 8 | Boot gate | Preflight for autonomous runs (binaries, daemon, guards, gh-auth, policy). **Invocation coverage: 0% of launch paths (G-P6 census)** — the gate defines the preflight; nothing operational invokes it | PR to develop | `scripts/boot-gate.sh`; census in `../g-p6/census.md` | GEN + PTR (census) |
| 9 | Skills sync governance | 98 skills in sync scope; 385 manifest entries pinning synced content; freshness enforced in CI | PR to develop (scope amendments are owner-ruled) | `.github/skills-sync-scope.txt`, `.github/skills-manifest.sha256`, `scripts/check_skills_manifest.py` | GEN |
| 10 | SkillSpector baselines | Per-skill security-scan dispositions (13 baseline files) gating skill changes | PR to develop | `skillspector-baselines/` | GEN |
| 11 | Vendor manifests | 12 vendored-tree pins (esf, neurostrata, docs-mcp-server, harness2, …); vendor-integrity CI check; trees change only by re-vendor | Re-vendor PR to develop (fork-first rule) | `.github/vendor-*.sha256` | GEN |
| 12 | Dependabot | Version updates scoped to skills/archify (npm) only; vendored trees deliberately absent. Security updates governed by a repo Settings toggle, not this file | PR to develop; toggle is owner-only settings | `.github/dependabot.yml` + Settings | GEN + PTR (toggle) |
| 13 | CODEOWNERS | Review ownership — 1 effective rule line | PR to develop | `.github/CODEOWNERS` | GEN |
| 14 | Procedural standing rules | Per-PR merge authorisation (owner's word per PR); deletion rule (explicit confirmation + 1-hour delay + reconfirmation); manual-promotion-only releases; fork-first filing venue rule | The owner, in chat; recorded in AGENTS.md / lane charters | Prose — no machine source | PTR |
| 15 | Harness runtime permissions + NeuroStrata guard namespace | Tool-call approval system governing agent sessions; standing guard rules for memory (checked, not defined, by boot-gate) | Runtime / daemon state, outside the repo | Runtime APIs | PTR |

Generation feasibility: 11 of 15 rows fully generatable from an API or a
parseable file; rows 6/8/12 generatable with a pointer component; rows
14–15 pointer-only by nature. No row requires restating a surface's
contents — each links its living source.
