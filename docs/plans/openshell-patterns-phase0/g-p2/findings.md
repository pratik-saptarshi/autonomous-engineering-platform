# G-P2 — Power-differ historical replay: findings

Gate (plan §2, pre-registered): prototype power-differ replayed over the last 20
merged policy-affecting PRs + 3 seeded escalations. **Pass:** catches all 3 seeds
AND at least 1 real delta human review missed. **Kill:** adds nothing beyond the
text diff reviewers already read.

## Method

- Prototype: `power_differ_prototype.py` (stdlib-only, throwaway). Model scope,
  stated in the tool and here: `scripts/policy.data` deny-sets (removal from a
  deny-set = newly allowed), `tools/ghg/ghg.py` `DEFAULT_LIMITS` caps +
  mutating-classification sets (AST-extracted), `.github/skills-sync-scope.txt`
  set deltas, and `skills/**` file-set deltas (new skill dir / added file =
  newly allowed surface; removals = newly denied). SKILL.md *content* changes
  in surviving skills are counted but declared not mechanically classifiable.
  Any ghg.py change with no modelled delta is reported as an explicit
  "changed, modelled power unchanged" note, never as silence.
- Universe: the 20 most recent merged PRs on `develop` whose diff touches at
  least one policy-bearing path (`scripts/policy.data`, `tools/ghg/ghg.py`,
  `.github/skills-sync-scope.txt`, `.github/skills-manifest.sha256`,
  `skills/**`): #141, #136, #132, #131, #84, #85, #83, #80, #76, #67, #58,
  #42, #43, #49, #46, #40, #32, #27, #23, #9.
  **Universe caveat:** the strict artefact subset (policy.data + ghg.py +
  scope + manifest only) contains just 9 PRs in the repo's entire history, so
  the plan's sample of 20 is only reachable by including skill-content PRs.
  Results are broken out by tier below; nothing was silently redefined.
- Missed-delta test: for each PR with a non-empty newly-allowed set, the full
  human record (title, body, review bodies, issue comments, and — for the
  decisive PR — line-level review comments including their anchored paths,
  fetched via the API) was searched for each item by full path, skill name,
  or bare filename. Any of the three counts as "mentioned" (a generous test).

## Seeds (into copies of the current artefacts)

| Seed | Result |
|---|---|
| S1 new credentialed host — new ghg bucket `metadata_creds` | **caught** (newly allowed call class) |
| S2 new method on an allowed host — `merge` leaves `_MUTATING_SUBCOMMANDS` | **caught** (escapes mutating classification) |
| S3 metadata-endpoint reach — `*/.config/gcloud{,/*}` leaves the policy.data deny-set | **caught** (both patterns reported newly allowed) |

Raw output: `seeds-output.json` (reproduce: `power_differ_prototype.py seeds`).

## Replay results (per-PR JSON in `replay/`)

- Genuine grants produce correct non-empty deltas: #84 (+36: 18 skills enter
  scope + tree), #58 (+40), #9 (+29), #141 (+8), #23 (+5), #132 (+2), #27 (+1).
- Non-grants produce empty deltas: #136 (ghg telemetry — differ reports the
  explicit note "ghg.py changed but modelled power (caps + classification)
  unchanged"), dependabot PRs #80/#49/#46 (empty), #76/#67 (syncs with no
  file-set change; SKILL.md content changes counted as unclassifiable).
- Removals produce denied-only deltas in the correct direction: #85 (−2,
  re0-upgrade leaves scope + tree), #32 (−5, archify self-update files removed).
- Creations are reported as creations, not deltas: #40 (policy.data), #43
  (ghg.py), #83 (scope file).
- #131 (+32) is the main→develop union merge; its delta is merge mechanics,
  not a reviewed grant, and is excluded from the missed-delta evidence.

## The missed real delta — PR #58

PR #58 ("chore(skills): sync vendored skill copies to the live skills",
merged 2026-10-26) has 40 differ-reported newly-allowed items. Under the
generous mention test, **35 of 40 appear nowhere in the PR's human record**
(body, 5 reviews, issue comments, and line-level review comments all
searched). The body aggregates ("55 files written: 16 modified, 39 added")
and names one added file (`skills/prototype/LOGIC.md`, for a lint note);
Codex line comments touched `helper.js` and `start-server.sh` during fix
waves. Never mentioned in any form:

- the `brainstorming` skill acquiring a runnable local server —
  `scripts/server.cjs`, `scripts/stop-server.sh`,
  `scripts/frame-template.html`, `visual-companion.md`,
  `builder-check-prompt.md` (7 files; the skill's name itself never appears
  in the record);
- `executing-plans` acquiring executable `scripts/task-start` /
  `scripts/task-done`;
- 27 further added files across `systematic-debugging`, `writing-skills`,
  `subagent-driven-development`, `writing-for-agents`,
  `test-driven-development`, `grilling`, `research`, `prototype`.

Control: the same test on PR #84 finds 0/36 unmentioned (its body enumerated
every grant) — the test is not trivially failed by every PR, and #141/#132's
grants were likewise fully acknowledged in their records.

## Scope observation (material for Phase 1)

Within the strict-9 tier, every grant was either a creation or was fully
enumerated by its author (#84, #141, #132) — the differ would have added a
mechanical checklist, not a catch. The catch came from the **skills tree**,
the artefact class R4's Phase 1 scoping deferred ("v1 scoped to policy.data
+ ghg cap tables only; skill manifests deferred"). As scoped, the Phase 1
build would not have caught the #58 delta. The gate passes on the plan's
criteria as written (the replay universe includes skill manifests), but the
Phase 1 scope decision should be re-examined against this evidence before
building.

## Verdict: **PASS**

All 3 seeds caught; replay deltas correct in direction and emptiness across
grants, non-grants, removals, and creations; ≥1 real delta human review
missed (PR #58, 35 items). Per the plan, Phase 1 (the power-differ) has
earned its build — with the scope observation above attached.
