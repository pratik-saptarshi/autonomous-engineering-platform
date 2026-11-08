Status: resolved

# Goldfish Annotated Review Report — Round 3

**Target:** `/home/hatch/workspace/plans/2026-11-06-egm-adoption-aep.md` (415 lines)

**Round:** 3 of 5 (cap). Rounds 1 and 2 both NOT CLEAN (0 clean rounds so far).

**Counts:** 93 findings = **87 PROPOSE FIX + 1 CONTEST + 0 new ESCALATE + 1 DECLINE + 4 SETTLED.**

By reviewer: design_critic 17 PROPOSE FIX; structural 12 PROPOSE FIX + 1 DECLINE + 2 SETTLED + 5 PROPOSE FIX (Nits) = 17 PROPOSE FIX + 1 DECLINE + 2 SETTLED; implementation_readiness 19 PROPOSE FIX; comprehension 26 PROPOSE FIX; zoom_out 8 PROPOSE FIX + 1 CONTEST + 2 SETTLED.

- **CONTEST:** 1 (Issue 88).
- **ESCALATE:** 0 new. The one live ESCALATE remains the round-1 item `zoom_out-1-1` (Environment A scope), carried by settled Issue 85, still awaiting the owner's ruling.
- **DECLINE:** 1 (Issue 31).
- **SETTLED:** 4 (Issues 32, 35, 85, 89).

## Shared edits (defined once, referenced by number)

- **E-A — Phase 2 two-skill variant + decision-3 decoupling + §5 temporal fix (Issues 10, 46, 58, 72):** (1) §5 Subset bullet: replace "Without that ruling, Phase 2 installs the 2 review skills only; `egm-bootstrap` and `egm-drift-report` deferred to Phase 1." with "Without that ruling, Phase 2 installs the 2 review skills only (`egm-review`, `egm-review-loop`); the remaining 5 skills are held until the ruling." (2) §11.1: append a 2-skill variant paragraph (see Issue 46). (3) §11 Phase 2 gate row: delete "; §14 decision 3 ruled (fresh VM provisioned, or Phase 3 marked documented-but-unexecuted with §9 moved to an appendix)". (4) §14 decision 3: replace "(required before Phase 2 merges)" with "(required before Phase 3 runs; it does not gate Phase 2)".
- **E-B — D3 idempotency + check C1 extension + vacuous example replacement (Issues 12, 42):** (1) D3 item 3 Mechanism: replace "Mechanism: apply the mapping mechanically (one `sed` per row, or manual edit) and verify with §10.6 Verification check (1)." with "Mechanism: apply the mapping mechanically (one `sed` per row, or manual edit) and verify with §10.6 Verification check C1. Idempotency guard: before applying, assert the file contains no `<bundle>/` prefix (`grep -q '<bundle>/' <file>` must find nothing); re-running the mapping on an already-adapted file is an error, not a no-op. Example literal command for the first row: `sed -i '/<bundle>\\/agents/!s|agents/|<bundle>/agents/|g' <file>`." (2) §10.6 check C1: extend the grep to `(agents|resources|docs)/[A-Za-z0-9_./-]+`, require the resolved path to be a regular file (`test -f`, not `test -e`), and add: "also assert the Muse routing line is present in each adapted `SKILL.md` and no upstream-relative reference (`../../docs/`, `${CLAUDE_PLUGIN_ROOT}/docs/`) remains." (3) Replace the vacuous persona-internal example in D3 item 3, §9.5 step 4, and §10.6: "Persona-internal references (`agents/zoom_out.md:44`, `agents/synthesizer.md:38`) resolve against the bundle root; the pilot verifies one such reference resolves in each environment" → "The pilot verifies the Muse routing line's target (`<bundle>/docs/muse.md`) resolves in each environment." Delete the `agents/zoom_out.md:44` / `agents/synthesizer.md:38` claims everywhere they appear (D3 item 3, §9.5 step 4, §10.6 last sentence).
- **E-C — Delete §8.1; move §8.2 roles table to §10.3 (Issues 21, 26, 75):** Delete the `### 8.1 AEP machinery` subsection (lines 196–198) entirely. Move the `### 8.2 Roles & dispatch` table to §10.3 as its opening (new `#### 10.3.0 Roles & dispatch` — no: keep the table under a `### Roles & dispatch` heading placed immediately before `#### 10.3.1 Reviewer brief`, i.e. the table becomes the §10.3 introduction). §8 then contains only D1–D7. All cross-references to §8.1/§8.2 become references to §10.3.
- **E-D — §11.1–11.3 renumber + split headings (Issues 23, 24):** `### 11.1 Phase 2 file-change list` → `### 11.3 Phase 2 file-change list`; `### 11.2 Phase 0 file-change list — Created: ...` → `### 11.1 Phase 0 file-change list` with the body moved to the following line (unchanged text, except "per §11.1" → "per §11.3"); `### 11.3 Phase 1 file-change list — Created: ...` → `### 11.2 Phase 1 file-change list` with the body moved to the following line (unchanged text). §11.1 is referenced nowhere else in the document, so no other cross-reference updates are needed.
- **E-E — Relabel §10.6 checks (1)–(6) → C1–C6 + list format (Issues 25, 30, 41, 80):** Rewrite the §10.6 paragraph as a numbered list with labels C1–C6 (same check texts, C1 with the E-B extension, C2 with the Issue 41 procedure, C3/C6 with the Issue 41 YAML procedure). Delete the disclaimer sentence "§10.5 steps 1–4 are the procedure; the checks below are the normative test list — a step and a check with the same number are not the same item." Replace with "§10.5 steps 1–4 are the procedure; the checks below (C1–C6) are the normative test list." Update the two numbered cross-references: D3 item 3 "§10.6 Verification check (1)" → "§10.6 Verification check C1"; §10.5 step 4 "verified by §10.6 check (1)" → "verified by §10.6 check C1".
- **E-F — Path 2 rework: Muse-only + `<install-root>` default `$HOME` (Issues 1, 38, 57):** (1) §9.3: replace "`<install-root>` is the directory holding the cloned repo and the installed skills, default `$HOME/egm` (example: `/home/<user>/egm`)." with "`<install-root>` is the directory holding the cloned repo and the installed skills, default `$HOME` (example: `/home/<user>`), so the bundle is `$HOME/egm/`." (2) §9.3: replace "No generic harness skill-discovery convention is specified: Path 2 requires the harness to load skills from `<install-root>/skills/` (or the harness's own skill directory, stated per harness in §9.2); only Muse's `custom-skills/` convention is specified here (Environment B)." with "Path 2 is supported only for Muse, whose skill-discovery convention is `custom-skills/` (Environment B). No generic harness skill-discovery convention is specified: a non-Muse harness has no supported Path 2 route until its skill directory and load mechanism are specified per harness in §9.2." (3) §9.4 headless row: "Headless / no harness plugin support | Path 2 (vendored skills)" → "Headless / no harness plugin support | Path 2 (vendored skills, Muse only)".

## Prioritized Findings & AI Suggestions

### [Issue 1] [design_critic-3-B1] - Severity: Blocker
*   **Affected Scope:** §9.3 (L248–264), §9.4 (L265–272)
*   **Discrepancy Description:** Path 2 has no skill loader; the headless Environment A route is unexecutable as specified. The doc admits no generic harness skill-discovery convention is specified, yet §9.4 routes every headless / no-plugin-support VM to Path 2.
*   **Rationale:** A directory layout is not an install: no mechanism is specified by which any non-Muse harness discovers, loads, or invokes skills from `<install-root>/skills/`. §9.4's decision matrix promises a route that does not exist.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The doc concedes the gap in its own text. The fix restricts Path 2 to the one harness whose discovery convention is specified (Muse) instead of inventing conventions for harnesses the author did not verify.
*   ***Proposed Edit:***
    *   Location: §9.3 + §9.4 (shared edit E-F).
    *   Change: Apply E-F.

### [Issue 2] [design_critic-3-B2] - Severity: Blocker
*   **Affected Scope:** §4 (L41), §6 (L68), D6 (L177–183)
*   **Discrepancy Description:** D6 snapshot protocol contradicts parallel dispatch; the core safety control cannot execute as written. D6 says both "after each reviewer completes, re-run the snapshot and diff it; any unexpected modification fails that reviewer's round" and "with parallel reviewers a modification is attributed to the round, not to one reviewer; the round fails." Snapshot scope excludes `~/workspace/plans/`, other workspace directories, and all memory/DB paths.
*   **Rationale:** Both cannot hold: a write by a still-running reviewer lands in another reviewer's post-run diff (false fail) or is unattributable, so the per-reviewer fail / discard / rollback procedure is unexecutable. Detection is post-hoc only with no prevention.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The contradiction is in the doc's own words. The fix serializes the snapshot window to the round (one diff after all reviewers complete, round-level failure) and widens the scope to the reports directory.
*   ***Proposed Edit:***
    *   Location: D6 (L177–183); §6 D6 bullet (L68).
    *   Change: In D6, replace "Snapshot scope is the target repo working tree plus the local bundle (`~/workspace/egm/`) and the adapted skills (`~/workspace/custom-skills/egm-*/`)." with "Snapshot scope is the target repo working tree plus the local bundle (`~/workspace/egm/`), the adapted skills (`~/workspace/custom-skills/egm-*/`), and the reports directory (`~/workspace/plans/`)." Replace "After each reviewer completes, re-run the snapshot and diff it; any unexpected modification fails that reviewer's round, the finding is discarded, and the reviewer is not re-dispatched." with "After all reviewers complete (the snapshot window is the whole round, not one reviewer — reviewers run in parallel), re-run the snapshot and diff it; any unexpected modification fails the round, the findings are discarded, and no reviewer is re-dispatched." Replace "Rollback: on a detected modification, fail that reviewer's round, discard its findings, restore the tree from git (`git checkout -- <paths>`) or re-vendor the bundle from the repo tree, and record the incident in the pilot log; the reviewer is not re-dispatched. Attribution: with parallel reviewers a modification is attributed to the round, not to one reviewer; the round fails." with "Rollback: on a detected modification, fail the round, discard its findings, restore the tree from git (`git checkout -- <paths>`, where `<paths>` are the paths the diff names) or re-vendor the bundle from the repo tree, and record the incident in the pilot log; no reviewer is re-dispatched. Attribution: with parallel reviewers a modification is attributed to the round, not to one reviewer." In §12, replace "enforcement is the post-run snapshot diff in D6 (snapshot before dispatch, diff after each reviewer; any unexpected modification fails that reviewer's round)" with "enforcement is the post-run snapshot diff in D6 (snapshot before dispatch, diff once after the round; any unexpected modification fails the round)". In §6, replace "read-only briefs + post-run snapshot diff (detection only — see D6)" with "read-only briefs + post-run round-level snapshot diff (detection only — see D6)".

### [Issue 3] [design_critic-3-M1] - Severity: Major
*   **Affected Scope:** §2 (L26–31), §3 (L35–37)
*   **Discrepancy Description:** Problem statement is unquantified; success metrics are activity-only. §3 admits adoption is precautionary with no drift incident or review-load count; §2 goals are all activity metrics with no outcome/quality metric.
*   **Rationale:** A competent reader cannot confirm the investment is proportionate to the problem.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix adds one outcome metric (finding action rate) to the §2 Adoption goal, labels the adoption explicitly as a precautionary experiment with the §11 rollback as its kill criterion, and defines the "findings categorized" taxonomy (shared with Issue 65).
*   ***Proposed Edit:***
    *   Location: §2 Adoption goal (L31); §3 (L37).
    *   Change: In §2, replace "- Adoption — at least one design document reviewed via `egm-review-loop` within 30 days of merge, with all reviewers run (0 not run)." with "- Adoption — at least one design document reviewed via `egm-review-loop` within 30 days of merge, with all reviewers run (0 not run). Outcome metric: finding action rate — the share of filed findings that lead to a change in the reviewed document, recorded in the pilot log; a 0% action rate with a positive pilot-value ruling must be justified in the ruling, not assumed. Findings are categorized by severity (Blocker / Major / Nit) and by scope (the section each finding targets)." In §3, append to the scale-baseline sentence: "Adoption is framed explicitly as a precautionary experiment: the kill criterion is the §11 rollback (a reviewer not run, or the owner ruling no marginal value)."

### [Issue 4] [design_critic-3-M2] - Severity: Major
*   **Affected Scope:** §5 (L51–54)
*   **Discrepancy Description:** Alternatives Rule — two rejections rest on non-technical grounds; three viable alternatives are never evaluated. Submodule is rejected for "no submodule precedent"; do-nothing is rejected in one clause. Never evaluated: referencing upstream live without vendoring; waiting for upstream issue #252; vendoring a docs subset.
*   **Rationale:** The standard requires each rejection to carry a concrete technical/scope trade-off.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix gives each rejection a technical ground and evaluates the three missing options as new bullets.
*   ***Proposed Edit:***
    *   Location: §5 (L51–54).
    *   Change: Replace "- Git submodule vs. vendoring — rejected: no submodule precedent in the repo; vendoring matches the existing `reference/` pattern." with "- Git submodule vs. vendoring — rejected: a submodule requires a network fetch at clone time and a second update mechanism outside the vendor-integrity hash; vendoring keeps the tree self-contained and hash-verified by the existing `vendor-integrity` job, matching the `reference/` pattern." Replace "- Do-nothing / extend `grilling` + `roundtable_review` + the Ralph verifier — rejected: leaves design review informal and unstandardized." with "- Do-nothing / extend `grilling` + `roundtable_review` + the Ralph verifier — rejected: the delta table (§5, roundtable_review vs EGM) shows the incumbents lack a written standard, a configured reviewer panel, filed reports, and the drift/bootstrap skills; grafting those onto `roundtable_review` means writing a new standard set, a panel configuration, and a report/resolve loop — the same machinery EGM already ships, maintained upstream, versus 2,810 vendored lines. The cheaper path is vendoring, not re-implementing." Append three bullets after the minimal-subset bullet: "- Referencing upstream live without vendoring — rejected: no version pin (the pin is the integrity anchor), no offline use, and no vendor-integrity hash; a live reference cannot be verified against a SHA. - Waiting for upstream issue #252 to close instead of the D3 routing line — rejected: the routing line is one line in each of 7 skills, #252 has no ETA, and hand-maintaining it is trivial; the line is removed if #252 closes. - Vendoring a docs subset (personas + standards only) — rejected: `docs/` is runtime-referenced (the Muse routing line targets `docs/muse.md`; D3 rewrites `docs/codex.md`, `docs/claude.md`, `docs/harnesses.md`), so a subset that omits `docs/` breaks the skills; the remaining non-runtime files (`TEST.md`, `test_scenarios.yaml`, `assets/icon.svg`, `docs/designs/`) ride along under the D2 unit rule because maintaining a subset file list is its own drift risk (see Issue 86)."

### [Issue 5] [design_critic-3-M3] - Severity: Major
*   **Affected Scope:** §6 (L64–73), §10.4 (L332–334), §14 decision 6 (L399–409)
*   **Discrepancy Description:** No cost or token budget for the pilot; worst-case spend is unbounded except by spawn count. Bounds are 25 spawns and a 30-minute interim timeout — up to 12.5 reviewer-hours — with no token or dollar estimate; the token budget is deferred to §14 decision 6, so the Phase 0 pilot runs with no budget at all.
*   **Rationale:** The most expensive new recurring cost is fixed before any measurement, with the budget decision postponed.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix states the interim budget in reviewer-hours (derived from the existing bounds), requires per-reviewer token recording in the pilot log, and makes the pilot log's actuals the basis for the Phase 1 budget (shared with Issues 45 and 91).
*   ***Proposed Edit:***
    *   Location: §10.4 Cost sentence (L334); §6 Loop-cost bullet (L71).
    *   Change: In §10.4, replace "Cost: each phase gate records reviewer count, rounds run, and tokens spent; cost is measured in reviewer spawns (max 25 per run) and tokens." with "Cost: each phase gate records reviewer count, rounds run, and tokens spent (per reviewer, in the pilot log); cost is measured in reviewer spawns (max 25 per run) and tokens. Interim pilot budget: at most 25 spawns × 30 minutes = 12.5 reviewer-hours per run; the pilot log's token actuals set the Phase 1 token budget via §14 decision 6." In §6, replace "cost recorded per phase gate; token budget set by §14 decision 6" with "cost recorded per phase gate (reviewer count, rounds, tokens per reviewer in the pilot log); interim budget 12.5 reviewer-hours per run; token budget set by §14 decision 6 from the pilot log's actuals".

### [Issue 6] [design_critic-3-M4] - Severity: Major
*   **Affected Scope:** §4 (L41), §8.2 (L200–207)
*   **Discrepancy Description:** The Elephant drafts the design and then judges critiques of its own draft. The Elephant merges/deduplicates findings, normalizes severity, and assigns stable ids, while §8.2 replaces the synthesizer with direct dispatch — no independent consolidator. No rule against downgrading severity and no appeal.
*   **Rationale:** The fresh-eyes independence EGM claims is broken at the consolidation step.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix is a recording rule, not a re-architecture: any severity change by the Elephant on consolidation must be recorded in the report with the original severity and the reason.
*   ***Proposed Edit:***
    *   Location: §8.2 Elephant row (L200–207); §10.3.5 (L330).
    *   Change: In the §8.2 Elephant row, replace "Consolidation procedure: the Elephant merges duplicate findings (same target lines + same discrepancy), normalizes severity to the assigned standard, and assigns stable ids (`<reviewer>-<round>-<n>`); overlaps are recorded in the report." with "Consolidation procedure: the Elephant merges duplicate findings (same target lines + same discrepancy), normalizes severity to the assigned standard, and assigns stable ids (`<reviewer>-<round>-<n>`); overlaps are recorded in the report. Severity rule: the Elephant must not change a finding's severity on consolidation without recording the change in the report (original severity, new severity, reason); a severity downgrade with no recorded reason is a defect in the report, not a judgment call." In §10.3.5, append to the consolidation sentence: "Any severity change on consolidation is recorded with its original severity and reason (see §8.2)."

### [Issue 7] [design_critic-3-M5] - Severity: Major
*   **Affected Scope:** §4 (L41), §10.4 (L332–334)
*   **Discrepancy Description:** Convergence ignores Nits entirely; the loop can go "clean" with all Nits undispositioned. No disposition rule exists for Nits (fix / defer-with-reason / decline).
*   **Rationale:** The pilot's 27 Nits could all stand at "clean."
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix states explicitly that Nits are non-blocking by design but must each carry a recorded disposition in the resolve report — this preserves the skill's convergence rule (Blocker/Major only) while closing the undispositioned-Nit gap.
*   ***Proposed Edit:***
    *   Location: §10.4 (L334).
    *   Change: Append to the 'Unsettled' sentence: " Nits are non-blocking by design: a round is clean when no Blocker or Major is unsettled, regardless of Nits — but every Nit must still be recorded in the resolve report with a disposition (fix / decline, with a reason). An undispositioned Nit is a defect in the resolve report, not a blocker of clean."

### [Issue 8] [design_critic-3-M6] - Severity: Major
*   **Affected Scope:** D5 (L168–176), §12 (L373–385)
*   **Discrepancy Description:** The 90-file vendored bundle is never content-scanned; only the adapted skills are gated. The bundle (792K, including `agents/openai.yaml`, per-skill `test_scenarios.yaml`, `references/*.json`, `assets/icon.svg`) enters on SHA integrity alone, which proves provenance against the pin, not safety. The hand-written `skill.yaml` files are covered by neither gate.
*   **Rationale:** An upstream compromise or malicious YAML passes both CI gates; YAML-parse + name-match proves well-formedness, not content safety.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix adds a vendor-time content review for bundle non-markdown files (recorded in the PR body) and states the gate input is the whole skill directory (including `skill.yaml`), plus records the SHA-proves-provenance-not-safety limit in §12.
*   ***Proposed Edit:***
    *   Location: D5 (L168–176); §12 (L373–385).
    *   Change: In D5, append: "Bundle non-markdown files (`agents/openai.yaml`, per-skill `test_scenarios.yaml`, `references/*.json`, `assets/icon.svg`, `docs/assets/*.svg`) are content-reviewed at vendor time: the vendor reads each file and records a one-line content note per file in the Phase 2 PR body. The gate input is the whole skill directory — `skill.yaml` is scanned together with its `SKILL.md`, so a malicious description (`include_in_prompt: true` injects it into the prompt) trips the same gate. SHA integrity proves provenance against the pin, not safety; the content review is the safety control for the bundle." In §12, append to the adapted-skill-content bullet: "SHA integrity proves provenance against the pin, not safety — bundle non-markdown files are content-reviewed at vendor time per D5."

### [Issue 9] [design_critic-3-M7] - Severity: Major
*   **Affected Scope:** §12 (L373–385), §7 (L89–95)
*   **Discrepancy Description:** `egm-review-loop` URL fetching is unbounded. The only control is "URLs the user supplied" — no scheme allowlist, size cap, content-type check, dedicated temp directory, or sandbox.
*   **Rationale:** §12 names it "the only network touchpoint" but sets no bound on it.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix bounds the fetch with a scheme allowlist, a size cap, a dedicated temp dir, and a data-only rule.
*   ***Proposed Edit:***
    *   Location: §12 (L381–383).
    *   Change: Replace "- `egm-review-loop`'s URL fetching is the only network touchpoint; scope it to URLs the user supplied for that review." with "- `egm-review-loop`'s URL fetching is the only network touchpoint; scope it to URLs the user supplied for that review, and bound it: https only (no http, no other schemes); each fetched page capped at 1 MB; saved under a dedicated temp dir (`/tmp/egm-urls-<run>/`, removed after the review); fetched content is treated as data, never executed; non-HTML content types are rejected."

### [Issue 10] [design_critic-3-M8] - Severity: Major
*   **Affected Scope:** §5 (L55), §11 (L349–363), §11.1 (L365–368), §14 (L399–409)
*   **Discrepancy Description:** Phase 2 scope is self-contradictory, and its gate is coupled to the Phase 3 provisioning decision. §5 and the §11 table say that without the decision-5 ruling, "Phase 2 installs the 2 review skills only" — but §11.1 enumerates all 7 wrappers unconditionally with no 2-skill variant file list. The Phase 2 gate requires "§14 decision 3 ruled" — coupling the AEP PR merge to a fresh-VM provisioning decision with no stated justification.
*   **Rationale:** A specified branch of the plan has no file boundary, and the gate couples two phases without justification.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix is shared edit E-A (2-skill variant + decision-3 decoupling + §5 temporal fix).
*   ***Proposed Edit:***
    *   Location: §5, §11, §11.1, §14 decision 3 (shared edit E-A).
    *   Change: Apply E-A.

### [Issue 11] [design_critic-3-M9] - Severity: Major
*   **Affected Scope:** §10.5–§10.6 (L336–347), D1 (L110–115), §10.2 (L294–308)
*   **Discrepancy Description:** Verification gaps — §10.6 check (2) has no executable procedure, and the pin record has no check at all. Check (2) asserts a wrapper `../../reference/...` target that does not exist fails the check, but no §10.5 step runs it: §10.5 step 4 normalize-then-diff would pass with identical dangling references on both sides. D1/§10.2 require a local bundle `README.md` pin record, but no check asserts its existence or content — and verified live, `~/workspace/egm/README.md` does not exist.
*   **Rationale:** An assertion without a command cannot be executed; an un-checked required file is not verified.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix adds a resolve loop against the repo tree for check C2 (shared with Issue 41's procedure) and a new pin-record check C7.
*   ***Proposed Edit:***
    *   Location: §10.5 step 4 (L341); §10.6 (L343–347).
    *   Change: In §10.5 step 4, append: "Also resolve every `../../reference/...` target in the repo wrappers against the repo tree (`for f in skills/egm-*/SKILL.md; do grep -oE '\\.\\./\\.\\./reference/[A-Za-z0-9_./-]+' \"$f\"; done | sort -u | while read -r p; do test -f \"reference/${p#../../reference/}\" || echo \"MISSING: $p\"; done` — expected output: no `MISSING` lines); this is check C2, and the normalize-then-diff alone does not run it." In §10.6, add check C7 (see E-E list format): "(C7) pin record — `~/workspace/egm/README.md` exists and contains the upstream URL, the pinned SHA (equal to the §14 decision 1 pin), the snapshot date, and the license (Apache-2.0)."

### [Issue 12] [design_critic-3-M10] - Severity: Major
*   **Affected Scope:** D3 (L126–135), §10.6 (L343–347)
*   **Discrepancy Description:** D3 adaptation is a hand `sed` with no idempotency guard, and its verification is vacuous in two places. A naive re-run double-prefixes (`<bundle>/<bundle>/agents/`). §10.6 check (1) verifies only `agents/...` and `resources/...` references — never `docs/...` references, the Muse routing line's presence, or that no upstream-relative reference remains. The cited "persona-internal references" (`agents/zoom_out.md:44`, `agents/synthesizer.md:38`) are not references at all — verified: line 44 of `zoom_out.md` is a review-step heading and line 38 of `synthesizer.md` is a spawning-step heading.
*   **Rationale:** A non-idempotent rewrite with a verification gap that cannot fail proves nothing.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid on all three points, each verified against the bundle. The fix is shared edit E-B.
*   ***Proposed Edit:***
    *   Location: D3 item 3; §10.6 check C1; §9.5 step 4; §10.6 last sentence (shared edit E-B).
    *   Change: Apply E-B.

### [Issue 13] [design_critic-3-M11] - Severity: Major
*   **Affected Scope:** §9.2 (L218–236), §9.5 (L274–281)
*   **Discrepancy Description:** Load-bearing Environment A commands are asserted without upstream citation. `muse plugins validate`, `muse skills list --source plugin`, and `muse exec` underpin §9.5 verification, but the doc cites bundle `docs/muse.md` for install/approve only — not for `validate`, `list --source plugin`, or `exec` or its approvals-simulation mode.
*   **Rationale:** If any of these does not exist on the target harness, Environment A verification collapses to the E2E fixture alone.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix downgrades step 1 from a gate to a pre-check: each command is confirmed to exist via the harness's own help before it is relied on, and its absence is recorded with the E2E fixture as the gate.
*   ***Proposed Edit:***
    *   Location: §9.5 step 1 (L276–278).
    *   Change: Replace "1. Offline pre-check: `muse plugins validate ./elephant-goldfish-model` (the cloned repo path from §9.2) (or the harness equivalent) reports the plugin valid with 7 skills and 10 agents." with "1. Offline pre-check (best-effort, not a gate): `muse plugins validate ./elephant-goldfish-model` (the cloned repo path from §9.2) (or the harness equivalent) reports the plugin valid with 7 skills and 10 agents. Before relying on `muse plugins validate`, `muse skills list --source plugin`, or `muse exec`, confirm each exists on the target harness (`<cmd> --help`); if any is absent, record it in the pilot log and proceed to the E2E fixture (step 3) as the verification gate. No step-1 command is cited to bundle `docs/muse.md` beyond install/approve — the doc does not assert upstream documents `validate`, `list --source plugin`, or `exec`."

### [Issue 14] [design_critic-3-M12] - Severity: Major
*   **Affected Scope:** D1 (L110–115), §11 (L349–363)
*   **Discrepancy Description:** No Phase 2 rollback and no vendored-dependency lifecycle. §11 rollback covers only the pilot. Re-sync is "a deliberate PR" with no cadence, owner, upstream monitoring, or staleness expiry — pin `e9e1f06a` will silently age with no trigger to revisit it.
*   **Rationale:** A merged PR with no revert procedure and a pin with no revisit trigger are both unbounded.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix adds a Phase 2 revert procedure and a re-sync cadence with a staleness trigger.
*   ***Proposed Edit:***
    *   Location: §11 Rollback (L361–363); D1 (L110–115).
    *   Change: In §11, replace "Rollback: if the pilot fails (a reviewer not run, or the owner rules no marginal value), roll back by deleting the 2 adapted skill dirs and the local bundle (`~/workspace/custom-skills/egm-*/`, `~/workspace/egm/`), with no AEP PR; record the outcome in the pilot log." with "Rollback: if the pilot fails (a reviewer not run, or the owner rules no marginal value), roll back by deleting the 2 adapted skill dirs and the local bundle (`~/workspace/custom-skills/egm-*/`, `~/workspace/egm/`), with no AEP PR; record the outcome in the pilot log. Phase 2 rollback (after merge): revert the merge commit (`git revert -m 1 <merge-sha>`) in a revert PR, which removes the bundle, the 7 wrappers, the scope/manifest/attribution updates, and the CI block together; a partial revert is not permitted." In D1, replace "Re-sync is a deliberate PR, not a silent pull." with "Re-sync is a deliberate PR, not a silent pull. Cadence and staleness: the pin is re-checked on every sync; if upstream HEAD is more than 90 days newer than the pin, the sync record notes the pin as stale and the owner rules on re-vendor. Owner: the agent running the sync (§10.2)."

### [Issue 15] [design_critic-3-N1] - Severity: Nit
*   **Affected Scope:** §3 (L37)
*   **Discrepancy Description:** "22 documents under AEP `docs/`" needs its counting rule. 22 is the top-level `*.md` count; the recursive count is 37 `.md` files (38 files total, including `docs/superpowers/plans/`).
*   **Rationale:** The demand baseline must be reproducible.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; one sentence closes it.
*   ***Proposed Edit:***
    *   Location: §3 (L37).
    *   Change: Replace "The design corpus the pilot draws on is 22 documents under AEP `docs/` plus the dated plans under `~/workspace/plans/`;" with "The design corpus the pilot draws on is 22 documents under AEP `docs/` (top-level `*.md` count; the recursive count is 37 `.md` files) plus the dated plans under `~/workspace/plans/`;"

### [Issue 16] [design_critic-3-N2] - Severity: Nit
*   **Affected Scope:** §10.6 (L343–347)
*   **Discrepancy Description:** Check (1) regex can false-pass and false-fail. The pattern class includes `.`, so a prose trailing period would be captured into the path and false-fail; conversely a bare directory reference passes as "resolves" because `test -e` succeeds on a directory.
*   **Rationale:** A verification command that can both false-pass and false-fail is unreliable.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; fixed inside the E-B check C1 extension (anchor the pattern, require a regular file).
*   ***Proposed Edit:***
    *   Location: §10.6 check C1 (shared edit E-B).
    *   Change: Apply E-B (C1 extension: pattern `(agents|resources|docs)/[A-Za-z0-9_/-]+\\.[A-Za-z0-9]+` anchored to a file extension, and `test -f` instead of `test -e`).

### [Issue 17] [design_critic-3-N3] - Severity: Nit
*   **Affected Scope:** D1 (L110–115), §9.3 (L248–263), §10.5 step 2 (L336–341)
*   **Discrepancy Description:** The pin SHA is hardcoded in at least five places while §14 decision 1 leaves it open. If the owner picks a different SHA, every occurrence must change by hand with no single source of truth.
*   **Rationale:** A pin with no single source of truth drifts on the first change.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the fix names D1 + §14 decision 1 as the single source of truth and lists the occurrences that must change together.
*   ***Proposed Edit:***
    *   Location: D1 (L110–115).
    *   Change: Append to D1: "Single source of truth: the pin is stated here and in §14 decision 1; every other occurrence (attribution, PROVENANCE.md, bundle README.md, §9.3 clone commands, §10.5 step 2 fetch + `rev-parse` expectation) is a use of that pin. When the pin changes, update D1 and §14 decision 1 first, then the uses together in the same PR."

### [Issue 18] [structural-3-M1] - Severity: Major
*   **Affected Scope:** §2 Goals (L26–33) vs §13 Non-goals (L387–397)
*   **Discrepancy Description:** Required "Goals & Non-Goals" heading is split, not present as one section. §2 ends with "Non-goals: see §13" and §13 opens with "Goals: see §2". A fresh reader must jump 360 lines to assemble scope, and neither section is self-contained.
*   **Rationale:** The standard names Goals & Non-Goals as one required area.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix merges the content into §2 (renamed "Goals & Non-goals") and turns §13 into a pointer, avoiding a renumbering cascade across the §14 cross-references.
*   ***Proposed Edit:***
    *   Location: §2 (L26–33); §13 (L387–397).
    *   Change: Rename `## 2. Goals` to `## 2. Goals & Non-goals`. Replace "Non-goals: see §13." with the four §13 bullets verbatim (under a "Non-goals:" lead-in). Replace the whole §13 section with: "## 13. Non-goals\n\nNon-goals are stated with the goals in §2."

### [Issue 19] [structural-3-M2] - Severity: Major
*   **Affected Scope:** §4 Proposed Architecture (L39–43)
*   **Discrepancy Description:** Architecture is not in its own section. The entire section is one 1,481-character paragraph that states the component map/data flow in compressed form and defers with "The existing §§8–10 keep their detail; this section is the map, with pointers to them."
*   **Rationale:** The standard requires the spec to detail component layout, data flows, and ecosystem integration; §4 alone does not let a fresh reader confirm the architecture.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix replaces the deferral with a component table and a short data-flow list built from the existing content (shared with Issue 92).
*   ***Proposed Edit:***
    *   Location: §4 (L39–43).
    *   Change: Replace "The existing §§8–10 keep their detail; this section is the map, with pointers to them. Data flow: the Elephant drafts the design doc → dispatches Goldfish reviewers in parallel (one fresh-context subagent per reviewer) → each reviewer files a report citing persona, standard, and target line numbers → the driver runs the line-existence + standard-name checks → the Elephant consolidates into a flat FindingsList with stable ids and writes the report artifact → `egm-resolve` categorizes → fixes are applied → the loop re-reviews until two consecutive clean rounds." with a component table plus flow list: "| Component | Location | Defined in |\n|---|---|\n| Pristine bundle | `~/workspace/egm/` local; `reference/elephant-goldfish-model/` in AEP | D2, §10.2 |\n| Adapted skills | local `custom-skills/egm-*/`; AEP `skills/egm-*` wrappers | D3, D4 |\n| Gates | SkillSpector gate-scan; vendor-integrity; skills-freshness | D5, D4 |\n| Dispatch | Elephant driver + Goldfish reviewers via `subagent.spawn` / harness subagent tool, direct dispatch in Environment B | §8.2, §10.3 |\n| Artifacts | design docs, review reports, drift reports | §10.3, §11 |\n\nData flow: the Elephant drafts the design doc → dispatches Goldfish reviewers in parallel (one fresh-context subagent per reviewer) → each reviewer files a report citing persona, standard, and target line numbers → the driver runs the line-existence + standard-name checks → the Elephant consolidates into a flat FindingsList with stable ids and writes the report artifact → `egm-resolve` categorizes → fixes are applied → the loop re-reviews until two consecutive clean rounds. Detail lives in §§8–10; this section is the map."

### [Issue 20] [structural-3-M3] - Severity: Major
*   **Affected Scope:** §7 "What EGM is (verified)" (L75–106)
*   **Discrepancy Description:** Background placed after Risks, before Design decisions. The definition of EGM, its skills table, and upstream state appear in §7, after Problem (§3), Architecture (§4), Alternatives (§5), and Risks (§6). A fresh reader meets the architecture and alternatives for a system that is not defined until §7.
*   **Rationale:** Background/context belongs before §4.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Moving §7 before §4 would renumber §§4–7 and cascade every cross-reference; the fix instead defines EGM briefly in §1 (where the term first appears) with a pointer to the full §7 inventory — a fresh reader is oriented before §4 without a renumber.
*   ***Proposed Edit:***
    *   Location: §1 (L5–22).
    *   Change: After "Adopt Google's Elephant-Goldfish Model (EGM) — a spec-driven development plugin for AI coding assistants — into AEP's skill catalog and local environment, so design-before-implementation becomes a loadable skill rather than an implicit habit." insert: "EGM in one paragraph: one agent (the Elephant) holds context and drafts the design; fresh-context reviewers (Goldfish) audit it against written document standards; a human approves before anything is built. It ships 7 skills, 10 reviewer personas, and 5 document standards — the full verified inventory is in §7."

### [Issue 21] [structural-3-M4] - Severity: Major
*   **Affected Scope:** §8 hierarchy (L108–207)
*   **Discrepancy Description:** Two different numbering schemes share H3. D1–D7 and numbered subsections 8.1 (line 196) and 8.2 (line 200) are all `###` under `## 8`, and 8.1/8.2 appear after D7 rather than before or as a separate section.
*   **Rationale:** Same-level headings should be the same kind of subdivision; mixing decision labels with numeric subsections breaks the outline and TOC navigation.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid, and not a re-raise of structural-1-6 DECLINE: that covered sibling H2 sections in the pre-restructure layout; this mixed scheme inside a single H2 was created by the round-1/2 restructuring, and the fix (moving 8.1/8.2 out) does not touch the stable D-references. The fix is shared edit E-C.
*   ***Proposed Edit:***
    *   Location: §8.1, §8.2 (shared edit E-C).
    *   Change: Apply E-C.

### [Issue 22] [structural-3-M5] - Severity: Major
*   **Affected Scope:** §9.2 sibling heading (L237)
*   **Discrepancy Description:** "Native installs for the other harnesses…" is an unnumbered H3 between numbered H3s. Sequence is 9.1, 9.2, unnumbered heading, 9.3, 9.4, 9.5. It is subordinate content of Path 1 (§9.2) presented at the same level as §9.3–9.5.
*   **Rationale:** It breaks the numbered sequence and implies a §9.2½ that does not exist.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The heading is subordinate to Path 1, so it demotes one level.
*   ***Proposed Edit:***
    *   Location: §9.2 (L237).
    *   Change: Replace "### Native installs for the other harnesses (commands from the bundle's `docs/harnesses.md` install table)" with "#### Native installs for the other harnesses (commands from the bundle's `docs/harnesses.md` install table)".

### [Issue 23] [structural-3-M6] - Severity: Major
*   **Affected Scope:** §11.1–11.3 (L365, 369, 371)
*   **Discrepancy Description:** Subsections out of phase order. Order is 11.1 Phase 2, 11.2 Phase 0, 11.3 Phase 1, while the §11 table and the rollout narrative run Phase 0 → 1 → 2 → 3.
*   **Rationale:** Numbered subsections should follow the document's own phase order.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix is shared edit E-D (renumber + split headings).
*   ***Proposed Edit:***
    *   Location: §11.1–11.3 (shared edit E-D).
    *   Change: Apply E-D.

### [Issue 24] [structural-3-M7] - Severity: Major
*   **Affected Scope:** §11.2 (L369), §11.3 (L371)
*   **Discrepancy Description:** Body content embedded in the heading line. Both headings carry the full file-change list after an em-dash on the heading line itself, unlike §11.1, which is a heading only with body on line 367.
*   **Rationale:** Headings must be navigable labels; embedding a paragraph in a heading breaks TOC/outline use and is inconsistent within the same section.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix is shared edit E-D.
*   ***Proposed Edit:***
    *   Location: §11.2, §11.3 (shared edit E-D).
    *   Change: Apply E-D.

### [Issue 25] [structural-3-M8] - Severity: Major
*   **Affected Scope:** §10.5 (L336–341) vs §10.6 (L343–347)
*   **Discrepancy Description:** Colliding step/check numbering. §10.5 has steps 1–4 and §10.6 has checks (1)–(6); line 345 has to disambiguate: "a step and a check with the same number are not the same item."
*   **Rationale:** A numbering scheme that needs an explicit disclaimer to prevent mis-citation is a structural defect; steps and checks should use distinct labels.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix is shared edit E-E (relabel to C1–C6, list format, update cross-references).
*   ***Proposed Edit:***
    *   Location: §10.6; D3 item 3; §10.5 step 4 (shared edit E-E).
    *   Change: Apply E-E.

### [Issue 26] [structural-3-M9] - Severity: Major
*   **Affected Scope:** §8.1 "AEP machinery" (L196–198)
*   **Discrepancy Description:** Empty pointer subsection with a wrong line citation. The subsection states it is "a pointer only and states no additional requirements," and cites "the D4 bullets (lines 121–129)" — lines 121–129 are the D2 paragraph, while the D4 bullets are lines 138–165.
*   **Rationale:** A subsection that adds nothing and points at the wrong lines is stale scaffolding; the citation is unverifiable as written.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The subsection contributes nothing but a wrong reference; the fix is shared edit E-C (delete §8.1).
*   ***Proposed Edit:***
    *   Location: §8.1 (shared edit E-C).
    *   Change: Apply E-C.

### [Issue 27] [structural-3-M10] - Severity: Major
*   **Affected Scope:** Alternatives split across §5 and §8 (L45–62 vs L160–165)
*   **Discrepancy Description:** §5 is the Alternatives section, but an additional rejected alternative ("shared `skills/egm-agents/` + `skills/egm-resources/` dirs") is filed as a bullet inside D4 (lines 160–165), duplicating the §5 bullet on the same option (line 51). §5's bullet list is interrupted by an 814-character unbulleted paragraph (line 59, "roundtable_review vs EGM — …"), with bullets resuming at lines 61–62.
*   **Rationale:** The standard's Alternatives Rule requires one evaluable alternatives section; scattering a rejection outside it risks it being missed in a completeness check.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix deletes the duplicate D4 bullet (leaving a pointer to §5) and moves the interrupting paragraph after the bullet list.
*   ***Proposed Edit:***
    *   Location: D4 (L160–165); §5 (L59–62).
    *   Change: In D4, replace the whole "- **Alternative considered and rejected:** shared `skills/egm-agents/` + `skills/egm-resources/` dirs alongside the skills. It keeps one manifest mechanism, but pollutes the skill catalog with non-skill directories and stretches the scope file's semantics (\"in-scope skill directory names\"). Two gates covering two layers (vendor-integrity for the bundle, skills-freshness for the wrappers) is cleaner separation." bullet with: "- **Alternative considered and rejected:** shared `skills/egm-agents/` + `skills/egm-resources/` dirs — evaluated in §5 (rejected: pollutes the skill catalog with non-skill directories). Two gates covering two layers (vendor-integrity for the bundle, skills-freshness for the wrappers) is cleaner separation." In §5, move the "roundtable_review vs EGM — …" paragraph to after the last bullet (after the Local-only bullet), preceded by "Delta table (roundtable_review vs EGM):".

### [Issue 28] [structural-3-M11] - Severity: Major
*   **Affected Scope:** Risks split across §6 (L64–73) and §12 Security notes (L373–385)
*   **Discrepancy Description:** §6 holds failure modes/cost/drift, while security implications — which the standard requires under Risks & Limits — live 300 lines later in §12, with no cross-reference from §6 to §12.
*   **Rationale:** A reader checking "risks and mitigations" against the standard must assemble two distant sections; security is a risk, not a separate appendix-style topic.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. A full merge of §12 into §6 would churn the document; the fix makes the two sections explicitly cross-referenced so no reader checks one without finding the other.
*   ***Proposed Edit:***
    *   Location: §6 (L64–73); §12 (L373–385).
    *   Change: In §6, append a bullet: "- Security risks — see §12 Security notes (principal risk: the D6 read-only caveat; URL-fetch bounds; bundle content review)." In §12, prepend: "Security notes (risks & mitigations live in §6; this section holds the security implications)."

### [Issue 29] [structural-3-M12] - Severity: Major
*   **Affected Scope:** D3 item 3 (L134, 2,141 chars)
*   **Discrepancy Description:** A mapping table written as inline prose in a numbered-list item. The upstream→installed path-rewrite mapping (7 rows) is a semicolon-separated run-on inside list item 3.
*   **Rationale:** Tabular data in a single-line list item is not scannable or citable per row; the mapping should be a table, as the document does elsewhere.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix converts the inline mapping to a Markdown table inside item 3.
*   ***Proposed Edit:***
    *   Location: D3 item 3 (L134).
    *   Change: Replace "Rewrite mapping table (upstream reference → installed reference): `agents/` → `<bundle>/agents/`; `resources/document_standards/` → `<bundle>/resources/document_standards/`; `resources/execution_instructions.md` → `<bundle>/resources/execution_instructions.md`; `../../docs/codex.md` → `<bundle>/docs/codex.md`; `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` → `<bundle>/docs/claude.md`; `docs/harnesses.md` → `<bundle>/docs/harnesses.md`; `docs/muse.md` → `<bundle>/docs/muse.md`; where `<bundle>` is `/home/hatch/workspace/egm` in Environment B, `<install-root>/egm` in Environment A Path 2, and `../../reference/elephant-goldfish-model` in the AEP wrappers." with "Rewrite mapping table (upstream reference → installed reference); `<bundle>` is `/home/hatch/workspace/egm` in Environment B, `<install-root>/egm` in Environment A Path 2, and `../../reference/elephant-goldfish-model` in the AEP wrappers:\n\n| Upstream reference | Installed reference |\n|---|---|\n| `agents/` | `<bundle>/agents/` |\n| `resources/document_standards/` | `<bundle>/resources/document_standards/` |\n| `resources/execution_instructions.md` | `<bundle>/resources/execution_instructions.md` |\n| `../../docs/codex.md` | `<bundle>/docs/codex.md` |\n| `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` | `<bundle>/docs/claude.md` |\n| `docs/harnesses.md` | `<bundle>/docs/harnesses.md` |\n| `docs/muse.md` | `<bundle>/docs/muse.md` |"

### [Issue 30] [structural-3-N1] - Severity: Nit
*   **Affected Scope:** §10.6 Verification checks (L347, 1,266 chars)
*   **Discrepancy Description:** Six normative checks in one paragraph. Checks (1)–(6) run inline in a single paragraph with no list, including an embedded shell loop.
*   **Rationale:** A normative test list should be a list; as one paragraph, individual checks cannot be cited, scanned, or checked off.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; worth fixing because the list format is also the vehicle for the C1–C6 relabel (shared edit E-E).
*   ***Proposed Edit:***
    *   Location: §10.6 (shared edit E-E).
    *   Change: Apply E-E.

### [Issue 31] [structural-3-N2] - Severity: Nit
*   **Affected Scope:** Unwrapped single-line paragraphs throughout (L37, 41, 182, 308, 314, 323, 330, 339, 341)
*   **Discrepancy Description:** Whole sections as single lines (up to 2,738 chars) impede fresh-reader parsing and make line-cited review findings coarse.
*   **Rationale:** No line-length rule is in the standard; the defect is readability only.
*   ***AI Suggestion:*** DECLINE
*   ***Justification:*** Cosmetic. Reflowing nine long lines is churn with no correctness gain — line-cited review still works, and every long line is a single sentence or command whose wrapping would obscure it. Record only.
*   ***Proposed Edit:***
    *   Location: None.
    *   Change: None.

### [Issue 32] [structural-3-N3] - Severity: Nit
*   **Affected Scope:** §7 table unit inconsistency (L89–95)
*   **Discrepancy Description:** `egm-brainstorm` is "(271 lines)" but `egm-draft` is "(321)", `egm-review` "(426)", `egm-resolve` "(187)", `egm-review-loop` "(199)", `egm-bootstrap` "(427)", `egm-drift-report` "(67)" — unit stated once, omitted six times.
*   **Rationale:** Inconsistent units in a single table column invite misreading of the counts.
*   ***AI Suggestion:*** SETTLED
*   ***Justification:*** Settled — same scope and issue as round-1 `structural-1-8` (DECLINE — cosmetic inconsistency in a table whose meaning is unambiguous). Per the loop's settled rule, a settled finding is not re-opened. No fix proposed; recorded here only.
*   ***Proposed Edit:***
    *   Location: None.
    *   Change: None. Matches round-1 disposition: DECLINE (structural-1-8).

### [Issue 33] [structural-3-N4] - Severity: Nit
*   **Affected Scope:** Link-style inconsistency, line 244
*   **Discrepancy Description:** The ChatGPT desktop plugin URL is a bare URL in parentheses, while every other external link in the document uses Markdown `[text](url)` form.
*   **Rationale:** One bare URL breaks the document's own link convention.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; one-line fix.
*   ***Proposed Edit:***
    *   Location: §9.2 (L244).
    *   Change: Replace "(desktop-only listing: https://chatgpt.com/plugins/plugins_6aeb90f47ec88191a3c107e01d3eb357)" with "(desktop-only listing: [ChatGPT plugin listing](https://chatgpt.com/plugins/plugins_6aeb90f47ec88191a3c107e01d3eb357))".

### [Issue 34] [structural-3-N5] - Severity: Nit
*   **Affected Scope:** Prose inside a code block, lines 222–226
*   **Discrepancy Description:** Line 223 embeds an annotation in the shell block: `git clone https://github.com/google/elephant-goldfish-model.git (creates \`./elephant-goldfish-model/\`, …)`.
*   **Rationale:** A code block presented as commands to run contains non-executable prose; the annotation belongs outside the fence.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; move the annotation out of the fence.
*   ***Proposed Edit:***
    *   Location: §9.2 (L222–226).
    *   Change: Replace "```sh\ngit clone https://github.com/google/elephant-goldfish-model.git (creates `./elephant-goldfish-model/`, the default directory name the next command uses)\nmuse plugins install ./elephant-goldfish-model --scope user\nmuse plugins approve egm\n```" with "```sh\ngit clone https://github.com/google/elephant-goldfish-model.git\nmuse plugins install ./elephant-goldfish-model --scope user\nmuse plugins approve egm\n```\n\n(The clone creates `./elephant-goldfish-model/`, the default directory name the next command uses.)"

### [Issue 35] [structural-3-N6] - Severity: Nit
*   **Affected Scope:** Appendix heading (L411)
*   **Discrepancy Description:** "## Appendix — Sources (all verified 2026-11-06)" is unnumbered after numbered §§1–14.
*   **Rationale:** It breaks the document's numbering scheme.
*   ***AI Suggestion:*** SETTLED
*   ***Justification:*** Settled — same scope and issue as round-1 `structural-1-7` (DECLINE — appendix unnumbered by convention), also round-2 `structural-2-14`. Per the loop's settled rule, a settled finding is not re-opened. No fix proposed; recorded here only.
*   ***Proposed Edit:***
    *   Location: None.
    *   Change: None. Matches round-1 disposition: DECLINE (structural-1-7).

### [Issue 36] [structural-3-N7] - Severity: Nit
*   **Affected Scope:** Overlapping sibling headings §10.3.2 (L315) "Approval gates" vs §10.3.3 (L321) "Readiness and section-approval gates"
*   **Discrepancy Description:** Both cover approval gating, and §10.3.2's body (lines 317–319) restates gates that §10.3.3 then defines.
*   **Rationale:** Near-duplicate headings at the same level signal one section split in two; merge or rename to distinguish scope.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. §10.3.2's body is an intro to the gates §10.3.3 defines, so it merges into §10.3.3 as opening sentences.
*   ***Proposed Edit:***
    *   Location: §10.3.2–§10.3.3 (L315–323).
    *   Change: Delete the "#### 10.3.2 Approval gates" heading and move its body to the head of §10.3.3: replace "#### 10.3.2 Approval gates\n\n- Approval gates: preserve the skill's readiness and section-approval gates. Tool unavailability is not approval — ask one plain-text question and wait for the answer where no structured question tool exists.\n\n#### 10.3.3 Readiness and section-approval gates\n\nReadiness gate (fires before a review loop starts):" with "#### 10.3.3 Readiness and section-approval gates\n\nApproval gates: preserve the skill's readiness and section-approval gates. Tool unavailability is not approval — ask one plain-text question and wait for the answer where no structured question tool exists.\n\nReadiness gate (fires before a review loop starts):"

### [Issue 37] [structural-3-N8] - Severity: Nit
*   **Affected Scope:** No explicit scalability-limits subsection (§6, L64–73)
*   **Discrepancy Description:** §6 covers loop cost (line 71) and failure modes (line 73), but no subsection states scalability limits as such, as the standard's Risks & Limits paragraph calls for.
*   **Rationale:** The content is partially present (cost bounds, bundle size in §5 line 49), but a fresh reader cannot locate a scalability-limits statement.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; one bullet in §6 closes it.
*   ***Proposed Edit:***
    *   Location: §6 (L64–73).
    *   Change: Append a bullet to §6: "- Scalability limits — bundle size is fixed at 90 files / 792K (D2 unit rule; it does not grow with use); loop cost is bounded at 25 spawns per run (§10.4); per-skill load is one `SKILL.md` + `skill.yaml` per skill, so catalog growth is linear in skills added, not in reviews run."

### [Issue 38] [implementation_readiness-3-B1] - Severity: Blocker
*   **Affected Scope:** §9.3 (L261)
*   **Discrepancy Description:** Path 2 has no executable skill-discovery step for a generic harness. "No generic harness skill-discovery convention is specified: Path 2 requires the harness to load skills from `<install-root>/skills/` (or the harness's own skill directory, stated per harness in §9.2); only Muse's `custom-skills/` convention is specified here (Environment B)." No per-harness skill directory is actually stated in §9.2 for any harness.
*   **Rationale:** The plan admits its own gap. An implementer on a headless VM with a non-Muse harness cannot complete the install — they must invent how that harness discovers skills. A whole install route fails the zero-decision rule.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid — same root cause as Issue 1. The fix is shared edit E-F.
*   ***Proposed Edit:***
    *   Location: §9.3 + §9.4 (shared edit E-F).
    *   Change: Apply E-F.

### [Issue 39] [implementation_readiness-3-M1] - Severity: Major
*   **Affected Scope:** §11.1, §11.2 (L367, 369)
*   **Discrepancy Description:** File-change lists give counts and directories, not exact file paths. Phase 2 "Created" lists the bundle as "90 files" with per-directory counts and wrapper directories `skills/egm-*/`, never the 90 repo-relative paths.
*   **Rationale:** The standard explicitly requires an exact path list "suitable for enforcing a Phase 5 write allowlist" and allows a glob only for generated output with unknowable filenames. All 90 filenames are knowable in advance. Counts cannot enforce an allowlist.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The exact path list exists as an artifact — the `.github/vendor-elephant-goldfish-model.sha256` manifest (D4 generation command) enumerates all 90 repo-relative paths — so the fix names the manifest as the authoritative exact list instead of pasting 90 paths into the doc.
*   ***Proposed Edit:***
    *   Location: §11.1 (L367).
    *   Change: Append to the §11.1 "Created" paragraph: "Exact path list (allowlist): the 90 bundle paths are enumerated in `.github/vendor-elephant-goldfish-model.sha256` (generated by the D4 command); the wrappers are exactly the 7 named `skills/egm-*/` directories (14 files, one `SKILL.md` + one `skill.yaml` each). Phase 0's exact list is the same 90 bundle paths plus the 2 pilot skill dirs; Phase 1's is the remaining 5 skill dirs."

### [Issue 40] [implementation_readiness-3-M2] - Severity: Major
*   **Affected Scope:** §9.5 step 3 (L280)
*   **Discrepancy Description:** E2E fixture is not an executable test. No literal prompt text for brainstorm → draft → review; fixture design `muse-wonder-1.0` ("line-count design") is never defined — no content, no expected line counts; `<shape>` values in `/tmp/egm-e2e-<shape>/` are unenumerated; `muse exec` invocation and the "installed cache" location are unspecified; pass criterion is only "all three stages complete and the review report is filed," with no per-stage assertions.
*   **Rationale:** The implementer must compose the fixture prompts and decide what "complete" means — design/test decisions left to the implementer, and the acceptance gate is unfalsifiable as written.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The prompt text lives upstream in TESTING.md (this doc must not duplicate it); the fix enumerates the shapes from §9.4, names the `muse exec` invocation form, and adds per-stage artifact assertions so "complete" is checkable.
*   ***Proposed Edit:***
    *   Location: §9.5 step 3 (L280).
    *   Change: Replace "End-to-end acceptance: the upstream fixture recorded in the Testing playbook ([TESTING.md](https://github.com/google/elephant-goldfish-model/blob/main/TESTING.md), 'Harness test record', Muse row, 2026-10-30) — fixture design `muse-wonder-1.0` (line-count design). `TESTING.md` lives at the upstream repo root and is NOT vendored. Run headless via `muse exec` in a temporary workspace (`/tmp/egm-e2e-<shape>/`) against the installed cache only — 'installed cache' means the harness's installed plugin/skill cache on that VM (the plugin installed per §9.2), not the upstream checkout — prompt naming `docs/muse.md`, approvals simulated up front: brainstorm → draft → uninterrupted review. Run once per VM shape. Pass: all three stages complete and the review report is filed." with "End-to-end acceptance: the upstream fixture recorded in the Testing playbook ([TESTING.md](https://github.com/google/elephant-goldfish-model/blob/main/TESTING.md), 'Harness test record', Muse row, 2026-10-30) — fixture design `muse-wonder-1.0` (the upstream fixture name for the brainstorm → draft → review sequence; its prompt text lives in TESTING.md, not in this document). `TESTING.md` lives at the upstream repo root and is NOT vendored. Run headless via `muse exec` (invocation: `muse exec --prompt <prompt-file>` in the temporary workspace, approvals simulated up front per the fixture) in a temporary workspace (`/tmp/egm-e2e-<shape>/`, where `<shape>` is one of the §9.4 VM shapes: `muse-cli`, `other-harness`, `headless`) against the installed cache only — 'installed cache' means the harness's installed plugin/skill cache on that VM (the plugin installed per §9.2), not the upstream checkout — prompt naming `docs/muse.md`, approvals simulated up front: brainstorm → draft → uninterrupted review. Run once per VM shape. Pass, per stage: brainstorm produces `concepts_brief.md` in the workspace; draft produces a design document; review produces a filed review report. 'Uninterrupted review' means the review stage runs with approvals simulated up front (no human turn), as in the upstream 2026-10-30 run."

### [Issue 41] [implementation_readiness-3-M3] - Severity: Major
*   **Affected Scope:** §10.6 (L347)
*   **Discrepancy Description:** Checks (2) and (3)/(6) name edge cases with no executable procedure. Check (1) ships a full shell loop; check (2) gives no command or enumeration method, and checks (3)/(6) name no parser, tool, command, or expected output.
*   **Rationale:** A test plan in which half the checks have no procedure cannot be executed on first attempt.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix gives C2 the resolve-loop command (shared with Issue 11) and C3/C6 a concrete YAML-parse + name-match command, inside the E-E list rewrite.
*   ***Proposed Edit:***
    *   Location: §10.6 checks C2, C3, C6 (shared edit E-E).
    *   Change: Apply E-E, with these procedure texts: C2 — "edge case — a wrapper `../../reference/...` target that does not exist fails the check (procedure: the §10.5 step 4 resolve loop — `for f in skills/egm-*/SKILL.md; do grep -oE '\\.\\./\\.\\./reference/[A-Za-z0-9_./-]+' \"$f\"; done | sort -u | while read -r p; do test -f \"reference/${p#../../reference/}\" || echo \"MISSING: $p\"; done` — expected output: no `MISSING` lines)."; C3 — "every `skill.yaml` parses as YAML and its `name` matches the `SKILL.md` frontmatter `name` (procedure: `python3 -c \"import yaml,sys; d=yaml.safe_load(open(sys.argv[1])); print(d['name'])\" <skill.yaml>` — expected: exit 0 and the printed name equals the frontmatter `name`)."; C6 — same procedure as C3, run on every sync and recorded in the sync record.

### [Issue 42] [implementation_readiness-3-M4] - Severity: Major
*   **Affected Scope:** §10.6 check (1) (L347) + D3 item 3 (L134)
*   **Discrepancy Description:** D3's rewritten `docs/` references are never verified. D3 rewrites five `docs/` rows, but check (1)'s grep covers only `(agents|resources)/…`. No check asserts any `<bundle>/docs/…` target resolves. A dangling `docs/muse.md` reference — the file the Muse routing line itself points at — would pass all six checks.
*   **Rationale:** A rewrite the plan mandates has zero verification coverage.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix is shared edit E-B (C1 extension to `docs/` + routing line + no upstream-relative reference remains).
*   ***Proposed Edit:***
    *   Location: §10.6 check C1 (shared edit E-B).
    *   Change: Apply E-B.

### [Issue 43] [implementation_readiness-3-M5] - Severity: Major
*   **Affected Scope:** §10.5 step 3 (L340) + §14 decision 2 (L403)
*   **Discrepancy Description:** Pilot run instruction is not invocable as written. "run `egm-review-loop` + `egm-review` once against the Phase 0 pilot target" gives no invocation mechanism or command, no brief text for the loop run itself, and the target is contingent — the PR number is unrecorded and the fallback "this document at its current HEAD" names no commit.
*   **Rationale:** The implementer must decide how a skill is invoked in Environment B and exactly what artifact/commit is under review.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix names the invocation (explicit skill invocation via subagent.spawn brief, as the pilot did) and pins the target to a commit recorded in the pilot log before dispatch (shared with Issue 59's decision-2 rewrite).
*   ***Proposed Edit:***
    *   Location: §10.5 step 3 (L340).
    *   Change: Replace "3. Pilot: run `egm-review-loop` + `egm-review` once against the Phase 0 pilot target (§14 decision 2), with an independent review subagent verifying the run (via the two checks defined in §10.3)." with "3. Pilot: run `egm-review-loop` + `egm-review` once against the Phase 0 pilot target (§14 decision 2). Invocation in Environment B: the Elephant invokes the skills explicitly via `subagent.spawn` briefs built per §10.3 (the pilot ran this way — the skills carry `disable-model-invocation: true` and are user-invocable only). Target: the commit recorded in the pilot log before dispatch (§14 decision 2). An independent review subagent verifies the run (via the two checks defined in §10.3)."

### [Issue 44] [implementation_readiness-3-M6] - Severity: Major
*   **Affected Scope:** §9.3 step 2 (L263)
*   **Discrepancy Description:** "Copy the bundle" specifies neither the command nor the file set. Step 2 is "Copy the bundle to `<install-root>/egm/`" with no copy command and no exclusion list, and it never references the §7 not-vendored list.
*   **Rationale:** Actionability gap on the step that creates the bundle in Environment A. The file set is the plan's central artifact and should be pinned at the step, not inferred.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix names the exact directories to copy (the vendored set), so no exclusion list is needed.
*   ***Proposed Edit:***
    *   Location: §9.3 step 2 (L263).
    *   Change: Replace "2) Copy the bundle to `<install-root>/egm/`." with "2) Copy the bundle to `<install-root>/egm/` with `mkdir -p <install-root>/egm && cp -r <install-root>/egm-checkout/skills <install-root>/egm-checkout/agents <install-root>/egm-checkout/resources <install-root>/egm-checkout/docs <install-root>/egm-checkout/LICENSE <install-root>/egm-checkout/plugin.json <install-root>/egm/` — exactly the vendored set (§7); `site/`, `scripts/`, `tests/`, `adapters/`, per-host plugin manifests, and all other repo-root files are not copied."

### [Issue 45] [implementation_readiness-3-M7] - Severity: Major
*   **Affected Scope:** §10.4 (L334) + §14 decision 6 (L409)
*   **Discrepancy Description:** Phase 1 execution parameters are unset until a future owner ruling. The 30-minute per-reviewer timeout is explicitly "for the pilot" (interim bound); decision 6 defers the Phase 1 timeout and whether a token budget applies to a pre–Phase 1 owner ruling, with no default or fallback value.
*   **Rationale:** Phase 1 loop runs cannot be executed without asking the owner a clarifying question.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix carries the pilot values forward as the Phase 1 interim default; §14 decision 6 may tighten them, not set them from nothing (shared with Issues 5 and 91).
*   ***Proposed Edit:***
    *   Location: §10.4 (L334); §14 decision 6 (L409).
    *   Change: In §10.4, replace "Timeout: 30 minutes per reviewer for the pilot (interim bound; no pilot log with per-reviewer elapsed times exists yet, so this bound is set now and the pilot log records actual elapsed times)." with "Timeout: 30 minutes per reviewer for the pilot (interim bound; no pilot log with per-reviewer elapsed times exists yet, so this bound is set now and the pilot log records actual elapsed times). Phase 1 interim default: the pilot's 30-minute timeout and the pilot log's token actuals carry forward; §14 decision 6 may tighten them before Phase 1, but Phase 1 does not wait on it." In §14 decision 6, replace "before Phase 1 the owner sets the per-reviewer timeout and whether a token budget applies, from the pilot log's elapsed-time and token records." with "before Phase 1 the owner may tighten the per-reviewer timeout and set a token budget, from the pilot log's elapsed-time and token records; the interim default is the pilot's 30-minute timeout and the pilot log's token actuals (see §10.4)."

### [Issue 46] [implementation_readiness-3-M8] - Severity: Major
*   **Affected Scope:** §5 (L55) + §11 table (L357)
*   **Discrepancy Description:** The two-skill Phase 2 fallback has no file-change list. "Without that ruling, Phase 2 installs the 2 review skills only" — but §11.1 lists only the 7-skill case (7 wrappers, 7 scope lines, 7 attribution rows, full bundle). Nothing states which 2 wrappers, how many scope lines, which attribution rows, or whether the CI block/manifest steps change in the fallback.
*   **Rationale:** A specified branch of the plan has no file boundary. §11.1 as written would over-install relative to the fallback.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix is shared edit E-A (the 2-skill variant: same bundle + PROVENANCE + sha256 + CI block, since D2 requires the bundle to move as one unit; only the wrappers, scope lines, and attribution rows shrink to 2).
*   ***Proposed Edit:***
    *   Location: §11.1 (shared edit E-A).
    *   Change: Apply E-A, with the 2-skill variant paragraph: "Two-skill variant (no §14 decision 5 ruling): the bundle, `.github/vendor-elephant-goldfish-model.sha256`, `PROVENANCE.md`, and the tenth `vendor-integrity` block land unchanged (D2: the bundle moves as one unit); only the wrappers shrink to `skills/egm-review/` + `skills/egm-review-loop/` (4 files), the scope file gains 2 lines, and `skills/README.md` gains 2 attribution rows. The manifest step is unchanged."

### [Issue 47] [implementation_readiness-3-M9] - Severity: Major
*   **Affected Scope:** §9.2 (L237–246) + §9.5 step 1 (L276–278)
*   **Discrepancy Description:** Per-harness verification commands are unnamed. "Verification per harness: the harness's own plugin-list/validate command" names no actual command for Claude Code, Codex, Antigravity, Cursor, or OpenCode; the only fallback is the §9.5 step 3 E2E fixture, which is itself underspecified (Issue 40).
*   **Rationale:** For every non-Muse harness, the verification chain has no executable form.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix does not invent per-harness commands (they are not verified); it makes the lookup procedure explicit — the command comes from the bundle's `docs/harnesses.md` install table, and the exact command used is recorded in the pilot log — with the E2E fixture as the verification where no validate equivalent exists.
*   ***Proposed Edit:***
    *   Location: §9.5 step 1 (L276–278).
    *   Change: Replace "Verification per harness: the harness's own plugin-list/validate command; where a harness has no validate equivalent, verification is the E2E fixture run in §9.5 step 3." with "Verification per harness: the harness's own plugin-list/validate command, taken from the bundle's `docs/harnesses.md` install table for that harness (this document does not assert a command it has not verified); the exact command used is recorded in the pilot log. Where a harness has no validate equivalent, verification is the E2E fixture run in §9.5 step 3."

### [Issue 48] [implementation_readiness-3-N1] - Severity: Nit
*   **Affected Scope:** D3 item 2 (L131–133)
*   **Discrepancy Description:** Muse routing-line insertion point unspecified. Exact line text is given ("In Muse, read `<bundle>/docs/muse.md` first.") but not where in `SKILL.md` it goes (after frontmatter, top of body, end).
*   **Rationale:** Low behavioral risk since the whole file loads, but placement is an implementer decision; one sentence would close it.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; one sentence closes it.
*   ***Proposed Edit:***
    *   Location: D3 item 2 (L131–133).
    *   Change: Append: "Insertion point: immediately after the frontmatter (first line of the body)."

### [Issue 49] [implementation_readiness-3-N2] - Severity: Nit
*   **Affected Scope:** D3 item 3 (L134)
*   **Discrepancy Description:** No literal `sed` commands for the rewrite mapping. "apply the mapping mechanically (one `sed` per row, or manual edit)" — no literal commands, though rows like `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` need escaping.
*   **Rationale:** Outcome is verifiable via §10.6 check C1, so this is a convenience gap, not a correctness gap.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; fixed inside the E-B mechanism text (literal example command for the first row, with the idempotency guard).
*   ***Proposed Edit:***
    *   Location: D3 item 3 Mechanism (shared edit E-B).
    *   Change: Apply E-B (includes the literal example `sed -i '/<bundle>\\/agents/!s|agents/|<bundle>/agents/|g' <file>`; the remaining rows follow the same form with `<bundle>` substituted per environment).

### [Issue 50] [implementation_readiness-3-N3] - Severity: Nit
*   **Affected Scope:** D4 (L152)
*   **Discrepancy Description:** PROVENANCE.md Purpose / Updating / Update history content undetermined. Field values are given for URL, SHA, date, license, and exclusions, but Purpose, Updating, and Update history are only "per the esf pattern" — and the esf exemplar's text is esf-specific, so it cannot be copied verbatim.
*   **Rationale:** The implementer must author EGM-specific prose.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the fix authors the three field values.
*   ***Proposed Edit:***
    *   Location: D4 (L152).
    *   Change: Replace "Purpose, Updating, and Update history per the esf pattern." with "Purpose: 'Vendored EGM bundle for the AEP skill catalog — the 7 `egm-*` skills' personas, standards, and instructions (see §8 D4).' Updating: 'Re-vendor is a deliberate PR per the §10.2 cadence; the pin is re-checked on every sync (D1).' Update history: '2026-11-06: initial vendor at `e9e1f06a` (Phase 2 PR).'"

### [Issue 51] [implementation_readiness-3-N4] - Severity: Nit
*   **Affected Scope:** §10.2 (L299)
*   **Discrepancy Description:** Local bundle README.md has fields but no template. Four fields listed (URL, SHA, date, license) with no literal file content or format, though it is "re-written on every re-sync."
*   **Rationale:** A one-paragraph template would make the deliverable first-attempt correct.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the fix gives the literal template.
*   ***Proposed Edit:***
    *   Location: §10.2 README.md line (L299).
    *   Change: Replace "README.md       # local pin record: upstream URL `https://github.com/google/elephant-goldfish-model`, pinned SHA (`e9e1f06a`), snapshot date `YYYY-MM-DD`, license (Apache-2.0). Written at install time; re-written on every re-sync (trigger: any upstream re-vendor or local adaptation change, per the §10.2 cadence)." with "README.md       # local pin record, literal template (four lines): `Upstream: https://github.com/google/elephant-goldfish-model`, `Pinned SHA: e9e1f06a`, `Snapshot date: YYYY-MM-DD`, `License: Apache-2.0`. Written at install time; re-written on every re-sync (trigger: any upstream re-vendor or local adaptation change, per the §10.2 cadence)."

### [Issue 52] [implementation_readiness-3-N5] - Severity: Nit
*   **Affected Scope:** D6 (L182)
*   **Discrepancy Description:** Snapshot/rollback procedure has placeholders. `<snapshot-file>` path is unnamed; "re-run the snapshot and diff it" gives no diff command; rollback says "re-vendor the bundle from the repo tree" with no command, and `git checkout -- <paths>` leaves `<paths>` unspecified.
*   **Rationale:** Recovery path only; the happy-path snapshot command is given, so the implementer can fill these in trivially — but as written they are not executable verbatim.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the fix names the snapshot file, the diff command, and the rollback paths (partly covered by the Issue 2 D6 rewrite — the `<paths>` definition; this adds the file name and diff command).
*   ***Proposed Edit:***
    *   Location: D6 (L182).
    *   Change: Replace "`find <dir> -type f -exec sha256sum {} + | sort > <snapshot-file>` for a non-repo target (mtimes alone are not content-sensitive and are not used)." with "`find <dir> -type f -exec sha256sum {} + | sort > /tmp/egm-snapshot-<run>.sha256` for a non-repo target (mtimes alone are not content-sensitive and are not used; `<run>` is the round number, e.g. `r3`). Re-run the same command to a second file and diff with `diff /tmp/egm-snapshot-<run>.sha256 /tmp/egm-snapshot-<run>-after.sha256`; any output names a modified path. Rollback re-vendor command: copy the bundle from the repo tree (`cp -r <repo>/reference/elephant-goldfish-model <local-bundle-path>`) after `git checkout -- <paths>` restores the repo tree, where `<paths>` are the paths the diff names."

### [Issue 53] [implementation_readiness-3-N6] - Severity: Nit
*   **Affected Scope:** §11.1 (L367)
*   **Discrepancy Description:** Scope-file lines and attribution-row Skill values not spelled out literally. ".github/skills-sync-scope.txt (7 lines under `[skills]`)" never lists the seven line values; "7 attribution rows" gives Notes text but not the full row text including the Skill column.
*   **Rationale:** Values are directly derivable from the §7 skill table, so risk is low; exact literals would remove all doubt for the allowlist.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the fix lists the seven scope lines and the Skill column values literally.
*   ***Proposed Edit:***
    *   Location: §11.1 (L367).
    *   Change: Replace "Modified: `.github/skills-sync-scope.txt` (7 lines under `[skills]`), `.github/skills-manifest.sha256` (regenerated via `scripts/check_skills_manifest.py --root skills --write` run from the repo root), `skills/README.md` (7 attribution rows)," with "Modified: `.github/skills-sync-scope.txt` (7 lines under `[skills]`, exactly: `egm-brainstorm`, `egm-draft`, `egm-review`, `egm-resolve`, `egm-review-loop`, `egm-bootstrap`, `egm-drift-report`), `.github/skills-manifest.sha256` (regenerated via `scripts/check_skills_manifest.py --root skills --write` run from the repo root), `skills/README.md` (7 attribution rows; Skill column values are the same 7 skill names, Source `google/elephant-goldfish-model`, License `Apache-2.0`, Notes per D4),"

### [Issue 54] [implementation_readiness-3-N7] - Severity: Nit
*   **Affected Scope:** §10.5 step 4 (L341)
*   **Discrepancy Description:** Sync-check temp dir unnamed; already-rewritten paths unhandled. "copy … to a temp dir" names no path (e.g. `mktemp -d`); the two `sed` expressions handle only `~/workspace/egm` and `/home/hatch/workspace/egm` forms, with no instruction if a local file already contains the `../../reference/…` form.
*   **Rationale:** Minor; the step is otherwise fully specified with literal commands.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the fix names `mktemp -d` and states the already-rewritten case explicitly.
*   ***Proposed Edit:***
    *   Location: §10.5 step 4 (L341).
    *   Change: Replace "copy the seven local `custom-skills/egm-*/SKILL.md` files to a temp dir preserving their `egm-*/SKILL.md` layout (one `egm-*/` subdir per skill)," with "copy the seven local `custom-skills/egm-*/SKILL.md` files to a temp dir created with `mktemp -d` (e.g. `/tmp/egm-sync-XXXXXX`), preserving their `egm-*/SKILL.md` layout (one `egm-*/` subdir per skill)," and append to the step: "A local file that already contains the `../../reference/…` form needs no rewrite — both `sed` expressions are no-ops on it (neither pattern matches) — but a file mixing both forms fails the check and must be normalized by hand."

### [Issue 55] [implementation_readiness-3-N8] - Severity: Nit
*   **Affected Scope:** §10.3.3 (L323) + §10.4 (L334)
*   **Discrepancy Description:** Gate questions lack literal text. Only the section-approval question is quoted verbatim; the readiness gate has no question text, and the driver "asks the owner one question" on cap/churn with options listed but no literal question.
*   **Rationale:** Conversational wording is low-stakes, but the driver interaction is not reproducible verbatim as specified.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the fix quotes both questions literally.
*   ***Proposed Edit:***
    *   Location: §10.3.3 (L323); §10.4 (L334).
    *   Change: In §10.3.3, after "Readiness gate (fires before a review loop starts): the target document exists, reviewers and standards resolve to existing files, and GoldfishContext is provided" insert: " Readiness-gate question (literal): 'Target document and reviewer panel verified — proceed with the review loop?' (options: proceed / stop)." In §10.4, replace "on cap or churn the driver stops and asks the owner one question (accept and proceed / continue past the cap / return to drafting)" with "on cap or churn the driver stops and asks the owner one question, literally: 'The loop hit its cap (5 rounds) with unsettled findings — how do you want to proceed?' (options: accept and proceed / continue past the cap / return to drafting)".

### [Issue 56] [implementation_readiness-3-N9] - Severity: Nit
*   **Affected Scope:** §14 decision 3 (L404)
*   **Discrepancy Description:** "Move §9 to an appendix" has no procedure. The documented-but-unexecuted option is defined as "§9 is moved to an appendix," with no specified appendix location, heading, or step for performing the move.
*   **Rationale:** A conditional restructuring of the document itself is left to whoever executes the ruling.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the fix names the appendix heading and the move step.
*   ***Proposed Edit:***
    *   Location: §14 decision 3 (L404).
    *   Change: Replace "'Documented-but-unexecuted' means: §9 carries the header note 'Provisional — validation pending owner provisioning.', §9 is moved to an appendix, and the Phase 3 gate records the ruling and its date." with "'Documented-but-unexecuted' means: §9 carries the header note 'Provisional — validation pending owner provisioning.', §9 is moved to an appendix (new heading `## Appendix A — Environment A (general-purpose Linux VM)`, placed after §14 and before the Sources appendix; all `§9` cross-references become `Appendix A` cross-references), and the Phase 3 gate records the ruling and its date."

### [Issue 57] [comprehension-3-B1] - Severity: Blocker
*   **Affected Scope:** §9.3 (L261–263)
*   **Discrepancy Description:** `<install-root>` definition contradicts its own layout and example. Line 261 defines `<install-root>` as "the directory holding the cloned repo and the installed skills, default `$HOME/egm`", then states the bundle is at `<install-root>/egm/` (i.e. `$HOME/egm/egm/`) — but the same paragraph's example says a Path 2 skill contains `$HOME/egm/agents/design_critic.md` (i.e. bundle = `$HOME/egm`). The Environment B mapping (`<install-root>` = `~/workspace`, bundle `~/workspace/egm/`) fits the `<install-root>/egm/` form, so the generic default should apparently be `$HOME`, not `$HOME/egm`.
*   **Rationale:** A fresh engineer cannot determine the actual Path 2 paths; the install steps in line 263 inherit the contradiction.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The default is `$HOME`, not `$HOME/egm` — the Environment B mapping proves the `<install-root>/egm/` form. The fix is shared edit E-F.
*   ***Proposed Edit:***
    *   Location: §9.3 (shared edit E-F).
    *   Change: Apply E-F.

### [Issue 58] [comprehension-3-B2] - Severity: Blocker
*   **Affected Scope:** §5 (L55) vs §11 (L353–355) and §11.1 (L367)
*   **Discrepancy Description:** Phase sequencing is self-contradictory. §5: "Without that ruling, Phase 2 installs the 2 review skills only; `egm-bootstrap` and `egm-drift-report` deferred to Phase 1." Phase 1 precedes Phase 2 and (§11) already installs the remaining 5 skills locally, so deferring skills "to Phase 1" after a Phase 2 condition is temporally incoherent; §11 Phase 2 says "without it, Phase 2 installs the 2 review skills only" while §11.1 unconditionally lists all 7 `skills/egm-*/` wrappers.
*   **Rationale:** The reviewer cannot paraphrase what Phase 2 contains with vs. without the ruling.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix is shared edit E-A.
*   ***Proposed Edit:***
    *   Location: §5, §11, §11.1 (shared edit E-A).
    *   Change: Apply E-A.

### [Issue 59] [comprehension-3-B3] - Severity: Blocker
*   **Affected Scope:** §14 decision 2 (L403)
*   **Discrepancy Description:** Pilot target cannot be paraphrased. "The AEP repo, with the Phase 2 PR … as the target state; the reviewed artifact is this document. If the pilot runs before that PR exists, the target is this document at its current HEAD." Three different targets are named in one decision (repo / PR-as-target-state / this document), with no statement of which one the reviewers actually read.
*   **Rationale:** Since the pilot is the evidence gate for everything downstream (§14 decision 5), this ambiguity blocks understanding of the rollout.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix names one target (this document at a recorded commit) and demotes the repo/PR to context.
*   ***Proposed Edit:***
    *   Location: §14 decision 2 (L403).
    *   Change: Replace "2. **Phase 0 pilot target:** the AEP repo, with the Phase 2 PR (branch `chore/reference-vendor-elephant-goldfish-model`) as the target state; the reviewed artifact is this document. If the pilot runs before that PR exists, the target is this document at its current HEAD (as the round-1 pilot did). The Elephant records the chosen PR number in the pilot log before dispatch." with "2. **Phase 0 pilot target:** the reviewed artifact is this document at the commit recorded in the pilot log before dispatch (as the round-1 pilot did — this document at its then-current HEAD). The AEP repo is context (GoldfishContext), not the target: the Phase 2 PR (branch `chore/reference-vendor-elephant-goldfish-model`) is the target state the pilot's evidence supports, not the artifact under review. The Elephant records the chosen commit SHA in the pilot log before dispatch."

### [Issue 60] [comprehension-3-M1] - Severity: Major
*   **Affected Scope:** §8.2 + §14 (L79, 204–207, 308, 334, 399–409)
*   **Discrepancy Description:** The "owner" / "human" / "Elephant" actors are never distinguished. §7 introduces "the human" (explicit approval gates); §8.2 defines the Elephant as "the main agent" in Environment B; §10.2 says the sync owner is "the agent running the sync (the Elephant / main agent…) — not a separate role"; yet §10.4 and §14 repeatedly require "the owner" to rule, be asked one question, and approve merges.
*   **Rationale:** The document never says who the owner is, whether owner = human = user, or how the owner is reached. Every phase gate and open decision depends on this actor.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix adds actor definitions to §1 Terminology.
*   ***Proposed Edit:***
    *   Location: §1 Terminology (L20).
    *   Change: After "Terminology: 'Muse' is the harness/assistant product; '`muse` CLI' is its command-line tool; 'current Muse environment' means Environment B (this VM, which has no `muse` CLI)." insert: "Actors: 'Owner' is the human user who owns the AEP repo and this environment — the same 'human' in §7's approval gates — reached by the main agent in chat; the owner rules on open decisions, answers the driver's one question, and approves merges. 'Elephant' is the agent session that owns the design doc and runs the loop (Environment B: the main agent). The Elephant is not the owner; the sync 'owner' in §10.2 is the Elephant acting in its sync capacity, not the human owner."

### [Issue 61] [comprehension-3-M2] - Severity: Major
*   **Affected Scope:** §§3, 7, 10.4, D7 (L37, 82–83, 104, 184–193, 334)
*   **Discrepancy Description:** Reviewer-panel membership is incoherent: 10 vs 5 vs 15. §7 calls all 10 personas "reviewer personas"; §3 says the pilot had "all 5 reviewers"; §10.4 caps at "5 reviewers per round"; the §7 fixture used "15 fresh-context reviewers"; D7 lists 10 named agents including `egm-synthesizer` and `egm-bootstrap-orchestrator`, which are not reviewers.
*   **Rationale:** The document never states which 5 personas form the `egm-review-loop` panel, so a fresh reader cannot reconstruct who reviews what.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix states the panel membership in §7 and §10.4 and explains the 15.
*   ***Proposed Edit:***
    *   Location: §7 (L82–83); §10.4 (L334).
    *   Change: In §7, replace "10 reviewer personas (`agents/`, 30–101 lines each)" with "10 personas (`agents/`, 30–101 lines each), of which 5 form the `egm-review-loop` panel: design_critic, structural, implementation_readiness, comprehension, zoom_out. The other 5 (`egm-style`, `egm-codebase-details`, `egm-inventive-catalyst`, `egm-synthesizer`, `egm-bootstrap-orchestrator`) are not loop reviewers — the synthesizer consolidates only where the harness nests subagents (§8.2), and the bootstrap orchestrator belongs to `egm-bootstrap`, not to review." In §10.4, replace "at most 5 reviewers per round" with "at most 5 reviewers per round (the panel named in §7: design_critic, structural, implementation_readiness, comprehension, zoom_out)". In §7, append to the fixture sentence: "The fixture's '15 fresh-context reviewers' is the upstream E2E fixture's reviewer count across its brainstorm/draft/review stages, not this loop's 5-reviewer panel."

### [Issue 62] [comprehension-3-M3] - Severity: Major
*   **Affected Scope:** §10.4 (L334)
*   **Discrepancy Description:** Convergence depends on four undefined dispositions. "'Unsettled' means a Blocker or Major that is neither fixed in the target nor recorded CONTEST, ESCALATE, DECLINE, or SETTLED in the resolve report." None of the four dispositions is defined anywhere in the document — not what each means, who records it, or how CONTEST differs from DECLINE.
*   **Rationale:** "Two consecutive clean rounds" (the loop's termination condition) is therefore not determinable from this document.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix defines all four dispositions in §10.4, next to 'Unsettled'.
*   ***Proposed Edit:***
    *   Location: §10.4 (L334).
    *   Change: Append to the 'Unsettled' sentence: " Dispositions (recorded by the Elephant in the resolve report): CONTEST — the finding is inaccurate, with checkable evidence cited (a file and symbol, or a decision recorded in the document); ESCALATE — the finding is inaccurate but the evidence is outside every file the reviewer could read (an owner decision or convention), so it goes to the owner; DECLINE — the finding is recorded with no fix (cosmetic, or out of scope for this document); SETTLED — a re-raise of a finding already recorded with one of the above dispositions at the same scope, not re-opened."

### [Issue 63] [comprehension-3-M4] - Severity: Major
*   **Affected Scope:** §§8.2, 10.4 (L206, 334)
*   **Discrepancy Description:** "Churn" is undefined. The Driver "stops and asks the owner on cap/churn" and "on cap or churn the driver stops and asks the owner one question." "Cap" is inferable (5 rounds), but "churn" — what counts as churn, how it is measured, what threshold triggers the stop — is never defined.
*   **Rationale:** The loop's stop condition cannot be applied as written.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix defines churn with a threshold in §10.4.
*   ***Proposed Edit:***
    *   Location: §10.4 (L334).
    *   Change: Append: " Churn: a new finding at the scope of an applied fix whose revert would resolve it, or a round whose unsettled findings substantially restate the previous round's fixed findings. Threshold: the first occurrence — on churn the driver stops and asks the owner one question (see the cap/churn question in §10.4)."

### [Issue 64] [comprehension-3-M5] - Severity: Major
*   **Affected Scope:** §14 vs body (L401–402, 405–409 vs L110–116, 168–176, 334)
*   **Discrepancy Description:** Decisions listed as open are already stated as decided in the body. Decision 1 (pin SHA) recommends `e9e1f06a`, which D1/§7/§11.1 already treat as pinned; decision 4 (force-sync policy) restates D5's already-stated policy; decision 6 (owner sets per-reviewer timeout before Phase 1) follows §10.4 already setting 30 minutes.
*   **Rationale:** A fresh reader cannot tell which of these are genuinely open vs. already settled and merely awaiting ratification.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix relabels decisions 1, 4, and 6 as ratifications of body decisions, leaving 2, 3, and 5 genuinely open.
*   ***Proposed Edit:***
    *   Location: §14 decisions 1, 4, 6 (L401–402, 405–409).
    *   Change: Replace decision 1 with "1. **Pin SHA (ratification):** the body already pins `e9e1f06a` (D1, §7, §11.1); the owner ratifies that pin, or names a different SHA (see D1's single-source-of-truth note)." Replace decision 4 with "4. **Force-sync policy (ratification):** the body already states the D5 policy (upstream fix / baseline entry / owner force-sync); the owner ratifies it." Replace decision 6 with "6. **Phase 1 loop bounds (ratification or tightening):** the body already sets the interim default (pilot's 30-minute timeout, pilot log's token actuals — §10.4); the owner ratifies it or tightens it before Phase 1."

### [Issue 65] [comprehension-3-M6] - Severity: Major
*   **Affected Scope:** §§2, 5, 14 (L28, 55, 59, 408)
*   **Discrepancy Description:** The pilot-value ruling has no criteria. The §14 decision 5 ruling ("whether the pilot demonstrated marginal value over the existing instruments") gates the remaining 5 skills, but no metric, threshold, or evidence standard is given; §5 admits no roundtable baseline control run was performed, so the 65-finding pilot cannot establish marginal value — yet the ruling is the sole mechanism for judging it. The §2 goal "findings categorized" is likewise undefined.
*   **Rationale:** A gate with no criteria cannot be applied; the ruling would be a bare judgment call.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix gives decision 5 three explicit criteria (defects the incumbents missed; finding action rate; qualitative judgment recorded with reasons) and defines the categorization taxonomy (shared with Issue 3).
*   ***Proposed Edit:***
    *   Location: §14 decision 5 (L408); §2 pilot goal (L28).
    *   Change: Replace decision 5 with "5. **Pilot-value ruling:** after the Phase 0 pilot, the owner rules whether the pilot demonstrated marginal value over the existing instruments. Criteria (all recorded in the ruling): (a) the pilot found defects the incumbents had not surfaced (the round-1 pilot: 65 findings including 3 Blockers, among them a genuine D3/Path 1 contradiction and a missing CI edit); (b) the finding action rate (§2) is above 0% — at least one filed finding led to a change in the reviewed document; (c) the qualitative judgment, with reasons stated. No roundtable baseline control run was performed, so the ruling is a judgment against these criteria, not a controlled comparison — and the ruling must say so." In §2, the pilot goal already gains the taxonomy via Issue 3's edit ("Findings are categorized by severity (Blocker / Major / Nit) and by scope (the section each finding targets).").

### [Issue 66] [comprehension-3-M7] - Severity: Major
*   **Affected Scope:** §10.2 (L308)
*   **Discrepancy Description:** Canonical direction contradicts itself. "The AEP repo is canonical for the wrappers; the local bundle … is canonical for the installed personas and standards. Sync runs in the existing live→repo direction… and any re-vendor replaces the local bundle wholesale from the repo tree." If the local bundle is canonical for personas/standards, replacing it wholesale from the repo tree (where the bundle is a copy) inverts the stated direction.
*   **Rationale:** The paragraph asserts both live→repo and repo→local without reconciling which artifact flows which way.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix rewrites the paragraph to state per-artifact canonicity: wrappers flow live→repo; the bundle flows upstream→repo→local (the repo tree is the reference copy, re-vendor replaces local from it).
*   ***Proposed Edit:***
    *   Location: §10.2 (L308).
    *   Change: Replace "Canonical direction: the AEP repo is canonical for the wrappers (`skills/egm-*/`); the local bundle at `~/workspace/egm/` is canonical for the installed personas and standards. Sync runs in the existing live→repo direction: any change to a local adapted skill is copied into the repo wrappers by the next sync (Sync steps (live→repo direction only): 1) diff local `custom-skills/egm-*/` against repo `skills/egm-*/`; 2) copy changed local files into the repo wrappers; 3) regenerate the manifest (`scripts/check_skills_manifest.py --root skills --write` from the repo root); 4) verify with the §10.5 step 4 normalize-then-diff check; 5) commit per Conventional Commits. Owner: the agent running the sync (the Elephant / main agent session that owns the change) — not a separate role.), and any re-vendor replaces the local bundle wholesale from the repo tree." with "Canonical direction, per artifact: the local adapted skills are canonical for wrapper content — sync runs live→repo (Sync steps (live→repo direction only): 1) diff local `custom-skills/egm-*/` against repo `skills/egm-*/`; 2) copy changed local files into the repo wrappers; 3) regenerate the manifest (`scripts/check_skills_manifest.py --root skills --write` from the repo root); 4) verify with the §10.5 step 4 normalize-then-diff check; 5) commit per Conventional Commits. Owner: the agent running the sync (the Elephant / main agent session that owns the change) — not a separate role.). The bundle flows the other way: upstream → repo tree → local — the repo's `reference/elephant-goldfish-model/` is the reference copy, and any re-vendor replaces the local bundle wholesale from the repo tree. The local bundle is therefore not canonical for personas and standards; it is a working copy of the repo reference, which is itself a copy of upstream at the pinned SHA."

### [Issue 67] [comprehension-3-M8] - Severity: Major
*   **Affected Scope:** §§10.3.1, 10.3.5, 10.5 (L312–314, 330, 340)
*   **Discrepancy Description:** The memory-prohibition check is circular and has no verifier. §10.3.1 says the memory prohibition "is enforced by the brief … and checked the same way" (as the line-existence/standard-name checks), then says §10.5 step 3's independent subagent "performs exactly these two checks" — but those two checks are line-existence and standard-name, neither of which can detect a finding whose rationale cites memory.
*   **Rationale:** No mechanism for detecting memory/conversation citation is ever described, so the prohibition is unenforceable as written.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix defines the check as a third, distinct check: a read-through of each finding's rationale for memory/conversation citation.
*   ***Proposed Edit:***
    *   Location: §10.3.1 (L314); §10.5 step 3 (L340).
    *   Change: In §10.3.1, replace "The memory prohibition is enforced by the brief (it forbids retrieval) and checked the same way: a finding whose rationale cites memory or conversation content is discarded and the reviewer is not re-dispatched. The independent verification subagent in §10.5 step 3 performs exactly these two checks against the filed reports: (a) every cited line exists in the target at the stated range; (b) the named standard is the assigned one." with "The memory prohibition is enforced by the brief (it forbids retrieval) and checked by a third, distinct check: the independent verification subagent in §10.5 step 3 reads each finding's rationale and flags any that cites memory or conversation content (a quote of, or a paraphrase that depends on, prior context rather than the target document and its GoldfishContext); a flagged finding is discarded and the reviewer is not re-dispatched. The independent verification subagent performs three checks against the filed reports: (a) every cited line exists in the target at the stated range; (b) the named standard is the assigned one; (c) no finding's rationale cites memory or conversation content." In §10.5 step 3, replace "(via the two checks defined in §10.3)" with "(via the three checks defined in §10.3.1)". In §10.3.5, replace "Enforcement of the read requirement is the line-existence check" with "Enforcement of the read requirement is the line-existence check, and of the memory prohibition is check (c) in §10.3.1".

### [Issue 68] [comprehension-3-M9] - Severity: Major
*   **Affected Scope:** §12 (L379–380)
*   **Discrepancy Description:** The principal risk control is unparseable. "Treat Goldfish reviewers as unprivileged-but-able-to-write until the harness proves otherwise. Never give a reviewer a write tool it did not ask for by design." "Unprivileged-but-able-to-write" is an unexplained oxymoron, and "a write tool it did not ask for by design" cannot be parsed.
*   **Rationale:** This is the document's own principal risk (§12, D6); its wording must be unambiguous.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix rewrites both sentences in plain terms.
*   ***Proposed Edit:***
    *   Location: §12 (L379–380).
    *   Change: Replace "treat Goldfish reviewers as unprivileged-but-able-to-write until the harness proves otherwise. Never give a reviewer a write tool it did not ask for by design; enforcement is the post-run snapshot diff in D6 (snapshot before dispatch, diff after each reviewer; any unexpected modification fails that reviewer's round)." with "treat Goldfish reviewers as unprivileged in intent but able to write in fact — assume they can write to the filesystem and to memory unless the harness proves otherwise. Give a reviewer only the tools its brief names: the read-only brief names no write tool, and no write tool is ever added to a reviewer brief; enforcement is the post-run snapshot diff in D6 (snapshot before dispatch, diff once after the round; any unexpected modification fails the round)."

### [Issue 69] [comprehension-3-M10] - Severity: Major
*   **Affected Scope:** §9.1 (L215)
*   **Discrepancy Description:** "pilot VM" is a third, undefined VM. "`python3` ≥ 3.12.3 (verified floor on the pilot VM) … installed … on the fresh VM (absent on this VM — record the installed version in the pilot log)." The document defines only Environment A (fresh VM) and Environment B (this VM); "pilot VM" appears nowhere else and is never equated with either.
*   **Rationale:** A fresh reader cannot tell which VM anything was verified on.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The verified floor was measured on this VM (Environment B); the fix says so and pins down the "absent" clause to pytest.
*   ***Proposed Edit:***
    *   Location: §9.1 (L215).
    *   Change: Replace "- `git` ≥ 2.43.0, `python3` ≥ 3.12.3 (verified floor on the pilot VM), `pytest`, installed before §9.5 step 2 with `python3 -m pip install pytest` on the fresh VM (absent on this VM — record the installed version in the pilot log), and one supported harness CLI — Muse ≥ 1.4.14 (the upstream-verified version)." with "- `git` ≥ 2.43.0, `python3` ≥ 3.12.3 (verified floor on this VM, Environment B), `pytest`, installed before §9.5 step 2 with `python3 -m pip install pytest` on the fresh VM (`pytest` is absent on this VM — record the installed version in the pilot log), and one supported harness CLI — Muse ≥ 1.4.14 (the upstream-verified version). There is no third 'pilot VM': the two environments are A (fresh VM) and B (this VM) only."

### [Issue 70] [comprehension-3-M11] - Severity: Major
*   **Affected Scope:** §9.2 (L245) vs §9.4 (L270)
*   **Discrepancy Description:** Cursor's status contradicts itself. §9.2: Cursor is "experimental, unverified upstream … not a supported Path 1 route until verified." §9.4's decision matrix lists "Another supported harness (Claude/Codex/Cursor/OpenCode/Antigravity) → Path 1 (native install)".
*   **Rationale:** A fresh reader cannot tell whether Cursor is a supported Path 1 route.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix removes Cursor and OpenCode from the supported row and footnotes their status.
*   ***Proposed Edit:***
    *   Location: §9.4 (L270).
    *   Change: Replace "| Another supported harness (Claude/Codex/Cursor/OpenCode/Antigravity) | Path 1 (native install) | Per-harness subagent tool |" with "| Another supported harness (Claude Code / Codex / Antigravity) | Path 1 (native install) | Per-harness subagent tool |" and append after the table: "Cursor and OpenCode are experimental / unverified upstream (§9.2) and are not supported Path 1 routes until verified; a VM with only Cursor or OpenCode installed follows the headless row (Path 2, Muse only) or does not adopt."

### [Issue 71] [comprehension-3-M12] - Severity: Major
*   **Affected Scope:** §10.5 step 4 (L341)
*   **Discrepancy Description:** Sync check claims coverage its procedure does not perform. The procedure copies only the seven `SKILL.md` files to a temp dir, seds them, and diffs against repo `skills/egm-*/`; it never copies `skill.yaml`. The same line then claims "The sync check also covers `skill.yaml`" via re-validation (YAML parses + name matches) — which is a parse check, not a content diff, so `skill.yaml` content drift between local and repo would not be caught. Also, the second `sed` (expanded `/home/hatch/...` form) is dead by D3's own statement that the expanded form "never appears in a pilot adapted file" (line 134).
*   **Rationale:** The claimed coverage exceeds the procedure's actual coverage.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid on both points. The fix copies `skill.yaml` too (content diff) and deletes the dead second `sed`, stating why.
*   ***Proposed Edit:***
    *   Location: §10.5 step 4 (L341).
    *   Change: Replace "4. Sync check: copy the seven local `custom-skills/egm-*/SKILL.md` files to a temp dir preserving their `egm-*/SKILL.md` layout (one `egm-*/` subdir per skill), run `sed -i 's|~/workspace/egm|../../reference/elephant-goldfish-model|g'` and `sed -i 's|/home/hatch/workspace/egm|../../reference/elephant-goldfish-model|g'` on the copies, then `diff -r` the temp dir against the repo `skills/egm-*/` — expecting zero differences." with "4. Sync check: copy the seven local `custom-skills/egm-*/SKILL.md` files and the seven `skill.yaml` files to a temp dir preserving their `egm-*/SKILL.md` + `egm-*/skill.yaml` layout (one `egm-*/` subdir per skill), run `sed -i 's|~/workspace/egm|../../reference/elephant-goldfish-model|g'` on the `SKILL.md` copies, then `diff -r` the temp dir against the repo `skills/egm-*/` — expecting zero differences (this diffs `skill.yaml` content too, not just `SKILL.md`). The second `sed` for the expanded `/home/hatch/workspace/egm` form is deleted: D3 states the expanded form never appears in a pilot adapted file, so the expression is dead." Replace "The sync check also covers `skill.yaml`: on every sync, every `skill.yaml` is re-validated (YAML parses, `name` matches the `SKILL.md` frontmatter `name`); a mismatch fails the sync." with "The sync check covers `skill.yaml` by content diff (above) and by re-validation on every sync (YAML parses, `name` matches the `SKILL.md` frontmatter `name`); a mismatch fails the sync."

### [Issue 72] [comprehension-3-M13] - Severity: Major
*   **Affected Scope:** §11 Phase 2 gate (L355) vs §14 decision 3 (L404)
*   **Discrepancy Description:** Phase 2 is gated on a Phase 3 decision. Phase 2 merges only once "§14 decision 3 [is] ruled (fresh VM provisioned, or Phase 3 marked documented-but-unexecuted…)". Decision 3 is the Phase 3 provisioning ruling, required "before Phase 2 merges" — so the AEP PR (Phase 2) is blocked on provisioning a fresh VM for a later phase, or on a ruling that moves §9 to an appendix.
*   **Rationale:** The temporal dependency is never explained.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix is shared edit E-A (decision 3 gates Phase 3 only, not Phase 2).
*   ***Proposed Edit:***
    *   Location: §11 Phase 2 gate row; §14 decision 3 (shared edit E-A).
    *   Change: Apply E-A.

### [Issue 73] [comprehension-3-M14] - Severity: Major
*   **Affected Scope:** D4 Wrappers bullet (L156)
*   **Discrepancy Description:** Skills-freshness sentence negates itself. "The gate proves the repo `skills/` tree equals the manifest generated from the repo tree after the last sync from live — it detects no drift against the upstream bundle and no drift against local `custom-skills/`." Read literally, "it detects no drift" states the gate's result; the intended meaning (a limitation) requires the reader to infer the negation from context.
*   **Rationale:** As the definition of a gate's coverage, this must be unambiguous.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; one-word-class fix.
*   ***Proposed Edit:***
    *   Location: D4 Wrappers bullet (L156).
    *   Change: Replace "it detects no drift against the upstream bundle and no drift against local `custom-skills/`." with "it detects neither drift against the upstream bundle nor drift against local `custom-skills/`."

### [Issue 74] [comprehension-3-M15] - Severity: Major
*   **Affected Scope:** D6 (L182)
*   **Discrepancy Description:** Snapshot procedure is Environment B-only, but the caveat is claimed for both environments. The snapshot scope is given only in local paths (target repo tree + `~/workspace/egm/` + `~/workspace/custom-skills/egm-*/`); §9.5 (Environment A verification) never mentions snapshotting, and no Environment A / Path 1 snapshot scope or command is defined — yet §12 calls the read-only caveat "the principal risk in both environments."
*   **Rationale:** A control claimed for both environments must be defined in both.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix adds an Environment A snapshot scope to §9.5 step 4 (Path 1: install dirs + temp workspace; Path 2: `<install-root>` paths) and cross-references D6.
*   ***Proposed Edit:***
    *   Location: §9.5 step 4 (L281).
    *   Change: Append to step 4: " Snapshot (Environment A, per D6): before dispatch, snapshot by content hash with the D6 command — Path 1 scope is the cloned repo, the installed plugin dir, and the temp workspace (`/tmp/egm-e2e-<shape>/`); Path 2 scope is `<install-root>/egm/`, `<install-root>/skills/egm-*/`, and the temp workspace. Diff once after the round; any unexpected modification fails the round (D6). Memory/DB paths are out of scope in both environments (D6 residual)."

### [Issue 75] [comprehension-3-N1] - Severity: Nit
*   **Affected Scope:** §8.1 (L198)
*   **Discrepancy Description:** Stale/wrong line pointer. "The normative definitions are the D4 bullets (lines 121–129)." Lines 121–129 are D2 and the start of D3; the D4 bullets are lines 136–166.
*   **Rationale:** A reader following the pointer lands on the wrong decisions. §8.1 is otherwise content-free ("a pointer only"), so the section contributes nothing but this wrong reference.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix is shared edit E-C (delete §8.1).
*   ***Proposed Edit:***
    *   Location: §8.1 (shared edit E-C).
    *   Change: Apply E-C.

### [Issue 76] [comprehension-3-N2] - Severity: Nit
*   **Affected Scope:** §1 (L22)
*   **Discrepancy Description:** Forward reference before definition. "Path 1 installs upstream verbatim and carries no adapted copies" appears in §1, but Path 1 is not defined until §9.2 (line 218).
*   **Rationale:** A fresh reader meets the term 200 lines before its meaning.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; one definition sentence in §1 closes it.
*   ***Proposed Edit:***
    *   Location: §1 (L22).
    *   Change: After "One vendored content set, two installation mechanisms; Path 1 installs upstream verbatim and carries no adapted copies." insert: "(Path 1 = plugin install, §9.2; Path 2 = vendored skills, §9.3.)"

### [Issue 77] [comprehension-3-N3] - Severity: Nit
*   **Affected Scope:** §3 (L37)
*   **Discrepancy Description:** "Scale baseline" asserts and retracts itself in one sentence. "Scale baseline (verified 2026-11-06): adoption is precautionary — no drift incident or review-load count is recorded in this document." Nothing verifiable is baselined; the sentence labels as "verified" the absence of any recorded count, and then says the Phase 0 pilot log "records design docs produced per month" — a log that does not yet exist at draft time.
*   **Rationale:** The "verified" label on an absence is self-contradictory.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the fix drops the false "verified" label and states what the baseline is (none yet) and where it will be recorded.
*   ***Proposed Edit:***
    *   Location: §3 (L37).
    *   Change: Replace "Scale baseline (verified 2026-11-06): adoption is precautionary — no drift incident or review-load count is recorded in this document." with "Scale baseline: none recorded — adoption is precautionary (no drift incident or review-load count is recorded in this document)."

### [Issue 78] [comprehension-3-N4] - Severity: Nit
*   **Affected Scope:** §7 (L97) and §10.5 (L339)
*   **Discrepancy Description:** Exclusion list ends in an open catch-all. "and all other repo-root files" is not enumerable: a fresh engineer cannot determine from this document which repo-root files are excluded from the vendor, which matters because the §10.5 step 2 zero-diff check and the vendor-integrity hash both depend on the exact file set.
*   **Rationale:** The included set must be exactly enumerable.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix defines the exclusion by the inclusion: the §10.5 step 2 diff command enumerates the included set, so "all other" is everything else by construction.
*   ***Proposed Edit:***
    *   Location: §7 (L97); §10.5 step 2 (L339).
    *   Change: In §7, replace "and all other repo-root files." with "and all other repo-root files (the included set is exactly the paths in the §10.5 step 2 diff command — `skills/`, `agents/`, `resources/`, `docs/`, `LICENSE`, `plugin.json` — so every other repo-root file is excluded by construction)." In §10.5 step 2, append: "The diff command enumerates the included set; any repo-root file it does not name is excluded."

### [Issue 79] [comprehension-3-N5] - Severity: Nit
*   **Affected Scope:** §11.1 (L367)
*   **Discrepancy Description:** The `skills/` 38-file count does not derive from its own breakdown. "per skill `SKILL.md`, `TEST.md`, `agents/openai.yaml`, `assets/icon.svg`, `test_scenarios.yaml` (7 × 5 = 35), plus `references/` in `egm-bootstrap` and `egm-draft`" — the breakdown sums to 35 plus an unstated number of `references/` files to reach 38.
*   **Rationale:** The arithmetic is not reproducible from the text.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the counts were verified against the local bundle (`egm-bootstrap/references/` = 2 files, `egm-draft/references/` = 1 file; 35 + 2 + 1 = 38).
*   ***Proposed Edit:***
    *   Location: §11.1 (L367).
    *   Change: Replace "`skills/` (38 files: per skill `SKILL.md`, `TEST.md`, `agents/openai.yaml`, `assets/icon.svg`, `test_scenarios.yaml`, plus `references/` in `egm-bootstrap` and `egm-draft`)" with "`skills/` (38 files: per skill `SKILL.md`, `TEST.md`, `agents/openai.yaml`, `assets/icon.svg`, `test_scenarios.yaml` — 7 × 5 = 35 — plus `references/` in `egm-bootstrap` (2 files) and `egm-draft` (1 file): 35 + 2 + 1 = 38)".

### [Issue 80] [comprehension-3-N6] - Severity: Nit
*   **Affected Scope:** §10.6 (L343–347)
*   **Discrepancy Description:** Two numbering schemes collide, and check (2) has no procedure. "§10.5 steps 1–4 are the procedure; the checks below are the normative test list — a step and a check with the same number are not the same item" forces the reader to track two parallel numberings. Check (1) gets a full shell command; check (2) gets no command or method at all.
*   **Rationale:** Same collision as Issue 25, plus the missing C2 procedure from Issue 41.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; fixed by shared edit E-E (relabel + procedures).
*   ***Proposed Edit:***
    *   Location: §10.6 (shared edit E-E).
    *   Change: Apply E-E.

### [Issue 81] [comprehension-3-N7] - Severity: Nit
*   **Affected Scope:** §§9.5, 8.2, 10.3.5 (L207, 280, 330)
*   **Discrepancy Description:** Undefined in-group vocabulary. "depth-2 spawning" (§8.2 Synthesizer row, with a self-reference to "this review itself"); "`muse-wonder-1.0` (line-count design)" and "uninterrupted review" (§9.5 step 3); the "verbatim prompt" pinned to `skills/egm-review-loop/SKILL.md:34` (§10.3.5, a line number in a file the reader does not have).
*   **Rationale:** Each is used in a normative instruction without definition or a resolvable pointer.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix defines each term where it is used (`muse-wonder-1.0` and "uninterrupted review" are defined by the Issue 40 edit; this adds "depth-2 spawning" and the verbatim-prompt pointer).
*   ***Proposed Edit:***
    *   Location: §8.2 Synthesizer row (L207); §10.3.5 (L330).
    *   Change: In the §8.2 Synthesizer row, replace "(direct dispatch from the Elephant by design — flat dispatch keeps attribution simple; this is a design choice, not a platform limit: depth-2 spawning works in this environment, as this review itself runs at depth 2)" with "(direct dispatch from the Elephant by design — flat dispatch keeps attribution simple; this is a design choice, not a platform limit: depth-2 spawning — a subagent spawning its own subagent — works in this environment)". In §10.3.5, replace "The verbatim prompt is the review instruction formed from the Delegation section of `skills/egm-review-loop/SKILL.md:34` (bundle path `<bundle>/skills/egm-review-loop/SKILL.md`, '## Delegation')" with "The verbatim prompt is the review instruction formed from the Delegation section of the bundle's `skills/egm-review-loop/SKILL.md` ('## Delegation'; line 34 in the vendored file at the pinned SHA)".

### [Issue 82] [comprehension-3-N8] - Severity: Nit
*   **Affected Scope:** D5 (L168–176); §13 (L396–397); §10.3.3 (L323)
*   **Discrepancy Description:** Undefined terms / missing pointers a fresh reader needs. SkillSpector is never defined or linked (only its invocation, score threshold, and baseline-file format are given); §13 says NeuroStrata "is covered separately" with no path to the companion document; §10.3.3's pilot GoldfishContext "supplied the companion doc, README, and repo clone" without naming which repo clone or its path.
*   **Rationale:** A fresh reader cannot resolve any of the three pointers.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the fix defines SkillSpector in D5 and adds the two missing paths.
*   ***Proposed Edit:***
    *   Location: D5 (L168–176); §13 (L396–397); §10.3.3 (L323).
    *   Change: In D5, prepend: "SkillSpector is the NVIDIA skill scanner (`~/workspace/skillspector/`, wrapper `scan-gate.sh`); the gate blocks on score > 50 or any HIGH/CRITICAL finding and fails closed on scan errors." In §13, replace "(NeuroStrata is covered separately)." with "(NeuroStrata is covered separately in `~/workspace/plans/2026-11-06-egm-adoption-neurostrata.md`)." In §10.3.3, replace "this document's pilot supplied the companion doc, README, and repo clone" with "this document's pilot supplied the companion doc (`~/workspace/plans/2026-11-06-egm-adoption-neurostrata.md`), README (`~/workspace/autonomous-engineering-platform/skills/README.md`), and repo clone (`~/workspace/autonomous-engineering-platform`)".

### [Issue 83] [zoom_out-3-M1] - Severity: Major
*   **Affected Scope:** §3 (L35–38)
*   **Discrepancy Description:** Root-problem scale is unestablished; adoption is precautionary. The doc admits "no drift incident or review-load count is recorded," and that the 65-finding pilot "is evidence the instrument works, not evidence of the problem's scale." The demand baseline is deferred to the Phase 0 pilot log and the value judgment to §14 decision 5 — i.e. the full local install is built before the problem's size is measured.
*   **Rationale:** A 90-file vendor + 7 skills + 2 CI gates adopted against an unmeasured problem; the staging mitigates but does not cure it, since Phase 0 still installs the bundle before the ruling.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid — same gap as Issue 3 (outcome metric + precautionary-experiment framing + kill criterion).
*   ***Proposed Edit:***
    *   Location: §2; §3 (Issue 3's edit).
    *   Change: Apply Issue 3's edit (finding action rate, categorized-findings taxonomy, precautionary-experiment framing with the §11 rollback as kill criterion).

### [Issue 84] [zoom_out-3-M2] - Severity: Major
*   **Affected Scope:** §5 (L49–50) and §6 (L64–73)
*   **Discrepancy Description:** "Extend the incumbents" rejected in one sentence, without sizing. `roundtable_review` already does fresh-context parallel reviewers, debate rounds, a judge, claim-verification subagents, and filed reports; `planning-wringer` is an adversarial plan review, and `requesting-review` already dispatches a fresh subagent. The doc's own delta table concedes both have fresh-context reviewers and claim verification; the genuinely new delta is the five written standards, the two gates, and the drift/bootstrap skills.
*   **Rationale:** No evidence that grafting written standards + filed reports onto `roundtable_review` was costed against vendoring 2,810 lines.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid — same gap as Issue 4 (costed do-nothing rejection).
*   ***Proposed Edit:***
    *   Location: §5 (Issue 4's edit).
    *   Change: Apply Issue 4's edit (do-nothing rejection with the grafting-vs-vendoring cost comparison).

### [Issue 85] [zoom_out-3-M3] - Severity: Major
*   **Affected Scope:** §1 (L15–24); §9 (L209–282); §14 decision 3
*   **Discrepancy Description:** Speculative second deployment target. The doc designs two environments, two install mechanisms, and native installs for seven harnesses (including Cursor, "experimental, unverified upstream," and OpenCode, "adapter unverified upstream"), yet only the Muse environment is actually used — and §9 is headed "Provisional — validation pending owner provisioning," with decision 3 contemplating marking Phase 3 "documented-but-unexecuted" and moving §9 to an appendix. ~74 lines design a section that may be discarded.
*   **Rationale:** YAGNI — design the one environment in use; add Environment A when a fresh VM is actually provisioned.
*   ***AI Suggestion:*** SETTLED
*   ***Justification:*** Settled — same scope and issue as round-1 `zoom_out-1-1` (ESCALATE — Environment A scope; the premise was wrong — the owner explicitly requested dual-environment coverage in the requesting conversation — and the scope decision needs the owner's ruling). Also round-2 `zoom_out-2-4`. Per the loop's settled rule, a settled finding is not re-opened. No fix proposed; recorded here only. The live ESCALATE remains open, awaiting the owner's ruling.
*   ***Proposed Edit:***
    *   Location: None.
    *   Change: None. Matches round-1 disposition: ESCALATE (zoom_out-1-1).

### [Issue 86] [zoom_out-3-M4] - Severity: Major
*   **Affected Scope:** D2 (L117–125); §5 (L62–63); §11.1 (L365–367)
*   **Discrepancy Description:** Full 90-file / 2,810-line vendor for a 2-skill pilot. Verified in `~/workspace/egm/`: the bundle includes 18 `docs/designs/*` upstream design notes, per-skill `TEST.md`, `test_scenarios.yaml`, `agents/openai.yaml`, `assets/icon.svg`, and harness docs for Claude/Codex/Copilot/Cursor/OpenCode. The minimal-subset rejection justifies personas + standards (runtime-resolved), not docs/designs, test fixtures, or icons.
*   **Rationale:** Vendoring non-runtime files inflates the vendor-integrity surface (every file hashed and checked) for content the pilot never executes.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix adds the runtime-dependency analysis to the §5 minimal-subset bullet: `docs/` is runtime-referenced, the rest rides under the D2 unit rule with the reason stated.
*   ***Proposed Edit:***
    *   Location: §5 minimal-subset bullet (L62–63).
    *   Change: Replace "- Minimal-subset vendoring (only the 2 pilot skills' dependencies) — rejected: D2 requires the bundle to move as one unit because skills resolve `agents/` and `resources/` at run time; a subset that omits personas or standards breaks the skills by construction, so the full 90-file bundle is vendored while only 2 skills are adapted in the pilot." with "- Minimal-subset vendoring (only the 2 pilot skills' dependencies) — rejected: D2 requires the bundle to move as one unit because skills resolve `agents/` and `resources/` at run time, and `docs/` is runtime-referenced too (the Muse routing line targets `docs/muse.md`; D3 rewrites `docs/codex.md`, `docs/claude.md`, `docs/harnesses.md`); a subset that omits personas, standards, or `docs/` breaks the skills by construction. The remaining non-runtime files (`TEST.md`, `test_scenarios.yaml`, `assets/icon.svg`, `docs/designs/`, `agents/openai.yaml`) ride along under the D2 unit rule: maintaining a subset file list is its own drift risk (every upstream addition would need a keep/drop decision), and the vendor-integrity hash covers them at no extra mechanism cost. So the full 90-file bundle is vendored while only 2 skills are adapted in the pilot."

### [Issue 87] [zoom_out-3-M5] - Severity: Major
*   **Affected Scope:** D4 (L136–167); §10.2 (L294–308)
*   **Discrepancy Description:** New wrapper→bundle coupling + dual canonical direction. The doc admits this is "a new pattern in this repo — no existing skill references a `reference/<tree>/` path" and that renaming either tree "silently breaks all 7 skills" (§6). On top of that, §10.2 splits canonicity and adds a normalize-then-diff sync check (§10.5 step 4) to keep the two trees aligned.
*   **Rationale:** Two trees, two gates, and sync machinery to reconcile them, where a single-tree or local-only layout would have no cross-tree drift to manage; an architectural dead-end risk accepted without a simpler-layout comparison.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid in part: the simpler layouts (adapted skills inside the bundle tree; local-only) are evaluated in §5, but D4 does not point at that evaluation, and the dual-canonicity half is fixed by Issue 66. The fix adds the explicit pointer in D4.
*   ***Proposed Edit:***
    *   Location: D4 (L160–165); §10.2 (Issue 66's edit).
    *   Change: In D4, replace "This wrapper→bundle coupling is a new pattern in this repo — no existing skill references a `reference/<tree>/` path. It is accepted explicitly here because the alternative (duplicating personas and standards per skill, or non-skill directories under `skills/`) is worse (see §5 Alternatives Considered)." with "This wrapper→bundle coupling is a new pattern in this repo — no existing skill references a `reference/<tree>/` path. It is accepted explicitly here because the alternatives are worse (see §5: adapted skills inside the bundle tree break the pristine/verbatim rule; shared `skills/egm-agents/` + `skills/egm-resources/` dirs pollute the catalog; local-only adoption is adopted in part for Phases 0–1). The two-tree drift the coupling creates is managed by the §10.2 canonical direction (per artifact) and the §10.5 step 4 sync check." Apply Issue 66's §10.2 rewrite for the canonical-direction half.

### [Issue 88] [zoom_out-3-M6] - Severity: Major
*   **Affected Scope:** D6 (L177–183); §12 (L384–386)
*   **Discrepancy Description:** Elaborate workaround for a missing harness control, admitted detection-only. Snapshot-by-content-hash before dispatch, diff after each reviewer, fail the round, discard findings, `git checkout` restore or re-vendor, round-level (not reviewer-level) attribution — plus the admission that memory/DB paths are not snapshotted, "silent memory use is undetectable," and "detection does not prevent the write."
*   **Rationale:** A per-run procedural apparatus is built around the absence of tool projections instead of bounding the blast radius structurally (e.g. reviewing only in a scratch copy), and the residual risk stands after all the machinery.
*   ***AI Suggestion:*** CONTEST
*   ***Justification:*** The critique proposes a different design (scratch-copy review), not a defect in the document's accuracy — and the document already states exactly what the finding faults it for: D6 and §12 record the control as detection-only and the residual risk explicitly ("detection does not prevent the write", "silent memory use is undetectable", "the residual write-before-detection risk stands"). The checkable evidence the reviewer could read: upstream `docs/muse.md` states agent tool projections are unsupported on Muse — there is no harness control to use instead of the procedural mitigation, so no structural fix exists within this environment; and a scratch copy would not bound the memory/DB blast radius either (the residual the finding cites would stand unchanged). The D6 snapshot procedure itself is fixed by Issue 2 (round-level window, widened scope) — this contest is about the finding's design prescription, not the procedure's executability. A scratch-copy review is a design alternative for the owner, not a textual defect; recorded here, not implemented.
*   ***Proposed Edit:***
    *   Location: None — no edit proposed.
    *   Change: None.

### [Issue 89] [zoom_out-3-M7] - Severity: Major
*   **Affected Scope:** D3, D4, §9.2–§9.3, §10.5–§10.6
*   **Discrepancy Description:** Altitude drops (weeds). D3 lines 126–135 (per-row `sed` mapping table, per-skill occurrence counts); D4 lines 136–167 (literal CI `run:` block, literal `sha256sum` command, PROVENANCE field order); §10.5 lines 336–342 (literal `diff -rq` commands, full `git clone/fetch/checkout/rev-parse` with 40-char hash); §10.6 lines 343–347 (literal `grep -oE` loop). A 415-line design doc spends a large share on shell/CI literals that belong in a runbook or the PR itself.
*   **Rationale:** High-level sections should carry architecture, interfaces, and data flow, not implementation commands.
*   ***AI Suggestion:*** SETTLED
*   ***Justification:*** Settled — same scope and issue as round-1 `zoom_out-1-8` (CONTEST — commands stay in the strategy doc; the document's stated purpose is executable design, and the same round's implementation-readiness standard demands more exact commands, not fewer). Also round-2 `zoom_out-2-10`. Per the loop's settled rule, a settled finding is not re-opened. No fix proposed; recorded here only.
*   ***Proposed Edit:***
    *   Location: None.
    *   Change: None. Matches round-1 disposition: CONTEST (zoom_out-1-8).

### [Issue 90] [zoom_out-3-M8] - Severity: Major
*   **Affected Scope:** §7 skill table (L84–93); §11 (L361–367)
*   **Discrepancy Description:** Five of seven skills duplicate or anticipate, only two are piloted. `egm-brainstorm` duplicates the existing `brainstorming` skill (verified in the catalog; its description mandates use "before any creative work"), and `egm-draft` overlaps `writing-plans` (verified: spec → bite-sized implementation tasks). All five non-pilot skills are deferred to Phase 1 on the pilot-value ruling, yet Phase 2 still installs all 7 wrappers (14 files, §11.1).
*   **Rationale:** Adopt the two review skills the pilot tests; vendor/wrap the other five only after the ruling that justifies them.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix evaluates the overlap in §5 (the two skills add the multi-reviewer panel + written standards; they are adopted only on the ruling) and relies on E-A's 2-skill variant so Phase 2 does not install all 7 wrappers without the ruling.
*   ***Proposed Edit:***
    *   Location: §5 (after the Subset bullet); §11.1 (shared edit E-A).
    *   Change: Append a bullet to §5: "- Overlap with `brainstorming` / `writing-plans` — `egm-brainstorm` overlaps `brainstorming` (both pre-creative-work) and `egm-draft` overlaps `writing-plans` (both produce implementation tasks). The EGM versions add the multi-reviewer panel and the written standards; they are adopted only on the §14 decision 5 pilot-value ruling (Phase 1), not in the pilot — and Phase 2 installs only the 2 review skills without that ruling (see §11.1 two-skill variant)." Apply E-A.

### [Issue 91] [zoom_out-3-M9] - Severity: Major
*   **Affected Scope:** §6 (L70–72); §10.4 (L332–334)
*   **Discrepancy Description:** 25-spawn loop adopted without a cost baseline. Up to 5 rounds × 5 reviewers = 25 spawns per run, 30-minute per-reviewer timeout "set now" because "no pilot log with per-reviewer elapsed times exists yet," token budget deferred to §14 decision 6 — against §3's admission that no review-load count exists. The incumbent panel uses four reviewers; nothing establishes that five reviewers × five rounds is the right scale.
*   **Rationale:** The most expensive new recurring cost in the design is fixed before any measurement, with the budget decision postponed.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid — same gap as Issues 5 and 45 (interim budget in reviewer-hours + per-reviewer token recording + Phase 1 carry-forward default).
*   ***Proposed Edit:***
    *   Location: §10.4; §6 (Issues 5 and 45's edits).
    *   Change: Apply Issues 5 and 45's edits (interim pilot budget: 12.5 reviewer-hours per run; per-reviewer tokens recorded in the pilot log; Phase 1 interim default carries the pilot values forward).

### [Issue 92] [zoom_out-3-N1] - Severity: Nit
*   **Affected Scope:** §4 (L39–44); §8.1 (L196–198)
*   **Discrepancy Description:** The architecture section is a pointer, not a map. §4 says "the existing §§8–10 keep their detail; this section is the map, with pointers to them," and §8.1 states it "states no additional requirements."
*   **Rationale:** The one section meant to give the high-altitude view defers to the detail sections.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid — same gap as Issue 19 (§4 expansion) and Issue 26 (§8.1 deletion).
*   ***Proposed Edit:***
    *   Location: §4 (Issue 19's edit); §8.1 (shared edit E-C).
    *   Change: Apply Issue 19's edit and E-C.

### [Issue 93] [zoom_out-3-N2] - Severity: Nit
*   **Affected Scope:** §2 (L26–33)
*   **Discrepancy Description:** Adoption goal measures usage, not outcome. "At least one design document reviewed via `egm-review-loop` within 30 days" counts that the instrument ran, not that it found drift or defects the incumbents missed — the very marginal-value question §14 decision 5 is meant to answer.
*   **Rationale:** A goal stated as usage lets the adoption succeed even if the pilot-value ruling is negative in substance.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid — same gap as Issue 3 (finding action rate outcome metric).
*   ***Proposed Edit:***
    *   Location: §2 (Issue 3's edit).
    *   Change: Apply Issue 3's edit.

---

Counts check: 93 findings = 87 PROPOSE FIX + 1 CONTEST + 0 new ESCALATE + 1 DECLINE + 4 SETTLED. The one live ESCALATE remains the settled round-1 item `zoom_out-1-1` (Environment A scope), carried by settled Issue 85 and still awaiting the owner's ruling.
