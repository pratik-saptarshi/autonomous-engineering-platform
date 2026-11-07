Status: resolved
Status: unresolved — awaiting the interactive gate (Step 4). No fixes applied.
# Goldfish Annotated Review Report — Round 2

**Target:** `/home/hatch/workspace/plans/2026-11-06-egm-adoption-aep.md` (full file, 358 lines, after round-1 fixes)
**Source findings:** `/home/hatch/workspace/plans/2026-11-06-egm-adoption-aep-goldfish-review-r2.md` (Round 2: 3 Blockers, 65 Majors, 22 Nits; all 5 reviewers completed; 3 findings already marked SETTLED in the report)
**Round-1 baseline:** `/home/hatch/workspace/plans/2026-11-06-egm-adoption-aep-goldfish-resolve.md` (60 PROPOSE FIX applied/present, 1 CONTEST, 1 ESCALATE, 3 DECLINE; marked resolved)
**Note on filename:** the skill prescribes `goldfish_review_report.md`; this dated name is used instead so the pilot's artifacts stay distinct.
**Note on discrepancies:** discrepancy/rationale text below is condensed from the FindingsList (substance preserved); full text is in the round-2 report. Shared root causes are fixed once and cross-referenced — see the Shared-edit map.

## Category counts (90 findings)

- **CONTEST:** 0
- **ESCALATE:** 0 new (the one live ESCALATE is the settled round-1 item `zoom_out-1-1`, carried by settled `zoom_out-2-4` below)
- **PROPOSE FIX:** 84 (3 Blockers, 63 Majors, 18 Nits)
- **DECLINE:** 3 (all Nits)
- **SETTLED:** 3 (2 Majors, 1 Nit — recorded, not re-categorized, no fix proposed)

By reviewer: design_critic 19 PROPOSE FIX; structural 12 PROPOSE FIX + 3 DECLINE + 1 SETTLED; implementation_readiness 24 PROPOSE FIX; comprehension 20 PROPOSE FIX; zoom_out 9 PROPOSE FIX + 2 SETTLED.

## Shared-edit map (one edit covers each group)

- **E-A** path-form / sync check: design_critic-2-1 + implementation_readiness-2-2
- **E-B** 90-file bundle inventory: design_critic-2-2 + implementation_readiness-2-1 + zoom_out-2-6
- **E-C** pinned-SHA fetch: design_critic-2-3 + implementation_readiness-2-16
- **E-D** loop cost / timeout / budget: design_critic-2-4 + implementation_readiness-2-14 + comprehension-2-20 + zoom_out-2-9
- **E-E** §4 architecture depth: design_critic-2-5 + structural-2-6 + comprehension-2-1
- **E-F** read-only detection scope / rollback / residual risk: design_critic-2-7 + implementation_readiness-2-17 + zoom_out-2-8
- **E-G** `<install-root>` reconciliation: design_critic-2-8 + comprehension-2-9
- **E-H** Path 1 install matrix (Cursor / OpenCode / Codex CLI): design_critic-2-9 + comprehension-2-10
- **E-I** E2E fixture executability: design_critic-2-9 (part) + implementation_readiness-2-10 + comprehension-2-11
- **E-J** dangling "Issue N" references: structural-2-4 + comprehension-2-7
- **E-K** `skill.yaml` hand-written vs generated: implementation_readiness-2-3 + comprehension-2-8
- **E-L** attribution Notes exception text: design_critic-2-15 + implementation_readiness-2-6
- **E-M** Phase 0 pilot target: implementation_readiness-2-15 + comprehension-2-13
- **E-N** live→repo sync procedure: implementation_readiness-2-13 + comprehension-2-12
- **E-O** pytest install + invocation: design_critic-2-19 + implementation_readiness-2-9
- **E-P** pilot-evidence criterion / gating / rollback: design_critic-2-10 + zoom_out-2-5
- **E-Q** problem scale / demand baseline: design_critic-2-14 + zoom_out-2-2 + zoom_out-2-3
- **E-R** pilot report path: structural-2-12 + comprehension-2-16 (part)
- **E-S** Phase 3 gate / enforcement: design_critic-2-11 + implementation_readiness-2-19 + comprehension-2-15
- **E-T** `AEP machinery` placement / duplication: structural-2-2 + structural-2-8

## Verification notes (evidence gathered for this resolve)

- Bundle at `~/workspace/egm/`: 90 files total — `skills/` 38, `agents/` 10, `resources/` 7, `docs/` 33 (13 top-level + 18 under `docs/designs/` + 1 asset SVG + 1 under `docs/verification/`), `LICENSE`, `plugin.json`. No `TESTING.md`, no `tests/`, no `adapters/` in the vendored tree. Upstream `TESTING.md` exists at `https://github.com/google/elephant-goldfish-model/blob/main/TESTING.md` (cited from bundle `docs/index.md:11`).
- Pilot adapted skills: `custom-skills/egm-review/SKILL.md` has 0 occurrences of `/home/hatch/workspace/egm` and 8 of `~/workspace/egm` (line 12: `In Muse, read ~/workspace/egm/docs/muse.md first.`); `egm-review-loop/SKILL.md` has 0 and 13 respectively.
- `scripts/check_skills_manifest.py:187`: `--root` is `required=True`; `--write` exists (line 190).
- Upstream `docs/muse.md:32-34`: "Approval is required once… the ten agent definitions need `approve` before activation." Upstream `docs/harnesses.md` install table: no Cursor or OpenCode row (0 mentions each); Codex CLI command at line 19; ChatGPT/Codex desktop listing link at lines 11–12. Bundle `docs/cursor.md:9`: "Do not add Cursor to the supported-host table yet" (issue #145); `docs/opencode.md:20`: install via `python3 adapters/opencode/install.py …` (OpenCode 1.18.29; issue #146).
- `GoldfishContext` is defined in bundle `skills/egm-review/SKILL.md:74` (reading list); Delegation sections at `skills/egm-review-loop/SKILL.md:34` and `skills/egm-review/SKILL.md:19`. `roundtable_review` skill verified: parallel debate rounds, per-dispute verification subagents, final judge.
- No pilot log file with per-reviewer elapsed times exists under `~/workspace/plans/`; no sync script exists in the AEP repo (`scripts/` has no skill-sync script). `pytest` is absent on this VM (verified). AEP `docs/` holds 22 `.md` files (verified count).

## Prioritized Findings & AI Suggestions

### [Issue 1] [design_critic-2-1] [`design_critic`] - Severity: Blocker
*   **Affected Scope:** Lines 117, 264, 295 (D3, §10.2, §10.4 step 4)
*   **Discrepancy Description:** L117 states Environment B uses the expanded absolute path `/home/hatch/workspace/egm/...` ("the pilot already does this; `~` is never written into an adapted file"). On disk both pilot skills contain zero occurrences of `/home/hatch/workspace/egm` and 8 / 13 occurrences of `~/workspace/egm`. L264 contradicts L117 ("absolute paths to `~/workspace/egm/`"). L295's sync check runs only `sed 's|/home/hatch/workspace/egm|../../reference/elephant-goldfish-model|g'`; simulated verbatim it produces 0 replacements, so `diff -r` can never report zero differences as written.
*   **Rationale:** The sync check is the sole mechanism proving local↔repo wrapper equivalence and cannot pass on the artifacts the pilot produced; the doc asserts a fact about its own pilot that is false on inspection.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified on disk (see Verification notes). Shared edit E-A with implementation_readiness-2-2.
*   ***Proposed Edit:***
    *   Location: D3 item 3 (L117); §10.2 (L264); §10.4 step 4 (L295).
    *   Change: Replace L117's sentence with: "Environment B uses the `~` form `~/workspace/egm/...` in adapted files (the pilot does this: `egm-review` 8 occurrences, `egm-review-loop` 13, verified 2026-11-06; the expanded form `/home/hatch/workspace/egm/...` never appears in a pilot adapted file)." Replace L264's "absolute paths to `~/workspace/egm/`" with "`~/workspace/egm/` paths". Replace §10.4 step 4 with: "Sync check: copy the seven local `custom-skills/egm-*/SKILL.md` files to a temp dir preserving their `egm-*/SKILL.md` layout (one `egm-*/` subdir per skill), run `sed -i 's|~/workspace/egm|../../reference/elephant-goldfish-model|g'` and `sed -i 's|/home/hatch/workspace/egm|../../reference/elephant-goldfish-model|g'` on the copies, then `diff -r` the temp dir against the repo `skills/egm-*/` — expecting zero differences. Also assert every `agents/...` and `resources/...` reference in each adapted `SKILL.md` resolves to an existing file at the installed location."

### [Issue 2] [implementation_readiness-2-1] [`implementation_readiness`] - Severity: Blocker
*   **Affected Scope:** Lines 317 vs 290 (Phase 2 file-change list vs §10.4 step 2)
*   **Discrepancy Description:** L317 lists the bundle as "39 files" — `skills/` (7 × `SKILL.md` only), `agents/` (10), `resources/` (7), `docs/` (13 files), `LICENSE`, `plugin.json`. The actual bundle contains 90 files: `skills/` alone has 38 files and `docs/` has 33. L290 then requires `diff -rq` of the bundle against the upstream subset expecting zero differences — a whole-directory diff that can only pass with the full 90-file tree. An implementer following L317 vendors an incomplete bundle that fails L290; following L290 vendors files L317 never lists.
*   **Rationale:** The exact file boundary is the one thing this plan must pin down, and it states two incompatible boundaries.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified on disk (90 files; see Verification notes). Shared edit E-B with design_critic-2-2 and zoom_out-2-6.
*   ***Proposed Edit:***
    *   Location: §11 Phase 2 file-change list (L317); §7 "Not vendored" (L78–80); §10.4 step 2 (L290).
    *   Change: Replace the L317 bundle inventory with: "`reference/elephant-goldfish-model/` bundle, 90 files at the pinned SHA — `skills/` (38 files: per skill `SKILL.md`, `TEST.md`, `agents/openai.yaml`, `assets/icon.svg`, `test_scenarios.yaml`, plus `references/` in `egm-bootstrap` and `egm-draft`), `agents/` (10 persona files), `resources/` (7: `execution_instructions.md`, `README.md`, 5 standards), `docs/` (33 files: 13 top-level, 18 under `docs/designs/`, 1 asset SVG, 1 under `docs/verification/`), `LICENSE`, `plugin.json`." Amend §7 "Not vendored" to: "Not vendored: the Astro docs site (`site/`), packaging scripts (`scripts/`), the top-level `tests/` directory, the `adapters/` directory, per-host plugin manifests (`.claude-plugin/`, `.codex-plugin/`, `.cursor-plugin/`), and all other repo-root files. Per-skill test files (`TEST.md`, `test_scenarios.yaml`) live under `skills/` and ARE vendored." No change to L290's diff scope — whole-directory diff is now consistent with the 90-file vendor.

### [Issue 3] [implementation_readiness-2-2] [`implementation_readiness`] - Severity: Blocker
*   **Affected Scope:** Lines 295 + 117 (§10.4 step 4 + D3)
*   **Discrepancy Description:** L295's check runs `sed -i 's|/home/hatch/workspace/egm|../../reference/elephant-goldfish-model|g'` on copies of the local adapted `SKILL.md` files and expects zero diff vs the repo wrappers. But the pilot adapted skill `~/workspace/custom-skills/egm-review/SKILL.md:12` reads `In Muse, read ~/workspace/egm/docs/muse.md first.` — the `~` form, not the expanded path. This directly contradicts L117's assertion that "the pilot already does this; `~` is never written into an adapted file," and the `sed` only replaces the `/home/hatch/...` form, so the `~/...` occurrences survive and the expected-zero diff fails. Additionally, "copy the seven … files to a temp dir" (singular) never specifies the 7-subdirectory layout that `diff -r` against `skills/egm-*/` requires.
*   **Rationale:** A specified verification step that deterministically fails on the existing pilot output is not a check — it blocks Phase 2 with no recovery path stated.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified on disk (see Verification notes). Shared edit E-A with design_critic-2-1 — apply Issue 1's edit once; it covers both findings.
*   ***Proposed Edit:***
    *   Location: §10.4 step 4 (L295); D3 item 3 (L117). Same fix as Issue 1, applied once.
    *   Change: Adopt Issue 1's replacement text (correct L117 to the `~` form with verified counts; two-sed sync check with the `egm-*/SKILL.md` temp-dir layout).

### [Issue 4] [design_critic-2-2] [`design_critic`] - Severity: Major
*   **Affected Scope:** Lines 78–80, 290, 317 (bundle file set, stated three ways)
*   **Discrepancy Description:** L317 claims the bundle is "39 files". The actual pristine bundle is 90 files: `skills/` holds 38 (each skill also has TEST.md, `agents/openai.yaml`, `assets/icon.svg`, `test_scenarios.yaml`, plus 3 `references/` files), `docs/` holds 33 (13 top-level plus 18 under `docs/designs/`, 1 asset SVG, 1 under `docs/verification/`). L78–80 says "tests" are not vendored, yet L290's `diff -rq` scope (whole `skills/`, `agents/`, `resources/`, `docs/`, LICENSE, `plugin.json`) includes the per-skill test files and expects zero differences.
*   **Rationale:** The vendor-integrity gate's input set is undefined; a PR author cannot determine from this doc what the bundle contains, and the 39-file scope understates the PR by >50%.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified on disk (90 files; see Verification notes). Shared edit E-B — apply Issue 2's edit once; it covers this finding, Issue 2, and zoom_out-2-6's core claim.
*   ***Proposed Edit:***
    *   Location: §11 Phase 2 file-change list (L317); §7 (L78–80). Same fix as Issue 2, applied once.
    *   Change: Adopt Issue 2's replacement text (90-file inventory; per-skill test files ARE vendored, only the top-level `tests/` dir is excluded).

### [Issue 5] [design_critic-2-3] [`design_critic`] - Severity: Major
*   **Affected Scope:** Line 290 (pinned-SHA verification command)
*   **Discrepancy Description:** `git clone --depth 1 ... && git rev-parse HEAD` prints whatever upstream HEAD is at execution time. It passes today only because HEAD still equals `e9e1f06a` (verified live); the first upstream commit after that date makes the check fail spuriously, and the check conflates "bundle matches the pin" with "upstream hasn't moved."
*   **Rationale:** A verification step that breaks on an event the doc itself anticipates (heads move daily) is not a verification step.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified live: upstream HEAD is still `e9e1f06a` (full SHA `e9e1f06aa4e26e95cd4ed37210a0632202c429e9`, via `git ls-remote`). Shared edit E-C with implementation_readiness-2-16.
*   ***Proposed Edit:***
    *   Location: §10.4 step 2 (L290).
    *   Change: Replace the fetch command with: "`git clone https://github.com/google/elephant-goldfish-model.git /tmp/egm-upstream && cd /tmp/egm-upstream && git fetch --depth 1 origin e9e1f06a && git checkout e9e1f06a && git rev-parse HEAD` must print exactly `e9e1f06aa4e26e95cd4ed37210a0632202c429e9`." Replace the bare "`diff -rq` the bundle against the upstream subset" with the concrete command: "`diff -rq /tmp/egm-upstream/skills <bundle>/skills && diff -rq /tmp/egm-upstream/agents <bundle>/agents && diff -rq /tmp/egm-upstream/resources <bundle>/resources && diff -rq /tmp/egm-upstream/docs <bundle>/docs && diff -q /tmp/egm-upstream/LICENSE <bundle>/LICENSE && diff -q /tmp/egm-upstream/plugin.json <bundle>/plugin.json` — expecting zero differences (where `<bundle>` is `~/workspace/egm/` locally, `reference/elephant-goldfish-model/` in AEP)."

### [Issue 6] [design_critic-2-4] [`design_critic`] - Severity: Major
*   **Affected Scope:** Lines 52, 285 (§6 loop cost, §10.3 Loop bounds)
*   **Discrepancy Description:** §6 lists "Loop cost — mitigation: bounds in §10.3," but §10.3 sets "no fixed per-reviewer timeout" and "no token budget … until pilot data exists." Bounds allow 5 rounds × 5 reviewers = 25 fresh-context spawns per loop, and the doc never states whether upstream's optional A/B duplication (two instances per reviewer) is used, which would double it to 50.
*   **Rationale:** The standard requires cost and scalability limits to be addressed; here the mitigation points at a section that expressly defers both controls. Each spawn re-reads persona + target + standard(s) + context, so cost scales with document size, which is also uncapped.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The mitigation points at a section that defers the controls it claims. Shared edit E-D with implementation_readiness-2-14, comprehension-2-20, and zoom_out-2-9.
*   ***Proposed Edit:***
    *   Location: §6 loop-cost row (L52); `### Loop bounds` (L283–285); §14 (new decision 6).
    *   Change: Replace §6's "Loop cost — mitigation: bounds in §10.3." with "Loop cost — mitigation: bounds in §10.4 Loop bounds (at most 5 rounds × 5 reviewers = 25 spawns per run; 30-minute interim per-reviewer timeout for the pilot; cost recorded per phase gate; token budget set by §14 decision 6). Upstream's optional A/B duplication (two instances per reviewer) is NOT used: one instance per reviewer." In Loop bounds, replace "Timeout: no fixed per-reviewer timeout is set in this document — the pilot log records per-reviewer elapsed time, and the timeout for Phase 1 is set from that evidence by the owner." with "Timeout: 30 minutes per reviewer for the pilot (interim bound; no pilot log with per-reviewer elapsed times exists yet, so this bound is set now and the pilot log records actual elapsed times). Cost: each phase gate records reviewer count, rounds run, and tokens spent; cost is measured in reviewer spawns (max 25 per run) and tokens." Add §14 decision 6: "Phase 1 loop bounds: before Phase 1 the owner sets the per-reviewer timeout and whether a token budget applies, from the pilot log's elapsed-time and token records."

### [Issue 7] [design_critic-2-5] [`design_critic`] - Severity: Major
*   **Affected Scope:** Lines 35–38 (§4 Proposed Architecture)
*   **Discrepancy Description:** §4 lists the component chain in a single sentence and defers all detail to §§8–10, which are decision lists and install procedures, not a design. No data flow, no review-loop sequence (dispatch → report → checks → synthesize → fix → re-review), no artifact lifecycle or write paths, no concurrency model (parallel vs. sequential reviewers), no failure propagation (what happens to in-flight reviewers when one fails mid-round).
*   **Rationale:** The standard requires component layout, data flows, and ecosystem integration; a fresh reader cannot implement or reason about the loop's runtime behavior from this section.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The round-1 fix (Issue 14) made §4 a map with pointers; the map alone does not satisfy the standard's data-flow requirement. Shared edit E-E with structural-2-6 and comprehension-2-1.
*   ***Proposed Edit:***
    *   Location: §4 (L35–37).
    *   Change: Append after the component-map sentence: "Data flow: the Elephant drafts the design doc → dispatches Goldfish reviewers in parallel (one fresh-context subagent per reviewer) → each reviewer files a report citing persona, standard, and target line numbers → the driver runs the line-existence + standard-name checks → the Elephant consolidates into a flat FindingsList with stable ids and writes the report artifact → `egm-resolve` categorizes → fixes are applied → the loop re-reviews until two consecutive clean rounds. Artifact lifecycle: design docs live in the working directory / repo; review reports are dated files under `~/workspace/plans/` (pilot) or in the PR (AEP); drift reports are dated files naming their destination in advance. Concurrency: reviewers run in parallel; synthesis waits for actual completion. Failure propagation: a reviewer that times out, fails, or returns no report is retried once, then recorded not run — never counted as zero findings — and the round is not clean."

### [Issue 8] [design_critic-2-6] [`design_critic`] - Severity: Major
*   **Affected Scope:** Lines 39–45 (§5 Alternatives Considered)
*   **Discrepancy Description:** All five rejections rest on unquantified assertions ("pollutes the skill catalog," "leaves design review informal," "no submodule precedent," "no artifact to version," "gated on pilot evidence") with no complexity, cost, performance, or scalability numbers. Two viable alternatives are missing: (a) sourcing from the user's fork — the repo's established convention, which D1 breaks with an explicit exception justified only by "the fork is a pure mirror and adds nothing," a property shared by most verbatim-vendored forks in the same README table; (b) minimal-subset vendoring — only the 2 pilot skills' dependencies — although the pilot installs the full bundle while adapting only 2 skills.
*   **Rationale:** The standard fails a spec that proposes a path without proving other viable designs were considered and rejected for specific documented reasons.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid in its core: the rejections are unquantified and two alternatives are unevaluated. The fork sub-claim ("a property shared by most verbatim-vendored forks in the same README table") was not verified against the README table and the fix does not depend on it — the fork-source alternative is evaluated below on the D1/pin ground, which is checkable. The minimal-subset alternative is answerable from D2.
*   ***Proposed Edit:***
    *   Location: §5 (L39–45).
    *   Change: Add two evaluated alternatives: "- Sourcing from the user's fork (`pratik-saptarshi/elephant-goldfish-model`) instead of upstream — rejected: the fork is a pure mirror (fork HEAD = upstream HEAD = `e9e1f06a`, verified 2026-11-06) and adds nothing; sourcing from upstream keeps the pin verifiable against `google/elephant-goldfish-model` directly, and the README fork-naming exception is already recorded in the attribution Notes (D4). - Minimal-subset vendoring (only the 2 pilot skills' dependencies) — rejected: D2 requires the bundle to move as one unit because skills resolve `agents/` and `resources/` at run time; a subset that omits personas or standards breaks the skills by construction, so the full 90-file bundle is vendored while only 2 skills are adapted in the pilot." Add the one quantified fact available to the existing rejections: append to §5's intro: "Scale of the adopted set (verified 2026-11-06): 90-file bundle (2,810 lines of skills + agents + standards + instructions), 7 wrappers, 2 CI gates, at most 25 reviewer spawns per loop run."

### [Issue 9] [design_critic-2-7] [`design_critic`] - Severity: Major
*   **Affected Scope:** Lines 49, 153–158 (D6), 273, 319–332 (§6, §10.3, §12)
*   **Discrepancy Description:** (a) The non-repo snapshot is "file list + mtimes," which cannot detect in-place content edits with preserved mtime (only repo targets get content-sensitive `git status`); (b) snapshot scope is undefined — target repo only, or also `~/workspace/egm/`, `custom-skills/`, memory/DB paths a reviewer could reach?; (c) no rollback/restore procedure — detection discards the finding but leaves the mutation in place; (d) with parallel reviewers, a mutation cannot be attributed to one reviewer; (e) the memory prohibition is enforced only by discarding findings whose rationale cites memory — silent use is undetectable.
*   **Rationale:** §12 names this the principal risk in both environments; a mitigation that detects only some writes, in an undefined scope, with no recovery, does not close it.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. All five sub-points are true of the text as written. Shared edit E-F with implementation_readiness-2-17 and zoom_out-2-8.
*   ***Proposed Edit:***
    *   Location: D6 (L153–158); §6 D6 row (L49); §12 (L319–332).
    *   Change: In D6, replace "snapshot the working tree (`git status --porcelain` in a repo target; file list + mtimes for a non-repo target)" with "snapshot the working tree by content hash: `git status --porcelain` in a repo target; `find <dir> -type f -exec sha256sum {} + | sort > <snapshot-file>` for a non-repo target (mtimes alone are not content-sensitive and are not used). Snapshot scope is the target repo working tree plus the local bundle (`~/workspace/egm/`) and the adapted skills (`~/workspace/custom-skills/egm-*/`). Memory/DB paths are out of scope: no snapshot is taken of the NeuroStrata store, and reviewers are briefed never to read or write memory — silent memory use is undetectable and is stated here as a residual risk, not as a closed control." Replace "Enforcement is post-hoc and fail-closed:" with "Detection is post-hoc: the snapshot diff detects a write after it happens; it does not prevent it. The round is fail-closed (a detected write fails the round), the filesystem is not — the residual write-before-detection risk stands (see §12)." Append to D6: "Rollback: on a detected modification, fail that reviewer's round, discard its findings, restore the tree from git (`git checkout -- <paths>`) or re-vendor the bundle from the repo tree, and record the incident in the pilot log; the reviewer is not re-dispatched. Attribution: with parallel reviewers a modification is attributed to the round, not to one reviewer; the round fails." In §6, replace the D6 mitigation with "read-only briefs + post-run snapshot diff (detection only — see D6) + line-existence check". In §12, append: "Residual risk: a reviewer write is detected only after it happens (D6); detection does not prevent the write, and memory/DB paths are not snapshotted."

### [Issue 10] [design_critic-2-8] [`design_critic`] - Severity: Major
*   **Affected Scope:** Lines 214–228 (§9.3), 257–270 (§10.2)
*   **Discrepancy Description:** §9.3 defines `<install-root>` with default `$HOME/egm` and example skill paths `$HOME/egm/agents/...`, with skills at `<install-root>/skills/egm-*/`. §10.2 maps `<install-root>` to `~/workspace`, with skills at `~/workspace/custom-skills/egm-*/` — a different directory name, not just a different root. A Path 2 installer following §9.3 literally creates `$HOME/egm/skills/egm-*/`, not the Environment B layout. No harness skill-discovery convention is cited for any generic harness; only Muse's `custom-skills/` convention is given (Environment B).
*   **Rationale:** "One vendored content set, two installation mechanisms" rests on a generic loading mechanism that is never specified; the two `<install-root>` definitions cannot both be followed.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified against the text. Shared edit E-G with comprehension-2-9.
*   ***Proposed Edit:***
    *   Location: §9.3 (L214–228); §10.2 (L257–270).
    *   Change: Replace the §9.3 `<install-root>` paragraph with: "`<install-root>` is the directory holding the cloned repo and the installed skills, default `$HOME/egm` (example: `/home/<user>/egm`). Generic Path 2 layout: bundle at `<install-root>/egm/`, skills at `<install-root>/skills/egm-*/`, resolving bundle paths against `<install-root>/egm/`. Environment B mapping: `<install-root>` = `~/workspace`, so the bundle is `~/workspace/egm/` and the skills are `~/workspace/custom-skills/egm-*/` (Muse's `custom-skills/` convention, not the generic `skills/`). Example path strings a Path 2 skill contains: `$HOME/egm/agents/design_critic.md`; in Environment B the same string reads `/home/hatch/workspace/egm/agents/design_critic.md`. No generic harness skill-discovery convention is specified: Path 2 requires the harness to load skills from `<install-root>/skills/` (or the harness's own skill directory, stated per harness in §9.2); only Muse's `custom-skills/` convention is specified here (Environment B)." In §10.2, append to the layout block: "(`<install-root>` = `~/workspace` per §9.3; skills live in `custom-skills/`, not the generic `skills/`.)"

### [Issue 11] [design_critic-2-9] [`design_critic`] - Severity: Major
*   **Affected Scope:** Lines 187–213 (§9.2), 234, 244 (Path 1 install matrix, E2E fixture)
*   **Discrepancy Description:** §1 names Muse, Claude Code, Codex, Cursor, OpenCode, Antigravity; §9.2 gives commands for Muse, Claude Code, Antigravity, and "Codex desktop" (listing only, no command — the Codex CLI command in `docs/harnesses.md` is omitted), while Cursor has no install entry at all and OpenCode has only a path pointer ("per the `adapters/opencode/` install path"). The E2E fixture (`muse-wonder-1.0`) is defined only by reference to upstream `TESTING.md`, which is excluded from the bundle and never quoted. "Against the installed cache only" is undefined (which cache, where, how it gets there on a fresh VM).
*   **Rationale:** Environment A's verification cannot be executed from the vendored content for half its harnesses, and the acceptance fixture is not reproducible from the artifacts this adoption produces.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: `docs/harnesses.md` has zero mentions of Cursor or OpenCode; the Codex CLI command exists there (line 19) but is omitted from §9.2; `TESTING.md` is not in the vendored tree. Shared edits E-H (install matrix, with comprehension-2-10) and E-I (fixture, with implementation_readiness-2-10 and comprehension-2-11).
*   ***Proposed Edit:***
    *   Location: §9.2 (L187–213); §9.5 step 3 (L243–244).
    *   Change: In §9.2, add after the Codex desktop row: "- **Codex CLI:** `codex plugin marketplace add google/elephant-goldfish-model && codex plugin add egm@egm` (from the bundle's `docs/harnesses.md` install table). - **Codex desktop and ChatGPT desktop:** install the published EGM plugin (desktop-only listing: https://chatgpt.com/plugins/plugins_6aeb90f47ec88191a3c107e01d3eb357). - **Cursor:** experimental, unverified upstream (bundle `docs/cursor.md`: 'Do not add Cursor to the supported-host table yet'; upstream issue #145) — install from a clean checkout per `docs/cursor.md` 'Install a candidate'; not a supported Path 1 route until verified. - **OpenCode:** OpenCode 1.18.29 only, from an upstream checkout at the pinned SHA: `python3 adapters/opencode/install.py /absolute/egm-opencode-candidate`, then `OPENCODE_CONFIG=/absolute/egm-opencode-candidate/opencode.json opencode --agent egm` (per bundle `docs/opencode.md`); `adapters/` is not vendored, so this runs from the upstream checkout, not the bundle; adapter unverified upstream (issue #146)." In §1, annotate the harness list: "(Cursor and OpenCode adapters are experimental / unverified upstream.)" For the fixture, adopt the E-I edit (see Issue 27): cite the exact upstream `TESTING.md` URL, define "installed cache" as the harness's installed plugin/skill cache on that VM (not the upstream checkout), and give the temp workspace, command form, and pass criterion.

### [Issue 12] [design_critic-2-10] [`design_critic`] - Severity: Major
*   **Affected Scope:** Lines 29, 45, 301–313 ("gated on pilot evidence", adoption goal)
*   **Discrepancy Description:** L45 gates the remaining 5 skills "on pilot evidence" but no threshold is defined — no pilot outcome is stated to block Phase 1. The §2 adoption goal ("at least one design document reviewed via `egm-review-loop` within 30 days") would be satisfied as written by a review with reviewers not run, since the Phase 0 "0 not run" gate does not carry into it. No rollback/decommission plan exists if the pilot fails.
*   **Rationale:** A gate without a criterion is not a gate; the rollout's central evidence claim is unfalsifiable.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Shared edit E-P with zoom_out-2-5.
*   ***Proposed Edit:***
    *   Location: §2 adoption goal (L29); §5 subset bullet (L45); §11 Phase 0/1 gates (L301–313); §14 (new decision 5).
    *   Change: Replace the §2 adoption goal with: "Adoption — at least one design document reviewed via `egm-review-loop` within 30 days of merge, with all reviewers run (0 not run)." Replace §5's "remaining 5 gated on pilot evidence" with "remaining 5 gated on pilot evidence, defined as: the pilot completes with all reviewers run (0 not run), the report is filed and findings categorized, and the owner rules the pilot demonstrated marginal value over the existing instruments (§14 decision 5, recorded in the pilot log). Without that ruling, Phase 2 installs the 2 review skills only." Add §14 decision 5: "Pilot-value ruling: after the Phase 0 pilot, the owner rules whether the pilot demonstrated marginal value over the existing instruments; the remaining 5 skills proceed only on a positive ruling." Add to §11: "Rollback: if the pilot fails (a reviewer not run, or the owner rules no marginal value), roll back by deleting the 2 adapted skill dirs and the local bundle (`~/workspace/custom-skills/egm-*/`, `~/workspace/egm/`), with no AEP PR; record the outcome in the pilot log."

### [Issue 13] [design_critic-2-11] [`design_critic`] - Severity: Major
*   **Affected Scope:** Lines 308, 349, 301–313 (Phase 3 ruling vs Phase 2 gate)
*   **Discrepancy Description:** §14 decision 3 requires the owner ruling (provision a fresh VM, or mark Phase 3 documented-but-unexecuted and move §9 to an appendix) "before Phase 2 merges," but the Phase 2 gate lists only CI green, Conventional Commits, and owner review. The only enforcement is the Phase 3 gate failing later — after the merge the ruling was meant to precede. If the owner picks "documented-but-unexecuted," §9 moves to an appendix with no criteria for what counts as "documented."
*   **Rationale:** A sequencing requirement with no enforcing gate will be missed; the fallback silently guts the doc's stated scope.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Shared edit E-S with implementation_readiness-2-19 and comprehension-2-15.
*   ***Proposed Edit:***
    *   Location: §11 Phase 2 gate (L311); §11 Phase 3 gate (L308); §14 decision 3 (L349).
    *   Change: Add to the Phase 2 gate: "§14 decision 3 ruled (fresh VM provisioned, or Phase 3 marked documented-but-unexecuted with §9 moved to an appendix)." Rewrite the Phase 3 gate cell as: "Pass: E2E fixture passes on the fresh VM. Fail: the fixture fails, or Phase 3 is unexecuted after the §14 decision 3 ruling without that ruling recording 'documented-but-unexecuted'. An unexecuted Phase 3 passes only by an explicit ruling, never by default." Append to decision 3: "'Documented-but-unexecuted' means: §9 carries the header note 'Provisional — validation pending owner provisioning.', §9 is moved to an appendix, and the Phase 3 gate records the ruling and its date."

### [Issue 14] [design_critic-2-12] [`design_critic`] - Severity: Major
*   **Affected Scope:** Lines 113, 129, 142, 295 (`skill.yaml` drift coverage)
*   **Discrepancy Description:** The doc correctly states `skill.yaml` is excluded from the manifest and "covered by neither gate," with coverage being the Phase 2 YAML-parse + name-match check. But Phase 2 is a one-time PR event; §10.4 step 4 (the ongoing sync check) diffs `SKILL.md` only. Any later local edit to a `skill.yaml` (e.g. `description` drifting from the `SKILL.md` frontmatter) is undetected by skills-freshness and by the sync check, indefinitely.
*   **Rationale:** For a document whose value proposition is drift detection, a known-uncovered file class in the sync loop is an unmitigated drift surface the doc itself identifies and then leaves open.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The one-time check is correctly identified as the gap; the ongoing sync check must include `skill.yaml`.
*   ***Proposed Edit:***
    *   Location: §10.4 step 4 (L295); §10.2 cadence (L269); `### Verification checks` (L297–299, new check 6).
    *   Change: Append to §10.4 step 4: "The sync check also covers `skill.yaml`: on every sync, every `skill.yaml` is re-validated (YAML parses, `name` matches the `SKILL.md` frontmatter `name`); a mismatch fails the sync." Append to §10.2's cadence sentence: "Each sync re-runs the YAML-parse + name-match check for all 7 `skill.yaml` files." Add Verification check (6): "on every sync, all 7 `skill.yaml` files parse as YAML and their `name` fields match the `SKILL.md` frontmatter `name` (recorded in the sync record)."

### [Issue 15] [design_critic-2-13] [`design_critic`] - Severity: Major
*   **Affected Scope:** Lines 172–178 (Roles), 160–171 (D7)
*   **Discrepancy Description:** Upstream assigns the synthesizer aggregation, triage, and dedup; in Environment B it "is replaced by direct dispatch … with the Elephant consolidating findings," but no dedup/normalization procedure for the Elephant is specified — round 1 produced 65 findings across 5 reviewers with evident overlap. The nesting limit is presented as a platform constraint with no cited source; depth-2 spawning demonstrably works in this environment (this review itself runs as a depth-2 subagent spawned by a depth-1 parent).
*   **Rationale:** Dropping a pipeline stage without specifying its replacement leaves finding consolidation undefined, and an unproven platform claim is doing load-bearing work in the dispatch design.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The depth-2 evidence is checkable (this review runs at depth 2), and no dedup procedure exists in the text.
*   ***Proposed Edit:***
    *   Location: `### Roles & dispatch` (L172–178); D7 (L160–171).
    *   Change: Add to the Roles table (Elephant row): "Consolidation procedure: the Elephant merges duplicate findings (same target lines + same discrepancy), normalizes severity to the assigned standard, and assigns stable ids (`<reviewer>-<round>-<n>`); overlaps are recorded in the report." In D7 / the Synthesizer row, replace "(no nesting below depth 1)" with "(direct dispatch from the Elephant by design — flat dispatch keeps attribution simple; this is a design choice, not a platform limit: depth-2 spawning works in this environment, as this review itself runs at depth 2)."

### [Issue 16] [design_critic-2-14] [`design_critic`] - Severity: Major
*   **Affected Scope:** Lines 31–34 (§3 Problem Statement)
*   **Discrepancy Description:** No count of AEP design docs, no drift incidents, no review load. The "concrete evidence" offered is the pilot round-1 review of this very document — which demonstrates the instrument works, not the scale of the problem in AEP. The doc never says whether adoption is fixing observed drift or is precautionary.
*   **Rationale:** The standard's core principle requires a fresh reader to understand the business motivation, including its magnitude; without a baseline, the rollout's value cannot be weighed against its cost.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Shared edit E-Q with zoom_out-2-2 and zoom_out-2-3. The baseline below uses only verified counts (AEP `docs/` holds 22 `.md` files) and states the precautionary position honestly rather than inventing incident counts.
*   ***Proposed Edit:***
    *   Location: §3 (L31–34).
    *   Change: Append: "Scale baseline (verified 2026-11-06): adoption is precautionary — no drift incident or review-load count is recorded in this document. The design corpus the pilot draws on is 22 documents under AEP `docs/` plus the dated plans under `~/workspace/plans/`; the Phase 0 pilot log records design docs produced per month as the demand baseline for the Phase 1 value judgment (§14 decision 5). The pilot round-1 review (65 findings) is evidence the instrument works, not evidence of the problem's scale."

### [Issue 17] [design_critic-2-15] [`design_critic`] - Severity: Nit
*   **Affected Scope:** Line 129 (attribution Notes text)
*   **Discrepancy Description:** "Record the exception in the Notes column," but the specified Notes text is 'Adapted (D3); bundle under `reference/elephant-goldfish-model/`; pinned `e9e1f06a`.' — it never mentions the fork-naming-convention exception or its reason.
*   **Rationale:** As stated in the discrepancy: the prescribed literal text contradicts the instruction it follows.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Clearly worth fixing (a required deliverable's literal text contradicts its own instruction). Shared edit E-L with implementation_readiness-2-6.
*   ***Proposed Edit:***
    *   Location: D4 wrappers bullet (L129) and `### AEP machinery` (L142) — both occurrences.
    *   Change: Replace 'Adapted (D3); bundle under `reference/elephant-goldfish-model/`; pinned `e9e1f06a`.' with 'Adapted (D3); exception to the README fork-naming convention — D1 sources from upstream (fork is a pure mirror); bundle under `reference/elephant-goldfish-model/`; pinned `e9e1f06a`.' in both places.

### [Issue 18] [design_critic-2-16] [`design_critic`] - Severity: Nit
*   **Affected Scope:** Lines 273, 287–296 (independent verifier's scope, stated two ways)
*   **Discrepancy Description:** §10.3 says the verification subagent "performs exactly these two checks," but the antecedent is ambiguous (line-existence + standard-name? or those plus the memory check = three?), while §10.4 step 3 describes broader verification ("did reviewers actually read persona/standards/target? were findings evidence-backed?").
*   **Rationale:** As stated in the discrepancy: two overlapping verification specifications under near-identical headings.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Normative ambiguity in a gate definition is clearly worth one edit.
*   ***Proposed Edit:***
    *   Location: §10.3 (L273); §10.4 step 3 (L291–293).
    *   Change: Replace "The independent verification subagent in §10.4 step 3 performs exactly these two checks against the filed reports." with "The independent verification subagent in §10.4 step 3 performs exactly these two checks against the filed reports: (a) every cited line exists in the target at the stated range; (b) the named standard is the assigned one. §10.4 step 3's questions ('did reviewers actually read persona/standards/target? were findings evidence-backed?') are answered by those two checks, not by additional checks." In §10.4 step 3, replace "(did reviewers actually read persona/standards/target? were findings evidence-backed?)" with "(via the two checks defined in §10.3)".

### [Issue 19] [design_critic-2-17] [`design_critic`] - Severity: Nit
*   **Affected Scope:** Line 278 (readiness gate passes with an empty GoldfishContext)
*   **Discrepancy Description:** "An empty list counts as provided," so a loop can start with zero context — yet for this document the pilot's context (companion doc, README, repo clone) was essential to the review.
*   **Rationale:** As stated in the discrepancy: the gate's purpose is unintelligible if empty context passes it.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. One-line fix, clearly worth it.
*   ***Proposed Edit:***
    *   Location: §10.3 readiness gate (L278).
    *   Change: Replace "(an empty list counts as provided)" with "(an empty list counts as provided only for a self-contained target; a design-doc review with external references must list them — this document's pilot supplied the companion doc, README, and repo clone)."

### [Issue 20] [design_critic-2-18] [`design_critic`] - Severity: Nit
*   **Affected Scope:** Lines 321–322 (§12 "Skill content is pure markdown")
*   **Discrepancy Description:** "Skill content is pure markdown" is false for the bundle as a whole: the vendored tree contains per-skill `openai.yaml`, `test_scenarios.yaml`, `icon.svg`, `references/*.json`, and `docs/assets/*.svg` — none of which is markdown. The claim is true only of the adapted `SKILL.md` files.
*   **Rationale:** As stated in the discrepancy: a false factual claim in the security notes.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Factual error; verified against the bundle tree. Clearly worth fixing.
*   ***Proposed Edit:***
    *   Location: §12 (L321–322).
    *   Change: Replace "Skill content is pure markdown: no network calls, no config modification, no credential access, no auto-updater." with "Adapted skill content (`SKILL.md` files) is pure markdown: no network calls, no config modification, no credential access, no auto-updater. The vendored bundle also contains non-markdown files (`agents/openai.yaml`, `test_scenarios.yaml`, `assets/icon.svg`, `references/*.json`, `docs/assets/*.svg`); the pure-markdown claim covers the adapted skills only."

### [Issue 21] [design_critic-2-19] [`design_critic`] - Severity: Nit
*   **Affected Scope:** Lines 182–186, 238–245 (`pytest` noted absent, no install instruction, yet §9.5 step 2 requires it)
*   **Discrepancy Description:** §9.1 notes "`pytest` installed separately (absent on this VM — required for `pytest tests/unit`)" but gives no install command or step; a fresh-VM implementer has a prerequisite with no procedure.
*   **Rationale:** As stated in the discrepancy: a prerequisite with no procedure.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. `pytest` absence verified on this VM. Shared edit E-O with implementation_readiness-2-9.
*   ***Proposed Edit:***
    *   Location: §9.1 (L182–186); §9.5 step 2 (L243).
    *   Change: In §9.1, replace "`pytest` installed separately (absent on this VM — required for `pytest tests/unit`)" with "`pytest`, installed before §9.5 step 2 with `python3 -m pip install pytest` on the fresh VM (absent on this VM — record the installed version in the pilot log)." In §9.5 step 2, replace "`pytest tests/unit` in the cloned repo." with "`pytest tests/unit` in the cloned repo root (the `elephant-goldfish-model` checkout from §9.2); pass = exit code 0, all tests pass."

### [Issue 22] [structural-2-1] [`structural`] - Severity: Major
*   **Affected Scope:** Line 206 (§9.2 heading swallowed into paragraph)
*   **Discrepancy Description:** `### Native installs for the other harnesses (commands from the bundle's docs/harnesses.md install table)` is appended inline to the end of the §9.2 paragraph (`…as plugin:egm:egm-*). ### Native installs…`), not on its own line. It therefore renders as plain text, not a heading, and the Claude Code / Antigravity / Codex / OpenCode installs (lines 208–212) have no heading at all.
*   **Rationale:** Breaks heading hierarchy and the §9.2/§9.3 numbering symmetry; a reader scanning headings misses the whole non-Muse install subsection.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified in the target file (line 206 ends with the heading text inline).
*   ***Proposed Edit:***
    *   Location: §9.2 (L206).
    *   Change: Move `### Native installs for the other harnesses (commands from the bundle's docs/harnesses.md install table)` onto its own line (blank line before and after), so it renders as a heading.

### [Issue 23] [structural-2-2] [`structural`] - Severity: Major
*   **Affected Scope:** Lines 140, 172 (unnumbered H3s interrupt the D1–D7 decision sequence in §8)
*   **Discrepancy Description:** `### AEP machinery` (line 140) sits between D4 (line 119) and D5 (line 144), and `### Roles & dispatch` (line 172) sits after D7 (line 160) under the same H2. Neither is a decision, neither carries a D-number, and neither is numbered 8.x.
*   **Rationale:** A reader expecting D1–D7 contiguous must skip a reference-glossary block mid-sequence; the decision list is not cleanly enumerable.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Shared edit E-T with structural-2-8 (the `AEP machinery` paragraph is also a duplicate of D4).
*   ***Proposed Edit:***
    *   Location: §8 (L140, L172).
    *   Change: Move the `AEP machinery` block to after D7 and rename it `### 8.1 AEP machinery`; rename `### Roles & dispatch` to `### 8.2 Roles & dispatch`. D1–D7 are then contiguous (lines 93–171) with the two reference subsections numbered after them. (The `AEP machinery` paragraph's content is trimmed per Issue 29.)

### [Issue 24] [structural-2-3] [`structural`] - Severity: Major
*   **Affected Scope:** Lines 283, 297 (unnumbered H3s break the §10 numbering sequence and duplicate §10.4)
*   **Discrepancy Description:** `### Loop bounds` (line 283) sits between `### 10.3 Dispatch` (271) and `### 10.4 Verification` (287), and `### Verification checks` (line 297) follows 10.4 as an unnumbered sibling. The latter restates §10.4 steps 1–4 as checks (1)–(5), including the same `agents/zoom_out.md:44` pilot check already in §9.5 step 4 (line 245) and §10.4.
*   **Rationale:** Two overlapping verification specifications under near-identical headings, with colliding numbering — a citation to "check (1)" vs "step 1" is ambiguous, and §9.5 line 245's phrase "§10.4's Verification checks" conflates the two sections.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The numbering collision and the duplicated check list are both real.
*   ***Proposed Edit:***
    *   Location: §10 (L283–299); §9.5 step 4 (L245); §6 (L52).
    *   Change: Rename `### Loop bounds` to `### 10.4 Loop bounds`; rename `### 10.4 Verification` to `### 10.5 Verification`; rename `### Verification checks` to `### 10.6 Verification checks`. In §10.5 step 4, add: "(verified by §10.6 check (1))"; in §10.6, add the headnote: "§10.5 steps 1–4 are the procedure; the checks below are the normative test list — a step and a check with the same number are not the same item." Fix L245's "§10.4's Verification checks" to "§10.6 Verification checks". Update the §6 pointer "bounds in §10.3" to "bounds in §10.4 Loop bounds" (see also Issue 34) and any other `§10.4` cross-references to the new numbers.

### [Issue 25] [structural-2-4] [`structural`] - Severity: Major
*   **Affected Scope:** Lines 225, 295, 313 (dangling Issue references with no definition)
*   **Discrepancy Description:** Line 225 cites "Issue 25" and "Issue 49"; line 295 cites "Issue 17"; line 313 cites "Issue 37". No issue list, link, or definition exists anywhere in the document or Appendix, and no repository/URL is given.
*   **Rationale:** Link-compliance gap — a fresh reader cannot resolve any of the four references; they function as unexplained pointers to an external tracker that is never named.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The "Issue N" labels are round-1 resolve-report issue numbers that leaked into the target document; they resolve to nothing a reader of this document can find. Shared edit E-J with comprehension-2-7.
*   ***Proposed Edit:***
    *   Location: §9.3 (L225); §10.4 step 4 (L295); §11 priority paragraph (L313).
    *   Change: Replace "invocation in Issue 25" with "invocation in D5"; replace "(defined in Issue 49)" with "(defined in D5)"; replace "(see Issue 17)" with "(see D3 item 3)"; replace "(see Issue 37)" with "(see §10.3 priority rationale)". Add the rule: no bare "Issue N" references remain in the document; upstream GitHub issues are cited only with repo + link (e.g. #252).

### [Issue 26] [structural-2-5] [`structural`] - Severity: Major
*   **Affected Scope:** Lines 41, 49–53 (forward references to D-labels before they are defined)
*   **Discrepancy Description:** §5 line 41 cites "(D4)" and §6 lines 49–53 cite D6 and §10.4/§10.3, but D1–D7 are only defined in §8 (lines 93–170).
*   **Rationale:** §§5–6 are not self-contained in reading order; the Alternatives/Risks sections depend on labels introduced ~50–100 lines later, forcing forward jumps with no up-front decision index.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. A decision index before first use resolves the forward references without restructuring the sections.
*   ***Proposed Edit:***
    *   Location: After §4 (L37); §5 intro (L39); §6 intro (L47).
    *   Change: Insert after §4 a "Decisions at a glance (defined in §8)" index: "D1 source from upstream at a pinned SHA; D2 vendor the bundle intact; D3 adaptation layer; D4 AEP layout; D5 SkillSpector gate; D6 Muse read-only caveat; D7 named-agent fallback." Add to the §5 and §6 intros: "D-labels refer to §8."

### [Issue 27] [structural-2-6] [`structural`] - Severity: Major
*   **Affected Scope:** Lines 35–37 (§4 Proposed Architecture is a stub)
*   **Discrepancy Description:** The section required by the standard is a single 3-line paragraph that is only a component-map sentence plus "The existing §§8–10 keep their detail; this section is the map, with pointers to them."
*   **Rationale:** The core architecture section contains no architecture of its own — its substance lives in §8 (decisions) and §§9–10 (environments), which are not architecture sections — so the standard's component-layout/data-flow area is present in name only at its expected location.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Same root cause as design_critic-2-5 and comprehension-2-1. Shared edit E-E — apply Issue 7's edit once; it covers all three findings.
*   ***Proposed Edit:***
    *   Location: §4 (L35–37). Same fix as Issue 7, applied once.
    *   Change: Adopt Issue 7's replacement text (data-flow sequence, artifact lifecycle, concurrency model, failure propagation).

### [Issue 28] [structural-2-7] [`structural`] - Severity: Major
*   **Affected Scope:** Lines 24–29 vs 334–342 (Goals and Non-Goals split across the document)
*   **Discrepancy Description:** The standard lists "Goals & Non-Goals" as one area. The doc puts "Goals" in §2 (lines 24–29) and "Non-goals" in §13 (lines 334–342), ~300 lines apart, with no cross-reference in either direction.
*   **Rationale:** The paired scope statement is structurally severed; a reader of §2 has no pointer to the exclusions that bound those goals.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Cross-references repair the split without moving either section.
*   ***Proposed Edit:***
    *   Location: §2 (L24–29); §13 (L334–342).
    *   Change: Append to §2: "Non-goals: see §13." Prepend to §13: "Goals: see §2."

### [Issue 29] [structural-2-8] [`structural`] - Severity: Major
*   **Affected Scope:** Line 142 (`### AEP machinery` is a single-paragraph restatement of D4)
*   **Discrepancy Description:** Line 142 re-states, in one unbroken paragraph, the vendor-integrity / skills-freshness / manifest-format / scope-file / PROVENANCE-fields / vendor-sha256-command / attribution-row definitions already given in the D4 bullets (lines 121–129, including the identical `sha256sum` command from line 125).
*   **Rationale:** Duplicate specification in a different shape (prose paragraph vs bullets) under a non-decision heading — the two copies can drift, and the reader cannot tell which is normative.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The paragraph duplicates D4's bullets in full. Shared edit E-T with structural-2-2.
*   ***Proposed Edit:***
    *   Location: `### AEP machinery` (L142, moved to §8.1 per Issue 23).
    *   Change: Replace the paragraph with a single pointer sentence: "Reference glossary for D4 — the normative definitions are the D4 bullets (lines 121–129); this subsection is a pointer only and states no additional requirements." (D4 remains the single normative source.)

### [Issue 30] [structural-2-9] [`structural`] - Severity: Major
*   **Affected Scope:** Lines 273–281 (§10.3 packs four topics under one heading with no subheadings)
*   **Discrepancy Description:** `### 10.3 Dispatch` contains, in sequence, the reviewer brief (line 273), approval gates (274–276), the readiness/section-approval gate definitions (278), the overlap-with-existing-tools discussion (279), and the brief-contents/verbatim-prompt/failure-handling paragraph (281) — as bullets then unheaded paragraphs.
*   **Rationale:** Asymmetric with §9, which splits the same material into numbered 9.1–9.5 subsections; §10.3 has no internal navigation for its five distinct topics.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: §10.3 (L273–281).
    *   Change: Split into H4 subsections, keeping all existing text: `#### 10.3.1 Reviewer brief` (L273 paragraph), `#### 10.3.2 Approval gates` (L274–276), `#### 10.3.3 Readiness and section-approval gates` (L278), `#### 10.3.4 Overlap with existing tools` (L279), `#### 10.3.5 Brief contents and failure handling` (L281).

### [Issue 31] [structural-2-10] [`structural`] - Severity: Nit
*   **Affected Scope:** Lines 24–35 (Goals precede Problem Statement)
*   **Discrepancy Description:** §2 Goals comes before §3 Problem Statement, inverting the standard's listed order (Problem, then Goals & Non-Goals).
*   **Rationale:** Goals are stated before the problem they serve is introduced; minor ordering deviation, content is otherwise present.
*   ***AI Suggestion:*** DECLINE
*   ***Justification:*** Cosmetic ordering deviation; the content is present and the cross-references added per Issue 28 make the pairing navigable. Renumbering §§2–3 would churn every cross-reference in the document. Record only.
*   ***Proposed Edit:***
    *   Location: None.
    *   Change: None.

### [Issue 32] [structural-2-11] [`structural`] - Severity: Nit
*   **Affected Scope:** Line 315 (`### Phase 2 file-change list` unnumbered under §11)
*   **Discrepancy Description:** Same unnumbered-H3 pattern as lines 140/172/283/297, under `## 11. Rollout`. Should be 11.x or a bold lead-in.
*   **Rationale:** Breaks the numbered-subsection symmetry of §§9–10.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Clearly worth it: one-word fix in the same edit batch as Issues 23–24, restoring the numbering symmetry those fixes establish.
*   ***Proposed Edit:***
    *   Location: §11 (L315).
    *   Change: Rename `### Phase 2 file-change list` to `### 11.1 Phase 2 file-change list`.

### [Issue 33] [structural-2-12] [`structural`] - Severity: Nit
*   **Affected Scope:** Lines 21, 32–33 (pathless report reference)
*   **Discrepancy Description:** The pilot report is cited as bare filename `2026-11-06-egm-adoption-aep-goldfish-review.md` with no directory path or link.
*   **Rationale:** A fresh reader cannot locate the cited report from the citation alone.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. One-line fix, clearly worth it. Shared edit E-R with comprehension-2-16 (path part).
*   ***Proposed Edit:***
    *   Location: §1 (L21); §3 (L33).
    *   Change: Replace the bare filename in both places with the full path `~/workspace/plans/2026-11-06-egm-adoption-aep-goldfish-review.md`.

### [Issue 34] [structural-2-13] [`structural`] - Severity: Nit
*   **Affected Scope:** Lines 49, 52 (imprecise section pointers)
*   **Discrepancy Description:** Line 49 "(see §8)" for the D6 caveat points at the whole 88-line §8 rather than D6 (line 153); line 52 "bounds in §10.3" points at §10.3, but the bounds actually live in the unnumbered `### Loop bounds` block (lines 283–285), not in §10.3.
*   **Rationale:** Pointers resolve to the wrong granularity, compounding the unnumbered-heading findings above.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. One-line fixes each; coordinate with the Issue 24 renumbering (Loop bounds becomes §10.4).
*   ***Proposed Edit:***
    *   Location: §6 (L49, L52).
    *   Change: Replace "(see §8)" with "(see D6, §8)". Replace "bounds in §10.3" with "bounds in §10.4 Loop bounds".

### [Issue 35] [structural-2-14] [`structural`] - Severity: Nit
*   **Affected Scope:** Line 354 (`## Appendix — Sources` unnumbered after numbered §§1–14)
*   **Discrepancy Description:** The Appendix is an H2 with no number following a strictly numbered 1–14 sequence.
*   **Rationale:** Minor inconsistency; conventional but breaks the document's own numbering scheme.
*   ***AI Suggestion:*** SETTLED
*   ***Justification:*** Settled — same scope and issue as round-1 `structural-1-7` (DECLINE — Appendix unnumbered by convention). Per the loop's settled rule, a settled finding is not re-opened. No fix proposed; recorded here only.
*   ***Proposed Edit:***
    *   Location: None.
    *   Change: None. Matches round-1 disposition: DECLINE (structural-1-7).

### [Issue 36] [structural-2-15] [`structural`] - Severity: Nit
*   **Affected Scope:** Lines 24, 334 (inconsistent capitalisation)
*   **Discrepancy Description:** §2 is "Goals", §13 is "Non-goals" (lowercase g); §7's title carries a parenthetical qualifier "(verified)" that no other H2 uses.
*   **Rationale:** Minor title-style inconsistency.
*   ***AI Suggestion:*** DECLINE
*   ***Justification:*** Cosmetic; meaning is unambiguous and no reader can misread a scope from it. Record only.
*   ***Proposed Edit:***
    *   Location: None.
    *   Change: None.

### [Issue 37] [structural-2-16] [`structural`] - Severity: Nit
*   **Affected Scope:** Lines 356–358 (Appendix as three very long single-line bullets)
*   **Discrepancy Description:** Each Appendix bullet is a single long line packing up to six links (line 357) or seven references (line 358). Valid Markdown, but the densest formatting in the document.
*   **Rationale:** Readability/navigation nit only; no link is malformed.
*   ***AI Suggestion:*** DECLINE
*   ***Justification:*** Valid Markdown with no malformed link; reflowing the lines is churn with no correctness gain. Record only.
*   ***Proposed Edit:***
    *   Location: None.
    *   Change: None.

### [Issue 38] [implementation_readiness-2-3] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Lines 113 vs 266 (`skill.yaml` production method contradicts itself)
*   **Discrepancy Description:** D3 item 1 (L113) says `skill.yaml` is "hand-written (the repo norm — 61 `skill.yaml` files exist in `skills/` and no script generates them)," while §10.2 (L266) says `skill.yaml` is "generated from frontmatter" and §9.3 repeats "generated `skill.yaml`." No generator script, command, or template is named anywhere, so neither the hand-written nor the generated route is actually specified.
*   **Rationale:** The implementer must choose the production method for 7 required deliverables, and the two instructions point opposite ways.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Direct contradiction, verified in the text. Shared edit E-K with comprehension-2-8.
*   ***Proposed Edit:***
    *   Location: §9.3 (L222); §10.2 layout (L266); D4 wrappers bullet (L129, "generated `skill.yaml`" wording).
    *   Change: Standardize on hand-written everywhere: replace §9.3's "generated `skill.yaml`" with "hand-written `skill.yaml` (D3 item 1)"; replace §10.2's "`skill.yaml` # generated from frontmatter" with "`skill.yaml` # hand-written per D3 item 1"; replace D4's "The generated `skill.yaml` files" with "The hand-written `skill.yaml` files".

### [Issue 39] [implementation_readiness-2-4] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Line 317 (manifest regeneration command is broken as written)
*   **Discrepancy Description:** "Regenerated via `check_skills_manifest.py --write`" omits the `--root` argument that `scripts/check_skills_manifest.py` requires (`--root` is `required=True`; the `--check` form at L142 correctly shows `--root skills`). The command as written exits with an argparse error. Working directory is also unstated.
*   **Rationale:** A step that cannot run is an actionability gap, not a style issue; the correct invocation exists in the same document at L142 and should be used consistently.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: `scripts/check_skills_manifest.py:187` sets `--root` `required=True`; `--write` exists (line 190).
*   ***Proposed Edit:***
    *   Location: §11 Phase 2 file-change list (L317).
    *   Change: Replace "regenerated via `check_skills_manifest.py --write`" with "regenerated via `scripts/check_skills_manifest.py --root skills --write` run from the repo root".

### [Issue 40] [implementation_readiness-2-5] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Line 125 (`PROVENANCE.md` vs `.sha256` generation order unspecified, and `PROVENANCE.md` field values undetermined)
*   **Discrepancy Description:** L125 lists sha-file generation and `PROVENANCE.md` writing in one bullet with no order. `PROVENANCE.md` lives inside the vendored tree, and the esf precedent (verified: `.github/vendor-esf.sha256` contains `./PROVENANCE.md`) shows it must be included in the sha file — generating the sha file first leaves it unlisted, so the vendor-integrity unlisted-files check fails. Separately, the field values are not given: "Pinned commit (+ subject)" — the commit subject string appears nowhere in the document; "Snapshot date" format is unspecified; "Excluded from the vendor" content is unspecified.
*   **Rationale:** Ordering is load-bearing for the CI gate, and the deliverable's content is left for the implementer to compose.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The ordering hazard and the missing field values are both real. The commit subject string is not recorded in any file available to this resolve; the fix gives the command to obtain it at vendor time rather than inventing it.
*   ***Proposed Edit:***
    *   Location: D4 bundle bullet (L125).
    *   Change: Append: "Order: write `PROVENANCE.md` first, then generate the `.sha256` file, so `PROVENANCE.md` itself is listed (esf precedent: `.github/vendor-esf.sha256` contains `./PROVENANCE.md`). Field values: Upstream URL `https://github.com/google/elephant-goldfish-model`; Pinned commit `e9e1f06a` + subject (copied from `git log -1 --format=%s e9e1f06a` at vendor time); Snapshot date `YYYY-MM-DD` (the vendor date); License `Apache-2.0`; Excluded from the vendor: `site/`, `scripts/`, `tests/`, `adapters/`, per-host plugin manifests, all other repo-root files; Purpose, Updating, and Update history per the esf pattern."

### [Issue 41] [implementation_readiness-2-6] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Line 129 (attribution-row instruction contradicts its own literal Notes text)
*   **Discrepancy Description:** L129 instructs "record the exception in the Notes column" (the exception to the README's fork-naming convention), then prescribes Notes verbatim as `'Adapted (D3); bundle under reference/elephant-goldfish-model/; pinned e9e1f06a.'` — which contains no mention of the fork-naming exception. An implementer copying the given text violates the instruction; an implementer following the instruction must invent the exception wording. (Same literal text repeated at L142.)
*   **Rationale:** Internal contradiction on a required deliverable; the README convention it excepts from is verified real.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Shared edit E-L with design_critic-2-15 — apply Issue 17's edit once; it covers both findings.
*   ***Proposed Edit:***
    *   Location: D4 wrappers bullet (L129) and `### AEP machinery` (L142). Same fix as Issue 17, applied once.
    *   Change: Adopt Issue 17's replacement Notes text (including the fork-naming-convention exception) in both places.

### [Issue 42] [implementation_readiness-2-7] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Lines 116–117 (path-rewrite procedure unspecified; two wordings of the Muse routing line)
*   **Discrepancy Description:** The mapping table is given, but no mechanism (sed command, script, manual edit), no search pattern, and no occurrence counts for the 5 non-pilot skills (counts are given only for the two pilot skills, with no procedure to compute the rest). The routing line also appears in two forms: L116 `*"In Muse, read `docs/muse.md` first."* vs L117 `In Muse, read <bundle>/docs/muse.md first.` (the pilot uses the latter, with `~`). The mapping's bare `agents/` → `<bundle>/agents/` form also does not cover the pilot's already-absolute `~/workspace/egm/agents/...` references.
*   **Rationale:** The D3 adaptation is the core per-file transformation of this plan (7 files × ~10 references each) and its execution is left to implementer inference.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. All four sub-points are true of the text.
*   ***Proposed Edit:***
    *   Location: D3 item 3 (L116–117).
    *   Change: Unify the routing line on the L117 form: replace L116's `*"In Muse, read `docs/muse.md` first."* with `*"In Muse, read <bundle>/docs/muse.md first."*` (where `<bundle>` is `~/workspace/egm` in Environment B). Append to item 3: "Mechanism: apply the mapping mechanically (one `sed` per row, or manual edit) and verify with §10.6 Verification check (1). Record per-skill occurrence counts for all 7 skills in the Phase 2 PR body (pilot counts are given for the 2 installed skills; counts for the remaining 5 are computed the same way at Phase 1). Already-absolute pilot references of the form `~/workspace/egm/...` resolve against the bundle root as-is in Environment B; in AEP wrappers they become `../../reference/elephant-goldfish-model/...`."

### [Issue 43] [implementation_readiness-2-8] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Lines 125, 317 (the tenth `vendor-integrity` `run:` block has no content)
*   **Discrepancy Description:** "Same `sha256sum -c` + unlisted-files + symlink pattern as the existing nine blocks" — no YAML text, no placement/order within the job (after `humanizer`? alphabetical? insertion point matters for reviewability). The pattern is visible in the repo (verified: 9 blocks in `ci.yml`, each `cd reference/<tree>` + `sha256sum -c` + `comm -23` unlisted-files check + broken-symlink loop), but the plan requires the implementer to reconstruct it by analogy rather than supplying it.
*   **Rationale:** The standard requires precise logic changes per file; a CI job edit that gates the whole PR should be spelled out, not inferred.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The pattern is verified in the repo, so the literal block can be stated.
*   ***Proposed Edit:***
    *   Location: D4 bundle bullet (L125); §11 Phase 2 file-change list (L317).
    *   Change: Replace "same `sha256sum -c` + unlisted-files + symlink pattern as the existing nine blocks" with the literal block to insert after the `humanizer` block in `.github/workflows/ci.yml` (pattern identical to the existing nine blocks, e.g. the esf block):
      ```
            - run: |
                cd reference/elephant-goldfish-model
                sha256sum -c ../../.github/vendor-elephant-goldfish-model.sha256
                comm -23 <(find . -type f | sort) <(cut -d' ' -f3- ../../.github/vendor-elephant-goldfish-model.sha256 | sed 's|^\./|./|' | sort) | grep -q . && { echo "ERROR: unlisted files"; exit 1; } || true
                find . -type l | while read -r link; do test -e "$link" || { echo "ERROR: broken symlink $link"; exit 1; }; done
      ```

### [Issue 44] [implementation_readiness-2-9] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Lines 184, 243 (`pytest` prerequisite has no install step; `pytest tests/unit` has no working directory or expected result)
*   **Discrepancy Description:** L184 admits pytest is "absent on this VM — required for `pytest tests/unit`" and gives no install command (pip/apt/venv, version pin). L243 gives the bare command with no cwd (cloned repo root is implied, never stated) and no pass criterion (all tests pass? exit code 0? known failures?).
*   **Rationale:** A verification step with no setup and no expected outcome cannot be executed or judged by a fresh implementer.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. `pytest` absence verified on this VM. Shared edit E-O with design_critic-2-19 — apply Issue 21's edit once; it covers both findings.
*   ***Proposed Edit:***
    *   Location: §9.1 (L184); §9.5 step 2 (L243). Same fix as Issue 21, applied once.
    *   Change: Adopt Issue 21's replacement text (pip install command + version recorded in the pilot log; cwd = cloned repo root; pass = exit code 0, all tests pass).

### [Issue 45] [implementation_readiness-2-10] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Line 244 (the §9.5 step 3 E2E fixture is not executable as specified)
*   **Discrepancy Description:** "Run headless via `muse exec` in a temporary workspace against the installed cache only" — no `muse exec` command line, no prompt text, no temporary-workspace path, no definition of "the installed cache," and no pass/fail criteria beyond the stage sequence "brainstorm → draft → uninterrupted review." The hand-exercise variant says to "record which gates fired" with no recording destination. The fixture design `muse-wonder-1.0` is named but its location/contents are not given.
*   **Rationale:** The standard's Test Plan requirement — the acceptance test for Environment A is described, not specified.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. `TESTING.md` is not in the vendored tree (verified); it exists upstream at the URL below (verified via bundle `docs/index.md:11`). Shared edit E-I with design_critic-2-9 (part) and comprehension-2-11.
*   ***Proposed Edit:***
    *   Location: §9.5 step 3 (L243–244).
    *   Change: Replace step 3 with: "End-to-end acceptance: the upstream fixture recorded in the Testing playbook ([TESTING.md](https://github.com/google/elephant-goldfish-model/blob/main/TESTING.md), 'Harness test record', Muse row, 2026-10-30) — fixture design `muse-wonder-1.0` (line-count design). `TESTING.md` lives at the upstream repo root and is NOT vendored. Run headless via `muse exec` in a temporary workspace (`/tmp/egm-e2e-<shape>/`) against the installed cache only — 'installed cache' means the harness's installed plugin/skill cache on that VM (the plugin installed per §9.2), not the upstream checkout — prompt naming `docs/muse.md`, approvals simulated up front: brainstorm → draft → uninterrupted review. Run once per VM shape. Pass: all three stages complete and the review report is filed. Hand exercise (first time per shape): run the same fixture with approvals given by hand at each gate instead of simulated, and record which gates fired in the pilot log (`~/workspace/plans/<date>-egm-pilot-log.md`)."

### [Issue 46] [implementation_readiness-2-11] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Lines 214–236 (§9.3 Path 2 has no install steps at all)
*   **Discrepancy Description:** §9.3 is layout description only (bundle at `<install-root>/egm/`, skills at `<install-root>/skills/egm-*/`, gate-scan "where available"). There is no command to obtain the bundle (clone? copy from where?), no copy step, no adaptation step invoking D3, and no `skill.yaml` creation step. This matters because Path 2 is the fallback for every headless VM and the template for Environment B.
*   **Rationale:** An install path with zero executable steps is a design summary, not an implementation plan.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: §9.3 contains no commands.
*   ***Proposed Edit:***
    *   Location: §9.3 (L214–236).
    *   Change: Append the install steps: "1) Clone upstream at the pinned SHA (`git clone https://github.com/google/elephant-goldfish-model.git <install-root>/egm-checkout && cd <install-root>/egm-checkout && git fetch --depth 1 origin e9e1f06a && git checkout e9e1f06a`). 2) Copy the bundle to `<install-root>/egm/`. 3) Adapt the 7 `SKILL.md` files per D3 into `<install-root>/skills/egm-*/`. 4) Hand-write the 7 `skill.yaml` files per D3 item 1. 5) Gate-scan each adapted skill (D5) where the gate is available, else per the §9.3 fallback (scan once on the authoring machine, scores in the install notes). 6) Verify per §10.6 Verification checks."

### [Issue 47] [implementation_readiness-2-12] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** §11 (Lines 301–313) + Lines 257–269 (no file-change lists for Phase 0 or Phase 1; local bundle README content unspecified)
*   **Discrepancy Description:** Only Phase 2 has a file-change list. Phase 0 ("bundle under `~/workspace/egm/`, 2 adapted skills") and Phase 1 ("remaining 5 skills") name no files — which bundle files (39 or 90, per Blocker 1?), which two skills' exact paths, and the Phase 1 drift-report destination are all unstated. L262 lists the local `README.md` pin-record fields but gives no values, format, or date format, and "re-written on every re-sync" has no trigger definition beyond L269's cadence sentence.
*   **Rationale:** The standard requires phased work with an explicit file boundary per phase; two of four phases have none.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The 90-file count is now established (Issue 2), so the Phase 0/1 lists can state it.
*   ***Proposed Edit:***
    *   Location: §11 (after the Phase 2 file-change list, L317); §10.2 layout (L262).
    *   Change: Add "### 11.2 Phase 0 file-change list — Created: `~/workspace/egm/` bundle (90 files at the pinned SHA, per §11.1); `~/workspace/custom-skills/egm-review/` + `~/workspace/custom-skills/egm-review-loop/` (each `SKILL.md` + `skill.yaml`); pilot report + pilot log under `~/workspace/plans/`. Modified: none. Deleted: none." Add "### 11.3 Phase 1 file-change list — Created: the remaining 5 `~/workspace/custom-skills/egm-*/` dirs (each `SKILL.md` + `skill.yaml`); drift report at `~/workspace/plans/<date>-<topic>-drift.md` (destination named in advance). Modified: none. Deleted: none." In §10.2, replace the README note with: "`README.md` — local pin record: upstream URL `https://github.com/google/elephant-goldfish-model`, pinned SHA (`e9e1f06a`), snapshot date `YYYY-MM-DD`, license (Apache-2.0). Written at install time; re-written on every re-sync (trigger: any upstream re-vendor or local adaptation change, per the §10.2 cadence)."

### [Issue 48] [implementation_readiness-2-13] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Line 269 (the live→repo sync procedure is referenced, not specified)
*   **Discrepancy Description:** "Same procedure as the 2026-11-06 skill sync" — no script, command, source/destination mapping, or document reference is given. A fresh implementer cannot execute the sync that keeps the canonical AEP wrappers and the local adapted skills consistent, which is the plan's own stated drift control.
*   **Rationale:** A procedure defined only by pointing at a past event is not an actionable step.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. No sync script exists in the AEP repo (verified — `scripts/` has no skill-sync script), so the procedure must be spelled out inline. Shared edit E-N with comprehension-2-12.
*   ***Proposed Edit:***
    *   Location: §10.2 (L269).
    *   Change: Replace "Same procedure as the 2026-11-06 skill sync" with the inline procedure: "Sync steps (live→repo direction only): 1) diff local `custom-skills/egm-*/` against repo `skills/egm-*/`; 2) copy changed local files into the repo wrappers; 3) regenerate the manifest (`scripts/check_skills_manifest.py --root skills --write` from the repo root); 4) verify with the §10.4 step 4 normalize-then-diff check; 5) commit per Conventional Commits. Owner: the agent running the sync (the Elephant / main agent session that owns the change) — not a separate role."

### [Issue 49] [implementation_readiness-2-14] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Line 285 (no per-reviewer timeout is set, and no owner decision exists to set it)
*   **Discrepancy Description:** "Timeout: no fixed per-reviewer timeout is set in this document — the pilot log records per-reviewer elapsed time, and the timeout for Phase 1 is set from that evidence by the owner." §14 lists four owner decisions; none covers the timeout, its default, or its decision procedure. Phase 1's review loop therefore cannot run bounded, and "propagate failures and timeouts" has no timeout to propagate.
*   **Rationale:** An explicitly deferred parameter with no owner-decision hook is a design choice left open, violating the zero-decision rule.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Shared edit E-D with design_critic-2-4, comprehension-2-20, and zoom_out-2-9 — apply Issue 6's edit once; it covers all four findings (30-minute interim pilot timeout + §14 decision 6 for the Phase 1 timeout/budget).
*   ***Proposed Edit:***
    *   Location: `### Loop bounds` (L285); §14 (new decision 6). Same fix as Issue 6, applied once.
    *   Change: Adopt Issue 6's replacement text.

### [Issue 50] [implementation_readiness-2-15] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Lines 291–292 + 348 (the Phase 0 pilot target is unnamed)
*   **Discrepancy Description:** §10.4 step 3 says run the loop "once against a real design document" with no document named; §14 decision 2 says "the AEP repo, with a PR as the target state" — a repo/PR, not a document — and no PR number or document path is given. The pilot's pass criterion ("all reviewers run, report filed") cannot be attempted until the implementer chooses the target.
*   **Rationale:** The pilot is the evidence gate for the remaining 5 skills; its target is a decision the plan must pre-determine.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The owner-directed target names a target state type but no concrete PR or document. Shared edit E-M with comprehension-2-13.
*   ***Proposed Edit:***
    *   Location: §14 decision 2 (L348); §10.4 step 3 (L291–292).
    *   Change: Replace decision 2 with: "Phase 0 pilot target: the AEP repo, with the Phase 2 PR (branch `chore/reference-vendor-elephant-goldfish-model`) as the target state; the reviewed artifact is this document. If the pilot runs before that PR exists, the target is this document at its current HEAD (as the round-1 pilot did). The Elephant records the chosen PR number in the pilot log before dispatch." Replace §10.4 step 3's "once against a real design document" with "once against the Phase 0 pilot target (§14 decision 2)".

### [Issue 51] [implementation_readiness-2-16] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Line 290 (the pinned-SHA fetch step is unexecutable as written)
*   **Discrepancy Description:** `git clone --depth 1 <url> /tmp/egm-upstream && git rev-parse HEAD` fetches the *current* upstream HEAD, not the pinned `e9e1f06a`; the moment upstream moves, the check fails with no recovery command (no `git fetch <sha>` / checkout-at-SHA step). The expected output is written as `` `e9e1f06a…` `` — an ellipsis, not a testable string. The subsequent "`diff -rq` the bundle against the upstream subset" gives no concrete command (which two paths, how exclusions are handled).
*   **Rationale:** A verification gate whose own commands cannot produce the stated expectation, with no fallback, blocks Phase 0/2 on upstream movement outside the implementer's control.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Shared edit E-C with design_critic-2-3 — apply Issue 5's edit once; it covers both findings (fetch-at-SHA, exact full SHA, concrete diff commands).
*   ***Proposed Edit:***
    *   Location: §10.4 step 2 (L290). Same fix as Issue 5, applied once.
    *   Change: Adopt Issue 5's replacement text.

### [Issue 52] [implementation_readiness-2-17] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Line 158 (D6 — the non-repo snapshot procedure is unspecified)
*   **Discrepancy Description:** "File list + mtimes for a non-repo target" — no command (`find`? `stat`?), no snapshot storage location, no diff command, and no definition of "unexpected modification" (mtime-only change vs content change?). This is the enforcement mechanism for the plan's self-declared principal risk (reviewers are not actually read-only on Muse), and its non-repo form is left to implementer invention.
*   **Rationale:** The mitigation for the top risk must be at least as specified as the risk is emphasized.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Shared edit E-F with design_critic-2-7 and zoom_out-2-8 — apply Issue 9's edit once; it covers all three findings (content-hash snapshot command, defined scope, rollback, attribution, residual risk).
*   ***Proposed Edit:***
    *   Location: D6 (L158). Same fix as Issue 9, applied once.
    *   Change: Adopt Issue 9's replacement text.

### [Issue 53] [implementation_readiness-2-18] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Line 299 (verification check (1) permits "by script or by hand" with no script)
*   **Discrepancy Description:** "Check by script or by hand against the mapping table" names no script, no command, and no expected output for resolving every `agents/...` and `resources/...` reference across 7 skills. "By hand" is an allowed method for a check whose failure mode (one dangling reference) is the exact coupling risk recorded in §6.
*   **Rationale:** The standard requires specific test cases; a verification step whose method is "whatever the implementer chooses" is not a test plan.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. A concrete shell loop can be stated exactly.
*   ***Proposed Edit:***
    *   Location: `### Verification checks` check (1) (L299).
    *   Change: Replace "check by script or by hand against the mapping table; a single dangling reference fails the check" with: "check by running, from the install location, `for f in <skills-dir>/egm-*/SKILL.md; do grep -oE '(agents|resources)/[A-Za-z0-9_./-]+' "$f"; done | sort -u | while read -r p; do test -e "<bundle>/$p" || echo "MISSING: $p"; done` (where `<skills-dir>` is `~/workspace/custom-skills` in Environment B or `<install-root>/skills` in Path 2, and `<bundle>` is `~/workspace/egm` / `<install-root>/egm` respectively) — expected output: no `MISSING` lines. 'By hand' is not an accepted method; a single dangling reference fails the check."

### [Issue 54] [implementation_readiness-2-19] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** §11 Phase 3 (Lines 301–313) + Line 349 (Phase 3 is not implementable)
*   **Discrepancy Description:** Phase 3 ("Path 1 install guide + Path 2 vendored layout validated on a fresh VM") contains no VM specification, no provisioning steps, no install commands beyond §9.2/§9.3, and no pass criteria beyond "E2E fixture passes." It is gated on §14 decision 3 (provision a fresh VM vs mark documented-but-unexecuted), which offers two options with no selection criteria, and the §11 gate makes an unexecuted Phase 3 without that ruling a failure — so the phase is simultaneously unexecutable and failing-by-default.
*   **Rationale:** A phase with no steps and an undecided existence cannot be executed; the document acknowledges it as "Provisional" but does not make it actionable.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. This finding does not re-open the settled Environment A scope question (zoom_out-2-4, settled) — it makes the phase as scoped executable. Shared edit E-S with design_critic-2-11 and comprehension-2-15.
*   ***Proposed Edit:***
    *   Location: §11 Phase 3 row (L308); §14 decision 3 (L349).
    *   Change: Add to the Phase 3 scope: "Fresh VM: a general-purpose Linux VM meeting §9.1 prerequisites (`git` ≥ 2.43.0, `python3` ≥ 3.12.3, `pytest` per §9.1, one supported harness CLI). Provisioning: install prerequisites, clone upstream at the pinned SHA, install per the §9.2/§9.3 path in the §9.4 decision matrix, run the §9.5 verification." Apply Issue 13's Phase 3 gate rewrite (pass/fail bullets; unexecuted Phase 3 passes only by an explicit §14 decision 3 ruling, never by default) and its "documented-but-unexecuted" definition. The decision-3 options themselves are the owner's ruling (no selection criteria are invented here — the ruling is required before Phase 2 merges per the Phase 2 gate, Issue 13).

### [Issue 55] [implementation_readiness-2-20] [`implementation_readiness`] - Severity: Nit
*   **Affected Scope:** Line 113 (`skill.yaml` titles for 6 of 7 skills unspecified)
*   **Discrepancy Description:** Only the example `egm-review` → `EGM Review` is given. Derivation (Title Case of the skill name) is near-mechanical, but the exact title strings for `egm-brainstorm`, `egm-draft`, `egm-resolve`, `egm-review-loop`, `egm-bootstrap`, `egm-drift-report` are never stated, and the upstream frontmatter carries no `title` field to copy.
*   **Rationale:** A required field in 7 deliverables should be enumerated, not derived.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Mechanical enumeration, clearly worth it.
*   ***Proposed Edit:***
    *   Location: D3 item 1 (L113).
    *   Change: Append: "Titles for all 7 skills: `egm-review` → `EGM Review`; `egm-brainstorm` → `EGM Brainstorm`; `egm-draft` → `EGM Draft`; `egm-resolve` → `EGM Resolve`; `egm-review-loop` → `EGM Review Loop`; `egm-bootstrap` → `EGM Bootstrap`; `egm-drift-report` → `EGM Drift Report`."

### [Issue 56] [implementation_readiness-2-21] [`implementation_readiness`] - Severity: Nit
*   **Affected Scope:** Line 151 (pilot log filename and PR-body score-line format unspecified)
*   **Discrepancy Description:** Scores go in "the pilot log file under `~/workspace/plans/`" (no filename pattern, unlike the dated report filename given in §1) and in the PR body as "one line per skill: name, score, pass/block" (no literal format).
*   **Rationale:** Two records the gates depend on have no defined form.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Two one-line definitions, clearly worth it.
*   ***Proposed Edit:***
    *   Location: D5 (L151).
    *   Change: Replace "the pilot log file under `~/workspace/plans/`" with "the pilot log file `~/workspace/plans/<date>-egm-pilot-log.md`". Replace "one line per skill: name, score, pass/block" with "one line per skill in the literal format `` `<skill-name>` — score <n>, pass|block ``".

### [Issue 57] [implementation_readiness-2-22] [`implementation_readiness`] - Severity: Nit
*   **Affected Scope:** Line 285 ("unsettled" is undefined in the convergence rule)
*   **Discrepancy Description:** "Converged = two consecutive clean rounds (no unsettled Blocker or Major)" — "unsettled" is never defined (resolved? withdrawn? dismissed? deferred to a later phase?). Two reviewers could reasonably disagree on whether a round is clean.
*   **Rationale:** The loop's stop condition needs one sentence of definition.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. One sentence defines the loop's stop condition; clearly worth it.
*   ***Proposed Edit:***
    *   Location: `### Loop bounds` (L285).
    *   Change: Append: "'Unsettled' means a Blocker or Major that is neither fixed in the target nor recorded CONTEST, ESCALATE, DECLINE, or SETTLED in the resolve report for that round."

### [Issue 58] [implementation_readiness-2-23] [`implementation_readiness`] - Severity: Nit
*   **Affected Scope:** Lines 187–212 (Path 1 — approval scope ambiguous; clone destination implicit)
*   **Discrepancy Description:** "Approval is required once" and "the ten agent definitions need `approve` before activation" never state whether the single `muse plugins approve egm` command covers the agent definitions or whether each needs separate approval. `git clone <url>` with no destination argument relies on the default directory name (`elephant-goldfish-model`), which the next command depends on but never states.
*   **Rationale:** Both are one-line clarifications that remove implementer guessing.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Resolved from upstream `docs/muse.md:32-34` (verified in the bundle): "Approval is required once… the ten agent definitions need `approve` before activation" — the single approve command is the one approval event covering the definitions; there is no per-agent step.
*   ***Proposed Edit:***
    *   Location: §9.2 (L187–212).
    *   Change: Replace "Approval is required once; skills stay active while the plugin is enabled, but the ten agent definitions need `approve` before activation." with "One approval covers the plugin and its ten agent definitions: run `muse plugins approve egm` once (upstream `docs/muse.md`: 'Approval is required once… the ten agent definitions need `approve` before activation'); there is no per-agent approval step." Replace "`git clone https://github.com/google/elephant-goldfish-model.git`" with "`git clone https://github.com/google/elephant-goldfish-model.git` (creates `./elephant-goldfish-model/`, the default directory name the next command uses)".

### [Issue 59] [implementation_readiness-2-24] [`implementation_readiness`] - Severity: Nit
*   **Affected Scope:** §11 Phase 1 gate (Lines 301–313 — Phase 1 drift-report destination unstated)
*   **Discrepancy Description:** The gate requires a dated finding or clean bill, but no filename or destination is given for the Phase 1 run. §7's pilot convention (`~/workspace/plans/<date>-<topic>-drift.md`) is a local pilot path; the Phase 1 target is the repo `skills/` tree, so the destination is genuinely ambiguous.
*   **Rationale:** A gate deliverable with no stated location cannot be verified as filed.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. One-line fix, clearly worth it.
*   ***Proposed Edit:***
    *   Location: §11 Phase 1 gate (L307).
    *   Change: Append to the Phase 1 gate: "The drift report is filed at `~/workspace/plans/<date>-skills-attribution-drift.md` (the §7 pilot convention)."

### [Issue 60] [comprehension-2-1] [`comprehension`] - Severity: Major
*   **Affected Scope:** §4, lines 35–37 (Proposed Architecture is a label chain, not an architecture)
*   **Discrepancy Description:** The section lists components joined by arrows (bundle → adapted skills → gates → dispatch → artifacts) and defers all detail to §§8–10, with no data flow, no sequencing (e.g. when gate-scan runs relative to dispatch, who invokes which gate), and no ecosystem integration.
*   **Rationale:** The assigned standard requires component layout, data flows, and ecosystem integration; a fresh reader cannot reconstruct how a skill invocation actually flows through this system from §4.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Same root cause as design_critic-2-5 and structural-2-6. Shared edit E-E — apply Issue 7's edit once; it covers all three findings.
*   ***Proposed Edit:***
    *   Location: §4 (L35–37). Same fix as Issue 7, applied once.
    *   Change: Adopt Issue 7's replacement text (data-flow sequence, artifact lifecycle, concurrency model, failure propagation).

### [Issue 61] [comprehension-2-2] [`comprehension`] - Severity: Major
*   **Affected Scope:** §1, lines 16–18; §7, lines 85–89; §9.2, lines 191–206; §10.1, lines 251–254 ("Muse" vs `muse` CLI is ambiguous)
*   **Discrepancy Description:** "Muse" is used both for the harness/CLI (Muse ≥ 1.4.14, `muse plugins install`) and for the current environment ("current Muse environment: this VM, where … there is no `muse` CLI").
*   **Rationale:** A fresh reader cannot tell whether "Muse" means the assistant, the CLI product, or this VM's environment — and therefore cannot tell which Muse sentences apply to Environment A vs B.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: §1 (after L18).
    *   Change: Add a terminology note: "Terminology: 'Muse' is the harness/assistant product; '`muse` CLI' is its command-line tool; 'current Muse environment' means Environment B (this VM, which has no `muse` CLI)." Replace §1's "current Muse environment: this VM, where skills live in `~/workspace/custom-skills/`, there is no `muse` CLI" with "current Muse environment (Environment B): this VM, where skills live in `~/workspace/custom-skills/`, there is no `muse` CLI".

### [Issue 62] [comprehension-2-3] [`comprehension`] - Severity: Major
*   **Affected Scope:** §1, line 18; §4, line 37; §10.3, lines 273, 281 (`subagent.spawn` is never defined)
*   **Discrepancy Description:** It is the sole dispatch mechanism in Environment B, but the document never says what it is (a Muse tool? a shell command? an API), what arguments it takes, or where its behaviour is documented.
*   **Rationale:** Assumed workflow prerequisite — the reader is told dispatch "runs through `subagent.spawn`" with no way to learn how to invoke it.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The term is used as the sole dispatch mechanism and defined nowhere in the document.
*   ***Proposed Edit:***
    *   Location: §10.1 (L251–254).
    *   Change: Add: "`subagent.spawn` is the Muse tool that spawns a fresh-context subagent from a brief (persona file path + prompt); it takes the brief items listed in §10.3. It has no tool-restriction parameter (see D6)."

### [Issue 63] [comprehension-2-4] [`comprehension`] - Severity: Major
*   **Affected Scope:** §10.3, lines 278, 281 (`GoldfishContext` is undefined in this document)
*   **Discrepancy Description:** It appears as a readiness-gate condition ("provided — an empty list counts as provided") and as brief item (4) ("GoldfishContext paths"), but nowhere does the document say what it contains (files? directories? URLs?), what format it takes, or what it is for. It is defined in the vendored bundle as a reading list in `egm-review/SKILL.md`, but the target document neither defines it nor links to that definition.
*   **Rationale:** A gate whose input is undefined cannot be evaluated, and "empty counts as provided" makes the gate's purpose unintelligible without the definition.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The bundle definition exists (verified: `skills/egm-review/SKILL.md:74`), so the fix is a definition plus a link to it.
*   ***Proposed Edit:***
    *   Location: §10.3 (L278, readiness gate).
    *   Change: Append to the readiness-gate sentence: "GoldfishContext is the reading list establishing system context for a review — files, directories, or URLs the reviewer must read (defined in the bundle's `skills/egm-review/SKILL.md:74`: '`GoldfishContext` (Optional): Reading list to establish the system…')."

### [Issue 64] [comprehension-2-5] [`comprehension`] - Severity: Major
*   **Affected Scope:** §10.3, lines 273, 281, 285 ("the driver" is an undefined actor)
*   **Discrepancy Description:** The driver "checks every cited line exists," "checks the named standard," and "stops and asks the owner" on cap/churn — but the Roles table (§8, lines 172–178) names only Elephant, Goldfish, and Synthesizer, and §10.3 also says the Elephant consolidates findings.
*   **Rationale:** The reader cannot tell whether driver = Elephant, a separate script, or a harness feature, so responsibility for the two verification checks is unassigned.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: `### Roles & dispatch` (L172–178).
    *   Change: Add a row: "| Driver | The Elephant acting in its driver capacity: checks every cited line exists in the target at the stated range and the named standard is the assigned one, enforces the readiness/section-approval gates, and stops and asks the owner on cap/churn. |"

### [Issue 65] [comprehension-2-6] [`comprehension`] - Severity: Major
*   **Affected Scope:** §10.3, line 281 ("the verbatim prompt" is defined circularly)
*   **Discrepancy Description:** It is "the review instruction formed from the skill's Delegation section plus the target," but the Delegation section is never quoted, located by path, or linked, and no example brief is given.
*   **Rationale:** The reader cannot construct the reviewer brief the document mandates, since the source it is "formed from" is not identified in the document.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The Delegation section's location is verifiable in the bundle (`skills/egm-review-loop/SKILL.md:34`, `skills/egm-review/SKILL.md:19`).
*   ***Proposed Edit:***
    *   Location: §10.3 (L281).
    *   Change: Replace "the review instruction formed from the skill's Delegation section plus the target" with "the review instruction formed from the Delegation section of `skills/egm-review-loop/SKILL.md:34` (bundle path `<bundle>/skills/egm-review-loop/SKILL.md`, '## Delegation') plus the target — i.e. the six brief items listed in the preceding paragraph".

### [Issue 66] [comprehension-2-7] [`comprehension`] - Severity: Major
*   **Affected Scope:** §9.3, line 225; §10.4, line 295; §11, line 313 (dangling "Issue N" references)
*   **Discrepancy Description:** "Invocation in Issue 25", "defined in Issue 49", "(see Issue 17)", "(see Issue 37)" name no repository, tracker, link, or issue title anywhere in the document.
*   **Rationale:** Load-bearing pointers — the Path 2 gate-scan fallback (§9.3) and the sync-check `~` rule (§10.4) depend on them — that a fresh reader cannot resolve.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Same root cause as structural-2-4. Shared edit E-J — apply Issue 25's edit once; it covers both findings.
*   ***Proposed Edit:***
    *   Location: §9.3 (L225); §10.4 step 4 (L295); §11 (L313). Same fix as Issue 25, applied once.
    *   Change: Adopt Issue 25's replacement text (D5 / D3 item 3 / §10.3 pointers; no bare "Issue N" references remain).

### [Issue 67] [comprehension-2-8] [`comprehension`] - Severity: Major
*   **Affected Scope:** §8 D3 item 1, line 113 vs §9.3, line 222 and §10.2, line 266 (`skill.yaml` is both "hand-written" and "generated")
*   **Discrepancy Description:** D3 says each `skill.yaml` is "hand-written (the repo norm … no script generates them)"; §9.3 calls it "generated `skill.yaml`" and §10.2's layout says "`skill.yaml` # generated from frontmatter". No generator is named.
*   **Rationale:** Direct contradiction on how the file is produced — a fresh reader cannot know whether to write it by hand or run a generator (and no generator is named).
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Same root cause as implementation_readiness-2-3. Shared edit E-K — apply Issue 38's edit once; it covers both findings.
*   ***Proposed Edit:***
    *   Location: §9.3 (L222); §10.2 (L266); D4 (L129). Same fix as Issue 38, applied once.
    *   Change: Adopt Issue 38's replacement text (standardize on hand-written everywhere).

### [Issue 68] [comprehension-2-9] [`comprehension`] - Severity: Major
*   **Affected Scope:** §9.3, line 227 (`<install-root>` mapping is self-contradictory)
*   **Discrepancy Description:** `<install-root>` defaults to `$HOME/egm`, yet the Environment B mapping sets `<install-root>` = `~/workspace`, and the example strings `$HOME/egm/agents/design_critic.md` are then said to "read `/home/hatch/workspace/egm/agents/design_critic.md`" — but `$HOME/egm` under `$HOME` = `/home/hatch` is `/home/hatch/egm`, not `/home/hatch/workspace/egm`. The generic template (`<install-root>/skills/egm-*/`) also does not literally hold in Environment B (`custom-skills/`, not `skills/`), and the stated mapping does not resolve the discrepancy.
*   **Rationale:** The path scheme cannot be paraphrased consistently; the generic template and the stated mapping disagree.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Same root cause as design_critic-2-8. Shared edit E-G — apply Issue 10's edit once; it covers both findings.
*   ***Proposed Edit:***
    *   Location: §9.3 (L225–228); §10.2 (L257–270). Same fix as Issue 10, applied once.
    *   Change: Adopt Issue 10's replacement text (generic Path 2 layout vs Environment B `custom-skills/` mapping; no generic harness skill-discovery convention is specified).

### [Issue 69] [comprehension-2-10] [`comprehension`] - Severity: Major
*   **Affected Scope:** §9.2, lines 206–212 (native installs for Cursor and OpenCode have no actionable step; Codex/ChatGPT and Antigravity App are vague)
*   **Discrepancy Description:** Cursor is listed as a supported harness (§1, line 14; §9.4, line 234) but gets no install command at all; OpenCode is only "per the `adapters/opencode/` install path in the bundle" with no command; Codex/ChatGPT desktop is "install the published EGM plugin (desktop-only listing)" with no listing name or link; Antigravity App is "run `/plugin`" with no stated context.
*   **Rationale:** Unlike the Muse/Claude/Antigravity-CLI rows, these rows cannot be executed from the document alone.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified against the bundle: `docs/harnesses.md` has no Cursor/OpenCode rows; Cursor is experimental per `docs/cursor.md:9`; OpenCode installs from `adapters/` (not vendored) per `docs/opencode.md:20`. Shared edit E-H with design_critic-2-9 — apply Issue 11's install-matrix edit once; it covers both findings.
*   ***Proposed Edit:***
    *   Location: §9.2 (L206–212); §1 (L14). Same fix as Issue 11, applied once.
    *   Change: Adopt Issue 11's replacement text (Codex CLI command, desktop listing link, Cursor experimental row, OpenCode install commands from the upstream checkout, §1 experimental annotation).

### [Issue 70] [comprehension-2-11] [`comprehension`] - Severity: Major
*   **Affected Scope:** §9.5, step 3, line 244 (the E2E fixture cannot be run from this description)
*   **Discrepancy Description:** The fixture `muse-wonder-1.0` ("line-count design") is to be run "headless via `muse exec` in a temporary workspace against the installed cache only," but no command, workspace path, cache location, or definition of "installed cache" or "line-count design" is given, and `TESTING.md` (where the fixture is "recorded") has no path — upstream repo, bundle, or elsewhere.
*   **Rationale:** Assumed workflow prerequisite for the acceptance test that gates Phases 1 and 3.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Shared edit E-I with design_critic-2-9 (part) and implementation_readiness-2-10 — apply Issue 45's edit once; it covers all three findings.
*   ***Proposed Edit:***
    *   Location: §9.5 step 3 (L243–244). Same fix as Issue 45, applied once.
    *   Change: Adopt Issue 45's replacement text (exact upstream `TESTING.md` URL, temp workspace, "installed cache" definition, pass criterion, hand-exercise recording destination).

### [Issue 71] [comprehension-2-12] [`comprehension`] - Severity: Major
*   **Affected Scope:** §10.2, line 269 (the sync procedure is cited, not described)
*   **Discrepancy Description:** "Same procedure as the 2026-11-06 skill sync" gives no file, link, or steps, and "Owner: the agent running the sync" is circular — it names no role or person.
*   **Rationale:** The canonical-direction rule (§6 "dual-install drift" mitigation) rests on a procedure the reader cannot locate or reproduce.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Shared edit E-N with implementation_readiness-2-13 — apply Issue 48's edit once; it covers both findings (inline steps + owner = the Elephant / main agent session that owns the change).
*   ***Proposed Edit:***
    *   Location: §10.2 (L269). Same fix as Issue 48, applied once.
    *   Change: Adopt Issue 48's replacement text.

### [Issue 72] [comprehension-2-13] [`comprehension`] - Severity: Major
*   **Affected Scope:** §14, decision 2, line 348 (Phase 0 pilot target is unspecified)
*   **Discrepancy Description:** "The AEP repo, with a PR as the target state (owner-directed 2026-11-06)" names no PR number, branch, or document.
*   **Rationale:** The pilot gate (§2, §11) requires a completed review of a target the reader cannot identify.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Shared edit E-M with implementation_readiness-2-15 — apply Issue 50's edit once; it covers both findings.
*   ***Proposed Edit:***
    *   Location: §14 decision 2 (L348); §10.4 step 3 (L291–292). Same fix as Issue 50, applied once.
    *   Change: Adopt Issue 50's replacement text (Phase 2 PR branch as target state; this document as the reviewed artifact; fallback to this document at current HEAD).

### [Issue 73] [comprehension-2-14] [`comprehension`] - Severity: Major
*   **Affected Scope:** §14, decision 3, lines 349–350 vs §9, line 180 (the required provisional header note is absent)
*   **Discrepancy Description:** Decision 3 says "Until ruled, §9 carries the header note 'Provisional — validation pending owner provisioning.'" — but §9 as written carries no such note.
*   **Rationale:** The document instructs the reader to rely on a marker that is not present, so the provisional status of §9 is unverifiable from the text.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: §9 has no such note.
*   ***Proposed Edit:***
    *   Location: §9 (L180, directly under the `## 9. Environment A` heading).
    *   Change: Add the line: "*Provisional — validation pending owner provisioning.*"

### [Issue 74] [comprehension-2-15] [`comprehension`] - Severity: Major
*   **Affected Scope:** §11, lines 305–308, esp. Phase 3 gate, line 308 (Phase 3 gate is near-unparseable)
*   **Discrepancy Description:** "Fails when the fixture fails or when Phase 3 is unexecuted past the owner ruling required by §14 decision 3 — an unexecuted Phase 3 without that ruling fails the gate rather than passing by default" requires the reader to untangle a double conditional across two sections to learn when an unexecuted phase passes vs fails.
*   **Rationale:** A gate condition that must be re-read several times to parse is a clarity defect in a normative table.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Shared edit E-S with design_critic-2-11 and implementation_readiness-2-19 — apply Issue 13's gate rewrite once; it covers all three findings.
*   ***Proposed Edit:***
    *   Location: §11 Phase 3 gate (L308). Same fix as Issue 13, applied once.
    *   Change: Adopt Issue 13's replacement text (pass/fail bullets; unexecuted Phase 3 passes only by an explicit ruling, never by default).

### [Issue 75] [comprehension-2-16] [`comprehension`] - Severity: Major
*   **Affected Scope:** §1, lines 22–23 and §3, line 33 (the pilot report is cited without a locatable path)
*   **Discrepancy Description:** The report `2026-11-06-egm-adoption-aep-goldfish-review.md` is given as a bare filename with no directory, and §3's "all 5 reviewers completed" never names which 5 of the 10 personas ran.
*   **Rationale:** The document's central evidence (65 findings) cannot be checked or reproduced from the citations given.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Path part shared with structural-2-12 (E-R — apply Issue 33's edit once); reviewer naming is additional.
*   ***Proposed Edit:***
    *   Location: §1 (L21–23); §3 (L33).
    *   Change: Replace the bare filename with `~/workspace/plans/2026-11-06-egm-adoption-aep-goldfish-review.md` (per Issue 33). Replace "all 5 reviewers completed" with "all 5 reviewers completed (design_critic, structural, implementation_readiness, comprehension, zoom_out)".

### [Issue 76] [comprehension-2-17] [`comprehension`] - Severity: Nit
*   **Affected Scope:** §7, line 78 ("the Astro docs site (`site/`)" — "Astro" is undefined)
*   **Discrepancy Description:** No expansion or link explains that Astro is the static-site generator the docs site is built with, or why that matters to the exclusion.
*   **Rationale:** A project-specific term used without definition; low impact since it only explains an exclusion.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. One parenthetical gloss, clearly worth it.
*   ***Proposed Edit:***
    *   Location: §7 (L78).
    *   Change: Replace "the Astro docs site (`site/`)" with "the Astro docs site (`site/`; Astro is the static-site generator the docs site is built with)".

### [Issue 77] [comprehension-2-18] [`comprehension`] - Severity: Nit
*   **Affected Scope:** §8 D7, lines 162–163 (`trusted_enabled` and `agent_definition_unavailable` are unexplained status/error strings)
*   **Discrepancy Description:** The reader is told named definitions "report `trusted_enabled` but spawning one is rejected (`agent_definition_unavailable`)" with no gloss of what either value means.
*   **Rationale:** The failure mode is inferable from context ("rejected"), but a fresh reader cannot tell whether `trusted_enabled` is an approval state, a capability flag, or something else.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. One parenthetical gloss, clearly worth it; the gloss paraphrases only what the sentence already states (a reported status vs a rejection error), so it adds no unverified claim.
*   ***Proposed Edit:***
    *   Location: D7 (L162–163).
    *   Change: Replace "report `trusted_enabled` but spawning one is rejected (`agent_definition_unavailable`)" with "report `trusted_enabled` (the status the harness reports for the named definition) but spawning one is rejected (`agent_definition_unavailable` — the error returned when spawning it is attempted)".

### [Issue 78] [comprehension-2-19] [`comprehension`] - Severity: Nit
*   **Affected Scope:** §8 D4, lines 124–125 (`reference/esf` is used as the pattern exemplar without expansion)
*   **Discrepancy Description:** The `PROVENANCE.md` fields are said to follow "the esf pattern's fields," but `esf` is never expanded or described.
*   **Rationale:** A fresh reader cannot know what `esf` is without opening the repo tree; the fields themselves are listed, so the gap is minor.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. One parenthetical gloss; `reference/esf/` is verified as an existing vendored tree (round 1). Clearly worth it.
*   ***Proposed Edit:***
    *   Location: D4 bundle bullet (L124–125).
    *   Change: Replace "with the esf pattern's fields" with "with the esf pattern's fields (`reference/esf/` is an existing vendored tree; its `PROVENANCE.md` is the pattern exemplar)".

### [Issue 79] [comprehension-2-20] [`comprehension`] - Severity: Nit
*   **Affected Scope:** §6, line 52 and §10.3, lines 283–285 ("Loop cost" has no unit and its mitigation is not a cost bound)
*   **Discrepancy Description:** The mitigation is "bounds in §10.3," but §10.3's bounds are round/reviewer caps and it explicitly states "no token budget is set until pilot data exists."
*   **Rationale:** The reader cannot tell what "cost" is measured in (tokens, time, money) or what would count as too costly.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Same root cause as design_critic-2-4 and implementation_readiness-2-14. Shared edit E-D — apply Issue 6's edit once; it covers all four findings (cost unit = reviewer spawns + tokens, recorded per phase gate; interim timeout; §14 decision 6).
*   ***Proposed Edit:***
    *   Location: §6 (L52); `### Loop bounds` (L283–285). Same fix as Issue 6, applied once.
    *   Change: Adopt Issue 6's replacement text.

### [Issue 80] [zoom_out-2-1] [`zoom_out`] - Severity: Major
*   **Affected Scope:** Lines 42, 279 (§5, §10.3 — "Extend the existing instruments" rejected in one sentence, with no comparative evidence — reinventing the wheel)
*   **Discrepancy Description:** §5 rejects extending `grilling` + `roundtable_review` + Ralph verifier as "leaves design review informal and unstandardized." But `roundtable_review` (verified in the repo) already implements parallel fresh-context reviewers, debate rounds, claim verification with VERIFIED/INACCURATE/HALLUCINATED labels, a completeness audit, and a judge's verdict — i.e. most of what §10.3 claims EGM uniquely adds ("written standard, configured reviewer panel, fresh-context reviewers"). The genuinely new delta is the five written standards files, which could be vendored as review inputs to the existing panel. No control run exists (roundtable was never run on this document as a baseline), so the 65-finding pilot does not establish marginal value over the incumbent.
*   **Rationale:** Adopting a second panel system (2,810-line bundle + 7 wrappers + 2 gates) without a feature-by-feature delta against the tool already in the catalog.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The `roundtable_review` capabilities are verified in the repo skill (parallel debate rounds, per-dispute verification subagents, final judge). The fix is a comparative delta plus an honest statement that no baseline control run exists — it does not claim a control run was performed.
*   ***Proposed Edit:***
    *   Location: §5 (L42); §10.3 overlap paragraph (L279).
    *   Change: Add a feature-by-feature delta table to §5 (and reference it from §10.3): "roundtable_review vs EGM — written standard: none vs 5 standards files; configured reviewer panel: per-run reviewers + debate + judge vs 10 named personas + synthesizer; fresh-context reviewers: both; claim verification: verification subagents + judge vs driver line-existence + standard-name checks; drift/bootstrap skills: none vs `egm-drift-report` + `egm-bootstrap`; dated report artifacts: single-session vs filed reports + resolve loop. Genuinely new delta: the five written standards, the gate-scan / vendor-integrity / skills-freshness gates, and the drift-report/bootstrap skills." Append: "No roundtable baseline control run was performed on this document, so the 65-finding pilot does not establish marginal value over the incumbent; the marginal-value judgment is the owner's §14 pilot-value ruling (decision 5)."

### [Issue 81] [zoom_out-2-2] [`zoom_out`] - Severity: Major
*   **Affected Scope:** Lines 22, 33 (§1, §3 — root-problem evidence is circular and n=1)
*   **Discrepancy Description:** Both the Purpose and the Problem Statement cite the same single data point: the pilot round-1 review of *this document itself*, run with the instrument being justified. A review of its own adoption doc by its own reviewers cannot establish that design review is generally missing or that EGM is the right fix — it is self-referential bootstrapping, not independent evidence. No design document outside this adoption pair has been reviewed.
*   **Rationale:** The root-problem claim rests on one self-review; the justification and the thing justified are the same event.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Shared edit E-Q with design_critic-2-14 and zoom_out-2-3 — apply Issue 16's edit once; it covers all three findings (precautionary statement, verified corpus baseline, pilot log as the demand baseline, pilot as evidence the instrument works rather than evidence of problem scale).
*   ***Proposed Edit:***
    *   Location: §3 (L31–34). Same fix as Issue 16, applied once.
    *   Change: Adopt Issue 16's replacement text.

### [Issue 82] [zoom_out-2-3] [`zoom_out`] - Severity: Major
*   **Affected Scope:** Line 29 (§2 — adoption bar is one use in 30 days; demand is never quantified)
*   **Discrepancy Description:** The success criterion is "at least one design document reviewed via `egm-review-loop` within 30 days of merge." Nothing in the document states how many design docs per month AEP (as opposed to NeuroStrata, whose real targets live in the companion doc) actually produces, or what review volume justifies a 7-skill adoption plus a vendored bundle plus two CI gates.
*   **Rationale:** YAGNI — a permanent catalog addition with ongoing sync/rename risk is being justified by a single future use.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Shared edit E-Q with design_critic-2-14 and zoom_out-2-2 — apply Issue 16's edit once for the baseline, plus the adoption-goal amendment in Issue 12 (the "0 not run" qualifier). The one-use bar is kept as a pilot floor, not the value case; the value case is the §14 pilot-value ruling.
*   ***Proposed Edit:***
    *   Location: §3 (L31–34); §2 (L29). Same fixes as Issues 16 and 12, applied once.
    *   Change: Adopt Issue 16's baseline text and Issue 12's amended adoption goal ("at least one design document reviewed via `egm-review-loop` within 30 days of merge, with all reviewers run (0 not run)").

### [Issue 83] [zoom_out-2-4] [`zoom_out`] - Severity: Major
*   **Affected Scope:** §9, line 308 (§11 Phase 3), line 349 (§14 decision 3 — Environment A / general-VM scope is speculative and should not be in this adoption)
*   **Discrepancy Description:** §9 specifies install paths for six harnesses on a fresh VM that does not exist, with no evidenced request for a general-VM install; Phase 3 is unexecuted pending an owner provisioning ruling, and §14.3 itself proposes moving §9 to an appendix if unruled. One document covering two deployment targets × two install paths is what creates the dual-install drift risk §6 then has to mitigate.
*   **Rationale:** YAGNI — cut §9/Phase 3 to a follow-up document gated on local pilot evidence; the local adoption does not need a second deployment target to be decided now.
*   ***AI Suggestion:*** SETTLED
*   ***Justification:*** Settled — same scope and issue as round-1 `zoom_out-1-1` (ESCALATE — Environment A scope is the owner's stated instruction, awaiting the owner's ruling). Per the loop's settled rule, a settled finding is not re-opened. No fix proposed; recorded here only.
*   ***Proposed Edit:***
    *   Location: None.
    *   Change: None. Matches round-1 disposition: ESCALATE (zoom_out-1-1) — needs the user's knowledge, listed first in the round-1 handoff.

### [Issue 84] [zoom_out-2-5] [`zoom_out`] - Severity: Major
*   **Affected Scope:** Lines 45, 279, 317 (§5, §10.3, §11 — all 7 skills vendored in Phase 2 despite the stated gating and deferral)
*   **Discrepancy Description:** §5 says the remaining 5 skills are "gated on pilot evidence" and `egm-bootstrap`/`egm-drift-report` are "deferred to Phase 1," yet the Phase 2 file-change list installs all 7 wrappers and the whole bundle. The gate as written is "pilot completes," not "pilot proves value," so the gating is timing, not scope. §11's own rationale admits drift-report and bootstrap "need a reviewed design corpus to work against" that does not yet exist — and §10.3 then invents targets for them (README attribution table vs. `skills/` tree; `reference/` READMEs) to justify their inclusion.
*   **Rationale:** Vendoring skills with no corpus and no real named target is speculative scope; pilot the 2 review skills and gate each of the other 5 on a real target.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The gate as written is timing, not scope. Shared edit E-P with design_critic-2-10 — apply Issue 12's edit once (defined pilot-evidence criterion + §14 decision 5 pilot-value ruling + rollback), plus the Phase 2 scope amendment below.
*   ***Proposed Edit:***
    *   Location: §5 (L45); §11 Phase 2 scope (L310). Same fix as Issue 12, applied once, plus:
    *   Change: Amend the §11 Phase 2 scope to: "`reference/elephant-goldfish-model/` + 7 `skills/egm-*` wrappers + scope/manifest/attribution updates — only after the §14 decision 5 pilot-value ruling; without it, Phase 2 installs the 2 review skills only." The §10.3 named targets for `egm-drift-report` and `egm-bootstrap` remain Phase 1 targets; they do not by themselves justify Phase 2 inclusion.

### [Issue 85] [zoom_out-2-6] [`zoom_out`] - Severity: Major
*   **Affected Scope:** Lines 107, 121 (D2) vs. lines 290, 317 (§10.4, §11 — "Bundle intact / verbatim / moves as one unit" contradicts the selective 39-file vendor)
*   **Discrepancy Description:** D2 claims the bundle moves as one intact verbatim unit, but the Phase 2 list vendors only 39 files. The local bundle at `~/workspace/egm/` contains 90 files — the 39-file list silently drops `TEST.md`, `agents/openai.yaml`, `assets/icon.svg`, `references/` and `test_scenarios.yaml` (per skill), `docs/designs/` (23 files), `docs/assets/`, and `docs/verification/`, with no exclusion rule stated for any of them. §10.4 step 2's `diff -rq` over whole `skills/`/`docs/` directories expecting zero differences would fail against upstream unless that stripping is defined.
*   **Rationale:** The core D2 scope claim ("intact") and the actual file list disagree by 51 files; the vendor subset is undefined.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid in its core claim (39 vs 90 files; the vendor subset is undefined). One sub-count is wrong: `docs/designs/` holds 18 files, not 23 (verified: 18 files under `docs/designs/`; 19 counting its `README.md`). The error does not change the finding — the fix uses the verified counts. Shared edit E-B — apply Issue 2's edit once; it covers this finding, Issue 2, and design_critic-2-2.
*   ***Proposed Edit:***
    *   Location: §11 Phase 2 file-change list (L317); §7 (L78–80). Same fix as Issue 2, applied once.
    *   Change: Adopt Issue 2's replacement text (90-file inventory with verified counts; per-skill test files ARE vendored).

### [Issue 86] [zoom_out-2-7] [`zoom_out`] - Severity: Major
*   **Affected Scope:** Lines 113, 121, 129, 131, 137 (D3–D4) + §10.2 (wrapper→bundle coupling is a new architectural pattern that creates the coverage hole it then patches bespoke)
*   **Discrepancy Description:** Verified — no existing skill loads from a `reference/<tree>/` path, so D4 introduces a repo-first coupling (rename either tree silently breaks all 7 skills), split across two gates (vendor-integrity for the bundle, skills-freshness for wrappers). The hand-written `skill.yaml` files are covered by *neither* gate (stated twice, lines 113 and 129), so a third bespoke mechanism — a YAML-parse + name-match check — is invented to cover a gap the wrapper design itself created. §10.2 adds split canonicality on top: AEP canonical for wrappers, local bundle canonical for personas/standards, glued by a `sed` normalize-then-diff sync check (§10.4 step 4).
*   **Rationale:** The design manufactures coupling, a coverage hole, and bespoke glue; simpler alternatives (adapted skills inside the bundle tree, or local-only adoption until AEP need is proven) are not evaluated — the "accepted explicitly" in D4 is doing the work of an architecture decision without an owner ruling attached.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid in its main claim: the two simpler alternatives are not evaluated in §5. On the owner-ruling sub-point, no new decision is needed: the whole document is draft for owner review and the Phase 2 gate already requires owner review (L311) — that review is the ruling on D4's explicit acceptance. The fix therefore evaluates the missing alternatives and leaves the ruling where it already sits.
*   ***Proposed Edit:***
    *   Location: §5 (L39–45).
    *   Change: Add two evaluated alternatives: "- Adapted skills inside the bundle tree instead of wrappers under `skills/` — rejected: the bundle must stay pristine/verbatim so the vendor-integrity hash and the §10.4 zero-diff check hold; any adaptation inside the tree breaks both. - Local-only adoption until AEP need is proven — adopted in part: Phases 0–1 are local-only; the AEP PR (Phase 2) proceeds only on the §14 decision 5 pilot-value ruling (see Issue 12)."

### [Issue 87] [zoom_out-2-8] [`zoom_out`] - Severity: Major
*   **Affected Scope:** Line 158 (D6 — read-only "enforcement" is detection after the write, not prevention — a workaround elevated to the principal safety mechanism)
*   **Discrepancy Description:** D6 admits there is no tool-restriction mechanism on Muse and the mitigation is a post-run snapshot diff: a reviewer that writes is caught only after the modification exists, and the round (not the filesystem change) "fails." The document calls this "fail-closed," but it is fail-closed for the review round, not for the tree/daemon/database — the damage is done before detection, and every run pays per-reviewer snapshot overhead for it.
*   **Rationale:** The principal risk in both environments rests on a detective control mislabeled as enforcement; the residual risk (write-before-detection) should be stated, not papered over.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The "fail-closed" label is doing work the control cannot do. Shared edit E-F with design_critic-2-7 and implementation_readiness-2-17 — apply Issue 9's edit once; it covers all three findings (detection relabel, residual risk stated, rollback procedure).
*   ***Proposed Edit:***
    *   Location: D6 (L153–158); §12 (L319–332). Same fix as Issue 9, applied once.
    *   Change: Adopt Issue 9's replacement text.

### [Issue 88] [zoom_out-2-9] [`zoom_out`] - Severity: Major
*   **Affected Scope:** §10.3 Loop bounds, line 285 (unbounded loop cost in the very phase meant to measure cost)
*   **Discrepancy Description:** Up to 5 rounds × 5 reviewers = 25 fresh-context reviewer spawns per run, with explicitly "no fixed per-reviewer timeout" and "no token budget … until pilot data exists." The pilot — the run that is supposed to generate the cost evidence — itself runs without a cost bound.
*   **Rationale:** Cost control deferred until after the spend it is meant to control; set a pilot cap (rounds/reviewers/timeout) now, from the round-1 pilot already run, instead of after.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Shared edit E-D with design_critic-2-4, implementation_readiness-2-14, and comprehension-2-20 — apply Issue 6's edit once; it covers all four findings. Note: no pilot log with per-reviewer elapsed times exists yet (verified — no such file under `~/workspace/plans/`), so the interim 30-minute pilot timeout is set now as a stated bound and the pilot log records actual elapsed times for the Phase 1 decision (§14 decision 6), rather than pretending the value came from pilot data.
*   ***Proposed Edit:***
    *   Location: `### Loop bounds` (L283–285); §6 (L52); §14 (new decision 6). Same fix as Issue 6, applied once.
    *   Change: Adopt Issue 6's replacement text.

### [Issue 89] [zoom_out-2-10] [`zoom_out`] - Severity: Major
*   **Affected Scope:** Altitude drops (weeds) throughout: a strategy document carrying runbook detail, including duplicated normative commands
*   **Discrepancy Description:** Examples — per-skill line counts (§7); per-skill reference occurrence counts (D3); exact `sha256sum` generation command stated in D4 and again in the "AEP machinery" paragraph; exact `git clone --depth 1 … && git rev-parse HEAD` and `sed -i 's|…|…|g'` commands (§10.4 steps 2, 4); the `egm-draft` gate question quoted verbatim twice (§10.3); the 39-file change list (§11, line 317). Duplicated normative detail can drift — the exact failure mode this adoption exists to detect.
*   **Rationale:** Implementation/runbook content belongs in the PR body and verification scripts, not in the design strategy; the document should state interfaces, decisions, and gates, and point at the runbook.
*   ***AI Suggestion:*** SETTLED
*   ***Justification:*** Settled — same scope and issue as round-1 `zoom_out-1-8` (CONTEST — executable detail belongs in the design per its stated purpose; commands stay). Per the loop's settled rule, a settled finding is not re-opened. No fix proposed; recorded here only.
*   ***Proposed Edit:***
    *   Location: None.
    *   Change: None. Matches round-1 disposition: CONTEST (zoom_out-1-8).

### [Issue 90] [zoom_out-2-11] [`zoom_out`] - Severity: Nit
*   **Affected Scope:** Duplicated definitional text
*   **Discrepancy Description:** The 65-finding evidence appears in both §1 (line 22) and §3 (line 33); "'Verify outputs' means the two checks in D6 … nothing else" is stated twice in the same paragraph (line 158); the gate question is quoted verbatim twice in §10.3.
*   **Rationale:** Trim to single sources of truth.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The same-paragraph duplication is a genuine redundancy; the §1/§3 and gate-question duplications are trimmable to cross-references without losing the verbatim quote where it is normative.
*   ***Proposed Edit:***
    *   Location: D6 (L158); §3 (L33); §10.3 (L281).
    *   Change: In D6, delete the second occurrence of "'Verify outputs' means the two checks in D6 (the snapshot diff and the line-existence check), nothing else." (keep the first). In §3, replace the restated evidence sentence with "Demonstrated case: see §1." In §10.3, keep the first verbatim gate-question quote (section-approval gate definition) and replace the second with "(gate question as quoted above in the section-approval gate definition)".

## End of report

Counts check: 90 findings = 84 PROPOSE FIX + 3 DECLINE + 3 SETTLED + 0 CONTEST + 0 new ESCALATE. The one live ESCALATE remains the settled round-1 item `zoom_out-1-1` (Environment A scope), carried by settled `zoom_out-2-4` and still awaiting the owner's ruling.
