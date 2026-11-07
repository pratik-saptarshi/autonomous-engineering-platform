Status: resolved
# Goldfish Annotated Review Report

**Target:** `/home/hatch/workspace/plans/2026-11-06-egm-adoption-aep.md` (full file, lines 1–337)
**Source findings:** `/home/hatch/workspace/plans/2026-11-06-egm-adoption-aep-goldfish-review.md` (Round 1: 3 Blockers, 35 Majors, 27 Nits; all 5 reviewers completed)
**Status:** unresolved — awaiting the interactive gate (Step 4). No fixes applied.
**Note on filename:** the skill prescribes `goldfish_review_report.md`; this dated name is used instead so the pilot's artifacts stay distinct.
**Note on the review report's dedup map:** its root-cause list misattributes one item — root cause 8 ("Gate contradictions") lists `design_critic-1-8`, but `design_critic-1-8` is the Appendix "8 trees" factual error, which belongs to root cause 9 (with `comprehension-1-21`). Root cause 8's real member is `zoom_out-1-6` only. This does not change any categorization below.

## Category counts

- **CONTEST:** 1 (zoom_out-1-8)
- **ESCALATE:** 1 (zoom_out-1-1) — needs the user's knowledge; listed first in the handoff.
- **PROPOSE FIX:** 60 (3 Blockers, 34 Majors, 23 Nits)
- **DECLINE:** 3 (all Nits)

## Prioritized Findings & AI Suggestions

### [Issue 1] [comprehension-1-1] [`comprehension`] - Severity: Blocker
*   **Affected Scope:** Lines 79, 84–92, 159–178 (D3, §4.2 Path 1)
*   **Discrepancy Description:** D3 says the three adaptations are "applied identically in both environments" and requires every adapted `SKILL.md` to gain the Muse routing line and bundle-relative path resolution. But §4.2 Path 1 is a verbatim upstream plugin install with no adaptation step, no `skill.yaml` generation, and no place where an adapted copy would live. A fresh reader cannot tell whether Path 1 skips D3 entirely, applies D3 to the cloned tree before install, or applies it somewhere else. The preferred install path for Environment A cannot be executed as written; the central "one adoption, two installations" claim fails for it.
*   **Rationale:** As stated in the discrepancy: the three readings of D3 vs. Path 1 contradict each other, and no reading is executable as written.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified against the target file: D3's line 79 ("applied identically in both environments") and §4.2's verbatim install commands are irreconcilable as written.
*   ***Proposed Edit:***
    *   Location: D3 intro (line 79) and §4.2 (lines 159–178); §1 lines 20–21.
    *   Change: Replace D3's opening line with: "Three mechanical adaptations, applied to every vendored-skills install (Path 2 and Environment B). Path 1 installs the upstream plugin verbatim and carries no adapted copies." Add to §4.2 after the install commands: "Path 1 performs no adaptation step: no `skill.yaml` is generated (the plugin's frontmatter is sufficient), no routing line is added — name `docs/muse.md` in the session prompt instead, per upstream practice until issue #252 closes — and the bundle is installed verbatim. The D3 adaptations exist only where skills are vendored." Amend §1 lines 20–21 to: "One vendored content set, two installation mechanisms; Path 1 installs upstream verbatim and carries no adapted copies."

### [Issue 2] [comprehension-1-2] [`comprehension`] - Severity: Blocker
*   **Affected Scope:** Lines 25–28, 137–149, 244–251 (§2 model, D7, §5.3 dispatch)
*   **Discrepancy Description:** The model is defined abstractly ("Elephant (one agent holds context and drafts the spec)"), but the document never maps Elephant / synthesizer / parent to a concrete actor in either environment. D7 introduces "dispatch reviewers directly from the parent (direct dispatch) instead of through the synthesizer" without ever defining the synthesizer; §5.3 says "Wait for actual completion before synthesizing" without saying who synthesizes, in what form, or where the synthesis goes. `subagent.spawn` is named as the dispatch mechanism but no invocation form, brief template, or argument list is given. A fresh reader can paraphrase the idea of fresh-eyes review but cannot run one review loop from this document alone.
*   **Rationale:** As stated in the discrepancy: roles are named but never bound to actors, and dispatch has no executable form.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the target file never binds Elephant, synthesizer, or parent to a concrete actor, and §5.3's "synthesizing" has no subject.
*   ***Proposed Edit:***
    *   Location: New subsection "### Roles & dispatch" inserted after D7 (line 150); §5.3 (lines 244–252).
    *   Change: Add the mapping table: Elephant = the session that owns the design doc and runs the loop (Environment B: the main agent; Environment A Path 1: the harness session that installed the plugin). Goldfish = one fresh-context subagent per reviewer (Environment B: `subagent.spawn` with a read-only brief; Path 1: named `egm/egm-*` agent where spawn works, else the general-purpose fallback). Synthesizer = the `agents/synthesizer.md` role; in Environment B it is replaced by direct dispatch (no nesting below depth 1) with the Elephant consolidating findings; in Path 1 it is used where the harness nests subagents. Add the brief template to §5.3: each reviewer brief contains (1) persona file absolute path, (2) target file absolute path + line range, (3) assigned standard absolute path, (4) GoldfishContext paths, (5) the read-only instruction, (6) the required report shape (severity, line numbers, discrepancy, rationale). Add the synthesis rule: the Elephant consolidates into a flat FindingsList with stable ids (`<reviewer>-<round>-<n>`) and writes the report artifact before any resolution.

### [Issue 3] [implementation_readiness-1-1] [`implementation_readiness`] - Severity: Blocker
*   **Affected Scope:** §3 D4 (lines 94–113), §6 Phase 2 (line 278)
*   **Discrepancy Description:** The standard requires an explicit list of exact repository-relative file paths to be created, modified, or deleted. The plan gives only directory patterns (`reference/elephant-goldfish-model/`, `skills/egm-*/`, "scope/manifest/attribution updates"). The bundle's exact file inventory at the pinned SHA is never enumerated, the seven wrapper dir names are only inferable, and at least one required modified file is omitted entirely — `.github/workflows/ci.yml`. An implementer cannot produce a bounded change or an allowlist from this.
*   **Rationale:** As stated in the discrepancy: directory patterns are not a file-change list, and a required file is missing from it.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the target file lists no exact paths for Phase 2 and never mentions `.github/workflows/ci.yml` as modified.
*   ***Proposed Edit:***
    *   Location: §6 Phase 2 row (line 278); add "Phase 2 file-change list" as a subsection under §6.
    *   Change: Add the exact list. Created: `reference/elephant-goldfish-model/` bundle, 39 files at the pinned SHA — `skills/` (7 × `SKILL.md`), `agents/` (10 persona files), `resources/` (`execution_instructions.md`, `README.md`, 5 standards), `docs/` (13 files), `LICENSE`, `plugin.json`; `.github/vendor-elephant-goldfish-model.sha256`; `reference/elephant-goldfish-model/PROVENANCE.md`; `skills/egm-brainstorm/`, `skills/egm-draft/`, `skills/egm-review/`, `skills/egm-resolve/`, `skills/egm-review-loop/`, `skills/egm-bootstrap/`, `skills/egm-drift-report/` (each `SKILL.md` + `skill.yaml`, 14 files). Modified: `.github/skills-sync-scope.txt` (7 lines under `[skills]`), `.github/skills-manifest.sha256` (regenerated via `check_skills_manifest.py --write`), `skills/README.md` (7 attribution rows), `.github/workflows/ci.yml` (tenth `vendor-integrity` `run:` block). Deleted: none.

### [Issue 4] [design_critic-1-1] [`design_critic`] - Severity: Major
*   **Affected Scope:** Lines 94–106 (D4), 278; AEP `.github/workflows/ci.yml` lines 73–132
*   **Discrepancy Description:** D4 states the bundle is "Covered by the `vendor-integrity` CI job". Verified: the job is nine hand-written, copy-pasted `run:` blocks, one per `reference/` tree, each doing `sha256sum -c` plus an unlisted-files check. Adding `reference/elephant-goldfish-model/` requires a tenth block in `ci.yml`, and Phase 2's scope list does not mention `ci.yml` at all. If the edit is missed, the new bundle ships with zero integrity verification while the document claims coverage — silent non-coverage.
*   **Rationale:** As stated in the discrepancy: coverage is claimed for a job that cannot cover a tree it has no block for.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified in the repo: 9 hardcoded per-tree `run:` blocks (esf, neurostrata, neurostrata-ops, harness2, security-audit-skill, ub-mode, grim-prompter, docs-mcp-server, humanizer); no generic loop.
*   ***Proposed Edit:***
    *   Location: D4 bundle bullet (lines 96–101); §6 Phase 2 file list (see Issue 3).
    *   Change: Replace "Covered by the `vendor-integrity` CI job." with: "Covered by the `vendor-integrity` CI job once the tenth per-tree `run:` block lands in `.github/workflows/ci.yml` in the same PR (same `sha256sum -c` + unlisted-files + symlink pattern as the existing nine blocks); until that block lands the bundle has zero integrity verification."

### [Issue 5] [design_critic-1-2] [`design_critic`] - Severity: Major
*   **Affected Scope:** Lines 100–113 (D4), 259–270 (§5.4)
*   **Discrepancy Description:** (a) The scope file's own header states the gate proves only that the repo `skills/` tree equals the manifest generated from the repo tree after the last sync from live — "never a freshness claim against the live tree (CI cannot see live)". It cannot detect wrapper↔upstream-bundle drift or wrapper↔local-`custom-skills` drift. (b) `[exclude-paths]` contains a bare `skill.yaml`, so D3's generated `skill.yaml` — the file that makes each skill loadable — is entirely excluded from the manifest. D4's "Covered by the `skills-freshness` gate" is true only for the adapted `SKILL.md`.
*   **Rationale:** As stated in the discrepancy: both halves of the coverage claim overstate what the gate proves and covers.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the scope-file header states the bounded claim verbatim, and `[exclude-paths]` line 96 is the bare name `skill.yaml`.
*   ***Proposed Edit:***
    *   Location: D4 wrappers bullet (lines 100–107); §5.4 steps 2–4.
    *   Change: Replace "Covered by the `skills-freshness` gate (manifest + `.github/skills-sync-scope.txt` entries for the seven `egm-*` dirs) and the attribution table in `skills/README.md`." with: "Covered by the `skills-freshness` gate for the adapted `SKILL.md` files only: the gate proves the repo `skills/` tree equals the manifest generated from the repo tree after the last sync from live — it detects no drift against the upstream bundle and no drift against local `custom-skills/`. The generated `skill.yaml` files are excluded from the manifest by the bare `skill.yaml` entry in `[exclude-paths]` and are therefore covered by neither gate; they are validated instead by a YAML-parse + name-match check in Phase 2 (see §5.4). Attribution rows live in `skills/README.md`."

### [Issue 6] [design_critic-1-3] [`design_critic`] - Severity: Major
*   **Affected Scope:** Lines 20–21 (§1), 239–240 (§5.2), 269 (§5.4 step 4)
*   **Discrepancy Description:** §5.2 calls `~/workspace/egm/` "the single source of truth for personas and standards", but the local bundle lives outside any repository (no version control, backup, or sync script named), while the AEP wrappers live in git. No direction of sync, owner, cadence, or procedure for propagating a fix in either direction is named. §5.4 step 4 ("byte-identical (modulo the path prefix…)") is not an executable check, and no normalisation procedure is defined. Dual-write drift is designed in, not guarded against.
*   **Rationale:** As stated in the discrepancy: two copies, no canonical direction, no executable sync check.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the target file names no sync direction, owner, cadence, or procedure, and §5.4 step 4 gives no command.
*   ***Proposed Edit:***
    *   Location: §5.2 (lines 229–240); §5.4 step 4 (lines 268–270).
    *   Change: Replace "The bundle stays pristine so re-sync is a clean replace" and the "single source of truth" sentence with: "Canonical direction: the AEP repo is canonical for the wrappers (`skills/egm-*/`); the local bundle at `~/workspace/egm/` is canonical for the installed personas and standards. Sync runs in the existing live→repo direction: any change to a local adapted skill is copied into the repo wrappers by the next sync (same procedure as the 2026-11-06 skill sync), and any re-vendor replaces the local bundle wholesale from the repo tree. Cadence: on every upstream re-vendor and on any local adaptation change. Owner: the agent running the sync; the sync is verified by the normalize-then-diff check in §5.4 step 4." Replace §5.4 step 4 with the procedure from Issue 22 (normalize-then-diff with an explicit `sed` prefix replacement, then `diff -r`, plus the path-resolution assertion).

### [Issue 7] [design_critic-1-4] [`design_critic`] - Severity: Major
*   **Affected Scope:** Lines 77–92 (D3); verified against `~/workspace/egm/skills/egm-review/SKILL.md`, `agents/zoom_out.md:44`, `agents/synthesizer.md:37–38`, `resources/README.md:16`
*   **Discrepancy Description:** (a) D3 gives no rewriting rule: which literal strings map to what in each environment, by what tool, with what verification. The only verification, `diff -rq` bundle vs. upstream (§5.4 step 2), checks the pristine bundle — not the adapted copies' links. (b) Bundle-relative references also live inside the pristine personas and standards (`agents/zoom_out.md:44` references `resources/document_standards/zoom-out-standard.md`; `agents/synthesizer.md:37–38` defines the resolution directories). If the harness resolves relative paths from the invoking skill's directory, those references break, and D3's "pristine bundle is never edited" forbids fixing them in place. (c) The Muse routing line (lines 84–86) is quoted without a path, though `docs/muse.md` lives at different absolute locations per environment.
*   **Rationale:** As stated in the discrepancy: no rewrite rule, persona-internal references unaddressed, routing line pathless.
*   ***AI Suggestion:*** PROPOSE FIX
*   **Justification:** Valid. Verified: `agents/zoom_out.md:44` and `agents/synthesizer.md:38` both carry bundle-relative `resources/document_standards/` references (the `resources/README.md:16` citation did not match on re-check, but the two confirmed references establish the point).
*   ***Proposed Edit:***
    *   Location: D3 item 3 (lines 87–92).
    *   Change: Replace item 3 with the rewrite mapping table: `agents/` → `<bundle>/agents/`; `resources/document_standards/` → `<bundle>/resources/document_standards/`; `resources/execution_instructions.md` → `<bundle>/resources/execution_instructions.md`; `../../docs/codex.md` → `<bundle>/docs/codex.md`; `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` → `<bundle>/docs/claude.md`; `docs/harnesses.md` → `<bundle>/docs/harnesses.md`; `docs/muse.md` → `<bundle>/docs/muse.md`; where `<bundle>` is `/home/hatch/workspace/egm` in Environment B, `<install-root>/egm` in Environment A Path 2, and `../../reference/elephant-goldfish-model` in the AEP wrappers. Add: "Record per-skill occurrence counts in the Phase 2 PR body (pilot counts for the two installed skills: `egm-review` 3× `agents/`, 1× `resources/document_standards/`, 1× each codex/claude/harnesses; `egm-review-loop` 4× `agents/`, 5× `resources/document_standards/`, 1× each codex/claude/harnesses). Persona-internal references (`agents/zoom_out.md:44`, `agents/synthesizer.md:38`) resolve against the bundle root; the pilot verifies one such reference resolves in each environment (added to §4.5 and §5.4 verification). The Muse routing line carries its path: `In Muse, read <bundle>/docs/muse.md first.`"

### [Issue 8] [design_critic-1-5] [`design_critic`] - Severity: Major
*   **Affected Scope:** Lines 124–135 (D6), 292–296 (§7)
*   **Discrepancy Description:** The mitigation is "brief reviewers read-only… do not hand reviewers write tools", but the document never establishes that `subagent.spawn` in Environment B (or any Environment A harness) can actually withhold write tools — D6 itself concedes Muse has no tool allowlist. There is no fail-closed control: no sandbox, no pre/post diff or `git status` check, and "verify outputs" is undefined. A reviewer that edits the working tree or touches memory services is detectable only after the fact, if at all.
*   **Rationale:** As stated in the discrepancy: a procedural mitigation over a mechanism the document concedes cannot enforce it, with no detection control.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the target file defines no detection or enforcement control beyond the brief wording.
*   ***Proposed Edit:***
    *   Location: D6 (lines 124–135); §7 second bullet (lines 292–296).
    *   Change: Append to D6: "Enforcement is post-hoc and fail-closed: before dispatch, snapshot the working tree (`git status --porcelain` in a repo target; file list + mtimes for a non-repo target). After each reviewer completes, re-run the snapshot and diff it; any unexpected modification fails that reviewer's round, the finding is discarded, and the reviewer is not re-dispatched. Each reviewer's report must cite every finding's target line numbers; the driver checks each cited line exists in the target at the stated range — a report failing the check is incomplete and re-run once, then recorded not run. 'Verify outputs' means these two checks, nothing else." Replace "Never give a reviewer a write tool it did not ask for by design." in §7 with the same snapshot-diff procedure by reference.

### [Issue 9] [design_critic-1-6] [`design_critic`] - Severity: Major
*   **Affected Scope:** Lines 242–257 (§5.3), 272–284 (§6)
*   **Discrepancy Description:** The adoption sets no iteration cap, no per-run subagent-count or token budget, no timeout values, and no escalation path on non-convergence. The upstream skill mentions cap/converge, but the plan never operationalises the cap value or who sets it, and no phase gate measures cost. The most expensive behaviour — repeated full-context re-reads by fresh reviewers — is unbudgeted.
*   **Rationale:** As stated in the discrepancy: the loop's most expensive behaviour runs without bounds or cost measurement.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the target file states no caps, budgets, timeouts, or escalation path.
*   ***Proposed Edit:***
    *   Location: New subsection "### Loop bounds" under §5.3 (after line 257); §6 phase gates.
    *   Change: Add: "Bounds per review-loop run: at most 5 rounds (the upstream cap); at most 5 reviewers per round; converged = two consecutive clean rounds (no unsettled Blocker or Major); on cap or churn the driver stops and asks the owner one question (accept and proceed / continue past the cap / return to drafting). Timeout: no fixed per-reviewer timeout is set in this document — the pilot log records per-reviewer elapsed time, and the timeout for Phase 1 is set from that evidence by the owner. Cost: each phase gate records reviewer count and rounds run; no token budget is set until pilot data exists."

### [Issue 10] [design_critic-1-7] [`design_critic`] - Severity: Major
*   **Affected Scope:** Lines 5–21 (§1), 108–113 (D4), 272–284 (§6), 302–310 (§8)
*   **Discrepancy Description:** (a) No Goals section and no measurable success criteria anywhere; phase gates are binary checklists ("gate-scan pass", "CI green", "drift report produces a dated, accurate finding or a clean bill" — "accurate" undefined, no judge named). (b) Only one alternative is evaluated (D4's shared `skills/egm-agents/` + `skills/egm-resources/` dirs). Never evaluated: do-nothing / extend `grilling` + `roundtable_review` + the Ralph verifier; git submodule vs. vendoring; Path 1 plugin install for AEP instead of vendoring; adopting a subset of skills vs. all seven.
*   **Rationale:** As stated in the discrepancy: success is unmeasurable and the alternative set is incomplete.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the target file has no Goals section and no measurable criteria; the four named alternatives are never evaluated.
*   ***Proposed Edit:***
    *   Location: Shared restructure — new "Goals" and "Alternatives Considered" sections (see Issues 12–15); §6 phase gates.
    *   Change: Add the Goals section with measurable criteria: pilot — all reviewers run (0 not run), report filed, findings categorized; local — 7/7 gate-scans pass with scores recorded; AEP PR — CI green including vendor-integrity + skills-freshness, merged with conversation resolution; adoption — at least one design document reviewed via `egm-review-loop` within 30 days of merge. Add the Alternatives Considered section evaluating all four: do-nothing / extend existing tools (rejected: leaves design review informal and unstandardized; §1 purpose + §5.3 overlap discussion); git submodule vs. vendoring (rejected: no submodule precedent in the repo; vendoring matches the existing `reference/` pattern); Path 1 plugin install for AEP (rejected: AEP is a version-controlled skill catalog, not a running harness — a plugin install has no artifact to version); subset vs. all seven (adopted in part: 2 skills in the pilot, remaining 5 gated on pilot evidence; `egm-bootstrap` and `egm-drift-report` deferred to Phase 1 with named targets — see Issue 31).

### [Issue 11] [structural-1-1] [`structural`] - Severity: Major
*   **Affected Scope:** Lines 1–337 (whole document)
*   **Discrepancy Description:** No "Alternatives Considered" heading anywhere in lines 1–337; nearest content is §3 D4 lines 108–114, §4.2 vs §4.3 (lines 159, 180), §4.4 decision matrix (lines 194–201), §9 item 4 (lines 320–323). The standard's Alternatives Rule makes evaluation of alternatives mandatory. The document evaluates alternatives only in fragments — a fresh reader cannot locate a single consolidated evaluation, and rejection rationales are not gathered in one place.
*   **Rationale:** As stated in the discrepancy: alternatives exist only in fragments, never in one consolidated evaluation.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: no "Alternatives Considered" heading exists; the content is fragmented as described.
*   ***Proposed Edit:***
    *   Location: Shared restructure (see Issue 15's edit for the full renumbering map). New section "## 5. Alternatives Considered" after "Proposed Architecture".
    *   Change: Add the section consolidating: D4's shared-dirs alternative (rejected: pollutes the skill catalog with non-skill directories, stretches the scope file's semantics); do-nothing / extend `grilling` + `roundtable_review` + Ralph verifier (rejected: leaves design review informal — see Issue 10); git submodule vs. vendoring (rejected: no submodule precedent in the repo; vendoring matches the `reference/` pattern); Path 1 plugin install for AEP (rejected: AEP is a version-controlled catalog, not a running harness); subset vs. all seven (adopted in part — see Issue 31).

### [Issue 12] [structural-1-2] [`structural`] - Severity: Major
*   **Affected Scope:** §8 "Non-goals" lines 302–311 only
*   **Discrepancy Description:** No "Goals" heading or goals list anywhere. The standard requires both Goals and Non-Goals. Goals must be inferred from §1 "Purpose" (lines 5–22) and §6 "Rollout" (lines 272–285).
*   **Rationale:** As stated in the discrepancy: the Goals half of the required pair is missing.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: no "Goals" heading exists.
*   ***Proposed Edit:***
    *   Location: Shared restructure (see Issue 15). New section "## 2. Goals" after §1 Purpose.
    *   Change: Add the section with the measurable criteria from Issue 10: pilot — all reviewers run (0 not run), report filed, findings categorized; local — 7/7 gate-scans pass with scores recorded; AEP PR — CI green including vendor-integrity + skills-freshness, merged with conversation resolution; adoption — at least one design document reviewed via `egm-review-loop` within 30 days of merge.

### [Issue 13] [structural-1-3] [`structural`] - Severity: Major
*   **Affected Scope:** §1 "Purpose" lines 5–22
*   **Discrepancy Description:** The standard requires a "Problem Statement"; the document covers motivation ("design-before-implementation becomes a loadable skill rather than an implicit habit", lines 7–10) under a different label.
*   **Rationale:** As stated in the discrepancy: the required heading is absent; the content exists under another label.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: no "Problem Statement" heading exists.
*   ***Proposed Edit:***
    *   Location: Shared restructure (see Issue 15). New section "## 3. Problem Statement" after "Goals".
    *   Change: Add the section moving §1's motivation sentences into it, plus the demonstrated case now available: the pilot round-1 review of this document (65 findings, 3 Blockers, all 5 reviewers completed — see `2026-11-06-egm-adoption-aep-goldfish-review.md`) as the concrete evidence that the existing informal instruments did not produce this review. State the problem as: design decisions reach implementation without a written, standards-audited review, and drift between design documents and code is detected only by accident.

### [Issue 14] [structural-1-4] [`structural`] - Severity: Major
*   **Affected Scope:** Lines 1–337 (whole document)
*   **Discrepancy Description:** No "Proposed Architecture" heading; architectural content is spread across §3 "Design decisions" (lines 58–150), §4 (lines 151–214), and §5 (lines 216–270). No single architectural overview section exists.
*   **Rationale:** As stated in the discrepancy: the architecture exists only as fragments across three sections.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: no "Proposed Architecture" heading exists.
*   ***Proposed Edit:***
    *   Location: Shared restructure (see Issue 15). New section "## 4. Proposed Architecture" after "Problem Statement".
    *   Change: Add the section as a single overview with the component map: pristine bundle (`~/workspace/egm/` local; `reference/elephant-goldfish-model/` in AEP) → adapted skills (local `custom-skills/egm-*/`; AEP `skills/egm-*` wrappers) → gates (SkillSpector gate-scan; vendor-integrity; skills-freshness) → dispatch (Elephant driver + Goldfish reviewers via `subagent.spawn` / harness subagent tool, direct dispatch in Environment B) → artifacts (design docs, review reports, drift reports). The existing §§3–5 keep their detail; this section is the map, with pointers to them.

### [Issue 15] [structural-1-5] [`structural`] - Severity: Major
*   **Affected Scope:** §7 "Security notes" lines 286–300; D6 read-only caveat lines 124–136
*   **Discrepancy Description:** The standard's "Risks & Limits" requires explicit failure modes, security implications, scalability limits, and mitigations under "Risks & Mitigations". The document heads only security notes; failure modes / scalability limits have no headed section, and the principal risk (D6) is stated in §3 and repeated in §7 rather than in a risks section.
*   **Rationale:** As stated in the discrepancy: risks exist only as a security subset, with no failure-mode or scalability section.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: no "Risks & Mitigations" heading exists; failure modes and scalability limits have no headed section.
*   ***Proposed Edit:***
    *   Location: Shared restructure — this edit defines it. Insert five new H2 sections after §1 Purpose ("## 2. Goals", "## 3. Problem Statement", "## 4. Proposed Architecture", "## 5. Alternatives Considered", "## 6. Risks & Mitigations") and renumber the existing sections: old §2 → §7, old §3 → §8, old §4 → §9, old §5 → §10, old §6 → §11, old §7 → §12, old §8 → §13, old §9 → §14; Appendix unchanged. Update all internal cross-references (§3→§8, §4→§9, §5→§10, §6→§11, §7→§12, §8→§13, §9→§14) to the new numbers.
    *   Change: Add "## 6. Risks & Mitigations" consolidating: D6 read-only caveat (mitigation: read-only briefs + post-run snapshot diff + line-existence check — see Issue 8); wrapper↔bundle coupling breakage on rename (mitigation: the resolve check in §5.4 verification — see Issue 32; rename of either tree is a deliberate PR touching both); dual-install drift (mitigation: canonical direction + normalize-then-diff — see Issue 6); loop cost (mitigation: bounds in §5.3 — see Issue 9); harness-version drift (mitigation: §4.5 step 4 re-run of the fixture after upgrades); failure modes (reviewer not run → round not clean, retry once; gate trip → upstream fix / baseline entry / owner force-sync; plugin install rejection on symlinks → symlink-free source).

### [Issue 16] [implementation_readiness-1-2] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Lines 81–83 (D3 item 1), 102–107, 232–235
*   **Discrepancy Description:** "Generate one per skill from the existing frontmatter (name + description)." The AEP `skill.yaml` format (verified, e.g. `skills/archify/skill.yaml`) carries `name`, `title`, `description`, `category`, `include_in_prompt` — the plan specifies values for only two fields and never says which other fields are required, what `category`/`title`/`include_in_prompt` should be, or how the file is validated. Further, the scope file's `[exclude-paths]` excludes the bare name `skill.yaml` from the manifest, so the generated files are covered by **neither** gate the plan cites.
*   **Rationale:** As stated in the discrepancy: two of five fields specified, no validation, and the file is outside both cited gates.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: `skills/archify/skill.yaml` carries all five fields; `[exclude-paths]` line 96 excludes bare `skill.yaml`; `check_skills_manifest.py` contains no `skill.yaml` reference.
*   ***Proposed Edit:***
    *   Location: D3 item 1 (lines 81–83).
    *   Change: Replace item 1 with: "`skill.yaml` per skill, hand-written (the repo norm — 61 `skill.yaml` files exist in `skills/` and no script generates them). Fields, per the established format: `name` (e.g. `egm-review`), `title` (Title Case, e.g. `EGM Review`), `description` (the frontmatter description verbatim), `category: "Work and knowledge"`, `include_in_prompt: true`. Validation: YAML parses, and `name` matches the `SKILL.md` frontmatter `name`. The files are excluded from the manifest by the bare `skill.yaml` entry in `[exclude-paths]` and are therefore covered by neither cited gate; the YAML-parse + name-match check in Phase 2 is their coverage."

### [Issue 17] [implementation_readiness-1-3] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Lines 87–90 (D3 item 3), 102–105, 185–189, 232–234
*   **Discrepancy Description:** (a) The plan never enumerates which path references inside each of the seven `SKILL.md` files must be rewritten, nor the exact replacement strings. (b) Environment B is told to use "absolute paths to `~/workspace/egm/`" — `~/workspace/egm/` is not literally an absolute path; the implementer must choose between `~/workspace/egm/...` and `/home/hatch/workspace/egm/...`. (c) The AEP wrapper resources path is given as "`.../resources/document_standards/`" with the prefix elided. (d) Environment A Path 2 (§4.3) uses an `<install-root>` that is never defined — no default value, no example — and the relative resolution from `<install-root>/skills/egm-*/` to `<install-root>/egm/` is never stated.
*   **Rationale:** As stated in the discrepancy: four separate underspecifications in one adaptation item.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified against the target file: all four gaps are as described.
*   ***Proposed Edit:***
    *   Location: D3 item 3 (lines 87–92); §4.3 (lines 180–189); §5.2 (lines 227–240).
    *   Change: (a) Adopt the rewrite mapping table from Issue 7 and require per-skill occurrence counts in the Phase 2 PR body. (b) State: Environment B uses the expanded absolute path `/home/hatch/workspace/egm/...` (the pilot already does this; `~` is never written into an adapted file). (c) Write the AEP wrapper resources path in full: `../../reference/elephant-goldfish-model/resources/document_standards/`. (d) Define `<install-root>` as the directory holding the cloned repo and the installed skills, default `$HOME/egm` (example: `/home/<user>/egm`); resolution: `<install-root>/skills/egm-*/` skills resolve bundle paths against `<install-root>/egm/`. Add the Environment B mapping (Issue 29): `<install-root>` = `~/workspace`, so `<install-root>/skills/egm-*/` is `~/workspace/custom-skills/egm-*/` and `<install-root>/egm/` is `~/workspace/egm/`.

### [Issue 18] [implementation_readiness-1-4] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Lines 261–263 (§5.4 step 2)
*   **Discrepancy Description:** "`diff -rq` bundle vs. upstream at the pinned SHA (expect zero differences outside the adaptation layer)." Two defects: (i) no command is given to fetch upstream at the pinned SHA; (ii) the bundle is a **subset** of upstream (§2: `site/`, `scripts/`, tests, per-host manifests are not vendored), so a bare `diff -rq` against a full upstream clone will report `Only in <upstream>: site`, `scripts/`, etc. — "zero differences" is unachievable as specified. No exclusion list is given, and the adaptation layer lives in `custom-skills/`, not in the bundle, so "outside the adaptation layer" has no meaning for this diff.
*   **Rationale:** As stated in the discrepancy: no fetch command, and the stated expectation is unachievable against a full upstream clone.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the bundle is a subset (§2 lists the excluded parts); the step gives no fetch command and no exclusion list.
*   ***Proposed Edit:***
    *   Location: §5.4 step 2 (lines 261–263).
    *   Change: Replace step 2 with: "Fetch upstream at the pinned SHA (`git clone --depth 1 https://github.com/google/elephant-goldfish-model.git /tmp/egm-upstream && cd /tmp/egm-upstream && git rev-parse HEAD` must print `e9e1f06a…`). Then `diff -rq` the bundle against the upstream subset only — `skills/`, `agents/`, `resources/`, `docs/`, `LICENSE`, `plugin.json` — expecting zero differences. Excluded from the comparison by design: `site/`, `scripts/`, `tests/`, `adapters/`, per-host plugin manifests (`.claude-plugin/`, `.codex-plugin/`, `.cursor-plugin/`), and all other repo-root files. The adaptation layer lives in `custom-skills/egm-*/`, not in the bundle, and is verified separately by the sync check in step 4."

### [Issue 19] [implementation_readiness-1-5] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Lines 268–270 (§5.4 step 4)
*   **Discrepancy Description:** "Sync check: local `custom-skills/egm-*` vs. AEP `skills/egm-*` wrappers byte-identical (modulo the path prefix: `~/workspace/egm/` locally vs. `../../reference/elephant-goldfish-model/` in the repo)." No command or normalization is specified. A plain `diff -r` fails on every path-reference line. The implementer must design the normalization themselves, including deciding whether `~` vs. the expanded home path counts as a difference.
*   **Rationale:** As stated in the discrepancy: a check with no command, no normalization, and an undecided edge case.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the step gives no command or normalization procedure.
*   ***Proposed Edit:***
    *   Location: §5.4 step 4 (lines 268–270).
    *   Change: Replace step 4 with: "Sync check: copy the seven local `custom-skills/egm-*/SKILL.md` files to a temp dir, run `sed -i 's|/home/hatch/workspace/egm|../../reference/elephant-goldfish-model|g'` on the copies, then `diff -r` the temp dir against the repo `skills/egm-*/` — expecting zero differences. The `~` form is never written into an adapted file (see Issue 17), so `~` vs. expanded home is not a difference the check must handle. Also assert every `agents/...` and `resources/...` reference in each adapted `SKILL.md` resolves to an existing file at the installed location (see Issue 20)."

### [Issue 20] [implementation_readiness-1-6] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Lines §4.5 (204–215), §5.4 (260–270), §6 (273–284)
*   **Discrepancy Description:** The standard requires specific test cases (happy path and edge cases). The plan contains only manual acceptance steps. There is no test case asserting that every `agents/...` and `resources/...` reference in each adapted `SKILL.md` resolves to an existing file at the installed location, no `skill.yaml` parse/schema validation, and no check that wrapper `skill.yaml` names match frontmatter. The exact failure mode D2 warns is "broken by construction" would only surface in the human pilot.
*   **Rationale:** As stated in the discrepancy: the failure mode the design most fears has no automated check.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the verification sections list manual steps only; no resolution assertion exists.
*   ***Proposed Edit:***
    *   Location: New subsection "### Verification checks" under §5.4 (after step 4); mirrored in §4.5 for Environment A Path 2.
    *   Change: Add the test cases: (1) happy path — for each of the 7 adapted `SKILL.md` files, every `agents/...` and `resources/...` reference resolves to an existing file at the installed location (check by script or by hand against the mapping table; a single dangling reference fails the check); (2) edge case — a wrapper `../../reference/...` target that does not exist fails the check (see Issue 32); (3) every `skill.yaml` parses as YAML and its `name` matches the `SKILL.md` frontmatter `name`; (4) gate-scan scores recorded for all 7 adapted skills; (5) the pilot review completes with all reviewers run (0 not run).

### [Issue 21] [implementation_readiness-1-7] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Lines 96–101, 278
*   **Discrepancy Description:** Verified in the repo: `.github/workflows/ci.yml` `vendor-integrity` is a series of **hardcoded per-tree `run:` blocks** (one each for `esf`, `neurostrata`, `neurostrata-ops`, `harness2`, `security-audit-skill`, `ub-mode`, `grim-prompter`, `docs-mcp-server`, `humanizer`) — no generic loop, so adding `reference/elephant-goldfish-model/` requires a new block in `ci.yml`, a file the plan never lists as modified. No command is given to generate `.github/vendor-elephant-goldfish-model.sha256` in the required `./path` sha256sum format, and `PROVENANCE.md`'s required fields are unspecified (existing pattern, e.g. `reference/esf/PROVENANCE.md`, carries upstream URL, pinned commit + subject, snapshot date, license, exclusions, purpose, and update history). Phase 2's gate "CI green" would pass vacuously for the new bundle without the CI edit.
*   **Rationale:** As stated in the discrepancy: the CI edit and the manifest-generation command are both missing, so the gate would pass without covering the new tree.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: 9 hardcoded per-tree blocks (confirmed by `grep -c "cd reference/"` = 10 matches, one being a `go vet` line in another job, leaving 9 vendor-integrity blocks); the esf `PROVENANCE.md` carries exactly the fields named.
*   ***Proposed Edit:***
    *   Location: D4 bundle bullet (lines 96–101); §6 Phase 2 file list (Issue 3).
    *   Change: Add to the bundle bullet: "Generate `.github/vendor-elephant-goldfish-model.sha256` with `cd reference/elephant-goldfish-model && find . -type f | sort | xargs sha256sum > ../../.github/vendor-elephant-goldfish-model.sha256` (vendor line format `<sha256hex>  ./<path>`, sorted by path). Add the tenth `vendor-integrity` `run:` block to `.github/workflows/ci.yml` for `reference/elephant-goldfish-model`, same `sha256sum -c` + unlisted-files + symlink pattern as the existing nine blocks. Write `reference/elephant-goldfish-model/PROVENANCE.md` with the esf pattern's fields: Upstream URL, Pinned commit (+ subject), Snapshot date, License, Excluded from the vendor, Purpose, Updating, Update history."

### [Issue 22] [implementation_readiness-1-8] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Lines 176–177, 198–199, 205–206
*   **Discrepancy Description:** "Equivalent native installs exist for Claude Code, Codex, Cursor, OpenCode, and Antigravity (see `docs/harnesses.md` and the per-host manifests in the repo root)." No install command, install path, or verification command is given for any of the five; the decision matrix assigns them all "Path 1 (native install)" and §4.5 step 1 defers to "the harness equivalent" of `muse plugins validate`, also undefined per harness. Only the Muse path has concrete commands.
*   **Rationale:** As stated in the discrepancy: five harnesses are assigned an install path with no commands for any of them.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: §4.2 gives commands for Muse only; the other five are a pointer to `docs/harnesses.md`.
*   ***Proposed Edit:***
    *   Location: §4.2 (lines 176–177); §4.5 step 1 (lines 205–207).
    *   Change: Replace the single deferral sentence with one subsection per harness, commands taken from the bundle's `docs/harnesses.md` install table (verified present): Claude Code — `claude plugin marketplace add google/elephant-goldfish-model && claude plugin install egm@egm`; Antigravity CLI — `agy plugin install https://github.com/google/elephant-goldfish-model`; Antigravity App/IDEs — run `/plugin`; Codex desktop and ChatGPT desktop — install the published EGM plugin (desktop-only listing); OpenCode — per the `adapters/opencode/` install path in the bundle. Verification per harness: the harness's own plugin-list/validate command; where a harness has no validate equivalent, verification is the E2E fixture run in §4.5 step 3. (If the owner scopes Environment A down per Issue 30, this fix is replaced by deleting the five-harness claim and keeping Muse only.)

### [Issue 23] [implementation_readiness-1-9] [`implementation_readiness`] - Severity: Major
*   **Affected Scope:** Lines 244–252 (§5.3)
*   **Discrepancy Description:** "Reviewers: `subagent.spawn` with the persona file path and the verbatim prompt in the brief" — the "verbatim prompt" is never quoted or located. "Require the reviewer to read persona + target + every supplied standard before returning findings (a missing read is an incomplete review…)" — no enforcement mechanism is specified. "Wait for actual completion before synthesizing; propagate failures and timeouts" — no timeout value, no failure-handling procedure. "Tool unavailability is not approval — ask one plain-text question" — the gate question text is never given. No `subagent.spawn` tool-restriction parameter is specified for the D6 "do not hand reviewers write tools" mitigation.
*   **Rationale:** As stated in the discrepancy: five dispatch parameters are asserted and none is specified.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: §5.3 names each parameter without specifying it.
*   ***Proposed Edit:***
    *   Location: §5.3 (lines 244–252); new "Roles & dispatch" subsection (Issue 2).
    *   Change: Add: "The verbatim prompt is the review instruction formed from the skill's Delegation section plus the target: persona file path, target file path + line range, assigned standard path, GoldfishContext paths, the read-only instruction, and the required report shape (severity, line numbers, discrepancy, rationale). Enforcement of the read requirement is the line-existence check (Issue 8): every cited line must exist in the target at the stated range, and the report must name the standard applied. Failure handling: a reviewer that times out, fails, or returns no report is retried once, then recorded not run — never counted as zero findings. Timeout: set from pilot evidence (see Issue 9). The gate question is the `egm-draft` section-approval question, quoted verbatim: 'Drafted [Section Name] in design_draft.md. Please review. How would you like to proceed?' with options 'Approve [Section Name] and proceed to next section' / 'Request revisions to [Section Name] (via inline comments or write-in)'. No `subagent.spawn` tool-restriction parameter exists on Muse — the D6 mitigation is the brief wording plus the post-run snapshot diff (Issue 8), stated explicitly rather than implied."

### [Issue 24] [comprehension-1-3] [`comprehension`] - Severity: Major
*   **Affected Scope:** Lines 71–73 (D2)
*   **Discrepancy Description:** "Skills resolve `agents/` and `resources/` relative to the plugin root (three parents above each `SKILL.md`)." A skill file at `skills/<skill>/SKILL.md` reaches the plugin root with two `..` segments (`../../agents/`), as D4 itself uses (`../../reference/elephant-goldfish-model/agents/`, lines 103–105). "Three parents" does not match the document's own path example.
*   **Rationale:** As stated in the discrepancy: the parent count contradicts the document's own path example.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: `skills/<skill>/SKILL.md` reaches the plugin root with `../../` — two parents.
*   ***Proposed Edit:***
    *   Location: D2 (line 72).
    *   Change: Replace "(three parents above each `SKILL.md`)" with "(two parents above each `SKILL.md`: `skills/<skill>/SKILL.md` reaches the plugin root as `../../`)."

### [Issue 25] [comprehension-1-4] [`comprehension`] - Severity: Major
*   **Affected Scope:** Lines 115–122, 190–192, 261, 276–277 (D5, §4.3, §5.4, §6)
*   **Discrepancy Description:** D5 mandates "`scan-gate.sh` on each adapted skill dir; block on score > 50 or any HIGH/CRITICAL finding, fail closed on scan errors," and §4.3/§5.4/§6 repeat "gate-scan" as a phase gate. Nowhere does the document say where `scan-gate.sh` lives, how to invoke it, what the score measures, what a HIGH/CRITICAL finding looks like, what a "dispositioned baseline entry" contains or where it is recorded, or where scores are recorded ("record scores," line 261 — in what file?).
*   **Rationale:** As stated in the discrepancy: the gate is invoked by name in five places and explained in none.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the target file never gives the script's path, invocation, score meaning, baseline format, or recording location.
*   ***Proposed Edit:***
    *   Location: D5 (lines 115–122).
    *   Change: Append to D5: "Invocation (local): `~/workspace/skillspector/scan-gate.sh <skill-dir>`; (AEP): `scripts/scan-gate.sh <skill-dir-or-file>` (usage line verified in the repo). The score is a 0–100 risk score; the gate blocks on score > 50 or any HIGH/CRITICAL finding and fails closed on scan errors. A dispositioned baseline entry is a `skillspector-baselines/<skill>.json` record (repo) / `~/workspace/skillspector/baselines/<skill>.json` (local) with accepted/dismissed findings, each carrying pattern, location, confidence, and justification. Scores are recorded in the Phase 2 PR body and in the pilot log file under `~/workspace/plans/`."

### [Issue 26] [comprehension-1-5] [`comprehension`] - Severity: Major
*   **Affected Scope:** Lines 96–107, 334–337 (D4, Appendix)
*   **Discrepancy Description:** D4 says the bundle is "Covered by the `vendor-integrity` CI job" and wrappers by "the `skills-freshness` gate (manifest + `.github/skills-sync-scope.txt` entries…)" and "the attribution table in `skills/README.md`," and D1 says to "Record the SHA in the attribution table and in the vendored tree's `PROVENANCE.md`." The document never states what either gate checks, what a manifest entry or scope-file entry looks like, what `PROVENANCE.md` or a `.github/vendor-*.sha256` file contains, or what an EGM row in the attribution table should contain (the baseline `skills/README.md` shows Source / License / Notes columns, but the target never maps EGM onto them).
*   **Rationale:** As stated in the discrepancy: five named mechanisms, none specified.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the target file names each mechanism without specifying its content or format.
*   ***Proposed Edit:***
    *   Location: New subsection "### AEP machinery" under D4 (after line 113).
    *   Change: Add the glossary: `vendor-integrity` — per-tree `run:` blocks in `.github/workflows/ci.yml` doing `sha256sum -c` on the tree's `.github/vendor-*.sha256`, plus an unlisted-files check and a broken-symlink check; `skills-freshness` — `scripts/check_skills_manifest.py --root skills --check` against `.github/skills-manifest.sha256`, proving the repo `skills/` tree equals the manifest generated after the last sync from live (bounded claim, quoted in Issue 5); manifest entry format `<sha256hex>  ./<path>`, sorted by path; scope-file entry — one directory name per line under `[skills]`; `PROVENANCE.md` fields — Upstream URL, Pinned commit (+ subject), Snapshot date, License, Excluded from the vendor, Purpose, Updating, Update history (esf pattern); `.github/vendor-*.sha256` generation command (Issue 21); attribution row — Source `google/elephant-goldfish-model` (upstream; see Issue 40 for the fork-convention exception), License `Apache-2.0`, Notes "Adapted (D3); bundle under `reference/elephant-goldfish-model/`".

### [Issue 27] [comprehension-1-6] [`comprehension`] - Severity: Major
*   **Affected Scope:** Lines 81–83, 235 (D3 item 1, §5.2)
*   **Discrepancy Description:** "Generate one per skill from the existing frontmatter (name + description)." No schema, field list, example file, or generator command is given; it is unclear whether `license` and `disable-model-invocation` (also named in the frontmatter list, line 82) belong in the YAML, whether any other fields are required by the local loader, or where the template lives. `disable-model-invocation` itself is never explained.
*   **Rationale:** As stated in the discrepancy: the generation instruction leaves schema, fields, and one named field unexplained.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the target file gives no schema, field list, or explanation of `disable-model-invocation`.
*   ***Proposed Edit:***
    *   Location: D3 item 1 (lines 81–83) — same fix as Issue 16, applied once.
    *   Change: Adopt Issue 16's replacement text, plus: "`license` and `disable-model-invocation` are frontmatter fields of the upstream `SKILL.md` and do not belong in `skill.yaml`. `disable-model-invocation: true` means the skill must not be invoked automatically by the model — it is user-invocable only (verified: the pilot skills carry this frontmatter and were invoked explicitly)."

### [Issue 28] [comprehension-1-7] [`comprehension`] - Severity: Major
*   **Affected Scope:** Lines 55–56, 209–212, 249–251 (§2, §4.5, §5.3)
*   **Discrepancy Description:** §5.3 says "preserve the skill's readiness and section-approval gates" and "ask one plain-text question and wait for the answer where no structured question tool exists," but the document never says what a readiness gate checks, what a section-approval gate approves, when either fires, or what the plain-text question should ask. §2 and §4.5 similarly mention "interactive approval gates" and approvals "simulated up front" (lines 55, 211) without explaining what was simulated or how.
*   **Rationale:** As stated in the discrepancy: gates are referenced in three places and defined in none.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the target file never defines either gate or the question text.
*   ***Proposed Edit:***
    *   Location: §5.3 (lines 249–251); §2 (lines 55–56); §4.5 step 3 (lines 209–212).
    *   Change: Add: "Readiness gate (fires before a review loop starts): the target document exists, reviewers and standards resolve to existing files, and GoldfishContext is provided (an empty list counts as provided). Section-approval gate (fires after each drafted section in `egm-draft`): the `egm-draft` question, quoted verbatim — 'Drafted [Section Name] in design_draft.md. Please review. How would you like to proceed?' with options 'Approve [Section Name] and proceed to next section' / 'Request revisions to [Section Name] (via inline comments or write-in)'. Where no structured question tool exists, ask the same question as one plain-text question and wait for the answer. 'Approvals simulated up front' (upstream 2026-10-30 fixture) means the headless run pre-approved every gate instead of waiting for a human turn — interactive gates are therefore untested upstream and must be exercised by hand the first time (§4.5 step 3)."

### [Issue 29] [comprehension-1-8] [`comprehension`] - Severity: Major
*   **Affected Scope:** Lines 244–248, 264–267 (§5.3, §5.4 step 3)
*   **Discrepancy Description:** §5.3 requires the reviewer "to read persona + target + every supplied standard before returning findings (a missing read is an incomplete review, not a clean result)," and §5.4 step 3 asks an independent subagent to verify "did reviewers actually read persona/standards/target?" No mechanism is given for observing or proving a read (no tool output, transcript check, or attestation is named), and D6 simultaneously says reviewers "must not retrieve conversation history or memory" (lines 133–135) without saying how that prohibition is enforced.
*   **Rationale:** As stated in the discrepancy: an unverifiable requirement paired with an unenforced prohibition.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the target file names no mechanism for observing a read or enforcing the prohibition.
*   ***Proposed Edit:***
    *   Location: §5.3 (lines 244–248); §5.4 step 3 (lines 264–267).
    *   Change: Replace the read requirement with its mechanism: "Each reviewer's report must cite the persona by name, the target's line numbers for every finding, and the standard applied. The driver checks every cited line exists in the target at the stated range and the named standard is the assigned one; a report failing either check is incomplete — re-run once, then record the reviewer not run. The memory prohibition is enforced by the brief (it forbids retrieval) and checked the same way: a finding whose rationale cites memory or conversation content is discarded and the reviewer is not re-dispatched. The independent verification subagent in §5.4 step 3 performs exactly these two checks against the filed reports."

### [Issue 30] [comprehension-1-9] [`comprehension`] - Severity: Major
*   **Affected Scope:** Lines 252–257, 306–308 (§5.3 overlap, §8 non-goal)
*   **Discrepancy Description:** §5.3's overlap decision ("EGM formalizes what `grilling`, `roundtable_review`, and the Ralph per-iteration verifier already do informally… keep the lighter tools for fast checks") and §8's non-goal ("No replacement of `grilling`, `roundtable_review`, or the Ralph verifier") name three project-specific instruments without a definition or link for any of them. A fresh reader cannot judge the claimed overlap, the "heavier vs. lighter" distinction, or when to choose EGM over them.
*   **Rationale:** As stated in the discrepancy: the overlap claim rests on three undefined instruments.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the target file never defines or locates any of the three instruments.
*   ***Proposed Edit:***
    *   Location: §5.3 overlap paragraph (lines 252–257).
    *   Change: Replace the paragraph with: "Overlap: EGM formalizes what three existing instruments do informally. `grilling` (`~/workspace/custom-skills/grilling/` — adversarial interview skill: relentless questioning of a plan or decision) and `roundtable_review` (`~/workspace/custom-skills/roundtable_review/` — multi-agent debate panel with claim verification and a judge's verdict) are single-session review tools with no written standard and no configured reviewer panel. The Ralph per-iteration verifier (`~/workspace/ralph/` loop — an independent, non-blocking verification subagent at the end of every iteration, per the standing loop rule) checks implementation against acceptance criteria, not design against a standard. EGM adds a written standard, a configured reviewer panel, and fresh-context reviewers. Use EGM where a written standard and a configured panel add value (design docs, upstream PRs); keep the lighter tools for fast checks."

### [Issue 31] [comprehension-1-10] [`comprehension`] - Severity: Major
*   **Affected Scope:** Lines 124–135, 292–295 (D6, §7)
*   **Discrepancy Description:** D6 states Claude tool allowlists "do **not** restrict Muse reviewers" and reviewers must be treated as able to write, then mitigates with "do not hand reviewers write tools" (line 132; repeated lines 294–295). If tool projections are unsupported on Muse, the document never explains how a reviewer is *not* handed write tools in practice, or what "agent tool projections," "Claude tool allowlists," "configured memory services," and "project instructions" (line 133) mean in the Muse environment. "Verify outputs" (line 132) is likewise vague — verify against what?
*   **Rationale:** As stated in the discrepancy: the mitigation contradicts its own premise and four terms plus "verify outputs" are undefined.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the target file never explains the mechanism or defines the terms.
*   ***Proposed Edit:***
    *   Location: D6 (lines 124–135).
    *   Change: Rewrite D6's mitigation paragraph as: "There is no tool-restriction mechanism on Muse: 'agent tool projections' (harness-level allowlists that would restrict a subagent's tools) and 'Claude tool allowlists' (the Claude Code mechanism) do not exist here, so 'do not hand reviewers write tools' means only this — the brief names no write tool, and the reviewer is instructed read-only. Enforcement is post-hoc: the snapshot-diff and line-existence checks in Issue 8. 'Configured memory services' means the NeuroStrata MCP connector and any other configured memory; 'project instructions' means `AGENTS.md` and repo instruction files. 'Verify outputs' means the two checks in Issue 8, nothing else."

### [Issue 32] [comprehension-1-11] [`comprehension`] - Severity: Major
*   **Affected Scope:** Lines 87–91, 180–189 (D3.3, §4.3)
*   **Discrepancy Description:** D3.3 defers to "see §4/§5," but §4.3 gives only the generic template "`<install-root>/egm/`" with "paths resolved against `<install-root>/egm/`" (lines 185–189) — no example of the actual path string a skill should contain, unlike §5.2 which gives the concrete local form (`~/workspace/egm/`, lines 233–234) and D4 which gives the concrete AEP form (`../../reference/...`, lines 103–105). `<install-root>` itself is never defined.
*   **Rationale:** As stated in the discrepancy: the generic template has no definition and no concrete example.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: `<install-root>` is never defined and §4.3 gives no example path string.
*   ***Proposed Edit:***
    *   Location: §4.3 (lines 180–189).
    *   Change: Add: "`<install-root>` is the directory holding the cloned repo and the installed skills, default `$HOME/egm`. Example path strings a Path 2 skill contains: `$HOME/egm/agents/design_critic.md` and `$HOME/egm/resources/document_standards/feature-spec-standard.md`. Mapping to Environment B (Issue 17): `<install-root>` is `~/workspace`, so the same strings read `/home/hatch/workspace/egm/agents/design_critic.md`."

### [Issue 33] [comprehension-1-12] [`comprehension`] - Severity: Major
*   **Affected Scope:** Lines 276–279 (§6 phase gates)
*   **Discrepancy Description:** Phase 0's gate is "pilot review verified by an independent subagent" (no verification criteria beyond the unobservable read check in comprehension-1-8); Phase 1's gate is "drift report produces a dated, accurate finding or a clean bill" — "accurate" is judged by no one and against nothing, and a "clean bill" (no findings) passes identically to a finding, so the gate cannot fail. Phase 3's gate ("E2E fixture passes on the fresh VM") is then softened by open decision 3 (lines 318–319), which asks whether Phase 3 may "stay documented-but-unexecuted."
*   **Rationale:** As stated in the discrepancy: two gates cannot fail and the third is softened by an open decision.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the gates are as described; Phase 1's gate passes on a clean bill with no target named.
*   ***Proposed Edit:***
    *   Location: §6 phase gates (lines 272–284).
    *   Change: Replace the gate column with explicit pass/fail criteria. Phase 0 passes when the pilot review completes with all reviewers run (0 not run), the report is filed, and findings are categorized; it fails on any reviewer not run or no filed report. Phase 1 passes when the drift report names its target in advance and produces a dated finding, or a clean bill with the target's design-doc coverage stated; it fails when no target is named. Phase 3 passes when the E2E fixture passes on the fresh VM; it fails when the fixture fails or when Phase 3 is unexecuted past the owner ruling required by §9 decision 3 (see Issue 36) — an unexecuted Phase 3 without that ruling fails the gate rather than passing by default.

### [Issue 34] [zoom_out-1-1] [`zoom_out`] - Severity: Major
*   **Affected Scope:** Lines 13–14, 20, §4 (151–213), §6 Phase 3 (line ~280), §9 decision 3 (lines 318–319)
*   **Discrepancy Description:** The document designs a complete second adoption — plugin install (§4.2), vendored-skills Path 2 (§4.3), a four-row decision matrix (§4.4, including a "No subagent tool at all — do not adopt" row for a case in neither environment), and per-VM-shape verification (§4.5) — covering five harnesses the user does not run (Claude Code, Codex, Cursor, OpenCode, Antigravity). The only environment with an identified user and machine is B (this VM, §5.1). The document concedes the point itself in §9 decision 3: Phase 3 may "stay documented-but-unexecuted." A section whose own author flags it as possibly never executed should not be designed in full detail now.
*   **Rationale:** As stated in the discrepancy: a full second adoption is designed for an environment with no identified user, and the document concedes it may never execute.
*   ***AI Suggestion:*** ESCALATE
*   ***Justification:*** The critique's premise — "no identified user" for Environment A — is inaccurate, and the evidence is outside every file the reviewer could read. The user explicitly requested this document to cover "both a general purpose linux VM as well as current environment; intended to support both use cases." That instruction is a user decision recorded in the requesting conversation, not in any file in GoldfishContext (the companion doc, the AEP skills README, or the repo clone). The dual-environment scope is the owner's stated intent, not the author's invention. Do not fix: whether Environment A stays fully designed, is demoted to an appendix, or is dropped is the owner's call, and the premise for dropping it does not hold.
*   ***Proposed Edit:***
    *   Location: None — no edit proposed.
    *   Change: None. Needs the user's knowledge: confirm Environment A stays in scope as fully designed (the requesting instruction says so), or rule otherwise.

### [Issue 35] [zoom_out-1-2] [`zoom_out`] - Severity: Major
*   **Affected Scope:** Lines §1 (5–10), §5.3 (252–257), §9 decision 2 (316–317)
*   **Discrepancy Description:** §1 states the purpose but cites no AEP design document, past review failure, or concrete case where existing instruments fell short. §9 decision 2 leaves the Phase 0 pilot target TBD. Meanwhile §5.3 concedes EGM "formalizes what `grilling`, `roundtable_review`, and the Ralph per-iteration verifier already do informally" and distinguishes it only by the asserted criterion "where a written standard and a configured reviewer panel add value" — but `roundtable_review` already *is* a configured reviewer panel, so the marginal value over the three existing instruments is asserted, not evidenced. Contrast the companion NeuroStrata doc (§2), which names 14 dated design docs and live questions (`identity_mode`, #44/#47) as concrete targets.
*   **Rationale:** As stated in the discrepancy: purpose asserted, no demonstrated AEP case, pilot target TBD, marginal value unevidenced.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid as written at review time — but the missing facts are now available. The pilot target is no longer TBD: the owner has directed the pilot at the AEP repo with a PR as the target state, and the pilot round-1 review of this document (65 findings, 3 Blockers, all 5 reviewers completed) is itself the demonstrated case: the existing instruments had not produced this review of this document. The fix names both.
*   ***Proposed Edit:***
    *   Location: §1 (lines 5–22); §9 decision 2 (lines 316–317).
    *   Change: Add to §1: "Demonstrated case: the pilot round-1 `egm-review-loop` run against this document (2026-11-06, 65 findings: 3 Blockers, 35 Majors, 27 Nits; report `2026-11-06-egm-adoption-aep-goldfish-review.md`) found defects — including a genuine contradiction between D3 and Path 1 and a missing CI edit — that the existing informal instruments had not surfaced. That is the marginal value: a written standard, a configured reviewer panel, and fresh-context reviewers applied to a design document, with findings filed as a dated report." Resolve §9 decision 2 by replacing it with: "Phase 0 pilot target: the AEP repo, with a PR as the target state (owner-directed 2026-11-06)."

### [Issue 36] [zoom_out-1-3] [`zoom_out`] - Severity: Major
*   **Affected Scope:** Lines 20, §5.2 (229–240), §5.4 step 4 (268–270)
*   **Discrepancy Description:** The same 7 adapted skills live in two places — local `~/workspace/custom-skills/egm-*` (paths to `~/workspace/egm/`) and AEP `skills/egm-*` wrappers (paths to `../../reference/elephant-goldfish-model/`) — with §5.2 calling `~/workspace/egm/` "the single source of truth" while the AEP copy is a second, divergent-by-path-prefix copy. The only sync enforcement is §5.4 step 4, a manual "byte-identical (modulo the path prefix)" check. No gate enforces it: the skills-freshness gate's own scope file states its bounded claim proves only that the repo tree equals the manifest generated from the repo tree after the last sync from live — "never a freshness claim against the live tree (CI cannot see live)." Vendor-integrity covers the bundle hash, not the wrappers.
*   **Rationale:** As stated in the discrepancy: two copies, one called the source of truth, no gate enforcing their agreement.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the target file's sync enforcement is the manual check, and neither cited gate covers wrapper↔local agreement.
*   ***Proposed Edit:***
    *   Location: §5.2 (lines 229–240); §5.4 step 4 (lines 268–270). Same fix as Issue 6, applied once.
    *   Change: Adopt Issue 6's replacement text (canonical direction, cadence, owner) and Issue 19's normalize-then-diff procedure. Delete the "single source of truth" sentence: neither copy is the single source of truth — the repo is canonical for wrappers, the local bundle is canonical for installed personas and standards, and their agreement is enforced by the normalize-then-diff check.

### [Issue 37] [zoom_out-1-4] [`zoom_out`] - Severity: Major
*   **Affected Scope:** Lines §2 table (38–43), §5.3 (256–257), §6 (274–284)
*   **Discrepancy Description:** The full set (2,810 lines) is scoped into the design, including `egm-bootstrap` (427 lines — the largest skill) and `egm-drift-report`. §5.3 claims both are "genuinely new capabilities with no local equivalent," but names no AEP codebase area needing bootstrap documentation and no AEP design doc needing drift detection. Phasing (§6) mitigates this only partly: Phase 1's gate is "drift report produces a dated, accurate finding **or a clean bill**" — a clean bill passes trivially, so the full set is never actually gated on demonstrated need.
*   **Rationale:** As stated in the discrepancy: the two largest unproven skills are scoped in with no named target and a gate that cannot fail.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: no AEP bootstrap or drift target is named anywhere in the document, and the Phase 1 gate passes on a clean bill.
*   ***Proposed Edit:***
    *   Location: §5.3 (lines 256–257); §6 Phase 1 gate (lines 276–277).
    *   Change: Name the targets: `egm-drift-report` — the `skills/README.md` attribution table vs. the `skills/` tree (a verifiable drift surface: rows can be missing, stale, or point at removed skills). `egm-bootstrap` — `reference/` tree documentation (each tree currently carries only a `PROVENANCE.md`; no per-tree README describing what the tree is for). Defer both skills to Phase 1 with these named targets, and replace the Phase 1 gate with Issue 33's version: the drift report names its target in advance and passes on a dated finding or a clean bill with the target's coverage stated; it fails when no target is named.

### [Issue 38] [zoom_out-1-5] [`zoom_out`] - Severity: Major
*   **Affected Scope:** Lines §3 D4 (104–120), §5.4 (260–270)
*   **Discrepancy Description:** Wrappers under `skills/egm-*/` point via relative paths (`../../reference/elephant-goldfish-model/agents/`, `.../resources/document_standards/`) into the vendored bundle. Verified in the AEP repo: no existing skill references a `reference/<tree>/` path (the only `reference/` mentions in `skills/` are `teach`'s own internal directory and `untangle-codebase`'s prohibition on running on vendored `reference/` trees). This cross-tree coupling is unproven in this codebase, and no verification step checks that the referenced paths resolve — §5.4 checks gate scores, bundle diff, pilot execution, and cross-installation byte-identity, but never that a wrapper's `../../reference/...` target exists. A rename of either tree silently breaks all 7 skills.
*   **Rationale:** As stated in the discrepancy: a new coupling pattern with no precedent and no resolve check.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified by grep: no `SKILL.md` in `skills/` references a `reference/<tree>/` path; `untangle-codebase`'s mention is a prohibition on running against vendored `reference/` trees.
*   ***Proposed Edit:***
    *   Location: D4 (lines 104–120); §5.4 verification checks (Issue 20).
    *   Change: Add to D4: "This wrapper→bundle coupling is a new pattern in this repo — no existing skill references a `reference/<tree>/` path. It is accepted explicitly here because the alternative (duplicating personas and standards per skill, or non-skill directories under `skills/`) is worse (see Alternatives Considered). Risk: renaming either tree silently breaks all 7 skills; recorded in Risks & Mitigations (Issue 15)." Add to the §5.4 verification checks (Issue 20): "(2) edge case — a wrapper `../../reference/...` target that does not exist fails the check."

### [Issue 39] [structural-1-6] [`structural`] - Severity: Nit
*   **Affected Scope:** §3 uses decision IDs `### D1`–`D7` (lines 60, 67, 77, 94, 115, 124, 137); §4 uses numeric `### 4.1`–`4.5`; §5 uses numeric `### 5.1`–`5.4`
*   **Discrepancy Description:** Sibling H2 sections use two different H3 naming schemes with no explanation.
*   **Rationale:** As stated in the discrepancy: inconsistent subsection numbering across sibling sections.
*   ***AI Suggestion:*** DECLINE
*   ***Justification:*** The two schemes serve different purposes: D1–D7 are decision identifiers (stable references used by the rest of the document and by the rollout), while 4.1–4.5 and 5.1–5.4 are positional subsections. Renumbering decisions as 3.1–3.7 would destroy the stable D-references. Cosmetic; record only.
*   ***Proposed Edit:***
    *   Location: None.
    *   Change: None.

### [Issue 40] [structural-1-7] [`structural`] - Severity: Nit
*   **Affected Scope:** Line 325: `## Appendix — Sources (all verified 2026-11-06)`
*   **Discrepancy Description:** The Appendix is the only unnumbered H2, following numbered H2s `## 1.` through `## 9.`
*   **Rationale:** As stated in the discrepancy: one unnumbered H2 breaks the numbered sequence.
*   ***AI Suggestion:*** DECLINE
*   ***Justification:*** An appendix is unnumbered by convention; the break is intentional and standard. Cosmetic; record only.
*   ***Proposed Edit:***
    *   Location: None.
    *   Change: None.

### [Issue 41] [structural-1-8] [`structural`] - Severity: Nit
*   **Affected Scope:** Lines 37–43 (§2 skills table)
*   **Discrepancy Description:** Line 37 reads `` `egm-brainstorm` (271 lines) ``; lines 38–43 read `` `egm-draft` (321) ``, `` `egm-review` (426) ``, etc. — the word "lines" appears only in the first row.
*   **Rationale:** As stated in the discrepancy: inconsistent parenthetical in the table.
*   ***AI Suggestion:*** DECLINE
*   ***Justification:*** Cosmetic inconsistency in a table whose meaning is unambiguous; not worth a review cycle on its own. Record only.
*   ***Proposed Edit:***
    *   Location: None.
    *   Change: None.

### [Issue 42] [structural-1-9] [`structural`] - Severity: Nit
*   **Affected Scope:** Lines 325–337 (Appendix)
*   **Discrepancy Description:** The Appendix lists sources as plain code spans with no URLs; the document's only URL is a bare string inside a code block (line 164). Citations cannot be followed or verified as links.
*   **Rationale:** As stated in the discrepancy: sources are not linkable.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Clearly worth it: linkifying the Appendix costs one edit per source and makes every citation verifiable, which is the point of a sources section.
*   ***Proposed Edit:***
    *   Location: Appendix (lines 325–337).
    *   Change: Render each source as a Markdown link: upstream repo `https://github.com/google/elephant-goldfish-model`; fork `https://github.com/pratik-saptarshi/elephant-goldfish-model`; `docs/muse.md`, `docs/harnesses.md`, `skills/*/SKILL.md`, `agents/*.md`, `resources/document_standards/*.md` linked at their upstream `main` paths; AEP files (`skills/README.md`, `.github/skills-sync-scope.txt`, `scripts/check_skills_manifest.py`, CI jobs, `reference/` vendor pattern) linked at their repo paths.

### [Issue 43] [design_critic-1-8] [`design_critic`] - Severity: Nit
*   **Affected Scope:** Line 337 (Appendix)
*   **Discrepancy Description:** The Appendix (headed "all verified 2026-11-06") says "`reference/` vendor pattern (8 trees, `.github/vendor-*.sha256`)". Verified by listing: `reference/` contains 9 trees (docs-mcp-server, esf, grim-prompter, harness2, humanizer, neurostrata, neurostrata-ops, security-audit-skill, ub-mode) and `.github/` contains 9 `vendor-*.sha256` files. Correct to 9. (Same error independently found by comprehension-1-21.)
*   **Rationale:** As stated in the discrepancy: a wrong count in a section headed "all verified".
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Factual error — the skill explicitly allows PROPOSE FIX for a Nit when the fix is clearly worth it, and a wrong count under a "verified" heading qualifies. Verified by listing: 9 trees, 9 manifests.
*   ***Proposed Edit:***
    *   Location: Appendix line 337.
    *   Change: Replace "(8 trees, `.github/vendor-*.sha256`)" with "(9 trees, `.github/vendor-*.sha256`)". Same fix as Issue 62 (dedup: one edit covers both findings).

### [Issue 44] [design_critic-1-9] [`design_critic`] - Severity: Nit
*   **Affected Scope:** Lines 60–66 (D1), 227–240 (§5.2)
*   **Discrepancy Description:** D1 requires the pinned SHA in "the vendored tree's `PROVENANCE.md` (AEP) / bundle README (local)". The §5.2 local layout lists only `skills/ agents/ resources/ docs/ LICENSE plugin.json` under `~/workspace/egm/` — no README or provenance file. The local record of the pin has no home in the layout it must live in.
*   **Rationale:** As stated in the discrepancy: a required artifact has no place in the layout.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Genuine omission: D1 mandates a local pin record and §5.2's layout omits it.
*   ***Proposed Edit:***
    *   Location: §5.2 layout (lines 229–232).
    *   Change: Add `README.md` to the `~/workspace/egm/` listing, with the note: "`README.md` — local pin record: upstream URL, pinned SHA (`e9e1f06a`), snapshot date, license (Apache-2.0). Written at install time; re-written on every re-sync."

### [Issue 45] [design_critic-1-10] [`design_critic`] - Severity: Nit
*   **Affected Scope:** Lines 312–323 (§9, decision 3), 203–214 (§4.5 step 3)
*   **Discrepancy Description:** Open decision 3 asks whether Phase 3 runs on a fresh VM "or stays documented-but-unexecuted", and §4.5 step 3 notes interactive approval gates "must be exercised by hand the first time" with no owner or time assigned. Roughly half the document's design surface (Environment A, §4) can therefore ship as unexecuted documentation. Until Phase 3 runs, Environment A is specified, not validated.
*   **Rationale:** As stated in the discrepancy: a parked decision leaves half the design surface unvalidated with no owner or time.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The remedy is a dated ruling requirement, not a scope decision (the scope question is Issue 34's ESCALATE; this fix only prevents the decision from staying parked).
*   ***Proposed Edit:***
    *   Location: §9 decision 3 (lines 318–319).
    *   Change: Replace decision 3 with: "Phase 3 ruling (required before Phase 2 merges): the owner rules — provision a fresh VM for Phase 3 validation, or mark Phase 3 documented-but-unexecuted and move §4 to an appendix. Until ruled, §4 carries the header note 'Provisional — validation pending owner provisioning.'"

### [Issue 46] [implementation_readiness-1-10] [`implementation_readiness`] - Severity: Nit
*   **Affected Scope:** Lines 205–207 (§4.5 step 1)
*   **Discrepancy Description:** "`muse plugins validate <path>` argument unspecified. `<path>` is presumably the cloned repo path (`./elephant-goldfish-model`), but this is never stated.
*   **Rationale:** As stated in the discrepancy: the command's argument is left to presumption.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** One-line fix, clearly worth it.
*   ***Proposed Edit:***
    *   Location: §4.5 step 1 (lines 205–207).
    *   Change: Replace "`muse plugins validate <path>`" with "`muse plugins validate ./elephant-goldfish-model` (the cloned repo path from §4.2)."

### [Issue 47] [implementation_readiness-1-11] [`implementation_readiness`] - Severity: Nit
*   **Affected Scope:** Lines 210–213 (§4.5 step 3)
*   **Discrepancy Description:** "The upstream fixture — brainstorm → draft → uninterrupted review — run once per VM shape" — no file path, test name, or invocation in the upstream repo is cited, and "interactive gates … must be exercised by hand the first time" has no hand-exercise procedure.
*   **Rationale:** As stated in the discrepancy: the fixture is named but not located or invokable from the document.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified in the bundle: the fixture run is recorded in `TESTING.md`, "Harness test record" (Muse row, 2026-10-30).
*   ***Proposed Edit:***
    *   Location: §4.5 step 3 (lines 209–212).
    *   Change: Replace step 3 with: "End-to-end acceptance: the upstream fixture recorded in `TESTING.md` ('Harness test record', Muse row, 2026-10-30) — fixture design `muse-wonder-1.0` (line-count design), run headless via `muse exec` in a temporary workspace against the installed cache only, prompt naming `docs/muse.md`, approvals simulated up front: brainstorm → draft → uninterrupted review. Run once per VM shape. Hand exercise (first time per shape): run the same fixture with approvals given by hand at each gate instead of simulated, and record which gates fired."

### [Issue 48] [implementation_readiness-1-12] [`implementation_readiness`] - Severity: Nit
*   **Affected Scope:** Lines 106–107, 278
*   **Discrepancy Description:** The plan requires seven new rows in `skills/README.md` but gives no row contents. The README's stated convention is "The Source column names pratik-saptarshi forks wherever a fork exists" — a fork exists (`pratik-saptarshi/elephant-goldfish-model`), but D1 mandates sourcing from upstream, not the fork. The implementer must resolve which value goes in Source (and what the Notes column says, e.g. adapted vs. verbatim).
*   **Rationale:** As stated in the discrepancy: row contents unspecified, and the Source convention conflicts with D1.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the README convention is verbatim as quoted, and the fork exists while D1 mandates upstream.
*   ***Proposed Edit:***
    *   Location: D4 wrappers bullet (lines 100–107).
    *   Change: Add: "Attribution rows (one per skill): Source `google/elephant-goldfish-model` — explicit exception to the README's fork-naming convention, because D1 sources from upstream (the fork is a pure mirror and adds nothing); record the exception in the Notes column. License `Apache-2.0`. Notes: 'Adapted (D3); bundle under `reference/elephant-goldfish-model/`; pinned `e9e1f06a`.'"

### [Issue 49] [implementation_readiness-1-13] [`implementation_readiness`] - Severity: Nit
*   **Affected Scope:** Lines 117–118, 261, 276–277 (D5, §5.4, §6)
*   **Discrepancy Description:** "Gate-scan all 7 adapted skills; record scores" — no location for the recorded scores (file, PR body, install notes). D5 names `scan-gate.sh` but not its path or the per-directory invocation loop (the script lives at AEP `scripts/scan-gate.sh`, usage `scan-gate.sh <skill-dir-or-file>`). §4.3 line 192 likewise says scores are "recorded in the install notes" without defining what/where the install notes are.
*   **Rationale:** As stated in the discrepancy: scores are recorded nowhere defined, and the invocation is incomplete.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: `scripts/scan-gate.sh` exists in the AEP repo with usage `scan-gate.sh <skill-dir-or-file>`; the target file never gives a recording location.
*   ***Proposed Edit:***
    *   Location: D5 (lines 115–122); §5.4 step 1 (line 261); §4.3 (lines 190–192).
    *   Change: Add to D5 the invocation and baseline format from Issue 25. Add: "Scores are recorded in the Phase 2 PR body (one line per skill: name, score, pass/block) and in the pilot log file under `~/workspace/plans/`. 'Install notes' (used in §4.3) means exactly these two records — a dated pilot log file locally, and the PR body for AEP — and the term is not used for any other artifact."

### [Issue 50] [implementation_readiness-1-14] [`implementation_readiness`] - Severity: Nit
*   **Affected Scope:** Lines 142–144 (D7)
*   **Discrepancy Description:** Only the example "`egm-design` is `agents/design_critic.md`" is given; the other nine frontmatter-`name` → file mappings must be derived by the implementer reading each `agents/*.md` frontmatter.
*   **Rationale:** As stated in the discrepancy: 1 of 10 mappings given.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified from the bundle frontmatter: all ten mappings are as below.
*   ***Proposed Edit:***
    *   Location: D7 (lines 142–144).
    *   Change: Replace the single example with the full mapping table (verified from `agents/*.md` frontmatter): `egm-design` → `agents/design_critic.md`; `egm-comprehension` → `agents/comprehension.md`; `egm-structural` → `agents/structural.md`; `egm-style` → `agents/style.md`; `egm-implementation-readiness` → `agents/implementation_readiness.md`; `egm-codebase-details` → `agents/codebase_details.md`; `egm-zoom-out` → `agents/zoom_out.md`; `egm-inventive-catalyst` → `agents/inventive_catalyst.md`; `egm-synthesizer` → `agents/synthesizer.md`; `egm-bootstrap-orchestrator` → `agents/bootstrap_orchestrator.md`.

### [Issue 51] [implementation_readiness-1-15] [`implementation_readiness`] - Severity: Nit
*   **Affected Scope:** Lines 185–189 vs. 230–235 (§4.3 generic layout vs. §5.2 actual layout)
*   **Discrepancy Description:** Path 2 puts skill dirs at `<install-root>/skills/egm-*/`; Environment B puts them at `~/workspace/custom-skills/egm-*/`. No mapping between the generic layout and the real one is stated.
*   **Rationale:** As stated in the discrepancy: two layouts for the same thing with no stated mapping.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: the two layouts differ as described with no mapping.
*   ***Proposed Edit:***
    *   Location: §4.3 (lines 185–189).
    *   Change: Add: "Mapping to Environment B: `<install-root>` is `~/workspace`, so `<install-root>/skills/egm-*/` is `~/workspace/custom-skills/egm-*/` and `<install-root>/egm/` is `~/workspace/egm/`."

### [Issue 52] [implementation_readiness-1-16] [`implementation_readiness`] - Severity: Nit
*   **Affected Scope:** Line 278 (§6 Phase 2)
*   **Discrepancy Description:** The gate requires "Conventional Commits; owner review," but no branch name is given, although the repo's `AGENTS.md` requires `type/scope-short-description` branches.
*   **Rationale:** As stated in the discrepancy: the branch convention is cited but no branch name is given.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** One-line fix, clearly worth it.
*   ***Proposed Edit:***
    *   Location: §6 Phase 2 row (line 278).
    *   Change: Add to the Phase 2 scope: "Branch: `chore/reference-vendor-elephant-goldfish-model` (per the repo's `type/scope-short-description` rule)."

### [Issue 53] [implementation_readiness-1-17] [`implementation_readiness`] - Severity: Nit
*   **Affected Scope:** Lines 158–161 (§4.1 prerequisites)
*   **Discrepancy Description:** `git`, `python3` (+ `pytest`), "one supported harness CLI" — no minimum versions, although §4.5's checks (`muse plugins validate`, named-spawn behavior) are version-sensitive per the document's own §4.5 step 4 note.
*   **Rationale:** As stated in the discrepancy: version-sensitive checks with unversioned prerequisites.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified on the pilot VM: git 2.43.0, Python 3.12.3; `pytest` is not installed on this VM; Muse 1.4.14 is the upstream-verified version.
*   ***Proposed Edit:***
    *   Location: §4.1 (lines 158–161).
    *   Change: Replace the prerequisites line with: "`git` ≥ 2.43.0, `python3` ≥ 3.12.3 (verified floor on the pilot VM), `pytest` installed separately (absent on this VM — required for `pytest tests/unit`), and one supported harness CLI — Muse ≥ 1.4.14 (the upstream-verified version)."

### [Issue 54] [comprehension-1-13] [`comprehension`] - Severity: Nit
*   **Affected Scope:** Lines 81–86 (D3 item 2)
*   **Discrepancy Description:** "No EGM skill routes a Muse session to `docs/muse.md` (upstream gap #252)" cites issue #252 with no link or summary; a fresh reader cannot check whether the one-line fix actually addresses it.
*   **Rationale:** As stated in the discrepancy: an issue citation with no link or summary.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** One-line fix, clearly worth it.
*   ***Proposed Edit:***
    *   Location: D3 item 2 (lines 84–86).
    *   Change: Replace "(upstream gap #252)" with "(upstream gap [#252](https://github.com/google/elephant-goldfish-model/issues/252): no skill routes a Muse session to `docs/muse.md`, so a Muse session does not read the guide unless pointed at it)."

### [Issue 55] [comprehension-1-14] [`comprehension`] - Severity: Nit
*   **Affected Scope:** Lines 55–56, 169–176, 205–207 (§2, §4.2, §4.5)
*   **Discrepancy Description:** "Headless run with approvals simulated up front," "chat link rendering are untested," "`marketplace add` discovers zero plugins (Muse reads the Codex catalog first and skips the entry)," and expected warnings "`multiple-manifests`; Claude-only fields ignored" are all stated without explanation of what they mean or why they matter.
*   **Rationale:** As stated in the discrepancy: four stated behaviors, none explained.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid — a fresh human reader needs these brief explanations, not only a reviewer. (Per the skill's rule: add context when a human reader needs it.)
*   ***Proposed Edit:***
    *   Location: §2 (lines 55–56); §4.2 (lines 169–176); §4.5 step 1 (lines 205–207).
    *   Change: Add parentheticals: "headless run with approvals simulated up front" → "(the run pre-approved every gate instead of waiting for a human turn, so interactive gates are untested)"; "chat link rendering are untested" → "(whether absolute-path Markdown links render as clickable links in Muse chat was not exercised)"; "`marketplace add` discovers zero plugins" → "(Muse reads the Codex catalog first and skips the entry, so it never falls through to the Claude catalog — install from a local path instead)"; expected warnings → "(`multiple-manifests` means the installer picked the Claude manifest over the Codex one; Claude-only fields such as presentation metadata, `color`, and unknown agent frontmatter keys are ignored on Muse)."

### [Issue 56] [comprehension-1-15] [`comprehension`] - Severity: Nit
*   **Affected Scope:** Lines 37, 43 (§2 skills table)
*   **Discrepancy Description:** The brainstorm output `concepts_brief.md` is named with no location or format, and `egm-drift-report` writes "a dated report" with no stated directory.
*   **Rationale:** As stated in the discrepancy: two named artifacts with no destination.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The destinations are determinable from the skills' own conventions and the pilot's practice.
*   ***Proposed Edit:***
    *   Location: §2 skills table (lines 37, 43).
    *   Change: Amend the `egm-brainstorm` row to: "Multi-reviewer idea exploration → `concepts_brief.md` (written to the working directory alongside the brainstorm). Amend the `egm-drift-report` row to: "Detect design-doc vs. code drift, write a dated report (pilot: `~/workspace/plans/<date>-<topic>-drift.md`; each drift run names its destination in advance)."

### [Issue 57] [comprehension-1-16] [`comprehension`] - Severity: Nit
*   **Affected Scope:** Lines 268–270 (§5.4 step 4)
*   **Discrepancy Description:** §5.4 step 4 requires local `custom-skills/egm-*` vs. AEP `skills/egm-*` wrappers to be "byte-identical (modulo the path prefix: `~/workspace/egm/` locally vs. `../../reference/elephant-goldfish-model/` in the repo)." Byte-identical files cannot differ by prefix; no comparison method (e.g. normalize-then-diff) is specified.
*   **Rationale:** As stated in the discrepancy: self-contradictory wording with no comparison method.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Same fix as Issue 19 (shared root cause 2).
*   ***Proposed Edit:***
    *   Location: §5.4 step 4 (lines 268–270). Same fix as Issue 19, applied once.
    *   Change: Adopt Issue 19's replacement text (normalize-then-diff with an explicit `sed` prefix replacement, then `diff -r`, plus the path-resolution assertion). Delete the phrase "byte-identical (modulo the path prefix)" everywhere it appears.

### [Issue 58] [comprehension-1-17] [`comprehension`] - Severity: Nit
*   **Affected Scope:** Lines 320–323 (§9 decision 4)
*   **Discrepancy Description:** Open decision 4 invokes "the `re0-upgrade` precedent: force-sync rests on the explicit decision, not on dispositioned findings" with no definition or link; a fresh reader cannot apply the precedent to a gate trip.
*   **Rationale:** As stated in the discrepancy: a precedent invoked without definition.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The precedent is a recorded owner decision; one sentence defines it.
*   ***Proposed Edit:***
    *   Location: §9 decision 4 (lines 320–323).
    *   Change: Replace "the `re0-upgrade` precedent: force-sync rests on the explicit decision, not on dispositioned findings" with "the `re0-upgrade` precedent (2026-11-06: 9 gate-blocked skills force-synced to local on the owner's explicit call; the override rests on that decision, not on dispositioned baseline entries): force-sync rests on the explicit decision, not on dispositioned findings."

### [Issue 59] [comprehension-1-18] [`comprehension`] - Severity: Nit
*   **Affected Scope:** Lines 224–225 (§5.1 standing rules)
*   **Discrepancy Description:** "Conventional Commits for any AEP PR; identity scrubbing in externally visible content" are stated as standing rules with no format, example, or pointer to where they are defined.
*   **Rationale:** As stated in the discrepancy: standing rules cited without format or pointer.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Both rules are defined in the AEP repo's `AGENTS.md` and the workspace `AGENTS.md`.
*   ***Proposed Edit:***
    *   Location: §5.1 (lines 224–225).
    *   Change: Replace the sentence with: "Standing rules apply: SkillSpector gate before install (D5); Conventional Commits for any AEP PR — `type(scope): description` for commits and PR titles, branches `type/scope-short-description` (AEP `AGENTS.md`); identity scrubbing in externally visible content — synthetic/bot identities only, never the user's personal name."

### [Issue 60] [comprehension-1-19] [`comprehension`] - Severity: Nit
*   **Affected Scope:** Lines 190–192 (§4.3)
*   **Discrepancy Description:** §4.3 says where the SkillSpector gate is unavailable, "the scan is run once on the authoring machine and the scores recorded in the install notes." No install-notes file, location, or format is defined anywhere in the document.
*   **Rationale:** As stated in the discrepancy: an artifact named but never defined.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Same definition as Issue 49.
*   ***Proposed Edit:***
    *   Location: §4.3 (lines 190–192). Same fix as Issue 49, applied once.
    *   Change: Adopt Issue 49's definition: "'Install notes' means exactly two records — a dated pilot log file under `~/workspace/plans/` locally, and the Phase 2 PR body for AEP — and the term is not used for any other artifact."

### [Issue 61] [comprehension-1-20] [`comprehension`] - Severity: Nit
*   **Affected Scope:** Lines 281–284 (§6 priority order)
*   **Discrepancy Description:** "Priority order within each phase follows value, not alphabetical order" lists `egm-review-loop` + `egm-review` first, then brainstorm, draft, resolve, drift-report, bootstrap — but never says why that order is the value order (e.g. why `egm-resolve` precedes `egm-drift-report`, which §5.3 calls "genuinely new").
*   **Rationale:** As stated in the discrepancy: an asserted value order with no rationale.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The rationale is statable from the document's own logic.
*   ***Proposed Edit:***
    *   Location: §6 priority paragraph (lines 281–284).
    *   Change: Append: "Rationale: review first because it gates everything else (it extends the existing review discipline and its pilot produces the evidence for the remaining skills); brainstorm, draft, and resolve next because they form the design pipeline (idea → document → findings); drift-report and bootstrap last because they need a reviewed design corpus to work against — drift detection needs design docs, and bootstrap needs scoped targets (see Issue 37)."

### [Issue 62] [comprehension-1-21] [`comprehension`] - Severity: Nit
*   **Affected Scope:** Line 337 (Appendix)
*   **Discrepancy Description:** The Appendix claims the `reference/` vendor pattern has "(8 trees, `.github/vendor-*.sha256`)"; a listing of `~/workspace/autonomous-engineering-platform/reference/` shows 9 entries (docs-mcp-server, esf, grim-prompter, harness2, humanizer, neurostrata, neurostrata-ops, security-audit-skill, ub-mode). (Same error independently found by design_critic-1-8.)
*   **Rationale:** As stated in the discrepancy: a wrong count, independently verified twice.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Factual error — same fix as Issue 43 (dedup: one edit covers both findings).
*   ***Proposed Edit:***
    *   Location: Appendix line 337. Same fix as Issue 43, applied once.
    *   Change: Replace "(8 trees, `.github/vendor-*.sha256`)" with "(9 trees, `.github/vendor-*.sha256`)".

### [Issue 63] [zoom_out-1-6] [`zoom_out`] - Severity: Nit
*   **Affected Scope:** Lines §3 D5 (122–128), §4.3 (190–192)
*   **Discrepancy Description:** D5 states "Standing rule, no exception" for the SkillSpector gate, yet §4.3 permits the scan to be "run once on the authoring machine and the scores recorded in the install notes" where the gate is unavailable — i.e. an unscanned install is acceptable in Environment A. The exception exists solely to serve the environment flagged in zoom_out-1-1.
*   **Rationale:** As stated in the discrepancy: "no exception" contradicted by an unscanned-install fallback.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The contradiction is real as written, independent of the Environment A scope question.
*   ***Proposed Edit:***
    *   Location: D5 (lines 115–122); §4.3 (lines 190–192).
    *   Change: Replace "Standing rule, no exception" in D5 with: "Standing rule, no exception where the gate is available." Replace §4.3's fallback sentence with: "Where the SkillSpector gate is unavailable on the target machine, the scan is run once on the authoring machine (invocation in Issue 25) and the scores recorded in the install notes (defined in Issue 49); an unscanned install is never acceptable — the scan happens somewhere before any install."

### [Issue 64] [zoom_out-1-7] [`zoom_out`] - Severity: Nit
*   **Affected Scope:** Lines §3 D3 item 1 (81–83)
*   **Discrepancy Description:** "Generate one per skill from the existing frontmatter (name + description)." Verified: 61 `skill.yaml` files exist in repo `skills/`, but no script generates them (`check_skills_manifest.py` does not reference `skill.yaml`), so "generate" means 7 hand-written files. Further, repo `skill.yaml` files carry fields beyond name/description (e.g. `skills/aim/skill.yaml` has `title`, `category`, `include_in_prompt`); D3 specifies name + description only, so the generated files would not match the established local format.
*   **Rationale:** As stated in the discrepancy: "generate" is unmechanized and the specified fields are thinner than the repo norm.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Verified: 61 `skill.yaml` files; `check_skills_manifest.py` contains no `skill.yaml` reference; `skills/aim/skill.yaml` carries all five fields. Same fix as Issues 16/27 (shared root cause 4).
*   ***Proposed Edit:***
    *   Location: D3 item 1 (lines 81–83). Same fix as Issue 16, applied once.
    *   Change: Adopt Issue 16's replacement text (5-field schema, hand-written per the repo norm, YAML-parse + name-match validation, manifest-exclusion note).

### [Issue 65] [zoom_out-1-8] [`zoom_out`] - Severity: Nit
*   **Affected Scope:** Lines 165–167 (`git clone ...; muse plugins install ...`), 207 ("Warnings are expected (`multiple-manifests`...)"), 262 (`diff -rq` bundle vs. upstream)
*   **Discrepancy Description:** Literal install commands, a specific expected warning string, and a specific diff invocation are implementation-level detail in a strategy document. They belong in the install runbook, not the design.
*   **Rationale:** As stated in the discrepancy: implementation detail in a strategy document.
*   ***AI Suggestion:*** CONTEST
*   ***Justification:*** The critique relies on a genre premise the document's own stated purpose contradicts — checkable evidence the reviewer could read. §1 states the document "covers technical design and architecture" for two deployment targets and is "intended to support both use cases" (lines 5–22); a design that cannot be executed is not a design for this purpose. The same round's implementation-readiness findings demand *more* exact commands, not fewer (implementation_readiness-1-8 asks for per-harness install commands, 1-10 and 1-11 ask for exact invocations). The two positions cannot both hold; the document's stated purpose and the round's own implementation-readiness standard support keeping executable detail in the design. The commands stay; if the owner wants a separate install runbook, that is a new artifact, not a deletion from this document.
*   ***Proposed Edit:***
    *   Location: None — no edit proposed.
    *   Change: None.
