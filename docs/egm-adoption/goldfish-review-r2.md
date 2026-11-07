# Goldfish Review Report — Round 2

**Target:** `/home/hatch/workspace/plans/2026-11-06-egm-adoption-aep.md` (358 lines, after round-1 fixes)
**Round:** 2 of 5 (cap). Round 1: NOT CLEAN (3 Blockers, 35 Majors, 27 Nits). Round-1 fixes applied: 55 applied + 5 already present = all 60 PROPOSE FIX; bypassed: 1 CONTEST (zoom_out-1-8), 1 ESCALATE (zoom_out-1-1), 3 DECLINE (structural-1-6/1-7/1-8). Resolve report marked resolved.
**Verdict: NOT CLEAN**

**Findings by severity (unsettled): 3 Blockers, 63 Majors, 21 Nits (87 unsettled; 3 settled, see below).**

| Reviewer | Standard | Status | Blocker | Major | Nit |
|---|---|---|---|---|---|
| design_critic | feature-spec | completed | 1 | 13 | 5 |
| structural | feature-spec | completed | 0 | 9 | 7 |
| implementation_readiness | implementation-readiness | completed | 2 | 17 | 5 |
| comprehension | feature-spec | completed | 0 | 16 | 4 |
| zoom_out | zoom-out | completed | 0 | 10 | 1 |
| **Total** | | **5 completed, 0 not run** | **3** | **65** | **22** |

**Settled findings (not re-opened, excluded from the clean verdict):** 3. Per the skill's settled rule, a finding is settled when contested or recorded without a fix, and a new reviewer raising the same issue at the same scope does not re-open it.
- `zoom_out-2-4` (Environment A scope / YAGNI) — same scope and issue as round-1 `zoom_out-1-1` (ESCALATE, awaiting the owner's ruling). Settled.
- `zoom_out-2-10` (altitude drops / runbook detail) — same scope and issue as round-1 `zoom_out-1-8` (CONTEST, commands stay). Settled.
- `structural-2-14` (Appendix unnumbered) — same scope and issue as round-1 `structural-1-7` (DECLINE, Appendix unnumbered by convention). Settled.

**Clean-round rule:** a round is clean when no reviewer raises a Blocker or Major that is not settled. Round 2 has 3 unsettled Blockers and 63 unsettled Majors — NOT CLEAN. No clean rounds yet (round 1 not clean, round 2 not clean); convergence requires two consecutive clean rounds.

## FindingsList

### design_critic

#### design_critic-2-1 — Blocker — Lines 117, 264, 295: D3's path-form claim about the pilot is false; §10.4 step 4 sync check deterministically fails
Discrepancy: L117 states "Environment B uses the expanded absolute path `/home/hatch/workspace/egm/...` (the pilot already does this; `~` is never written into an adapted file)." On disk both pilot skills contain zero occurrences of `/home/hatch/workspace/egm` and 8 / 13 occurrences of `~/workspace/egm` respectively, including the routing line. L264 contradicts L117 ("absolute paths to `~/workspace/egm/`"). L295's sync check runs only `sed 's|/home/hatch/workspace/egm|../../reference/elephant-goldfish-model|g'`; simulated verbatim on copies of the pilot files it produces 0 replacements, so `diff -r` against repo wrappers can never report zero differences as written.
Rationale: the sync check is the sole mechanism proving local↔repo wrapper equivalence and cannot pass on the artifacts the pilot produced; the doc also asserts a fact about its own pilot that is false on inspection.

#### design_critic-2-2 — Major — Lines 78–80, 290, 317: vendored bundle's file set stated three incompatible ways; Phase 2 list undercounts by 51 files
Discrepancy: L317 claims the bundle is "39 files" (7 SKILL.md + 10 agents + 7 resources + 13 docs + LICENSE + plugin.json). The actual pristine bundle at `~/workspace/egm/` is 90 files: `skills/` holds 38 (each skill also has TEST.md, `agents/openai.yaml`, `assets/icon.svg`, `test_scenarios.yaml`, plus 3 `references/` files), `docs/` holds 33 (13 top-level plus 18 under `docs/designs/`, 1 asset SVG, 1 under `docs/verification/`). L78–80 says "tests" are not vendored, yet L290's `diff -rq` scope (whole `skills/`, `agents/`, `resources/`, `docs/`, LICENSE, `plugin.json`) includes the per-skill test files and expects zero differences.
Rationale: the vendor-integrity gate's input set is undefined; a PR author cannot determine from this doc what the bundle contains, and the 39-file scope understates the PR by >50%.

#### design_critic-2-3 — Major — Line 290: pinned-SHA verification command fetches current HEAD, not the pinned SHA
Discrepancy: `git clone --depth 1 ... && git rev-parse HEAD` prints whatever upstream HEAD is at execution time. It passes today only because HEAD still equals `e9e1f06a` (verified live); the first upstream commit after that date makes the check fail spuriously, and the check conflates "bundle matches the pin" with "upstream hasn't moved."
Rationale: a verification step that breaks on an event the doc itself anticipates (heads move daily) is not a verification step.

#### design_critic-2-4 — Major — Lines 52, 285: loop cost claimed mitigated but explicitly unbounded — no token budget, no per-reviewer timeout
Discrepancy: §6 lists "Loop cost — mitigation: bounds in §10.3," but §10.3 sets "no fixed per-reviewer timeout" and "no token budget … until pilot data exists." Bounds allow 5 rounds × 5 reviewers = 25 fresh-context spawns per loop, and the doc never states whether upstream's optional A/B duplication (two instances per reviewer) is used, which would double it to 50.
Rationale: the standard requires cost and scalability limits to be addressed; here the mitigation points at a section that expressly defers both controls. Each spawn re-reads persona + target + standard(s) + context, so cost scales with document size, which is also uncapped.

#### design_critic-2-5 — Major — Lines 35–38 (§4): Proposed Architecture is a one-sentence component map, not an architecture
Discrepancy: §4 lists the component chain in a single sentence and defers all detail to §§8–10, which are decision lists and install procedures, not a design. No data flow, no review-loop sequence (dispatch → report → checks → synthesize → fix → re-review), no artifact lifecycle or write paths, no concurrency model (parallel vs. sequential reviewers), no failure propagation (what happens to in-flight reviewers when one fails mid-round).
Rationale: the standard requires component layout, data flows, and ecosystem integration; a fresh reader cannot implement or reason about the loop's runtime behavior from this section.

#### design_critic-2-6 — Major — Lines 39–45 (§5): alternatives fail the standard's Alternatives Rule — no quantified rejection rationale, and the fork-source alternative is never evaluated
Discrepancy: all five rejections rest on unquantified assertions ("pollutes the skill catalog," "leaves design review informal," "no submodule precedent," "no artifact to version," "gated on pilot evidence") with no complexity, cost, performance, or scalability numbers. Two viable alternatives are missing: (a) sourcing from the user's fork — the repo's established convention, which D1 breaks with an explicit exception justified only by "the fork is a pure mirror and adds nothing," a property shared by most verbatim-vendored forks in the same README table; (b) minimal-subset vendoring — only the 2 pilot skills' dependencies — although the pilot installs the full bundle while adapting only 2 skills.
Rationale: the standard fails a spec that proposes a path without proving other viable designs were considered and rejected for specific documented reasons.

#### design_critic-2-7 — Major — Lines 49, 153–158 (D6), 273, 319–332: read-only mitigation is detection-only, technically incomplete, and its scope is undefined — for the doc's own principal risk
Discrepancy: (a) the non-repo snapshot is "file list + mtimes," which cannot detect in-place content edits with preserved mtime (only repo targets get content-sensitive `git status`); (b) snapshot scope is undefined — target repo only, or also `~/workspace/egm/`, `custom-skills/`, memory/DB paths a reviewer could reach?; (c) no rollback/restore procedure — detection discards the finding but leaves the mutation in place; (d) with parallel reviewers, a mutation cannot be attributed to one reviewer; (e) the memory prohibition is enforced only by discarding findings whose rationale cites memory — silent use is undetectable.
Rationale: §12 names this the principal risk in both environments; a mitigation that detects only some writes, in an undefined scope, with no recovery, does not close it.

#### design_critic-2-8 — Major — Lines 214–228 (§9.3), 257–270 (§10.2): Path 2's generic skill-loading mechanism is unspecified, and `<install-root>` is defined inconsistently
Discrepancy: §9.3 defines `<install-root>` with default `$HOME/egm` and example skill paths `$HOME/egm/agents/...`, with skills at `<install-root>/skills/egm-*/`. §10.2 maps `<install-root>` to `~/workspace`, with skills at `~/workspace/custom-skills/egm-*/` — a different directory name, not just a different root. A Path 2 installer following §9.3 literally creates `$HOME/egm/skills/egm-*/`, not the Environment B layout. No harness skill-discovery convention is cited for any generic harness; only Muse's `custom-skills/` convention is given (Environment B).
Rationale: "one vendored content set, two installation mechanisms" rests on a generic loading mechanism that is never specified; the two `<install-root>` definitions cannot both be followed.

#### design_critic-2-9 — Major — Lines 187–213 (§9.2), 234, 244: Path 1 install matrix is incomplete for 2 of the 6 harnesses named in §1, and the §9.5 step 3 fixture is not self-contained
Discrepancy: §1 names Muse, Claude Code, Codex, Cursor, OpenCode, Antigravity; §9.2 gives commands for Muse, Claude Code, Antigravity, and "Codex desktop" (listing only, no command — the Codex CLI command in `docs/harnesses.md` is omitted), while Cursor has no install entry at all and OpenCode has only a path pointer ("per the `adapters/opencode/` install path"). The E2E fixture (`muse-wonder-1.0`) is defined only by reference to upstream `TESTING.md`, which is excluded from the bundle and never quoted. "Against the installed cache only" is undefined (which cache, where, how it gets there on a fresh VM).
Rationale: Environment A's verification cannot be executed from the vendored content for half its harnesses, and the acceptance fixture is not reproducible from the artifacts this adoption produces.

#### design_critic-2-10 — Major — Lines 29, 45, 301–313: "gated on pilot evidence" has no pass/fail criterion, and the adoption goal has no quality bar
Discrepancy: L45 gates the remaining 5 skills "on pilot evidence" but no threshold is defined — no pilot outcome is stated to block Phase 1. The §2 adoption goal ("at least one design document reviewed via `egm-review-loop` within 30 days") would be satisfied as written by a review with reviewers not run, since the Phase 0 "0 not run" gate does not carry into it. No rollback/decommission plan exists if the pilot fails.
Rationale: a gate without a criterion is not a gate; the rollout's central evidence claim is unfalsifiable.

#### design_critic-2-11 — Major — Lines 308, 349, 301–313: the Phase 3 ruling is required before Phase 2 merges but no Phase 2 gate enforces it
Discrepancy: §14 decision 3 requires the owner ruling (provision a fresh VM, or mark Phase 3 documented-but-unexecuted and move §9 to an appendix) "before Phase 2 merges," but the Phase 2 gate lists only CI green, Conventional Commits, and owner review. The only enforcement is the Phase 3 gate failing later — after the merge the ruling was meant to precede. If the owner picks "documented-but-unexecuted," §9 moves to an appendix with no criteria for what counts as "documented."
Rationale: a sequencing requirement with no enforcing gate will be missed; the fallback silently guts the doc's stated scope.

#### design_critic-2-12 — Major — Lines 113, 129, 142, 295: `skill.yaml` has no ongoing drift coverage — only a one-time Phase 2 check
Discrepancy: the doc correctly states `skill.yaml` is excluded from the manifest and "covered by neither gate," with coverage being the Phase 2 YAML-parse + name-match check. But Phase 2 is a one-time PR event; §10.4 step 4 (the ongoing sync check) diffs `SKILL.md` only. Any later local edit to a `skill.yaml` (e.g. `description` drifting from the `SKILL.md` frontmatter) is undetected by skills-freshness and by the sync check, indefinitely.
Rationale: for a document whose value proposition is drift detection, a known-uncovered file class in the sync loop is an unmitigated drift surface the doc itself identifies and then leaves open.

#### design_critic-2-13 — Major — Lines 172–178 (Roles), 160–171 (D7): the synthesizer is dropped in Environment B with no dedup replacement, and "no nesting below depth 1" is asserted without a source
Discrepancy: upstream assigns the synthesizer aggregation, triage, and dedup; in Environment B it "is replaced by direct dispatch … with the Elephant consolidating findings," but no dedup/normalization procedure for the Elephant is specified — round 1 produced 65 findings across 5 reviewers with evident overlap. The nesting limit is presented as a platform constraint with no cited source; depth-2 spawning demonstrably works in this environment (this review itself runs as a depth-2 subagent spawned by a depth-1 parent).
Rationale: dropping a pipeline stage without specifying its replacement leaves finding consolidation undefined, and an unproven platform claim is doing load-bearing work in the dispatch design.

#### design_critic-2-14 — Major — Lines 31–34 (§3): the problem statement is unquantified — no baseline for the problem's magnitude in AEP
Discrepancy: no count of AEP design docs, no drift incidents, no review load. The "concrete evidence" offered is the pilot round-1 review of this very document — which demonstrates the instrument works, not the scale of the problem in AEP. The doc never says whether adoption is fixing observed drift or is precautionary.
Rationale: the standard's core principle requires a fresh reader to understand the business motivation, including its magnitude; without a baseline, the rollout's value cannot be weighed against its cost.

#### design_critic-2-15 — Nit — Line 129: the attribution Notes text does not do what the sentence requires
Discrepancy: "record the exception in the Notes column," but the specified Notes text is 'Adapted (D3); bundle under `reference/elephant-goldfish-model/`; pinned `e9e1f06a`.' — it never mentions the fork-naming-convention exception or its reason.

#### design_critic-2-16 — Nit — Lines 273, 287–296: the independent verifier's scope is stated two different ways
Discrepancy: §10.3 says the verification subagent "performs exactly these two checks," but the antecedent is ambiguous (line-existence + standard-name? or those plus the memory check = three?), while §10.4 step 3 describes broader verification ("did reviewers actually read persona/standards/target? were findings evidence-backed?").

#### design_critic-2-17 — Nit — Line 278: the readiness gate passes with an empty GoldfishContext
Discrepancy: "an empty list counts as provided," so a loop can start with zero context — yet for this document the pilot's context (companion doc, README, repo clone) was essential to the review.

#### design_critic-2-18 — Nit — Lines 321–322: "Skill content is pure markdown" is false for the bundle as a whole
Discrepancy: the vendored tree contains per-skill `openai.yaml`, `test_scenarios.yaml`, `icon.svg`, `references/*.json`, and `docs/assets/*.svg` — none of which is markdown. The claim is true only of the adapted `SKILL.md` files.

#### design_critic-2-19 — Nit — Lines 182–186, 238–245: `pytest` is noted absent with no install instruction, yet §9.5 step 2 requires it
Discrepancy: §9.1 notes "`pytest` installed separately (absent on this VM — required for `pytest tests/unit`)" but gives no install command or step; a fresh-VM implementer has a prerequisite with no procedure.

### structural

#### structural-2-1 — Major — Line 206: heading swallowed into paragraph
Discrepancy: `### Native installs for the other harnesses (commands from the bundle's docs/harnesses.md install table)` is appended inline to the end of the §9.2 paragraph (`…as plugin:egm:egm-*). ### Native installs…`), not on its own line. It therefore renders as plain text, not a heading, and the Claude Code / Antigravity / Codex / OpenCode installs (lines 208–212) have no heading at all.
Rationale: breaks heading hierarchy and the §9.2/§9.3 numbering symmetry; a reader scanning headings misses the whole non-Muse install subsection.

#### structural-2-2 — Major — Lines 140, 172: unnumbered H3s interrupt the D1–D7 decision sequence in §8
Discrepancy: `### AEP machinery` (line 140) sits between D4 (line 119) and D5 (line 144), and `### Roles & dispatch` (line 172) sits after D7 (line 160) under the same H2. Neither is a decision, neither carries a D-number, and neither is numbered 8.x.
Rationale: a reader expecting D1–D7 contiguous must skip a reference-glossary block mid-sequence; the decision list is not cleanly enumerable.

#### structural-2-3 — Major — Lines 283, 297: unnumbered H3s break the §10 numbering sequence and duplicate §10.4
Discrepancy: `### Loop bounds` (line 283) sits between `### 10.3 Dispatch` (271) and `### 10.4 Verification` (287), and `### Verification checks` (line 297) follows 10.4 as an unnumbered sibling. The latter restates §10.4 steps 1–4 as checks (1)–(5), including the same `agents/zoom_out.md:44` pilot check already in §9.5 step 4 (line 245) and §10.4.
Rationale: two overlapping verification specifications under near-identical headings, with colliding numbering — a citation to "check (1)" vs "step 1" is ambiguous, and §9.5 line 245's phrase "§10.4's Verification checks" conflates the two sections.

#### structural-2-4 — Major — Lines 225, 295, 313: dangling Issue references with no definition
Discrepancy: line 225 cites "Issue 25" and "Issue 49"; line 295 cites "Issue 17"; line 313 cites "Issue 37". No issue list, link, or definition exists anywhere in the document or Appendix, and no repository/URL is given.
Rationale: link-compliance gap — a fresh reader cannot resolve any of the four references; they function as unexplained pointers to an external tracker that is never named.

#### structural-2-5 — Major — Lines 41, 49–53: forward references to D-labels before they are defined
Discrepancy: §5 line 41 cites "(D4)" and §6 lines 49–53 cite D6 and §10.4/§10.3, but D1–D7 are only defined in §8 (lines 93–170).
Rationale: §§5–6 are not self-contained in reading order; the Alternatives/Risks sections depend on labels introduced ~50–100 lines later, forcing forward jumps with no up-front decision index.

#### structural-2-6 — Major — Lines 35–37: §4 Proposed Architecture is a stub
Discrepancy: the section required by the standard is a single 3-line paragraph that is only a component-map sentence plus "The existing §§8–10 keep their detail; this section is the map, with pointers to them."
Rationale: the core architecture section contains no architecture of its own — its substance lives in §8 (decisions) and §§9–10 (environments), which are not architecture sections — so the standard's component-layout/data-flow area is present in name only at its expected location.

#### structural-2-7 — Major — Lines 24–29 vs 334–342: Goals and Non-Goals split across the document
Discrepancy: the standard lists "Goals & Non-Goals" as one area. The doc puts "Goals" in §2 (lines 24–29) and "Non-goals" in §13 (lines 334–342), ~300 lines apart, with no cross-reference in either direction.
Rationale: the paired scope statement is structurally severed; a reader of §2 has no pointer to the exclusions that bound those goals.

#### structural-2-8 — Major — Line 142: `### AEP machinery` is a single-paragraph restatement of D4
Discrepancy: line 142 re-states, in one unbroken paragraph, the vendor-integrity / skills-freshness / manifest-format / scope-file / PROVENANCE-fields / vendor-sha256-command / attribution-row definitions already given in the D4 bullets (lines 121–129, including the identical `sha256sum` command from line 125).
Rationale: duplicate specification in a different shape (prose paragraph vs bullets) under a non-decision heading — the two copies can drift, and the reader cannot tell which is normative.

#### structural-2-9 — Major — Lines 273–281: §10.3 packs four topics under one heading with no subheadings
Discrepancy: `### 10.3 Dispatch` contains, in sequence, the reviewer brief (line 273), approval gates (274–276), the readiness/section-approval gate definitions (278), the overlap-with-existing-tools discussion (279), and the brief-contents/verbatim-prompt/failure-handling paragraph (281) — as bullets then unheaded paragraphs.
Rationale: asymmetric with §9, which splits the same material into numbered 9.1–9.5 subsections; §10.3 has no internal navigation for its five distinct topics.

#### structural-2-10 — Nit — Lines 24–35: Goals precede Problem Statement
Discrepancy: §2 Goals comes before §3 Problem Statement, inverting the standard's listed order (Problem, then Goals & Non-Goals).
Rationale: goals are stated before the problem they serve is introduced; minor ordering deviation, content is otherwise present.

#### structural-2-11 — Nit — Line 315: `### Phase 2 file-change list` unnumbered under §11
Discrepancy: same unnumbered-H3 pattern as lines 140/172/283/297, under `## 11. Rollout`. Should be 11.x or a bold lead-in.
Rationale: breaks the numbered-subsection symmetry of §§9–10.

#### structural-2-12 — Nit — Lines 21, 32–33: pathless report reference
Discrepancy: the pilot report is cited as bare filename `2026-11-06-egm-adoption-aep-goldfish-review.md` with no directory path or link.
Rationale: a fresh reader cannot locate the cited report from the citation alone.

#### structural-2-13 — Nit — Lines 49, 52: imprecise section pointers
Discrepancy: line 49 "(see §8)" for the D6 caveat points at the whole 88-line §8 rather than D6 (line 153); line 52 "bounds in §10.3" points at §10.3, but the bounds actually live in the unnumbered `### Loop bounds` block (lines 283–285), not in §10.3.
Rationale: pointers resolve to the wrong granularity, compounding the unnumbered-heading findings above.

#### structural-2-14 — Nit — Line 354: `## Appendix — Sources` unnumbered after numbered §§1–14
Discrepancy: the Appendix is an H2 with no number following a strictly numbered 1–14 sequence.
Rationale: minor inconsistency; conventional but breaks the document's own numbering scheme.
**Settled:** same scope and issue as round-1 `structural-1-7` (DECLINE — Appendix unnumbered by convention). Do not re-open.

#### structural-2-15 — Nit — Lines 24, 334: inconsistent capitalisation
Discrepancy: §2 is "Goals", §13 is "Non-goals" (lowercase g); §7's title carries a parenthetical qualifier "(verified)" that no other H2 uses.
Rationale: minor title-style inconsistency.

#### structural-2-16 — Nit — Lines 356–358: Appendix as three very long single-line bullets
Discrepancy: each Appendix bullet is a single long line packing up to six links (line 357) or seven references (line 358). Valid Markdown, but the densest formatting in the document.
Rationale: readability/navigation nit only; no link is malformed.

### implementation_readiness

#### implementation_readiness-2-1 — Blocker — Lines 317 vs 290: the Phase 2 vendored file set contradicts the §10.4 verification diff
Discrepancy: L317 lists the bundle as "39 files" — `skills/` (7 × `SKILL.md` only), `agents/` (10), `resources/` (7), `docs/` (13 files), `LICENSE`, `plugin.json`. The actual bundle at `~/workspace/egm/` contains 90 files: `skills/` alone has 38 files (per skill: `SKILL.md`, `TEST.md`, `agents/openai.yaml`, `assets/icon.svg`, `test_scenarios.yaml`, plus `references/` in two skills) and `docs/` has 33 files (including `docs/designs/` × 20, `docs/assets/`, `docs/verification/`). L290 then requires `diff -rq` of the bundle against the upstream subset expecting zero differences — a whole-directory diff that can only pass with the full 90-file tree. An implementer following L317 vendors an incomplete bundle that fails L290; following L290 vendors files L317 never lists.
Rationale: the standard's Target Scope & File Boundary requirement — the exact file boundary is the one thing this plan must pin down, and it states two incompatible boundaries.

#### implementation_readiness-2-2 — Blocker — Lines 295 + 117: the §10.4 step 4 sync check fails against the actual pilot artifacts
Discrepancy: L295's check runs `sed -i 's|/home/hatch/workspace/egm|../../reference/elephant-goldfish-model|g'` on copies of the local adapted `SKILL.md` files and expects zero diff vs the repo wrappers. But the pilot adapted skill `~/workspace/custom-skills/egm-review/SKILL.md:12` reads `In Muse, read ~/workspace/egm/docs/muse.md first.` — the `~` form, not the expanded path. This directly contradicts L117's assertion that "the pilot already does this; `~` is never written into an adapted file," and the L295 `sed` only replaces the `/home/hatch/...` form, so the `~/...` occurrences survive and the expected-zero diff fails. Additionally, "copy the seven … files to a temp dir" (singular) never specifies the 7-subdirectory layout that `diff -r` against `skills/egm-*/` requires.
Rationale: a specified verification step that deterministically fails on the existing pilot output is not a check — it blocks Phase 2 with no recovery path stated.

#### implementation_readiness-2-3 — Major — Lines 113 vs 266: `skill.yaml` production method contradicts itself
Discrepancy: D3 item 1 (L113) says `skill.yaml` is "hand-written (the repo norm — 61 `skill.yaml` files exist in `skills/` and no script generates them)," while §10.2 (L266) says `skill.yaml` is "generated from frontmatter" and §9.3 repeats "generated `skill.yaml`." No generator script, command, or template is named anywhere, so neither the hand-written nor the generated route is actually specified.
Rationale: the implementer must choose the production method for 7 required deliverables, and the two instructions point opposite ways.

#### implementation_readiness-2-4 — Major — Line 317: manifest regeneration command is broken as written
Discrepancy: "regenerated via `check_skills_manifest.py --write`" omits the `--root` argument that `scripts/check_skills_manifest.py` requires (`--root` is `required=True`; the `--check` form at L142 correctly shows `--root skills`). The command as written exits with an argparse error. Working directory is also unstated.
Rationale: a step that cannot run is an actionability gap, not a style issue; the correct invocation exists in the same document at L142 and should be used consistently.

#### implementation_readiness-2-5 — Major — Line 125: `PROVENANCE.md` vs `.sha256` generation order unspecified, and `PROVENANCE.md` field values undetermined
Discrepancy: L125 lists sha-file generation and `PROVENANCE.md` writing in one bullet with no order. `PROVENANCE.md` lives inside the vendored tree, and the esf precedent (verified: `.github/vendor-esf.sha256` contains `./PROVENANCE.md`) shows it must be included in the sha file — generating the sha file first leaves it unlisted, so the vendor-integrity unlisted-files check fails. Separately, the field values are not given: "Pinned commit (+ subject)" — the commit subject string appears nowhere in the document; "Snapshot date" format is unspecified; "Excluded from the vendor" content is unspecified.
Rationale: ordering is load-bearing for the CI gate, and the deliverable's content is left for the implementer to compose.

#### implementation_readiness-2-6 — Major — Line 129: attribution-row instruction contradicts its own literal Notes text
Discrepancy: L129 instructs "record the exception in the Notes column" (the exception to the README's fork-naming convention), then prescribes Notes verbatim as `'Adapted (D3); bundle under reference/elephant-goldfish-model/; pinned e9e1f06a.'` — which contains no mention of the fork-naming exception. An implementer copying the given text violates the instruction; an implementer following the instruction must invent the exception wording. (Same literal text repeated at L142.)
Rationale: internal contradiction on a required deliverable; the README convention it excepts from is verified real.

#### implementation_readiness-2-7 — Major — Lines 116–117: path-rewrite procedure unspecified; two wordings of the Muse routing line
Discrepancy: the mapping table is given, but no mechanism (sed command, script, manual edit), no search pattern, and no occurrence counts for the 5 non-pilot skills (counts are given only for the two pilot skills, with no procedure to compute the rest). The routing line also appears in two forms: L116 `*"In Muse, read `docs/muse.md` first."* vs L117 `In Muse, read <bundle>/docs/muse.md first.` (the pilot uses the latter, with `~`). The mapping's bare `agents/` → `<bundle>/agents/` form also does not cover the pilot's already-absolute `~/workspace/egm/agents/...` references.
Rationale: the D3 adaptation is the core per-file transformation of this plan (7 files × ~10 references each) and its execution is left to implementer inference.

#### implementation_readiness-2-8 — Major — Lines 125, 317: the tenth `vendor-integrity` `run:` block has no content
Discrepancy: "Same `sha256sum -c` + unlisted-files + symlink pattern as the existing nine blocks" — no YAML text, no placement/order within the job (after `humanizer`? alphabetical? insertion point matters for reviewability). The pattern is visible in the repo (verified: 9 blocks in `ci.yml`, each `cd reference/<tree>` + `sha256sum -c` + `comm -23` unlisted-files check + broken-symlink loop), but the plan requires the implementer to reconstruct it by analogy rather than supplying it.
Rationale: the standard requires precise logic changes per file; a CI job edit that gates the whole PR should be spelled out, not inferred.

#### implementation_readiness-2-9 — Major — Lines 184, 243: `pytest` prerequisite has no install step; `pytest tests/unit` has no working directory or expected result
Discrepancy: L184 admits pytest is "absent on this VM — required for `pytest tests/unit`" and gives no install command (pip/apt/venv, version pin). L243 gives the bare command with no cwd (cloned repo root is implied, never stated) and no pass criterion (all tests pass? exit code 0? known failures?).
Rationale: a verification step with no setup and no expected outcome cannot be executed or judged by a fresh implementer.

#### implementation_readiness-2-10 — Major — Line 244: the §9.5 step 3 E2E fixture is not executable as specified
Discrepancy: "Run headless via `muse exec` in a temporary workspace against the installed cache only" — no `muse exec` command line, no prompt text, no temporary-workspace path, no definition of "the installed cache," and no pass/fail criteria beyond the stage sequence "brainstorm → draft → uninterrupted review." The hand-exercise variant says to "record which gates fired" with no recording destination. The fixture design `muse-wonder-1.0` is named but its location/contents are not given.
Rationale: the standard's Test Plan requirement — the acceptance test for Environment A is described, not specified.

#### implementation_readiness-2-11 — Major — Lines 214–236 (§9.3): Path 2 has no install steps at all
Discrepancy: §9.3 is layout description only (bundle at `<install-root>/egm/`, skills at `<install-root>/skills/egm-*/`, gate-scan "where available"). There is no command to obtain the bundle (clone? copy from where?), no copy step, no adaptation step invoking D3, and no `skill.yaml` creation step. This matters because Path 2 is the fallback for every headless VM and the template for Environment B.
Rationale: an install path with zero executable steps is a design summary, not an implementation plan.

#### implementation_readiness-2-12 — Major — §11 (Lines 301–313) + Lines 257–269: no file-change lists for Phase 0 or Phase 1; local bundle README content unspecified
Discrepancy: only Phase 2 has a file-change list. Phase 0 ("bundle under `~/workspace/egm/`, 2 adapted skills") and Phase 1 ("remaining 5 skills") name no files — which bundle files (39 or 90, per Blocker 1?), which two skills' exact paths, and the Phase 1 drift-report destination are all unstated. L262 lists the local `README.md` pin-record fields but gives no values, format, or date format, and "re-written on every re-sync" has no trigger definition beyond L269's cadence sentence.
Rationale: the standard requires phased work with an explicit file boundary per phase; two of four phases have none.

#### implementation_readiness-2-13 — Major — Line 269: the live→repo sync procedure is referenced, not specified
Discrepancy: "Same procedure as the 2026-11-06 skill sync" — no script, command, source/destination mapping, or document reference is given. A fresh implementer cannot execute the sync that keeps the canonical AEP wrappers and the local adapted skills consistent, which is the plan's own stated drift control.
Rationale: a procedure defined only by pointing at a past event is not an actionable step.

#### implementation_readiness-2-14 — Major — Line 285: no per-reviewer timeout is set, and no owner decision exists to set it
Discrepancy: "Timeout: no fixed per-reviewer timeout is set in this document — the pilot log records per-reviewer elapsed time, and the timeout for Phase 1 is set from that evidence by the owner." §14 lists four owner decisions; none covers the timeout, its default, or its decision procedure. Phase 1's review loop therefore cannot run bounded, and "propagate failures and timeouts" has no timeout to propagate.
Rationale: an explicitly deferred parameter with no owner-decision hook is a design choice left open, violating the zero-decision rule.

#### implementation_readiness-2-15 — Major — Lines 291–292 + 348: the Phase 0 pilot target is unnamed
Discrepancy: §10.4 step 3 says run the loop "once against a real design document" with no document named; §14 decision 2 says "the AEP repo, with a PR as the target state" — a repo/PR, not a document — and no PR number or document path is given. The pilot's pass criterion ("all reviewers run, report filed") cannot be attempted until the implementer chooses the target.
Rationale: the pilot is the evidence gate for the remaining 5 skills; its target is a decision the plan must pre-determine.

#### implementation_readiness-2-16 — Major — Line 290: the pinned-SHA fetch step is unexecutable as written
Discrepancy: `git clone --depth 1 <url> /tmp/egm-upstream && git rev-parse HEAD` fetches the *current* upstream HEAD, not the pinned `e9e1f06a`; the moment upstream moves, the check fails with no recovery command (no `git fetch <sha>` / checkout-at-SHA step). The expected output is written as `` `e9e1f06a…` `` — an ellipsis, not a testable string. The subsequent "`diff -rq` the bundle against the upstream subset" gives no concrete command (which two paths, how exclusions are handled).
Rationale: a verification gate whose own commands cannot produce the stated expectation, with no fallback, blocks Phase 0/2 on upstream movement outside the implementer's control.

#### implementation_readiness-2-17 — Major — Line 158 (D6): the non-repo snapshot procedure is unspecified
Discrepancy: "File list + mtimes for a non-repo target" — no command (`find`? `stat`?), no snapshot storage location, no diff command, and no definition of "unexpected modification" (mtime-only change vs content change?). This is the enforcement mechanism for the plan's self-declared principal risk (reviewers are not actually read-only on Muse), and its non-repo form is left to implementer invention.
Rationale: the mitigation for the top risk must be at least as specified as the risk is emphasized.

#### implementation_readiness-2-18 — Major — Line 299: verification check (1) permits "by script or by hand" with no script
Discrepancy: "Check by script or by hand against the mapping table" names no script, no command, and no expected output for resolving every `agents/...` and `resources/...` reference across 7 skills. "By hand" is an allowed method for a check whose failure mode (one dangling reference) is the exact coupling risk recorded in §6.
Rationale: the standard requires specific test cases; a verification step whose method is "whatever the implementer chooses" is not a test plan.

#### implementation_readiness-2-19 — Major — §11 Phase 3 (Lines 301–313) + Line 349: Phase 3 is not implementable
Discrepancy: Phase 3 ("Path 1 install guide + Path 2 vendored layout validated on a fresh VM") contains no VM specification, no provisioning steps, no install commands beyond §9.2/§9.3, and no pass criteria beyond "E2E fixture passes." It is gated on §14 decision 3 (provision a fresh VM vs mark documented-but-unexecuted), which offers two options with no selection criteria, and the §11 gate makes an unexecuted Phase 3 without that ruling a failure — so the phase is simultaneously unexecutable and failing-by-default.
Rationale: a phase with no steps and an undecided existence cannot be executed; the document acknowledges it as "Provisional" but does not make it actionable.

#### implementation_readiness-2-20 — Nit — Line 113: `skill.yaml` titles for 6 of 7 skills unspecified
Discrepancy: only the example `egm-review` → `EGM Review` is given. Derivation (Title Case of the skill name) is near-mechanical, but the exact title strings for `egm-brainstorm`, `egm-draft`, `egm-resolve`, `egm-review-loop`, `egm-bootstrap`, `egm-drift-report` are never stated, and the upstream frontmatter carries no `title` field to copy.
Rationale: a required field in 7 deliverables should be enumerated, not derived.

#### implementation_readiness-2-21 — Nit — Line 151: pilot log filename and PR-body score-line format unspecified
Discrepancy: scores go in "the pilot log file under `~/workspace/plans/`" (no filename pattern, unlike the dated report filename given in §1) and in the PR body as "one line per skill: name, score, pass/block" (no literal format).
Rationale: two records the gates depend on have no defined form.

#### implementation_readiness-2-22 — Nit — Line 285: "unsettled" is undefined in the convergence rule
Discrepancy: "Converged = two consecutive clean rounds (no unsettled Blocker or Major)" — "unsettled" is never defined (resolved? withdrawn? dismissed? deferred to a later phase?). Two reviewers could reasonably disagree on whether a round is clean.
Rationale: the loop's stop condition needs one sentence of definition.

#### implementation_readiness-2-23 — Nit — Lines 187–212 (Path 1): approval scope ambiguous; clone destination implicit
Discrepancy: "Approval is required once" and "the ten agent definitions need `approve` before activation" never state whether the single `muse plugins approve egm` command covers the agent definitions or whether each needs separate approval. `git clone <url>` with no destination argument relies on the default directory name (`elephant-goldfish-model`), which the next command depends on but never states.
Rationale: both are one-line clarifications that remove implementer guessing.

#### implementation_readiness-2-24 — Nit — §11 Phase 1 gate (Lines 301–313): Phase 1 drift-report destination unstated
Discrepancy: the gate requires a dated finding or clean bill, but no filename or destination is given for the Phase 1 run. §7's pilot convention (`~/workspace/plans/<date>-<topic>-drift.md`) is a local pilot path; the Phase 1 target is the repo `skills/` tree, so the destination is genuinely ambiguous.
Rationale: a gate deliverable with no stated location cannot be verified as filed.

### comprehension

#### comprehension-2-1 — Major — §4, lines 35–37: Proposed Architecture is a label chain, not an architecture
Discrepancy: the section lists components joined by arrows (bundle → adapted skills → gates → dispatch → artifacts) and defers all detail to §§8–10, with no data flow, no sequencing (e.g. when gate-scan runs relative to dispatch, who invokes which gate), and no ecosystem integration.
Rationale: the assigned standard requires component layout, data flows, and ecosystem integration; a fresh reader cannot reconstruct how a skill invocation actually flows through this system from §4.

#### comprehension-2-2 — Major — §1, lines 16–18; §7, lines 85–89; §9.2, lines 191–206; §10.1, lines 251–254: "Muse" vs `muse` CLI is ambiguous
Discrepancy: "Muse" is used both for the harness/CLI (Muse ≥ 1.4.14, `muse plugins install`) and for the current environment ("current Muse environment: this VM, where … there is no `muse` CLI").
Rationale: a fresh reader cannot tell whether "Muse" means the assistant, the CLI product, or this VM's environment — and therefore cannot tell which Muse sentences apply to Environment A vs B.

#### comprehension-2-3 — Major — §1, line 18; §4, line 37; §10.3, lines 273, 281: `subagent.spawn` is never defined
Discrepancy: it is the sole dispatch mechanism in Environment B, but the document never says what it is (a Muse tool? a shell command? an API), what arguments it takes, or where its behaviour is documented.
Rationale: assumed workflow prerequisite — the reader is told dispatch "runs through `subagent.spawn`" with no way to learn how to invoke it.

#### comprehension-2-4 — Major — §10.3, lines 278, 281: `GoldfishContext` is undefined in this document
Discrepancy: it appears as a readiness-gate condition ("provided — an empty list counts as provided") and as brief item (4) ("GoldfishContext paths"), but nowhere does the document say what it contains (files? directories? URLs?), what format it takes, or what it is for. It is defined in the vendored bundle as a reading list in `egm-review/SKILL.md`, but the target document neither defines it nor links to that definition.
Rationale: a gate whose input is undefined cannot be evaluated, and "empty counts as provided" makes the gate's purpose unintelligible without the definition.

#### comprehension-2-5 — Major — §10.3, lines 273, 281, 285: "the driver" is an undefined actor
Discrepancy: the driver "checks every cited line exists," "checks the named standard," and "stops and asks the owner" on cap/churn — but the Roles table (§8, lines 172–178) names only Elephant, Goldfish, and Synthesizer, and §10.3 also says the Elephant consolidates findings.
Rationale: the reader cannot tell whether driver = Elephant, a separate script, or a harness feature, so responsibility for the two verification checks is unassigned.

#### comprehension-2-6 — Major — §10.3, line 281: "the verbatim prompt" is defined circularly
Discrepancy: it is "the review instruction formed from the skill's Delegation section plus the target," but the Delegation section is never quoted, located by path, or linked, and no example brief is given.
Rationale: the reader cannot construct the reviewer brief the document mandates, since the source it is "formed from" is not identified in the document.

#### comprehension-2-7 — Major — §9.3, line 225; §10.4, line 295; §11, line 313: dangling "Issue N" references
Discrepancy: "invocation in Issue 25", "defined in Issue 49", "(see Issue 17)", "(see Issue 37)" name no repository, tracker, link, or issue title anywhere in the document.
Rationale: load-bearing pointers — the Path 2 gate-scan fallback (§9.3) and the sync-check `~` rule (§10.4) depend on them — that a fresh reader cannot resolve.

#### comprehension-2-8 — Major — §8 D3 item 1, line 113 vs §9.3, line 222 and §10.2, line 266: `skill.yaml` is both "hand-written" and "generated"
Discrepancy: D3 says each `skill.yaml` is "hand-written (the repo norm … no script generates them)"; §9.3 calls it "generated `skill.yaml`" and §10.2's layout says "`skill.yaml` # generated from frontmatter". No generator is named.
Rationale: direct contradiction on how the file is produced — a fresh reader cannot know whether to write it by hand or run a generator (and no generator is named).

#### comprehension-2-9 — Major — §9.3, line 227: `<install-root>` mapping is self-contradictory
Discrepancy: `<install-root>` defaults to `$HOME/egm`, yet the Environment B mapping sets `<install-root>` = `~/workspace`, and the example strings `$HOME/egm/agents/design_critic.md` are then said to "read `/home/hatch/workspace/egm/agents/design_critic.md`" — but `$HOME/egm` under `$HOME` = `/home/hatch` is `/home/hatch/egm`, not `/home/hatch/workspace/egm`. The generic template (`<install-root>/skills/egm-*/`) also does not literally hold in Environment B (`custom-skills/`, not `skills/`), and the stated mapping does not resolve the discrepancy.
Rationale: the path scheme cannot be paraphrased consistently; the generic template and the stated mapping disagree.

#### comprehension-2-10 — Major — §9.2, lines 206–212: native installs for Cursor and OpenCode have no actionable step; Codex/ChatGPT and Antigravity App are vague
Discrepancy: Cursor is listed as a supported harness (§1, line 14; §9.4, line 234) but gets no install command at all; OpenCode is only "per the `adapters/opencode/` install path in the bundle" with no command; Codex/ChatGPT desktop is "install the published EGM plugin (desktop-only listing)" with no listing name or link; Antigravity App is "run `/plugin`" with no stated context.
Rationale: unlike the Muse/Claude/Antigravity-CLI rows, these rows cannot be executed from the document alone.

#### comprehension-2-11 — Major — §9.5, step 3, line 244: the E2E fixture cannot be run from this description
Discrepancy: the fixture `muse-wonder-1.0` ("line-count design") is to be run "headless via `muse exec` in a temporary workspace against the installed cache only," but no command, workspace path, cache location, or definition of "installed cache" or "line-count design" is given, and `TESTING.md` (where the fixture is "recorded") has no path — upstream repo, bundle, or elsewhere.
Rationale: assumed workflow prerequisite for the acceptance test that gates Phases 1 and 3.

#### comprehension-2-12 — Major — §10.2, line 269: the sync procedure is cited, not described
Discrepancy: "Same procedure as the 2026-11-06 skill sync" gives no file, link, or steps, and "Owner: the agent running the sync" is circular — it names no role or person.
Rationale: the canonical-direction rule (§6 "dual-install drift" mitigation) rests on a procedure the reader cannot locate or reproduce.

#### comprehension-2-13 — Major — §14, decision 2, line 348: Phase 0 pilot target is unspecified
Discrepancy: "The AEP repo, with a PR as the target state (owner-directed 2026-11-06)" names no PR number, branch, or document.
Rationale: the pilot gate (§2, §11) requires a completed review of a target the reader cannot identify.

#### comprehension-2-14 — Major — §14, decision 3, lines 349–350 vs §9, line 180: the required provisional header note is absent
Discrepancy: decision 3 says "Until ruled, §9 carries the header note 'Provisional — validation pending owner provisioning.'" — but §9 as written carries no such note.
Rationale: the document instructs the reader to rely on a marker that is not present, so the provisional status of §9 is unverifiable from the text.

#### comprehension-2-15 — Major — §11, lines 305–308, esp. Phase 3 gate, line 308: Phase 3 gate is near-unparseable
Discrepancy: "Fails when the fixture fails or when Phase 3 is unexecuted past the owner ruling required by §14 decision 3 — an unexecuted Phase 3 without that ruling fails the gate rather than passing by default" requires the reader to untangle a double conditional across two sections to learn when an unexecuted phase passes vs fails.
Rationale: a gate condition that must be re-read several times to parse is a clarity defect in a normative table.

#### comprehension-2-16 — Major — §1, lines 22–23 and §3, line 33: the pilot report is cited without a locatable path
Discrepancy: the report `2026-11-06-egm-adoption-aep-goldfish-review.md` is given as a bare filename with no directory, and §3's "all 5 reviewers completed" never names which 5 of the 10 personas ran.
Rationale: the document's central evidence (65 findings) cannot be checked or reproduced from the citations given.

#### comprehension-2-17 — Nit — §7, line 78: "the Astro docs site (`site/`)" — "Astro" is undefined
Discrepancy: no expansion or link explains that Astro is the static-site generator the docs site is built with, or why that matters to the exclusion.
Rationale: a project-specific term used without definition; low impact since it only explains an exclusion.

#### comprehension-2-18 — Nit — §8 D7, lines 162–163: `trusted_enabled` and `agent_definition_unavailable` are unexplained status/error strings
Discrepancy: the reader is told named definitions "report `trusted_enabled` but spawning one is rejected (`agent_definition_unavailable`)" with no gloss of what either value means.
Rationale: the failure mode is inferable from context ("rejected"), but a fresh reader cannot tell whether `trusted_enabled` is an approval state, a capability flag, or something else.

#### comprehension-2-19 — Nit — §8 D4, lines 124–125: `reference/esf` is used as the pattern exemplar without expansion
Discrepancy: the `PROVENANCE.md` fields are said to follow "the esf pattern's fields," but `esf` is never expanded or described.
Rationale: a fresh reader cannot know what `esf` is without opening the repo tree; the fields themselves are listed, so the gap is minor.

#### comprehension-2-20 — Nit — §6, line 52 and §10.3, lines 283–285: "Loop cost" has no unit and its mitigation is not a cost bound
Discrepancy: the mitigation is "bounds in §10.3," but §10.3's bounds are round/reviewer caps and it explicitly states "no token budget is set until pilot data exists."
Rationale: the reader cannot tell what "cost" is measured in (tokens, time, money) or what would count as too costly.

### zoom_out

#### zoom_out-2-1 — Major — Lines 42, 279 (§5, §10.3): "Extend the existing instruments" rejected in one sentence, with no comparative evidence — reinventing the wheel
Discrepancy: §5 rejects extending `grilling` + `roundtable_review` + Ralph verifier as "leaves design review informal and unstandardized." But `roundtable_review` (verified in the repo) already implements parallel fresh-context reviewers, debate rounds, claim verification with VERIFIED/INACCURATE/HALLUCINATED labels, a completeness audit, and a judge's verdict — i.e. most of what §10.3 claims EGM uniquely adds ("written standard, configured reviewer panel, fresh-context reviewers"). The genuinely new delta is the five written standards files, which could be vendored as review inputs to the existing panel. No control run exists (roundtable was never run on this document as a baseline), so the 65-finding pilot does not establish marginal value over the incumbent.
Rationale: adopting a second panel system (2,810-line bundle + 7 wrappers + 2 gates) without a feature-by-feature delta against the tool already in the catalog.

#### zoom_out-2-2 — Major — Lines 22, 33 (§1, §3): Root-problem evidence is circular and n=1
Discrepancy: both the Purpose and the Problem Statement cite the same single data point: the pilot round-1 review of *this document itself*, run with the instrument being justified. A review of its own adoption doc by its own reviewers cannot establish that design review is generally missing or that EGM is the right fix — it is self-referential bootstrapping, not independent evidence. No design document outside this adoption pair has been reviewed.
Rationale: the root-problem claim rests on one self-review; the justification and the thing justified are the same event.

#### zoom_out-2-3 — Major — Line 29 (§2): Adoption bar is one use in 30 days; demand is never quantified
Discrepancy: the success criterion is "at least one design document reviewed via `egm-review-loop` within 30 days of merge." Nothing in the document states how many design docs per month AEP (as opposed to NeuroStrata, whose real targets live in the companion doc) actually produces, or what review volume justifies a 7-skill adoption plus a vendored bundle plus two CI gates.
Rationale: YAGNI — a permanent catalog addition with ongoing sync/rename risk is being justified by a single future use.

#### zoom_out-2-4 — Major — §9, line 308 (§11 Phase 3), line 349 (§14 decision 3): Environment A / general-VM scope is speculative and should not be in this adoption
Discrepancy: §9 specifies install paths for six harnesses on a fresh VM that does not exist, with no evidenced request for a general-VM install; Phase 3 is unexecuted pending an owner provisioning ruling, and §14.3 itself proposes moving §9 to an appendix if unruled. One document covering two deployment targets × two install paths is what creates the dual-install drift risk §6 then has to mitigate.
Rationale: YAGNI — cut §9/Phase 3 to a follow-up document gated on local pilot evidence; the local adoption does not need a second deployment target to be decided now.
**Settled:** same scope and issue as round-1 `zoom_out-1-1` (ESCALATE — Environment A scope is the owner's stated instruction, awaiting the owner's ruling). Do not re-open.

#### zoom_out-2-5 — Major — Lines 45, 279, 317 (§5, §10.3, §11): All 7 skills vendored in Phase 2 despite the stated gating and deferral
Discrepancy: §5 says the remaining 5 skills are "gated on pilot evidence" and `egm-bootstrap`/`egm-drift-report` are "deferred to Phase 1," yet the Phase 2 file-change list installs all 7 wrappers and the whole bundle. The gate as written is "pilot completes," not "pilot proves value," so the gating is timing, not scope. §11's own rationale admits drift-report and bootstrap "need a reviewed design corpus to work against" that does not yet exist — and §10.3 then invents targets for them (README attribution table vs. `skills/` tree; `reference/` READMEs) to justify their inclusion.
Rationale: vendoring skills with no corpus and no real named target is speculative scope; pilot the 2 review skills and gate each of the other 5 on a real target.

#### zoom_out-2-6 — Major — Lines 107, 121 (D2) vs. lines 290, 317 (§10.4, §11): "Bundle intact / verbatim / moves as one unit" contradicts the selective 39-file vendor
Discrepancy: D2 claims the bundle moves as one intact verbatim unit, but the Phase 2 list vendors only 39 files. The local bundle at `~/workspace/egm/` contains 90 files — the 39-file list silently drops `TEST.md`, `agents/openai.yaml`, `assets/icon.svg`, `references/` and `test_scenarios.yaml` (per skill), `docs/designs/` (23 files), `docs/assets/`, and `docs/verification/`, with no exclusion rule stated for any of them. §10.4 step 2's `diff -rq` over whole `skills/`/`docs/` directories expecting zero differences would fail against upstream unless that stripping is defined.
Rationale: the core D2 scope claim ("intact") and the actual file list disagree by 51 files; the vendor subset is undefined.

#### zoom_out-2-7 — Major — Lines 113, 121, 129, 131, 137 (D3–D4) + §10.2: Wrapper→bundle coupling is a new architectural pattern that creates the coverage hole it then patches bespoke
Discrepancy: verified — no existing skill loads from a `reference/<tree>/` path, so D4 introduces a repo-first coupling (rename either tree silently breaks all 7 skills), split across two gates (vendor-integrity for the bundle, skills-freshness for wrappers). The hand-written `skill.yaml` files are covered by *neither* gate (stated twice, lines 113 and 129), so a third bespoke mechanism — a YAML-parse + name-match check — is invented to cover a gap the wrapper design itself created. §10.2 adds split canonicality on top: AEP canonical for wrappers, local bundle canonical for personas/standards, glued by a `sed` normalize-then-diff sync check (§10.4 step 4).
Rationale: the design manufactures coupling, a coverage hole, and bespoke glue; simpler alternatives (adapted skills inside the bundle tree, or local-only adoption until AEP need is proven) are not evaluated — the "accepted explicitly" in D4 is doing the work of an architecture decision without an owner ruling attached.

#### zoom_out-2-8 — Major — Line 158 (D6): Read-only "enforcement" is detection after the write, not prevention — a workaround elevated to the principal safety mechanism
Discrepancy: D6 admits there is no tool-restriction mechanism on Muse and the mitigation is a post-run snapshot diff: a reviewer that writes is caught only after the modification exists, and the round (not the filesystem change) "fails." The document calls this "fail-closed," but it is fail-closed for the review round, not for the tree/daemon/database — the damage is done before detection, and every run pays per-reviewer snapshot overhead for it.
Rationale: the principal risk in both environments rests on a detective control mislabeled as enforcement; the residual risk (write-before-detection) should be stated, not papered over.

#### zoom_out-2-9 — Major — §10.3 Loop bounds, line 285: Unbounded loop cost in the very phase meant to measure cost
Discrepancy: up to 5 rounds × 5 reviewers = 25 fresh-context reviewer spawns per run, with explicitly "no fixed per-reviewer timeout" and "no token budget … until pilot data exists." The pilot — the run that is supposed to generate the cost evidence — itself runs without a cost bound.
Rationale: cost control deferred until after the spend it is meant to control; set a pilot cap (rounds/reviewers/timeout) now, from the round-1 pilot already run, instead of after.

#### zoom_out-2-10 — Major — Altitude drops (weeds) throughout: a strategy document carrying runbook detail, including duplicated normative commands
Discrepancy: examples — per-skill line counts (§7); per-skill reference occurrence counts (D3); exact `sha256sum` generation command stated in D4 and again in the "AEP machinery" paragraph; exact `git clone --depth 1 … && git rev-parse HEAD` and `sed -i 's|…|…|g'` commands (§10.4 steps 2, 4); the `egm-draft` gate question quoted verbatim twice (§10.3); the 39-file change list (§11, line 317). Duplicated normative detail can drift — the exact failure mode this adoption exists to detect.
Rationale: implementation/runbook content belongs in the PR body and verification scripts, not in the design strategy; the document should state interfaces, decisions, and gates, and point at the runbook.
**Settled:** same scope and issue as round-1 `zoom_out-1-8` (CONTEST — executable detail belongs in the design per its stated purpose; commands stay). Do not re-open.

#### zoom_out-2-11 — Nit — Duplicated definitional text
Discrepancy: the 65-finding evidence appears in both §1 (line 22) and §3 (line 33); "'Verify outputs' means the two checks in D6 … nothing else" is stated twice in the same paragraph (line 158); the gate question is quoted verbatim twice in §10.3.
Rationale: trim to single sources of truth.
