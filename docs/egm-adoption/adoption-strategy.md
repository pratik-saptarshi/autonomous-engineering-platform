# EGM Adoption Strategy — Autonomous Engineering Platform

**Date:** 2026-11-06 · **Status:** Draft for owner review · **Source:** `google/elephant-goldfish-model` v0.1.1 (Apache-2.0)

## 1. Purpose

Adopt Google's Elephant-Goldfish Model (EGM) — a spec-driven development
plugin for AI coding assistants — into AEP's skill catalog and local
environment, so design-before-implementation becomes a loadable skill rather
than an implicit habit. EGM in one paragraph: one agent (the Elephant) holds context and drafts the design; fresh-context reviewers (Goldfish) audit it against written document standards; a human approves before anything is built. It ships 7 skills, 10 reviewer personas, and 5 document standards — the full verified inventory is in §7. This document covers **technical design and
architecture for two deployment targets**, and is intended to support both:

- **Environment A — general-purpose Linux VM:** a fresh VM with a supported
  coding-assistant harness installed (Muse, Claude Code, Codex, Cursor,
  OpenCode, Antigravity). (Cursor and OpenCode adapters are experimental / unverified upstream.)
- **Environment B — current Muse environment (Environment B):** this VM, where skills live
  in `~/workspace/custom-skills/`, there is no `muse` CLI, and dispatch runs
  through `subagent.spawn`.

Terminology: 'Muse' is the harness/assistant product; '`muse` CLI' is its command-line tool; 'current Muse environment' means Environment B (this VM, which has no `muse` CLI). Actors: 'Owner' is the human user who owns the AEP repo and this environment — the same 'human' in §10.3.2's approval gates — reached by the main agent in chat; the owner rules on open decisions, answers the driver's one question, and approves merges. 'Elephant' is the agent session that owns the design doc and runs the loop (Environment B: the main agent). The Elephant is not the owner; the sync 'owner' in §10.2 is the Elephant acting in its sync capacity, not the human owner.

### 1.1 Glossary

Defined terms used in this document. New terms go here, not in the section that first trips over them.

- **Agent tool projections:** harness-level allowlists that would restrict a subagent's tools; they do not exist on Muse (D6).
- **Claude tool allowlists:** the Claude Code mechanism for restricting a subagent's tools; it does not exist on Muse (D6).
- **Configured memory services:** the NeuroStrata MCP connector and any other configured memory (D6). NeuroStrata is the local memory store used by this environment (see the companion doc, §2); the NeuroStrata MCP connector is the MCP (Model Context Protocol) connection through which agents read and write that store.
- **Project instructions:** `AGENTS.md` and repo instruction files (D6). `AGENTS.md` files are repo instruction files for agents (e.g. the AEP repo's `AGENTS.md`).
- **Verify outputs:** the snapshot diff plus the three checks in §10.3.1 (line-existence, standard-name, memory-prohibition), nothing else (D6).
- **Live:** the local `~/workspace/custom-skills/` tree (§10.2).
- **Sync record:** the record of a sync — the pilot-log entry for a local sync (`~/workspace/plans/<date>-egm-pilot-log.md`), or the sync PR body for a repo sync. The D1 staleness note and the C6 record are written there (§10.2).
- **Maximum tolerable drift window:** one sync interval on the local side; zero on the repo side (C2 runs on every PR) (§10.2).
- **Unsettled:** a Blocker or Major that is neither fixed in the target nor recorded CONTEST, ESCALATE, DECLINE, or SETTLED in the resolve report for that round (§10.4).
- **Substantially restate:** the same target lines and the same discrepancy as a finding fixed in the previous round (§10.4).
- **SETTLED:** a re-raise of a finding already recorded with one of the above dispositions at the same scope (same target lines and same discrepancy as the dispositioned finding), not re-opened (§10.4).
- **Namespace note:** the 10 `egm-*` names are the named agent definitions — each is the frontmatter `name` of one `agents/*.md` file (loop five: `egm-design`, `egm-comprehension`, `egm-structural`, `egm-implementation-readiness`, `egm-zoom-out`, mapped in D7; non-loop five: `egm-style`, `egm-codebase-details`, `egm-inventive-catalyst`, `egm-synthesizer`, `egm-bootstrap-orchestrator`). The 7 skill names (`egm-review`, `egm-draft`, …) are a separate namespace — skill directories, not agent definitions (§7).
- **Install notes:** exactly two records — a dated pilot log file locally, and the PR body for AEP — and the term is not used for any other artifact (D5).
- **GoldfishContext:** the reading list establishing system context for a review — files, directories, or URLs the reviewer must read (defined in the bundle's `skills/egm-review/SKILL.md:74`) (§10.3.2).
- **Documented-but-unexecuted:** a design recorded in this document that has not been run. §14 decision 3 was ruled 2026-11-07: §9 is retained as a numbered section (the appendix move described in earlier drafts of this entry is not taken), the headless (Path 2) shape was executed and validated the same day, and the term now applies within §9 only to the Path 1 (muse-cli) shape — plugin install, §9.5 step 1, and the step 3 E2E fixture — which remains documented-but-unexecuted pending a harness environment. The Phase 3 gate records the ruling and its date (§14 decision 3, §11).

One vendored content set, two installation mechanisms; Path 1 installs upstream verbatim and carries no adapted copies. (Path 1 = plugin install, §9.2; Path 2 = vendored skills, §9.3.)

Demonstrated case: the pilot round-1 `egm-review-loop` run against this document (2026-11-06; see §3 for the pilot results, report `~/workspace/plans/2026-11-06-egm-adoption-aep-goldfish-review.md`) found defects — including a genuine contradiction between D3 and Path 1 and a missing CI edit — that the existing informal instruments had not surfaced. That is the marginal value: a written standard, a configured reviewer panel, and fresh-context reviewers applied to a design document, with findings filed as a dated report.

## 2. Goals & Non-goals

- Pilot — all reviewers run (0 not run), report filed, findings categorized.
- Local — 7/7 gate-scans pass with scores recorded.
- AEP PR — CI green including vendor-integrity + skills-freshness, merged with conversation resolution — every PR review thread resolved, per the repo's branch protection (conversation resolution required).
- Adoption — at least one design document reviewed via `egm-review-loop` within 30 days of merge, with all reviewers run (0 not run). Outcome metric: finding action rate — the share of filed findings that lead to a change in the reviewed document, recorded in the pilot log; a positive pilot-value ruling must record the action rate and justify its proportionality against the §10.4 cost, whatever the rate — including 0% — and Phase 2 proceeds only on the decision 5 ruling (see §11). Findings are categorized by severity (Blocker / Major / Nit) and by scope (the section each finding targets).

Non-goals:

- No changes to upstream EGM content beyond the D3 adaptation layer.
- No vendoring of the docs site, tests, or packaging scripts.
- No replacement of `grilling`, `roundtable_review`, or the Ralph verifier (defined in §10.3.3) — EGM is an additional, heavier instrument for design work, not a substitute for fast checks.
- No EGM adoption into repos other than AEP under this document (NeuroStrata is covered separately in `~/workspace/plans/2026-11-06-egm-adoption-neurostrata.md`).

## 3. Problem Statement

Design-before-implementation is an implicit habit, not a loadable skill: design decisions reach implementation without a written, standards-audited review, and drift between design documents and code is detected only by accident. The concrete evidence: the pilot round-1 review of this document found 65 findings (3 Blockers, all 5 reviewers completed (design_critic, structural, implementation_readiness, comprehension, zoom_out) — see `~/workspace/plans/2026-11-06-egm-adoption-aep-goldfish-review.md`), a review the existing informal instruments did not produce. Scale baseline: none recorded — adoption is precautionary (no drift incident or review-load count is recorded in this document). Adoption is framed explicitly as a precautionary experiment: the kill criterion is the §11 rollback (a reviewer not run, or the owner rules no marginal value). The design corpus the pilot draws on is 22 documents under AEP `docs/` (top-level `*.md` count; the recursive count is 37 `.md` files) plus the dated plans under `~/workspace/plans/`; the Phase 0 pilot log records design docs produced per month as the demand baseline for the Phase 1 value judgment (§14 decision 5). Corpus: the 22 top-level AEP `docs/*.md` files (37 recursive) plus dated plans under `~/workspace/plans/`. Window: one calendar month. Counting method: at month end the Elephant counts design documents created in the month — dated plans by filename date (`YYYY-MM-DD` prefix), AEP `docs/` files by first-commit date (`git log --diff-filter=A --format=%ad --date=short -- docs/` in the AEP repo) — and records the two counts separately in the pilot log. (`~/workspace/plans/` is not versioned, so no git-based count covers it; the filename-date count is the method there.) The pilot round-1 review is evidence the instrument works, not evidence of the problem's scale. Rounds 1–4 are complete (round 4: 56 findings, 52 fixes applied); no round has been clean.

## 4. Proposed Architecture

Component map: pristine bundle (`~/workspace/egm/` local; `reference/elephant-goldfish-model/` in AEP) → adapted skills (local `custom-skills/egm-*/`; AEP `skills/egm-*` wrappers) → gates (SkillSpector gate-scan; vendor-integrity; skills-freshness) → dispatch (Elephant driver + Goldfish reviewers via `subagent.spawn` / harness subagent tool, direct dispatch in Environment B) → artifacts (design docs, review reports, drift reports). The existing §§8–10 keep their detail; this section is the map, with pointers to them.

| Component | Location | Defined in |
|---|---|---|
| Pristine bundle | `~/workspace/egm/` local; `reference/elephant-goldfish-model/` in AEP | D2, §10.2 |
| Adapted skills | local `custom-skills/egm-*/`; AEP `skills/egm-*` wrappers | D3, D4 |
| Gates | SkillSpector gate-scan; vendor-integrity; skills-freshness | D5, D4 |
| Dispatch | Elephant driver + Goldfish reviewers via `subagent.spawn` / harness subagent tool, direct dispatch in Environment B | §10.3 |
| Artifacts | design docs, review reports, drift reports | §10.3, §11 |

Data flow: the Elephant drafts the design doc → dispatches Goldfish reviewers in parallel (one fresh-context subagent per reviewer) → each reviewer files a report at `~/workspace/plans/<date>-<topic>-<reviewer>-r<n>.md` (§10.3.4) citing persona, standard, and target line numbers → the driver runs the line-existence + standard-name checks → the Elephant consolidates into a flat FindingsList with stable ids and writes the report artifact → `egm-resolve` categorizes → fixes are applied → the loop re-reviews until two consecutive clean rounds. Loop sequence (both paths): draft → dispatch reviewers in parallel → each files a report → driver checks (a),(b) → Elephant consolidates into the FindingsList and writes the review report → `egm-resolve` categorizes → fixes applied → re-review until two consecutive clean rounds. Path 1 differences: reviewers are named `egm/egm-*` agents where spawn works (else the general-purpose fallback), and the synthesizer is used where the harness nests subagents; Path 2 / Environment B: direct dispatch from the Elephant, no synthesizer. FindingsList fields: `id` (`<reviewer>-<round>-<n>`), reviewer, round, severity (as filed; as consolidated, if changed), target lines, discrepancy, rationale, standard, disposition (recorded in the resolve report). Detail lives in §§8–10; this section is the map. Artifact lifecycle: design docs live in the working directory / repo; review reports are dated files under `~/workspace/plans/` (pilot) or in the PR (AEP); drift reports are dated files naming their destination in advance. Concurrency: reviewers run in parallel; synthesis waits for actual completion. Failure propagation: a reviewer that times out, fails, or returns no report is retried once, then recorded not run — never counted as zero findings — and the round is not clean.

Decisions at a glance (defined in §8): D1 source from upstream at a pinned SHA; D2 vendor the bundle intact; D3 adaptation layer; D4 AEP layout; D5 SkillSpector gate; D6 Muse read-only caveat; D7 named-agent fallback.

## 5. Alternatives Considered

D-labels refer to §8.

Scale of the adopted set (verified 2026-11-06): 90-file bundle (2,810 lines of skills + agents + standards + instructions), 7 wrappers, 2 CI gates, at most 25 reviewer spawns per loop run.

- Shared `skills/egm-agents/` + `skills/egm-resources/` dirs (D4) — rejected: pollutes the skill catalog with non-skill directories and stretches `.github/skills-sync-scope.txt`'s semantics ("in-scope skill directory names").
- Do-nothing / extend `grilling` + `roundtable_review` + the Ralph verifier — not rejected on evidence; deferred to the §14 decision 5 pilot-value ruling: the delta table (§5, roundtable_review vs EGM) shows the incumbents lack a written standard, a configured reviewer panel, filed reports, and the drift/bootstrap skills, but no baseline control run establishes that those differences produce marginal value, so the option stays open until the ruling. If the ruling is negative, the do-nothing option is the adopted outcome (pilot rollback, §11).
- Point `roundtable_review` at the five upstream standards files, keeping the incumbent machinery — rejected: the five standards are written as inputs to `egm-review`'s five-stage procedure (each standard maps to one review stage); `roundtable_review`'s debate-and-judge format does not consume them, so adopting the standards alone means writing a panel configuration, a report/resolve loop, and a standards-to-debate mapping — the same machinery EGM already ships, maintained upstream. The standards are not separable from the review skill that applies them.
- Git submodule vs. vendoring — rejected: a submodule requires a network fetch at clone time and a second update mechanism outside the vendor-integrity hash; vendoring keeps the tree self-contained and hash-verified by the existing `vendor-integrity` job, matching the `reference/` pattern.
- Path 1 plugin install for AEP — rejected: AEP is a version-controlled skill catalog, not a running harness — a plugin install has no artifact to version.
- Subset vs. all seven — adopted in part: 2 skills in the pilot, remaining 5 gated on pilot evidence, defined as: the pilot completes with all reviewers run (0 not run), the report is filed and findings categorized, and the owner rules the pilot demonstrated marginal value over the existing instruments (§14 decision 5, recorded in the pilot log). Without that ruling, Phase 2 installs the 2 review skills only (`egm-review`, `egm-review-loop`); the remaining 5 skills are held until the ruling.
- Sourcing from the user's fork (`pratik-saptarshi/elephant-goldfish-model`) instead of upstream — rejected: the fork is a pure mirror (fork HEAD = upstream HEAD = `e9e1f06a`, verified 2026-11-06) and adds nothing; sourcing from upstream keeps the pin verifiable against `google/elephant-goldfish-model` directly, and the README fork-naming exception is already recorded in the attribution Notes (D4).
- Minimal-subset vendoring (only the 2 pilot skills' dependencies) — rejected: D2 requires the bundle to move as one unit because skills resolve `agents/` and `resources/` at run time, and `docs/` is runtime-referenced too (the Muse routing line targets `docs/muse.md`; D3 rewrites references to `docs/codex.md`, `docs/claude.md`, `docs/harnesses.md`); a subset that omits personas, standards, or `docs/` breaks the skills by construction. The remaining non-runtime files (`TEST.md`, `test_scenarios.yaml`, `assets/icon.svg`, `docs/designs/`, `agents/openai.yaml`) ride along under the D2 unit rule: maintaining a subset file list is its own drift risk (every upstream addition would need a keep/drop decision), and the vendor-integrity hash covers them at no extra mechanism cost. So the full 90-file bundle is vendored while only 2 skills are adapted in the pilot.

- Referencing upstream live without vendoring — rejected: no version pin (the pin is the integrity anchor), no offline use, and no vendor-integrity hash; a live reference cannot be verified against a SHA.
- Waiting for upstream [issue #252](https://github.com/google/elephant-goldfish-model/issues/252) to close instead of the D3 routing line — rejected: the routing line is one line in each of 7 skills, [#252](https://github.com/google/elephant-goldfish-model/issues/252) has no ETA, and hand-maintaining it is trivial; the line is removed if [#252](https://github.com/google/elephant-goldfish-model/issues/252) closes.
- Vendoring a docs subset (personas + standards only) — rejected: `docs/` is runtime-referenced (the Muse routing line targets `docs/muse.md`; D3 rewrites references to `docs/codex.md`, `docs/claude.md`, `docs/harnesses.md`), so a subset that omits `docs/` breaks the skills; the remaining non-runtime files (`TEST.md`, `test_scenarios.yaml`, `assets/icon.svg`, `docs/designs/`) ride along under the D2 unit rule because maintaining a subset file list is its own drift risk.
- Overlap with `brainstorming` / `writing-plans` — `egm-brainstorm` overlaps `brainstorming` (both pre-creative-work) and `egm-draft` overlaps `writing-plans` (both produce implementation tasks). The EGM versions add the multi-reviewer panel and the written standards; they are adopted only on the §14 decision 5 pilot-value ruling (Phase 1), not in the pilot — and Phase 2 installs only the 2 review skills without that ruling (see §11.3 two-skill variant).

- Adapted skills inside the bundle tree instead of wrappers under `skills/` — rejected: the bundle must stay pristine/verbatim so the vendor-integrity hash and the §10.5 step 2 zero-diff check hold; any adaptation inside the tree breaks both.
- Single canonical direction (the repo is canonical for everything; local is a checkout) instead of per-artifact directions — rejected: local pilot edits originate locally and must be testable before any repo PR, while the bundle originates upstream via the repo; a single repo-canonical direction would force pilot edits through the repo PR flow before they can be tested locally. The per-artifact directions (§10.2) follow the origin of each artifact. A sync run in the wrong direction is prevented by the §10.5 step 4 check, which fails (non-zero diff) rather than overwriting when the trees do not match after normalization.
- Local-only adoption until AEP need is proven — adopted in part: Phases 0–1 are local-only; the AEP PR (Phase 2) proceeds only on the §14 decision 5 pilot-value ruling.

| Dimension | roundtable_review | EGM |
|---|---|---|
| Written standard | none | 5 standards files |
| Configured reviewer panel | per-run reviewers + debate + judge | 10 named personas + synthesizer |
| Fresh-context reviewers | yes | yes |
| Claim verification | verification subagents + judge | driver line-existence + standard-name checks |
| Drift/bootstrap skills | none | `egm-drift-report` + `egm-bootstrap` |
| Dated report artifacts | single-session | filed reports + resolve loop |

Genuinely new delta: the five written standards, the gate-scan / vendor-integrity / skills-freshness gates, and the drift-report/bootstrap skills. No roundtable baseline control run was performed on this document, so the §3 pilot does not establish marginal value over the incumbent; the marginal-value judgment is the owner's §14 pilot-value ruling (decision 5).

## 6. Risks & Mitigations

D-labels refer to §8.

- D6 read-only caveat — controls (detection only — the residual stands): read-only briefs + disposable target copy + post-run round-level snapshot diff (detection only — see D6) + line-existence check; memory/DB writes are unrecoverable.
- Wrapper↔bundle coupling breakage on rename — mitigation: the resolve check in §10.5 verification; rename of either tree is a deliberate PR touching both.
- Dual-install drift — mitigation: canonical direction + normalize-then-diff (§10.5 step 4).
- Loop cost — mitigation: bounds in §10.4 Loop bounds (at most 5 rounds × 5 reviewers = 25 spawns per run, and no other spawns are made by the loop; 30-minute interim per-reviewer timeout for the pilot; cost recorded per phase gate (reviewer count, rounds, tokens per reviewer in the pilot log); interim budget 12.5 reviewer-hours per run; interim pilot token cap (per-reviewer and per-run maxima) set by owner ruling before the next pilot run — no further pilot run proceeds without a recorded cap — and the Phase 1 token budget set by §14 decision 6 from the pilot log's actuals (per-reviewer and per-run maxima) before Phase 1 starts — no Phase 1 run proceeds without it). Upstream's optional A/B duplication (two instances per reviewer) is NOT used: one instance per reviewer. (A/B duplication: the synthesizer's Mode REVIEW option of launching two independent instances of each reviewer to maximize finding recall and eliminate non-deterministic evaluation gaps — bundle `docs/designs/synthesizer.md`, Mode REVIEW, 'Redundant Subagent Spawning (A/B Sampling)'.)
- Harness-version drift — mitigation: §9.5 step 4 re-run of the fixture after upgrades.
- Failure modes: reviewer not run → round not clean, retry once; gate trip → upstream fix / baseline entry / owner force-sync; plugin install rejection on symlinks → symlink-free source.
- Security risks — see §12 Security notes (principal risk: the D6 read-only caveat; URL-fetch bounds; bundle content review).
- Scalability limits — bundle size is fixed at 90 files / 792K (D2 unit rule; it does not grow with use); loop cost is bounded at 25 spawns per run (§10.4); per-skill load is one `SKILL.md` + `skill.yaml` per skill, so catalog growth is linear in skills added, not in reviews run.

## 7. What EGM is (verified)

- **Model:** Elephant (one agent holds context and drafts the spec) +
  Goldfish (reviewers spawned in fresh contexts with zero conversation
  history, to expose unstated assumptions) + the human (explicit approval
  gates before anything is built). Designed to defeat hallucination
  cascades, premature implementation, and documentation drift.
- **Vendoring-relevant content:** 7 skills (1,898 lines), 10 personas (`agents/`, 30–101 lines each), of which 5 form the `egm-review-loop` panel: design_critic, structural, implementation_readiness, comprehension, zoom_out. The other 5 (`egm-style`, `egm-codebase-details`, `egm-inventive-catalyst`, `egm-synthesizer`, `egm-bootstrap-orchestrator`) are not loop reviewers — the synthesizer consolidates only where the harness nests subagents (§10.3), and the bootstrap orchestrator belongs to `egm-bootstrap`, not to review. Namespace note: see §1.1 Glossary. 5 document standards
  (`resources/document_standards/`), 1 execution-instructions file.
  Skills + agents + standards + instructions total 2,810 lines.

| Skill | Function |
|---|---|
| `egm-brainstorm` (271 lines) | Multi-reviewer idea exploration → `concepts_brief.md` (written to the working directory alongside the brainstorm) |
| `egm-draft` (321) | Brief → design document, section-by-section with user feedback |
| `egm-review` (426) | Five-stage fresh-eyes design review |
| `egm-resolve` (187) | Work through review findings with the Elephant |
| `egm-review-loop` (199) | Configured reviewer panel + standards + iterative fix loop |
| `egm-bootstrap` (427) | Document an existing codebase via parallel scout subagents |
| `egm-drift-report` (67) | Detect design-doc vs. code drift, write a dated report (pilot: `~/workspace/plans/<date>-<topic>-drift.md`; each drift run names its destination in advance) |

- **Not vendored:** the Astro docs site (`site/`; Astro is the static-site generator the docs site is built with), packaging scripts (`scripts/`), the top-level `tests/` directory, the `adapters/` directory, per-host plugin manifests (`.claude-plugin/`, `.codex-plugin/`, `.cursor-plugin/`), and all other repo-root files (the included set is exactly the paths in the §10.5 step 2 diff command — `skills/`, `agents/`, `resources/`, `docs/`, `LICENSE`, `plugin.json` — so every other repo-root file is excluded by construction). Per-skill test files (`TEST.md`, `test_scenarios.yaml`) live under `skills/` and ARE vendored. The authoritative included set is the §10.5 step 2 diff command's enumeration — the prose lists here state what is excluded, not a second copy of what is included.
- **Upstream state (verified 2026-11-06):** the user's fork
  (`pratik-saptarshi/elephant-goldfish-model`) is a **pure mirror** — fork
  HEAD and upstream HEAD are both `e9e1f06a`. Source from upstream, not the
  fork. The fork adds nothing.
- **Muse support (verified upstream):** `docs/muse.md` + `docs/harnesses.md`
  document Muse 1.4.14 support; the end-to-end fixture (brainstorm, draft,
  uninterrupted review with 15 fresh-context reviewers) passed 2026-10-30. The fixture's '15 fresh-context reviewers' is the upstream E2E fixture's reviewer count across its brainstorm/draft/review stages, not this loop's 5-reviewer panel.
  Headless run with approvals simulated up front (the run pre-approved every gate instead of waiting for a human turn, so interactive gates are untested).
  Interactive approval gates and chat link rendering are untested (whether absolute-path Markdown links render as clickable links in Muse chat was not exercised).

## 8. Design decisions

### D1 — Source from upstream at a pinned SHA

Vendor from `google/elephant-goldfish-model` at a recorded commit SHA, never
from the fork and never from a floating branch. Record the SHA in the
attribution table and in the vendored tree's `PROVENANCE.md` (AEP) / bundle
README (local). Re-sync is a deliberate PR, not a silent pull. Cadence and staleness: the pin is re-checked on every sync; if upstream HEAD is more than 90 days newer than the pin — computed from commit dates in the upstream clone (`git log -1 --format=%ci <pin>` vs `git log -1 --format=%ci HEAD`; stale when the HEAD date is more than 90 days after the pin date) — the sync record notes the pin as stale and the owner rules on re-vendor. The check runs on every sync and at each phase gate; between gates a pin may go stale silently, which is accepted explicitly (no continuous staleness watch exists). Owner: the agent running the sync (§10.2). Single source of truth: the pin is stated here and in §14 decision 1; every other occurrence (attribution, PROVENANCE.md, bundle README.md, §9.3 clone commands, §10.5 step 2 fetch + `rev-parse` expectation) is a use of that pin. When the pin changes, update D1 and §14 decision 1 first, then the uses together in the same PR.

### D2 — Vendor the bundle intact; never skill-only

Upstream states this explicitly in `docs/harnesses.md`: *"Skill-only
installers that copy `skills/` alone break EGM, because the skills read
`agents/` and `resources/document_standards/` at run time."* Skills resolve
`agents/` and `resources/` relative to the plugin root (two parents above each `SKILL.md`: `skills/<skill>/SKILL.md` reaches the plugin root as `../../`). Any layout that separates skills from personas and
standards is broken by construction. The bundle — skills + agents +
resources + docs — moves as one unit in both environments.

### D3 — Adaptation layer, not upstream edits

Three mechanical adaptations, applied to every vendored-skills install (Path 2 and Environment B). Path 1 installs the upstream plugin verbatim and carries no adapted copies.

1. **`skill.yaml` per skill, hand-written (the repo norm — 61 `skill.yaml` files exist in `skills/` and no script generates them).** Fields, per the established format: `name` (e.g. `egm-review`), `title` (Title Case, e.g. `EGM Review`), `description` (the frontmatter description verbatim), `category: "Work and knowledge"`, `include_in_prompt: true`. Validation: YAML parses, and `name` matches the `SKILL.md` frontmatter `name`. The files are excluded from the manifest by the bare `skill.yaml` entry in `[exclude-paths]` and are therefore covered by neither cited gate; the YAML-parse + name-match check in Phase 2 is their coverage. `license` and `disable-model-invocation` are frontmatter fields of the upstream `SKILL.md` and do not belong in `skill.yaml`. `disable-model-invocation: true` means the skill must not be invoked automatically by the model — it is user-invocable only (verified: the pilot skills carry this frontmatter and were invoked explicitly). Titles for all 7 skills: `egm-review` → `EGM Review`; `egm-brainstorm` → `EGM Brainstorm`; `egm-draft` → `EGM Draft`; `egm-resolve` → `EGM Resolve`; `egm-review-loop` → `EGM Review Loop`; `egm-bootstrap` → `EGM Bootstrap`; `egm-drift-report` → `EGM Drift Report`.
2. **Muse routing line.** No EGM skill routes a Muse session to
   `docs/muse.md` (upstream gap [#252](https://github.com/google/elephant-goldfish-model/issues/252): no skill routes a Muse session to `docs/muse.md`, so a Muse session does not read the guide unless pointed at it). Each adapted `SKILL.md` gains one
   line: *"In Muse, read <bundle>/docs/muse.md first."* Insertion point: immediately after the frontmatter (first line of the body).
3. **Path resolution.** Rewrite mapping table (upstream reference → installed reference); `<bundle>` is `/home/hatch/workspace/egm` in Environment B, `<install-root>/egm` in Environment A Path 2, and `../../reference/elephant-goldfish-model` in the AEP wrappers:

| Upstream reference | Installed reference |
|---|---|
| `agents/` | `<bundle>/agents/` |
| `resources/document_standards/` | `<bundle>/resources/document_standards/` |
| `resources/execution_instructions.md` | `<bundle>/resources/execution_instructions.md` |
| `../../docs/codex.md` | `<bundle>/docs/codex.md` |
| `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` | `<bundle>/docs/claude.md` |
| `docs/harnesses.md` | `<bundle>/docs/harnesses.md` |
| `docs/muse.md` | `<bundle>/docs/muse.md` |

Record per-skill occurrence counts in the Phase 2 PR body (pilot counts for the two installed skills: `egm-review` 3× `agents/`, 1× `resources/document_standards/`, 1× each codex/claude/harnesses; `egm-review-loop` 4× `agents/`, 5× `resources/document_standards/`, 1× each codex/claude/harnesses). The pilot verifies the Muse routing line's target (`<bundle>/docs/muse.md`) resolves in each environment. The Muse routing line carries its path: `In Muse, read <bundle>/docs/muse.md first.` Environment B uses the `~` form `~/workspace/egm/...` in adapted files (the pilot does this: `egm-review` 8 occurrences, `egm-review-loop` 13, verified 2026-11-06; the expanded form `/home/hatch/workspace/egm/...` never appears in a pilot adapted file). The pristine bundle is never edited; adaptations live only in the installed skill copies.
4. **Post-vendoring behavioral adaptations (PR #111 fix rounds, 2026-11-07).** Recorded here so a re-sync from upstream re-applies them instead of silently dropping them; they came out of Codex review of the vendored wrappers and an adversarial panel on the fix round. (a) `egm-bootstrap` / `egm-draft`: skill-local `references/` links redirected into the bundle (the wrappers carry no `references/` directory). (b) `egm-review-loop`: a frontmatter-name normalization table at intake — item 3's rewrite covers paths, not persona names. (c) `egm-review`: stage-report copy steps before the Critic and Implementation Readiness checkpoints; the Uninterrupted Full Flow passes filename shortnames with `Mode: REVIEW` (the synthesizer resolves names as files and does not normalize); the Zoom Out subflow gives the `inventive_catalyst` persona path explicitly. (d) `egm-bootstrap` Step 5 item 2: intermediate directories receive Step 4's scout scan **and** directory classification — a deliberate behavioral divergence from upstream, whose identical step generates Intermediate Blueprints from child summaries only. (e) The item-2 routing line is amended in the wrappers: it states the bundle is already vendored and that `docs/muse.md`'s install and plugin-root instructions do not apply to this layout. (f) `egm-review`: the Uninterrupted Full Flow passes each stage's standards explicitly (Codex re-review of the fix-round-2 head). (g) `egm-bootstrap` Step 3: a partition coverage check carries shallower terminal branches into the partition set and verifies every retained directory is covered — a deliberate divergence from upstream's partitioning algorithm, which can skip such branches (Codex re-review of the fix-round-2 head). (h) `egm-bootstrap` Step 3 / Step 4: workers receive the partition's retained directory list and traverse only it, so Step 2's exclusions survive partitioning (fix round 4). (i) `egm-bootstrap` Step 5 item 2: the Correction & Modification Policy applies to intermediate contracts, not just the root (fix round 4). (j) `egm-review-loop` gains a `DeferResolution` parameter and `egm-review`'s interactive subflows pass it, so the loop returns after the review and the stage checkpoint — not the loop — decides whether resolution runs (Codex review of the fix-round-3 head).

Mechanism: apply item 3 before item 2 (the routing line inserted in item 2 already contains `<bundle>/docs/muse.md`, so a later item-3 rewrite must not touch it), one `sed` per row in table order, and verify with §10.6 Verification check C1. Bind `<bundle>` first (Environment B: `bundle='~/workspace/egm'` — quoted, so the `~` form is preserved literally, not expanded; AEP wrappers: `bundle='../../reference/elephant-goldfish-model'`; Path 2: `bundle='<install-root>/egm'`), then run the literal commands below (one per row, `<file>` is the adapted `SKILL.md`; each skips already-prefixed lines; the `\|...|` address form is used because the bound value contains `/`, which would terminate a `/.../` address):

```
sed -i "\|$bundle/agents|!s|agents/|$bundle/agents/|g" <file>
sed -i "\|$bundle/resources/document_standards|!s|resources/document_standards/|$bundle/resources/document_standards/|g" <file>
sed -i "\|$bundle/resources/execution_instructions.md|!s|resources/execution_instructions.md|$bundle/resources/execution_instructions.md|g" <file>
sed -i "\|$bundle/docs/codex.md|!s|\.\./\.\./docs/codex.md|$bundle/docs/codex.md|g" <file>
sed -i "\|$bundle/docs/claude.md|!s|\${CLAUDE_PLUGIN_ROOT}/docs/claude.md|$bundle/docs/claude.md|g" <file>
sed -i "\|$bundle/docs/harnesses.md|!s|docs/harnesses.md|$bundle/docs/harnesses.md|g" <file>
sed -i "\|$bundle/docs/muse.md|!s|docs/muse.md|$bundle/docs/muse.md|g" <file>
```

After running them, assert no literal placeholder remains: `grep -q '<bundle>' <file> && { echo "ERROR: unbound <bundle> remains in <file>"; exit 1; }`. (C1's substring grep cannot catch this failure mode: `agents/...` matches inside a literal `<bundle>/agents/...` string while the real bundle path exists, so C1 passes on a corrupted file — this check is the only guard.)

Ordering: item 3 runs before item 2; the routing line is never rewritten.

Idempotency guard: before applying, assert the file contains neither the `<bundle>/` prefix nor, in Environment B, the `~/workspace/egm/` prefix (`grep -qE '(<bundle>|~/workspace/egm)/' <file>` must find nothing — the literal `<bundle>/` check alone cannot detect a re-run in Environment B, where adapted files use the `~` form); re-running the mapping on an already-adapted file is an error, not a no-op. Example literal command for the first row: `sed -i '/<bundle>\/agents/!s|agents/|<bundle>/agents/|g' <file>`. Record per-skill occurrence counts for all 7 skills in the Phase 2 PR body (pilot counts are given for the 2 installed skills; counts for the remaining 5 are computed the same way at Phase 1). Already-absolute pilot references of the form `~/workspace/egm/...` resolve against the bundle root as-is in Environment B; in AEP wrappers they become `../../reference/elephant-goldfish-model/...`.

### D4 — AEP layout: bundle under `reference/`, thin wrappers under `skills/`

- **Bundle:** `reference/elephant-goldfish-model/` — verbatim upstream tree
  (skills, agents, resources, docs, LICENSE, `plugin.json`), with
  `.github/vendor-elephant-goldfish-model.sha256` and `PROVENANCE.md`, per
  the existing vendor pattern (`reference/esf`, `reference/neurostrata`,
  `reference/docs-mcp-server`, etc.). Covered by the `vendor-integrity` CI job once the tenth per-tree `run:` block lands in `.github/workflows/ci.yml` in the same PR (same `sha256sum -c` + unlisted-files + symlink pattern as the existing nine blocks); until that block lands the bundle has zero integrity verification. Generate `.github/vendor-elephant-goldfish-model.sha256` with `cd reference/elephant-goldfish-model && find . -type f | sort | xargs sha256sum > ../../.github/vendor-elephant-goldfish-model.sha256` (vendor line format `<sha256hex>  ./<path>`, sorted by path). Add the tenth `vendor-integrity` `run:` block to `.github/workflows/ci.yml` for `reference/elephant-goldfish-model`, inserted after the `humanizer` block (the `vendor-integrity` `run:` block for the existing `reference/humanizer/` tree) (pattern identical to the existing nine blocks, e.g. the esf block):

  ```
      - run: |
          cd reference/elephant-goldfish-model
          sha256sum -c ../../.github/vendor-elephant-goldfish-model.sha256
          comm -23 <(find . -type f | sort) <(cut -d' ' -f3- ../../.github/vendor-elephant-goldfish-model.sha256 | sed 's|^\./|./|' | sort) | grep -q . && { echo "ERROR: unlisted files"; exit 1; } || true
          find . -type l | while read -r link; do test -e "$link" || { echo "ERROR: broken symlink $link"; exit 1; }; done
      - run: |
          missing=$(for f in skills/egm-*/SKILL.md; do grep -oE '\.\./\.\./reference/[A-Za-z0-9_./-]+' "$f"; done | sed 's/\.$//' | sort -u | while read -r p; do test -e "reference/${p#../../reference/}" || echo "MISSING: $p"; done)
          [ -z "$missing" ] || { echo "$missing"; exit 1; }
  ```

Write `reference/elephant-goldfish-model/PROVENANCE.md` with the esf pattern's fields (`reference/esf/` is an existing vendored tree — the ESF reference implementation for the AEP factory lane, vendored from `pratik-saptarshi/esf`; its `PROVENANCE.md` is the pattern exemplar): Upstream URL, Pinned commit (+ subject), Snapshot date, License, Excluded from the vendor, Purpose, Updating, Update history. Order: write `PROVENANCE.md` first, then generate the `.sha256` file, so `PROVENANCE.md` itself is listed (esf precedent: `.github/vendor-esf.sha256` contains `./PROVENANCE.md`). Field values: Upstream URL `https://github.com/google/elephant-goldfish-model`; Pinned commit `e9e1f06a` + subject (copied from `git log -1 --format=%s e9e1f06a` at vendor time); Snapshot date `YYYY-MM-DD` (the vendor date); License `Apache-2.0`; Excluded from the vendor: `site/`, `scripts/`, `tests/`, `adapters/`, per-host plugin manifests, all other repo-root files; Purpose: 'Vendored EGM bundle for the AEP skill catalog — the 7 `egm-*` skills' personas, standards, and instructions (see §8 D4).' Updating: 'Re-vendor is a deliberate PR per the §10.2 cadence; the pin is re-checked on every sync (D1).' Update history: '2026-11-06: initial vendor at `e9e1f06a` (Phase 2 PR).'
- **Wrappers:** `skills/egm-*/` — one thin directory per skill containing
  the adapted `SKILL.md` (D3) + `skill.yaml`, with paths pointing into
  `../../reference/elephant-goldfish-model/agents/` and
  `../../reference/elephant-goldfish-model/resources/document_standards/`. Covered by the `skills-freshness` gate for the adapted `SKILL.md` files only: the gate proves the repo `skills/` tree equals the manifest (`.github/skills-manifest.sha256`, §11.3) generated from the repo tree after the last sync from the local tree (`~/workspace/custom-skills/`, 'live' in §10.2) — it detects neither drift against the upstream bundle nor drift against local `custom-skills/`. The hand-written `skill.yaml` files are excluded from the manifest by the bare `skill.yaml` entry in `[exclude-paths]` and are therefore covered by neither gate; they are validated instead by a YAML-parse + name-match check in Phase 2 (see §10.5). Attribution rows live in `skills/README.md`. Attribution rows (one per skill): Source `google/elephant-goldfish-model` — explicit exception to the README's fork-naming convention, because D1 sources from upstream (the fork is a pure mirror and adds nothing); record the exception in the Notes column. License `Apache-2.0`. Notes: 'Adapted (D3); exception to the README fork-naming convention — D1 sources from upstream (fork is a pure mirror); bundle under `reference/elephant-goldfish-model/`; pinned `e9e1f06a`.'

This wrapper→bundle coupling follows the existing `skills/craft-anything-protocol/` → `reference/craft-anything/` precedent (a skill referencing a vendored `reference/` tree under the sha256 vendor-integrity regime with a `PROVENANCE.md`); what is new is only the two-direction sync discipline for it, evaluated in §5. It is accepted explicitly here because the alternatives are worse (see §5: adapted skills inside the bundle tree break the pristine/verbatim rule; shared `skills/egm-agents/` + `skills/egm-resources/` dirs pollute the catalog; local-only adoption is adopted in part for Phases 0–1). The two-tree drift the coupling creates is managed by the §10.2 canonical direction (per artifact) and the §10.5 step 4 sync check.

- **Alternative considered and rejected:** shared `skills/egm-agents/` + `skills/egm-resources/` dirs — evaluated in §5 (rejected: pollutes the skill catalog with non-skill directories). Two gates covering two layers (vendor-integrity for the bundle, skills-freshness for the wrappers) is cleaner separation.


### D5 — Every adapted skill passes the SkillSpector gate before install

SkillSpector is the NVIDIA skill scanner (`~/workspace/skillspector/`, wrapper `scan-gate.sh`); the gate blocks on score > 50 or any HIGH/CRITICAL finding and fails closed on scan errors.

Standing rule, no exception where the gate is available: `scan-gate.sh` on each adapted skill dir;
block on score > 50 or any HIGH/CRITICAL finding, fail closed on scan
errors. Pure-markdown skill content is expected to pass easily (the only
plausible flags are wording false positives). A block is resolved by an
upstream fix, a dispositioned baseline entry, or the owner's explicit
force-sync — never silently. Invocation (local): `~/workspace/skillspector/scan-gate.sh <skill-dir>`; (AEP): `scripts/scan-gate.sh <skill-dir-or-file>` (usage line verified in the repo). The score is a 0–100 risk score; the gate blocks on score > 50 or any HIGH/CRITICAL finding and fails closed on scan errors. A dispositioned baseline entry is a `skillspector-baselines/<skill>.json` record (repo) / `~/workspace/skillspector/baselines/<skill>.json` (local) with accepted/dismissed findings, each carrying pattern, location, confidence, and justification. Scores are recorded in the Phase 2 PR body (one line per skill in the literal format `` `<skill-name>` — score <n>, pass|block ``) and in the pilot log file `~/workspace/plans/<date>-egm-pilot-log.md`. 'Install notes' (used in §9.3; see §1.1 Glossary). Bundle non-markdown files are content-reviewed at vendor time — 25 files at the pinned SHA: `agents/openai.yaml` ×7 (one per skill), per-skill `test_scenarios.yaml` ×7, `skills/egm-bootstrap/references/worker-return.schema.json` ×1, `assets/icon.svg` ×7 (one per skill), `docs/assets/readme-header.svg` ×1, `LICENSE` ×1, `plugin.json` ×1 (the harness-read plugin manifest — the highest-trust file, declaring what the harness loads). The vendor reads each file and records a one-line content note per file in the Phase 2 PR body, in the template '`<path>`: <what the file is and that it contains no executable code, network call, or credential>'. Pass/fail: a file blocks the vendor if it contains executable code, a network call, a credential, or content whose purpose the vendor cannot state in one line; a blocked file is removed from the vendor or dispositioned by the owner before the PR merges. The gate input is the whole skill directory — `skill.yaml` is scanned together with its `SKILL.md`, so a malicious description (`include_in_prompt: true` injects it into the prompt) trips the same gate. SHA integrity proves provenance against the pin, not safety; the content review is the safety control for the bundle.

### D6 — The Muse read-only caveat is procedural, not technical

Upstream states it plainly in `docs/muse.md`: agent tool projections are
unsupported on Muse — Claude tool allowlists do **not** restrict Muse
reviewers, so do **not** assume Goldfish reviewers are read-only, even
though every persona mandates read-only. There is no tool-restriction mechanism on Muse: 'agent tool projections' (see §1.1 Glossary) and 'Claude tool allowlists' (see §1.1 Glossary) do not exist here, so 'do not hand reviewers write tools' means only this — the brief names no write tool, and the reviewer is instructed read-only. Brief reviewers read-only, pass absolute paths to the persona / standards / target document, and never pass the parent transcript or private reasoning. Fresh context does not isolate the filesystem, configured memory services, or project instructions — reviewers must not retrieve conversation history or memory to supply missing design context. 'Configured memory services' (see §1.1 Glossary) and 'project instructions' (see §1.1 Glossary). NeuroStrata, the NeuroStrata MCP connector, and `AGENTS.md` are defined in the glossary (see §1.1 Glossary). 'Verify outputs' (see §1.1 Glossary). Detection is post-hoc: the snapshot diff detects a write after it happens; it does not prevent it. The round is fail-closed (a detected write fails the round), the filesystem is not — the residual write-before-detection risk stands (see §12). Before dispatch, snapshot each scope location by content hash with the `find` form (`find <dir> -type f -exec sha256sum {} + | sort > /tmp/egm-snapshot-<run>-<n>.sha256`, one file per location, `<n>` = 1–4 for the four locations in scope order, `<run>` is the round number, e.g. `r3`): (1) the target repo working tree, (2) `~/workspace/egm/`, (3) all seven `~/workspace/custom-skills/egm-*/` dirs together in one snapshot file (one `find` over the glob: `find ~/workspace/custom-skills/egm-*/ -type f -exec sha256sum {} + | sort`), (4) `~/workspace/plans/`. `git status --porcelain` is not a content hash and is not used as the snapshot command. Re-run the same commands to `-after` files (`/tmp/egm-snapshot-<run>-<n>-after.sha256`) and compare each pair with the exclusion procedure below; any output names a modified path. Exclusion procedure (per pair, with `<before>` the snapshot file and `<after>` the `-after` file): added paths are `comm -13 <(awk '{print $2}' <before> | sort) <(awk '{print $2}' <after> | sort)`; removed paths are `comm -23` with the same inputs; changed paths are those present in both files with a different hash, `join -j 2 <(sort -k2 <before>) <(sort -k2 <after>) | awk '$2 != $3 {print $1}'`. The after-diff ignores added paths under `~/workspace/plans/` (the round's own report and pilot-log entries); any removed or changed path anywhere, or any added path outside `~/workspace/plans/`, fails the round. Rollback re-vendor command: `rm -rf ~/workspace/egm/ && cp -r <repo>/reference/elephant-goldfish-model ~/workspace/egm/` (where `<repo>` is the AEP repo root; the `rm -rf` comes first because `cp -r` onto an existing destination nests rather than replaces), after `git checkout -- <paths>` restores the repo tree, where `<paths>` are the paths the diff names. Snapshot scope is the target repo working tree plus the local bundle (`~/workspace/egm/`), the adapted skills (`~/workspace/custom-skills/egm-*/`), and the reports directory (`~/workspace/plans/`). Before dispatch, copy the target document to a disposable per-round copy with the literal commands (`<target>` is the target document's absolute path):

```
mkdir -p /tmp/egm-review-<run> && cp <target> /tmp/egm-review-<run>/target.md
```

The copy is byte-identical; line numbers map 1:1 onto the original and brief reviewers with the copy's path; a write to the copy harms nothing and the original is never opened by a reviewer. This protects the target document only: reviewers still receive absolute paths to the persona, standards, and GoldfishContext files, so writes elsewhere in the tree remain possible and are covered by detection only (below). Full containment (a reviewer that cannot write anywhere) is unavailable on Muse — there is no tool-restriction mechanism — so detection plus the disposable target copy is the strongest available control; the residual write-before-detection risk stands. Memory/DB paths are out of scope: no snapshot is taken of the NeuroStrata store, and reviewers are briefed never to read or write memory — silent memory use is undetectable and is stated here as a residual risk, not as a closed control. After all reviewers complete (the snapshot window is the whole round, not one reviewer — reviewers run in parallel), re-run the snapshot and diff it; any unexpected modification fails the round, the findings are discarded, and no reviewer is re-dispatched. Each reviewer's report must cite every finding's target line numbers; the driver checks each cited line exists in the target at the stated range — a report failing the check is incomplete and re-run once, then recorded not run. Rollback: on a detected modification, fail the round, discard its findings, restore tracked files from git (`git checkout -- <paths>`, where `<paths>` are the paths the diff names), remove newly created untracked files and directories (`rm -rf -- <paths>`; plain `rm` fails on newly created directories), and re-vendor the bundle from the repo tree; a deleted untracked file cannot be restored — its loss is recorded in the pilot log as unrecoverable, and record the incident in the pilot log; no reviewer is re-dispatched. Attribution: with parallel reviewers a modification is attributed to the round, not to one reviewer.

### D7 — Named-agent spawn falls back to general-purpose subagents

On Muse 1.4.14 the named `egm/egm-*` definitions report `trusted_enabled` (`trusted_enabled`: the harness lists the definition as trusted/available, though spawning it is still rejected with `agent_definition_unavailable`)
but spawning one is rejected (`agent_definition_unavailable` — the error returned when spawning it is attempted). The working
path is the general-purpose fallback EGM itself documents: spawn a
general-purpose subagent and tell it to read the persona file first,
matched by frontmatter `name`, never by filename (verified from `agents/*.md` frontmatter): `egm-design` → `agents/design_critic.md`; `egm-comprehension` → `agents/comprehension.md`; `egm-structural` → `agents/structural.md`; `egm-style` → `agents/style.md`; `egm-implementation-readiness` → `agents/implementation_readiness.md`; `egm-codebase-details` → `agents/codebase_details.md`; `egm-zoom-out` → `agents/zoom_out.md`; `egm-inventive-catalyst` → `agents/inventive_catalyst.md`; `egm-synthesizer` → `agents/synthesizer.md`; `egm-bootstrap-orchestrator` → `agents/bootstrap_orchestrator.md`. In Environment B this maps
exactly onto `subagent.spawn` with "read this persona file first" in the
brief. If a harness cannot nest subagents, dispatch reviewers directly
from the parent (direct dispatch) instead of through the synthesizer; if a
harness has no subagent tool at all, the review skills stop instead of running in the same context.

## 9. Environment A — general-purpose Linux VM

*Ruled 2026-11-07 (§14 decision 3): this section is retained as designed. The headless (Path 2) shape was validated 2026-11-07 in an emulated fresh-VM rootfs (pilot log dated 2026-11-07): §9.1 provisioning, the §10.6 checks, the D5 gate scans, and the §9.5 step 2 packaging tests all pass. The Path 1 (muse-cli) shape — plugin install, §9.5 step 1, and the step 3 E2E fixture — remains documented-but-unexecuted pending a harness environment and owner sign-in.*

### 9.1 Prerequisites

- `git` ≥ 2.43.0, `python3` ≥ 3.12.3 (verified floor on this VM, Environment B), Fresh-VM image: an Ubuntu 24.04 cloud image (which ships `git` 2.43.0 and `python3` 3.12.3, the floors above). Provisioning: install `git`, `python3`, and `python3-venv` from the distro packages, then install the harness CLI per its vendor instructions (§9.2 links) — no other install source is specified. `pytest==9.2.0` and `PyYAML==6.0.3` (C3/C6 need the `yaml` module), installed before §9.5 step 2 in a virtualenv on the fresh VM (`python3 -m venv /tmp/egm-venv && /tmp/egm-venv/bin/pip install "pytest==9.2.0" "PyYAML==6.0.3"`; a venv is used because PEP 668 (the Python standard for externally-managed environments) means externally-managed environments refuse bare `pip install` and the fresh VM may have no system pip — record the installed versions in the pilot log; pytest 9.2.0 and PyYAML 6.0.3 are the latest releases, verified 2026-11-06), and one supported harness CLI — Muse ≥ 1.4.14 (the upstream-verified version). The harness determines the install path; the VM shape
  determines which path applies. There is no third 'pilot VM': the two environments are A (fresh VM) and B (this VM) only. Two provisioning notes from the 2026-11-07 validation run: (1) the distro packages are the cloud image's standard set — its apt sources enable the universe component, which `python3-venv` requires (a minimal system with main-only sources cannot install it); (2) `nodejs` (the noble distro package) must also be installed before §9.5 step 2 — three upstream unit tests at the pinned SHA shell out to `node`, which this list otherwise omits.

### 9.2 Path 1 — Plugin install (preferred where the harness exists)

For Muse (per `docs/muse.md`):

```sh
git clone https://github.com/google/elephant-goldfish-model.git
muse plugins install ./elephant-goldfish-model --scope user
muse plugins approve egm
```

(The clone creates `./elephant-goldfish-model/`, the default directory name the next command uses.) That directory is also the working directory for §9.5 step 2; §9.3's `<install-root>/egm-checkout` is the same checkout under its Path 2 name — one checkout, two names, not two checkouts.

Path 1 performs no adaptation step: no `skill.yaml` is generated (the plugin's frontmatter is sufficient), no routing line is added — name `docs/muse.md` in the session prompt instead, per upstream practice until [issue #252](https://github.com/google/elephant-goldfish-model/issues/252) closes — and the bundle is installed verbatim. The D3 adaptations exist only where skills are vendored.

Notes, all verified upstream: install from a local path — `marketplace add`
discovers zero plugins (Muse reads the Codex catalog first and skips the
entry, so it never falls through to the Claude catalog — install from a local path instead). Keep the source free of symlinks (remove scratch dirs such as
`.venv/`; the installer rejects symlink entries). One approval covers the plugin and its ten agent definitions: run `muse plugins approve egm` once (upstream `docs/muse.md`: 'Approval is required once… the ten agent definitions need `approve` before activation'); there is no per-agent approval step. Start a fresh session after
install; confirm with `muse skills list --source plugin` (skills surface
as `plugin:egm:egm-*`).

**Native installs for the other harnesses:** commands from the bundle's `docs/harnesses.md` install table.


- **Claude Code:** `claude plugin marketplace add google/elephant-goldfish-model && claude plugin install egm@egm`
- **Antigravity CLI:** `agy plugin install https://github.com/google/elephant-goldfish-model`
- **Antigravity App/IDEs:** run the `/plugin` slash command to open the plugin installer
- **Codex CLI:** `codex plugin marketplace add google/elephant-goldfish-model && codex plugin add egm@egm` (from the bundle's `docs/harnesses.md` install table).
- **Codex desktop and ChatGPT desktop:** install the published EGM plugin (desktop-only listing: [ChatGPT plugin listing](https://chatgpt.com/plugins/plugins_6aeb90f47ec88191a3c107e01d3eb357)).
- **Cursor:** experimental, unverified upstream (bundle `docs/cursor.md`: 'Do not add Cursor to the supported-host table yet'; upstream [issue #145](https://github.com/google/elephant-goldfish-model/issues/145)) — install from a clean checkout per `docs/cursor.md` 'Install a candidate'; not a supported Path 1 route until verified.
- **OpenCode:** OpenCode 1.18.29 only, from an upstream checkout at the pinned SHA: `python3 adapters/opencode/install.py /absolute/egm-opencode-candidate`, then `OPENCODE_CONFIG=/absolute/egm-opencode-candidate/opencode.json opencode --agent egm` (per bundle `docs/opencode.md`); `adapters/` is not vendored, so this runs from the upstream checkout, not the bundle; adapter unverified upstream ([issue #146](https://github.com/google/elephant-goldfish-model/issues/146)).

### 9.3 Path 2 — Vendored skills (headless VM, or no harness plugin support)

Where no plugin install is available, install the same adapted content as
in Environment B (§10), laid out generically:

- Bundle intact at `<install-root>/egm/` (skills, agents, resources,
  docs, LICENSE).
- One skill directory per skill at `<install-root>/custom-skills/egm-*/`
  (adapted `SKILL.md` per D3 + hand-written `skill.yaml` (D3 item 1)), with paths
  resolved against `<install-root>/egm/`.
- Gate-scan each adapted skill before use (D5) where the SkillSpector gate
  is available. Where the SkillSpector gate is unavailable on the target machine, the scan is run once on the authoring machine (invocation in D5) and the scores recorded in the install notes (defined in D5); an unscanned install is never acceptable — the scan happens somewhere before any install.

`<install-root>` is `~/workspace`, the directory holding the cloned repo and the installed skills. Path 2 is specified only in its one known form: bundle at `<install-root>/egm/`, skills at `<install-root>/custom-skills/egm-*/` (Muse's `custom-skills/` convention). There is no generic `<install-root>/skills/` layout: no harness is specified to read it, so no generic skills directory is prescribed as an install target. Example path strings a Path 2 skill contains: `~/workspace/egm/agents/design_critic.md` (the `~` form, per D3; the expanded form `/home/hatch/workspace/egm/...` never appears in a pilot adapted file). Path 2 is supported only for Muse. No generic harness skill-discovery convention is specified: a non-Muse harness has no supported Path 2 route until its skill directory and load mechanism are specified per harness in §9.2.

Install steps:

1. Clone upstream at the pinned SHA (`rm -rf <install-root>/egm-checkout && git clone https://github.com/google/elephant-goldfish-model.git <install-root>/egm-checkout && cd <install-root>/egm-checkout && git fetch --depth 1 origin e9e1f06a && git checkout e9e1f06a`).
2. Copy the bundle to `<install-root>/egm/` with `mkdir -p <install-root>/egm && cp -r <install-root>/egm-checkout/skills <install-root>/egm-checkout/agents <install-root>/egm-checkout/resources <install-root>/egm-checkout/docs <install-root>/egm-checkout/LICENSE <install-root>/egm-checkout/plugin.json <install-root>/egm/` — exactly the vendored set (§7); `site/`, `scripts/`, `tests/`, `adapters/`, per-host plugin manifests, and all other repo-root files are not copied.
3. Adapt the 7 `SKILL.md` files per D3 into `<install-root>/custom-skills/egm-*/`.
4. Hand-write the 7 `skill.yaml` files per D3 item 1.
5. Gate-scan each adapted skill (D5) where the gate is available, else per the §9.3 fallback (scan once on the authoring machine, scores in the install notes).
6. Verify per §10.6 Verification checks.

### 9.4 Decision matrix

| VM shape | Install path | Dispatch |
|---|---|---|
| Muse CLI present | Path 1 (plugin install) | Named `egm/egm-*` agents where spawn works; general-purpose fallback otherwise |
| Another supported harness (Claude Code / Codex / Antigravity) | Path 1 (native install) | Per-harness subagent tool |
| Headless / no harness plugin support | Path 2 (vendored skills, Muse only) | Harness subagent tool; general-purpose fallback |
| No subagent tool at all | — (do not adopt) | Review skills stop by design; same-context review is not EGM |

Cursor and OpenCode are experimental / unverified upstream (§9.2) and are not supported Path 1 routes until verified; a VM with only Cursor or OpenCode installed does not adopt (Path 2 is Muse-only); the headless row applies only where Muse is present without its CLI.

### 9.5 Verification (Environment A)

1. Offline pre-check (best-effort, not a gate): `muse plugins validate ./elephant-goldfish-model` (the cloned repo path from §9.2) (or the harness equivalent) reports the plugin valid with 7 skills and 10 agents. Before relying on `muse plugins validate`, `muse skills list --source plugin`, or `muse exec`, confirm each exists on the target harness — the three commands are `muse plugins validate`, `muse skills list --source plugin`, and `muse exec`, each probed with `<cmd> --help`; if any is absent, record it in the pilot log and proceed to the E2E fixture (step 3) as the verification gate. If the absent command is `muse exec` itself, the gate is the hand-exercised fixture run (step 3, hand exercise: the same fixture with approvals given by hand at each gate instead of simulated, which needs no `muse exec`); a VM shape with no `muse exec` and no hand-exercised run has no verification gate and does not pass. No step-1 command is cited to bundle `docs/muse.md` beyond install/approve — the doc does not assert upstream documents `validate`, `list --source plugin`, or `exec`.
   Warnings are expected (`multiple-manifests` means the installer picked the Claude manifest over the Codex one; Claude-only fields such as presentation metadata, `color`, and unknown agent frontmatter keys are ignored on Muse). Verification per harness: the harness's own plugin-list/validate command, taken from the bundle's `docs/harnesses.md` install table for that harness (this document does not assert a command it has not verified); the exact command used is recorded in the pilot log. Where a harness has no validate equivalent, verification is the E2E fixture run in §9.5 step 3.
2. Packaging checks: `/tmp/egm-venv/bin/pytest tests/unit` in the cloned repo root (the `elephant-goldfish-model` checkout from §9.2, i.e. `./elephant-goldfish-model/` from the §9.2 clone command); pass = exit code 0, all tests pass. `tests/unit` exists at the pinned SHA (upstream TESTING.md documents `pytest tests/unit` as the unit-test command); the venv binary is used because §9.1 installs pytest only into `/tmp/egm-venv`, and bare `pytest` is not on `PATH` on a fresh VM.
3. End-to-end acceptance: the upstream fixture recorded in the Testing playbook ([TESTING.md](https://github.com/google/elephant-goldfish-model/blob/main/TESTING.md), 'Harness test record', Muse row, 2026-10-30) — fixture design `muse-wonder-1.0` (the upstream fixture name for the brainstorm → draft → review sequence; a line-count design — the fixture's design subject is a line-counting tool, per the upstream Muse row in TESTING.md — and the draft stage produces a design document for that tool). The prompt text is NOT in TESTING.md — verified at the pinned SHA, TESTING.md records the fixture name, the Muse row, and the run summary, but no prompt text — so the prompt is specified here, not by reference: 'Run the EGM brainstorm → draft → review sequence (fixture `muse-wonder-1.0`, a line-count design) against the installed plugin/skill cache only, in the temporary workspace, with approvals simulated up front: brainstorm the design, draft it, then run an uninterrupted review. Name `docs/muse.md` in the session prompt.'. `TESTING.md` lives at the upstream repo root and is NOT vendored. Before the run, write that prompt to `/tmp/egm-e2e-<shape>/prompt.md` (`<prompt-file>`). Run once per VM shape. `muse-cli` shape: run headless via `muse exec --prompt /tmp/egm-e2e-muse-cli/prompt.md` in the temporary workspace (`/tmp/egm-e2e-muse-cli/`), approvals simulated up front per the fixture, against the installed cache only — 'installed cache' means the harness's installed plugin/skill cache on that VM (the plugin installed per §9.2), not the upstream checkout — prompt naming `docs/muse.md`, approvals simulated up front: brainstorm → draft → uninterrupted review. `other-harness` shape: run the same fixture with that harness's headless run command, named in the pilot log; if the harness has no headless run command, the shape has no E2E gate and does not pass. `headless` shape: there is no harness CLI to run the fixture — the E2E fixture does not apply; the shape's verification is the §10.6 checks alone, and 'installed cache' for Path 2 means the installed skills under `<install-root>/custom-skills/egm-*/` (per §9.3). The step-1 hand-exercise fallback does not save the headless shape: there is no harness to hand-exercise. Pass, per stage: brainstorm produces `concepts_brief.md` in the workspace; draft produces `design_draft.md` in the workspace (the draft filename used by the bundle's `docs/claude.md` and `docs/muse.md`); review produces a filed review report in the workspace, named `<date>-muse-wonder-1.0-review.md` (`<date>` is the run date, `YYYY-MM-DD`). 'Uninterrupted review' means the review stage runs with approvals simulated up front (no human turn), as in the upstream 2026-10-30 run. Hand exercise (first time per shape): run the same fixture with approvals given by hand at each gate instead of simulated, and record which gates fired in the pilot log (`~/workspace/plans/<date>-egm-pilot-log.md`).
4. Drift check: re-run the fixture after any harness upgrade; named-spawn availability and tool-projection behavior vary by version. Path 2 applies the same checks as §10.6 Verification checks: every `agents/...` and `resources/...` reference resolves, every `skill.yaml` parses with matching `name`, gate-scan scores recorded. The pilot verifies the Muse routing line's target (`<bundle>/docs/muse.md`) resolves in each environment. Snapshot (Environment A, per D6): before dispatch, snapshot by content hash with the D6 command — Path 1 scope is the cloned repo, the installed plugin dir, and the temp workspace (`/tmp/egm-e2e-<shape>/`); Path 2 scope is `<install-root>/egm/`, `<install-root>/custom-skills/egm-*/`, and the temp workspace. Diff once after the round; any unexpected modification fails the round (D6). Memory/DB paths are out of scope in both environments (D6 residual).

## 10. Environment B — current Muse environment (this VM)

### 10.1 Constraints (verified)

- No `muse` CLI (`command not found`) — Path 1 is unavailable; Path 2
  (vendored skills) is the only route.
- Skills are discovered from `~/workspace/custom-skills/` (one directory
  per skill, `SKILL.md` + `skill.yaml`); dispatch is `subagent.spawn`.
- `subagent.spawn` is the Muse tool that spawns a fresh-context subagent from a brief (persona file path + prompt); it takes the brief items listed in §10.3. It has no tool-restriction parameter (see D6).
- Standing rules apply: SkillSpector gate before install (D5); Conventional Commits for any AEP PR — `type(scope): description` for commits and PR titles, branches `type/scope-short-description` (AEP `AGENTS.md`); identity scrubbing in externally visible content — synthetic/bot identities only, never the user's personal name.

### 10.2 Layout

```
~/workspace/egm/                          # pristine bundle, verbatim upstream
  skills/ agents/ resources/ docs/ LICENSE plugin.json
  README.md       # local pin record, literal template (four lines): `Upstream: https://github.com/google/elephant-goldfish-model`, `Pinned SHA: e9e1f06a`, `Snapshot date: YYYY-MM-DD`, `License: Apache-2.0`. Written at install time; re-written on every re-sync (trigger: any upstream re-vendor or local adaptation change, per the §10.2 cadence).
~/workspace/custom-skills/egm-*/          # one dir per skill (7 total)
  SKILL.md        # adapted per D3: `~/workspace/egm/` paths,
                  #   Muse routing line, no other content changes
  skill.yaml      # hand-written per D3 item 1
```

(`<install-root>` = `~/workspace` per §9.3; skills live in `custom-skills/`, not the generic `skills/`.)

Canonical direction, per artifact: the local adapted skills are canonical for wrapper content — sync runs local→repo ('live', see §1.1 Glossary). Sync steps (local→repo direction only):

1. Diff local `custom-skills/egm-*/` against repo `skills/egm-*/` using the §10.5 step 4 normalize-then-diff (the `sed` runs on temp copies, per-skill loop — a raw diff would show every adapted `SKILL.md` as changed, because local files contain `~/workspace/egm/...` and repo wrappers contain `../../reference/elephant-goldfish-model/...`).
2. Copy the normalized temp copies (not the verbatim local files) into the repo wrappers, applying the same `~/workspace/egm` → `../../reference/elephant-goldfish-model` translation — copying local files verbatim would write local paths into the repo wrappers and break them.
3. Regenerate the manifest (`scripts/check_skills_manifest.py --root skills --write` from the repo root).
4. Verify with the §10.5 step 4 normalize-then-diff check.
5. Commit per Conventional Commits.

Owner: the agent running the sync (the Elephant / main agent session that owns the change) — not a separate role. The bundle flows the other way: upstream → repo tree → local — the repo's `reference/elephant-goldfish-model/` is the reference copy, and any re-vendor replaces the local bundle wholesale from the repo tree. The local bundle is therefore not canonical for personas and standards; it is a working copy of the repo reference, which is itself a copy of upstream at the pinned SHA. Cadence: on every upstream re-vendor and on any local adaptation change. Each sync re-runs the YAML-parse + name-match check for all 7 `skill.yaml` files. Owner: the agent running the sync; the sync is verified by the normalize-then-diff check in §10.5 step 4. The bundle stays pristine so re-sync is a clean replace; the adapted copies are the loadable skills — never copy personas and standards per-skill (bloat, drift risk). Sync record (see §1.1 Glossary). The D1 staleness note and the C6 record are written there. Continuous detection between syncs: repo-side drift (wrappers vs bundle) is covered by check C2, whose resolve loop runs as a step in the `vendor-integrity` CI job on every PR (it reads only the repo tree). Local↔repo drift is detected only at sync time; the cadence bounds the window — a local adaptation change and its sync land in the same change, so no local change sits unsynced past its own PR, and a re-vendor triggers a sync in the same PR. Maximum tolerable drift window: see §1.1 Glossary.

### 10.3 Dispatch

Roles & dispatch:

| Role | Actor |
|---|---|
| Elephant | The session that owns the design doc and runs the loop (Environment B: the main agent; Environment A Path 1: the harness session that installed the plugin). |
| Goldfish | One fresh-context subagent per reviewer (Environment B: `subagent.spawn` with a read-only brief; Path 1: named `egm/egm-*` agent where spawn works, else the general-purpose fallback). |
| Driver | The Elephant acting in its driver capacity: checks every cited line exists in the target at the stated range and the named standard is the assigned one, enforces the readiness/section-approval gates, and stops and asks the owner on cap/churn. |
| Synthesizer | The `agents/synthesizer.md` role; in Environment B it is replaced by direct dispatch from the Elephant, with the Elephant consolidating findings; in Path 1 it is used where the harness nests subagents. |

Direct dispatch from the Elephant is by design — flat dispatch keeps attribution simple; this is a design choice, not a platform limit: depth-2 spawning — a subagent spawning its own subagent — works in this environment.

#### 10.3.1 Reviewer brief

- Reviewers: `subagent.spawn` with the persona file path and the verbatim prompt in the brief. Each reviewer's report must cite the persona by name, the target's line numbers for every finding, and the standard applied. The driver checks every cited line exists in the target at the stated range and the named standard is the assigned one; a report failing either check is incomplete — re-run once, then record the reviewer not run. The memory prohibition is enforced by the brief (it forbids retrieval) and checked by check (c): the Elephant at consolidation reads each finding's rationale and flags any that cites memory or conversation content (a quote of, or a paraphrase that depends on, prior context rather than the target document and its GoldfishContext); a flagged finding is discarded and the reviewer is not re-dispatched. Three checks are performed once each against the filed reports: (a) every cited line exists in the target at the stated range — performed by the driver at intake; (b) the named standard is the assigned one — performed by the driver at intake; (c) no finding's rationale cites memory or conversation content — performed by the Elephant at consolidation (it holds the conversation context, so it can judge whether a rationale quotes or paraphrases prior context). §10.5 step 3's questions ('did reviewers actually read persona/standards/target? were findings evidence-backed?') are answered by those three checks, not by additional checks. Wait for actual completion before consolidating; propagate failures and timeouts.
#### 10.3.2 Readiness and section-approval gates

Approval gates: preserve the skill's readiness and section-approval gates. Tool unavailability is not approval — ask one plain-text question and wait for the answer where no structured question tool exists.

Readiness gate (fires before a review loop starts): the target document exists, reviewers and standards resolve to existing files, and GoldfishContext is provided (an empty list counts as provided only for a self-contained target; a design-doc review with external references must list them — this document's pilot supplied the companion doc (`~/workspace/plans/2026-11-06-egm-adoption-neurostrata.md`), README (`~/workspace/autonomous-engineering-platform/skills/README.md`), and repo clone (`~/workspace/autonomous-engineering-platform`)). The Elephant runs this check before asking the gate question, with the brief's absolute paths substituted for the placeholders:

```
for p in <target> <persona-paths...> <standard-paths...> <goldfishcontext-paths...>; do test -f "$p" || echo "MISSING: $p"; done
```

Expected output: no `MISSING` lines; any `MISSING` line fails the readiness gate. Readiness-gate question (literal): 'Target document and reviewer panel verified — proceed with the review loop?' (options: proceed / stop). GoldfishContext: see §1.1 Glossary. Section-approval gate (fires after each drafted section in `egm-draft`): the `egm-draft` question, quoted verbatim — 'Drafted [Section Name] in design_draft.md. Please review. How would you like to proceed?' with options 'Approve [Section Name] and proceed to next section' / 'Request revisions to [Section Name] (via inline comments or write-in)'. Where no structured question tool exists, ask the same question as one plain-text question and wait for the answer. 'Approvals simulated up front' (upstream 2026-10-30 fixture) means the headless run pre-approved every gate instead of waiting for a human turn — interactive gates are therefore untested upstream and must be exercised by hand the first time (§9.5 step 3).
#### 10.3.3 Overlap with existing tools

- Overlap: EGM formalizes what three existing instruments do informally. `grilling` (`~/workspace/custom-skills/grilling/` — adversarial interview skill: relentless questioning of a plan or decision) and `roundtable_review` (`~/workspace/custom-skills/roundtable_review/` — multi-agent debate panel with claim verification and a judge's verdict) are single-session review tools with no written standard and no configured reviewer panel. The Ralph per-iteration verifier (Ralph is the autonomous loop system in `~/workspace/ralph/`; the verifier is an independent, non-blocking verification subagent at the end of every iteration, per the standing loop rule recorded in `~/workspace/custom-skills/ralph_loop/SKILL.md`, 'Independent verification (standing rule, 2026-10-17)') checks implementation against acceptance criteria, not design against a standard. EGM adds a written standard, a configured reviewer panel, and fresh-context reviewers. See the roundtable_review vs EGM delta table in §5. Named targets: `egm-drift-report` — the `skills/README.md` attribution table vs. the `skills/` tree (a verifiable drift surface: rows can be missing, stale, or point at removed skills). `egm-bootstrap` — `reference/` tree documentation (each tree currently carries only a `PROVENANCE.md`; no per-tree README describing what the tree is for). Both skills are deferred to Phase 1 with these named targets. Phase 1 runs `egm-drift-report` once against its named target (§11) and runs `egm-bootstrap` once against the `reference/` tree documentation, each producing a dated finding or a clean bill. Selection rule: use EGM when the artifact is a design document (or an upstream PR) that needs a written standard and a configured panel with filed reports; use `grilling` or `roundtable_review` for a fast single-session challenge with no filed report; use the Ralph verifier for implementation-against-acceptance-criteria checks, not design review; use `brainstorming` / `writing-plans` for pre-creative work and implementation-task planning, and `egm-brainstorm` / `egm-draft` only when the multi-reviewer panel and written standards are needed for those stages.

#### 10.3.4 Brief contents and failure handling

Each reviewer brief contains (1) persona file absolute path, (2) target file absolute path + line range, (3) assigned standard absolute path, (4) GoldfishContext paths, (5) the read-only instruction, (6) the required report shape (severity, line numbers, discrepancy, rationale). The Elephant consolidates into a flat FindingsList with stable ids (`<reviewer>-<round>-<n>`) and writes the report artifact before any resolution. The Elephant merges duplicate findings (same target lines + same discrepancy), normalizes severity to the assigned standard, and assigns stable ids (`<reviewer>-<round>-<n>`); overlaps are recorded in the report. Any severity change on consolidation is recorded with its original severity, new severity, and reason; a severity downgrade with no recorded reason is a defect in the report, not a judgment call. The verbatim prompt is the Delegation section of the bundle's `skills/egm-review-loop/SKILL.md` ('## Delegation'; line 34 in the vendored file at the pinned SHA), quoted here in full, followed by the six brief items in the literal template below. Delegation (verbatim): 'A Goldfish runs in a fresh context with no conversation history. Spawn each subagent with your harness's subagent tool (Antigravity: `invoke_subagent`; Claude Code: `Agent`; Codex: `spawn_agent`). Each subagent is defined in `agents/<file>.md`, and its frontmatter `name` (for example `egm-zoom-out`) is the subagent type to request where your harness registers named subagents. Otherwise spawn a general-purpose subagent and tell it to read that persona file first. Pass the prompt verbatim and wait for the report. If your harness cannot nest subagents, use direct dispatch instead of the synthesizer. See `docs/harnesses.md`. If your harness has no subagent tool, stop and tell the user: a review in the same context is not a Goldfish review.' Brief template (literal, filling the six items in order): 'Review the target as a Goldfish reviewer. (1) Persona: read <persona-file-absolute-path> first and follow it. (2) Target: <target-file-absolute-path>, lines <start>–<end>. (3) Standard: apply <standard-file-absolute-path>. (4) GoldfishContext: read <paths>. (5) Read-only: do not write to any file and do not read or write memory; report findings only. (6) Report shape: file one report citing the persona by name, the target line numbers for every finding, and the standard applied, with severity, discrepancy, and rationale per finding, and, for any file saved from a URL, that file's source URL.' Enforcement of the read requirement is the line-existence check, and of the memory prohibition is check (c) in §10.3.1: every cited line must exist in the target at the stated range, and the report must name the standard applied. Failure handling: a reviewer that times out (a report arriving more than 30 minutes after dispatch; see §10.4), fails, or returns no report is retried once, then recorded not run — never counted as zero findings. Timeout: set from pilot evidence (see Loop bounds below). The gate question is the `egm-draft` section-approval question (gate question as quoted above in the section-approval gate definition). No `subagent.spawn` tool-restriction parameter exists on Muse — the D6 mitigation is the brief wording plus the post-run snapshot diff, stated explicitly rather than implied. Artifacts: each reviewer files one report at `~/workspace/plans/<date>-<topic>-<reviewer>-r<n>.md` (pilot; in the PR for AEP) before consolidation; the review report (`~/workspace/plans/<date>-<topic>-goldfish-review[-rN].md` in the pilot; in the PR for AEP) is the FindingsList — the consolidated flat list, one entry per finding with the fields above. The resolve report (`~/workspace/plans/<date>-<topic>-goldfish-resolve[-rN].md`) records one disposition per finding (CONTEST / ESCALATE / DECLINE / SETTLED, §10.4). Loop state between turns is these two files plus the pilot log: if the Elephant session ends mid-round, resume by re-reading them and re-dispatching only reviewers with no filed report at the path above; no loop state lives only in the session.

### 10.4 Loop bounds

Bounds per review-loop run: at most 5 rounds (the upstream cap); at most 5 reviewers per round (the panel named in §7: design_critic, structural, implementation_readiness, comprehension, zoom_out); converged = two consecutive clean rounds (no unsettled Blocker or Major); on cap or churn the driver stops and asks the owner one question, literally. On cap: 'The loop hit its cap (5 rounds) with unsettled findings — how do you want to proceed?' (options: accept and proceed / continue past the cap / return to drafting). On churn: 'The loop hit churn at round <n> — a new finding restates a finding fixed in an earlier round — how do you want to proceed?' (options: accept and proceed / continue the loop / return to drafting). Timeout: 30 minutes per reviewer for the pilot (interim bound; no pilot log with per-reviewer elapsed times exists yet, so this bound is set now and the pilot log records actual elapsed times). Enforcement: `subagent.spawn` has no timeout parameter and no in-flight kill, so the timeout is enforced at acceptance — the driver records the dispatch wall-clock time, and a report arriving more than 30 minutes after dispatch is treated as timed out (retried once, then recorded not run); a late report is never accepted as on time. Phase 1 interim default: the pilot's 30-minute timeout carries forward; the pilot log's token actuals set the Phase 1 token budget via §14 decision 6, and Phase 1 does not start until decision 6 sets it. During the pilot, cost is bounded only by spawns × time (at most 25 spawns × 30 minutes); no token cap and no maximum target size exist yet. The decision-6 per-reviewer token cap, once set, becomes the size bound for Phase 1 (token cost scales with target size, so the cap is the size bound); no separate maximum target size is set. Overflow: if a target document alone exceeds the per-reviewer token cap, the reviewer is recorded not run for that reviewer — never truncate the target, never breach the cap — and the round is not clean; the driver records the overflow in the pilot log. Cost: each phase gate records reviewer count, rounds run, and tokens spent (per reviewer, in the pilot log); cost is measured in reviewer spawns (max 25 per run) and tokens. Interim pilot budget: at most 25 spawns × 30 minutes = 12.5 reviewer-hours per run; the interim pilot token cap is set by owner ruling before the next pilot run (see §6); the pilot log's token actuals set the Phase 1 token budget via §14 decision 6. 'Unsettled' (see §1.1 Glossary). Dispositions (recorded by the Elephant in the resolve report): CONTEST — the finding is inaccurate, with checkable evidence cited (a file and symbol, or a decision recorded in the document); ESCALATE — the finding is inaccurate but the evidence is outside every file the reviewer could read (an owner decision or convention), so it goes to the owner; DECLINE — the finding is recorded with no fix (cosmetic, or out of scope for this document); SETTLED (see §1.1 Glossary). Nits are non-blocking by design: a round is clean when no Blocker or Major is unsettled, regardless of Nits — but every Nit must still be recorded in the resolve report with a disposition (fix / decline, with a reason). An undispositioned Nit is a defect in the resolve report, not a blocker of clean. Churn: a new finding at the scope of an applied fix whose revert would resolve it, or a round whose unsettled findings substantially restate the previous round's fixed findings — 'substantially restate' (see §1.1 Glossary). Threshold: the first occurrence — on churn the driver stops and asks the owner the churn question above.

### 10.5 Verification (Environment B)

1. Gate-scan all 7 adapted skills; record scores.
2. Fetch upstream at the pinned SHA (`rm -rf /tmp/egm-upstream && git clone https://github.com/google/elephant-goldfish-model.git /tmp/egm-upstream && cd /tmp/egm-upstream && git fetch --depth 1 origin e9e1f06a && git checkout e9e1f06a && git rev-parse HEAD` must print exactly `e9e1f06aa4e26e95cd4ed37210a0632202c429e9` (the full form of the `e9e1f06a` pin)). Then `diff -rq /tmp/egm-upstream/skills <bundle>/skills && diff -rq /tmp/egm-upstream/agents <bundle>/agents && diff -rq /tmp/egm-upstream/resources <bundle>/resources && diff -rq /tmp/egm-upstream/docs <bundle>/docs && diff -q /tmp/egm-upstream/LICENSE <bundle>/LICENSE && diff -q /tmp/egm-upstream/plugin.json <bundle>/plugin.json` — expecting zero differences (where `<bundle>` is `~/workspace/egm/` locally, `reference/elephant-goldfish-model/` in AEP). Excluded from the comparison by design: `site/`, `scripts/`, `tests/`, `adapters/`, per-host plugin manifests (`.claude-plugin/`, `.codex-plugin/`, `.cursor-plugin/`), and all other repo-root files. The adaptation layer lives in `custom-skills/egm-*/`, not in the bundle, and is verified separately by the sync check in step 4. The diff command enumerates the included set; any repo-root file it does not name is excluded.
3. Pilot: run `egm-review-loop` + `egm-review` once against the Phase 0 pilot target (§14 decision 2). Invocation in Environment B: the Elephant invokes the skills explicitly via `subagent.spawn` briefs built per §10.3 (the pilot ran this way — the skills carry `disable-model-invocation: true` and are user-invocable only). Target: the content hash recorded in the pilot log before dispatch — `sha256sum <target>` output plus the recording date (`YYYY-MM-DD`) — (§14 decision 2); `~/workspace/plans/` is not a git repository, so no commit SHA exists for the pilot target. The Elephant audits its own consolidation in the same pass: it verifies each recorded severity change against the filed per-reviewer report (original severity matches, reason present) and that no severity change went unrecorded. Checks (a) and (b) are performed once, by the driver at intake; check (c) is performed once, by the Elephant at consolidation. No audit subagent is spawned: the check is a deterministic comparison of two artifacts the Elephant already holds (the filed per-reviewer reports and the consolidated report), and a fresh-context agent would add non-determinism to it. The §6/§10.4 spawn bound (at most 25 spawns per run) counts reviewer spawns only, and no other spawn is made by the loop.
4. Sync check: copy the seven local `custom-skills/egm-*/SKILL.md` files and the seven `skill.yaml` files to a temp dir and compare per skill, as one compound command (run as a single invocation — `$tmp` is assigned and used inside it — with `<repo-root>` the AEP repo root, `~/workspace/autonomous-engineering-platform`):

```
tmp=$(mktemp -d) && cd ~/workspace/custom-skills && cp --parents egm-*/SKILL.md egm-*/skill.yaml "$tmp"/ && sed -i 's|~/workspace/egm|../../reference/elephant-goldfish-model|g' "$tmp"/egm-*/SKILL.md && cd ~/workspace/autonomous-engineering-platform && for s in "$tmp"/egm-*/; do diff -r "$s" "skills/$(basename "$s")" || exit 1; done
```

Expecting zero differences. (The `sed` now names its file operand, `"$tmp"/egm-*/SKILL.md`; the loop iterates the temp dir's own subdirectories, so it executes from any starting directory once the explicit `cd` to the repo root runs.) (this diffs `skill.yaml` content too, not just `SKILL.md`). The second `sed` for the expanded `/home/hatch/workspace/egm` form is deleted: D3 states the expanded form never appears in a pilot adapted file, so the expression is dead. Also assert every `agents/...` and `resources/...` reference in each adapted `SKILL.md` resolves to an existing file at the installed location (verified by §10.6 check C1). Also resolve every `../../reference/...` target in the repo wrappers against the repo tree (```
for f in skills/egm-*/SKILL.md; do grep -oE '\.\./\.\./reference/[A-Za-z0-9_./-]+' "$f"; done | sed 's/\.$//' | sort -u | while read -r p; do test -e "reference/${p#../../reference/}" || echo "MISSING: $p"; done
``` — expected output: no `MISSING` lines); this is check C2, and the normalize-then-diff alone does not run it. The sync check covers `skill.yaml` by content diff (above) and by re-validation on every sync (YAML parses, `name` matches the `SKILL.md` frontmatter `name`); a mismatch fails the sync. A local file that already contains the `../../reference/…` form needs no rewrite — both `sed` expressions are no-ops on it (neither pattern matches) — but a file mixing both forms fails the check and must be normalized by hand.

### 10.6 Verification checks

§10.5 steps 1–4 are the procedure; the checks below (C1–C7) are the normative test list.

1. **C1 — Happy path:** for each of the 7 adapted `SKILL.md` files, every `agents/...`, `resources/...`, and `docs/...` reference resolves to an existing file or directory at the installed location (check by running, from the install location — Environment B: `<skills-dir>` is `~/workspace/custom-skills`, `<bundle>` is `~/workspace/egm`; Path 2: `<install-root>/skills` and `<install-root>/egm` respectively — `for f in <skills-dir>/egm-*/SKILL.md; do grep -oE '(agents|resources|docs)/[A-Za-z0-9_./-]*' "$f"; done | sed 's/\.$//' | sort -u | while read -r p; do test -e "<bundle>/$p" || echo "MISSING: $p"; done` — expected output: no `MISSING` lines. The pattern has no extension requirement, so bare directory references such as `agents/` and `resources/document_standards/` are covered; a trailing prose period is stripped before the check. 'By hand' is not an accepted method; a single dangling reference fails the check). Also assert, per adapted `SKILL.md`, the Muse routing line is present and no upstream-relative reference remains (run, from the install location, with `<skills-dir>` as in the C1 loop above):

```
for f in <skills-dir>/egm-*/SKILL.md; do grep -q 'In Muse, read .*docs/muse\.md first\.' "$f" || echo "MISSING routing line: $f"; ! grep -qE '(\.\./\.\./docs/|\$\{CLAUDE_PLUGIN_ROOT\}/docs/)' "$f" || echo "UPSTREAM-RELATIVE reference remains: $f"; done
```

Expected output: no `MISSING` / `UPSTREAM-RELATIVE` lines.
2. **C2 — Edge case:** a wrapper `../../reference/...` target that does not exist fails the check (procedure: the §10.5 step 4 resolve loop — ```
for f in skills/egm-*/SKILL.md; do grep -oE '\.\./\.\./reference/[A-Za-z0-9_./-]+' "$f"; done | sed 's/\.$//' | sort -u | while read -r p; do test -e "reference/${p#../../reference/}" || echo "MISSING: $p"; done
``` — expected output: no `MISSING` lines).
3. **C3 — `skill.yaml` parses:** every `skill.yaml` parses as YAML and its `name` matches the `SKILL.md` frontmatter `name` (procedure: run with the §9.1 venv interpreter, `/tmp/egm-venv/bin/python3`, on the fresh VM — the literal loop below uses it; on Environment B, use the system `python3` only after `python3 -c "import yaml"` exits 0, and record the interpreter path in the pilot log:

   ```
for f in <skills-dir>/egm-*/skill.yaml; do skill="${f%/skill.yaml}/SKILL.md"; a=$(/tmp/egm-venv/bin/python3 -c "import yaml,sys; print(yaml.safe_load(open(sys.argv[1]))['name'])" "$f"); b=$(sed -n '/^---$/,/^---$/p' "$skill" | sed -n 's/^name: *//p' | head -1); [ "$a" = "$b" ] || { echo "MISMATCH: $f ($a) vs $skill ($b)"; exit 1; }; done
   ```

   Expected: exit 0, no `MISMATCH` lines).
4. **C4 — Gate-scan scores:** gate-scan scores recorded for all 7 adapted skills.
5. **C5 — Pilot completes:** the pilot review completes with all reviewers run (0 not run).
6. **C6 — Sync `skill.yaml`:** on every sync, all 7 `skill.yaml` files parse as YAML and their `name` fields match the `SKILL.md` frontmatter `name` (procedure: same as C3; recorded in the sync record).
7. **C7 — Pin record:** `~/workspace/egm/README.md` exists and contains the upstream URL, the pinned SHA (equal to the §14 decision 1 pin), the snapshot date, and the license (Apache-2.0).

The pilot verifies the Muse routing line's target (`<bundle>/docs/muse.md`) resolves in each environment.

## 11. Rollout

| Phase | Scope | Gate |
|---|---|---|
| 0 — Pilot (local only) | `egm-review-loop` + `egm-review`, bundle under `~/workspace/egm/`, 2 adapted skills | Gate-scan pass; pilot review completes with all reviewers run (0 not run), report filed, findings categorized; fails on any reviewer not run or no filed report |
| 1 — Full local | Remaining 5 skills; `egm-drift-report` run once against the named target in the Gate column; `egm-bootstrap` run once against `reference/` tree documentation (see §10.3.3) | All 7 gate-scanned; drift report names its target in advance (`skills/README.md` attribution table vs. `skills/` tree) and produces a dated finding, or a clean bill stating the table's row coverage — every skill in the `skills/` tree accounted for as a row, a stated absence, or a stated mismatch, with the counts (rows compared vs skills in the tree) recorded; fails when no target is named. The drift report is filed at `~/workspace/plans/<date>-skills-attribution-drift.md` (the §7 pilot convention). |
| 2 — AEP PR | `reference/elephant-goldfish-model/` + 7 `skills/egm-*` wrappers + scope/manifest/attribution updates — only after the §14 decision 5 pilot-value ruling; without it, Phase 2 installs the 2 review skills only. Branch: `chore/reference-vendor-elephant-goldfish-model` (per the repo's `type/scope-short-description` rule). | CI green (vendor-integrity + skills-freshness); Conventional Commits; owner review |
| 3 — General VM | Path 1 install guide + Path 2 vendored layout validated on a fresh VM. Fresh VM: a general-purpose Linux VM meeting §9.1 prerequisites (`git` ≥ 2.43.0, `python3` ≥ 3.12.3, `pytest` per §9.1, one supported harness CLI). Provisioning: install prerequisites per §9.1 (Ubuntu 24.04 image; distro packages `git`, `python3`, `python3-venv`; harness CLI per vendor instructions), clone upstream at the pinned SHA, install per the §9.2/§9.3 path in the §9.4 decision matrix, run the §9.5 verification. | Pass: E2E fixture passes on the fresh VM. Fail: the fixture fails, or Phase 3 is unexecuted after the §14 decision 3 ruling without that ruling recording 'documented-but-unexecuted'. An unexecuted Phase 3 passes only by an explicit ruling, never by default |

**Phase 3 gate record (2026-11-07):** the owner ruled (§14 decision 3) to retain §9 as designed — no appendix move. Phase 3 was partially executed the same day in an emulated fresh-VM rootfs: the headless (Path 2) shape passed §9.1 provisioning, the §10.6 verification checks, the D5 gate scans, the D6 snapshot, and the §9.5 step 2 packaging tests (342 tests, 0 failures, after the §9.1 Node.js gap recorded in §9.1 was closed). The muse-cli shape's E2E fixture remains unexecuted and is recorded documented-but-unexecuted by this ruling, so the gate's fail condition (an unexecuted Phase 3 without an explicit ruling recording it) is not triggered.

Priority order within each phase follows value, not alphabetical order:
`egm-review-loop` + `egm-review` first (extend the existing review
discipline), then `egm-brainstorm`, `egm-draft`, `egm-resolve`,
`egm-drift-report`, `egm-bootstrap`. Rationale: review first because it gates everything else (it extends the existing review discipline and its pilot produces the evidence for the remaining skills); brainstorm, draft, and resolve next because they form the design pipeline (idea → document → findings); drift-report and bootstrap last because they need a reviewed design corpus to work against — drift detection needs design docs, and bootstrap needs scoped targets (rationale in this paragraph). No bare "Issue N" references remain in the document; upstream GitHub issues are cited only with repo + link (e.g. [#252](https://github.com/google/elephant-goldfish-model/issues/252)).

Rollback: if the pilot fails (a reviewer not run, or the owner rules no marginal value), roll back by deleting the 2 adapted skill dirs and the local bundle (`~/workspace/custom-skills/egm-*/`, `~/workspace/egm/`), with no AEP PR; record the outcome in the pilot log. Phase 2 rollback (after merge): revert the merge commit (`git revert -m 1 <merge-sha>`) in a revert PR, which removes the bundle, the 7 wrappers, the scope/manifest/attribution updates, and the CI block together; a partial revert is not permitted.

### 11.1 Phase 0 file-change list

Created: `~/workspace/egm/` bundle (90 files at the pinned SHA, per §11.3); plus the locally written `~/workspace/egm/README.md` (a 91st file, per the §10.2 template; not part of the 90-file upstream bundle); `~/workspace/custom-skills/egm-review/` + `~/workspace/custom-skills/egm-review-loop/` (each `SKILL.md` + `skill.yaml`); pilot report (`~/workspace/plans/<date>-<topic>-goldfish-review.md`) + pilot log (`~/workspace/plans/<date>-egm-pilot-log.md`, per D5). Modified: none. Deleted: none.

### 11.2 Phase 1 file-change list

Created: the remaining 5 `~/workspace/custom-skills/egm-*/` dirs (each `SKILL.md` + `skill.yaml`); drift report at `~/workspace/plans/<date>-skills-attribution-drift.md` (the §11 table's filename for the Phase 1 named target — the `<topic>=skills-attribution` instance of the §7 `<date>-<topic>-drift.md` pattern; `<date>` is the run date, `YYYY-MM-DD`). Modified: none. Deleted: none.

### 11.3 Phase 2 file-change list

Created: `reference/elephant-goldfish-model/` bundle, 90 files at the pinned SHA (per-skill files under `skills/`, `agents/`, `resources/`, `docs/`, `LICENSE`, `plugin.json` — the full path list is the generated `.github/vendor-elephant-goldfish-model.sha256`); `.github/vendor-elephant-goldfish-model.sha256`; `reference/elephant-goldfish-model/PROVENANCE.md`; `skills/egm-brainstorm/`, `skills/egm-draft/`, `skills/egm-review/`, `skills/egm-resolve/`, `skills/egm-review-loop/`, `skills/egm-bootstrap/`, `skills/egm-drift-report/` (each `SKILL.md` + `skill.yaml`, 14 files). Modified: `.github/skills-sync-scope.txt` (7 lines under `[skills]`, exactly: `egm-brainstorm`, `egm-draft`, `egm-review`, `egm-resolve`, `egm-review-loop`, `egm-bootstrap`, `egm-drift-report`), `.github/skills-manifest.sha256` (regenerated via `scripts/check_skills_manifest.py --root skills --write` run from the repo root), `skills/README.md` (7 attribution rows; Skill column values are the same 7 skill names, Source `google/elephant-goldfish-model`, License `Apache-2.0`, Notes per D4), `.github/workflows/ci.yml` (tenth `vendor-integrity` `run:` block — literal block in D4, inserted after the `humanizer` block — plus an eleventh `run:` block running the C2 wrapper-reference resolve loop from the repo root, literal block in D4). Deleted: none.

Two-skill variant (no §14 decision 5 ruling): the bundle, `.github/vendor-elephant-goldfish-model.sha256`, `PROVENANCE.md`, and the tenth `vendor-integrity` block land unchanged (D2: the bundle moves as one unit); only the wrappers shrink to `skills/egm-review/` + `skills/egm-review-loop/` (4 files), the scope file gains 2 lines, and `skills/README.md` gains 2 attribution rows. The manifest step is unchanged. Allowlist: the allowlist is the generated `.github/vendor-elephant-goldfish-model.sha256` itself (a Created file in this PR, generated by the D4 command from the pinned SHA); the `vendor-integrity` job enforces it. The 90-file total above is a count, not a path list — no prose inventory of the 90 paths is maintained, because the generated hash file is the single source of truth for the vendored set.

## 12. Security notes

Security notes (risks & mitigations live in §6; this section holds the security implications).

- Adapted skill content (`SKILL.md` files) is pure markdown: no network calls, no config modification, no credential access, no auto-updater. The vendored bundle also contains non-markdown files (`agents/openai.yaml`, `test_scenarios.yaml`, `assets/icon.svg`, `references/*.json`, `docs/assets/*.svg`); the pure-markdown claim covers the adapted skills only. SHA integrity proves provenance against the pin, not safety — bundle non-markdown files are content-reviewed at vendor time per D5. The one exception is
  `egm-review-loop` saving user-supplied URL pages as local files before
  review — user-directed only.
- The Muse read-only caveat (D6) is the principal risk in both
  environments: treat Goldfish reviewers as unprivileged in intent but able to write in fact — assume they can write to the filesystem and to memory unless the harness proves otherwise. Give a reviewer only the tools its brief names: the read-only brief names no write tool, and no write tool is ever added to a reviewer brief; enforcement is the post-run snapshot diff in D6 (snapshot before dispatch, diff once after the round; any unexpected modification fails the round).
- `egm-review-loop`'s URL fetching is the only network touchpoint; scope it to URLs the user supplied for that review, and bound it: https only (no http, no other schemes); each fetched page capped at 1 MB; saved under a dedicated temp dir (`/tmp/egm-urls-<run>/`, removed after the review); fetched content is treated as data, never executed; non-HTML content types are rejected. Enforcement: the Elephant audits the temp dir after the round — every saved file is ≤1 MB (`find /tmp/egm-urls-<run>/ -type f -size +1M` must print nothing), every recorded source URL uses https, every saved file is HTML (`file -b --mime-type <file>` must print `text/html`) — and removes `/tmp/egm-urls-<run>/` after the round even if a reviewer fails or is recorded not run; a violation fails the round and is recorded in the pilot log. The audit is post-hoc: a fetch that already happened cannot be unfetched, so these bounds are enforced by the audit, not by the fetch itself.
- Do not vendor `scripts/` (packaging/install code) or `site/` into either
  environment; the install path in Environment A uses the harness's own installer, not EGM's scripts.
- Residual risk: a reviewer write is detected only after it happens (D6); detection does not prevent the write, and memory/DB paths are not snapshotted. Memory/DB writes are unrecoverable: no snapshot is taken of the NeuroStrata store, and a memory write cannot be undone.

## 13. Non-goals

Non-goals are stated with the goals in §2.

## 14. Open decisions (owner)

1. **Pin SHA (ratification):** the body already pins `e9e1f06a` (D1, §7, §11.3); the owner ratifies that pin, or names a different SHA (see D1's single-source-of-truth note).
2. **Phase 0 pilot target:** the reviewed artifact is this document at the content hash recorded in the pilot log before dispatch — `sha256sum` of the file plus the recording date (as the round-1 pilot did — this document at its then-current content). The AEP repo is context (GoldfishContext), not the artifact under review: the Phase 2 PR (branch `chore/reference-vendor-elephant-goldfish-model`) is the end state the pilot's evidence supports, not the artifact under review. The Elephant records the chosen content hash and date in the pilot log before dispatch.
3. **Phase 3 ruling (required before Phase 3 runs; it does not gate Phase 2):** the owner rules — provision a fresh VM for Phase 3 validation, or mark Phase 3 documented-but-unexecuted and move §9 to an appendix. Until ruled, §9 carries the header note 'Provisional — validation pending owner provisioning.' 'Documented-but-unexecuted' (see §1.1 Glossary). **RULED 2026-11-07: keep §9 as a numbered section (no appendix move). Phase 3 partially executed the same day — the headless (Path 2) shape validated in an emulated fresh-VM rootfs (pilot log dated 2026-11-07; environment record in `docs/environment/`); the Path 1 (muse-cli) shape is documented-but-unexecuted until a harness environment is available. zoom_out-1-1 (the round-1 ESCALATE this decision answers) is closed by this ruling.**
4. **Force-sync policy (ratification):** the body already states the D5 policy (upstream fix / baseline entry / owner force-sync); the owner ratifies it.
5. **Pilot-value ruling:** after the Phase 0 pilot, the owner rules whether the pilot demonstrated marginal value over the existing instruments. Criteria (all recorded in the ruling): (a) the pilot found defects the incumbents had not surfaced (the round-1 pilot — see §3 — including 3 Blockers, among them a genuine D3/Path 1 contradiction and a missing CI edit); (b) the finding action rate (§2) is recorded in the ruling, and the ruling states why that rate justifies the §10.4 cost; a single changed finding does not by itself establish value; (c) the qualitative judgment, with reasons stated. No roundtable baseline control run was performed, so the ruling is a judgment against these criteria, not a controlled comparison — and the ruling must say so.
6. **Phase 1 loop bounds (ratification or tightening):** the body already sets the interim default (pilot's 30-minute timeout, pilot log's token actuals — §10.4); before the next pilot run the owner sets the interim pilot token cap (per-reviewer and per-run maxima); before Phase 1 the owner sets the per-reviewer timeout and the Phase 1 token budget (per-reviewer and per-run maxima), from the pilot log's elapsed-time and token records; Phase 1 does not start until this ruling is recorded.

## Appendix — Sources (all verified 2026-11-06)

- Upstream repo: [google/elephant-goldfish-model](https://github.com/google/elephant-goldfish-model), v0.1.1, Apache-2.0, HEAD `e9e1f06a`; fork [pratik-saptarshi/elephant-goldfish-model](https://github.com/pratik-saptarshi/elephant-goldfish-model) verified byte-identical HEAD.
- [docs/muse.md](https://github.com/google/elephant-goldfish-model/blob/main/docs/muse.md) (Muse install, named-spawn rejection on 1.4.14, read-only caveat, 2026-10-30 E2E fixture), [docs/harnesses.md](https://github.com/google/elephant-goldfish-model/blob/main/docs/harnesses.md) ("skill-only installers break EGM"), [plugin.json](https://github.com/google/elephant-goldfish-model/blob/main/plugin.json), [skills/*/SKILL.md](https://github.com/google/elephant-goldfish-model/tree/main/skills), [agents/*.md](https://github.com/google/elephant-goldfish-model/tree/main/agents), [resources/document_standards/*.md](https://github.com/google/elephant-goldfish-model/tree/main/resources/document_standards).
- AEP: [skills/README.md](https://github.com/pratik-saptarshi/autonomous-engineering-platform/blob/develop/skills/README.md) attribution format, [.github/skills-sync-scope.txt](https://github.com/pratik-saptarshi/autonomous-engineering-platform/blob/develop/.github/skills-sync-scope.txt), [scripts/check_skills_manifest.py](https://github.com/pratik-saptarshi/autonomous-engineering-platform/blob/develop/scripts/check_skills_manifest.py), CI jobs ([.github/workflows/ci.yml](https://github.com/pratik-saptarshi/autonomous-engineering-platform/blob/develop/.github/workflows/ci.yml): docs-lint, shell-lint, script-tests, go-checks, security, vendor-integrity, skills-freshness), [reference/](https://github.com/pratik-saptarshi/autonomous-engineering-platform/tree/develop/reference) vendor pattern (9 trees, `.github/vendor-*.sha256`).
