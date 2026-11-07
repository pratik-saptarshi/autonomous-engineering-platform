# Goldfish Annotated Review Report — Round 4

**Target:** `/home/hatch/workspace/plans/2026-11-06-egm-adoption-aep.md` (443 lines)

**Round:** 4 of 5 (cap). Rounds 1, 2, and 3 all NOT CLEAN (0 clean rounds so far).

**Source findings:** `/home/hatch/workspace/plans/2026-11-06-egm-adoption-aep-goldfish-review-r4.md` (Round 4: 3 Blockers, 44 Majors, 9 Nits = 56 findings; all 5 reviewers completed; 0 settled items re-raised).

**Status:** resolved — all 52 PROPOSE FIX items applied to the target doc (443 → 457 lines) and verified by the coordinator; CONTEST (Issue 49), DECLINE (Issues 20, 21), and SETTLED (Issue 51) bypassed.

**Note on filename:** the skill prescribes `goldfish_review_report.md`; this dated name is used instead so the pilot's artifacts stay distinct.

**Note on discrepancy/rationale text:** condensed from the FindingsList (substance preserved); full text is in the round-4 report. Shared root causes are fixed once and cross-referenced — see the Shared-edit map. The review report's dedup map (R-A..R-O) is adopted as the cluster map; each cluster is one fix, not one fix per Issue.

## ESCALATE — none new

**No new ESCALATE items in round 4.** The one live ESCALATE remains the round-1 item `zoom_out-1-1` (Environment A scope), carried by settled round-3 Issue 85, still awaiting the owner's ruling. It was not re-raised in round 4 (the round-4 report confirms none of the 4 settled items was re-raised).

## Category counts (56 findings)

- **CONTEST:** 1 (Issue 49)
- **ESCALATE:** 0 new (live `zoom_out-1-1` remains open, see above)
- **PROPOSE FIX:** 52 (3 Blockers, 42 Majors, 7 Nits)
- **DECLINE:** 2 (Issues 20, 21 — both Nits)
- **SETTLED:** 1 (Issue 51)

By reviewer: design_critic 13 PROPOSE FIX; structural 6 PROPOSE FIX + 2 DECLINE; implementation_readiness 15 PROPOSE FIX; comprehension 12 PROPOSE FIX; zoom_out 6 PROPOSE FIX + 1 CONTEST + 1 SETTLED.

## Citation verification notes (checked against the 443-line target before writing fixes)

- All line citations in the round-4 report verified correct, with two exceptions: (a) Issue 51 cites "§11 (L400)" for the two-skill variant, but that text is at L402–403 (L400 is inside the Phase 2 Created list); (b) Issue 7/28's premise that "the fixture's prompt text lives in TESTING.md" (target L298) is **false at the pinned SHA** — TESTING.md at `e9e1f06a` (fetched verbatim) records the fixture name `muse-wonder-1.0`, the Muse row, and the run summary, but contains no prompt text anywhere. The E-I fix corrects the claim instead of relying on it.
- D5's `references/*.json` pattern matches exactly 1 file at the pin (`skills/egm-bootstrap/references/worker-return.schema.json`); the other two `references/` files are `.md` (`templates.md`, `design_doc.md`). Total bundle non-markdown files for the D5 review: 23 (see E-P).
- Issue 52's `craft-anything-protocol` precedent verified: `skills/craft-anything-protocol/SKILL.md` ("Pinned reference") cites `reference/craft-anything/` @ `2e4afc5`, vendored under the sha256 vendor-integrity regime with a `PROVENANCE.md`; the `vendor-integrity` job has a `reference/craft-anything` block (`.github/workflows/ci.yml:125`).
- Issue 44's A/B duplication located upstream: bundle `docs/designs/synthesizer.md`, Mode REVIEW, "Redundant Subagent Spawning (A/B Sampling)".
- Issue 45's namespaces verified against the bundle: all 10 `agents/*.md` frontmatter `name` values are `egm-*` (loop five: `egm-design`, `egm-comprehension`, `egm-structural`, `egm-implementation-readiness`, `egm-zoom-out`; non-loop five: `egm-style`, `egm-codebase-details`, `egm-inventive-catalyst`, `egm-synthesizer`, `egm-bootstrap-orchestrator`).
- pytest latest release verified 2026-11-06: 9.2.0 (Oct 27, 2026). PyYAML latest: 6.0.3 (Sep 25, 2025).

## Shared-edit map (one edit covers each group)

- **E-A** R-A §10.3.2 numbering gap: Issues 12, 14, 35, 37.
- **E-B** R-B §11 reorder + R-M cross-references: Issues 12, 15, 16, 17, 35, 38.
- **E-C** R-D "two checks" vs three checks + verification ownership: Issues 19, 39, 54 (and the severity-change audit half of Issue 8).
- **E-D** R-E "verbatim prompt" quoted in full: Issues 32, 40.
- **E-E** R-F C3/C6 `skill.yaml` check: Issues 6, 26.
- **E-F** R-G `pytest` pin + PyYAML prerequisite: Issues 13, 36.
- **E-G** R-H read-only residual + rollback for untracked files: Issues 1, 53.
- **E-H** R-I token budget + Phase 1 waits for decision 6: Issues 2, 34, 55.
- **E-I** R-J Environment A E2E gate: Issues 7, 28, 29.
- **E-J** R-K FindingsList / resolve-report artifacts + loop-state persistence: Issues 8 (loop-state half), 10, 41.
- **E-K** R-L problem scale / marginal value: Issues 3, 4, 50.
- **E-L** D3 table-cell prose + seven literal commands + ordering + guard: Issues 18, 25.
- **E-M** Sync check command + §10.2 translation: Issues 22, 23.
- **E-N** C1 coverage: Issue 27.
- **E-O** D6 snapshot: Issue 30.
- **E-P** D5 content-review enumeration + criterion: Issue 31.
- **E-Q** URL-fetch enforcement: Issue 11.
- **E-R** Filenames + drift + allowlist: Issues 24, 33.
- **E-S** Definitions (`live`, sync record, A/B, `egm-*` namespaces, churn/SETTLED): Issues 42, 43, 44, 45, 46.
- **E-T** Small Nits (glosses, scope-file naming, selection rule): Issues 47, 48, 56.
- **E-U** Citation-rule links: Issue 5.
- **E-V** Continuous drift detection: Issue 9.

## Shared edits (defined once, referenced by number)

- **E-A — Renumber §10.3.3–10.3.5 → §10.3.2–10.3.4.** Replace `#### 10.3.3 Readiness and section-approval gates` (L342) with `#### 10.3.2 Readiness and section-approval gates`; `#### 10.3.4 Overlap with existing tools` (L347) with `#### 10.3.3 Overlap with existing tools`; `#### 10.3.5 Brief contents and failure handling` (L351) with `#### 10.3.4 Brief contents and failure handling`. No other cross-reference updates are needed: a grep of the target finds no textual reference to §10.3.3, §10.3.4, or §10.3.5 outside the headings themselves.
- **E-B — Reorder §11 file-change lists; fix the two dangling cross-references.** (1) Move the `### 11.3 Phase 2 file-change list` block (L396 through the "Exact path list (allowlist)" paragraph, ending just before `### 11.1`) to after the `### 11.2 Phase 1 file-change list` block (L408–411). No heading renumbering: the headings already match their content (11.1 = Phase 0, 11.2 = Phase 1, 11.3 = Phase 2); only the physical order is wrong. (2) L77: replace "(see §11.1 two-skill variant)" with "(see §11.3 two-skill variant)" — the two-skill variant text lives under §11.3 (L402–403), not §11.1. (3) L392: replace "(see §10.3 priority rationale)" with "(rationale in this paragraph)" — the priority rationale sits in §11 itself (L390–393), not in §10.3.
- **E-C — Reconcile the check counts and give each check exactly one owner.** (1) In D6 (L210), replace "'Verify outputs' means the two checks in D6 (the snapshot diff and the line-existence check), nothing else." with "'Verify outputs' means the snapshot diff plus the three checks in §10.3.1 (line-existence, standard-name, memory-prohibition), nothing else." (2) In §10.3.1 (L341), replace "The memory prohibition is enforced by the brief (it forbids retrieval) and checked by a third, distinct check: the independent verification subagent in §10.5 step 3 reads each finding's rationale and flags any that cites memory or conversation content (a quote of, or a paraphrase that depends on, prior context rather than the target document and its GoldfishContext); a flagged finding is discarded and the reviewer is not re-dispatched. The independent verification subagent performs three checks against the filed reports: (a) every cited line exists in the target at the stated range; (b) the named standard is the assigned one; (c) no finding's rationale cites memory or conversation content. §10.5 step 3's questions ('did reviewers actually read persona/standards/target? were findings evidence-backed?') are answered by those two checks, not by additional checks." with "The memory prohibition is enforced by the brief (it forbids retrieval) and checked by check (c): the Elephant at consolidation reads each finding's rationale and flags any that cites memory or conversation content (a quote of, or a paraphrase that depends on, prior context rather than the target document and its GoldfishContext); a flagged finding is discarded and the reviewer is not re-dispatched. Three checks are performed once each against the filed reports: (a) every cited line exists in the target at the stated range — performed by the driver at intake; (b) the named standard is the assigned one — performed by the driver at intake; (c) no finding's rationale cites memory or conversation content — performed by the Elephant at consolidation (it holds the conversation context, so it can judge whether a rationale quotes or paraphrases prior context). §10.5 step 3's questions ('did reviewers actually read persona/standards/target? were findings evidence-backed?') are answered by those three checks, not by additional checks." (3) In §10.5 step 3 (L363), replace "An independent review subagent verifies the run (via the three checks defined in §10.3.1)." with "An independent review subagent audits the consolidation: it verifies each recorded severity change against the filed report (original severity matches, reason present) and that no severity change went unrecorded. Checks (a) and (b) are performed once, by the driver at intake; check (c) is performed once, by the Elephant at consolidation — the subagent does not re-perform them."
- **E-D — Quote the Delegation section verbatim and give the literal brief template.** In §10.3.5 (L353), replace "The verbatim prompt is the review instruction formed from the Delegation section of the bundle's `skills/egm-review-loop/SKILL.md` ('## Delegation'; line 34 in the vendored file at the pinned SHA) plus the target — i.e. the six brief items listed in the preceding paragraph: persona file path, target file path + line range, assigned standard path, GoldfishContext paths, the read-only instruction, and the required report shape (severity, line numbers, discrepancy, rationale)." with "The verbatim prompt is the Delegation section of the bundle's `skills/egm-review-loop/SKILL.md` ('## Delegation'; line 34 in the vendored file at the pinned SHA), quoted here in full, followed by the six brief items in the literal template below. Delegation (verbatim): 'A Goldfish runs in a fresh context with no conversation history. Spawn each subagent with your harness's subagent tool (Antigravity: `invoke_subagent`; Claude Code: `Agent`; Codex: `spawn_agent`). Each subagent is defined in `agents/<file>.md`, and its frontmatter `name` (for example `egm-zoom-out`) is the subagent type to request where your harness registers named subagents. Otherwise spawn a general-purpose subagent and tell it to read that persona file first. Pass the prompt verbatim and wait for the report. If your harness cannot nest subagents, use direct dispatch instead of the synthesizer. See `docs/harnesses.md`. If your harness has no subagent tool, stop and tell the user: a review in the same context is not a Goldfish review.' Brief template (literal, filling the six items in order): 'Review the target as a Goldfish reviewer. (1) Persona: read <persona-file-absolute-path> first and follow it. (2) Target: <target-file-absolute-path>, lines <start>–<end>. (3) Standard: apply <standard-file-absolute-path>. (4) GoldfishContext: read <paths>. (5) Read-only: do not write to any file and do not read or write memory; report findings only. (6) Report shape: file one report citing the persona by name, the target line numbers for every finding, and the standard applied, with severity, discrepancy, and rationale per finding.'"
- **E-E — Fix the C3/C6 `skill.yaml` procedure (compare, loop, bind the argument).** In §10.6 C3 (L372), replace the procedure `python3 -c "import yaml,sys; d=yaml.safe_load(open(sys.argv[1])); print(d['name'])" <skill.yaml>` — expected: exit 0 and the printed name equals the frontmatter `name` — with a loop that passes the path as an argument, extracts both names, and compares them (run with a python3 that has PyYAML installed; fresh VM: the §9.1 venv, `/tmp/egm-venv/bin/python3`):
    ```
    for f in <skills-dir>/egm-*/skill.yaml; do skill="${f%/skill.yaml}/SKILL.md"; a=$(python3 -c "import yaml,sys; print(yaml.safe_load(open(sys.argv[1]))['name'])" "$f"); b=$(sed -n '/^---$/,/^---$/p' "$skill" | sed -n 's/^name: *//p' | head -1); [ "$a" = "$b" ] || { echo "MISMATCH: $f ($a) vs $skill ($b)"; exit 1; }; done
    ```
    Expected: exit 0, no `MISMATCH` lines. C6 (L375) inherits this procedure unchanged ("same as C3").
- **E-F — Pin `pytest` and PyYAML; install in a venv.** In §9.1 (L230), replace "`pytest`, installed before §9.5 step 2 with `python3 -m pip install pytest` on the fresh VM (`pytest` is absent on this VM — record the installed version in the pilot log)" with "`pytest==9.2.0` and `PyYAML==6.0.3` (C3/C6 need the `yaml` module), installed before §9.5 step 2 in a virtualenv on the fresh VM (`python3 -m venv /tmp/egm-venv && /tmp/egm-venv/bin/pip install "pytest==9.2.0" "PyYAML==6.0.3"`; a venv is used because PEP 668 externally-managed environments refuse bare `pip install` and the fresh VM may have no system pip — record the installed versions in the pilot log; pytest 9.2.0 and PyYAML 6.0.3 are the latest releases, verified 2026-11-06)".
- **E-G — Read-only residual: disposable target copy + untracked-aware rollback + honest §6 wording.** (1) In §6, replace the D6 bullet's "mitigation: read-only briefs + post-run round-level snapshot diff (detection only — see D6) + line-existence check" with "controls (detection only — the residual stands): read-only briefs + disposable target copy + post-run round-level snapshot diff (detection only — see D6) + line-existence check; memory/DB writes are unrecoverable". (2) In D6 (L210), after the snapshot-scope sentence, insert: "Before dispatch, copy the target document to a disposable per-round copy (`/tmp/egm-review-<run>/target.md`, byte-identical; line numbers map 1:1 onto the original) and brief reviewers with the copy's path; a write to the copy harms nothing and the original is never opened by a reviewer. This protects the target document only: reviewers still receive absolute paths to the persona, standards, and GoldfishContext files, so writes elsewhere in the tree remain possible and are covered by detection only (below). Full containment (a reviewer that cannot write anywhere) is unavailable on Muse — there is no tool-restriction mechanism — so detection plus the disposable target copy is the strongest available control; the residual write-before-detection risk stands." (3) In D6, replace "restore the tree from git (`git checkout -- <paths>`, where `<paths>` are the paths the diff names) or re-vendor the bundle from the repo tree" with "restore tracked files from git (`git checkout -- <paths>`, where `<paths>` are the paths the diff names), remove newly created untracked files (`rm -- <paths>`), and re-vendor the bundle from the repo tree; a deleted untracked file cannot be restored — its loss is recorded in the pilot log as unrecoverable". (4) In §12 (L424), append to the residual-risk bullet: "Memory/DB writes are unrecoverable: no snapshot is taken of the NeuroStrata store, and a memory write cannot be undone."
- **E-H — Token budget: Phase 1 waits for decision 6; the cap is the size bound.** (1) In §6, replace "interim budget 12.5 reviewer-hours per run; token budget set by §14 decision 6 from the pilot log's actuals" with "interim budget 12.5 reviewer-hours per run; token budget set by §14 decision 6 from the pilot log's actuals (per-reviewer and per-run maxima) before Phase 1 starts — no Phase 1 run proceeds without it". (2) In §10.4 (L357), replace "Phase 1 interim default: the pilot's 30-minute timeout and the pilot log's token actuals carry forward; §14 decision 6 may tighten them before Phase 1, but Phase 1 does not wait on it." with "Phase 1 interim default: the pilot's 30-minute timeout carries forward; the pilot log's token actuals set the Phase 1 token budget via §14 decision 6, and Phase 1 does not start until decision 6 sets it. A per-reviewer token cap bounds cost regardless of target-document size (token cost scales with target size, so the cap is the size bound); no separate maximum target size is set." (3) In §14 decision 6 (L437), replace "before Phase 1 the owner may tighten the per-reviewer timeout and set a token budget, from the pilot log's elapsed-time and token records." with "before Phase 1 the owner sets the per-reviewer timeout and the token budget (per-reviewer and per-run maxima), from the pilot log's elapsed-time and token records; Phase 1 does not start until this ruling is recorded."

- **E-I — Environment A E2E gate: correct the TESTING.md claim, specify the prompt and outputs in-doc, define the no-`exec` path.** (1) In §9.5 step 3 (L298), replace "fixture design `muse-wonder-1.0` (the upstream fixture name for the brainstorm → draft → review sequence; its prompt text lives in TESTING.md, not in this document)" with "fixture design `muse-wonder-1.0` (the upstream fixture name for the brainstorm → draft → review sequence; a line-count design, per the upstream Muse row in TESTING.md). The prompt text is NOT in TESTING.md — verified at the pinned SHA, TESTING.md records the fixture name, the Muse row, and the run summary, but no prompt text — so the prompt is specified here, not by reference: 'Run the EGM brainstorm → draft → review sequence (fixture `muse-wonder-1.0`, a line-count design) against the installed plugin/skill cache only, in the temporary workspace, with approvals simulated up front: brainstorm the design, draft it, then run an uninterrupted review. Name `docs/muse.md` in the session prompt.'" (2) In the same step, replace "Run headless via `muse exec` (invocation: `muse exec --prompt <prompt-file>` in the temporary workspace, approvals simulated up front per the fixture)" with "Before the run, write that prompt to `/tmp/egm-e2e-<shape>/prompt.md` (`<prompt-file>`). Run headless via `muse exec --prompt /tmp/egm-e2e-<shape>/prompt.md` in the temporary workspace, approvals simulated up front per the fixture". (3) In the same step, replace "Pass, per stage: brainstorm produces `concepts_brief.md` in the workspace; draft produces a design document; review produces a filed review report." with "Pass, per stage: brainstorm produces `concepts_brief.md` in the workspace; draft produces `design_draft.md` in the workspace (the draft filename used by the bundle's `docs/claude.md` and `docs/muse.md`); review produces a filed review report in the workspace, named `<date>-muse-wonder-1.0-review.md` (`<date>` is the run date, `YYYY-MM-DD`)." (4) In §9.5 step 1 (L295–296), replace "confirm each exists on the target harness (`<cmd> --help`)" with "confirm each exists on the target harness — the three commands are `muse plugins validate`, `muse skills list --source plugin`, and `muse exec`, each probed with `<cmd> --help`", and replace "if any is absent, record it in the pilot log and proceed to the E2E fixture (step 3) as the verification gate." with "if any is absent, record it in the pilot log and proceed to the E2E fixture (step 3) as the verification gate. If the absent command is `muse exec` itself, the gate is the hand-exercised fixture run (step 3, hand exercise: the same fixture with approvals given by hand at each gate instead of simulated, which needs no `muse exec`); a VM shape with no `muse exec` and no hand-exercised run has no verification gate and does not pass."
- **E-J — FindingsList / resolve-report artifacts + loop-state persistence + resume.** (1) In §4 (L56), after "the loop re-reviews until two consecutive clean rounds.", insert "Loop sequence (both paths): draft → dispatch reviewers in parallel → each files a report → driver checks (a),(b) → Elephant consolidates into the FindingsList and writes the review report → `egm-resolve` categorizes → fixes applied → re-review until two consecutive clean rounds. Path 1 differences: reviewers are named `egm/egm-*` agents where spawn works (else the general-purpose fallback), and the synthesizer is used where the harness nests subagents; Path 2 / Environment B: direct dispatch from the Elephant, no synthesizer. FindingsList fields: `id` (`<reviewer>-<round>-<n>`), reviewer, round, severity (as filed; as consolidated, if changed), target lines, discrepancy, rationale, standard, disposition (recorded in the resolve report)." (2) In §10.3.5 (L353), append: "Artifacts: the review report (`~/workspace/plans/<date>-<topic>-goldfish-review[-rN].md` in the pilot; in the PR for AEP) is the FindingsList — the consolidated flat list, one entry per finding with the fields above. The resolve report (`~/workspace/plans/<date>-<topic>-goldfish-resolve[-rN].md`) records one disposition per finding (CONTEST / ESCALATE / DECLINE / SETTLED, §10.4). Loop state between turns is these two files plus the pilot log: if the Elephant session ends mid-round, resume by re-reading them and re-dispatching only reviewers with no filed report; no loop state lives only in the session."
- **E-K — Problem scale / marginal value: strengthen the criterion, reframe the do-nothing rejection, evaluate the middle option.** (1) In §14 decision 5 (L436), replace "(b) the finding action rate (§2) is above 0% — at least one filed finding led to a change in the reviewed document" with "(b) the finding action rate (§2) is recorded in the ruling, and the ruling states why that rate justifies the §10.4 cost; a single changed finding does not by itself establish value". (2) In §2 (L31), replace "a 0% action rate with a positive pilot-value ruling must be justified in the ruling, not assumed" with "a positive pilot-value ruling must record the action rate and justify its proportionality against the §10.4 cost, whatever the rate — including 0% — and Phase 2 proceeds only on the decision 5 ruling (see §11)". (3) In §5 (L67), replace "- Do-nothing / extend `grilling` + `roundtable_review` + the Ralph verifier — rejected: the delta table (§5, roundtable_review vs EGM) shows the incumbents lack a written standard, a configured reviewer panel, filed reports, and the drift/bootstrap skills; grafting those onto `roundtable_review` means writing a new standard set, a panel configuration, and a report/resolve loop — the same machinery EGM already ships, maintained upstream, versus 2,810 vendored lines. The cheaper path is vendoring, not re-implementing." with "- Do-nothing / extend `grilling` + `roundtable_review` + the Ralph verifier — not rejected on evidence; deferred to the §14 decision 5 pilot-value ruling: the delta table (§5, roundtable_review vs EGM) shows the incumbents lack a written standard, a configured reviewer panel, filed reports, and the drift/bootstrap skills, but no baseline control run establishes that those differences produce marginal value, so the option stays open until the ruling. If the ruling is negative, the do-nothing option is the adopted outcome (pilot rollback, §11)." (4) In §5, append after the do-nothing bullet: "- Point `roundtable_review` at the five upstream standards files, keeping the incumbent machinery — rejected: the five standards are written as inputs to `egm-review`'s five-stage procedure (each standard maps to one review stage); `roundtable_review`'s debate-and-judge format does not consume them, so adopting the standards alone means writing a panel configuration, a report/resolve loop, and a standards-to-debate mapping — the same machinery EGM already ships, maintained upstream. The standards are not separable from the review skill that applies them."
- **E-L — D3 item 3 tail: move the prose out of the table; seven literal commands; item 3 before item 2; guard fixed for Environment B.** (1) In D3 item 3 (L157–165), end the rewrite-mapping table after the `docs/muse.md` row and move the passage now inside the last row's second cell ("Record per-skill occurrence counts … Already-absolute pilot references …") into body text below the table, as ordinary paragraphs (same wording, except for the mechanism, ordering, and guard sentences replaced per (2)–(4) below). (2) Mechanism: replace "Mechanism: apply the mapping mechanically (one `sed` per row, or manual edit) and verify with §10.6 Verification check C1." with "Mechanism: apply item 3 before item 2 (the routing line inserted in item 2 already contains `<bundle>/docs/muse.md`, so a later item-3 rewrite must not touch it), one `sed` per row in table order, and verify with §10.6 Verification check C1. Literal commands (one per row, `<file>` is the adapted `SKILL.md`; each skips already-prefixed lines): `sed -i '/<bundle>\\/agents/!s|agents/|<bundle>/agents/|g' <file>`; `sed -i '/<bundle>\\/resources\\/document_standards/!s|resources/document_standards/|<bundle>/resources/document_standards/|g' <file>`; `sed -i '/<bundle>\\/resources\\/execution_instructions\\.md/!s|resources/execution_instructions\\.md|<bundle>/resources/execution_instructions.md|g' <file>`; `sed -i '/<bundle>\\/docs\\/codex\\.md/!s|\\.\\./\\.\\./docs/codex\\.md|<bundle>/docs/codex.md|g' <file>`; `sed -i '/<bundle>\\/docs\\/claude\\.md/!s|\\${CLAUDE_PLUGIN_ROOT}/docs/claude\\.md|<bundle>/docs/claude.md|g' <file>`; `sed -i '/<bundle>\\/docs\\/harnesses\\.md/!s|docs/harnesses\\.md|<bundle>/docs/harnesses.md|g' <file>`; `sed -i '/<bundle>\\/docs\\/muse\\.md/!s|docs/muse\\.md|<bundle>/docs/muse.md|g' <file>`." (3) Ordering: item 3 runs before item 2 (see (2)); the routing line is never rewritten. (4) Idempotency guard: replace "before applying, assert the file contains no `<bundle>/` prefix (`grep -q '<bundle>/' <file>` must find nothing)" with "before applying, assert the file contains neither the `<bundle>/` prefix nor, in Environment B, the `~/workspace/egm/` prefix (`grep -qE '(<bundle>|~/workspace/egm)/' <file>` must find nothing — the literal `<bundle>/` check alone cannot detect a re-run in Environment B, where adapted files use the `~` form)".
- **E-M — §10.5 step 4: executable copy + per-skill diff; §10.2: normalize-then-copy.** (1) In §10.5 step 4 (L364), replace "copy the seven local `custom-skills/egm-*/SKILL.md` files and the seven `skill.yaml` files to a temp dir created with `mktemp -d` (e.g. `/tmp/egm-sync-XXXXXX`), preserving their `egm-*/SKILL.md` + `egm-*/skill.yaml` layout (one `egm-*/` subdir per skill), run `sed -i 's|~/workspace/egm|../../reference/elephant-goldfish-model|g'` on the `SKILL.md` copies, then `diff -r` the temp dir against the repo `skills/egm-*/` — expecting zero differences" with "copy the seven local `custom-skills/egm-*/SKILL.md` files and the seven `skill.yaml` files to a temp dir created with `mktemp -d` (e.g. `/tmp/egm-sync-XXXXXX`), preserving their `egm-*/SKILL.md` + `egm-*/skill.yaml` layout: `tmp=$(mktemp -d); cd ~/workspace/custom-skills && cp --parents egm-*/SKILL.md egm-*/skill.yaml "$tmp"/`. Run `sed -i 's|~/workspace/egm|../../reference/elephant-goldfish-model|g'` on the `SKILL.md` copies, then compare per skill from the repo root (`for s in egm-*/; do diff -r "$tmp/$s" "skills/$s" || exit 1; done`) — expecting zero differences. (`diff -r` takes exactly two operands, so the temp dir is diffed against each repo `skills/egm-*/` directory in turn, not against the seven directories at once.)" (2) In §10.2 (L326), replace "Sync steps (live→repo direction only): 1) diff local `custom-skills/egm-*/` against repo `skills/egm-*/`; 2) copy changed local files into the repo wrappers;" with "Sync steps (local→repo direction only): 1) diff local `custom-skills/egm-*/` against repo `skills/egm-*/` using the §10.5 step 4 normalize-then-diff (the `sed` runs on temp copies, per-skill loop — a raw diff would show every adapted `SKILL.md` as changed, because local files contain `~/workspace/egm/...` and repo wrappers contain `../../reference/elephant-goldfish-model/...`); 2) copy the normalized temp copies (not the verbatim local files) into the repo wrappers, applying the same `~/workspace/egm` → `../../reference/elephant-goldfish-model` translation — copying local files verbatim would write local paths into the repo wrappers and break them."
- **E-N — C1: cover extensionless references, bind the placeholders, give the assertions commands.** In §10.6 C1 (L370), replace the check with: "for each of the 7 adapted `SKILL.md` files, every `agents/...`, `resources/...`, and `docs/...` reference resolves to an existing file or directory at the installed location (check by running, from the install location — Environment B: `<skills-dir>` is `~/workspace/custom-skills`, `<bundle>` is `~/workspace/egm`; Path 2: `<install-root>/skills` and `<install-root>/egm` respectively — `for f in <skills-dir>/egm-*/SKILL.md; do grep -oE '(agents|resources|docs)/[A-Za-z0-9_./-]*' "$f"; done | sed 's/\.$//' | sort -u | while read -r p; do test -e "<bundle>/$p" || echo "MISSING: $p"; done` — expected output: no `MISSING` lines. The pattern has no extension requirement, so bare directory references such as `agents/` and `resources/document_standards/` are covered; a trailing prose period is stripped before the check. 'By hand' is not an accepted method; a single dangling reference fails the check). Also assert, per adapted `SKILL.md`, the Muse routing line is present (`grep -q 'In Muse, read .*docs/muse\.md first\.' "$f"`) and no upstream-relative reference remains (`! grep -qE '(\.\./\.\./docs/|\$\{CLAUDE_PLUGIN_ROOT\}/docs/)' "$f"`)."
- **E-O — D6 snapshot: per-location loop, content hash everywhere, own-outputs exclusion, bound rollback.** In D6 (L210), replace "Before dispatch, snapshot the working tree by content hash: `git status --porcelain` in a repo target; `find <dir> -type f -exec sha256sum {} + | sort > /tmp/egm-snapshot-<run>.sha256` for a non-repo target (mtimes alone are not content-sensitive and are not used; `<run>` is the round number, e.g. `r3`). Re-run the same command to a second file and diff with `diff /tmp/egm-snapshot-<run>.sha256 /tmp/egm-snapshot-<run>-after.sha256`; any output names a modified path." with "Before dispatch, snapshot each scope location by content hash with the `find` form (`find <dir> -type f -exec sha256sum {} + | sort > /tmp/egm-snapshot-<run>-<n>.sha256`, one file per location, `<n>` = 1–4 for the four locations in scope order, `<run>` is the round number, e.g. `r3`): (1) the target repo working tree, (2) `~/workspace/egm/`, (3) each `~/workspace/custom-skills/egm-*/` dir, (4) `~/workspace/plans/`. `git status --porcelain` is not a content hash and is not used as the snapshot command. Re-run the same commands to `-after` files and `diff` each pair; any output names a modified path. The after-diff ignores files under `~/workspace/plans/` that did not exist at snapshot time (the round's own report and pilot-log entries); any modification or deletion of a pre-existing file under `~/workspace/plans/`, or any change at the other three locations, fails the round." In D6, replace "Rollback re-vendor command: copy the bundle from the repo tree (`cp -r <repo>/reference/elephant-goldfish-model <local-bundle-path>`) after `git checkout -- <paths>` restores the repo tree, where `<paths>` are the paths the diff names." with "Rollback re-vendor command: `rm -rf ~/workspace/egm/ && cp -r <repo>/reference/elephant-goldfish-model ~/workspace/egm/` (where `<repo>` is the AEP repo root; the `rm -rf` comes first because `cp -r` onto an existing destination nests rather than replaces), after `git checkout -- <paths>` restores the repo tree, where `<paths>` are the paths the diff names."
- **E-P — D5 content review: enumerate the 23 files, add a note template and a blocking criterion.** In D5 (L203), replace "Bundle non-markdown files (`agents/openai.yaml`, per-skill `test_scenarios.yaml`, `references/*.json`, `assets/icon.svg`, `docs/assets/*.svg`) are content-reviewed at vendor time: the vendor reads each file and records a one-line content note per file in the Phase 2 PR body." with "Bundle non-markdown files are content-reviewed at vendor time — 23 files at the pinned SHA: `agents/openai.yaml` ×7 (one per skill), per-skill `test_scenarios.yaml` ×7, `skills/egm-bootstrap/references/worker-return.schema.json` ×1, `assets/icon.svg` ×7 (one per skill), `docs/assets/readme-header.svg` ×1. The vendor reads each file and records a one-line content note per file in the Phase 2 PR body, in the template '`<path>`: <what the file is and that it contains no executable code, network call, or credential>'. Pass/fail: a file blocks the vendor if it contains executable code, a network call, a credential, or content whose purpose the vendor cannot state in one line; a blocked file is removed from the vendor or dispositioned by the owner before the PR merges."
- **E-Q — URL-fetch bounds: name the enforcer (post-round audit + cleanup owner).** In §12 (L421), replace "`egm-review-loop`'s URL fetching is the only network touchpoint; scope it to URLs the user supplied for that review, and bound it: https only (no http, no other schemes); each fetched page capped at 1 MB; saved under a dedicated temp dir (`/tmp/egm-urls-<run>/`, removed after the review); fetched content is treated as data, never executed; non-HTML content types are rejected." with "`egm-review-loop`'s URL fetching is the only network touchpoint; scope it to URLs the user supplied for that review, and bound it: https only (no http, no other schemes); each fetched page capped at 1 MB; saved under a dedicated temp dir (`/tmp/egm-urls-<run>/`, removed after the review); fetched content is treated as data, never executed; non-HTML content types are rejected. Enforcement: the Elephant audits the temp dir after the round — every saved file is ≤1 MB, every cited URL uses https, every saved file is HTML — and removes `/tmp/egm-urls-<run>/` after the round even if a reviewer fails or is recorded not run; a violation fails the round and is recorded in the pilot log. The audit is post-hoc: a fetch that already happened cannot be unfetched, so these bounds are enforced by the audit, not by the fetch itself."
- **E-R — Filenames, drift-report alignment, allowlist.** (1) In §11.1 (L406), replace "pilot report + pilot log under `~/workspace/plans/`" with "pilot report (`~/workspace/plans/<date>-<topic>-goldfish-review.md`) + pilot log (`~/workspace/plans/<date>-egm-pilot-log.md`, per D5)". (2) In §11.1, after "Created: `~/workspace/egm/` bundle (90 files at the pinned SHA, per §11.3);" insert "plus the locally written `~/workspace/egm/README.md` (a 91st file, per the §10.2 template; not part of the 90-file upstream bundle);". (3) In §11.2 (L410), replace "drift report at `~/workspace/plans/<date>-<topic>-drift.md` (destination named in advance)" with "drift report at `~/workspace/plans/<date>-skills-attribution-drift.md` (the §11 table's filename for the Phase 1 named target — the `<topic>=skills-attribution` instance of the §7 `<date>-<topic>-drift.md` pattern; `<date>` is the run date, `YYYY-MM-DD`)". (4) In §11.3 (L402), after "The manifest step is unchanged." append "Exact path list (allowlist): the allowlist is the generated `.github/vendor-elephant-goldfish-model.sha256` itself (a Created file in this PR, generated by the D4 command from the pinned SHA); the pre-execution statement of its contents is the 90-path inventory above (38 + 10 + 7 + 33 + `LICENSE` + `plugin.json`), and the `vendor-integrity` job enforces it." (The existing "Exact path list (allowlist)" paragraph in §11.3 is replaced by this sentence.)
- **E-S — Definitions.** (1) "live": in §10.2 (L326), replace "sync runs live→repo" with "sync runs local→repo ('live' in this section means the local `~/workspace/custom-skills/` tree)" and "Sync steps (live→repo direction only)" with "Sync steps (local→repo direction only)". (2) Sync record: in §10.2, append: "Sync record: the record of a sync — the pilot-log entry for a local sync (`~/workspace/plans/<date>-egm-pilot-log.md`), or the sync PR body for a repo sync. The D1 staleness note and the C6 record are written there." (3) A/B duplication: in §6 (L91), replace "Upstream's optional A/B duplication (two instances per reviewer) is NOT used: one instance per reviewer." with "Upstream's optional A/B duplication (two instances per reviewer) is NOT used: one instance per reviewer. (A/B duplication: the synthesizer's Mode REVIEW option of launching two independent instances of each reviewer to maximize finding recall and eliminate non-deterministic evaluation gaps — bundle `docs/designs/synthesizer.md`, Mode REVIEW, 'Redundant Subagent Spawning (A/B Sampling)'.)" (4) `egm-*` namespaces: in §7 (L104–106), after "The other 5 (`egm-style`, `egm-codebase-details`, `egm-inventive-catalyst`, `egm-synthesizer`, `egm-bootstrap-orchestrator`) are not loop reviewers — the synthesizer consolidates only where the harness nests subagents (§10.3), and the bootstrap orchestrator belongs to `egm-bootstrap`, not to review." insert "Namespace note: the 10 `egm-*` names are the named agent definitions — each is the frontmatter `name` of one `agents/*.md` file (loop five: `egm-design`, `egm-comprehension`, `egm-structural`, `egm-implementation-readiness`, `egm-zoom-out`, mapped in D7; non-loop five: the five listed above). The 7 skill names (`egm-review`, `egm-draft`, …) are a separate namespace — skill directories, not agent definitions." (5) Churn/SETTLED: in §10.4 (L357), replace "Churn: a new finding at the scope of an applied fix whose revert would resolve it, or a round whose unsettled findings substantially restate the previous round's fixed findings." with "Churn: a new finding at the scope of an applied fix whose revert would resolve it, or a round whose unsettled findings substantially restate the previous round's fixed findings — 'substantially restate' means the same target lines and the same discrepancy as a finding fixed in the previous round." and replace "SETTLED — a re-raise of a finding already recorded with one of the above dispositions at the same scope, not re-opened." with "SETTLED — a re-raise of a finding already recorded with one of the above dispositions at the same scope (same target lines and same discrepancy as the dispositioned finding), not re-opened."
- **E-T — Small Nits.** (1) D4 (L171–183): replace "(`reference/esf/` is an existing vendored tree; its `PROVENANCE.md` is the pattern exemplar)" with "(`reference/esf/` is an existing vendored tree — the ESF reference implementation for the AEP factory lane, vendored from `pratik-saptarshi/esf`; its `PROVENANCE.md` is the pattern exemplar)" and replace "inserted after the `humanizer` block" with "inserted after the `humanizer` block (the `vendor-integrity` `run:` block for the existing `reference/humanizer/` tree)". (2) §5 (L66): replace "stretches the scope file's semantics" with "stretches `.github/skills-sync-scope.txt`'s semantics". (3) §10.3.4 (L349): append "Selection rule: use EGM when the artifact is a design document (or an upstream PR) that needs a written standard and a configured panel with filed reports; use `grilling` or `roundtable_review` for a fast single-session challenge with no filed report; use the Ralph verifier for implementation-against-acceptance-criteria checks, not design review; use `brainstorming` / `writing-plans` for pre-creative work and implementation-task planning, and `egm-brainstorm` / `egm-draft` only when the multi-reviewer panel and written standards are needed for those stages."
- **E-U — Upstream-issue links (citation rule).** (1) L75: replace "#252 has no ETA" with "[#252](https://github.com/google/elephant-goldfish-model/issues/252) has no ETA" and "the line is removed if #252 closes" with "the line is removed if [#252](https://github.com/google/elephant-goldfish-model/issues/252) closes". (2) L245: replace "until issue #252 closes" with "until [issue #252](https://github.com/google/elephant-goldfish-model/issues/252) closes". (3) L262: replace "upstream issue #145" with "upstream [issue #145](https://github.com/google/elephant-goldfish-model/issues/145)". (4) L263: replace "(issue #146)" with "([issue #146](https://github.com/google/elephant-goldfish-model/issues/146))". (5) L392: replace "upstream GitHub issues are cited only with repo + link (e.g. #252)" with "upstream GitHub issues are cited only with repo + link (e.g. [#252](https://github.com/google/elephant-goldfish-model/issues/252))" — the example itself was a bare `#252`.
- **E-V — Continuous drift detection.** In §10.2 (L326), append: "Continuous detection between syncs: repo-side drift (wrappers vs bundle) is covered by check C2, whose resolve loop runs as a step in the `vendor-integrity` CI job on every PR (it reads only the repo tree). Local↔repo drift is detected only at sync time; the cadence bounds the window — a local adaptation change and its sync land in the same change, so no local change sits unsynced past its own PR, and a re-vendor triggers a sync in the same PR. Maximum tolerable drift window: one sync interval on the local side; zero on the repo side (C2 runs on every PR)."

## Prioritized Findings & AI Suggestions

### Blockers

### [Issue 1] [design_critic-4-1] - Severity: Blocker
*   **Affected Scope:** §6 (L88), §8 D6 (L210), §12 (L424)
*   **Discrepancy Description:** The read-only guarantee is false by the doc's own admission: detection is post-hoc, rollback (`git checkout -- <paths>`) restores tracked-file content only (cannot restore a deleted untracked file, remove a newly created untracked file, or undo a memory/DB write), and memory/DB paths are out of snapshot scope.
*   **Rationale:** A standard requires risks to be identified *and* mitigated; the principal risk is accepted as a residual while reviewers run with full filesystem/memory access in parallel. §6 lists it as "mitigated by" a brief (an instruction, not a tool restriction) plus a snapshot diff and a line-existence check.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid in substance, with one correction to the framing: the doc never claims a read-only guarantee — D6 states explicitly "do not assume Goldfish reviewers are read-only". What is genuinely defective is (a) the rollback, which cannot handle untracked creation/deletion, (b) §6's "mitigated by" wording, which overstates a detection-only control, and (c) the unrecoverability of memory writes, which is stated only for the snapshot scope and not as a rollback limit. Full containment is unavailable on Muse (no tool-restriction mechanism), so the fix closes what can be closed textually: a disposable target copy (the one containment control available), untracked-aware rollback, and honest residual wording. Shared edit E-G.
*   ***Proposed Edit:***
    *   Location: §6 D6 bullet; D6 (L210); §12 (L424) (shared edit E-G).
    *   Change: Apply E-G.

### [Issue 22] [implementation_readiness-4-1] - Severity: Blocker
*   **Affected Scope:** §10.5 step 4 (L364)
*   **Discrepancy Description:** `diff -r` with "the temp dir against the repo `skills/egm-*/`" — the shell expands `skills/egm-*/` to seven directory operands, so `diff -r <tmp> <7 dirs>` fails with an extra-operand error. No copy command is given for getting the seven `SKILL.md` + seven `skill.yaml` files into the `mktemp -d` directory while preserving their layout.
*   **Rationale:** A normative verification step whose literal command errors, and whose setup step is unstated, forces the implementer to invent the procedure; under the zero-decision rule the sync gate cannot be run on first attempt as written.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. `diff -r` takes exactly two operands; the seven-directory form cannot execute. The fix gives the `cp --parents` setup and a per-skill diff loop. Shared edit E-M (with Issue 23).
*   ***Proposed Edit:***
    *   Location: §10.5 step 4 (L364) (shared edit E-M).
    *   Change: Apply E-M part (1).

### [Issue 26] [implementation_readiness-4-5] - Severity: Blocker
*   **Affected Scope:** §10.6 C3 (L372) and C6 (L375)
*   **Discrepancy Description:** `python3 -c "import yaml,sys; d=yaml.safe_load(open(sys.argv[1])); print(d['name'])" <skill.yaml>` — no filename argument is passed, so `sys.argv[1]` raises `IndexError`; the `<skill.yaml` stdin redirect is irrelevant. The command only prints one `name` — it never extracts the `SKILL.md` frontmatter `name`, never compares the two, never iterates over the 7 skills, and never states the working directory. C6 inherits the same procedure.
*   **Rationale:** C3/C6 are the sole coverage for `skill.yaml` files, which the plan itself states are covered by neither CI gate; a broken, non-comparing test procedure means the implementer must write the actual test.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid on every point; the `IndexError` is deterministic. The fix passes the path as an argument, extracts both names, compares them, and loops over all 7 skills. Shared edit E-E (with Issue 6).
*   ***Proposed Edit:***
    *   Location: §10.6 C3 (L372); C6 (L375) (shared edit E-E).
    *   Change: Apply E-E.

### Majors

### [Issue 2] [design_critic-4-2] - Severity: Major
*   **Affected Scope:** §6 (L91), §10.4 (L357), §14 decision 6 (L437)
*   **Discrepancy Description:** No enforceable token or dollar budget: only a spawn/time bound (25 spawns, 12.5 reviewer-hours); §10.4 says the pilot log's token actuals carry forward and decision 6 may tighten them, but Phase 1 does not wait on it. No per-reviewer token estimate, no dollar figure, no cap on target-document size.
*   **Rationale:** A "25 spawns" bound is not a cost bound: each spawn reads the persona, the standard(s), and the full target, so token cost scales with target size, which is unbounded.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix does not invent a token number (that is the owner's decision-6 ruling, which is exactly the doc's existing mechanism) — it makes Phase 1 actually wait for that ruling and states that the per-reviewer token cap is the size bound, since cost scales with target size. Shared edit E-H (with Issues 34, 55).
*   ***Proposed Edit:***
    *   Location: §6; §10.4 (L357); §14 decision 6 (L437) (shared edit E-H).
    *   Change: Apply E-H.

### [Issue 3] [design_critic-4-3] - Severity: Major
*   **Affected Scope:** §3 (L42), §2 (L31), §14 decision 5 (L436)
*   **Discrepancy Description:** Problem scale unestablished (no incident, no load count, demand baseline deferred to the pilot log) while §14 criterion (b) is "finding action rate above 0% — at least one filed finding led to a change", i.e. 1-in-65 satisfies it. A precautionary adoption with a >0% success bar does not establish the §10.4 cost (up to 25 spawns, 12.5 reviewer-hours) is proportionate.
*   **Rationale:** The r3 fix (justify a 0% action rate) leaves the 1-finding case unjustified; the bar is trivially satisfiable.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix strengthens criterion (b) to require the ruling to record the rate and justify proportionality at whatever rate — including 0% — and states that a single changed finding does not by itself establish value. No threshold number is invented; the proportionality judgment stays with the owner, but it must now be stated. Shared edit E-K (with Issues 4, 50).
*   ***Proposed Edit:***
    *   Location: §14 decision 5 (L436); §2 (L31) (shared edit E-K parts (1)–(2)).
    *   Change: Apply E-K parts (1)–(2).

### [Issue 4] [design_critic-4-4] - Severity: Major
*   **Affected Scope:** §5 (L67, L82–83), §14 decision 5 (L436)
*   **Discrepancy Description:** Line 67 rejects do-nothing / extend the incumbents because the delta table "shows" they lack a written standard, a configured panel, filed reports, and the drift/bootstrap skills — while lines 82–83 concede no baseline control run was performed, so the 65-finding pilot does not establish marginal value over the incumbent. Feature presence is not evidence of marginal value.
*   **Rationale:** The rejection rests on evidence the doc says does not exist; the alternatives rule requires each rejection to carry a concrete trade-off.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix reframes the bullet as deferred-to-decision-5 rather than rejected-on-evidence, and makes the Phase 2 gate conditional on the ruling in §2 as well as §11. Shared edit E-K (with Issues 3, 50).
*   ***Proposed Edit:***
    *   Location: §5 (L67); §2 (L31) (shared edit E-K part (3), plus the Phase 2 sentence in part (2)).
    *   Change: Apply E-K parts (2)–(3).

### [Issue 5] [design_critic-4-5] - Severity: Major
*   **Affected Scope:** §5 (L75), §9.2 (L262–263), §9.2 Path 1 (L245), §11 (L392)
*   **Discrepancy Description:** Line 392 asserts "No bare 'Issue N' references remain in this document; upstream GitHub issues are cited only with repo + link (e.g. #252)." In fact line 262 cites "upstream issue #145" with no link, line 263 cites "(issue #146)" with no link, line 75 cites "#252 has no ETA" bare, and line 245 says "until issue #252 closes" bare (the linked form exists only at line 153, in D3). Direct internal contradiction; also breaches the standard's Alternatives Rule on attributing a rejection to a maintainer without linking their issue.
*   **Rationale:** The doc violates a citation rule it asserts; the Cursor/OpenCode rejections rest on unlinked issues.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; all four bare citations verified in the target, and L392's own "(e.g. #252)" example is itself a bare citation. The fix adds the full issue links and fixes the example. Shared edit E-U.
*   ***Proposed Edit:***
    *   Location: L75, L245, L262–263, L392 (shared edit E-U).
    *   Change: Apply E-U.

### [Issue 6] [design_critic-4-6] - Severity: Major
*   **Affected Scope:** §10.6 C3 (L372), C6 (L375), §9.1 (L230)
*   **Discrepancy Description:** Normative `skill.yaml` verification cannot run as written (missing argument, `IndexError`, stdin redirect irrelevant; C6 inherits the bug). Separately, PyYAML is not listed in §9.1 prerequisites, so `import yaml` may fail on the fresh VM even with a fixed command.
*   **Rationale:** C1–C7 are declared "the normative test list" (L366); a broken procedure plus a missing dependency means the check cannot run.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid — same defect as Issue 26 (Blocker), stated here with the added PyYAML prerequisite gap. Shared edits E-E (procedure) and E-F (PyYAML in §9.1).
*   ***Proposed Edit:***
    *   Location: §10.6 C3 (L372), C6 (L375); §9.1 (L230) (shared edits E-E, E-F).
    *   Change: Apply E-E and E-F.

### [Issue 7] [design_critic-4-7] - Severity: Major
*   **Affected Scope:** §9.5 (L295, L298), §9 header (L226), §14 decision 3 (L434)
*   **Discrepancy Description:** Environment A end-to-end gate is circular and depends on an external document that is not vendored: the fixture prompt "lives in TESTING.md, not in this document" and TESTING.md is NOT vendored; the fixture runs "via `muse exec`", whose existence step 1 declines to assert. If `exec` is absent, there is no gate at all for Path 1.
*   **Rationale:** The gate (step 3) requires the very command step 1 declined to assert; half the claimed two-target architecture (§1) is unvalidated by design.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid, and the premise is worse than stated: TESTING.md at the pinned SHA `e9e1f06a` (fetched verbatim) contains no prompt text at all — only the fixture name, the Muse row, and the run summary — so L298's "its prompt text lives in TESTING.md" is false. The fix specifies the prompt in-doc, creates `<prompt-file>` before the run, names the draft/review outputs, expands `<cmd>`, and defines the no-`exec` gate as the hand-exercised run. Shared edit E-I (with Issues 28, 29).
*   ***Proposed Edit:***
    *   Location: §9.5 steps 1 and 3 (L295–298) (shared edit E-I).
    *   Change: Apply E-I.

### [Issue 8] [design_critic-4-8] - Severity: Major
*   **Affected Scope:** §10.3 (L334, L336–337), §6 (L93), §4 (L54–56)
*   **Discrepancy Description:** The Elephant is a single point of failure with no failure handling: it owns the design doc, runs the loop, acts as Driver, replaces the Synthesizer, merges duplicates, normalizes severity, and assigns stable ids. §6 covers reviewer failure but no Elephant/driver failure: no persisted loop state, no recovery if the Elephant session crashes mid-round, no handoff procedure, and no check on the consolidator (it can change severity, subject only to a recording rule).
*   **Rationale:** The design's integrity rests entirely on one session's correctness and survival, while reviewers are deliberately fresh-context and cannot reconstruct loop state.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid on both halves. Loop state: the fix persists it in the review report (FindingsList) + resolve report + pilot log and defines resume (re-dispatch only reviewers with no filed report). Consolidator check: the fix re-scopes the §10.5 step 3 independent subagent to audit severity-change records against the filed reports. Shared edits E-J (loop state) and E-C part (3) (severity-change audit).
*   ***Proposed Edit:***
    *   Location: §10.3.5 (L353); §4 (L56); §10.5 step 3 (L363) (shared edits E-J, E-C).
    *   Change: Apply E-J part (2) and E-C part (3).

### [Issue 9] [design_critic-4-9] - Severity: Major
*   **Affected Scope:** §10.2 (L326), §8 D4 (L187), §10.5 step 4 (L364)
*   **Discrepancy Description:** Dual-install drift mitigated only at sync time, with no continuous detection: opposite canonical directions per artifact, and the normalize-then-diff runs only when a human/agent performs a sync; no CI job, cron, or scheduled check is specified between syncs, and §6's mitigation is just "canonical direction + normalize-then-diff". Two writable copies of the same skills plus a third copy of the bundle will drift silently between syncs, undetectable by either CI gate.
*   **Rationale:** The `skills-freshness` gate detects neither drift against the upstream bundle nor drift against local `custom-skills/` (L187); a sync-time-only check leaves the drift window unbounded.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix adds continuous detection where it is possible (repo-side: the C2 resolve loop as a `vendor-integrity` CI step on every PR) and bounds the local side by the cadence (a local change and its sync land in the same change). Shared edit E-V.
*   ***Proposed Edit:***
    *   Location: §10.2 (L326) (shared edit E-V).
    *   Change: Apply E-V.

### [Issue 10] [design_critic-4-10] - Severity: Major
*   **Affected Scope:** §4 (L44–58), §10.3.5 (L353)
*   **Discrepancy Description:** §4 is a pointer, not a design: "The existing §§8–10 keep their detail; this section is the map, with pointers to them" / "Detail lives in §§8–10; this section is the map." No interface between the Elephant and the harness plugin cache (Path 1) versus the vendored tree (Path 2), no state machine for the loop, and no schema for the FindingsList ("flat FindingsList with stable ids" — fields beyond severity/lines never defined).
*   **Rationale:** A fresh engineer cannot implement or operate the loop from §4; the standard requires the section to detail component layout, data flows, and ecosystem integration.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix adds the per-path loop sequence and the FindingsList field list to §4, and defines the FindingsList/resolve-report artifacts in §10.3.5. Shared edit E-J (with Issues 8, 41).
*   ***Proposed Edit:***
    *   Location: §4 (L56); §10.3.5 (L353) (shared edit E-J).
    *   Change: Apply E-J.

### [Issue 11] [design_critic-4-11] - Severity: Major
*   **Affected Scope:** §12 (L421), §8 D6 (L210)
*   **Discrepancy Description:** URL-fetch bounds are prose with no enforcement mechanism: https-only, 1 MB cap, dedicated temp dir, data-only, non-HTML rejection — no actor, tool, or check is named that enforces any of them, and if the reviewer fails or is recorded not run, cleanup is unspecified. A reviewer that fetches an http URL, a 50 MB page, or executable content has violated every bound before anyone notices.
*   **Rationale:** Fetched external content is fed into the review — the classic prompt-injection surface for a fresh-context reviewer — with no named enforcement.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. No enforcement exists in the text. The fix names the enforcer (the Elephant's post-round audit of the temp dir) and the cleanup owner on failure (the Elephant removes the dir after the round even if a reviewer fails), and states honestly that the audit is post-hoc. Shared edit E-Q.
*   ***Proposed Edit:***
    *   Location: §12 (L421) (shared edit E-Q).
    *   Change: Apply E-Q.

### [Issue 14] [structural-4-1] - Severity: Major
*   **Affected Scope:** §10.3.2 missing (§10.3, L339–342)
*   **Discrepancy Description:** The subsection numbering jumps from `#### 10.3.1 Reviewer brief` (line 339) directly to `#### 10.3.3 Readiness and section-approval gates` (line 342). No §10.3.2 heading exists anywhere in the document, and no text references §10.3.2, so a section was deleted without renumbering (or a section is missing).
*   **Rationale:** A gap in a numbered sequence breaks the document's internal addressing: a reader or a later cross-reference cannot tell whether §10.3.2 content was lost or the numbering is simply wrong.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; verified — no §10.3.2 exists. The fix renumbers 10.3.3–10.3.5 to 10.3.2–10.3.4 (no missing content is restored; the gap is a renumbering error, not a lost section — nothing in the document references §10.3.2 content). Shared edit E-A (R-A cluster: Issues 12, 14, 35, 37).
*   ***Proposed Edit:***
    *   Location: §10.3 headings (L342, L347, L351) (shared edit E-A).
    *   Change: Apply E-A.

### [Issue 15] [structural-4-2] - Severity: Major
*   **Affected Scope:** §11 subsections out of numerical order (§11, L396, L404, L408)
*   **Discrepancy Description:** The subsections appear as `### 11.3 Phase 2 file-change list` (line 396), then `### 11.1 Phase 0 file-change list` (line 404), then `### 11.2 Phase 1 file-change list` (line 408) — Phase 2 before Phase 0 and Phase 1. This contradicts the §11 rollout table itself (lines 384–387), which lists phases in order 0, 1, 2, 3.
*   **Rationale:** Subsections of a numbered section must follow numerical order; the current order forces a reader to jump backwards through the rollout sequence and invites misreading the phase order.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix moves the Phase 2 block after the Phase 1 block; no heading renumbering is needed because the headings already match their content. Shared edit E-B (R-B cluster: Issues 12, 15, 35, 38).
*   ***Proposed Edit:***
    *   Location: §11 (L396–411) (shared edit E-B part (1)).
    *   Change: Apply E-B part (1).

### [Issue 16] [structural-4-3] - Severity: Major
*   **Affected Scope:** Cross-reference points at the wrong subsection (§11.1 vs §11.3) (§5, L77)
*   **Discrepancy Description:** Line 77 says "(see §11.1 two-skill variant)", but the two-skill variant text (lines 402–403) lives under `### 11.3 Phase 2 file-change list` (line 396), not under §11.1 (line 404, Phase 0 file-change list, which contains no two-skill variant).
*   **Rationale:** The reference is misdirected — compounded by Issue 15, since renumbering/reordering §11 changes which heading is §11.1.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; verified L77 and L402–403. The fix points at §11.3, which is the correct number both before and after the E-B reorder. Shared edit E-B part (2).
*   ***Proposed Edit:***
    *   Location: §5 (L77) (shared edit E-B part (2)).
    *   Change: Apply E-B part (2).

### [Issue 17] [structural-4-4] - Severity: Major
*   **Affected Scope:** Dangling cross-reference to a non-existent "§10.3 priority rationale" (§11, L392)
*   **Discrepancy Description:** Line 392 ends "(see §10.3 priority rationale)", but §10.3 (Dispatch, lines 328–353) contains no priority rationale — no discussion of phase/skill priority order appears anywhere in §10.3. The priority rationale actually sits in §11 itself, lines 390–393 (the paragraph containing the reference).
*   **Rationale:** The cited location does not contain the cited content, so the reference cannot be followed.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; verified — §10.3 has no priority rationale, and L390–393 is the rationale. The fix points at the paragraph itself. Shared edit E-B part (3).
*   ***Proposed Edit:***
    *   Location: §11 (L392) (shared edit E-B part (3)).
    *   Change: Apply E-B part (3).

### [Issue 18] [structural-4-5] - Severity: Major
*   **Affected Scope:** Substantive prose embedded inside a table cell (D3 mapping table) (§8 D3, L157–165, defect on L165)
*   **Discrepancy Description:** The last row of the rewrite-mapping table has a multi-sentence prose passage appended inside its second cell on line 165 — per-skill occurrence counts, the Muse routing-line verification note, the `~` vs expanded-path rule, the pristine-bundle rule, the mechanical-application mechanism, the idempotency guard, the literal `sed` example, and the Phase 2 PR-body recording instruction — all running on as table-cell content rather than body text.
*   **Rationale:** A table cell is not a container for a paragraph of normative procedure: it renders as an unreadably wide cell, breaks the table's two-column symmetry, and hides verification instructions where a reader scanning body text will not look.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; verified L165. The fix moves the passage into body text below the table and, in the same move, replaces the mechanism/ordering/guard sentences with the corrected versions (Issue 25). Shared edit E-L (with Issue 25).
*   ***Proposed Edit:***
    *   Location: D3 item 3 (L157–165) (shared edit E-L).
    *   Change: Apply E-L.

### [Issue 19] [structural-4-6] - Severity: Major
*   **Affected Scope:** Internal count contradiction: "two checks" vs three checks in §10.3.1 (§10.3.1, L341)
*   **Discrepancy Description:** The same bullet first introduces the memory-prohibition enforcement as "a third, distinct check" and enumerates three checks — (a) line existence, (b) standard name, (c) no memory/conversation citation — then concludes "§10.5 step 3's questions … are answered by those two checks, not by additional checks."
*   **Rationale:** A normative verification description that contradicts its own enumeration within one paragraph leaves the driver/verification subagent unable to tell whether two or three checks are required, and whether check (c) is in or out.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; verified L341. The fix aligns the sentence with the three-check enumeration and reconciles D6's "two checks" (snapshot diff + line-existence) with §10.3.1's three (the line-existence check is the shared one). Shared edit E-C (R-D cluster: Issues 19, 39, with Issue 54's ownership half).
*   ***Proposed Edit:***
    *   Location: §10.3.1 (L341); D6 (L210); §10.5 step 3 (L363) (shared edit E-C).
    *   Change: Apply E-C.

### [Issue 23] [implementation_readiness-4-2] - Severity: Major
*   **Affected Scope:** §10.2 (L326)
*   **Discrepancy Description:** Sync procedure omits the path translation that §10.5 step 4 exists to perform. Step 1 is a bare "diff local `custom-skills/egm-*/` against repo `skills/egm-*/`", with no diff command and no normalize step; step 2 is "copy changed local files into the repo wrappers", with no copy command. A raw diff will show every adapted `SKILL.md` as changed (local `~/workspace/egm/...` vs repo `../../reference/elephant-goldfish-model/...`), and copying the "changed" files verbatim would write local paths into the repo wrappers and break them.
*   **Rationale:** Following §10.2 literally produces incorrect wrappers; producing correct ones requires the implementer to design the normalize-then-copy step. The only translation in the document (`sed 's|~/workspace/egm|../../reference/elephant-goldfish-model|g'`, L364) is defined for the temp-dir *check*, not for the actual sync copy.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix states the normalize-then-copy explicitly in §10.2 steps 1–2, referencing the §10.5 step 4 procedure. Shared edit E-M part (2) (with Issue 22).
*   ***Proposed Edit:***
    *   Location: §10.2 (L326) (shared edit E-M part (2)).
    *   Change: Apply E-M part (2).

### [Issue 24] [implementation_readiness-4-3] - Severity: Major
*   **Affected Scope:** §10.2 layout (L317) vs §11.1 (L406) and C7 (L376)
*   **Discrepancy Description:** `~/workspace/egm/README.md` is required by C7 (L376) and its literal four-line template is given in the §10.2 layout (L317), but it appears in no phase file-change list. §11.1 (L406) says Phase 0 creates "the `~/workspace/egm/` bundle (90 files …)" plus the two pilot skill dirs. The 90 files are the upstream bundle; `README.md` is a locally written 91st file, not part of the upstream bundle, so it is not covered by the "90 files" count and is not listed as created anywhere in §11.
*   **Rationale:** An implementer enforcing §11.1 would not create `README.md`; an implementer satisfying C7 must create it. The plan does not say which phase creates it or what its exact creation step is.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; verified L317, L376, L406. The fix adds `README.md` to the Phase 0 Created list (it is written at install time, which is Phase 0). Shared edit E-R part (2) (with Issue 33).
*   ***Proposed Edit:***
    *   Location: §11.1 (L406) (shared edit E-R part (2)).
    *   Change: Apply E-R part (2).

### [Issue 25] [implementation_readiness-4-4] - Severity: Major
*   **Affected Scope:** D3 (L165)
*   **Discrepancy Description:** Path-resolution adaptation has one literal command for seven rows: only the `agents/` `sed` example exists; the mechanism is "one `sed` per row, or manual edit". No ordered commands are given for the remaining six rows, whose patterns need different escaping and anchoring (notably `${CLAUDE_PLUGIN_ROOT}` and the `../../` prefix). The ordering of D3 items 2 and 3 is unspecified: the routing line inserted in item 2 already contains `<bundle>/docs/muse.md`, so a naive item-3 rewrite of `docs/muse.md` could double-prefix it. The idempotency guard (`grep -q '<bundle>/'` must find nothing) checks for the literal placeholder `<bundle>/`, which never appears in an Environment B adapted file — Environment B uses the `~` form `~/workspace/egm/...` — so the guard cannot detect a re-run in Environment B.
*   **Rationale:** The core adaptation step is specified as "do it somehow, then verify with C1".
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid on all three points; verified L165 and the r3 E-B guard text. The fix gives all seven literal commands with exclusion guards, orders item 3 before item 2, and fixes the guard to check both the placeholder and the Environment B `~` form. Shared edit E-L (with Issue 18).
*   ***Proposed Edit:***
    *   Location: D3 item 3 (L165) (shared edit E-L parts (2)–(4)).
    *   Change: Apply E-L parts (2)–(4).

### [Issue 27] [implementation_readiness-4-6] - Severity: Major
*   **Affected Scope:** §10.6 C1 (L370)
*   **Discrepancy Description:** Reference-resolution check covers only part of what it asserts. C1's grep regex requires a file extension (`\.[A-Za-z0-9]+`), so it misses extensionless/directory references such as bare `agents/` and `resources/document_standards/`, which the D3 mapping table itself treats as references. The `<skills-dir>` and `<bundle>` placeholders are never bound to a concrete invocation. The two additional assertions in the same check — "assert the Muse routing line is present in each adapted `SKILL.md` and no upstream-relative reference (`../../docs/`, `${CLAUDE_PLUGIN_ROOT}/docs/`) remains" — have no command, pattern, or expected output at all.
*   **Rationale:** Half of C1 is a command with a coverage hole; the other half is an assertion with no procedure.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; verified L370. The fix drops the extension requirement (stripping a trailing prose period before the check), binds the placeholders with the Environment B example, and gives explicit commands for both assertions. Shared edit E-N.
*   ***Proposed Edit:***
    *   Location: §10.6 C1 (L370) (shared edit E-N).
    *   Change: Apply E-N.

### [Issue 28] [implementation_readiness-4-7] - Severity: Major
*   **Affected Scope:** §9.5 step 3 (L298)
*   **Discrepancy Description:** E2E fixture input never materialised; two of three stage pass criteria unverifiable. The prompt text "lives in TESTING.md, not in this document", TESTING.md is explicitly not vendored, and no step creates the `<prompt-file>` that `muse exec --prompt <prompt-file>` requires. The pass criteria name an output file only for brainstorm (`concepts_brief.md`); for draft the criterion is "produces a design document" (no filename or path) and for review "produces a filed review report" (no filename or path).
*   **Rationale:** A test plan must state specific test cases and expected outputs; here the input artifact is never created and two of three expected outputs are unnamed.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid, and the premise is false as well as unexecutable: TESTING.md at the pinned SHA contains no prompt text (verified by fetch), so the prompt must be specified in-doc. The fix writes the prompt to `/tmp/egm-e2e-<shape>/prompt.md` before the run, names the draft output `design_draft.md` (per the bundle's `docs/claude.md`/`docs/muse.md`) and the review output `<date>-muse-wonder-1.0-review.md`. Shared edit E-I (with Issues 7, 29).
*   ***Proposed Edit:***
    *   Location: §9.5 step 3 (L298) (shared edit E-I parts (1)–(3)).
    *   Change: Apply E-I parts (1)–(3).

### [Issue 29] [implementation_readiness-4-8] - Severity: Major
*   **Affected Scope:** §9.5 step 1 (L295–296)
*   **Discrepancy Description:** Offline pre-check fallback is unexecutable in the case it covers. Step 1 says to confirm each of `muse plugins validate`, `muse skills list --source plugin`, `muse exec` exists (`<cmd> --help`); "if any is absent, record it in the pilot log and proceed to the E2E fixture (step 3) as the verification gate". Step 3 itself runs via `muse exec`. If the absent command is `muse exec`, the designated fallback gate cannot run, and no alternative verification is specified. The `<cmd>` placeholder is also never expanded into the concrete list of commands to probe.
*   **Rationale:** A verification procedure whose fallback depends on the very command whose absence triggers it leaves the implementer with no defined path to a pass verdict on that VM shape.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; verified L295–296. The fix expands `<cmd>` into the three concrete commands and defines the no-`exec` gate as the hand-exercised fixture run (which needs no `muse exec`). Shared edit E-I part (4) (with Issues 7, 28).
*   ***Proposed Edit:***
    *   Location: §9.5 step 1 (L295–296) (shared edit E-I part (4)).
    *   Change: Apply E-I part (4).

### [Issue 30] [implementation_readiness-4-9] - Severity: Major
*   **Affected Scope:** D6 (L210)
*   **Discrepancy Description:** Snapshot command unbound, non-hash for repo targets, flags its own outputs. (a) The command takes a single `<dir>`, but the stated scope is four locations; no loop or per-location command is given, and `<dir>` is never bound. (b) For a repo target the prescribed command is `git status --porcelain`, which is not a content hash — it contradicts the section's own "snapshot the working tree by content hash" and has no stated after-command or diff procedure. (c) The scope includes the reports directory (`~/workspace/plans/`), where the round's own review report and pilot log are written, yet "any unexpected modification fails the round" with no exclusion for the round's own outputs — as written, a successful round that files its report would diff as a modification and fail itself. The rollback command is likewise unbound (`cp -r` onto an existing destination nests rather than replaces).
*   **Rationale:** The D6 snapshot is the plan's only enforcement for the principal (read-only) risk; as specified it cannot be run over its stated scope.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid on all four points; verified L210. The fix gives a per-location loop with the content-hash form for every location, drops `git status --porcelain` as a snapshot command, excludes the round's own added files under `~/workspace/plans/`, and binds the rollback command with `rm -rf` before `cp -r`. Shared edit E-O.
*   ***Proposed Edit:***
    *   Location: D6 (L210) (shared edit E-O).
    *   Change: Apply E-O.

### [Issue 31] [implementation_readiness-4-10] - Severity: Major
*   **Affected Scope:** D5 (L203)
*   **Discrepancy Description:** Bundle content review has unenumerated input and no decision criterion. The files are named only by patterns (`agents/openai.yaml`, per-skill `test_scenarios.yaml`, `references/*.json`, `assets/icon.svg`, `docs/assets/*.svg`) — no total count or explicit file list is given, so the implementer cannot confirm the review is complete. "Records a one-line content note per file in the Phase 2 PR body" gives no note template, and no pass/fail criterion is stated. The plan states this review is "the safety control for the bundle" because SHA integrity proves provenance, not safety.
*   **Rationale:** A safety control with an unenumerated input and no blocking criterion leaves the implementer to decide both what to review and what counts as unsafe.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The input is enumerated by counting the bundle at the pin: 23 files (7 `openai.yaml` + 7 `test_scenarios.yaml` + 1 references JSON + 7 `icon.svg` + 1 docs asset SVG); the `references/*.json` pattern matches exactly one file. The fix adds the count, the note template, and a blocking criterion. Shared edit E-P.
*   ***Proposed Edit:***
    *   Location: D5 (L203) (shared edit E-P).
    *   Change: Apply E-P.

### [Issue 32] [implementation_readiness-4-11] - Severity: Major
*   **Affected Scope:** §10.3.1 (L341) and §10.3.5 (L353)
*   **Discrepancy Description:** No literal prompt text exists anywhere. Line 341 says reviewers receive "the persona file path and the verbatim prompt in the brief", and line 353 defines the verbatim prompt only by reference: the Delegation section of `skills/egm-review-loop/SKILL.md` ("## Delegation"; line 34 in the vendored file) "plus the target — i.e. the six brief items". The six items are a contents list, not prompt wording. The implementer must compose the actual brief text — wording, ordering, how the six items are embedded, and how the Delegation section is quoted or paraphrased — and that wording materially affects reviewer behaviour.
*   **Rationale:** Under the zero-decision rule, the instruction an agent is actually spawned with cannot be left to the implementer to draft.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; verified L341 and L353. The fix quotes the Delegation section verbatim (from the vendored file at the pinned SHA) and gives the literal six-item brief template. Shared edit E-D (R-E cluster: Issues 32, 40).
*   ***Proposed Edit:***
    *   Location: §10.3.5 (L353) (shared edit E-D).
    *   Change: Apply E-D.

### [Issue 33] [implementation_readiness-4-12] - Severity: Major
*   **Affected Scope:** §11.3 (L402), §11.1 (L406), §11.2 (L410), §11 table (L385)
*   **Discrepancy Description:** Filenames missing/inconsistent; allowlist deferred to a generated file. (a) The Phase 0 list (L406) names its outputs only as "pilot report + pilot log under `~/workspace/plans/`" — no filenames. The pilot log pattern is given only in D5 (L203); the pilot *report* filename is never given anywhere. (b) The drift report filename is inconsistent: the §11 table (L385) files it at `~/workspace/plans/<date>-skills-attribution-drift.md`, while §11.2 (L410) files it at `~/workspace/plans/<date>-<topic>-drift.md` — two different patterns for the same Phase 1 artifact, with `<date>` and `<topic>` unbound in both. (c) The "exact path list (allowlist)" (L402) defers the 90 bundle paths to `.github/vendor-elephant-goldfish-model.sha256`, a file generated *by* the D4 command during execution — so the allowlist does not exist in the plan before execution.
*   **Rationale:** A file-change list that does not name its files, and an allowlist that does not exist before execution, cannot be enforced from the plan alone.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid on (a) and (b); verified L385, L406, L410. On (c) the fix is honest rather than enumerative: the allowlist *is* the generated `.sha256` file (itself a Created file in the same PR), and the pre-execution statement of its contents is the 90-path inventory in §11.3 (38 + 10 + 7 + 33 + LICENSE + plugin.json) enforced by the `vendor-integrity` job — enumerating all 90 paths inline in the doc would duplicate the generated file and drift from it. Shared edit E-R (with Issue 24).
*   ***Proposed Edit:***
    *   Location: §11.1 (L406); §11.2 (L410); §11.3 (L402) (shared edit E-R parts (1), (3), (4)).
    *   Change: Apply E-R parts (1), (3), (4).

### [Issue 34] [implementation_readiness-4-13] - Severity: Major
*   **Affected Scope:** §10.4 (L357)
*   **Discrepancy Description:** Phase 1 has no numeric token budget and does not wait for the ruling that would set it. Line 357 states the pilot log's token actuals "set the Phase 1 token budget via §14 decision 6", and in the same paragraph that "Phase 1 does not wait on" decision 6. So Phase 1 is instructed to proceed without the budget that is supposed to bound it, and no interim number, cap, or formula is given for the period before the ruling.
*   **Rationale:** A cost bound that exists only as a future decision, combined with an instruction not to wait for it, leaves the implementer to run Phase 1 with no enforceable token limit.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; verified L357. The fix deletes the "does not wait" clause and makes Phase 1 start conditional on the decision-6 ruling. Shared edit E-H (R-I cluster: Issues 2, 34, 55).
*   ***Proposed Edit:***
    *   Location: §10.4 (L357); §14 decision 6 (L437) (shared edit E-H parts (2)–(3)).
    *   Change: Apply E-H parts (2)–(3).

### [Issue 37] [comprehension-4-1] - Severity: Major
*   **Affected Scope:** §10.3 (L339–342)
*   **Discrepancy Description:** §10.3.2 is missing: the subsections run `10.3.1 Reviewer brief` (line 339) then `10.3.3 Readiness and section-approval gates` (line 342), with no `10.3.2` anywhere in the document. A fresh reader cannot tell whether a whole subsection was deleted, renumbered incorrectly, or never written.
*   **Rationale:** Numbering gaps in a procedure the reader must execute undermine trust in every other cross-reference.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; same defect as Issue 14. Shared edit E-A (R-A cluster).
*   ***Proposed Edit:***
    *   Location: §10.3 headings (L342, L347, L351) (shared edit E-A).
    *   Change: Apply E-A.

### [Issue 38] [comprehension-4-2] - Severity: Major
*   **Affected Scope:** §11 Rollout (L396, L404, L408)
*   **Discrepancy Description:** Phase subsections are out of order: `11.3 Phase 2 file-change list` (line 396) appears before `11.1 Phase 0 file-change list` (line 404) and `11.2 Phase 1 file-change list` (line 408). A reader proceeding sequentially meets Phase 2 first, and §11.1 itself refers back to §11.3 for the bundle definition.
*   **Rationale:** The rollout narrative is chronological (Phase 0 → 1 → 2), but the file-change lists are presented in reverse order with no explanation; a fresh reader cannot tell at first reading whether Phase 2 is a prerequisite for Phase 0 or the ordering is an error.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; same defect as Issue 15. Shared edit E-B (R-B cluster).
*   ***Proposed Edit:***
    *   Location: §11 (L396–411) (shared edit E-B part (1)).
    *   Change: Apply E-B part (1).

### [Issue 39] [comprehension-4-3] - Severity: Major
*   **Affected Scope:** D6 (L207–211) vs §10.3.1 (L341)
*   **Discrepancy Description:** "two checks" vs "three checks" contradiction. D6 states "'Verify outputs' means the two checks in D6 (the snapshot diff and the line-existence check), nothing else." §10.3.1 states the independent verification subagent "performs three checks": (a) cited lines exist, (b) named standard is the assigned one, (c) no finding's rationale cites memory or conversation content — and then, in the same paragraph, says §10.5 step 3's questions "are answered by those two checks, not by additional checks." Three different counts (two, three, then two again) for the same verification, with no reconciliation.
*   **Rationale:** A fresh reader cannot paraphrase how many checks exist, which checks the driver vs the independent subagent performs, or whether check (c) is part of "verify outputs" or a separate control. Comprehension blocker for the core safety mechanism.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; verified L210 and L341. The fix reconciles the counts (D6's pair is snapshot diff + line-existence; §10.3.1's three are line-existence + standard-name + memory-prohibition, with line-existence shared) and gives each check exactly one owner. Shared edit E-C (R-D cluster).
*   ***Proposed Edit:***
    *   Location: D6 (L210); §10.3.1 (L341); §10.5 step 3 (L363) (shared edit E-C).
    *   Change: Apply E-C.

### [Issue 40] [comprehension-4-4] - Severity: Major
*   **Affected Scope:** §10.3.5 (L353) and §10.3.1 (L341)
*   **Discrepancy Description:** The "verbatim prompt" is not given verbatim. §10.3.5 defines it as "the review instruction formed from the Delegation section of the bundle's `skills/egm-review-loop/SKILL.md` ('## Delegation'; line 34 in the vendored file at the pinned SHA) plus the target — i.e. the six brief items listed in the preceding paragraph." The six items are a list of *inputs*, not prompt wording. A fresh reader who has not read the vendored file (it is not in GoldfishContext) cannot reconstruct the actual prompt text to spawn a reviewer, and cannot tell whether "verbatim" means a literal string to copy or a paraphrase assembled from the six items.
*   **Rationale:** The definition is circular: the prompt is defined by reference to a brief whose contents are defined by reference to the prompt.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; same defect as Issue 32. Shared edit E-D (R-E cluster).
*   ***Proposed Edit:***
    *   Location: §10.3.5 (L353) (shared edit E-D).
    *   Change: Apply E-D.

### [Issue 41] [comprehension-4-5] - Severity: Major
*   **Affected Scope:** §4 (L56), §10.3.5 (L353), §10.4 (L357)
*   **Discrepancy Description:** "flat FindingsList" and "resolve report" are never defined. §4 and §10.3.5 say the Elephant "consolidates into a flat FindingsList with stable ids (`<reviewer>-<round>-<n>`) and writes the report artifact before any resolution." §10.4 says dispositions are "recorded by the Elephant in the resolve report." Neither artifact's format, fields, file name, or location is specified anywhere — unlike the review report and pilot log, which are given dated paths under `~/workspace/plans/`.
*   **Rationale:** Consolidation, severity-change recording, and disposition tracking all happen in these two artifacts; their undefined shape leaves the loop's central bookkeeping unimplementable from this document alone.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; verified L56, L353, L357. The fix defines the FindingsList fields and identifies the artifacts with the pilot's existing dated filenames (the review report *is* the FindingsList; the resolve report records dispositions). Shared edit E-J (R-K cluster: Issues 8, 10, 41).
*   ***Proposed Edit:***
    *   Location: §4 (L56); §10.3.5 (L353) (shared edit E-J).
    *   Change: Apply E-J.

### [Issue 42] [comprehension-4-6] - Severity: Major
*   **Affected Scope:** §10.2 (L326)
*   **Discrepancy Description:** "live" is never defined. §10.2 states "the local adapted skills are canonical for wrapper content — sync runs live→repo" and then gives "Sync steps (live→repo direction only)." The word "live" appears here with no prior definition; the surrounding text uses "local" (`~/workspace/custom-skills/egm-*/`) and "repo" (`skills/egm-*/`).
*   **Rationale:** "Live" could equally mean a running harness, a deployed skill set, or the current VM. The canonical-direction rule is the mechanism that prevents dual-install drift (§6, L90), so an ambiguous direction label leaves the reader unsure which tree overwrites which.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; verified L326. The fix defines "live" as the local tree at first use and replaces the label with "local→repo". Shared edit E-S part (1).
*   ***Proposed Edit:***
    *   Location: §10.2 (L326) (shared edit E-S part (1)).
    *   Change: Apply E-S part (1).

### [Issue 43] [comprehension-4-7] - Severity: Major
*   **Affected Scope:** D1 (L131–136)
*   **Discrepancy Description:** "sync record" is never defined. D1 says "if upstream HEAD is more than 90 days newer than the pin, the sync record notes the pin as stale and the owner rules on re-vendor." No "sync record" artifact is defined anywhere else: its file, format, location, and author are unspecified, and it is distinct from the pilot log, the PROVENANCE.md, and the bundle README, all of which are defined.
*   **Rationale:** A fresh reader cannot tell where the staleness note is written, who writes it, or how the owner would find it to rule on it. The staleness rule is therefore unenforceable from this document.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; verified L131–136 (and C6's "recorded in the sync record", L375, which has the same gap). The fix defines the sync record as the pilot-log entry (local) or the sync PR body (repo), consistent with D5's "install notes" definition. Shared edit E-S part (2).
*   ***Proposed Edit:***
    *   Location: §10.2 (L326) (shared edit E-S part (2)).
    *   Change: Apply E-S part (2).

### [Issue 44] [comprehension-4-8] - Severity: Major
*   **Affected Scope:** §6 (L91)
*   **Discrepancy Description:** "Upstream's optional A/B duplication (two instances per reviewer)" is unexplained. No upstream location, link, or rationale is given for what A/B duplication is, what the two instances are compared on, or why duplicating reviewers would ever be desirable.
*   **Rationale:** A fresh reader cannot evaluate the cost/benefit of rejecting this option — whether it is a reliability measure, an experiment, or a quality check — and therefore cannot tell whether "NOT used" is a cost saving or a quality concession.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The upstream location exists and was verified: bundle `docs/designs/synthesizer.md`, Mode REVIEW, "Redundant Subagent Spawning (A/B Sampling)" — two independent instances of each reviewer to maximize finding recall and eliminate non-deterministic evaluation gaps. The fix cites it. Shared edit E-S part (3).
*   ***Proposed Edit:***
    *   Location: §6 (L91) (shared edit E-S part (3)).
    *   Change: Apply E-S part (3).

### [Issue 45] [comprehension-4-9] - Severity: Major
*   **Affected Scope:** §7 (L104–106) vs D7 (L212–219)
*   **Discrepancy Description:** The `egm-*` prefix names two different sets. §7 lists 10 personas, of which the 5 non-loop ones are named `egm-style`, `egm-codebase-details`, `egm-inventive-catalyst`, `egm-synthesizer`, `egm-bootstrap-orchestrator`. D7 maps named agents to persona files using a different `egm-*` scheme: `egm-design` → `agents/design_critic.md`, `egm-comprehension` → `agents/comprehension.md`, `egm-structural` → `agents/structural.md`, etc. The same `egm-` prefix is also used for the 7 skills (`egm-review`, `egm-draft`, …).
*   **Rationale:** A fresh reader cannot tell whether `egm-style` (§7) and `egm-design` (D7) are the same kind of thing, whether the D7 names are harness agent definitions and the §7 names are something else, or how to map one list onto the other. Three overlapping `egm-*` namespaces with no disambiguation table makes every `egm-*` reference in §§9–10 ambiguous on first reading.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid in substance, with a correction: the two lists are the *same* namespace, not two different schemes — verified against the bundle, all 10 `agents/*.md` frontmatter `name` values are `egm-*`, and §7 names the five non-loop ones while D7 names the five loop ones. What is missing is the statement that they are one namespace (named agent definitions, one per persona file) plus the disambiguation against the skill namespace. Shared edit E-S part (4).
*   ***Proposed Edit:***
    *   Location: §7 (L104–106) (shared edit E-S part (4)).
    *   Change: Apply E-S part (4).

### [Issue 46] [comprehension-4-10] - Severity: Major
*   **Affected Scope:** §10.4 (L357)
*   **Discrepancy Description:** "churn" and "substantially restate" are unquantified, and SETTLED is circular. §10.4 defines churn as "a new finding at the scope of an applied fix whose revert would resolve it, or a round whose unsettled findings substantially restate the previous round's fixed findings," with "Threshold: the first occurrence." "Substantially restate" has no test (same lines? same discrepancy? same scope?). SETTLED is defined as "a re-raise of a finding already recorded with one of the above dispositions at the same scope, not re-opened" — i.e. a finding is settled if it was already dispositioned, which restates the definition of a disposition rather than giving a criterion for recognising a re-raise.
*   **Rationale:** The driver must stop and ask the owner on churn, and a round is clean only when no Blocker/Major is "unsettled" — but a fresh reader (or driver) cannot determine from the text when churn has occurred or when a restated finding counts as a new finding vs a settled re-raise. The loop's termination condition rests on a judgment call the document does not operationalise.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; verified L357. The fix operationalises both tests with the document's own dedup key — same target lines and same discrepancy (the merge rule already in §10.3). Shared edit E-S part (5).
*   ***Proposed Edit:***
    *   Location: §10.4 (L357) (shared edit E-S part (5)).
    *   Change: Apply E-S part (5).

### [Issue 49] [zoom_out-4-1] - Severity: Major
*   **Affected Scope:** §3 (L42), §5 (L82), §1 (L24)
*   **Discrepancy Description:** Full-scope adoption for an explicitly unmeasured problem. The document concedes it has no evidence of the problem's scale (§3 L42) and concedes the pilot does not establish marginal value (§5 L82), yet §1 L24 presents the same pilot as "the marginal value", and the document proceeds to specify the full end state now: a 90-file bundle, 7 skills, 10 personas, 2 CI gates, and dual-environment installation. The precautionary-experiment framing and the §11 kill criterion bound *execution*, not *specification*: the full 7-skill end state is designed before the §14 decision 5 pilot-value ruling that gates it. The minimal design specifies only the pilot (Phase 0) and defers the rest until the ruling exists.
*   **Rationale:** Per standard §1, the design must solve the underlying problem, not proceed on an unproven one.
*   ***AI Suggestion:*** CONTEST
*   ***Justification:*** The finding mistakes specification for execution, and the document already binds execution to the ruling with checkable evidence: §11's Phase 2 gate is "only after the §14 decision 5 pilot-value ruling" (L385–387), §5 states "Without that ruling, Phase 2 installs the 2 review skills only" (L76–77), and §11's rollback is the kill criterion for a negative ruling. Specifying the end state before the ruling is the design document's purpose — the ruling judges the specified end state; a document that specified only Phase 0 would give the owner nothing to rule *on* for Phases 1–2. The §1 L24 wording ("That is the marginal value") is loose, but the operative gates are as stated, so the design-before-ruling complaint does not stand. No fix proposed. (The §1 wording and the decision-5 criterion itself are addressed by Issues 3 and 4 / shared edit E-K, which strengthen what the ruling must record.)
*   ***Proposed Edit:***
    *   Location: None.
    *   Change: None.

### [Issue 50] [zoom_out-4-2] - Severity: Major
*   **Affected Scope:** §5 (L67, L82), §2 (L37)
*   **Discrepancy Description:** YAGNI — the genuinely new delta is five standards files, but the adoption vendors 90. §5 L82 names the genuinely new delta: "the five written standards, the gate-scan / vendor-integrity / skills-freshness gates, and the drift-report/bootstrap skills." The alternatives section evaluates only two poles — extend the incumbents (rejected as "writing a new standard set, a panel configuration, and a report/resolve loop," L67) versus vendoring all of EGM — and never evaluates the middle option: point the existing `roundtable_review` panel (which already has per-run reviewers, debate, a judge, and claim verification) at the five upstream standards files, keeping the incumbent machinery.
*   **Rationale:** Per standard §4, reuse existing components instead of reinventing them. The standards are the load-bearing innovation; the 7 skills, 10 personas, and 2 CI gates are packaging around them.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid — the middle option was never evaluated (the r3-evaluated docs subset, §5 L76, is a different option: vendoring fewer files, not keeping the incumbent machinery). The fix evaluates it on a concrete technical ground: the five standards are written as inputs to `egm-review`'s five-stage procedure, and `roundtable_review`'s debate-and-judge format does not consume them, so the standards-only route still requires writing the panel configuration, report/resolve loop, and a standards-to-debate mapping. Shared edit E-K part (4) (with Issues 3, 4).
*   ***Proposed Edit:***
    *   Location: §5 (after the do-nothing bullet, L67) (shared edit E-K part (4)).
    *   Change: Apply E-K part (4).

### [Issue 51] [zoom_out-4-3] - Severity: Major
*   **Affected Scope:** §11 (L402–403), §5 (L72, L76)
*   **Discrepancy Description:** YAGNI — the two-skill variant still vendors all 90 files. The two-skill variant (no §14 decision 5 ruling) lands "the bundle… unchanged (D2: the bundle moves as one unit)" — all 90 files — while only 2 skills are adapted. Files no pilot skill can reference at runtime (`TEST.md`, `test_scenarios.yaml`, `assets/icon.svg`, `docs/designs/`, `agents/openai.yaml`) ride along. The justification (§5 L72, L76) is that "maintaining a subset file list is its own drift risk." That justification is speculative, while the cost of the full bundle is concrete: D5 L203 requires the vendor to read each non-markdown file and record a one-line content note per file in the PR body, and the 90-path vendor-integrity surface must be maintained on every sync.
*   **Rationale:** A static keep-list is a one-time cost; the full bundle taxes every vendor and sync. Even accepting the D2 unit rule for the full adoption, the *pilot* variant — the state that exists before any value ruling — should carry only the 2 skills' runtime dependencies.
*   ***AI Suggestion:*** SETTLED
*   ***Justification:*** Settled — same scope and issue as round-2 Issue 8 (`design_critic-2-8`, minimal-subset vendoring), dispositioned PROPOSE FIX and applied as the §5 minimal-subset bullet (L72: "the full 90-file bundle is vendored while only 2 skills are adapted in the pilot", D2 unit rule) and the round-3 docs-subset bullet (L76, same non-runtime files listed). The two-skill variant *is* that pilot state. Per §10.4, SETTLED is "a re-raise of a finding already recorded with one of the above dispositions at the same scope, not re-opened". The "static keep-list is a one-time cost" argument was already weighed in those dispositions (subset-list drift risk). No fix proposed; recorded here only. (Citation note: the finding cites "§11 (L400)"; the two-skill variant text is at L402–403.)
*   ***Proposed Edit:***
    *   Location: None.
    *   Change: None. Matches round-2 disposition: PROPOSE FIX, applied at §5 L72/L76.

### [Issue 52] [zoom_out-4-4] - Severity: Major
*   **Affected Scope:** D4 (L189), §10.2 (L326), §10.5 (L364)
*   **Discrepancy Description:** The layout creates the drift it then builds sync machinery to manage. D4 L189 admits the wrapper→bundle coupling "is a new pattern in this repo" and that "the two-tree drift the coupling creates is managed by the §10.2 canonical direction (per artifact) and the §10.5 step 4 sync check." §10.2 L326 then defines *two opposite* canonical directions in a single sync (wrappers live→repo; bundle upstream→repo→local), plus a normalize-then-diff check with `sed` normalization, per-sync YAML re-validation, and C2 resolve loops. Per standard §2 (minimalist data flow) and §4 (pattern consistency), a design should not manufacture its own drift surface and then build three mechanisms to contain it. Two canonical directions in one sync is itself a hazard — a sync run in the wrong direction silently overwrites the other tree's canonical content. Two simpler options exist: a single canonical direction (the repo is canonical for everything; local is a checkout), or a single-tree layout. Further, the "new pattern" framing overstates novelty: the reviewer verified in the repo that `skills/craft-anything-protocol/SKILL.md:74` already references a vendored `reference/craft-anything/` tree under the sha256 vendor-integrity regime with a `PROVENANCE.md` — an established precedent for skills referencing `reference/` trees, with no bidirectional canonical-direction discipline.
*   **Rationale:** The doc should evaluate the EGM coupling against that existing pattern instead of inventing a new sync discipline.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid on the verified point and on the unevaluated option. The `craft-anything-protocol` precedent checks out (verified: `skills/craft-anything-protocol/SKILL.md` "Pinned reference" cites `reference/craft-anything/` @ `2e4afc5`, vendored under the sha256 vendor-integrity regime with a `PROVENANCE.md`; the `vendor-integrity` job has a `reference/craft-anything` block). The fix corrects the "new pattern" claim and evaluates the single-canonical-direction alternative on a technical ground: local pilot edits originate locally (and must be testable before any repo PR), while the bundle originates upstream via the repo — a single repo-canonical direction would force pilot edits through the repo PR flow before they can be tested locally, which is why the per-artifact directions are retained. The single-tree layout is already rejected in §5 (adapted skills inside the bundle tree break the pristine/verbatim rule).
*   ***Proposed Edit:***
    *   Location: D4 (L189); §5 (new bullet after the D4-alternatives bullet).
    *   Change: In D4, replace "This wrapper→bundle coupling is a new pattern in this repo — no existing skill references a `reference/<tree>/` path." with "This wrapper→bundle coupling follows the existing `skills/craft-anything-protocol/` → `reference/craft-anything/` precedent (a skill referencing a vendored `reference/` tree under the sha256 vendor-integrity regime with a `PROVENANCE.md`); what is new is only the two-direction sync discipline for it, evaluated in §5." In §5, append: "- Single canonical direction (the repo is canonical for everything; local is a checkout) instead of per-artifact directions — rejected: local pilot edits originate locally and must be testable before any repo PR, while the bundle originates upstream via the repo; a single repo-canonical direction would force pilot edits through the repo PR flow before they can be tested locally. The per-artifact directions (§10.2) follow the origin of each artifact. A sync run in the wrong direction is prevented by the §10.5 step 4 check, which fails (non-zero diff) rather than overwriting when the trees do not match after normalization."

### [Issue 53] [zoom_out-4-5] - Severity: Major
*   **Affected Scope:** D6 (L210), §12 (L419–424)
*   **Discrepancy Description:** Workaround vs structural fix — post-hoc detection instead of removing write access. The read-only caveat is handled entirely by detection after the fact: snapshot before dispatch, diff after the round, fail the round, discard its findings, restore the tree, re-vendor, record the incident, attribute to the round not the reviewer (D6 L210; §12 L419–420). §12 L424 concedes the residual: "a reviewer write is detected only after it happens (D6); detection does not prevent the write, and memory/DB paths are not snapshotted." Per standard §3, prefer a structural fix over a complex local workaround. The root cause is that reviewers run with write access to the live tree (and, per the companion NeuroStrata doc, a live daemon and database). The structural fix is isolation before the fact — run reviewers against a disposable copy of the target document (and bundle), so a write is impossible rather than detected-after-the-fact.
*   **Rationale:** The current design pays for an elaborate detect-discard-restore apparatus and still leaves the memory/DB exposure entirely unaddressed, which no amount of snapshot-diff tuning can close.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid in its actionable part. The disposable-copy structural fix is adopted for the target document (the one artifact whose corruption matters most and whose copy maps 1:1 by line number) — but a copy of the target alone does not isolate the run, because reviewers still receive absolute paths to the persona, standards, and GoldfishContext files and could write there; full isolation is unavailable on Muse (no tool-restriction mechanism, D6). The fix therefore adopts the copy, fixes the rollback for untracked files, and states the memory/DB unrecoverability explicitly, rather than claiming containment it cannot deliver. Shared edit E-G (with Issue 1).
*   ***Proposed Edit:***
    *   Location: §6 D6 bullet; D6 (L210); §12 (L424) (shared edit E-G).
    *   Change: Apply E-G.

### [Issue 54] [zoom_out-4-6] - Severity: Major
*   **Affected Scope:** §10.3.1 (L341), §10.3 (L336), §10.5 (L363)
*   **Discrepancy Description:** Duplicated verification layer — two components perform the same two checks. The Driver already performs the line-existence check and the standard-name check (§10.3 L336; §10.3.1 L341). §10.5 step 3 (L363) then adds an independent verification subagent that re-performs the *same two checks* — (a) every cited line exists, (b) the named standard is the assigned one — plus (c) a memory-prohibition check. Per standard §2, data should pass through the minimal number of components. Two agents doing the same two checks is redundant flow; the only new work is check (c), which requires a subagent to judge whether a finding's rationale is "a paraphrase that depends on" prior context — an inherently subjective judgment that cannot be reliably automated — yet a flagged finding is discarded and the reviewer is not re-dispatched.
*   **Rationale:** Do not run a whole extra agent per round to redo checks the Driver already ran; fold (c) into the Driver's consolidation pass, or drop the second subagent and keep the Driver's checks plus the brief prohibition.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; verified L336, L341, L363. The fix gives each check exactly one owner — driver does (a),(b) at intake, the Elephant does (c) at consolidation (it holds the conversation context, so the paraphrase judgment is placed where the context lives) — and re-scopes the §10.5 step 3 independent subagent to the one job no other component can do itself: auditing the Elephant's severity-change records against the filed reports. Shared edit E-C (with Issues 19, 39, and Issue 8's audit half).
*   ***Proposed Edit:***
    *   Location: §10.3.1 (L341); §10.5 step 3 (L363) (shared edit E-C parts (2)–(3)).
    *   Change: Apply E-C parts (2)–(3).

### [Issue 55] [zoom_out-4-7] - Severity: Major
*   **Affected Scope:** §10.4 (L357), §6 (L91)
*   **Discrepancy Description:** Unbounded cost — the pilot that measures cost runs without a token ceiling. §10.4 L357 sets the 30-minute per-reviewer timeout as an interim bound while conceding "no pilot log with per-reviewer elapsed times exists yet, so this bound is set now." §6 L91 sets an "interim budget 12.5 reviewer-hours per run" and defers the token budget: "the pilot log's token actuals set the Phase 1 token budget via §14 decision 6." Loop cost is named as a risk in §6, but the primary cost (tokens) is unbounded at adoption time. The §14 decision 5 pilot-value ruling is supposed to be a *value* judgment, which requires both sides of the ledger — yet the pilot that generates the cost evidence runs with no token cap, so the experiment's own cost is uncapped.
*   **Rationale:** A design whose main risk is loop cost should carry a closed cost envelope (a token ceiling, even a generous interim one) before the pilot runs, not invent a time bound from no data and defer the token budget to a decision made after the spend.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. No token number is invented here — the number is the owner's decision-6 ruling, which is the doc's existing mechanism for it. What the fix closes is the *gate*: Phase 1 does not start until decision 6 sets the per-reviewer and per-run token maxima from the pilot log's actuals, so no post-pilot run proceeds uncapped; the pilot itself (already 4 rounds in) is bounded by the 25-spawn / 30-minute envelope and its actuals are what set the Phase 1 budget. Shared edit E-H (R-I cluster: Issues 2, 34, 55).
*   ***Proposed Edit:***
    *   Location: §6 (L91); §10.4 (L357); §14 decision 6 (L437) (shared edit E-H).
    *   Change: Apply E-H.

### Nits

### [Issue 12] [design_critic-4-12] - Severity: Nit
*   **Affected Scope:** §10.3 (L339, L342), §11 (L396, L404, L408), §13 (L426–427)
*   **Discrepancy Description:** Numbering and section-order defects. §10.3 jumps from "#### 10.3.1 Reviewer brief" (line 339) to "#### 10.3.3 Readiness and section-approval gates" (line 342) — no 10.3.2, no note explaining the gap. §11 presents "### 11.3 Phase 2 file-change list" (line 396) before "### 11.1 Phase 0" (line 404) and "### 11.2 Phase 1" (line 408). §13 is an empty pointer: "Non-goals are stated with the goals in §2."
*   **Rationale:** In a document whose own loop checks line numbers and section names, misnumbered sections and out-of-order subsections invite mis-citation.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid for the numbering and ordering legs (R-A, R-B); the §13 leg is declined inside this fix — deleting §13 would force a §14→§13 renumber with a cross-reference cascade across §§2, 5, 10.4, 11, and 14, for a one-line pointer that is the r3-agreed fix for the split-goals problem (r3 Issue 18). Shared edits E-A and E-B; no §13 change.
*   ***Proposed Edit:***
    *   Location: §10.3 headings (L342, L347, L351); §11 (L396–411) (shared edits E-A, E-B).
    *   Change: Apply E-A and E-B part (1). §13 unchanged (see Issue 21).

### [Issue 13] [design_critic-4-13] - Severity: Nit
*   **Affected Scope:** §9.1 (L230), §9.5 step 2 (L297)
*   **Discrepancy Description:** `pytest` installed unpinned by a method that may fail: "`python3 -m pip install pytest` on the fresh VM (`pytest` is absent on this VM — record the installed version in the pilot log)." No version pin, no virtualenv, and no handling for PEP 668 externally-managed environments (where bare `pip install` refuses) or for a system without pip. The installed version is recorded only after the fact, in the pilot log, so two fresh-VM runs are not reproducible from the spec.
*   **Rationale:** Two fresh-VM runs are not reproducible from the spec as written.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; worth fixing because the pin + venv also carries the PyYAML prerequisite for C3/C6. Shared edit E-F (R-G cluster: Issues 13, 36).
*   ***Proposed Edit:***
    *   Location: §9.1 (L230) (shared edit E-F).
    *   Change: Apply E-F.

### [Issue 20] [structural-4-7] - Severity: Nit
*   **Affected Scope:** Required sections in reverse order (§2 Goals before §3 Problem) (§§2–3, L26, L40)
*   **Discrepancy Description:** The document places `## 2. Goals & Non-goals` (line 26) before `## 3. Problem Statement` (line 40), reversing the order in which the standard lists its required areas (Problem Statement, then Goals & Non-Goals, then Proposed Architecture, Alternatives Considered, Risks & Mitigations). All five areas are present and correctly headed; only the first two are swapped.
*   **Rationale:** Template compliance includes section order, and the standard's order (problem first, goals as the response to it) is the logical reading order. Low impact since both sections exist and are findable — fixed by swapping §§2 and 3 (and renumbering the §2/§3 cross-references).
*   ***AI Suggestion:*** DECLINE
*   ***Justification:*** Cosmetic. Swapping §§2 and 3 forces a full renumber of every §2/§3 cross-reference in the document (§13's pointer, §3 references in §§1, 4, and 11, §2 references in §§5, 11, and 14) for a Nit whose sections both exist, are correctly headed, and are findable; the r1 restructure deliberately placed Goals first (r1 Issues 12–13). Record only.
*   ***Proposed Edit:***
    *   Location: None.
    *   Change: None.

### [Issue 21] [structural-4-8] - Severity: Nit
*   **Affected Scope:** §13 is a content-free pointer section duplicating §2 (§13, L426–428)
*   **Discrepancy Description:** `## 13. Non-goals` (line 426) contains a single sentence: "Non-goals are stated with the goals in §2." (line 428). It carries no content of its own, and its subject is already covered by the "Non-goals:" list inside §2 (lines 34–38). A heading that exists only to point at another section is structural dead weight.
*   **Rationale:** It inflates the table of contents, splits the Goals & Non-goals area across two sections, and gives a heading-navigating reader an empty stop. Delete the §13 heading or move the non-goals list into §13.
*   ***AI Suggestion:*** DECLINE
*   ***Justification:*** Cosmetic, and the cure is worse than the defect. Deleting §13 forces §14→§13 renumbering plus a cascade across every §14 decision citation (§§2, 5, 10.4, 11, 14); moving the non-goals list into §13 re-splits the Goals & Non-goals area that r3 Issue 18 deliberately merged into §2 (renaming `## 2. Goals` to `## 2. Goals & Non-goals` and turning §13 into the pointer). The one-line pointer costs nothing and preserves the numbering. Record only.
*   ***Proposed Edit:***
    *   Location: None.
    *   Change: None.

### [Issue 35] [implementation_readiness-4-14] - Severity: Nit
*   **Affected Scope:** §10.3 headings (L339–353) and §11 headings (L396–408)
*   **Discrepancy Description:** Numbering gaps and out-of-order phase lists. §10.3 jumps from 10.3.1 (line 339) to 10.3.3 (line 342) — no 10.3.2, and no cross-reference explains the gap. §11 presents the file-change lists out of order: 11.3 Phase 2 (line 396) before 11.1 Phase 0 (line 404) and 11.2 Phase 1 (line 408), while the rollout table itself lists phases 0–3 in order (lines 384–387).
*   **Rationale:** Numbering gaps and out-of-order phase lists do not block execution on their own, but they create ambiguity about whether content is missing and which list applies to which phase.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; worth fixing because the ambiguity is about whether content is missing (R-A) and which list applies to which phase (R-B). Shared edits E-A and E-B.
*   ***Proposed Edit:***
    *   Location: §10.3 headings; §11 (L396–411) (shared edits E-A, E-B).
    *   Change: Apply E-A and E-B part (1).

### [Issue 36] [implementation_readiness-4-15] - Severity: Nit
*   **Affected Scope:** §9.1 (L230) with C3 (L372)
*   **Discrepancy Description:** `pytest` unpinned; PyYAML never listed as a prerequisite. `pytest` is to be installed with bare `python3 -m pip install pytest` — no version pin, no virtualenv/`--user`/system-package handling, and no step verifying `pip` exists on the fresh VM (where `pip` may be absent or externally-managed-environment blocked). Separately, C3's procedure requires the `yaml` module (`import yaml`, line 372), but PyYAML is never listed as a prerequisite in §9.1 or anywhere else.
*   **Rationale:** Both are small install-method decisions left to the implementer; individually minor, but each can cause a first-attempt failure of a step the plan presents as mechanical.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; same defect as Issue 13 plus the PyYAML prerequisite gap (shared with Issue 6). Shared edit E-F (R-G cluster).
*   ***Proposed Edit:***
    *   Location: §9.1 (L230) (shared edit E-F).
    *   Change: Apply E-F.

### [Issue 47] [comprehension-4-11] - Severity: Nit
*   **Affected Scope:** D4 (L171–183)
*   **Discrepancy Description:** "esf" and the "humanizer block" are unexplained anchors. D4 uses `reference/esf/` as the pattern exemplar for PROVENANCE.md and instructs inserting the tenth `run:` block "after the `humanizer` block" in `.github/workflows/ci.yml`. Neither "esf" (what it is, what the acronym means) nor "humanizer" (a skill? a CI job? a block name?) is defined in the document or in GoldfishContext.
*   **Rationale:** The instruction is executable only if the reader already knows the repo's `reference/` trees and `ci.yml` layout; a one-line gloss for each would make D4 self-contained.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; worth one line each. Verified: `reference/esf/` is the ESF reference implementation for the AEP factory lane (vendored from `pratik-saptarshi/esf`); the `humanizer` block is the `vendor-integrity` `run:` block for the existing `reference/humanizer/` tree (`.github/workflows/ci.yml:120`). Shared edit E-T part (1).
*   ***Proposed Edit:***
    *   Location: D4 (L171–183) (shared edit E-T part (1)).
    *   Change: Apply E-T part (1).

### [Issue 48] [comprehension-4-12] - Severity: Nit
*   **Affected Scope:** §5 (L66)
*   **Discrepancy Description:** "the scope file" is used before it is introduced. §5 rejects shared `skills/egm-agents/` + `skills/egm-resources/` dirs because they "stretch the scope file's semantics ('in-scope skill directory names')." The scope file is not named until §11.3, line 398 (`.github/skills-sync-scope.txt`, 7 lines under `[skills]`).
*   **Rationale:** The term is defined later in the document, so this is a forward-reference rather than a true gap — but a reader at §5 cannot resolve which file is meant or verify the semantics claim without jumping ahead to §11.3.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; one-word fix, clearly worth it. Shared edit E-T part (2).
*   ***Proposed Edit:***
    *   Location: §5 (L66) (shared edit E-T part (2)).
    *   Change: Apply E-T part (2).

### [Issue 56] [zoom_out-4-8] - Severity: Nit
*   **Affected Scope:** §10.3.4 (L349), §5 (L77), §2 (L37)
*   **Discrepancy Description:** No selection rule among four overlapping review instruments. After adoption the catalog holds `grilling`, `roundtable_review`, the Ralph verifier, `brainstorming`, `writing-plans`, plus 7 EGM skills; §5 L77 acknowledges `egm-brainstorm` overlaps `brainstorming` and `egm-draft` overlaps `writing-plans`. The only selection guidance is §10.3.4 L349: "Use EGM where a written standard and a configured panel add value." That is a heuristic, not a decision rule — every design review now requires a meta-decision about which of four review instruments to use, with no criterion for choosing.
*   **Rationale:** A one-paragraph selection rule would prevent the heavier instrument from being reached for by default or never reached for at all. Nit because the doc does acknowledge the overlap and defers 5 skills; the gap is the missing rule, not a structural flaw.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; worth one paragraph. Shared edit E-T part (3).
*   ***Proposed Edit:***
    *   Location: §10.3.4 (L349) (shared edit E-T part (3)).
    *   Change: Apply E-T part (3).

## Counts check

56 findings = **52 PROPOSE FIX + 1 CONTEST + 0 new ESCALATE + 2 DECLINE + 1 SETTLED.**

- Blockers (3): Issues 1, 22, 26 — all PROPOSE FIX.
- Majors (44): Issues 2–11, 14–19, 23–25, 27–34, 37–46, 49–55 — 42 PROPOSE FIX + 1 CONTEST (49) + 1 SETTLED (51).
- Nits (9): Issues 12, 13, 20, 21, 35, 36, 47, 48, 56 — 7 PROPOSE FIX + 2 DECLINE (20, 21).

By reviewer: design_critic 13 PROPOSE FIX (Issues 1–13); structural 6 PROPOSE FIX (14–19) + 2 DECLINE (20, 21); implementation_readiness 15 PROPOSE FIX (22–34); comprehension 12 PROPOSE FIX (37–48, excluding none — Issues 37–48 are all PROPOSE FIX); zoom_out 6 PROPOSE FIX (50, 52–56) + 1 CONTEST (49) + 1 SETTLED (51).

Dedup clusters (R-A..R-O) all accounted for: R-A (12, 14, 35, 37) → E-A; R-B (12, 15, 35, 38) → E-B; R-C (12, 21) → E-A/E-B + DECLINE of the §13 leg (Issue 21); R-D (19, 39) → E-C; R-E (32, 40) → E-D; R-F (6, 26) → E-E; R-G (13, 36) → E-F; R-H (1, 53) → E-G; R-I (2, 34, 55) → E-H; R-J (7, 28, 29) → E-I; R-K (10, 41) → E-J; R-L (3, 4, 49, 50) → E-K + CONTEST (49); R-M (16) → E-B; R-N (30) → E-O; R-O (20) → DECLINE.

Live items carried forward (unchanged by this round): the round-1 ESCALATE `zoom_out-1-1` (Environment A scope), still awaiting the owner's ruling; the round-1 CONTEST `zoom_out-1-8` (commands stay in the strategy doc), settled and not re-opened.
