# EGM Adoption (AEP) — Goldfish Review, Round 5

- **Target:** `/home/hatch/workspace/plans/2026-11-06-egm-adoption-aep.md` (457 lines, read in full by all reviewers)
- **Round:** 5 of 5 (cap). Rounds 1–4 all NOT CLEAN (0 clean rounds so far).
- **Reviewers:** 5 fresh-context Goldfish, direct dispatch — design_critic (feature-spec), structural (feature-spec), implementation_readiness (implementation-readiness), comprehension (feature-spec), zoom_out (zoom-out).
- **GoldfishContext:** companion NeuroStrata doc + AEP `skills/README.md` + AEP repo clone (read-only).
- **Counts:** **4 Blockers, 40 Majors, 28 Nits = 72 findings.**
- **Settled (not re-opened, per the loop's settled rule):** 0 — no reviewer re-raised a settled item.
- **Verdict:** NOT CLEAN. No clean round yet (0 of 2 needed for convergence).
- **Provenance:** This file was reconstructed from the round-5 resolve report (`2026-11-06-egm-adoption-aep-goldfish-resolve-r5.md`) because the original consolidated review file was never written to disk. The resolve report is the primary record; this file reproduces its finding substance grouped by reviewer, with no resolver commentary included.

## design_critic — 2 Blockers, 14 Majors, 9 Nits (25)

### [Issue 1] [design_critic-5-1] — Blocker — §10.5 step 4 (L374), §10.6 C2 (L381)
C2 grep pattern has doubled backslashes (`'\\.\\./\\.\\./reference/...'`) so in ERE it requires literal backslashes and can never match `../../reference/...`; verified by running the literal loop against the real wrappers: zero output, vacuous pass. With corrected single-backslash pattern it flags two MISSING lines: `../../reference/elephant-goldfish-model/agents/` and `.../resources/document_standards/` — both existing directories; C2 uses `test -f` which fails on directories, while C1 uses `test -e`.

C2 is the check that wrapper references resolve; as printed it can never fail, so a dangling wrapper reference passes silently — and the two directory references it should catch are exactly the ones `test -f` mishandles.

### [Issue 2] [design_critic-5-2] — Blocker — §10.2 (L336) vs D4 (L183–191), §11.3 (L422)
§10.2 claims C2's resolve loop "runs as a step in the vendor-integrity CI job on every PR" and repo-side drift window is "zero"; D4's literal tenth vendor-integrity block has only sha256sum -c, comm unlisted-files check, symlink check — no C2 step; §11.3's ci.yml change adds only that block; live ci.yml egm block corroborates (exactly those three commands).

The "zero drift on the repo side" claim rests on a CI step that is not in the specified CI change, so the claim is unfounded as specified.

### [Issue 5] [design_critic-5-3] — Major — §5 (L76) vs §11 (L408)
L76 still reads "Waiting for upstream issue #252 to close instead of the D3 routing line" — bare, no link — while L408 asserts "No bare 'Issue N' references remain in this document". Round-4 E-U fix linked the other instances but missed this one (grep confirms L76 is the only remaining bare instance). This is the flagged round-4 wart #2.

The doc asserts a citation rule it violates on one line; the rule's own assertion is false until L76 is linked.

### [Issue 6] [design_critic-5-4] — Major — §10.5 step 4 (L374)
Sync-check diff loop cannot execute from either plausible working directory. From repo root, `egm-*/` matches nothing (skill dirs live under skills/), glob stays literal, diff errors. Preceding command did `cd ~/workspace/custom-skills`, where `skills/$s` does not exist, diff errors there too. No cd to repo root given.

Same defect as Issue 4, stated from the design-critic angle; the loop as printed has no working directory from which it runs.

### [Issue 7] [design_critic-5-5] — Major — §14 decision 2 (L447), §10.5 step 3 (L373)
Pilot target's "commit" refers to a repository that does not exist — `~/workspace/plans/` is not a git repo (`git -C plans rev-parse` fails, no .git in plans or ~/workspace). No commit SHA or HEAD to record, so step 3 cannot be satisfied and the pilot target is not version-identified.

A verification step that requires a commit SHA from a non-repository cannot be satisfied as written.

### [Issue 8] [design_critic-5-6] — Major — §8 D3 (L171)
The seven "Literal commands" contain unbound `<bundle>` placeholder; run literally, first command writes literal `<bundle>/agents/` into the adapted file. Undetectable by C1: C1 greps for substring `agents/...` (matches inside literal `<bundle>/agents/...`) then tests the real bundle path, which exists, so C1 passes on a corrupted file.

A literal command that corrupts the file it adapts, with the corruption invisible to the doc's own verification check.

### [Issue 9] [design_critic-5-7] — Major — §6 (L93), §10.4 (L367), §14 decision 6 (L451)
Phase 0 pilot still runs with no token ceiling; E-H gates only Phase 1. Grep for "token" finds no numeric cap anywhere; only cost numbers are 25 spawns and 12.5 reviewer-hours. The pilot generates the cost evidence for the decision-5 value ruling while its own cost is uncapped. Flagged explicitly as r4 Issue 55's surviving core (fix-verification failure), not a silent re-raise.

The experiment that generates the cost evidence runs uncapped — the cap is derived from the very spend it is supposed to bound.

### [Issue 10] [design_critic-5-8] — Major — §10.4 (L367)
Per-reviewer token cap as "size bound" has no defined overflow behavior — if a target document alone exceeds the cap, doc defines no behavior (refuse, truncate, split, breach?).

A bound with no defined behaviour at its boundary is not a bound; the first oversized target forces an ad-hoc decision.

### [Issue 11] [design_critic-5-9] — Major — §9.5 step 3 (L308), §9.1 (L240), §9.4
E2E gate's run command exists for only one of three VM shapes. Step 3 prescribes `muse exec --prompt /tmp/egm-e2e-<shape>/prompt.md` for shapes muse-cli, other-harness, headless; `muse exec` exists only for muse-cli; other-harness has no muse exec, headless has no harness CLI at all (yet §9.1 prerequisites demand "one supported harness CLI", which headless cannot satisfy). "Installed cache only" = "plugin installed per §9.2", undefined for headless Path 2. Step-1 fallback (hand-exercised fixture run if muse exec absent) does not save headless (no harness to hand-exercise).

A gate whose run command exists for one of three shapes cannot gate the other two; the headless shape has no verification gate at all as written.

### [Issue 12] [design_critic-5-10] — Major — §9.5 step 2 (L307), §10.6 C3 (L382–385), §9.1 (L240)
Venv installed but never invoked by any command that needs it. §9.1 installs pytest==9.2.0 and PyYAML==6.0.3 only into /tmp/egm-venv, no activation step anywhere. §9.5 step 2 runs bare `pytest tests/unit` (not on PATH on fresh VM); C3 literal loop runs bare `python3 -c "import yaml..."` (system python has no yaml) though prose above names /tmp/egm-venv/bin/python3. Both fail on first attempt on fresh VM.

The only pytest and the only PyYAML on the fresh VM live in the venv, and no normative command uses the venv — both commands fail on first attempt.

### [Issue 13] [design_critic-5-11] — Major — §10.3.4 (L363), §4 (L56), §10.5 step 3 (L373)
Mid-round resume unimplementable — no per-reviewer report artifact exists. No path/filename/location specified for an individual reviewer's report ("each reviewer files a report", L56; "file one report", L363). Resume rule (re-read filed reports, re-dispatch only reviewers with no filed report) cannot work: if Elephant dies before consolidation, no review report exists and nothing on disk identifies which reviewers filed. Same gap breaks §10.5 step 3 severity-change audit ("verifies each recorded severity change against the filed report").

The resume rule and the severity-change audit both presuppose per-reviewer artifacts the doc never defines.

### [Issue 14] [design_critic-5-12] — Major — §12 (L435)
URL-fetch audit cannot perform two of its three checks. Requires "every saved file ≤1 MB, every cited URL uses https, every saved file is HTML". (a) No artifact maps saved files to source URLs, and brief template (L363) does not require reviewers to record source URL per saved file, so https check is unperformable for saved files whose URL is not cited in the report. (b) "is HTML" has no defined test (extension? `file` output? Content-Type?).

An enforcement audit that cannot perform two of its three checks is not enforcement.

### [Issue 15] [design_critic-5-13] — Major — §8 D5 (L213)
Content review enumerates 23 non-markdown files; bundle has 25. Listed: 7 openai.yaml + 7 test_scenarios.yaml + 1 worker-return.schema.json + 7 icon.svg + 1 readme-header.svg = 23; omitted: LICENSE and plugin.json. plugin.json is the harness-read plugin manifest — highest-trust file, declaring what the harness loads.

The safety control's enumeration omits the highest-trust file in the bundle; an unreviewed manifest is unreviewed by construction.

### [Issue 16] [design_critic-5-14] — Major — §10.4 (L367)
Churn stop reuses a cap-specific literal question asserting a false precondition. "on cap or churn the driver stops and asks the owner one question, literally: 'The loop hit its cap (5 rounds) with unsettled findings — how do you want to proceed?'" — churn fires on "the first occurrence", which can be round 2; options ("continue past the cap") presuppose the cap.

A driver stopping on churn at round 2 would ask a question falsely asserting the 5-round cap was hit, and offer "continue past the cap" when there is no cap to continue past.

### [Issue 17] [design_critic-5-15] — Major — §8 D6 (L220)
Disposable target copy has no executable procedure. E-G fix: "Before dispatch, copy the target document to a disposable per-round copy (/tmp/egm-review-<run>/target.md, byte-identical...) and brief reviewers with the copy's path" — no literal cp command, no mkdir -p for the per-round directory (does not exist). Under the same literal-executability bar round 4 applied to the sync check, the central containment control is prose, not a procedure.

The doc's central containment control cannot be executed as written — the directory it copies into does not exist.

### [Issue 18] [design_critic-5-16] — Major — §3 (L42)
Demand baseline has no measurement method, window, or corpus. "the Phase 0 pilot log records design docs produced per month as the demand baseline for the Phase 1 value judgment (§14 decision 5)". No method: which corpus (22 top-level docs/? 37 recursive? dated plans under ~/workspace/plans/ too?), what window, counted how (file dates? git log? — and per 5-5, ~/workspace/plans/ is not versioned, so git-based counting cannot cover it).

The demand baseline is the evidence for the Phase 1 value judgment; without a method it cannot be produced or audited.

### [Issue 45] [design_critic-5-17] — Nit — §10.6 C1 (L380)
Routing-line and upstream-relative assertions reference `$f` outside any loop. `$f` is the loop variable of the preceding for loop, which has closed; standalone assertions have no binding for `$f`.

Assertions that reference a closed loop's variable have no binding; run as written they test the wrong file or fail.

### [Issue 46] [design_critic-5-18] — Nit — §8 D6 (L220)
Three snapshot imprecisions. (a) "one file per location, <n> = 1–4" but location (3) is "each ~/workspace/custom-skills/egm-*/ dir" (seven dirs sharing one slot); single-<dir> command form does not say one globbed find or seven files. (b) "The after-diff ignores files under ~/workspace/plans/ that did not exist at snapshot time" — no filter command given; plain diff will list the round's own report file. (c) Rollback "remove newly created untracked files (rm -- <paths>)" fails on newly created directories (rm without -r).

Three small imprecisions in the core safety control, each of which makes the stated procedure unexecutable or wrong as written.

### [Issue 47] [design_critic-5-19] — Nit — §11 rollout table (L401)
Phase 1 Scope and Gate name different drift targets. Scope: "egm-drift-report run once against a live design doc"; Gate: target is "skills/README.md attribution table vs. skills/ tree" — not a design doc — and clean bill requires "the target's design-doc coverage stated", incoherent for an attribution-table target.

Scope and Gate of the same phase name different targets, and the clean-bill criterion does not apply to the Gate's named target.

### [Issue 48] [design_critic-5-20] — Nit — §11.3 (L422–424) vs §10.3.3 (L359)
egm-bootstrap's named target has no scheduled run in any phase. "Both skills are deferred to Phase 1 with these named targets" — but Phase 1 runs only egm-drift-report; no phase schedules the egm-bootstrap run against reference/ tree documentation.

A named target with no scheduled run is a deferred skill that never runs.

### [Issue 49] [design_critic-5-21] — Nit — §11.3 (L422–424)
"exact path list (allowlist)" is counts, not paths. "The pre-execution statement of its contents is the 90-path inventory above (38 + 10 + 7 + 33 + LICENSE + plugin.json)". Inventory gives counts, not paths: 13 top-level docs/ files and 18 docs/designs/ files never named, so generated .sha256 cannot be checked against the plan before execution — the gap r4 Issue 33(c) raised, now relabeled rather than closed.

A path list that lists counts, not paths, cannot be checked against the generated hash it claims to state.

### [Issue 50] [design_critic-5-22] — Nit — §14 decision 3 (L448)
Appendix move creates inconsistent appendix naming. "§9 is moved to an appendix (new heading ## Appendix A — Environment A...)" while existing appendix remains unlettered "## Appendix — Sources". After move: "Appendix A" plus unlettered "Appendix"; renaming of §9.1–§9.5 cross-references unspecified.

A move that leaves two appendices with inconsistent naming and unspecified subsection mapping creates the confusion it was meant to resolve.

### [Issue 51] [design_critic-5-23] — Nit — §9.3 step 1 (L290), §10.5 step 2 (L372)
Clone steps not re-runnable. Both clone into a fixed path (<install-root>/egm-checkout, /tmp/egm-upstream) with no rm -rf first; re-running fails because destination exists — same failure mode D6's rollback guards with rm -rf first.

A verification procedure that fails on its second run is not re-runnable.

### [Issue 52] [design_critic-5-24] — Nit — §9.4 note (L301)
Cursor/OpenCode-only VM route points at a Muse-only path. "a VM with only Cursor or OpenCode installed follows the headless row (Path 2, Muse only) or does not adopt". Path 2 is Muse-only, so a VM with only Cursor/OpenCode cannot follow the headless row — first alternative inapplicable without Muse.

Same defect as Issue 63: the first alternative of the note is inapplicable to the VM it describes.

### [Issue 53] [design_critic-5-25] — Nit — §8 D1 (L138)
90-day staleness rule has no computation and fires only at sync time. "if upstream HEAD is more than 90 days newer than the pin, the sync record notes the pin as stale" — no computation stated (which dates, which command), and check fires only "on every sync", so a pin can go stale silently as long as no sync happens.

A rule with no computation and a sync-only trigger cannot be applied and silently misses the case it exists for.

## structural — 0 Blockers, 2 Majors, 4 Nits (6)

### [Issue 19] [structural-5-1] — Major — §10.3 Roles table, L342–347
Normative procedure embedded inside table cells. Elephant row (L344, 670 chars) contains role definition plus two distinct normative rules (consolidation procedure; severity rule: Elephant must not change a finding's severity without recording change in report, downgrade with no recorded reason is a defect). Synthesizer row (L347, 425 chars) embeds design-choice aside (direct dispatch by design, depth-2 spawning works). Contrast Goldfish row (198 chars) and Driver row (255 chars), single-sentence role definitions. Consolidation procedure also stated in body text at §10.3.4 (L363) — rule now lives in two places. New instance in a different table from r4 Issue 18 (D3 mapping table, fixed); not a re-raise.

Normative rules in table cells duplicate body text and break the table's role-definition function; the severity rule now lives in two places and can drift.

### [Issue 20] [structural-5-2] — Major — §5, L84
"Delta table" is prose, not a table, yet cited as a table from two places. L84 is one 854-char paragraph with six pairwise comparisons (roundtable_review vs EGM). Doc has six real Markdown tables elsewhere (§4 L48–54, §7 L110–118, D3 L159–167, §9.4 L294–299, §10.3 L342–347, §11 L398–403). Two cross-references point at it as a table: L67 ("the delta table (§5, roundtable_review vs EGM) shows...") and §10.3.3 L359 ("See the roundtable_review vs EGM delta table in §5.").

A thing cited as a table from two places should be a table; as prose it cannot be scanned as the comparison it is cited for.

### [Issue 54] [structural-5-3] — Nit — §8 D4 L179–194; §10.6 L382–389
Unindented fenced code blocks inside list items split the lists: D4 "- **Bundle:**" bullet (L179, continuations indented 2 spaces) contains a fence at column 0 (L185, L191); paragraph "Write reference/elephant-goldfish-model/PROVENANCE.md…" (L193, indent 0) sits outside the bullet; "- **Wrappers:**" (L194) starts a second list. §10.6 item "3. **C3 — skill.yaml parses:**" (L382) contains fence at column 0 (L384, L386); "Expected: exit 0, no MISMATCH lines)." (L388, indent 0) floats outside item 3; items 4–7 resume as a second list. Other fenced blocks (§9.2 L247–251, §10.2 L324–332) sit at top level and do not split anything.

List items split by unindented fences render as separate lists with floating paragraphs — the document's structure is not what its numbering claims.

### [Issue 55] [structural-5-4] — Nit — §9.2, L264
Lone H4 single-child subsection with a 107-char heading. "#### Native installs for the other harnesses (commands from the bundle's `docs/harnesses.md` install table)" is the only H4 under §9.2 and one of only five H4s (other four are §10.3.1–10.3.4 sibling set). Muse install content in same §9.2 (L245–262) has no parallel subheading; heading carries a source parenthetical that belongs in body text.

A lone single-child subsection with a source parenthetical in its heading breaks the document's heading discipline.

### [Issue 56] [structural-5-5] — Nit — §9.3 (L290), §10.2 (L336)
Multi-step procedures formatted inconsistently: inline-numbered single paragraphs vs ordered lists. §9.3 (L290, 1,051 chars) packs six install steps into one paragraph; §10.2 (L336, 2,751 chars) packs five sync steps the same way. Parallel procedures in the same document are proper ordered lists: §9.5 steps 1–4 (L305–309), §10.5 steps 1–4 (L371–374), §10.6 checks C1–C7 (L380–392), §14 decisions 1–6 (L446–451).

Parallel procedures in the same document should share a format; inline-numbered paragraphs hide step boundaries.

### [Issue 57] [structural-5-6] — Nit — Whole document (line wrap)
Line-wrap inconsistency: 78 lines over 300 chars against a predominantly ~80-column wrap. Worst cases, all single-line normative paragraphs: L220 (4,828 chars, D6 read-only caveat), L363 (3,499 chars, §10.3.4 brief contents), L336 (2,751 chars, §10.2 sync steps), L308 (2,345 chars, §9.5 step 3), L213 (2,026 chars, D6 snapshot/rollback). Several are round-4 fix insertions applied as single lines (E-C, E-D, E-M). Recommendation: re-wrap the five lines above (and the other >1,000-char lines: L153, L171, L193, L305, L372, L374, L380, L422) to the document's prevailing ~80-column wrap. No wording change.

Long single-line paragraphs are hard to read in source and inconsistent with the document's prevailing wrap.

## implementation_readiness — 2 Blockers, 7 Majors, 2 Nits (11)

### [Issue 3] [implementation_readiness-5-1] — Blocker — §10.5 step 4 (L374), §10.6 C1 (L380), C2 (L381)
Literal commands carry stray backslash-escapes and cannot run as written; C2 is vacuously passing. File literally contains `\"$tmp\"`, `\"$f\"`, `\"<bundle>/$p\"`, `\"reference/...\"`, and C2 grep pattern `'\\.\\./\\.\\./reference/[A-Za-z0-9_./-]+'` (four double-backslash pairs). Empirical tests: `grep -q . \"$f\"` → `grep: "/etc/hostname": No such file or directory`, exit 2; `echo \"$tmp\"/` → `"hello"/` (literal quotes in path); double-backslash grep pattern on `../../reference/elephant-goldfish-model/agents/design_critic.md` → no match, exit 1; single-backslash form → matches. Consequences: step-4 cp targets a directory whose name contains literal quotes (fails); C1 loop's grep fails on all 7 files and `test -e \"<bundle>/$p\"` is false for every path, so every reference is falsely reported MISSING; C1 routing-line assertions additionally use `$f` outside any loop (unbound). C2's pattern matches nothing, so its while-read loop never executes and check always reports "no MISSING lines" — a false pass. The two defects mask each other. Not a re-raise of r4 Issues 22/23/27: the E-M/E-N logic fixes are present; the defect is new transcription-level breakage in the literal commands as printed.

A normative verification step whose literal commands cannot run as written, with a vacuously passing check masking real breakage.

### [Issue 4] [implementation_readiness-5-2] — Blocker — §10.5 step 4 (L374)
Sync-check diff loop is unexecutable from either working directory. "then compare per skill from the repo root (`for s in egm-*/; do diff -r \"$tmp/$s\" \"skills/$s\" || exit 1; done`)". Preceding command did `cd ~/workspace/custom-skills`, and no cd to repo root is ever given; repo root's local path is never named. From repo root, `egm-*/` matches nothing (dirs live under skills/egm-*/), glob stays literal, diff errors. From ~/workspace/custom-skills, `skills/$s` does not exist, diff errors. Further: `$tmp` was assigned in the cp command, lost if implementer runs step's commands as separate invocations (doc never says to run step 4 as one compound command); and the sed for the SKILL.md copies names no file operand.

The sync gate's literal procedure errors from every working directory the doc puts the implementer in.

### [Issue 21] [implementation_readiness-5-3] — Major — §10.2 (L336) vs D4 (L186–191) and §11.3 (L422)
C2 claimed to run in CI, but no CI step implements it. §10.2: "repo-side drift (wrappers vs bundle) is covered by check C2, whose resolve loop runs as a step in the vendor-integrity CI job on every PR" and "Maximum tolerable drift window: … zero on the repo side (C2 runs on every PR)." D4's literal tenth vendor-integrity run: block (L186–191) has only sha256sum -c, unlisted-files check, symlink check — no C2 loop. §11.3 (L422) defines ci.yml change as exactly that block.

Same root cause as Issue 2: the specified CI change contains no C2 step, so the "zero drift" claim is unfounded as specified.

### [Issue 22] [implementation_readiness-5-4] — Major — §6 (L93), §10.4 (L367), §14 decision 6 (L451)
Pilot itself has no token cap — the unclosed half of r4 Issue 55. R4 E-H fix gated Phase 1 on decision 6 ("Phase 1 does not start until decision 6 sets it"), but pilot (Phase 0) still has no token number anywhere: §6 gives only "interim budget 12.5 reviewer-hours per run; token budget set by §14 decision 6 from the pilot log's actuals", and decision 6 sets the budget "from the pilot log's elapsed-time and token records". The cap is therefore derived from the very spend it is supposed to bound — the experiment that generates the cost evidence runs uncapped. Explicitly flagged as the pilot half of r4 Issue 55, not a silent re-raise.

The round-4 fix closed the Phase 1 half and left the pilot half open; the pilot is the run currently spending.

### [Issue 23] [implementation_readiness-5-5] — Major — D6 (L220)
Snapshot after-diff exclusion rule has no procedure. "Re-run the same commands to -after files and diff each pair; any output names a modified path. The after-diff ignores files under ~/workspace/plans/ that did not exist at snapshot time (the round's own report and pilot-log entries); any modification or deletion of a pre-existing file under ~/workspace/plans/, or any change at the other three locations, fails the round." Plain diff of the two sha256sum lists reports added files as differences; no command or interpretation rule implements the exclusion (e.g. separating added lines from changed lines), the -after filenames are never specified, and scope location (3) ("each ~/workspace/custom-skills/egm-*/ dir" — seven dirs) is assigned a single <n> slot (1–4), leaving it ambiguous whether it is one snapshot file over the glob or seven. The pass/fail verdict of the plan's core safety control is left to the implementer to design.

The core safety control's verdict cannot be produced as written — the exclusion rule has no procedure and the location-(3) snapshot form is ambiguous.

### [Issue 24] [implementation_readiness-5-6] — Major — §10.4 (L367), §10.3.4 (L363)
30-minute per-reviewer timeout has no enforcement mechanism. §10.4 sets "Timeout: 30 minutes per reviewer for the pilot" and §10.3.4 says "a reviewer that times out, fails, or returns no report is retried once, then recorded not run". No timeout parameter, watchdog, timer, or kill step is named anywhere, and subagent.spawn's timeout behaviour (if any) is never documented. Nothing defines how a timeout is detected or who enforces the 30 minutes.

A bound with no enforcement mechanism and no detection rule cannot be enforced.

### [Issue 25] [implementation_readiness-5-7] — Major — §9.1 (L240), §11 Phase 3
Fresh-VM provisioning has no install procedure. §9.1 lists "git ≥ 2.43.0, python3 ≥ 3.12.3 …, and one supported harness CLI — Muse ≥ 1.4.14" as prerequisites. Only install command given is the venv/pip install for pytest/PyYAML; no install commands for git, python3, or any harness CLI, and no OS/distro or VM image is specified for the "general-purpose Linux VM". §11 Phase 3 provisioning says only "install prerequisites, clone upstream at the pinned SHA, install per the §9.2/§9.3 path" — "install prerequisites" is the entire provisioning instruction.

Phase 3 cannot be executed on a fresh VM as written — there is no image and no install procedure for the prerequisites themselves.

### [Issue 26] [implementation_readiness-5-8] — Major — §9.5 step 2 (L307)
`pytest tests/unit` is unbound in binary, location, and input. (a) Bare pytest is unbound — the only pytest installed per §9.1 is /tmp/egm-venv/bin/pytest; no activation or path given. (b) §9.2's clone (L248, `git clone https://github.com/google/elephant-goldfish-model.git`) has no destination and no working directory, so ./elephant-goldfish-model/ is location-unbound; §9.3 (L290) clones to a different path (<install-root>/egm-checkout), giving a Path 2 implementer two candidate checkouts. (c) `tests/unit` existence at the pinned SHA is never established — §7's inventory and §11.3's 90-file inventory contain no tests/ at all, and top-level tests/ is listed as not vendored.

A verification step unbound in binary, location, and input cannot run on first attempt.

### [Issue 27] [implementation_readiness-5-9] — Major — §10.6 C3 (L385), C6, §9.1 (L240)
Skill.yaml check's interpreter is unbound. C3 loop uses bare `python3 -c "import yaml,sys; ..."` (L385; byte-checked clean of escaping defects), while the only PyYAML on the fresh VM is installed into the venv — doc names /tmp/egm-venv/bin/python3 only in a parenthetical ("run with a python3 that has PyYAML installed; fresh VM: the §9.1 venv, /tmp/egm-venv/bin/python3") and the literal command does not use it. System python3 on a stock fresh VM has no yaml module, so the literal loop fails with ModuleNotFoundError. Environment B has no python3-with-PyYAML identified or installed at all. C6 inherits the procedure ("same as C3").

The literal C3 command fails on a fresh VM because its interpreter is the one Python that lacks the module it imports.

### [Issue 58] [implementation_readiness-5-10] — Nit — §10.3.2 (L352)
Readiness-gate file-existence verification has no command. "the target document exists, reviewers and standards resolve to existing files, and GoldfishContext is provided" — no existence-check command (e.g. `test -f` per path) is given for the Elephant to run before asking the gate question.

A gate whose precondition check has no command cannot be run by the Elephant as written.

### [Issue 59] [implementation_readiness-5-11] — Nit — §11 Phase 1 gate (L401)
Clean-bill criterion "coverage stated" is undefined. "produces a dated finding, or a clean bill with the target's design-doc coverage stated". What coverage, of what, in what form, is undefined — and the named target is the skills/README.md attribution table vs the skills/ tree, not a design doc, so "design-doc coverage" does not obviously apply.

Same defect as Issues 47 and 69: the clean-bill criterion is undefined for its named target.

## comprehension — 0 Blockers, 10 Majors, 11 Nits (21)

### [Issue 28] [comprehension-5-1] — Major — §8 D6, L220
"Verify outputs" is defined twice, contradictorily, in the same paragraph. Same paragraph (single line L220) contains both "'Verify outputs' means the snapshot diff plus the three checks in §10.3.1 (line-existence, standard-name, memory-prohibition), nothing else" and later "'Verify outputs' means these two checks, nothing else." Second definition's "these two checks" has no clear antecedent — immediately preceding sentence names only the line-existence check. New evidence from round-4 E-C fix, which rewrote the first definition but left the second; not a re-raise of r4 Issue 19/39 (old single definition).

The document's core verification term has two contradictory definitions 200 words apart in one paragraph.

### [Issue 29] [comprehension-5-2] — Major — §1, L20
Owner definition points at "§7's approval gates," but §7 defines no gates. L20: "'Owner' is the human user who owns the AEP repo and this environment — the same 'human' in §7's approval gates". §7 (L101–104) only mentions gates in passing ("the human (explicit approval gates before anything is built)") and defines none. Actual gates (readiness gate, section-approval gate) are defined in §10.3.2 (L352–356).

A definition that points at a section that does not define what it points to misdirects the reader.

### [Issue 30] [comprehension-5-3] — Major — §2, L30
"merged with conversation resolution" is undefined anywhere in the document. L30: "AEP PR — CI green including vendor-integrity + skills-freshness, merged with conversation resolution." Phrase appears nowhere else, never defined — not what a "conversation" is, not what counts as resolved, not who resolves it. Stated as a merge criterion.

A merge criterion the reader cannot interpret is not a criterion.

### [Issue 31] [comprehension-5-4] — Major — §8 D4, L195–197
"sync from live" and "the manifest" are used before either is defined. L197: "the gate proves the repo skills/ tree equals the manifest generated from the repo tree after the last sync from live". Term "live" is defined only later, in §10.2 (L336), and that definition is explicitly scoped — "('live' in this section means the local ~/workspace/custom-skills/ tree)" — so it does not cover this D4 use. "The manifest" is never defined at all; file .github/skills-manifest.sha256 is first named only in §11.3 (L422), with no explanation of what the manifest contains. Different occurrence from r4 Issue 42 (§10.2 use, now fixed), not a re-raise.

A first use that relies on a later, narrowly scoped definition and an undefined file name cannot be followed by a fresh reader.

### [Issue 32] [comprehension-5-5] — Major — §8 D6, L220, and §12, L438
"NeuroStrata MCP connector," "NeuroStrata store," and "AGENTS.md" are undefined in the target document. L220: "'Configured memory services' means the NeuroStrata MCP connector and any other configured memory; 'project instructions' means AGENTS.md and repo instruction files." L220 again: "no snapshot is taken of the NeuroStrata store". Target doc never defines NeuroStrata (only mention is §2, L38, pointing at companion doc), never expands/defines "MCP," never says what the connector is or where it lives, never explains what an AGENTS.md file is or whose it is. These terms carry the central safety prohibition.

The terms carrying the central safety prohibition are undefined in the document that states the prohibition — a human reader cannot assess what is prohibited.

### [Issue 33] [comprehension-5-6] — Major — §9.3, L288, vs §8 D3, L169
Three mutually inconsistent literal forms for the Environment B bundle path. L288: "Example path strings a Path 2 skill contains: $HOME/egm/agents/design_critic.md; in Environment B the same string reads /home/hatch/workspace/egm/agents/design_critic.md." But §9.3 also says <install-root> defaults to $HOME (example /home/<user>) while Environment B sets <install-root> = ~/workspace — so $HOME/egm/... and ~/workspace/egm/... are different directories unless $HOME is /home/hatch/workspace. And D3 (L169) states the opposite of the L288 example: "Environment B uses the ~ form ~/workspace/egm/... in adapted files … the expanded form /home/hatch/workspace/egm/... never appears in a pilot adapted file." A naive reader cannot determine the literal string an Environment B skill file contains: $HOME/egm/..., ~/workspace/egm/..., or /home/hatch/workspace/egm/... .

Three mutually inconsistent literal forms for the same string leave the implementer unable to determine what an adapted file contains.

### [Issue 34] [comprehension-5-7] — Major — §9.5 step 3, L308
"a line-count design" is undefined; the fixture's subject is never explained. L308: "fixture design muse-wonder-1.0 (the upstream fixture name for the brainstorm → draft → review sequence; a line-count design, per the upstream Muse row in TESTING.md)" and the specified prompt: "'Run the EGM brainstorm → draft → review sequence (fixture muse-wonder-1.0, a line-count design) … brainstorm the design, draft it, then run an uninterrupted review.'" Nothing says what a "line-count design" is — a design for a line-counting tool? a design document measured in lines? — or what artifact the brainstorm/draft stages are supposed to produce beyond the filenames.

The E2E gate's fixture subject is unexplained; the reader cannot tell what is being designed.

### [Issue 35] [comprehension-5-8] — Major — §10.2, L336
C2's resolve loop is claimed to run in CI, but no such CI step exists in the document. L336: "repo-side drift (wrappers vs bundle) is covered by check C2, whose resolve loop runs as a step in the vendor-integrity CI job on every PR". D4 gives the literal tenth vendor-integrity run: block (L183–190): sha256sum -c, unlisted-files check, broken-symlink check — no C2 resolve loop. No other section defines a CI step that runs C2; §10.5 step 4 defines C2's resolve loop only as a manual procedure.

Same root cause as Issues 2 and 21: the claim and the specified CI block disagree.

### [Issue 36] [comprehension-5-9] — Major — §10.4, L367
The literal cap/churn question asserts the cap was hit, but it is prescribed for churn too. L367: "on cap or churn the driver stops and asks the owner one question, literally: 'The loop hit its cap (5 rounds) with unsettled findings — how do you want to proceed?' (options: accept and proceed / continue past the cap / return to drafting)." Churn can trigger at any round (first occurrence), so a driver stopping on churn at round 2 would ask a question falsely asserting the 5-round cap was hit, and offer "continue past the cap" when there is no cap to continue past.

Same defect as Issue 16: one literal question text cannot serve two triggers with different preconditions.

### [Issue 37] [comprehension-5-10] — Major — §10.3.3, L359, and §2, L37
"Ralph" and "the standing loop rule" are undefined. L359: "The Ralph per-iteration verifier (~/workspace/ralph/ loop — an independent, non-blocking verification subagent at the end of every iteration, per the standing loop rule) checks implementation against acceptance criteria". The gloss explains what the verifier does, but never says what Ralph is (a loop system? a tool? a skill?), and "the standing loop rule" is cited as authority with no location — it appears nowhere in the document or in GoldfishContext (the README mentions only "the Ralph autonomous loop" in passing). Same undefined "Ralph verifier" is a non-goal boundary in §2 (L37).

An authority cited with no location and a system named but never defined cannot be checked by the reader.

### [Issue 60] [comprehension-5-11] — Nit — §8 D7, L224
The trusted_enabled gloss is tautological. "the named egm/egm-* definitions report trusted_enabled (the status the harness reports for the named definition)". Parenthetical restates that it is a reported status without saying what trusted_enabled signifies — so the sentence's own puzzle (reports enabled, yet spawning is rejected with agent_definition_unavailable) is left unexplained.

A gloss that restates the term without explaining it leaves the sentence's own puzzle unexplained.

### [Issue 61] [comprehension-5-12] — Nit — §9.1, L240
"PEP 668" is cited by number only. "a venv is used because PEP 668 externally-managed environments refuse bare pip install". Consequence explained, but "PEP 668" never expanded or identified as a Python packaging standard.

A standard cited by number only, with no expansion, cannot be understood by a reader who does not already know it.

### [Issue 62] [comprehension-5-13] — Nit — §9.2, L269
Antigravity "run /plugin" is unexplained. "**Antigravity App/IDEs:** run `/plugin`". No other line says what /plugin is — a slash command, a menu item, a keystroke — or what it does (opens the plugin installer?). Every other harness row gives an explicit command; this one gives an unexplained token.

One unexplained token where every parallel row gives an explicit command.

### [Issue 63] [comprehension-5-14] — Nit — §9.4, L301
Cursor/OpenCode row offers two outcomes with no selection rule. "a VM with only Cursor or OpenCode installed follows the headless row (Path 2, Muse only) or does not adopt." Two incompatible outcomes with no rule for which applies when — and the headless row is Path 2, "Muse only," so a VM with only Cursor installed arguably cannot follow it at all.

Same defect as Issue 52: two incompatible outcomes with no selection rule, one of them inapplicable.

### [Issue 64] [comprehension-5-15] — Nit — §10.5 step 2, L372
The 40-character SHA is never stated to be the same commit as the short pin. "`git rev-parse HEAD` must print exactly `e9e1f06aa4e26e95cd4ed37210a0632202c429e9`". The pin stated everywhere else (D1, §7, §11.3, §14 decision 1) is the 8-character e9e1f06a. Doc never says the 40-character string is the full expansion of the short pin.

A reader cannot tell whether the 40-character expected hash is the same commit as the 8-character pin stated everywhere else.

### [Issue 65] [comprehension-5-16] — Nit — §10.3.1, L351
"before synthesizing" collides with "no synthesizer in Environment B". "Wait for actual completion before synthesizing; propagate failures and timeouts." But §10.3 role table (L347) says the synthesizer "in Environment B … is replaced by direct dispatch … with the Elephant consolidating findings." Reader cannot tell whether "synthesizing" is a leftover reference to the unused synthesizer role or a synonym for the Elephant's consolidation.

A term that collides with a role the doc says is unused in this environment confuses the reader about who does the step.

### [Issue 66] [comprehension-5-17] — Nit — §14 decision 2, L447
Two senses of "target" in one sentence. "The AEP repo is context (GoldfishContext), not the target: the Phase 2 PR … is the target state the pilot's evidence supports, not the artifact under review." Sentence uses "target" to mean both "the artifact under review" (which the PR is not) and "target state" (which the PR is).

One word used in two senses in one sentence invites misreading of what the pilot's evidence supports.

### [Issue 67] [comprehension-5-18] — Nit — §5, L73 and L77
"D3 rewrites docs/codex.md" misstates what D3 rewrites. L73 and L77 both say "D3 rewrites docs/codex.md, docs/claude.md, docs/harnesses.md". D3 rewrites *references to* those files inside adapted SKILL.md files; the bundle files themselves are never edited ("The pristine bundle is never edited," D3). As written, a reader would conclude the bundle's docs files are modified, contradicting the pristine-bundle rule.

The wording contradicts the pristine-bundle rule it sits next to.

### [Issue 68] [comprehension-5-19] — Nit — §8 D6, L220
Snapshot file counting contradicts itself for location (3). "snapshot each scope location by content hash with the find form (… > /tmp/egm-snapshot-<run>-<n>.sha256, one file per location, <n> = 1–4 for the four locations in scope order …): (1) the target repo working tree, (2) ~/workspace/egm/, (3) each ~/workspace/custom-skills/egm-*/ dir, (4) ~/workspace/plans/." "One file per location" with <n> = 1–4 implies four files, but location (3) is "each … dir" — seven skill directories — which implies either one file covering all seven (unstated: the find form takes a single <dir>) or seven files (which breaks the 1–4 numbering).

Same defect as Issues 23 and 46: the location-(3) snapshot form is ambiguous between one file and seven.

### [Issue 69] [comprehension-5-20] — Nit — §11, L401
"design-doc coverage" is undefined for an attribution-table target. Phase 1 gate: "drift report names its target in advance (skills/README.md attribution table vs. skills/ tree) and produces a dated finding, or a clean bill with the target's design-doc coverage stated". Named target is an attribution table, not a design doc — "design-doc coverage" has no meaning for it, and the term is defined nowhere.

Same defect as Issues 47 and 59: a coverage criterion that does not apply to its named target.

### [Issue 70] [comprehension-5-21] — Nit — §14 decision 3, L449
The Appendix A rename rule does not say how subsection references map. "§9 is moved to an appendix (new heading ## Appendix A — Environment A (general-purpose Linux VM) …; all §9 cross-references become Appendix A cross-references)". Doc cross-references §9.1, §9.2, §9.3, §9.4, §9.5 throughout; rule does not say whether those become "Appendix A §1," "Appendix A.1," or stay as §9.1 under a renamed heading.

Same defect as Issue 50: the rename rule leaves subsection mapping unspecified.

## zoom_out — 0 Blockers, 7 Majors, 2 Nits (9)

### [Issue 38] [zoom_out-5-1] — Major — §10.5 step 3 (L373)
A whole fresh-context agent to do a deterministic diff the Elephant can do itself — and it is uncounted in the cost bound. "An independent review subagent audits the consolidation: it verifies each recorded severity change against the filed report (original severity matches, reason present) and that no severity change went unrecorded." Deterministic comparison of two artifacts the Elephant itself holds — the filed reviewer reports and the consolidated report it just wrote. Elephant can perform it in its own consolidation pass at zero spawns; instead the design spends a fresh-context subagent per pilot (frequency unstated — once per pilot, or once per round, when severity changes happen per round's consolidation). A fresh-context agent adds non-determinism to a deterministic check, and it is invisible to the cost envelope: §6 (L93, L97) and §10.4 (L367) all state the bound as "at most 25 spawns per run" / "max 25 per run", counting reviewer spawns only — true maximum is 26 (once per pilot) or 30 (once per round). Note: §10.3 dropped the synthesizer in Environment B for simplicity ("flat dispatch keeps attribution simple"), while the round-4 fix (E-C) added an agent back for bookkeeping. New, not a re-raise of r4 Issue 54: Issue 54 complained the subagent duplicated checks (a)/(b); E-C fixed that duplication but preserved the agent by re-scoping it to a job that needs no agent at all.

A deterministic check done by a fresh-context agent costs a spawn, adds non-determinism, and is invisible to the stated cost bound.

### [Issue 39] [zoom_out-5-2] — Major — §10.2 (L336)
"Zero drift on the repo side" rests on a CI step that is not in the specified CI change. §10.2: "repo-side drift (wrappers vs bundle) is covered by check C2, whose resolve loop runs as a step in the vendor-integrity CI job on every PR (it reads only the repo tree). … Maximum tolerable drift window: one sync interval on the local side; zero on the repo side (C2 runs on every PR)." But the CI change the doc actually specifies contains no C2 step: D4's literal tenth vendor-integrity block (L183–190) is only sha256sum -c, the comm -23 unlisted-files check, and the broken-symlink loop — and §11.3 (L422) specifies the ci.yml change as exactly "tenth vendor-integrity run: block — literal block in D4." C2 exists only as a manual sync-time procedure (§10.5 step 4, L374; §10.6 C2, L381), which runs at sync time, not on every PR. The vendor-integrity block checks files inside reference/elephant-goldfish-model/; the wrapper files C2 resolves live in skills/egm-*/, outside that tree. So the "zero on the repo side" claim is unfounded as specified. New, not a re-raise of r4 Issue 9: Issue 9 asked for continuous detection; the r4 fix (E-V) claimed to provide it via C2-in-CI, but the claim and the specified CI block disagree.

Same root cause as Issues 2, 21, and 35: the E-V fix claimed C2-in-CI but never added the step to the specified CI block.

### [Issue 40] [zoom_out-5-3] — Major — §10.4 (L367)
A token cap that does not exist yet is used to justify having no target-size cap now. §10.4: "A per-reviewer token cap bounds cost regardless of target-document size (token cost scales with target size, so the cap is the size bound); no separate maximum target size is set." The cap is created only by §14 decision 6 (L451), a pre-Phase-1 ruling ("Phase 1 does not start until decision 6 sets it"). During the pilot — currently in round 5 — neither a token cap nor a target-size cap exists; the pilot's actual bound is spawns × time (25 spawns × 30 minutes, L367), and a 30-minute reviewer can burn unbounded tokens on an unbounded target. The sentence asserts a control in the present tense and uses it to justify an in-force decision ("no separate maximum target size is set"), when the control comes into existence only after the pilot. New, not a re-raise of r4 Issue 55: Issue 55 complained the budget was deferred; the r4 fix (E-H) gated Phase 1 on decision 6 but inserted this sentence, which now misdescribes the pilot's own cost envelope.

A future control is used to justify a present absence; the sentence misdescribes the pilot's actual cost envelope.

### [Issue 41] [zoom_out-5-4] — Major — §11.3 (L422) et al.
The vendored set is enumerated five times in prose while the generated .sha256 file is the allowlist. One vendored set enumerated in five places with three different formulations: §7 "Not vendored" exclusion list (L120); D4's exclusion + file list (L183); §9.3 step 2's copy-command list (L290); §10.5 step 2's diff-command list (L372); §11.3's arithmetic inventory (L422: "skills/ (38 files: … 7 × 5 = 35 — plus references/ in egm-bootstrap (2 files) and egm-draft (1 file): 35 + 2 + 1 = 38) … docs/ (33 files: 13 top-level, 18 under docs/designs/, 1 asset SVG, 1 under docs/verification/)"). Yet §11.3 itself states "the allowlist is the generated .github/vendor-elephant-goldfish-model.sha256 itself … and the vendor-integrity job enforces it" — the machine-enforced truth is the generated file, and the prose arithmetic is a second, hand-maintained source of truth that must be re-verified on every re-vendor or it contradicts the hash. The doc's own §5 argument against subset vendoring is that "maintaining a subset file list is its own drift risk" — that argument applies verbatim to maintaining a prose inventory of the same 90 paths.

Five hand-maintained enumerations of one set, against the doc's own argument that maintaining such a list is itself a drift risk.

### [Issue 42] [zoom_out-5-5] — Major — L24, L42, L84, L450
The round-1 "65 findings" evidence is copied five times with no single source, and frozen at round 1. Same pilot statistic appears five times: L24 ("65 findings: 3 Blockers, 35 Majors, 27 Nits"), L42 twice ("found 65 findings" and "(65 findings) is evidence"), L84 ("the 65-finding pilot"), L450 ("the round-1 pilot: 65 findings including 3 Blockers"). It is load-bearing evidence for the §14 decision 5 pilot-value ruling (criterion (a), L450), yet it has no single source — the doc's D1 single-source-of-truth discipline covers the pin SHA but not its own evidence number — and it is frozen at round 1 while the loop has since completed rounds 2, 3, and 4 (round 4 alone: 56 findings, 52 fixes applied). Any correction to the count, or any decision to cite a later round, requires five coordinated edits across §§1, 3, 5, and 14. New, not a re-raise of r4 Issue 49 (which concerned specifying the full end state before the ruling): this concerns the evidence number's duplication and staleness.

Load-bearing evidence with no single source, frozen at round 1 while the loop has completed four rounds.

### [Issue 43] [zoom_out-5-6] — Major — §10.3.1 (L351) / D6 (L220)
'Verify outputs' is defined twice in one paragraph with different content — the round-4 fix replaced one occurrence and missed the second. Line 220, a single D6 paragraph, contains both: "'Verify outputs' means the snapshot diff plus the three checks in §10.3.1 (line-existence, standard-name, memory-prohibition), nothing else." — and, later in the same paragraph: "'Verify outputs' means these two checks, nothing else." The only check named in the sentences immediately preceding the second definition is the line-existence check (plus the snapshot diff earlier in the paragraph), so "these two checks" reads as snapshot diff + line-existence — exactly the old definition the round-4 fix (E-C part 1) was supposed to replace. The fix corrected one occurrence and left its stale twin in the same paragraph, so the document's core verification term now has two contradictory definitions 200 words apart. New evidence about an incomplete fix, not a re-raise of r4 Issues 19/39 (whose §10.3.1 sentence was fixed).

Same defect as Issue 28, stated from the zoom-out angle: the round-4 fix was incomplete in the same paragraph it fixed.

### [Issue 44] [zoom_out-5-7] — Major — §9.3 (L288–290)
The generic Path 2 layout installs skills into a directory no specified harness reads. §9.3 (L288): "Generic Path 2 layout: bundle at <install-root>/egm/, skills at <install-root>/skills/egm-*/ … Path 2 is supported only for Muse, whose skill-discovery convention is custom-skills/ (Environment B). No generic harness skill-discovery convention is specified: a non-Muse harness has no supported Path 2 route until its skill directory and load mechanism are specified per harness in §9.2." Step 3 (L290) then instructs: "Adapt the 7 SKILL.md files per D3 into <install-root>/skills/egm-*/." The generic skills/ directory is explicitly not Muse's convention ("not the generic skills/", L288) and no other consumer is specified — so the generic install procedure, followed literally on a headless VM, lands loadable skills in a directory nothing is specified to read. The generic layout is an abstraction over a single instance (Environment B's custom-skills/), with no generic consumer. Distinct from the open zoom_out-1-1 ESCALATE (whether §9 belongs in the doc / its provisional scope); it is an internal defect of §9.3's specified layout.

An install procedure that lands loadable skills in a directory nothing is specified to read is not an install procedure.

### [Issue 71] [zoom_out-5-8] — Nit — §10.3.3 (L359)
The selection rule is stated twice in the same paragraph. Line 359 contains, in one paragraph: "Use EGM where a written standard and a configured panel add value (design docs, upstream PRs); keep the lighter tools for fast checks." — and later in the same paragraph: "Selection rule: use EGM when the artifact is a design document (or an upstream PR) that needs a written standard and a configured panel with filed reports; use grilling or roundtable_review for a fast single-session challenge with no filed report; …" The round-4 fix (E-T part 3) appended the selection rule to a paragraph that already stated it. The boundary is also restated in §5's overlap bullet and §2's non-goal. One rule, stated once.

The round-4 fix appended a rule to a paragraph that already stated it, duplicating it in place.

### [Issue 72] [zoom_out-5-9] — Nit — Whole document (definitions)
Inline definitions are scattered across eight sections while §1 already has a Terminology paragraph. §1 (L20) already carries a Terminology paragraph (Muse / muse CLI / current Muse environment / Owner / Elephant / sync 'owner'), but the round-4 fixes added definitions elsewhere instead of there: D6 (L220) defines 'agent tool projections', 'Claude tool allowlists', 'configured memory services', 'project instructions', 'Verify outputs'; §10.2 (L336) defines 'live', 'sync record', 'Maximum tolerable drift window'; §10.4 (L367) defines 'Unsettled', 'substantially restate', SETTLED; §7 carries a 'Namespace note'; D5 (L213) defines 'Install notes'; §10.3.2 defines GoldfishContext; §14 decision 3 defines 'Documented-but-unexecuted'. Each round's comprehension fix adds another inline gloss where the term is first used, so defined terms are now spread across the whole document and two of them (§10.4's token cap, D6's 'Verify outputs' — see 5-3 and 5-6) have already drifted from their own definitions. A glossary that grows by accretion is itself a maintenance surface.

Definitions scattered across eight sections have already drifted from each other; each round adds more inline glosses to new locations.
