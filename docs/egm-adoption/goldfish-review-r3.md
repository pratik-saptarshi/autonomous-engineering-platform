# EGM Adoption (AEP) — Goldfish Review, Round 3

- **Target:** `/home/hatch/workspace/plans/2026-11-06-egm-adoption-aep.md` (415 lines, read in full by all reviewers)
- **Round:** 3 of 5 (cap). Rounds 1 and 2 both NOT CLEAN (0 clean rounds so far).
- **Reviewers:** 5 fresh-context Goldfish, direct dispatch — design_critic (feature-spec), structural (feature-spec), implementation_readiness (implementation-readiness), comprehension (feature-spec), zoom_out (zoom-out).
- **GoldfishContext:** companion NeuroStrata doc + AEP `skills/README.md` + AEP repo clone (read-only).
- **Counts:** **6 Blockers, 57 Majors, 30 Nits = 93 findings.** (Note: structural's report states "11 Majors, 6 Nits" but lists 12 Majors and 8 Nits; the counts here use the actual listed items.)
- **Settled (not re-opened, per the loop's settled rule):** 4 — Issue 32 (structural §7 table units = structural-1-8 DECLINE), Issue 35 (structural Appendix heading = structural-1-7 DECLINE, also structural-2-14), Issue 85 (zoom_out Environment A scope = zoom_out-1-1 ESCALATE, also zoom_out-2-4), Issue 89 (zoom_out runbook detail = zoom_out-1-8 CONTEST, also zoom_out-2-10).
- **Unsettled:** 6 Blockers, 55 Majors, 28 Nits = 89.
- **Verdict:** NOT CLEAN. No clean round yet (0 of 2 needed for convergence).

## design_critic — 2 Blockers, 12 Majors, 3 Nits (17)

### [Issue 1] [design_critic-3-B1] — Blocker — §9.3 (L248–264), §9.4 (L265–272): Path 2 has no skill loader; the headless Environment A route is unexecutable as specified
The doc admits: "No generic harness skill-discovery convention is specified: Path 2 requires the harness to load skills from `<install-root>/skills/` … only Muse's `custom-skills/` convention is specified here." §9.4 nevertheless routes every headless / no-plugin-support VM to Path 2. A directory layout is not an install: no mechanism is specified by which any non-Muse harness discovers, loads, or invokes skills from `<install-root>/skills/`. §9.4's decision matrix promises a route that does not exist.

### [Issue 2] [design_critic-3-B2] — Blocker — §4 (L41), §6 (L68), D6 (L177–183): D6 snapshot protocol contradicts parallel dispatch; the core safety control cannot execute as written
§4 states reviewers run in parallel. D6 states "after each reviewer completes, re-run the snapshot and diff it; any unexpected modification fails that reviewer's round" — and in the same paragraph states the opposite: "with parallel reviewers a modification is attributed to the round, not to one reviewer; the round fails." Both cannot hold: a write by a still-running reviewer lands in another reviewer's post-run diff (false fail) or is unattributable, so the per-reviewer fail / discard / rollback procedure is unexecutable. Separately, snapshot scope ("target repo working tree plus the local bundle and the adapted skills") excludes `~/workspace/plans/` (where review reports are written), other workspace directories, and all memory/DB paths — writes there are undetectable, and detection is post-hoc only with no prevention.

### [Issue 3] [design_critic-3-M1] — Major — §2 (L26–31), §3 (L35–37): Problem statement is unquantified; success metrics are activity-only
§3 admits adoption is precautionary — "no drift incident or review-load count is recorded in this document" — and defers the demand baseline (design docs per month) to the Phase 0 pilot log, while §14 decision 5 defers the marginal-value judgment to an owner ruling. §2 goals are all activity metrics (reviewers run, report filed, CI green, one review in 30 days) with no outcome/quality metric (finding action rate, false-positive rate, design improvement). A competent reader cannot confirm the investment is proportionate to the problem.

### [Issue 4] [design_critic-3-M2] — Major — §5 (L51–54): Alternatives Rule — two rejections rest on non-technical grounds; three viable alternatives are never evaluated
Submodule is rejected for "no submodule precedent in the repo" — precedent is not a complexity, cost, performance, or scalability trade-off, as the standard requires. Do-nothing / extend `grilling` + `roundtable_review` is rejected in one clause ("leaves design review informal") with no quantification. Never evaluated: referencing upstream live without vendoring; waiting for upstream issue #252 to close instead of hand-maintaining the D3 routing line in 7 skills; vendoring a docs subset (33 docs files, most never referenced by the 2 pilot skills).

### [Issue 5] [design_critic-3-M3] — Major — §6 (L64–73), §10.4 (L332–334), §14 decision 6 (L399–409): No cost or token budget for the pilot; worst-case spend is unbounded except by spawn count
Bounds are 25 spawns per run and a 30-minute interim per-reviewer timeout — i.e. up to 12.5 reviewer-hours and 150 minutes wall clock if rounds serialize — with no token or dollar estimate anywhere in the doc. The token budget is explicitly deferred to §14 decision 6 ("before Phase 1"), so the Phase 0 pilot runs with no budget at all.

### [Issue 6] [design_critic-3-M4] — Major — §4 (L41), §8.2 (L200–207): The Elephant drafts the design and then judges critiques of its own draft
The Elephant owns the design doc, merges/deduplicates findings, normalizes severity, and assigns stable ids — while §8.2 replaces the synthesizer with direct dispatch in Environment B, so there is no independent consolidator. The fresh-eyes independence EGM claims (defeating hallucination cascades) is broken at the consolidation step: the drafter decides the severity and fate of criticism of its own work, with no rule against downgrading severity and no appeal.

### [Issue 7] [design_critic-3-M5] — Major — §4 (L41), §10.4 (L332–334): Convergence ignores Nits entirely; the loop can go "clean" with all Nits undispositioned
Converged = two consecutive clean rounds defined as "no unsettled Blocker or Major." No disposition rule exists for Nits (fix / defer-with-reason / decline) — the pilot's 27 Nits could all stand at "clean."

### [Issue 8] [design_critic-3-M6] — Major — D5 (L168–176), §12 (L373–385): The 90-file vendored bundle is never content-scanned; only the adapted skills are gated
D5 gate-scans adapted `SKILL.md` files only. The bundle (verified 792K, including `agents/openai.yaml`, per-skill `test_scenarios.yaml`, `references/*.json`, `assets/icon.svg`) enters on SHA integrity alone, which proves provenance against the pin, not safety — an upstream compromise or malicious YAML passes both CI gates. The hand-written `skill.yaml` files are excluded from the manifest by the bare `skill.yaml` entry and covered by neither gate; YAML-parse + name-match proves well-formedness, not content safety, while `include_in_prompt: true` injects the description into the prompt.

### [Issue 9] [design_critic-3-M7] — Major — §12 (L373–385), §7 (L89–95): `egm-review-loop` URL fetching is unbounded
The loop saves the raw page of each user-supplied URL as a local file before review. The only control is "URLs the user supplied" — no scheme allowlist, size cap, content-type check, dedicated temp directory, or sandbox. §12 names it "the only network touchpoint" but sets no bound on it.

### [Issue 10] [design_critic-3-M8] — Major — §5 (L55), §11 (L349–363), §11.1 (L365–368), §14 (L399–409): Phase 2 scope is self-contradictory, and its gate is coupled to the Phase 3 provisioning decision
§5 and the §11 table say that without the decision-5 ruling, "Phase 2 installs the 2 review skills only" — but §11.1 enumerates all 7 wrappers unconditionally with no 2-skill variant file list. Separately, the Phase 2 gate requires "§14 decision 3 ruled" (provision a fresh VM for Phase 3, or mark Phase 3 documented-but-unexecuted) — coupling the AEP PR merge to a fresh-VM provisioning decision with no stated justification.

### [Issue 11] [design_critic-3-M9] — Major — §10.5–§10.6 (L336–347), D1 (L110–115), §10.2 (L294–308): Verification gaps — §10.6 check (2) has no executable procedure, and the pin record has no check at all
Check (2) asserts a wrapper `../../reference/...` target that does not exist fails the check, but no §10.5 step runs it in AEP: §10.5 step 4 normalize-then-diff compares local vs. repo copies and would pass with identical dangling references on both sides. Unlike check (1), which ships a shell loop, check (2) is an assertion without a command. Likewise, D1/§10.2 require a local bundle `README.md` pin record, but no §10.5/§10.6 check asserts its existence or content — and verified live, `~/workspace/egm/README.md` does not exist.

### [Issue 12] [design_critic-3-M10] — Major — D3 (L126–135), §10.6 (L343–347): D3 adaptation is a hand `sed` with no idempotency guard, and its verification is vacuous in two places
Mechanism is "one `sed` per row, or manual edit" with no script. A naive re-run of `agents/` → `<bundle>/agents/` on an already-adapted file double-prefixes (`<bundle>/<bundle>/agents/`). §10.6 check (1) verifies only `agents/...` and `resources/...` references — never `docs/...` references, the Muse routing line's presence, or that no upstream-relative reference remains. And the cited "persona-internal references" (`agents/zoom_out.md:44`, `agents/synthesizer.md:38`) are not references at all — verified: line 44 of `zoom_out.md` is a review-step heading and line 38 of `synthesizer.md` is a spawning-step heading — so "the pilot verifies one such reference resolves" cannot fail and proves nothing.

### [Issue 13] [design_critic-3-M11] — Major — §9.2 (L218–236), §9.5 (L274–281): Load-bearing Environment A commands are asserted without upstream citation
`muse plugins validate`, `muse skills list --source plugin`, and `muse exec` underpin §9.5 verification (step 1's "offline pre-check" is the sole pre-E2E gate for Path 1), but the doc cites bundle `docs/muse.md` for install/approve only — not for `validate`, `list --source plugin`, or `exec` or its approvals-simulation mode. If any of these does not exist on the target harness, Environment A verification collapses to the E2E fixture alone.

### [Issue 14] [design_critic-3-M12] — Major — D1 (L110–115), §11 (L349–363): No Phase 2 rollback and no vendored-dependency lifecycle
§11 rollback covers only the pilot (delete the 2 local skill dirs and the bundle). There is no revert procedure for a merged Phase 2 PR (bundle + 7 wrappers + scope/manifest/attribution + CI block). Re-sync is "a deliberate PR" with no cadence, owner, upstream monitoring, or staleness expiry — pin `e9e1f06a` will silently age with no trigger to revisit it.

### [Issue 15] [design_critic-3-N1] — Nit — §3 (L37): "22 documents under AEP `docs/`" needs its counting rule
22 is the top-level `*.md` count; the recursive count is 37 `.md` files (38 files total, including `docs/superpowers/plans/`). State whether the corpus is top-level or recursive so the demand baseline is reproducible.

### [Issue 16] [design_critic-3-N2] — Nit — §10.6 (L343–347): Check (1) regex can false-pass and false-fail
The pattern class includes `.`, so a prose trailing period (e.g. `agents/foo.md.`) would be captured into the path and false-fail; conversely a bare directory reference passes as "resolves" — verified present in the adapted `egm-review-loop` file (`resources/document_standards/` with no file), because `test -e` succeeds on a directory.

### [Issue 17] [design_critic-3-N3] — Nit — D1 (L110–115), §9.3 (L248–263), §10.5 step 2 (L336–341): The pin SHA is hardcoded in at least five places while §14 decision 1 leaves it open
`e9e1f06a` appears in attribution, PROVENANCE/README, §9.3 clone commands, and §10.5 step 2's fetch plus full-40-char `rev-parse` expectation. If the owner picks a different SHA, every occurrence must change by hand with no single source of truth.

## structural — 0 Blockers, 12 Majors, 8 Nits (20)

### [Issue 18] [structural-3-M1] — Major — §2 Goals (L26–33) vs §13 Non-goals (L387–397): required "Goals & Non-Goals" heading is split, not present as one section
§2 ends with the pointer "Non-goals: see §13" (line 33) and §13 opens with the reciprocal pointer "Goals: see §2" (line 389). The standard names Goals & Non-Goals as one required area; a fresh reader must jump 360 lines to assemble scope, and neither section is self-contained.

### [Issue 19] [structural-3-M2] — Major — §4 Proposed Architecture (L39–43): architecture is not in its own section
The entire section is one 1,481-character paragraph (line 41) that states the component map/data flow in compressed form and defers with "The existing §§8–10 keep their detail; this section is the map, with pointers to them." The standard requires the spec to detail component layout, data flows, and ecosystem integration; here that detail lives fragmented across §§8, 9, and 10, so §4 alone does not let a fresh reader confirm the architecture.

### [Issue 20] [structural-3-M3] — Major — §7 "What EGM is (verified)" (L75–106): background placed after Risks, before Design decisions
The definition of EGM, its skills table, and upstream state appear in §7, after Problem (§3), Architecture (§4), Alternatives (§5), and Risks (§6). A fresh reader meets the architecture and alternatives for a system that is not defined until §7; background/context belongs before §4.

### [Issue 21] [structural-3-M4] — Major — §8 hierarchy (L108–207): two different numbering schemes share H3
D1–D7 (lines 110, 117, 126, 136, 168, 177, 184) and numbered subsections 8.1 (line 196) and 8.2 (line 200) are all `###` under `## 8`, and 8.1/8.2 appear after D7 rather than before or as a separate section. Same-level headings should be the same kind of subdivision; mixing decision labels with numeric subsections breaks the outline and TOC navigation. (Not a re-raise of structural-1-6 DECLINE: that covered sibling H2 sections in the pre-restructure layout; this mixed scheme inside a single H2 was created by the round-1/2 restructuring, and the fix — moving 8.1/8.2 out or before D1 — does not touch the stable D-references.)

### [Issue 22] [structural-3-M5] — Major — §9.2 sibling heading (L237): "Native installs for the other harnesses…" is an unnumbered H3 between numbered H3s
Sequence is 9.1 (line 213), 9.2 (line 218), unnumbered heading (line 237), 9.3 (line 248), 9.4 (line 265), 9.5 (line 274). It is subordinate content of Path 1 (§9.2) presented at the same level as §9.3–9.5, breaking the numbered sequence and implying a §9.2½ that does not exist.

### [Issue 23] [structural-3-M6] — Major — §11.1–11.3 (L365, 369, 371): subsections out of phase order
Order is 11.1 Phase 2, 11.2 Phase 0, 11.3 Phase 1, while the §11 table (lines 353–356) and the rollout narrative run Phase 0 → 1 → 2 → 3. Numbered subsections should follow the document's own phase order; the current order forces the reader to reorder them mentally.

### [Issue 24] [structural-3-M7] — Major — §11.2 (L369, 316 chars) and §11.3 (L371, 257 chars): body content embedded in the heading line
Both headings carry the full file-change list after an em-dash on the heading line itself, unlike §11.1 (line 365), which is a heading only with body on line 367. Headings must be navigable labels; embedding a paragraph in a heading breaks TOC/outline use and is inconsistent within the same section.

### [Issue 25] [structural-3-M8] — Major — §10.5 (L336–341) vs §10.6 (L343–347): colliding step/check numbering
§10.5 has steps 1–4 and §10.6 has checks (1)–(6); line 345 has to disambiguate: "a step and a check with the same number are not the same item." A numbering scheme that needs an explicit disclaimer to prevent mis-citation is a structural defect; steps and checks should use distinct labels.

### [Issue 26] [structural-3-M9] — Major — §8.1 "AEP machinery" (L196–198): empty pointer subsection with a wrong line citation
The subsection states it is "a pointer only and states no additional requirements," and cites "the D4 bullets (lines 121–129)" — lines 121–129 in the current file are the D2 paragraph, while the D4 bullets are lines 138–165. A subsection that adds nothing and points at the wrong lines is stale scaffolding; the citation is unverifiable as written.

### [Issue 27] [structural-3-M10] — Major — Alternatives split across §5 and §8 (L45–62 vs L160–165)
§5 is the Alternatives section, but an additional rejected alternative ("shared `skills/egm-agents/` + `skills/egm-resources/` dirs") is filed as a bullet inside D4 (lines 160–165), duplicating the §5 bullet on the same option (line 51). The standard's Alternatives Rule requires one evaluable alternatives section; scattering a rejection outside it risks it being missed in a completeness check. Related formatting defect: §5's bullet list is interrupted by an 814-character unbulleted paragraph (line 59, "roundtable_review vs EGM — …"), with bullets resuming at lines 61–62.

### [Issue 28] [structural-3-M11] — Major — Risks split across §6 (L64–73) and §12 Security notes (L373–385)
§6 holds failure modes/cost/drift, while security implications — which the standard requires under Risks & Limits — live 300 lines later in §12, with no cross-reference from §6 to §12. A reader checking "risks and mitigations" against the standard must assemble two distant sections; security is a risk, not a separate appendix-style topic.

### [Issue 29] [structural-3-M12] — Major — D3 item 3 (L134, 2,141 chars): a mapping table written as inline prose in a numbered-list item
The upstream→installed path-rewrite mapping (7 rows) is a semicolon-separated run-on inside list item 3, alongside item 1 (line 130, 1,232 chars). Tabular data in a single-line list item is not scannable or citable per row; the mapping should be a table, as the document does elsewhere (§§7, 8.2, 9.4, 11).

### [Issue 30] [structural-3-N1] — Nit — §10.6 Verification checks (L347, 1,266 chars): six normative checks in one paragraph
Checks (1)–(6) run inline in a single paragraph with no list, including an embedded shell loop. A normative test list should be a list; as one paragraph, individual checks cannot be cited, scanned, or checked off.

### [Issue 31] [structural-3-N2] — Nit — Unwrapped single-line paragraphs throughout
Representative: line 37 (1,063 chars, §3), line 41 (1,481, §4), line 182 (2,738, D6), line 308 (1,287, §10.2), line 314 (1,121, §10.3.1), line 323 (1,348, §10.3.3), line 330 (1,594, §10.3.5), line 339 (1,080, §10.5 step 2), line 341 (783, §10.5 step 4). No line-length rule is in the standard, but whole sections as single lines impede fresh-reader parsing and make line-cited review findings coarse.

### [Issue 32] [structural-3-N3] — Nit — §7 table unit inconsistency (L89–95) — SETTLED
`egm-brainstorm` is "(271 lines)" but `egm-draft` is "(321)", `egm-review` "(426)", `egm-resolve` "(187)", `egm-review-loop` "(199)", `egm-bootstrap` "(427)", `egm-drift-report` "(67)" — unit stated once, omitted six times. **Settled: same scope and issue as round-1 structural-1-8 (DECLINE). Per the loop's settled rule, not re-opened. Recorded here only; no fix proposed.**

### [Issue 33] [structural-3-N4] — Nit — Link-style inconsistency, line 244
The ChatGPT desktop plugin URL is a bare URL in parentheses, while every other external link in the document (e.g. lines 280, 413–415) uses Markdown `[text](url)` form. One bare URL breaks the document's own link convention.

### [Issue 34] [structural-3-N5] — Nit — Prose inside a code block, lines 222–226
Line 223 embeds an annotation in the shell block: `git clone https://github.com/google/elephant-goldfish-model.git (creates \`./elephant-goldfish-model/\`, …)`. A code block presented as commands to run contains non-executable prose; the annotation belongs outside the fence.

### [Issue 35] [structural-3-N6] — Nit — Appendix heading (L411): "## Appendix — Sources (all verified 2026-11-06)" is unnumbered after numbered §§1–14 — SETTLED
**Settled: same scope and issue as round-1 structural-1-7 (DECLINE — appendix unnumbered by convention), also round-2 structural-2-14. Per the loop's settled rule, not re-opened. Recorded here only; no fix proposed.**

### [Issue 36] [structural-3-N7] — Nit — Overlapping sibling headings §10.3.2 (L315) "Approval gates" vs §10.3.3 (L321) "Readiness and section-approval gates"
Both cover approval gating, and §10.3.2's body (lines 317–319) restates gates that §10.3.3 then defines. Near-duplicate headings at the same level signal one section split in two; merge or rename to distinguish scope.

### [Issue 37] [structural-3-N8] — Nit — No explicit scalability-limits subsection
§6 covers loop cost (line 71) and failure modes (line 73), but no subsection states scalability limits as such, as the standard's Risks & Limits paragraph calls for. The content is partially present (cost bounds, bundle size in §5 line 49), but a fresh reader cannot locate a scalability-limits statement; minor because the cost bound does address the main scaling dimension.

## implementation_readiness — 1 Blocker, 9 Majors, 9 Nits (19)

Verified correct (no finding): §11.1 counts match the installed bundle exactly (skills 38, agents 10, resources 7, docs 33, total 90); full SHA `e9e1f06aa4e26e95cd4ed37210a0632202c429e9` confirmed as upstream HEAD; `tests/unit` exists upstream (so §9.5 step 2's path is real); D4's CI block matches the existing nine `vendor-integrity` blocks and the `humanizer` block is the last one, so the insertion point is unambiguous; `skill.yaml` fields match the repo norm (61 files; `archify` example matches); bare `skill.yaml` in `[exclude-paths]` confirmed (scope line 96).

### [Issue 38] [implementation_readiness-3-B1] — Blocker — §9.3 (L261): Path 2 has no executable skill-discovery step for a generic harness
"No generic harness skill-discovery convention is specified: Path 2 requires the harness to load skills from `<install-root>/skills/` (or the harness's own skill directory, stated per harness in §9.2); only Muse's `custom-skills/` convention is specified here (Environment B)." No per-harness skill directory is actually stated in §9.2 for any harness. The plan admits its own gap. An implementer on a headless VM with a non-Muse harness cannot complete the install — they must invent how that harness discovers skills. A whole install route fails the zero-decision rule.

### [Issue 39] [implementation_readiness-3-M1] — Major — §11.1, §11.2 (L367, 369): File-change lists give counts and directories, not exact file paths
Phase 2 "Created" lists the bundle as "90 files" with per-directory counts (skills 38, agents 10, resources 7, docs 33) and wrapper directories `skills/egm-*/`, never the 90 repo-relative paths; Phase 0/1 lists are directory-level the same way. The standard explicitly requires an exact path list "suitable for enforcing a Phase 5 write allowlist" and allows a glob only for generated output with unknowable filenames. All 90 filenames are knowable in advance (pinned SHA; verified against the local bundle). Counts cannot enforce an allowlist. The §10.5 step 2 upstream diff constrains content after the fact but does not satisfy the allowlist requirement.

### [Issue 40] [implementation_readiness-3-M2] — Major — §9.5 step 3 (L280): E2E fixture is not an executable test
No literal prompt text for brainstorm → draft → review; fixture design `muse-wonder-1.0` ("line-count design") is never defined — no content, no expected line counts; `<shape>` values in `/tmp/egm-e2e-<shape>/` are unenumerated; `muse exec` invocation and the "installed cache" location are unspecified; pass criterion is only "all three stages complete and the review report is filed," with no per-stage assertions. The implementer must compose the fixture prompts and decide what "complete" means — design/test decisions left to the implementer, and the acceptance gate is unfalsifiable as written.

### [Issue 41] [implementation_readiness-3-M3] — Major — §10.6 (L347): Checks (2) and (3)/(6) name edge cases with no executable procedure
Check (1) ships a full shell loop; check (2) ("a wrapper `../../reference/...` target that does not exist fails the check") gives no command or enumeration method, and checks (3)/(6) ("every `skill.yaml` parses as YAML") name no parser, tool, command, or expected output. A test plan in which half the checks have no procedure cannot be executed on first attempt.

### [Issue 42] [implementation_readiness-3-M4] — Major — §10.6 check (1) (L347) + D3 item 3 (L134): D3's rewritten `docs/` references are never verified
D3 rewrites five `docs/` rows (`../../docs/codex.md`, `${CLAUDE_PLUGIN_ROOT}/docs/claude.md`, `docs/harnesses.md`, `docs/muse.md`, plus `resources/execution_instructions.md`), but check (1)'s grep covers only `(agents|resources)/…`. No check asserts any `<bundle>/docs/…` target resolves. A dangling `docs/muse.md` reference — the file the Muse routing line itself points at — would pass all six checks.

### [Issue 43] [implementation_readiness-3-M5] — Major — §10.5 step 3 (L340) + §14 decision 2 (L403): Pilot run instruction is not invocable as written
"run `egm-review-loop` + `egm-review` once against the Phase 0 pilot target" gives no invocation mechanism or command, no brief text for the loop run itself (brief contents in §10.3.5 cover reviewers, not the loop invocation), and the target is contingent — the PR number is unrecorded and the fallback "this document at its current HEAD" names no commit. The implementer must decide how a skill is invoked in Environment B and exactly what artifact/commit is under review.

### [Issue 44] [implementation_readiness-3-M6] — Major — §9.3 step 2 (L263): "Copy the bundle" specifies neither the command nor the file set
Step 2 is "Copy the bundle to `<install-root>/egm/`" with no copy command and no exclusion list, and it never references the §7 not-vendored list (`site/`, `scripts/`, `tests/`, `adapters/`, plugin manifests, other repo-root files). The implementer decides whether the whole checkout or the pruned set is copied; only the after-the-fact §10.5 step 2 diff would catch an over-copy.

### [Issue 45] [implementation_readiness-3-M7] — Major — §10.4 (L334) + §14 decision 6 (L409): Phase 1 execution parameters are unset until a future owner ruling
The 30-minute per-reviewer timeout is explicitly "for the pilot" (interim bound); decision 6 defers the Phase 1 timeout and whether a token budget applies to a pre–Phase 1 owner ruling, with no default or fallback value. Phase 1 loop runs cannot be executed without asking the owner a clarifying question. Deferring a numeric execution parameter with no default leaves the phase unready under the standard, even though the deferral is honestly labeled.

### [Issue 46] [implementation_readiness-3-M8] — Major — §5 (L55) + §11 table (L357): The two-skill Phase 2 fallback has no file-change list
"Without that ruling, Phase 2 installs the 2 review skills only" — but §11.1 lists only the 7-skill case (7 wrappers, 7 scope lines, 7 attribution rows, full bundle). Nothing states which 2 wrappers, how many scope lines, which attribution rows, or whether the CI block/manifest steps change in the fallback. A specified branch of the plan has no file boundary. The implementer must derive the fallback's change set, and §11.1 as written would over-install relative to the fallback.

### [Issue 47] [implementation_readiness-3-M9] — Major — §9.2 (L237–246) + §9.5 step 1 (L276–278): Per-harness verification commands are unnamed
"Verification per harness: the harness's own plugin-list/validate command" names no actual command for Claude Code, Codex, Antigravity, Cursor, or OpenCode; the only fallback is the §9.5 step 3 E2E fixture, which is itself underspecified (Issue 40). For every non-Muse harness, the verification chain has no executable form.

### [Issue 48] [implementation_readiness-3-N1] — Nit — D3 item 2 (L131–133): Muse routing-line insertion point unspecified
Exact line text is given ("In Muse, read `<bundle>/docs/muse.md` first.") but not where in `SKILL.md` it goes (after frontmatter, top of body, end). Low behavioral risk since the whole file loads, but placement is an implementer decision; one sentence would close it.

### [Issue 49] [implementation_readiness-3-N2] — Nit — D3 item 3 (L134): No literal `sed` commands for the rewrite mapping
"apply the mapping mechanically (one `sed` per row, or manual edit)" — no literal commands, though rows like `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` need escaping. Outcome is verifiable via §10.6 check (1), so this is a convenience gap, not a correctness gap.

### [Issue 50] [implementation_readiness-3-N3] — Nit — D4 (L152): PROVENANCE.md Purpose / Updating / Update history content undetermined
Field values are given for URL, SHA, date, license, and exclusions, but Purpose, Updating, and Update history are only "per the esf pattern" — and the esf exemplar's text is esf-specific (verified in `reference/esf/PROVENANCE.md`), so it cannot be copied verbatim. The implementer must author EGM-specific prose.

### [Issue 51] [implementation_readiness-3-N4] — Nit — §10.2 (L299): Local bundle README.md has fields but no template
Four fields listed (URL, SHA, date, license) with no literal file content or format, though it is "re-written on every re-sync." A one-paragraph template would make the deliverable first-attempt correct.

### [Issue 52] [implementation_readiness-3-N5] — Nit — D6 (L182): Snapshot/rollback procedure has placeholders
`<snapshot-file>` path is unnamed; "re-run the snapshot and diff it" gives no diff command; rollback says "re-vendor the bundle from the repo tree" with no command, and `git checkout -- <paths>` leaves `<paths>` unspecified. Recovery path only; the happy-path snapshot command is given, so the implementer can fill these in trivially — but as written they are not executable verbatim.

### [Issue 53] [implementation_readiness-3-N6] — Nit — §11.1 (L367): Scope-file lines and attribution-row Skill values not spelled out literally
".github/skills-sync-scope.txt (7 lines under `[skills]`)" never lists the seven line values; "7 attribution rows" gives Notes text but not the full row text including the Skill column. Values are directly derivable from the §7 skill table, so risk is low; exact literals would remove all doubt for the allowlist.

### [Issue 54] [implementation_readiness-3-N7] — Nit — §10.5 step 4 (L341): Sync-check temp dir unnamed; already-rewritten paths unhandled
"copy … to a temp dir" names no path (e.g. `mktemp -d`); the two `sed` expressions handle only `~/workspace/egm` and `/home/hatch/workspace/egm` forms, with no instruction if a local file already contains the `../../reference/…` form.

### [Issue 55] [implementation_readiness-3-N8] — Nit — §10.3.3 (L323) + §10.4 (L334): Gate questions lack literal text
Only the section-approval question is quoted verbatim; the readiness gate has no question text, and the driver "asks the owner one question" on cap/churn with options listed but no literal question. Conversational wording is low-stakes, but the driver interaction is not reproducible verbatim as specified.

### [Issue 56] [implementation_readiness-3-N9] — Nit — §14 decision 3 (L404): "Move §9 to an appendix" has no procedure
The documented-but-unexecuted option is defined as "§9 is moved to an appendix," with no specified appendix location, heading, or step for performing the move. A conditional restructuring of the document itself is left to whoever executes the ruling.

## comprehension — 3 Blockers, 15 Majors, 8 Nits (26)

Baseline spot-checked read-only (9 `vendor-*.sha256` files, 9 `reference/` trees, 61 `skill.yaml` files — those counts check out and are not flagged).

### [Issue 57] [comprehension-3-B1] — Blocker — §9.3 (L261–263): `<install-root>` definition contradicts its own layout and example
Line 261 defines `<install-root>` as "the directory holding the cloned repo and the installed skills, default `$HOME/egm`", then states the bundle is at `<install-root>/egm/` (i.e. `$HOME/egm/egm/`) — but the same paragraph's example says a Path 2 skill contains `$HOME/egm/agents/design_critic.md` (i.e. bundle = `$HOME/egm`). The Environment B mapping (`<install-root>` = `~/workspace`, bundle `~/workspace/egm/`) fits the `<install-root>/egm/` form, so the generic default should apparently be `$HOME`, not `$HOME/egm`. A fresh engineer cannot determine the actual Path 2 paths; the install steps in line 263 inherit the contradiction.

### [Issue 58] [comprehension-3-B2] — Blocker — §5 (L55) vs §11 (L353–355) and §11.1 (L367): phase sequencing is self-contradictory
§5: "Without that ruling, Phase 2 installs the 2 review skills only; `egm-bootstrap` and `egm-drift-report` deferred to Phase 1." Phase 1 precedes Phase 2 and (§11, line 353) already installs the remaining 5 skills locally, so deferring skills "to Phase 1" after a Phase 2 condition is temporally incoherent; §11 Phase 2 says "without it, Phase 2 installs the 2 review skills only" while §11.1 unconditionally lists all 7 `skills/egm-*/` wrappers in the Phase 2 file-change list. The reviewer cannot paraphrase what Phase 2 contains with vs. without the ruling.

### [Issue 59] [comprehension-3-B3] — Blocker — §14 decision 2 (L403): pilot target cannot be paraphrased
"The AEP repo, with the Phase 2 PR … as the target state; the reviewed artifact is this document. If the pilot runs before that PR exists, the target is this document at its current HEAD." Three different targets are named in one decision (repo / PR-as-target-state / this document), with no statement of which one the reviewers actually read. Since the pilot is the evidence gate for everything downstream (§14 decision 5), this ambiguity blocks understanding of the rollout.

### [Issue 60] [comprehension-3-M1] — Major — §8.2 + §14 (L79, 204–207, 308, 334, 399–409): the "owner" / "human" / "Elephant" actors are never distinguished
§7 introduces "the human" (explicit approval gates); §8.2 defines the Elephant as "the main agent" in Environment B; §10.2 says the sync owner is "the agent running the sync (the Elephant / main agent…) — not a separate role"; yet §10.4 and §14 repeatedly require "the owner" to rule, be asked one question, and approve merges. The document never says who the owner is, whether owner = human = user, or how the owner is reached. Every phase gate and open decision depends on this actor.

### [Issue 61] [comprehension-3-M2] — Major — §§3, 7, 10.4, D7 (L37, 82–83, 104, 184–193, 334): reviewer-panel membership is incoherent — 10 vs 5 vs 15
§7 calls all 10 personas "reviewer personas"; §3 says the pilot had "all 5 reviewers" (design_critic, structural, implementation_readiness, comprehension, zoom_out); §10.4 caps at "5 reviewers per round"; the §7 fixture used "15 fresh-context reviewers"; D7 lists 10 named agents including `egm-synthesizer` and `egm-bootstrap-orchestrator`, which are not reviewers. The document never states which 5 personas form the `egm-review-loop` panel, so a fresh reader cannot reconstruct who reviews what.

### [Issue 62] [comprehension-3-M3] — Major — §10.4 (L334): convergence depends on four undefined dispositions
"'Unsettled' means a Blocker or Major that is neither fixed in the target nor recorded CONTEST, ESCALATE, DECLINE, or SETTLED in the resolve report." None of the four dispositions is defined anywhere in the document — not what each means, who records it, or how CONTEST differs from DECLINE. "Two consecutive clean rounds" (the loop's termination condition) is therefore not determinable from this document.

### [Issue 63] [comprehension-3-M4] — Major — §§8.2, 10.4 (L206, 334): "churn" is undefined
The Driver "stops and asks the owner on cap/churn" and "on cap or churn the driver stops and asks the owner one question." "Cap" is inferable (5 rounds), but "churn" — what counts as churn, how it is measured, what threshold triggers the stop — is never defined.

### [Issue 64] [comprehension-3-M5] — Major — §14 vs body (L401–402, 405–409 vs L110–116, 168–176, 334): decisions listed as open are already stated as decided in the body
Decision 1 (pin SHA) recommends `e9e1f06a`, which D1/§7/§11.1 already treat as pinned; decision 4 (force-sync policy) restates D5's already-stated policy (upstream fix / baseline / owner force-sync); decision 6 (owner sets per-reviewer timeout before Phase 1) follows §10.4 already setting 30 minutes. A fresh reader cannot tell which of these are genuinely open vs. already settled and merely awaiting ratification.

### [Issue 65] [comprehension-3-M6] — Major — §§2, 5, 14 (L28, 55, 59, 408): the pilot-value ruling has no criteria
The §14 decision 5 ruling ("whether the pilot demonstrated marginal value over the existing instruments") gates the remaining 5 skills, but no metric, threshold, or evidence standard is given; §5 admits no roundtable baseline control run was performed, so the 65-finding pilot cannot establish marginal value — yet the ruling is the sole mechanism for judging it. The §2 goal "findings categorized" is likewise undefined: no categorization taxonomy is stated anywhere.

### [Issue 66] [comprehension-3-M7] — Major — §10.2 (L308): canonical direction contradicts itself
"The AEP repo is canonical for the wrappers; the local bundle … is canonical for the installed personas and standards. Sync runs in the existing live→repo direction… and any re-vendor replaces the local bundle wholesale from the repo tree." If the local bundle is canonical for personas/standards, replacing it wholesale from the repo tree (where the bundle is a copy) inverts the stated direction; the paragraph asserts both live→repo and repo→local without reconciling which artifact flows which way.

### [Issue 67] [comprehension-3-M8] — Major — §§10.3.1, 10.3.5, 10.5 (L312–314, 330, 340): the memory-prohibition check is circular and has no verifier
§10.3.1 says the memory prohibition "is enforced by the brief … and checked the same way" (as the line-existence/standard-name checks), then says §10.5 step 3's independent subagent "performs exactly these two checks" — but those two checks are line-existence and standard-name, neither of which can detect a finding whose rationale cites memory. No mechanism for detecting memory/conversation citation is ever described, so the prohibition is unenforceable as written.

### [Issue 68] [comprehension-3-M9] — Major — §12 (L379–380): the principal risk control is unparseable
"Treat Goldfish reviewers as unprivileged-but-able-to-write until the harness proves otherwise. Never give a reviewer a write tool it did not ask for by design." "Unprivileged-but-able-to-write" is an unexplained oxymoron (what privilege model makes an agent both?), and "a write tool it did not ask for by design" cannot be parsed — it is unclear whether reviewers may ever be given write tools, or under what condition. This is the document's own principal risk (§12, D6); its wording must be unambiguous.

### [Issue 69] [comprehension-3-M10] — Major — §9.1 (L215): "pilot VM" is a third, undefined VM
"`python3` ≥ 3.12.3 (verified floor on the pilot VM) … installed … on the fresh VM (absent on this VM — record the installed version in the pilot log)." The document defines only Environment A (fresh VM) and Environment B (this VM); "pilot VM" appears nowhere else and is never equated with either, and "absent on this VM" leaves unclear whether pytest is absent on the pilot VM, this VM, or both.

### [Issue 70] [comprehension-3-M11] — Major — §9.2 (L245) vs §9.4 (L270): Cursor's status contradicts itself
§9.2: Cursor is "experimental, unverified upstream … not a supported Path 1 route until verified." §9.4's decision matrix lists "Another supported harness (Claude/Codex/Cursor/OpenCode/Antigravity) → Path 1 (native install)". A fresh reader cannot tell whether Cursor is a supported Path 1 route.

### [Issue 71] [comprehension-3-M12] — Major — §10.5 step 4 (L341): sync check claims coverage its procedure does not perform
The procedure copies only the seven `SKILL.md` files to a temp dir, seds them, and diffs against repo `skills/egm-*/`; it never copies `skill.yaml`. The same line then claims "The sync check also covers `skill.yaml`" via re-validation (YAML parses + name matches) — which is a parse check, not a content diff, so `skill.yaml` content drift between local and repo would not be caught by the stated procedure. Also, the second `sed` (expanded `/home/hatch/...` form) is dead by D3's own statement that the expanded form "never appears in a pilot adapted file" (line 134).

### [Issue 72] [comprehension-3-M13] — Major — §11 Phase 2 gate (L355) vs §14 decision 3 (L404): Phase 2 is gated on a Phase 3 decision
Phase 2 merges only once "§14 decision 3 [is] ruled (fresh VM provisioned, or Phase 3 marked documented-but-unexecuted…)". Decision 3 is the Phase 3 provisioning ruling, required "before Phase 2 merges" — so the AEP PR (Phase 2) is blocked on provisioning a fresh VM for a later phase, or on a ruling that moves §9 to an appendix. The temporal dependency is never explained.

### [Issue 73] [comprehension-3-M14] — Major — D4 Wrappers bullet (L156): skills-freshness sentence negates itself
"The gate proves the repo `skills/` tree equals the manifest generated from the repo tree after the last sync from live — it detects no drift against the upstream bundle and no drift against local `custom-skills/`." Read literally, "it detects no drift" states the gate's result; the intended meaning (a limitation: the gate cannot detect such drift) requires the reader to infer the negation from context. As the definition of a gate's coverage, this must be unambiguous.

### [Issue 74] [comprehension-3-M15] — Major — D6 (L182): snapshot procedure is Environment B-only, but the caveat is claimed for both environments
The snapshot scope is given only in local paths (target repo tree + `~/workspace/egm/` + `~/workspace/custom-skills/egm-*/`); §9.5 (Environment A verification) never mentions snapshotting, and no Environment A / Path 1 snapshot scope or command is defined — yet §12 calls the read-only caveat "the principal risk in both environments."

### [Issue 75] [comprehension-3-N1] — Nit — §8.1 (L198): stale/wrong line pointer
"The normative definitions are the D4 bullets (lines 121–129)." Lines 121–129 are D2 and the start of D3; the D4 bullets are lines 136–166. A reader following the pointer lands on the wrong decisions. §8.1 is otherwise content-free ("a pointer only"), so the section contributes nothing but this wrong reference.

### [Issue 76] [comprehension-3-N2] — Nit — §1 (L22): forward reference before definition
"Path 1 installs upstream verbatim and carries no adapted copies" appears in §1, but Path 1 is not defined until §9.2 (line 218). A fresh reader meets the term 200 lines before its meaning.

### [Issue 77] [comprehension-3-N3] — Nit — §3 (L37): "scale baseline" asserts and retracts itself in one sentence
"Scale baseline (verified 2026-11-06): adoption is precautionary — no drift incident or review-load count is recorded in this document." Nothing verifiable is baselined; the sentence labels as "verified" the absence of any recorded count, and then says the Phase 0 pilot log "records design docs produced per month" — a log that does not yet exist at draft time.

### [Issue 78] [comprehension-3-N4] — Nit — §7 (L97) and §10.5 (L339): exclusion list ends in an open catch-all
"and all other repo-root files" is not enumerable: a fresh engineer cannot determine from this document which repo-root files are excluded from the vendor, which matters because the §10.5 step 2 zero-diff check and the vendor-integrity hash both depend on the exact file set.

### [Issue 79] [comprehension-3-N5] — Nit — §11.1 (L367): the `skills/` 38-file count does not derive from its own breakdown
"per skill `SKILL.md`, `TEST.md`, `agents/openai.yaml`, `assets/icon.svg`, `test_scenarios.yaml` (7 × 5 = 35), plus `references/` in `egm-bootstrap` and `egm-draft`" — the breakdown sums to 35 plus an unstated number of `references/` files to reach 38. The arithmetic is not reproducible from the text (contrast `docs/` 33 = 13+18+1+1, which is fully derived).

### [Issue 80] [comprehension-3-N6] — Nit — §10.6 (L343–347): two numbering schemes collide, and check (2) has no procedure
"§10.5 steps 1–4 are the procedure; the checks below are the normative test list — a step and a check with the same number are not the same item" forces the reader to track two parallel numberings. Check (1) gets a full shell command; check (2) ("a wrapper `../../reference/...` target that does not exist fails the check") gets no command or method at all.

### [Issue 81] [comprehension-3-N7] — Nit — §§9.5, 8.2, 10.3.5 (L207, 280, 330): undefined in-group vocabulary
"depth-2 spawning" (§8.2 Synthesizer row, with a self-reference to "this review itself"); "`muse-wonder-1.0` (line-count design)" and "uninterrupted review" (§9.5 step 3); the "verbatim prompt" pinned to `skills/egm-review-loop/SKILL.md:34` (§10.3.5, a line number in a file the reader does not have). Each is used in a normative instruction without definition or a resolvable pointer.

### [Issue 82] [comprehension-3-N8] — Nit — D5 (L168–176); §13 (L396–397); §10.3.3 (L323): undefined terms / missing pointers a fresh reader needs
SkillSpector is never defined or linked (only its invocation, score threshold, and baseline-file format are given); §13 says NeuroStrata "is covered separately" with no path to the companion document; §10.3.3's pilot GoldfishContext "supplied the companion doc, README, and repo clone" without naming which repo clone or its path.

## zoom_out — 0 Blockers, 9 Majors, 2 Nits (11)

Review status: RUN — all assigned files read, reuse claims checked against the AEP repo (`skills/`, `reference/`, `.github/skills-sync-scope.txt`, `ci.yml`) and the local bundle at `~/workspace/egm/`. No Blockers: the objective is determinable and Phases 1–3 are gated on owner rulings, so the §0 fail condition is not met.

### [Issue 83] [zoom_out-3-M1] — Major — §3 (L35–38): root-problem scale is unestablished; adoption is precautionary
The doc admits "no drift incident or review-load count is recorded," and that the 65-finding pilot "is evidence the instrument works, not evidence of the problem's scale." The demand baseline (design docs/month) is deferred to the Phase 0 pilot log and the value judgment to §14 decision 5 — i.e. the full local install is built before the problem's size is measured. A 90-file vendor + 7 skills + 2 CI gates adopted against an unmeasured problem; the staging mitigates but does not cure it, since Phase 0 still installs the bundle before the ruling.

### [Issue 84] [zoom_out-3-M2] — Major — §5 (L49–50) and §6 (L64–73): "extend the incumbents" rejected in one sentence, without sizing
`roundtable_review` (verified in `skills/roundtable_review/SKILL.md`) already does fresh-context parallel reviewers, debate rounds, a judge, claim-verification subagents, and filed reports; `planning-wringer` (55 lines) is an adversarial plan review, and `requesting-review` already dispatches a fresh subagent. The doc's own delta table concedes both have fresh-context reviewers and claim verification; the genuinely new delta is the five written standards, the two gates, and the drift/bootstrap skills. No evidence that grafting written standards + filed reports onto `roundtable_review` was costed against vendoring 2,810 lines; reinventing the wheel by importing a whole second review instrument.

### [Issue 85] [zoom_out-3-M3] — Major — §1 (L15–24); §9 (L209–282); §14 decision 3: speculative second deployment target — SETTLED
The doc designs two environments, two install mechanisms, and native installs for seven harnesses (including Cursor, "experimental, unverified upstream," and OpenCode, "adapter unverified upstream," lines 245–247), yet only the Muse environment is actually used — and §9 is headed "Provisional — validation pending owner provisioning," with decision 3 contemplating marking Phase 3 "documented-but-unexecuted" and moving §9 to an appendix. ~74 lines design a section that may be discarded. **Settled: same scope and issue as round-1 zoom_out-1-1 (ESCALATE — Environment A scope; the premise was wrong — the owner explicitly requested dual-environment coverage — and the scope decision needs the owner's ruling). Also round-2 zoom_out-2-4. Per the loop's settled rule, not re-opened. Recorded here only; no fix proposed. The live ESCALATE remains open, awaiting the owner's ruling.**

### [Issue 86] [zoom_out-3-M4] — Major — D2 (L117–125); §5 (L62–63); §11.1 (L365–367): full 90-file / 2,810-line vendor for a 2-skill pilot
Verified in `~/workspace/egm/`: the bundle includes 18 `docs/designs/*` upstream design notes, per-skill `TEST.md`, `test_scenarios.yaml`, `agents/openai.yaml`, `assets/icon.svg`, and harness docs for Claude/Codex/Copilot/Cursor/OpenCode. The minimal-subset rejection justifies personas + standards (runtime-resolved), not docs/designs, test fixtures, or icons. Vendoring non-runtime files inflates the vendor-integrity surface (every file hashed and checked) for content the pilot never executes.

### [Issue 87] [zoom_out-3-M5] — Major — D4 (L136–167); §10.2 (L294–308): new wrapper→bundle coupling + dual canonical direction
The doc admits this is "a new pattern in this repo — no existing skill references a `reference/<tree>/` path" (verified: no `skills/*/SKILL.md` references a `reference/` tree) and that renaming either tree "silently breaks all 7 skills" (§6). On top of that, §10.2 splits canonicity (AEP canonical for wrappers, local bundle canonical for personas/standards) and adds a normalize-then-diff sync check (§10.5 step 4) to keep the two trees aligned. Two trees, two gates, and sync machinery to reconcile them, where a single-tree or local-only layout would have no cross-tree drift to manage; an architectural dead-end risk accepted without a simpler-layout comparison.

### [Issue 88] [zoom_out-3-M6] — Major — D6 (L177–183); §12 (L384–386): elaborate workaround for a missing harness control, admitted detection-only
Snapshot-by-content-hash before dispatch, diff after each reviewer, fail the round, discard findings, `git checkout` restore or re-vendor, round-level (not reviewer-level) attribution — plus the admission that memory/DB paths are not snapshotted, "silent memory use is undetectable," and "detection does not prevent the write." A per-run procedural apparatus is built around the absence of tool projections instead of bounding the blast radius structurally (e.g. reviewing only in a scratch copy), and the residual risk stands after all the machinery.

### [Issue 89] [zoom_out-3-M7] — Major — D3, D4, §9.2–§9.3, §10.5–§10.6: altitude drops (weeds) — SETTLED
D3 lines 126–135 (per-row `sed` mapping table, per-skill occurrence counts such as "`egm-review` 3× `agents/`", title-case mapping for all 7 skills); D4 lines 136–167 (literal CI `run:` block, literal `sha256sum` command, PROVENANCE field order); §10.5 lines 336–342 (literal `diff -rq` commands, full `git clone/fetch/checkout/rev-parse` with 40-char hash); §10.6 lines 343–347 (literal `grep -oE` loop). A 415-line design doc spends a large share on shell/CI literals that belong in a runbook or the PR itself. **Settled: same scope and issue as round-1 zoom_out-1-8 (CONTEST — commands stay in the strategy doc; the document's stated purpose is executable design, and the same round's implementation-readiness standard demands more exact commands, not fewer). Also round-2 zoom_out-2-10. Per the loop's settled rule, not re-opened. Recorded here only; no fix proposed.**

### [Issue 90] [zoom_out-3-M8] — Major — §7 skill table (L84–93); §11 (L361–367): five of seven skills duplicate or anticipate, only two are piloted
`egm-brainstorm` duplicates the existing `brainstorming` skill (verified in the catalog; its description mandates use "before any creative work"), and `egm-draft` overlaps `writing-plans` (verified: spec → bite-sized implementation tasks). `egm-brainstorm`, `egm-draft`, `egm-resolve`, `egm-drift-report`, `egm-bootstrap` are all deferred to Phase 1 on the pilot-value ruling, yet Phase 2 still installs all 7 wrappers (14 files, §11.1). Adopt the two review skills the pilot tests; vendor/wrap the other five only after the ruling that justifies them.

### [Issue 91] [zoom_out-3-M9] — Major — §6 (L70–72); §10.4 (L332–334): 25-spawn loop adopted without a cost baseline
Up to 5 rounds × 5 reviewers = 25 spawns per run, 30-minute per-reviewer timeout "set now" because "no pilot log with per-reviewer elapsed times exists yet," token budget deferred to §14 decision 6 — against §3's admission that no review-load count exists. The incumbent panel uses four reviewers; nothing establishes that five reviewers × five rounds is the right scale. The most expensive new recurring cost in the design is fixed before any measurement, with the budget decision postponed.

### [Issue 92] [zoom_out-3-N1] — Nit — §4 (L39–44); §8.1 (L196–198): the architecture section is a pointer, not a map
§4 says "the existing §§8–10 keep their detail; this section is the map, with pointers to them," and §8.1 states it "states no additional requirements." A reader must reassemble the architecture from the weeds-heavy §§8–10. The one section meant to give the high-altitude view defers to the detail sections.

### [Issue 93] [zoom_out-3-N2] — Nit — §2 (L26–33): adoption goal measures usage, not outcome
"At least one design document reviewed via `egm-review-loop` within 30 days" counts that the instrument ran, not that it found drift or defects the incumbents missed — the very marginal-value question §14 decision 5 is meant to answer. A goal stated as usage lets the adoption succeed even if the pilot-value ruling is negative in substance.

---

## Totals and verdict

| Reviewer | Blockers | Majors | Nits | Total |
|---|---|---|---|---|
| design_critic | 2 | 12 | 3 | 17 |
| structural | 0 | 12 | 8 | 20 |
| implementation_readiness | 1 | 9 | 9 | 19 |
| comprehension | 3 | 15 | 8 | 26 |
| zoom_out | 0 | 9 | 2 | 11 |
| **Total** | **6** | **57** | **30** | **93** |

- **Settled:** 4 (Issues 32, 35, 85, 89).
- **Unsettled:** 6 Blockers, 55 Majors, 28 Nits = 89.
- **Churn check:** performed against the round-2 applied fixes — no stop condition triggered. Several round-3 findings sit at scopes round-2 fixes touched (§9.3, D6, §8.1), but each has a forward fix (correct the definition, reconcile the snapshot rule, correct the citation); none is resolvable only by reverting an applied fix.
- **Verdict: NOT CLEAN.** Round 3 of 5. Clean rounds so far: 0 of 2 needed for convergence. Next: resolve round 3, auto-apply PROPOSE FIX items, run round 4.
