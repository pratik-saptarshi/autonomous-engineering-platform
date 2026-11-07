# Goldfish Annotated Review Report — Round 5

**Target:** `/home/hatch/workspace/plans/2026-11-06-egm-adoption-aep.md` (457 lines, post-round-4 fixes)

**Round:** 5 of 5 (cap). Rounds 1–4 all NOT CLEAN (0 clean rounds so far).

**Source findings:** round-5 FindingsList (72 findings: 4 Blockers, 40 Majors, 28 Nits; all 5 reviewers completed; no reviewer re-raised a settled item).

**Status:** resolved — all 71 PROPOSE FIX items applied to the target doc (457 → 546 lines) and verified by the coordinator; DECLINE (Issue 57) bypassed. No new ESCALATE. Cap reached: round 5 of 5.

**Note on filename:** the skill prescribes `goldfish_review_report.md`; this dated name is used instead so the pilot's artifacts stay distinct (as in prior rounds).

**Note on discrepancy/rationale text:** condensed from the FindingsList (substance preserved). Shared root causes are fixed once and cross-referenced — see the Shared-edit map. Each cluster is one fix, not one fix per Issue.

**Note on counts line:** 71 PROPOSE FIX + 0 CONTEST + 0 ESCALATE + 1 DECLINE + 0 SETTLED = 72 findings.

## ESCALATE — none new

**No new ESCALATE items in round 5.** The one live ESCALATE remains the round-1 item `zoom_out-1-1` (Environment A scope), still awaiting the owner's ruling. It was not re-raised in round 5.

## Category counts (72 findings)

- **CONTEST:** 0
- **ESCALATE:** 0 new (live `zoom_out-1-1` remains open, see above)
- **PROPOSE FIX:** 71 (4 Blockers, 40 Majors, 27 Nits)
- **DECLINE:** 1 (Issue 57 — structural-5-6, a Nit)
- **SETTLED:** 0

By reviewer: design_critic 25 PROPOSE FIX; structural 5 PROPOSE FIX + 1 DECLINE; implementation_readiness 11 PROPOSE FIX; comprehension 21 PROPOSE FIX; zoom_out 9 PROPOSE FIX.

## Citation / verification notes (checked against the 457-line target and live shell before writing fixes)

- **C2 corruption is real and byte-verified.** `od -c` on L381 proves the file literally contains doubled backslashes (`\\.` sequences) and backslash-quotes (`\"$f\"`, `\"reference/...\"`) in both C2 loops (L374, L381). The single-backslash form matches `../../reference/...`; the doubled form never matches (tested). `test -f` returns false on directories, `test -e` true (tested against the real bundle dirs). Bare directory references exist in the real adapted files exactly as the reviewer states: `~/workspace/egm/agents/` 4×, `~/workspace/egm/resources/document_standards/` 2×.
- **Correction to implementation_readiness-5-1 (recorded, not contested — the finding's core C2 defect is real).** Two of its sub-claims are wrong, verified by `od -c`: (a) the C1 main loop (L380) is byte-clean — plain `"$f"`, plain `"<bundle>/$p"`, single-backslash `sed 's/\.$//'` — its grep does not fail and its `test -e` is not false; (b) the §10.5 step-4 `cp`/`diff` commands are byte-clean (plain `"$tmp/$s"`, `"skills/$s"`), so no cp target contains literal quotes. The corruption is confined to the two C2 resolve loops, plus the C1 assertions' unbound `$f` (DC-5-17). The C1 assertions themselves have correct single-backslash ERE (`(\.\./\.\./docs/|\$\{CLAUDE_PLUGIN_ROOT\}/docs/)`) and plain quotes. R5-E fixes only what is actually broken.
- **Correction to implementation_readiness-5-8(c) (recorded, not contested).** `tests/unit` existence at the pin IS established upstream: TESTING.md at `e9e1f06a` documents `pytest tests/unit` as the unit-test command (L113), and the §9.2 clone is a full checkout including `tests/` (only the *vendored* set excludes it). The gap is the missing citation in the target doc, not an unknown path. R5-G asserts it with the citation.
- **D5 count corrected: 25, not 23.** `find ~/workspace/egm -type f ! -name '*.md'` returns 25 files; round 4's E-P count of 23 omitted `LICENSE` and `plugin.json`. R5-R enumerates all 25.
- **L76 bare `#252` confirmed** — the only remaining bare instance in the document (grep). L408's "No bare 'Issue N' references remain" is therefore false on this one line.
- **"Verify outputs" double definition confirmed** — both sentences are in the single L220 paragraph; "two checks" occurs nowhere else in the document (grep).
- **`~/workspace/plans/` is not a git repository** (`git -C plans rev-parse` fails; no `.git` in `plans/` or `~/workspace`), so §14 decision 2's "commit recorded in the pilot log" cannot be satisfied. R5-M replaces the commit with a content hash + date.
- **"65 findings" occurs 5 times on 4 lines** (L24, L42 twice, L84, L450). R5-AW keeps §3 as the single source.
- **Standing-loop-rule citation verified:** `~/workspace/custom-skills/ralph_loop/SKILL.md` L57, "Independent verification (standing rule, 2026-10-17)". R5-AN cites it.
- **Shell commands in the proposed edits were pasted verbatim into a shell and run in a sandbox before being written here**, except where noted: corrected C2 loop (passes on good refs, flags a genuinely dangling ref), CI C2 step form, sync-check compound script, D3 `bundle`-bound sed rows 1–7 (all rows run verbatim, idempotent on re-run), D6 `comm` exclusion procedure, C3 loop, readiness-gate `test -f` loop, disposable-copy `mkdir -p && cp`, `find -size +1M`, `file -b --mime-type` (`text/html`), `git log --format=%ci` staleness comparison, and the `date -d` 90-day arithmetic. Two caveats: (a) the C3 loop was run with system `python3` (this VM's python3 has PyYAML; `/tmp/egm-venv` does not exist on this VM) — the venv path in the fix is the doc's own §9.1 binding; (b) the `rm -rf` + `git clone` re-run prefix was not run against the network (clone is slow); the failure it cures — clone into an existing directory — is standard git behaviour, and the same `rm -rf`-first pattern is already used in the doc's D6 rollback. All proposed shell code is in fenced code blocks so Markdown escaping cannot re-corrupt it (the round-4 failure mode).
- **One consistent position on the C2-in-CI cluster (R5-A): ADD the C2 step to the CI block.** The doc's design intent (round-4 E-V) was C2-in-CI; the fix implements it rather than retreating the §10.2 claim. Applied consistently across all four findings in the cluster.

## Shared-edit map (one edit covers each group)

- **R5-A** C2-in-CI (add the C2 step to the CI block): Issues 2, 21, 35, 39.
- **R5-B** Pilot token cap (honest present tense + interim pilot cap ruling): Issues 9, 22, 40.
- **R5-C** Token-cap overflow behaviour: Issue 10.
- **R5-D** "Verify outputs" second definition deleted: Issues 28, 43.
- **R5-E** C2 loops fixed + C1 assertions bound in a per-file loop: Issues 1, 3, 45.
- **R5-F** Sync-check compound script: Issues 6, 4.
- **R5-G** Venv interpreter binding (pytest + python3 + checkout path + tests/unit citation): Issues 12, 26, 27.
- **R5-H** Cap/churn two literal questions: Issues 16, 36.
- **R5-I** Cursor/OpenCode row: Issues 52, 63.
- **R5-J** Design-doc coverage (Phase 1 Scope/Gate aligned, coverage defined): Issues 47, 69, 59.
- **R5-K** Appendix A naming/mapping: Issues 50, 70.
- **R5-L** L76 bare #252 link: Issue 5.
- **R5-M** Pilot target identity without git: Issue 7.
- **R5-N** D3 `<bundle>` binding: Issue 8.
- **R5-O** E2E gate per-shape: Issue 11.
- **R5-P** Per-reviewer report paths: Issue 13.
- **R5-Q** URL-fetch audit (URL-per-file + HTML test): Issue 14.
- **R5-R** D5 25 files: Issue 15.
- **R5-S** D6 disposable copy literal command: Issue 17.
- **R5-T** Demand baseline method: Issue 18.
- **R5-U** D6 snapshot exclusion procedure + location (3) + `rm -rf`: Issues 46, 23, 68.
- **R5-V** Bootstrap scheduled run in Phase 1: Issue 48.
- **R5-W** §11.3 arithmetic inventory deleted: Issues 49, 41.
- **R5-X** Clone steps re-runnable: Issue 51.
- **R5-Y** 90-day staleness computation + trigger: Issue 53.
- **R5-Z** Roles table normative prose moved to body: Issue 19 (structural-5-1 — see Issue numbering below; shared-edit label only).
- **R5-AA** Delta table as a real table: Issue 20 (structural-5-2).
- **R5-AB** Indent fenced blocks in lists: Issue 54.
- **R5-AC** Demote lone H4: Issue 55.
- **R5-AD** Procedures as ordered lists: Issue 56.
- **R5-AE** Timeout enforcement (acceptance-time): Issue 24.
- **R5-AF** Fresh-VM provisioning: Issue 25 (implementation_readiness-5-7).
- **R5-AG** Readiness-gate existence check: Issue 58.
- **R5-AH** Owner pointer to §10.3.2: Issue 29.
- **R5-AI** "Merged with conversation resolution" defined: Issue 30.
- **R5-AJ** "Sync from live" / "the manifest" at first use: Issue 31.
- **R5-AK** NeuroStrata / MCP / AGENTS.md defined: Issue 32.
- **R5-AL** §9.3 Path 2 layout (generic `skills/` deleted; `<install-root>` = `~/workspace`, skills in `custom-skills/`): Issues 33, 44.
- **R5-AM** Line-count design defined: Issue 34.
- **R5-AN** Ralph defined + standing loop rule cited: Issue 37.
- **R5-AO** `trusted_enabled` gloss: Issue 60.
- **R5-AP** PEP 668 expanded: Issue 61.
- **R5-AQ** Antigravity `/plugin` spelled out: Issue 62.
- **R5-AR** 40-char SHA gloss: Issue 64.
- **R5-AS** "Before synthesizing" → "before consolidating": Issue 65.
- **R5-AT** Decision 2 target senses separated: Issue 66.
- **R5-AU** "Rewrites references to": Issue 67 (comprehension-5-18).
- **R5-AV** Audit subagent deleted: Issue 38 (zoom_out-5-1).
- **R5-AW** 65-findings single source + round-4 outcome: Issue 42.
- **R5-AY** Selection rule stated once: Issue 71.
- **R5-AZ** Glossary consolidation (§1.1): Issue 72.

Note: shared-edit labels R5-Z onward collide with Issue numbers by design — the labels are edit IDs, not Issue numbers; each Issue entry below cites its edit ID explicitly.

## Shared edits (defined once, referenced by number)

- **R5-A — Add the C2 resolve loop as an eleventh step in the D4 vendor-integrity CI change; §10.2's claim stands.** (1) In D4, after the tenth `run:` block's final line (`find . -type l | while read -r link; do test -e "$link" || { echo "ERROR: broken symlink $link"; exit 1; }; done`), insert a second `run:` block inside the same fenced block (it starts at the repo root, so it reads `skills/` and `reference/` directly):

    ```
          - run: |
              missing=$(for f in skills/egm-*/SKILL.md; do grep -oE '\.\./\.\./reference/[A-Za-z0-9_./-]+' "$f"; done | sed 's/\.$//' | sort -u | while read -r p; do test -e "reference/${p#../../reference/}" || echo "MISSING: $p"; done)
              [ -z "$missing" ] || { echo "$missing"; exit 1; }
    ```

    (2) In §11.3 (L422), replace "`.github/workflows/ci.yml` (tenth `vendor-integrity` `run:` block — literal block in D4, inserted after the `humanizer` block)" with "`.github/workflows/ci.yml` (tenth `vendor-integrity` `run:` block — literal block in D4, inserted after the `humanizer` block — plus an eleventh `run:` block running the C2 wrapper-reference resolve loop from the repo root, literal block in D4)". No change to §10.2: with the step added, "zero on the repo side (C2 runs on every PR)" is now true as specified.
- **R5-B — Pilot token cap: honest present tense + an interim pilot cap ruling.** (1) In §6 (L93), replace "interim budget 12.5 reviewer-hours per run; token budget set by §14 decision 6 from the pilot log's actuals (per-reviewer and per-run maxima) before Phase 1 starts — no Phase 1 run proceeds without it" with "interim budget 12.5 reviewer-hours per run; interim pilot token cap (per-reviewer and per-run maxima) set by owner ruling before the next pilot run — no further pilot run proceeds without a recorded cap — and the Phase 1 token budget set by §14 decision 6 from the pilot log's actuals (per-reviewer and per-run maxima) before Phase 1 starts — no Phase 1 run proceeds without it". No token number is invented here; the number is the owner's ruling, which is exactly the doc's existing decision-6 mechanism. (2) In §10.4 (L367), replace "A per-reviewer token cap bounds cost regardless of target-document size (token cost scales with target size, so the cap is the size bound); no separate maximum target size is set." with "During the pilot, cost is bounded only by spawns × time (at most 25 spawns × 30 minutes); no token cap and no maximum target size exist yet. The decision-6 per-reviewer token cap, once set, becomes the size bound for Phase 1 (token cost scales with target size, so the cap is the size bound); no separate maximum target size is set." (3) In §10.4, replace "Interim pilot budget: at most 25 spawns × 30 minutes = 12.5 reviewer-hours per run; the pilot log's token actuals set the Phase 1 token budget via §14 decision 6." with "Interim pilot budget: at most 25 spawns × 30 minutes = 12.5 reviewer-hours per run; the interim pilot token cap is set by owner ruling before the next pilot run (see §6); the pilot log's token actuals set the Phase 1 token budget via §14 decision 6." (4) In §14 decision 6 (L451), replace "before Phase 1 the owner sets the per-reviewer timeout and the token budget (per-reviewer and per-run maxima), from the pilot log's elapsed-time and token records; Phase 1 does not start until this ruling is recorded." with "before the next pilot run the owner sets the interim pilot token cap (per-reviewer and per-run maxima); before Phase 1 the owner sets the per-reviewer timeout and the Phase 1 token budget (per-reviewer and per-run maxima), from the pilot log's elapsed-time and token records; Phase 1 does not start until this ruling is recorded."
- **R5-C — Token-cap overflow behaviour.** In §10.4 (L367), immediately after the R5-B part (2) replacement, insert: "Overflow: if a target document alone exceeds the per-reviewer token cap, the reviewer is recorded not run for that reviewer — never truncate the target, never breach the cap — and the round is not clean; the driver records the overflow in the pilot log."
- **R5-D — Delete the second "Verify outputs" definition.** In D6 (L220), replace "Each reviewer's report must cite every finding's target line numbers; the driver checks each cited line exists in the target at the stated range — a report failing the check is incomplete and re-run once, then recorded not run. 'Verify outputs' means these two checks, nothing else. Rollback: on a detected modification," with "Each reviewer's report must cite every finding's target line numbers; the driver checks each cited line exists in the target at the stated range — a report failing the check is incomplete and re-run once, then recorded not run. Rollback: on a detected modification,". The first definition (snapshot diff + the three §10.3.1 checks) stands alone. Verified: no other "two checks" phrasing survives in the document (grep).
- **R5-E — Fix the C2 loops (single backslashes, `test -e`, trailing-period strip); bind the C1 assertions' `$f`.** (1) In §10.5 step 4 (L374) and §10.6 C2 (L381), replace the resolve loop — current text (byte-verified): ``for f in skills/egm-*/SKILL.md; do grep -oE '\\.\\./\\.\\./reference/[A-Za-z0-9_./-]+' \"$f\"; done | sort -u | while read -r p; do test -f \"reference/${p#../../reference/}\" || echo \"MISSING: $p\"; done`` — with the corrected loop, in a fenced code block:

    ```
    for f in skills/egm-*/SKILL.md; do grep -oE '\.\./\.\./reference/[A-Za-z0-9_./-]+' "$f"; done | sed 's/\.$//' | sort -u | while read -r p; do test -e "reference/${p#../../reference/}" || echo "MISSING: $p"; done
    ```

    The `sed 's/\.$//'` strip is an addition beyond the reviewers' recommendation, verified in sandbox: without it a reference ending a sentence (`.../design_critic.md.`) is captured with its prose period and falsely reported MISSING. (2) In §10.6 C1 (L380), replace "Also assert, per adapted `SKILL.md`, the Muse routing line is present (`grep -q 'In Muse, read .*docs/muse\.md first\.' "$f"`) and no upstream-relative reference remains (`! grep -qE '(\.\./\.\./docs/|\$\{CLAUDE_PLUGIN_ROOT\}/docs/)' "$f"`)." with "Also assert, per adapted `SKILL.md`, the Muse routing line is present and no upstream-relative reference remains (run, from the install location, with `<skills-dir>` as in the C1 loop above):

    ```
    for f in <skills-dir>/egm-*/SKILL.md; do grep -q 'In Muse, read .*docs/muse\.md first\.' "$f" || echo "MISSING routing line: $f"; ! grep -qE '(\.\./\.\./docs/|\$\{CLAUDE_PLUGIN_ROOT\}/docs/)' "$f" || echo "UPSTREAM-RELATIVE reference remains: $f"; done
    ```

    Expected output: no `MISSING` / `UPSTREAM-RELATIVE` lines." The two component commands were verified verbatim against the real adapted files (both pass); the loop form mirrors the verified C1 loop. Note: the C1 assertions' patterns themselves were byte-clean (single-backslash ERE, plain quotes) — only their `$f` was unbound.
- **R5-F — Sync check as one compound, executable script.** In §10.5 step 4 (L374), replace "copy the seven local `custom-skills/egm-*/SKILL.md` files and the seven `skill.yaml` files to a temp dir created with `mktemp -d` (e.g. `/tmp/egm-sync-XXXXXX`), preserving their `egm-*/SKILL.md` + `egm-*/skill.yaml` layout: `tmp=$(mktemp -d); cd ~/workspace/custom-skills && cp --parents egm-*/SKILL.md egm-*/skill.yaml "$tmp"/`. Run `sed -i 's|~/workspace/egm|../../reference/elephant-goldfish-model|g'` on the `SKILL.md` copies, then compare per skill from the repo root (`for s in egm-*/; do diff -r "$tmp/$s" "skills/$s" || exit 1; done`) — expecting zero differences. (`diff -r` takes exactly two operands, so the temp dir is diffed against each repo `skills/egm-*/` directory in turn, not against the seven directories at once.)" with "copy the seven local `custom-skills/egm-*/SKILL.md` files and the seven `skill.yaml` files to a temp dir and compare per skill, as one compound command (run as a single invocation — `$tmp` is assigned and used inside it — with `<repo-root>` the AEP repo root, `~/workspace/autonomous-engineering-platform`):

    ```
    tmp=$(mktemp -d) && cd ~/workspace/custom-skills && cp --parents egm-*/SKILL.md egm-*/skill.yaml "$tmp"/ && sed -i 's|~/workspace/egm|../../reference/elephant-goldfish-model|g' "$tmp"/egm-*/SKILL.md && cd ~/workspace/autonomous-engineering-platform && for s in "$tmp"/egm-*/; do diff -r "$s" "skills/$(basename "$s")" || exit 1; done
    ```

    Expecting zero differences. (The `sed` now names its file operand, `"$tmp"/egm-*/SKILL.md`; the loop iterates the temp dir's own subdirectories, so it executes from any starting directory once the explicit `cd` to the repo root runs.)"
- **R5-G — Bind the venv interpreter; bind the checkout path; cite `tests/unit`.** (1) In §9.5 step 2 (L307), replace "`pytest tests/unit` in the cloned repo root (the `elephant-goldfish-model` checkout from §9.2); pass = exit code 0, all tests pass." with "`/tmp/egm-venv/bin/pytest tests/unit` in the cloned repo root (the `elephant-goldfish-model` checkout from §9.2, i.e. `./elephant-goldfish-model/` from the §9.2 clone command); pass = exit code 0, all tests pass. `tests/unit` exists at the pinned SHA (upstream TESTING.md documents `pytest tests/unit` as the unit-test command); the venv binary is used because §9.1 installs pytest only into `/tmp/egm-venv`, and bare `pytest` is not on `PATH` on a fresh VM." (2) In §10.6 C3 (L382–385), replace the parenthetical "(procedure: run with a python3 that has PyYAML installed; fresh VM: the §9.1 venv, `/tmp/egm-venv/bin/python3`:" with "(procedure: run with the §9.1 venv interpreter, `/tmp/egm-venv/bin/python3`, on the fresh VM — the literal loop below uses it; on Environment B, use the system `python3` only after `python3 -c "import yaml"` exits 0, and record the interpreter path in the pilot log:" and in the fenced C3 loop replace `a=$(python3 -c "import yaml,sys; print(yaml.safe_load(open(sys.argv[1]))['name'])" "$f")` with `a=$(/tmp/egm-venv/bin/python3 -c "import yaml,sys; print(yaml.safe_load(open(sys.argv[1]))['name'])" "$f")`. C6 inherits the procedure unchanged ("same as C3"). (3) In §9.2, after "(The clone creates `./elephant-goldfish-model/`, the default directory name the next command uses.)" append "That directory is also the working directory for §9.5 step 2; §9.3's `<install-root>/egm-checkout` is the same checkout under its Path 2 name — one checkout, two names, not two checkouts."
- **R5-H — Two literal questions: one for cap, one for churn.** In §10.4 (L367), replace "on cap or churn the driver stops and asks the owner one question, literally: 'The loop hit its cap (5 rounds) with unsettled findings — how do you want to proceed?' (options: accept and proceed / continue past the cap / return to drafting)." with "on cap or churn the driver stops and asks the owner one question, literally. On cap: 'The loop hit its cap (5 rounds) with unsettled findings — how do you want to proceed?' (options: accept and proceed / continue past the cap / return to drafting). On churn: 'The loop hit churn at round <n> — a new finding restates a finding fixed in an earlier round — how do you want to proceed?' (options: accept and proceed / continue the loop / return to drafting)." In the same line, replace "Threshold: the first occurrence — on churn the driver stops and asks the owner one question (see the cap/churn question in §10.4)." with "Threshold: the first occurrence — on churn the driver stops and asks the owner the churn question above."
- **R5-I — Cursor/OpenCode-only VMs do not adopt.** In §9.4 (L301), replace "a VM with only Cursor or OpenCode installed follows the headless row (Path 2, Muse only) or does not adopt." with "a VM with only Cursor or OpenCode installed does not adopt (Path 2 is Muse-only); the headless row applies only where Muse is present without its CLI."
- **R5-J — Phase 1 Scope/Gate aligned; coverage defined.** In the §11 rollout table, Phase 1 row (L401), replace Scope "Remaining 5 skills; `egm-drift-report` run once against a live design doc" with "Remaining 5 skills; `egm-drift-report` run once against the named target in the Gate column; `egm-bootstrap` run once against `reference/` tree documentation (see §10.3.3)" and replace Gate "All 7 gate-scanned; drift report names its target in advance (`skills/README.md` attribution table vs. `skills/` tree) and produces a dated finding, or a clean bill with the target's design-doc coverage stated; fails when no target is named." with "All 7 gate-scanned; drift report names its target in advance (`skills/README.md` attribution table vs. `skills/` tree) and produces a dated finding, or a clean bill stating the table's row coverage — every skill in the `skills/` tree accounted for as a row, a stated absence, or a stated mismatch, with the counts (rows compared vs skills in the tree) recorded; fails when no target is named."
- **R5-K — Appendix A naming and subsection mapping.** In §14 decision 3 (L448), replace "§9 is moved to an appendix (new heading `## Appendix A — Environment A (general-purpose Linux VM)`, placed after §14 and before the Sources appendix; all `§9` cross-references become `Appendix A` cross-references)" with "§9 is moved to an appendix (new heading `## Appendix A — Environment A (general-purpose Linux VM)`, placed after §14 and before the Sources appendix, which becomes `## Appendix B — Sources`; all `§9` cross-references become `Appendix A` cross-references, with subsections mapping §9.x → Appendix A §x, e.g. §9.5 step 3 → Appendix A §5 step 3)".
- **R5-L — Link the L76 bare `#252`.** In §5 (L76), replace "Waiting for upstream issue #252 to close instead of the D3 routing line" with "Waiting for upstream [issue #252](https://github.com/google/elephant-goldfish-model/issues/252) to close instead of the D3 routing line". The rest of the line already links #252 twice; after this fix a re-grep finds no bare instance, and L408's assertion holds.
- **R5-M — Pilot target identity without git.** (1) In §10.5 step 3 (L373), replace "Target: the commit recorded in the pilot log before dispatch (§14 decision 2)." with "Target: the content hash recorded in the pilot log before dispatch — `sha256sum <target>` output plus the recording date (`YYYY-MM-DD`) — (§14 decision 2); `~/workspace/plans/` is not a git repository, so no commit SHA exists for the pilot target." (2) In §14 decision 2 (L447), replace "the reviewed artifact is this document at the commit recorded in the pilot log before dispatch (as the round-1 pilot did — this document at its then-current HEAD)." with "the reviewed artifact is this document at the content hash recorded in the pilot log before dispatch — `sha256sum` of the file plus the recording date (as the round-1 pilot did — this document at its then-current content)." and replace "The Elephant records the chosen commit SHA in the pilot log before dispatch." with "The Elephant records the chosen content hash and date in the pilot log before dispatch."

- **R5-N — Bind `<bundle>` in the D3 literal commands; add a no-literal-`<bundle>` check.** In D3 (L171), replace "Literal commands (one per row, `<file>` is the adapted `SKILL.md`; each skips already-prefixed lines):" plus the seven `sed` commands with "Bind `<bundle>` first (Environment B: `bundle='~/workspace/egm'` — quoted, so the `~` form is preserved literally, not expanded; AEP wrappers: `bundle='../../reference/elephant-goldfish-model'`; Path 2: `bundle='<install-root>/egm'`), then run the literal commands below (one per row, `<file>` is the adapted `SKILL.md`; each skips already-prefixed lines; the `\|...|` address form is used because the bound value contains `/`, which would terminate a `/.../` address):

    ```
    sed -i "\|$bundle/agents|!s|agents/|$bundle/agents/|g" <file>
    sed -i "\|$bundle/resources/document_standards|!s|resources/document_standards/|$bundle/resources/document_standards/|g" <file>
    sed -i "\|$bundle/resources/execution_instructions.md|!s|resources/execution_instructions.md|$bundle/resources/execution_instructions.md|g" <file>
    sed -i "\|$bundle/docs/codex.md|!s|\.\./\.\./docs/codex.md|$bundle/docs/codex.md|g" <file>
    sed -i "\|$bundle/docs/claude.md|!s|\${CLAUDE_PLUGIN_ROOT}/docs/claude.md|$bundle/docs/claude.md|g" <file>
    sed -i "\|$bundle/docs/harnesses.md|!s|docs/harnesses.md|$bundle/docs/harnesses.md|g" <file>
    sed -i "\|$bundle/docs/muse.md|!s|docs/muse.md|$bundle/docs/muse.md|g" <file>
    ```

    After running them, assert no literal placeholder remains: `grep -q '<bundle>' <file> && { echo "ERROR: unbound <bundle> remains in <file>"; exit 1; }`. (C1's substring grep cannot catch this failure mode: `agents/...` matches inside a literal `<bundle>/agents/...` string while the real bundle path exists, so C1 passes on a corrupted file — this check is the only guard.)" All seven commands were run verbatim in a sandbox (Environment B binding): all upstream references rewritten, no literal `<bundle>`, re-running is a no-op.
- **R5-O — E2E gate per VM shape.** In §9.5 step 3 (L308), replace "Run headless via `muse exec --prompt /tmp/egm-e2e-<shape>/prompt.md` in the temporary workspace, approvals simulated up front per the fixture in a temporary workspace (`/tmp/egm-e2e-<shape>/`, where `<shape>` is one of the §9.4 VM shapes: `muse-cli`, `other-harness`, `headless`) against the installed cache only — 'installed cache' means the harness's installed plugin/skill cache on that VM (the plugin installed per §9.2), not the upstream checkout — prompt naming `docs/muse.md`, approvals simulated up front: brainstorm → draft → uninterrupted review. Run once per VM shape." with "Run once per VM shape. `muse-cli` shape: run headless via `muse exec --prompt /tmp/egm-e2e-muse-cli/prompt.md` in the temporary workspace (`/tmp/egm-e2e-muse-cli/`), approvals simulated up front per the fixture, against the installed cache only — 'installed cache' means the harness's installed plugin/skill cache on that VM (the plugin installed per §9.2), not the upstream checkout — prompt naming `docs/muse.md`, approvals simulated up front: brainstorm → draft → uninterrupted review. `other-harness` shape: run the same fixture with that harness's headless run command, named in the pilot log; if the harness has no headless run command, the shape has no E2E gate and does not pass. `headless` shape: there is no harness CLI to run the fixture — the E2E fixture does not apply; the shape's verification is the §10.6 checks alone, and 'installed cache' for Path 2 means the installed skills under `<install-root>/custom-skills/egm-*/` (per §9.3). The step-1 hand-exercise fallback does not save the headless shape: there is no harness to hand-exercise."
- **R5-P — Per-reviewer report paths.** (1) In §10.3.4 (L363), replace "Artifacts: the review report (`~/workspace/plans/<date>-<topic>-goldfish-review[-rN].md` in the pilot; in the PR for AEP) is the FindingsList — the consolidated flat list, one entry per finding with the fields above." with "Artifacts: each reviewer files one report at `~/workspace/plans/<date>-<topic>-<reviewer>-r<n>.md` (pilot; in the PR for AEP) before consolidation; the review report (`~/workspace/plans/<date>-<topic>-goldfish-review[-rN].md` in the pilot; in the PR for AEP) is the FindingsList — the consolidated flat list, one entry per finding with the fields above." (2) In the same paragraph, replace "resume by re-reading them and re-dispatching only reviewers with no filed report" with "resume by re-reading them and re-dispatching only reviewers with no filed report at the path above". (3) In §4 (L56), replace "each reviewer files a report" (both occurrences in the data-flow and loop-sequence sentences) with "each reviewer files a report at `~/workspace/plans/<date>-<topic>-<reviewer>-r<n>.md` (§10.3.4)".
- **R5-Q — URL-fetch audit: URL-per-file recording + a named HTML test.** (1) In §10.3.4 (L363), in the brief template item (6), replace "'Review the target as a Goldfish reviewer. (1) Persona: read <persona-file-absolute-path> first and follow it. (2) Target: <target-file-absolute-path>, lines <start>–<end>. (3) Standard: apply <standard-file-absolute-path>. (4) GoldfishContext: read <paths>. (5) Read-only: do not write to any file and do not read or write memory; report findings only. (6) Report shape: file one report citing the persona by name, the target line numbers for every finding, and the standard applied, with severity, discrepancy, and rationale per finding.'" with the same template plus, at the end of item (6): "and, for any file saved from a URL, that file's source URL." (2) In §12 (L435), replace "Enforcement: the Elephant audits the temp dir after the round — every saved file is ≤1 MB, every cited URL uses https, every saved file is HTML — and removes `/tmp/egm-urls-<run>/` after the round even if a reviewer fails or is recorded not run; a violation fails the round and is recorded in the pilot log." with "Enforcement: the Elephant audits the temp dir after the round — every saved file is ≤1 MB (`find /tmp/egm-urls-<run>/ -type f -size +1M` must print nothing), every recorded source URL uses https, every saved file is HTML (`file -b --mime-type <file>` must print `text/html`) — and removes `/tmp/egm-urls-<run>/` after the round even if a reviewer fails or is recorded not run; a violation fails the round and is recorded in the pilot log."
- **R5-R — D5 content review enumerates all 25 non-markdown files.** In D5 (L213), replace "Bundle non-markdown files are content-reviewed at vendor time — 23 files at the pinned SHA: `agents/openai.yaml` ×7 (one per skill), per-skill `test_scenarios.yaml` ×7, `skills/egm-bootstrap/references/worker-return.schema.json` ×1, `assets/icon.svg` ×7 (one per skill), `docs/assets/readme-header.svg` ×1." with "Bundle non-markdown files are content-reviewed at vendor time — 25 files at the pinned SHA: `agents/openai.yaml` ×7 (one per skill), per-skill `test_scenarios.yaml` ×7, `skills/egm-bootstrap/references/worker-return.schema.json` ×1, `assets/icon.svg` ×7 (one per skill), `docs/assets/readme-header.svg` ×1, `LICENSE` ×1, `plugin.json` ×1 (the harness-read plugin manifest — the highest-trust file, declaring what the harness loads)." (Round 4's E-P count of 23 omitted `LICENSE` and `plugin.json`; the 25-file total is verified against the local bundle.)
- **R5-S — D6 disposable copy as a literal command.** In D6 (L220), replace "Before dispatch, copy the target document to a disposable per-round copy (`/tmp/egm-review-<run>/target.md`, byte-identical; line numbers map 1:1 onto the original) and brief reviewers with the copy's path" with "Before dispatch, copy the target document to a disposable per-round copy with the literal commands (`<target>` is the target document's absolute path):

    ```
    mkdir -p /tmp/egm-review-<run> && cp <target> /tmp/egm-review-<run>/target.md
    ```

    The copy is byte-identical; line numbers map 1:1 onto the original) and brief reviewers with the copy's path".
- **R5-T — Demand baseline: corpus, window, counting method.** In §3 (L42), replace "the Phase 0 pilot log records design docs produced per month as the demand baseline for the Phase 1 value judgment (§14 decision 5)." with "the Phase 0 pilot log records design docs produced per month as the demand baseline for the Phase 1 value judgment (§14 decision 5). Corpus: the 22 top-level AEP `docs/*.md` files (37 recursive) plus dated plans under `~/workspace/plans/`. Window: one calendar month. Counting method: at month end the Elephant counts design documents created in the month — dated plans by filename date (`YYYY-MM-DD` prefix), AEP `docs/` files by first-commit date (`git log --diff-filter=A --format=%ad --date=short -- docs/` in the AEP repo) — and records the two counts separately in the pilot log. (`~/workspace/plans/` is not versioned, so no git-based count covers it; the filename-date count is the method there.)"
- **R5-U — D6 snapshot: location (3) form, exclusion procedure, `-after` names, `rm -rf`.** (1) In D6 (L220), replace "(`find <dir> -type f -exec sha256sum {} + | sort > /tmp/egm-snapshot-<run>-<n>.sha256`, one file per location, `<n>` = 1–4 for the four locations in scope order, `<run>` is the round number, e.g. `r3`): (1) the target repo working tree, (2) `~/workspace/egm/`, (3) each `~/workspace/custom-skills/egm-*/` dir, (4) `~/workspace/plans/`." with "(`find <dir> -type f -exec sha256sum {} + | sort > /tmp/egm-snapshot-<run>-<n>.sha256`, one file per location, `<n>` = 1–4 for the four locations in scope order, `<run>` is the round number, e.g. `r3`): (1) the target repo working tree, (2) `~/workspace/egm/`, (3) all seven `~/workspace/custom-skills/egm-*/` dirs together in one snapshot file (one `find` over the glob: `find ~/workspace/custom-skills/egm-*/ -type f -exec sha256sum {} + | sort`), (4) `~/workspace/plans/`." (2) In D6, replace "Re-run the same commands to `-after` files and `diff` each pair; any output names a modified path. The after-diff ignores files under `~/workspace/plans/` that did not exist at snapshot time (the round's own report and pilot-log entries); any modification or deletion of a pre-existing file under `~/workspace/plans/`, or any change at the other three locations, fails the round." with "Re-run the same commands to `-after` files (`/tmp/egm-snapshot-<run>-<n>-after.sha256`) and compare each pair with the exclusion procedure below; any output names a modified path. Exclusion procedure (per pair, with `<before>` the snapshot file and `<after>` the `-after` file): added paths are `comm -13 <(awk '{print $2}' <before> | sort) <(awk '{print $2}' <after> | sort)`; removed paths are `comm -23` with the same inputs; changed paths are those present in both files with a different hash, `join -j 2 <(sort -k2 <before>) <(sort -k2 <after>) | awk '$2 != $3 {print $1}'`. The after-diff ignores added paths under `~/workspace/plans/` (the round's own report and pilot-log entries); any removed or changed path anywhere, or any added path outside `~/workspace/plans/`, fails the round." (3) In D6, replace "remove newly created untracked files (`rm -- <paths>`)" with "remove newly created untracked files and directories (`rm -rf -- <paths>`; plain `rm` fails on newly created directories)".
- **R5-V — Bootstrap run scheduled in Phase 1.** In §10.3.3 (L359), replace "Both skills are deferred to Phase 1 with these named targets." with "Both skills are deferred to Phase 1 with these named targets. Phase 1 runs `egm-drift-report` once against its named target (§11) and runs `egm-bootstrap` once against the `reference/` tree documentation, each producing a dated finding or a clean bill." (The §11 Phase 1 Scope half of this is in R5-J.)
- **R5-W — Delete the §11.3 arithmetic inventory; the generated hash is the allowlist.** (1) In §11.3 (L422), replace "Created: `reference/elephant-goldfish-model/` bundle, 90 files at the pinned SHA — `skills/` (38 files: per skill `SKILL.md`, `TEST.md`, `agents/openai.yaml`, `assets/icon.svg`, `test_scenarios.yaml` — 7 × 5 = 35 — plus `references/` in `egm-bootstrap` (2 files) and `egm-draft` (1 file): 35 + 2 + 1 = 38), `agents/` (10 persona files), `resources/` (7: `execution_instructions.md`, `README.md`, 5 standards), `docs/` (33 files: 13 top-level, 18 under `docs/designs/`, 1 asset SVG, 1 under `docs/verification/`), `LICENSE`, `plugin.json`;" with "Created: `reference/elephant-goldfish-model/` bundle, 90 files at the pinned SHA (per-skill files under `skills/`, `agents/`, `resources/`, `docs/`, `LICENSE`, `plugin.json` — the full path list is the generated `.github/vendor-elephant-goldfish-model.sha256`);" (2) In §11.3, replace "Exact path list (allowlist): the allowlist is the generated `.github/vendor-elephant-goldfish-model.sha256` itself (a Created file in this PR, generated by the D4 command from the pinned SHA); the pre-execution statement of its contents is the 90-path inventory above (38 + 10 + 7 + 33 + `LICENSE` + `plugin.json`), and the `vendor-integrity` job enforces it." with "Allowlist: the allowlist is the generated `.github/vendor-elephant-goldfish-model.sha256` itself (a Created file in this PR, generated by the D4 command from the pinned SHA); the `vendor-integrity` job enforces it. The 90-file total above is a count, not a path list — no prose inventory of the 90 paths is maintained, because the generated hash file is the single source of truth for the vendored set." (3) In §7 (L120), append to the "Not vendored" bullet: "The authoritative included set is the §10.5 step 2 diff command's enumeration — the prose lists here state what is excluded, not a second copy of what is included."
- **R5-X — Clone steps re-runnable.** (1) In §9.3 step 1 (L290), replace "1) Clone upstream at the pinned SHA (`git clone https://github.com/google/elephant-goldfish-model.git <install-root>/egm-checkout && cd <install-root>/egm-checkout && git fetch --depth 1 origin e9e1f06a && git checkout e9e1f06a`)" with "1) Clone upstream at the pinned SHA (`rm -rf <install-root>/egm-checkout && git clone https://github.com/google/elephant-goldfish-model.git <install-root>/egm-checkout && cd <install-root>/egm-checkout && git fetch --depth 1 origin e9e1f06a && git checkout e9e1f06a`)". (2) In §10.5 step 2 (L372), replace "`git clone https://github.com/google/elephant-goldfish-model.git /tmp/egm-upstream && cd /tmp/egm-upstream && git fetch --depth 1 origin e9e1f06a && git checkout e9e1f06a && git rev-parse HEAD`" with "`rm -rf /tmp/egm-upstream && git clone https://github.com/google/elephant-goldfish-model.git /tmp/egm-upstream && cd /tmp/egm-upstream && git fetch --depth 1 origin e9e1f06a && git checkout e9e1f06a && git rev-parse HEAD`".
- **R5-Y — 90-day staleness: computation + trigger.** In D1 (L138), replace "if upstream HEAD is more than 90 days newer than the pin, the sync record notes the pin as stale and the owner rules on re-vendor." with "if upstream HEAD is more than 90 days newer than the pin — computed from commit dates in the upstream clone (`git log -1 --format=%ci <pin>` vs `git log -1 --format=%ci HEAD`; stale when the HEAD date is more than 90 days after the pin date) — the sync record notes the pin as stale and the owner rules on re-vendor. The check runs on every sync and at each phase gate; between gates a pin may go stale silently, which is accepted explicitly (no continuous staleness watch exists)."
- **R5-Z — Roles table: one-sentence role definitions; normative prose to body text.** (1) In the §10.3 Roles table (L344), replace the Elephant cell "The session that owns the design doc and runs the loop (Environment B: the main agent; Environment A Path 1: the harness session that installed the plugin). Consolidation procedure: the Elephant merges duplicate findings (same target lines + same discrepancy), normalizes severity to the assigned standard, and assigns stable ids (`<reviewer>-<round>-<n>`); overlaps are recorded in the report. Severity rule: the Elephant must not change a finding's severity on consolidation without recording the change in the report (original severity, new severity, reason); a severity downgrade with no recorded reason is a defect in the report, not a judgment call." with "The session that owns the design doc and runs the loop (Environment B: the main agent; Environment A Path 1: the harness session that installed the plugin)." (2) In §10.3.4 (L363), extend "Any severity change on consolidation is recorded with its original severity and reason (see §10.3)." to "The Elephant merges duplicate findings (same target lines + same discrepancy), normalizes severity to the assigned standard, and assigns stable ids (`<reviewer>-<round>-<n>`); overlaps are recorded in the report. Any severity change on consolidation is recorded with its original severity, new severity, and reason; a severity downgrade with no recorded reason is a defect in the report, not a judgment call." (3) In the Roles table (L347), replace the Synthesizer cell "The `agents/synthesizer.md` role; in Environment B it is replaced by direct dispatch (direct dispatch from the Elephant by design — flat dispatch keeps attribution simple; this is a design choice, not a platform limit: depth-2 spawning — a subagent spawning its own subagent — works in this environment) with the Elephant consolidating findings; in Path 1 it is used where the harness nests subagents." with "The `agents/synthesizer.md` role; in Environment B it is replaced by direct dispatch from the Elephant, with the Elephant consolidating findings; in Path 1 it is used where the harness nests subagents." and add to the §10.3 body text under the table: "Direct dispatch from the Elephant is by design — flat dispatch keeps attribution simple; this is a design choice, not a platform limit: depth-2 spawning — a subagent spawning its own subagent — works in this environment."
- **R5-AA — Delta table as a real table.** In §5 (L84), replace the one-paragraph "Delta table (roundtable_review vs EGM): roundtable_review vs EGM — written standard: none vs 5 standards files; configured reviewer panel: per-run reviewers + debate + judge vs 10 named personas + synthesizer; fresh-context reviewers: both; claim verification: verification subagents + judge vs driver line-existence + standard-name checks; drift/bootstrap skills: none vs `egm-drift-report` + `egm-bootstrap`; dated report artifacts: single-session vs filed reports + resolve loop." with:

    ```
    | Dimension | roundtable_review | EGM |
    |---|---|---|
    | Written standard | none | 5 standards files |
    | Configured reviewer panel | per-run reviewers + debate + judge | 10 named personas + synthesizer |
    | Fresh-context reviewers | yes | yes |
    | Claim verification | verification subagents + judge | driver line-existence + standard-name checks |
    | Drift/bootstrap skills | none | `egm-drift-report` + `egm-bootstrap` |
    | Dated report artifacts | single-session | filed reports + resolve loop |
    ```

    Keep the two trailing sentences ("Genuinely new delta: …" and "No roundtable baseline control run was performed …") as body text below the table. No cross-reference changes needed (L67 and L359 already point at "the delta table (§5, …)").
- **R5-AB — Indent fenced blocks (and the C3 "Expected:" line) into their list items.** (1) D4 (L185, L191): indent the opening and closing fence lines of the tenth `run:` block by 2 spaces (the `- **Bundle:**` bullet's continuation indent). (2) §10.6 C3 (L384, L386): indent the opening and closing fence lines by 3 spaces (the numbered item's continuation indent), and indent the `Expected: exit 0, no MISMATCH lines).` line (L388) by 3 spaces. The other fenced blocks (§9.2 L247–251, §10.2 L324–332) sit at top level and do not split anything — unchanged.
- **R5-AC — Demote the lone H4 to a bold lead-in.** In §9.2 (L264), replace "#### Native installs for the other harnesses (commands from the bundle's `docs/harnesses.md` install table)" with "**Native installs for the other harnesses:** commands from the bundle's `docs/harnesses.md` install table." Do not promote to H3 (would cascade-renumber §9.3–§9.5 and cross-references).
- **R5-AD — Multi-step procedures as ordered lists.** (1) In §9.3 (L290), reformat "Install steps: 1) Clone … 2) Copy … 3) Adapt … 4) Hand-write … 5) Gate-scan … 6) Verify …" as an ordered list ("Install steps:" followed by six `N.` items, one step per item, same wording). (2) In §10.2 (L336), replace "(Sync steps (local→repo direction only): 1) diff local `custom-skills/egm-*/` against repo `skills/egm-*/` using the §10.5 step 4 normalize-then-diff (the `sed` runs on temp copies, per-skill loop — a raw diff would show every adapted `SKILL.md` as changed, because local files contain `~/workspace/egm/...` and repo wrappers contain `../../reference/elephant-goldfish-model/...`); 2) copy the normalized temp copies (not the verbatim local files) into the repo wrappers, applying the same `~/workspace/egm` → `../../reference/elephant-goldfish-model` translation — copying local files verbatim would write local paths into the repo wrappers and break them; 3) regenerate the manifest (`scripts/check_skills_manifest.py --root skills --write` from the repo root); 4) verify with the §10.5 step 4 normalize-then-diff check; 5) commit per Conventional Commits. Owner: the agent running the sync (the Elephant / main agent session that owns the change) — not a separate role.)" with "Sync steps (local→repo direction only):

    1. Diff local `custom-skills/egm-*/` against repo `skills/egm-*/` using the §10.5 step 4 normalize-then-diff (the `sed` runs on temp copies, per-skill loop — a raw diff would show every adapted `SKILL.md` as changed, because local files contain `~/workspace/egm/...` and repo wrappers contain `../../reference/elephant-goldfish-model/...`).
    2. Copy the normalized temp copies (not the verbatim local files) into the repo wrappers, applying the same `~/workspace/egm` → `../../reference/elephant-goldfish-model` translation — copying local files verbatim would write local paths into the repo wrappers and break them.
    3. Regenerate the manifest (`scripts/check_skills_manifest.py --root skills --write` from the repo root).
    4. Verify with the §10.5 step 4 normalize-then-diff check.
    5. Commit per Conventional Commits.

    Owner: the agent running the sync (the Elephant / main agent session that owns the change) — not a separate role."
- **R5-AE — Timeout enforcement (acceptance-time, not a kill).** In §10.4 (L367), replace "Timeout: 30 minutes per reviewer for the pilot (interim bound; no pilot log with per-reviewer elapsed times exists yet, so this bound is set now and the pilot log records actual elapsed times)." with "Timeout: 30 minutes per reviewer for the pilot (interim bound; no pilot log with per-reviewer elapsed times exists yet, so this bound is set now and the pilot log records actual elapsed times). Enforcement: `subagent.spawn` has no timeout parameter and no in-flight kill, so the timeout is enforced at acceptance — the driver records the dispatch wall-clock time, and a report arriving more than 30 minutes after dispatch is treated as timed out (retried once, then recorded not run); a late report is never accepted as on time." In §10.3.4 (L363), replace "a reviewer that times out, fails, or returns no report is retried once, then recorded not run" with "a reviewer that times out (a report arriving more than 30 minutes after dispatch; see §10.4), fails, or returns no report is retried once, then recorded not run".
- **R5-AF — Fresh-VM provisioning: image + packages + harness CLI source.** In §9.1 (L240), after "`git` ≥ 2.43.0, `python3` ≥ 3.12.3 (verified floor on this VM, Environment B)," insert "Fresh-VM image: an Ubuntu 24.04 cloud image (which ships `git` 2.43.0 and `python3` 3.12.3, the floors above). Provisioning: install `git`, `python3`, and `python3-venv` from the distro packages, then install the harness CLI per its vendor instructions (§9.2 links) — no other install source is specified." In §11 Phase 3 Scope, replace "Provisioning: install prerequisites, clone upstream at the pinned SHA, install per the §9.2/§9.3 path" with "Provisioning: install prerequisites per §9.1 (Ubuntu 24.04 image; distro packages `git`, `python3`, `python3-venv`; harness CLI per vendor instructions), clone upstream at the pinned SHA, install per the §9.2/§9.3 path".
- **R5-AG — Readiness-gate existence check.** In §10.3.2 (L352), after "Readiness gate (fires before a review loop starts): the target document exists, reviewers and standards resolve to existing files, and GoldfishContext is provided" insert "The Elephant runs this check before asking the gate question, with the brief's absolute paths substituted for the placeholders:

    ```
    for p in <target> <persona-paths...> <standard-paths...> <goldfishcontext-paths...>; do test -f "$p" || echo "MISSING: $p"; done
    ```

    Expected output: no `MISSING` lines; any `MISSING` line fails the readiness gate."
- **R5-AH — Owner pointer to §10.3.2.** In §1 (L20), replace "the same 'human' in §7's approval gates" with "the same 'human' in §10.3.2's approval gates".
- **R5-AI — Define "merged with conversation resolution".** In §2 (L30), replace "AEP PR — CI green including vendor-integrity + skills-freshness, merged with conversation resolution." with "AEP PR — CI green including vendor-integrity + skills-freshness, merged with conversation resolution — every PR review thread resolved, per the repo's branch protection (conversation resolution required)."
- **R5-AJ — Name the manifest and "live" at first use in D4.** In D4 (L195–197), replace "the gate proves the repo `skills/` tree equals the manifest generated from the repo tree after the last sync from live" with "the gate proves the repo `skills/` tree equals the manifest (`.github/skills-manifest.sha256`, §11.3) generated from the repo tree after the last sync from the local tree (`~/workspace/custom-skills/`, 'live' in §10.2)".
- **R5-AK — Define NeuroStrata / MCP / AGENTS.md in D6.** In D6 (L220), after "'Configured memory services' means the NeuroStrata MCP connector and any other configured memory; 'project instructions' means `AGENTS.md` and repo instruction files." insert "NeuroStrata is the local memory store used by this environment (see the companion doc, §2); the NeuroStrata MCP connector is the MCP (Model Context Protocol) connection through which agents read and write that store. `AGENTS.md` files are repo instruction files for agents (e.g. the AEP repo's `AGENTS.md`)."
- **R5-AL — §9.3 Path 2: no generic `skills/` layout; `<install-root>` = `~/workspace`.** (1) In §9.3 (L288), replace "`<install-root>` is the directory holding the cloned repo and the installed skills, default `$HOME` (example: `/home/<user>`), so the bundle is `$HOME/egm/`. Generic Path 2 layout: bundle at `<install-root>/egm/`, skills at `<install-root>/skills/egm-*/`, resolving bundle paths against `<install-root>/egm/`. Environment B mapping: `<install-root>` = `~/workspace`, so the bundle is `~/workspace/egm/` and the skills are `~/workspace/custom-skills/egm-*/` (Muse's `custom-skills/` convention, not the generic `skills/`). Example path strings a Path 2 skill contains: `$HOME/egm/agents/design_critic.md`; in Environment B the same string reads `/home/hatch/workspace/egm/agents/design_critic.md`. Path 2 is supported only for Muse, whose skill-discovery convention is `custom-skills/` (Environment B). No generic harness skill-discovery convention is specified: a non-Muse harness has no supported Path 2 route until its skill directory and load mechanism are specified per harness in §9.2." with "`<install-root>` is `~/workspace`, the directory holding the cloned repo and the installed skills. Path 2 is specified only in its one known form: bundle at `<install-root>/egm/`, skills at `<install-root>/custom-skills/egm-*/` (Muse's `custom-skills/` convention). There is no generic `<install-root>/skills/` layout: no harness is specified to read it, so no generic skills directory is prescribed as an install target. Example path strings a Path 2 skill contains: `~/workspace/egm/agents/design_critic.md` (the `~` form, per D3; the expanded form `/home/hatch/workspace/egm/...` never appears in a pilot adapted file). Path 2 is supported only for Muse. No generic harness skill-discovery convention is specified: a non-Muse harness has no supported Path 2 route until its skill directory and load mechanism are specified per harness in §9.2." (2) In §9.3 (L282–286), replace "- Bundle intact at `<install-root>/egm/` (skills, agents, resources, docs, LICENSE)." with "- Bundle intact at `<install-root>/egm/` (skills, agents, resources, docs, LICENSE)." (unchanged) and replace "- One skill directory per skill at `<install-root>/skills/egm-*/`" with "- One skill directory per skill at `<install-root>/custom-skills/egm-*/`" and in install step 3 (L290) replace "Adapt the 7 `SKILL.md` files per D3 into `<install-root>/skills/egm-*/`." with "Adapt the 7 `SKILL.md` files per D3 into `<install-root>/custom-skills/egm-*/`."
- **R5-AM — Define the line-count design.** In §9.5 step 3 (L308), replace "fixture design `muse-wonder-1.0` (the upstream fixture name for the brainstorm → draft → review sequence; a line-count design, per the upstream Muse row in TESTING.md)" with "fixture design `muse-wonder-1.0` (the upstream fixture name for the brainstorm → draft → review sequence; a line-count design — the fixture's design subject is a line-counting tool, per the upstream Muse row in TESTING.md — and the draft stage produces a design document for that tool)". (TESTING.md names it "line-count design" without elaborating; the doc states the subject plainly rather than leaving the reader to guess what is being designed.)
- **R5-AN — Define Ralph; cite the standing loop rule.** (1) In §10.3.3 (L359), replace "The Ralph per-iteration verifier (`~/workspace/ralph/` loop — an independent, non-blocking verification subagent at the end of every iteration, per the standing loop rule)" with "The Ralph per-iteration verifier (Ralph is the autonomous loop system in `~/workspace/ralph/`; the verifier is an independent, non-blocking verification subagent at the end of every iteration, per the standing loop rule recorded in `~/workspace/custom-skills/ralph_loop/SKILL.md`, 'Independent verification (standing rule, 2026-10-17)')". (2) In §2 (L37), replace "or the Ralph verifier" with "or the Ralph verifier (defined in §10.3.3)".
- **R5-AO — Gloss `trusted_enabled`.** In D7 (L224), replace "report `trusted_enabled` (the status the harness reports for the named definition)" with "report `trusted_enabled` (`trusted_enabled`: the harness lists the definition as trusted/available, though spawning it is still rejected with `agent_definition_unavailable`)".
- **R5-AP — Expand PEP 668.** In §9.1 (L240), replace "a venv is used because PEP 668 externally-managed environments refuse bare `pip install`" with "a venv is used because PEP 668 (the Python standard for externally-managed environments) means externally-managed environments refuse bare `pip install`".
- **R5-AQ — Spell out the Antigravity `/plugin` step.** In §9.2 (L269), replace "- **Antigravity App/IDEs:** run `/plugin`" with "- **Antigravity App/IDEs:** run the `/plugin` slash command to open the plugin installer".
- **R5-AR — Full-form pin gloss.** In §10.5 step 2 (L372), replace "`git rev-parse HEAD` must print exactly `e9e1f06aa4e26e95cd4ed37210a0632202c429e9`" with "`git rev-parse HEAD` must print exactly `e9e1f06aa4e26e95cd4ed37210a0632202c429e9` (the full form of the `e9e1f06a` pin)".
- **R5-AS — "Before consolidating".** In §10.3.1 (L351), replace "Wait for actual completion before synthesizing; propagate failures and timeouts." with "Wait for actual completion before consolidating; propagate failures and timeouts."
- **R5-AT — Separate the two senses of "target" in decision 2.** In §14 decision 2 (L447), replace "The AEP repo is context (GoldfishContext), not the target: the Phase 2 PR (branch `chore/reference-vendor-elephant-goldfish-model`) is the target state the pilot's evidence supports, not the artifact under review." with "The AEP repo is context (GoldfishContext), not the artifact under review: the Phase 2 PR (branch `chore/reference-vendor-elephant-goldfish-model`) is the end state the pilot's evidence supports, not the artifact under review."
- **R5-AU — "Rewrites references to".** In §5 (L73 and L77), replace both occurrences of "D3 rewrites `docs/codex.md`, `docs/claude.md`, `docs/harnesses.md`" with "D3 rewrites references to `docs/codex.md`, `docs/claude.md`, `docs/harnesses.md`".
- **R5-AV — Delete the audit subagent; fold the severity-change audit into the Elephant's consolidation pass.** (1) In §10.5 step 3 (L373), replace "An independent review subagent audits the consolidation: it verifies each recorded severity change against the filed report (original severity matches, reason present) and that no severity change went unrecorded. Checks (a) and (b) are performed once, by the driver at intake; check (c) is performed once, by the Elephant at consolidation — the subagent does not re-perform them." with "The Elephant audits its own consolidation in the same pass: it verifies each recorded severity change against the filed per-reviewer report (original severity matches, reason present) and that no severity change went unrecorded. Checks (a) and (b) are performed once, by the driver at intake; check (c) is performed once, by the Elephant at consolidation. No audit subagent is spawned: the check is a deterministic comparison of two artifacts the Elephant already holds (the filed per-reviewer reports and the consolidated report), and a fresh-context agent would add non-determinism to it. The §6/§10.4 spawn bound (at most 25 spawns per run) counts reviewer spawns only, and no other spawn is made by the loop." (2) In §6 (L93), replace "(at most 5 rounds × 5 reviewers = 25 spawns per run; 30-minute interim per-reviewer timeout for the pilot;" with "(at most 5 rounds × 5 reviewers = 25 spawns per run, and no other spawns are made by the loop; 30-minute interim per-reviewer timeout for the pilot;". (If independence of the severity audit is the point, the doc must say so and price it — it currently does neither.)
- **R5-AW — "65 findings" stated once (in §3); round-4 outcome recorded.** (1) In §1 (L24), replace "(2026-11-06, 65 findings: 3 Blockers, 35 Majors, 27 Nits; report `~/workspace/plans/2026-11-06-egm-adoption-aep-goldfish-review.md`)" with "(2026-11-06; see §3 for the pilot results, report `~/workspace/plans/2026-11-06-egm-adoption-aep-goldfish-review.md`)". (2) In §3 (L42), replace "The pilot round-1 review (65 findings) is evidence the instrument works, not evidence of the problem's scale." with "The pilot round-1 review is evidence the instrument works, not evidence of the problem's scale. Rounds 1–4 are complete (round 4: 56 findings, 52 fixes applied); no round has been clean." (3) In §5 (L84), replace "so the 65-finding pilot does not establish marginal value over the incumbent" with "so the §3 pilot does not establish marginal value over the incumbent". (4) In §14 decision 5 (L450), replace "(the round-1 pilot: 65 findings including 3 Blockers, among them a genuine D3/Path 1 contradiction and a missing CI edit)" with "(the round-1 pilot — see §3 — including 3 Blockers, among them a genuine D3/Path 1 contradiction and a missing CI edit)".
- **R5-AY — Selection rule stated once.** In §10.3.3 (L359), delete "Use EGM where a written standard and a configured panel add value (design docs, upstream PRs); keep the lighter tools for fast checks. " (the sentence preceding "Named targets:"), keeping the "Selection rule:" sentence. The §5/§2 mentions remain as the single cross-references.
- **R5-AZ — Consolidate defined terms into a §1.1 Glossary.** (1) Insert after the §1 Terminology paragraph (L20) a "### 1.1 Glossary" listing, verbatim as currently defined, each term below with its defining location noted; new terms go here, not in the section that first trips over them: 'agent tool projections' / 'Claude tool allowlists' / 'configured memory services' / 'project instructions' / 'Verify outputs' (D6); 'live' / 'sync record' / 'Maximum tolerable drift window' (§10.2); 'Unsettled' / 'substantially restate' / 'SETTLED' (§10.4); 'Namespace note' (§7); 'Install notes' (D5); 'GoldfishContext' (§10.3.2); 'Documented-but-unexecuted' (§14 decision 3). (2) Replace each inline definition with "(see §1.1 Glossary)" at its current location, keeping the term's first use in place. Interactions: R5-B's reworded token-cap sentence and R5-D's deleted second "Verify outputs" definition apply to the glossary text (the glossary carries the first, three-check "Verify outputs" definition only), not to inline text, if both edits are accepted.

## Prioritized Findings & AI Suggestions

### Blockers

### [Issue 1] [design_critic-5-1] - Severity: Blocker
*   **Affected Scope:** §10.5 step 4 (L374), §10.6 C2 (L381)
*   **Discrepancy Description:** C2 grep pattern has doubled backslashes (`'\\.\\./\\.\\./reference/...'`) so in ERE it requires literal backslashes and can never match `../../reference/...`; verified by running the literal loop against the real wrappers: zero output, vacuous pass. With corrected single-backslash pattern it flags two MISSING lines: `../../reference/elephant-goldfish-model/agents/` and `.../resources/document_standards/` — both existing directories; C2 uses `test -f` which fails on directories, while C1 uses `test -e`.
*   **Rationale:** C2 is the check that wrapper references resolve; as printed it can never fail, so a dangling wrapper reference passes silently — and the two directory references it should catch are exactly the ones `test -f` mishandles.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid on every point, byte-verified: `od -c` on L381 proves the doubled backslashes and backslash-quotes in the file; the single-backslash form matches; `test -f` is false on directories while `test -e` is true; the real adapted files contain the bare directory references exactly 4× / 2× as stated. Shared edit R5-E (with Issues 3, 45).
*   ***Proposed Edit:***
    *   Location: §10.5 step 4 (L374); §10.6 C2 (L381) (shared edit R5-E).
    *   Change: Apply R5-E part (1).

### [Issue 2] [design_critic-5-2] - Severity: Blocker
*   **Affected Scope:** §10.2 (L336) vs D4 (L183–191), §11.3 (L422)
*   **Discrepancy Description:** §10.2 claims C2's resolve loop "runs as a step in the vendor-integrity CI job on every PR" and repo-side drift window is "zero"; D4's literal tenth vendor-integrity block has only sha256sum -c, comm unlisted-files check, symlink check — no C2 step; §11.3's ci.yml change adds only that block; live ci.yml egm block corroborates (exactly those three commands).
*   **Rationale:** The "zero drift on the repo side" claim rests on a CI step that is not in the specified CI change, so the claim is unfounded as specified.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Per the task's one-position rule for this cluster, the fix ADDS the C2 step to the CI block (the doc's round-4 design intent) rather than retreating the §10.2 claim. Shared edit R5-A (with Issues 21, 35, 39).
*   ***Proposed Edit:***
    *   Location: D4 tenth vendor-integrity block (L183–191); §11.3 (L422) (shared edit R5-A).
    *   Change: Apply R5-A.

### [Issue 3] [implementation_readiness-5-1] - Severity: Blocker
*   **Affected Scope:** §10.5 step 4 (L374), §10.6 C1 (L380), C2 (L381)
*   **Discrepancy Description:** Literal commands carry stray backslash-escapes and cannot run as written; C2 is vacuously passing. File literally contains `\"$tmp\"`, `\"$f\"`, `\"<bundle>/$p\"`, `\"reference/...\"`, and C2 grep pattern `'\\.\\./\\.\\./reference/[A-Za-z0-9_./-]+'` (four double-backslash pairs). Empirical tests: `grep -q . \"$f\"` → `grep: "/etc/hostname": No such file or directory`, exit 2; `echo \"$tmp\"/` → `"hello"/` (literal quotes in path); double-backslash grep pattern on `../../reference/elephant-goldfish-model/agents/design_critic.md` → no match, exit 1; single-backslash form → matches. Consequences: step-4 cp targets a directory whose name contains literal quotes (fails); C1 loop's grep fails on all 7 files and `test -e \"<bundle>/$p\"` is false for every path, so every reference is falsely reported MISSING; C1 routing-line assertions additionally use `$f` outside any loop (unbound). C2's pattern matches nothing, so its while-read loop never executes and check always reports "no MISSING lines" — a false pass. The two defects mask each other. Not a re-raise of r4 Issues 22/23/27: the E-M/E-N logic fixes are present; the defect is new transcription-level breakage in the literal commands as printed.
*   **Rationale:** A normative verification step whose literal commands cannot run as written, with a vacuously passing check masking real breakage.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid in its core (the C2 corruption) but two sub-claims are wrong — see the verification notes. `od -c` proves: the C1 main loop is byte-clean (plain `"$f"`, plain `"<bundle>/$p"`, single-backslash `sed 's/\.$//'`), so its grep does not fail and no reference is falsely reported MISSING; the §10.5 step-4 `cp`/`diff` commands are byte-clean, so no cp target contains literal quotes; the C1 assertions' patterns are correct single-backslash ERE with plain quotes. What is actually broken: the two C2 loops (doubled backslashes, backslash-quotes, `test -f`), and the C1 assertions' unbound `$f`. R5-E fixes only what is actually broken and does not "fix" the clean commands. Shared edit R5-E (with Issues 1, 45).
*   ***Proposed Edit:***
    *   Location: §10.5 step 4 (L374); §10.6 C1 (L380), C2 (L381) (shared edit R5-E).
    *   Change: Apply R5-E.

### [Issue 4] [implementation_readiness-5-2] - Severity: Blocker
*   **Affected Scope:** §10.5 step 4 (L374)
*   **Discrepancy Description:** Sync-check diff loop is unexecutable from either working directory. "then compare per skill from the repo root (`for s in egm-*/; do diff -r \"$tmp/$s\" \"skills/$s\" || exit 1; done`)". Preceding command did `cd ~/workspace/custom-skills`, and no cd to repo root is ever given; repo root's local path is never named. From repo root, `egm-*/` matches nothing (dirs live under skills/egm-*/), glob stays literal, diff errors. From ~/workspace/custom-skills, `skills/$s` does not exist, diff errors. Further: `$tmp` was assigned in the cp command, lost if implementer runs step's commands as separate invocations (doc never says to run step 4 as one compound command); and the sed for the SKILL.md copies names no file operand.
*   **Rationale:** The sync gate's literal procedure errors from every working directory the doc puts the implementer in.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Reproduced in sandbox: from a repo-root-shaped tree the `egm-*/` glob stays literal and diff exits 2; from `custom-skills`, `skills/$s` does not exist. The fix is one compound command with an explicit cd to the named repo root, a sed with its file operand, and a loop over the temp dir's own subdirectories — run verbatim in sandbox, PASS. Shared edit R5-F (with Issue 6).
*   ***Proposed Edit:***
    *   Location: §10.5 step 4 (L374) (shared edit R5-F).
    *   Change: Apply R5-F.

### Majors

### [Issue 5] [design_critic-5-3] - Severity: Major
*   **Affected Scope:** §5 (L76) vs §11 (L408)
*   **Discrepancy Description:** L76 still reads "Waiting for upstream issue #252 to close instead of the D3 routing line" — bare, no link — while L408 asserts "No bare 'Issue N' references remain in this document". Round-4 E-U fix linked the other instances but missed this one (grep confirms L76 is the only remaining bare instance). This is the flagged round-4 wart #2.
*   **Rationale:** The doc asserts a citation rule it violates on one line; the rule's own assertion is false until L76 is linked.
*   **AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; verified by grep — L76 is the only remaining bare instance. Shared edit R5-L.
*   ***Proposed Edit:***
    *   Location: §5 (L76) (shared edit R5-L).
    *   Change: Apply R5-L.

### [Issue 6] [design_critic-5-4] - Severity: Major
*   **Affected Scope:** §10.5 step 4 (L374)
*   **Discrepancy Description:** Sync-check diff loop cannot execute from either plausible working directory. From repo root, `egm-*/` matches nothing (skill dirs live under skills/), glob stays literal, diff errors. Preceding command did `cd ~/workspace/custom-skills`, where `skills/$s` does not exist, diff errors there too. No cd to repo root given.
*   **Rationale:** Same defect as Issue 4, stated from the design-critic angle; the loop as printed has no working directory from which it runs.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid — same defect as Issue 4. Shared edit R5-F (with Issue 4).
*   ***Proposed Edit:***
    *   Location: §10.5 step 4 (L374) (shared edit R5-F).
    *   Change: Apply R5-F.

### [Issue 7] [design_critic-5-5] - Severity: Major
*   **Affected Scope:** §14 decision 2 (L447), §10.5 step 3 (L373)
*   **Discrepancy Description:** Pilot target's "commit" refers to a repository that does not exist — `~/workspace/plans/` is not a git repo (`git -C plans rev-parse` fails, no .git in plans or ~/workspace). No commit SHA or HEAD to record, so step 3 cannot be satisfied and the pilot target is not version-identified.
*   **Rationale:** A verification step that requires a commit SHA from a non-repository cannot be satisfied as written.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; `git rev-parse` failure verified for both `~/workspace/plans/` and `~/workspace`. The fix defines target identity without git (content hash + date in the pilot log). Shared edit R5-M.
*   ***Proposed Edit:***
    *   Location: §10.5 step 3 (L373); §14 decision 2 (L447) (shared edit R5-M).
    *   Change: Apply R5-M.

### [Issue 8] [design_critic-5-6] - Severity: Major
*   **Affected Scope:** §8 D3 (L171)
*   **Discrepancy Description:** The seven "Literal commands" contain unbound `<bundle>` placeholder; run literally, first command writes literal `<bundle>/agents/` into the adapted file. Undetectable by C1: C1 greps for substring `agents/...` (matches inside literal `<bundle>/agents/...`) then tests the real bundle path, which exists, so C1 passes on a corrupted file.
*   **Rationale:** A literal command that corrupts the file it adapts, with the corruption invisible to the doc's own verification check.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The D3 sed commands as printed are otherwise byte-clean (single `\/` escapes, verified by `od -c`) — the defect is purely the unbound placeholder. The fix binds `bundle` first and rewrites the commands to use it (all seven rows run verbatim in sandbox, idempotent on re-run), plus a post-check that no literal `<bundle>` remains, which is the only guard against this failure mode. Shared edit R5-N.
*   ***Proposed Edit:***
    *   Location: §8 D3 (L171) (shared edit R5-N).
    *   Change: Apply R5-N.

### [Issue 9] [design_critic-5-7] - Severity: Major
*   **Affected Scope:** §6 (L93), §10.4 (L367), §14 decision 6 (L451)
*   **Discrepancy Description:** Phase 0 pilot still runs with no token ceiling; E-H gates only Phase 1. Grep for "token" finds no numeric cap anywhere; only cost numbers are 25 spawns and 12.5 reviewer-hours. The pilot generates the cost evidence for the decision-5 value ruling while its own cost is uncapped. Flagged explicitly as r4 Issue 55's surviving core (fix-verification failure), not a silent re-raise.
*   **Rationale:** The experiment that generates the cost evidence runs uncapped — the cap is derived from the very spend it is supposed to bound.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; verified — no numeric token cap exists anywhere in the document. The fix addresses the pilot (Phase 0) explicitly, as the task requires: an interim pilot cap set by owner ruling before the next pilot run, plus honest present-tense wording in §10.4. No token number is invented; the number is the owner's ruling. Shared edit R5-B (with Issues 22, 40).
*   ***Proposed Edit:***
    *   Location: §6 (L93); §10.4 (L367); §14 decision 6 (L451) (shared edit R5-B).
    *   Change: Apply R5-B.

### [Issue 10] [design_critic-5-8] - Severity: Major
*   **Affected Scope:** §10.4 (L367)
*   **Discrepancy Description:** Per-reviewer token cap as "size bound" has no defined overflow behavior — if a target document alone exceeds the cap, doc defines no behavior (refuse, truncate, split, breach?).
*   **Rationale:** A bound with no defined behaviour at its boundary is not a bound; the first oversized target forces an ad-hoc decision.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; distinct from the cap's existence (Issue 9) — this is the overflow sub-issue. The fix specifies refuse-and-record-not-run (never truncate, never breach). Shared edit R5-C.
*   ***Proposed Edit:***
    *   Location: §10.4 (L367) (shared edit R5-C).
    *   Change: Apply R5-C.

### [Issue 11] [design_critic-5-9] - Severity: Major
*   **Affected Scope:** §9.5 step 3 (L308), §9.1 (L240), §9.4
*   **Discrepancy Description:** E2E gate's run command exists for only one of three VM shapes. Step 3 prescribes `muse exec --prompt /tmp/egm-e2e-<shape>/prompt.md` for shapes muse-cli, other-harness, headless; `muse exec` exists only for muse-cli; other-harness has no muse exec, headless has no harness CLI at all (yet §9.1 prerequisites demand "one supported harness CLI", which headless cannot satisfy). "Installed cache only" = "plugin installed per §9.2", undefined for headless Path 2. Step-1 fallback (hand-exercised fixture run if muse exec absent) does not save headless (no harness to hand-exercise).
*   **Rationale:** A gate whose run command exists for one of three shapes cannot gate the other two; the headless shape has no verification gate at all as written.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix gives each shape its gate: muse-cli keeps the `muse exec` run; other-harness uses its own headless run command (or has no gate and does not pass); headless is verified by the §10.6 checks alone, with "installed cache" defined for Path 2. Shared edit R5-O.
*   ***Proposed Edit:***
    *   Location: §9.5 step 3 (L308) (shared edit R5-O).
    *   Change: Apply R5-O.

### [Issue 12] [design_critic-5-10] - Severity: Major
*   **Affected Scope:** §9.5 step 2 (L307), §10.6 C3 (L382–385), §9.1 (L240)
*   **Discrepancy Description:** Venv installed but never invoked by any command that needs it. §9.1 installs pytest==9.2.0 and PyYAML==6.0.3 only into /tmp/egm-venv, no activation step anywhere. §9.5 step 2 runs bare `pytest tests/unit` (not on PATH on fresh VM); C3 literal loop runs bare `python3 -c "import yaml..."` (system python has no yaml) though prose above names /tmp/egm-venv/bin/python3. Both fail on first attempt on fresh VM.
*   **Rationale:** The only pytest and the only PyYAML on the fresh VM live in the venv, and no normative command uses the venv — both commands fail on first attempt.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix qualifies both commands with the venv binaries and adds the Environment B pre-check. (Note: on this VM the system python3 does have yaml, so the failure is fresh-VM-specific — exactly the environment the doc specifies.) Shared edit R5-G (with Issues 26, 27).
*   ***Proposed Edit:***
    *   Location: §9.5 step 2 (L307); §10.6 C3 (L382–385) (shared edit R5-G).
    *   Change: Apply R5-G parts (1)–(2).

### [Issue 13] [design_critic-5-11] - Severity: Major
*   **Affected Scope:** §10.3.4 (L363), §4 (L56), §10.5 step 3 (L373)
*   **Discrepancy Description:** Mid-round resume unimplementable — no per-reviewer report artifact exists. No path/filename/location specified for an individual reviewer's report ("each reviewer files a report", L56; "file one report", L363). Resume rule (re-read filed reports, re-dispatch only reviewers with no filed report) cannot work: if Elephant dies before consolidation, no review report exists and nothing on disk identifies which reviewers filed. Same gap breaks §10.5 step 3 severity-change audit ("verifies each recorded severity change against the filed report").
*   **Rationale:** The resume rule and the severity-change audit both presuppose per-reviewer artifacts the doc never defines.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Round-4 E-J specified the consolidated review-report path but not per-reviewer report paths — this is the remaining half. The fix specifies `~/workspace/plans/<date>-<topic>-<reviewer>-r<n>.md` and makes the resume rule read them. Shared edit R5-P.
*   ***Proposed Edit:***
    *   Location: §4 (L56); §10.3.4 (L363) (shared edit R5-P).
    *   Change: Apply R5-P.

### [Issue 14] [design_critic-5-12] - Severity: Major
*   **Affected Scope:** §12 (L435)
*   **Discrepancy Description:** URL-fetch audit cannot perform two of its three checks. Requires "every saved file ≤1 MB, every cited URL uses https, every saved file is HTML". (a) No artifact maps saved files to source URLs, and brief template (L363) does not require reviewers to record source URL per saved file, so https check is unperformable for saved files whose URL is not cited in the report. (b) "is HTML" has no defined test (extension? `file` output? Content-Type?).
*   **Rationale:** An enforcement audit that cannot perform two of its three checks is not enforcement.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix requires URL-per-file recording in the brief template and names both tests (`find -size +1M` must print nothing; `file -b --mime-type` must print `text/html`) — both run verbatim in sandbox. Shared edit R5-Q.
*   ***Proposed Edit:***
    *   Location: §10.3.4 brief template (L363); §12 (L435) (shared edit R5-Q).
    *   Change: Apply R5-Q.

### [Issue 15] [design_critic-5-13] - Severity: Major
*   **Affected Scope:** §8 D5 (L213)
*   **Discrepancy Description:** Content review enumerates 23 non-markdown files; bundle has 25. Listed: 7 openai.yaml + 7 test_scenarios.yaml + 1 worker-return.schema.json + 7 icon.svg + 1 readme-header.svg = 23; omitted: LICENSE and plugin.json. plugin.json is the harness-read plugin manifest — highest-trust file, declaring what the harness loads.
*   **Rationale:** The safety control's enumeration omits the highest-trust file in the bundle; an unreviewed manifest is unreviewed by construction.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the 25-file total is verified against the local bundle (`find ... ! -name '*.md'` = 25). Round 4's E-P count of 23 was wrong. Shared edit R5-R.
*   ***Proposed Edit:***
    *   Location: §8 D5 (L213) (shared edit R5-R).
    *   Change: Apply R5-R.

### [Issue 16] [design_critic-5-14] - Severity: Major
*   **Affected Scope:** §10.4 (L367)
*   **Discrepancy Description:** Churn stop reuses a cap-specific literal question asserting a false precondition. "on cap or churn the driver stops and asks the owner one question, literally: 'The loop hit its cap (5 rounds) with unsettled findings — how do you want to proceed?'" — churn fires on "the first occurrence", which can be round 2; options ("continue past the cap") presuppose the cap.
*   **Rationale:** A driver stopping on churn at round 2 would ask a question falsely asserting the 5-round cap was hit, and offer "continue past the cap" when there is no cap to continue past.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix gives churn its own literal question text stating churn, not the cap. Shared edit R5-H (with Issue 36).
*   ***Proposed Edit:***
    *   Location: §10.4 (L367) (shared edit R5-H).
    *   Change: Apply R5-H.

### [Issue 17] [design_critic-5-15] - Severity: Major
*   **Affected Scope:** §8 D6 (L220)
*   **Discrepancy Description:** Disposable target copy has no executable procedure. E-G fix: "Before dispatch, copy the target document to a disposable per-round copy (/tmp/egm-review-<run>/target.md, byte-identical...) and brief reviewers with the copy's path" — no literal cp command, no mkdir -p for the per-round directory (does not exist). Under the same literal-executability bar round 4 applied to the sync check, the central containment control is prose, not a procedure.
*   **Rationale:** The doc's central containment control cannot be executed as written — the directory it copies into does not exist.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix gives the literal `mkdir -p ... && cp ...` command (run verbatim in sandbox, byte-identical copy verified). Shared edit R5-S.
*   ***Proposed Edit:***
    *   Location: §8 D6 (L220) (shared edit R5-S).
    *   Change: Apply R5-S.

### [Issue 18] [design_critic-5-16] - Severity: Major
*   **Affected Scope:** §3 (L42)
*   **Discrepancy Description:** Demand baseline has no measurement method, window, or corpus. "the Phase 0 pilot log records design docs produced per month as the demand baseline for the Phase 1 value judgment (§14 decision 5)". No method: which corpus (22 top-level docs/? 37 recursive? dated plans under ~/workspace/plans/ too?), what window, counted how (file dates? git log? — and per 5-5, ~/workspace/plans/ is not versioned, so git-based counting cannot cover it).
*   **Rationale:** The demand baseline is the evidence for the Phase 1 value judgment; without a method it cannot be produced or audited.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix specifies corpus (22 top-level / 37 recursive AEP docs + dated plans), window (one calendar month), and counting method (filename dates for plans, first-commit dates via `git log --diff-filter=A` for AEP docs — the git command verified in the AEP repo). Shared edit R5-T.
*   ***Proposed Edit:***
    *   Location: §3 (L42) (shared edit R5-T).
    *   Change: Apply R5-T.

### [Issue 19] [structural-5-1] - Severity: Major
*   **Affected Scope:** §10.3 Roles table, L342–347
*   **Discrepancy Description:** Normative procedure embedded inside table cells. Elephant row (L344, 670 chars) contains role definition plus two distinct normative rules (consolidation procedure; severity rule: Elephant must not change a finding's severity without recording change in report, downgrade with no recorded reason is a defect). Synthesizer row (L347, 425 chars) embeds design-choice aside (direct dispatch by design, depth-2 spawning works). Contrast Goldfish row (198 chars) and Driver row (255 chars), single-sentence role definitions. Consolidation procedure also stated in body text at §10.3.4 (L363) — rule now lives in two places. New instance in a different table from r4 Issue 18 (D3 mapping table, fixed); not a re-raise.
*   **Rationale:** Normative rules in table cells duplicate body text and break the table's role-definition function; the severity rule now lives in two places and can drift.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the two-place duplication is verified (L344 cell vs L363 body). The fix moves both rules into §10.3.4 body text and the design aside into §10.3 body text, leaving one-sentence rows. Shared edit R5-Z.
*   ***Proposed Edit:***
    *   Location: §10.3 Roles table (L342–347); §10.3.4 (L363) (shared edit R5-Z).
    *   Change: Apply R5-Z.

### [Issue 20] [structural-5-2] - Severity: Major
*   **Affected Scope:** §5, L84
*   **Discrepancy Description:** "Delta table" is prose, not a table, yet cited as a table from two places. L84 is one 854-char paragraph with six pairwise comparisons (roundtable_review vs EGM). Doc has six real Markdown tables elsewhere (§4 L48–54, §7 L110–118, D3 L159–167, §9.4 L294–299, §10.3 L342–347, §11 L398–403). Two cross-references point at it as a table: L67 ("the delta table (§5, roundtable_review vs EGM) shows...") and §10.3.3 L359 ("See the roundtable_review vs EGM delta table in §5.").
*   **Rationale:** A thing cited as a table from two places should be a table; as prose it cannot be scanned as the comparison it is cited for.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix reformats L84 as a real three-column table with six rows, keeping the two trailing sentences as body text; no cross-reference changes needed. Shared edit R5-AA.
*   ***Proposed Edit:***
    *   Location: §5 (L84) (shared edit R5-AA).
    *   Change: Apply R5-AA.

### [Issue 21] [implementation_readiness-5-3] - Severity: Major
*   **Affected Scope:** §10.2 (L336) vs D4 (L186–191) and §11.3 (L422)
*   **Discrepancy Description:** C2 claimed to run in CI, but no CI step implements it. §10.2: "repo-side drift (wrappers vs bundle) is covered by check C2, whose resolve loop runs as a step in the vendor-integrity CI job on every PR" and "Maximum tolerable drift window: … zero on the repo side (C2 runs on every PR)." D4's literal tenth vendor-integrity run: block (L186–191) has only sha256sum -c, unlisted-files check, symlink check — no C2 loop. §11.3 (L422) defines ci.yml change as exactly that block.
*   **Rationale:** Same root cause as Issue 2: the specified CI change contains no C2 step, so the "zero drift" claim is unfounded as specified.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. One consistent position for the cluster (R5-A): add the C2 step to the CI block. Shared edit R5-A (with Issues 2, 35, 39).
*   ***Proposed Edit:***
    *   Location: D4 (L186–191); §11.3 (L422) (shared edit R5-A).
    *   Change: Apply R5-A.

### [Issue 22] [implementation_readiness-5-4] - Severity: Major
*   **Affected Scope:** §6 (L93), §10.4 (L367), §14 decision 6 (L451)
*   **Discrepancy Description:** Pilot itself has no token cap — the unclosed half of r4 Issue 55. R4 E-H fix gated Phase 1 on decision 6 ("Phase 1 does not start until decision 6 sets it"), but pilot (Phase 0) still has no token number anywhere: §6 gives only "interim budget 12.5 reviewer-hours per run; token budget set by §14 decision 6 from the pilot log's actuals", and decision 6 sets the budget "from the pilot log's elapsed-time and token records". The cap is therefore derived from the very spend it is supposed to bound — the experiment that generates the cost evidence runs uncapped. Explicitly flagged as the pilot half of r4 Issue 55, not a silent re-raise.
*   **Rationale:** The round-4 fix closed the Phase 1 half and left the pilot half open; the pilot is the run currently spending.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix addresses the pilot explicitly (interim pilot cap by owner ruling before the next pilot run) and rewords §10.4 to state the actual pilot envelope honestly. Shared edit R5-B (with Issues 9, 40).
*   ***Proposed Edit:***
    *   Location: §6 (L93); §10.4 (L367); §14 decision 6 (L451) (shared edit R5-B).
    *   Change: Apply R5-B.

### [Issue 23] [implementation_readiness-5-5] - Severity: Major
*   **Affected Scope:** D6 (L220)
*   **Discrepancy Description:** Snapshot after-diff exclusion rule has no procedure. "Re-run the same commands to -after files and diff each pair; any output names a modified path. The after-diff ignores files under ~/workspace/plans/ that did not exist at snapshot time (the round's own report and pilot-log entries); any modification or deletion of a pre-existing file under ~/workspace/plans/, or any change at the other three locations, fails the round." Plain diff of the two sha256sum lists reports added files as differences; no command or interpretation rule implements the exclusion (e.g. separating added lines from changed lines), the -after filenames are never specified, and scope location (3) ("each ~/workspace/custom-skills/egm-*/ dir" — seven dirs) is assigned a single <n> slot (1–4), leaving it ambiguous whether it is one snapshot file over the glob or seven. The pass/fail verdict of the plan's core safety control is left to the implementer to design.
*   **Rationale:** The core safety control's verdict cannot be produced as written — the exclusion rule has no procedure and the location-(3) snapshot form is ambiguous.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix names the `-after` files, gives the `comm`/`join` exclusion procedure (run verbatim in sandbox: added, removed, and changed paths distinguished correctly), states location (3) is one snapshot file over the glob, and fixes `rm` → `rm -rf` for directories. Shared edit R5-U (with Issues 46, 68).
*   ***Proposed Edit:***
    *   Location: §8 D6 (L220) (shared edit R5-U).
    *   Change: Apply R5-U.

### [Issue 24] [implementation_readiness-5-6] - Severity: Major
*   **Affected Scope:** §10.4 (L367), §10.3.4 (L363)
*   **Discrepancy Description:** 30-minute per-reviewer timeout has no enforcement mechanism. §10.4 sets "Timeout: 30 minutes per reviewer for the pilot" and §10.3.4 says "a reviewer that times out, fails, or returns no report is retried once, then recorded not run". No timeout parameter, watchdog, timer, or kill step is named anywhere, and subagent.spawn's timeout behaviour (if any) is never documented. Nothing defines how a timeout is detected or who enforces the 30 minutes.
*   **Rationale:** A bound with no enforcement mechanism and no detection rule cannot be enforced.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix names the mechanism honestly: `subagent.spawn` has no timeout parameter and no in-flight kill, so the timeout is enforced at acceptance via the driver's recorded dispatch wall-clock time. Shared edit R5-AE.
*   ***Proposed Edit:***
    *   Location: §10.4 (L367); §10.3.4 (L363) (shared edit R5-AE).
    *   Change: Apply R5-AE.

### [Issue 25] [implementation_readiness-5-7] - Severity: Major
*   **Affected Scope:** §9.1 (L240), §11 Phase 3
*   **Discrepancy Description:** Fresh-VM provisioning has no install procedure. §9.1 lists "git ≥ 2.43.0, python3 ≥ 3.12.3 …, and one supported harness CLI — Muse ≥ 1.4.14" as prerequisites. Only install command given is the venv/pip install for pytest/PyYAML; no install commands for git, python3, or any harness CLI, and no OS/distro or VM image is specified for the "general-purpose Linux VM". §11 Phase 3 provisioning says only "install prerequisites, clone upstream at the pinned SHA, install per the §9.2/§9.3 path" — "install prerequisites" is the entire provisioning instruction.
*   **Rationale:** Phase 3 cannot be executed on a fresh VM as written — there is no image and no install procedure for the prerequisites themselves.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix names the image (Ubuntu 24.04 cloud image — verified: it ships git 2.43.0 and python3 3.12.3, the §9.1 floors, and `python3-venv` 3.12.3 is the packaged version) and the provisioning source (distro packages for git/python3/python3-venv; harness CLI per vendor instructions). Shared edit R5-AF.
*   ***Proposed Edit:***
    *   Location: §9.1 (L240); §11 Phase 3 Scope (shared edit R5-AF).
    *   Change: Apply R5-AF.

### [Issue 26] [implementation_readiness-5-8] - Severity: Major
*   **Affected Scope:** §9.5 step 2 (L307)
*   **Discrepancy Description:** `pytest tests/unit` is unbound in binary, location, and input. (a) Bare pytest is unbound — the only pytest installed per §9.1 is /tmp/egm-venv/bin/pytest; no activation or path given. (b) §9.2's clone (L248, `git clone https://github.com/google/elephant-goldfish-model.git`) has no destination and no working directory, so ./elephant-goldfish-model/ is location-unbound; §9.3 (L290) clones to a different path (<install-root>/egm-checkout), giving a Path 2 implementer two candidate checkouts. (c) `tests/unit` existence at the pinned SHA is never established — §7's inventory and §11.3's 90-file inventory contain no tests/ at all, and top-level tests/ is listed as not vendored.
*   **Rationale:** A verification step unbound in binary, location, and input cannot run on first attempt.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid on (a) and (b); corrected on (c) — see the verification notes. `tests/unit` existence at the pin IS established upstream (TESTING.md at `e9e1f06a` documents `pytest tests/unit`, L113) and the §9.2 clone is a full checkout including `tests/`; the gap is the missing citation, not an unknown path. R5-G binds the binary, names the checkout path and working directory, states the two clone paths are one checkout under two names, and asserts `tests/unit` with the citation. Shared edit R5-G (with Issues 12, 27).
*   ***Proposed Edit:***
    *   Location: §9.5 step 2 (L307); §9.2 (L248) (shared edit R5-G parts (1), (3)).
    *   Change: Apply R5-G parts (1), (3).

### [Issue 27] [implementation_readiness-5-9] - Severity: Major
*   **Affected Scope:** §10.6 C3 (L385), C6, §9.1 (L240)
*   **Discrepancy Description:** Skill.yaml check's interpreter is unbound. C3 loop uses bare `python3 -c "import yaml,sys; ..."` (L385; byte-checked clean of escaping defects), while the only PyYAML on the fresh VM is installed into the venv — doc names /tmp/egm-venv/bin/python3 only in a parenthetical ("run with a python3 that has PyYAML installed; fresh VM: the §9.1 venv, /tmp/egm-venv/bin/python3") and the literal command does not use it. System python3 on a stock fresh VM has no yaml module, so the literal loop fails with ModuleNotFoundError. Environment B has no python3-with-PyYAML identified or installed at all. C6 inherits the procedure ("same as C3").
*   **Rationale:** The literal C3 command fails on a fresh VM because its interpreter is the one Python that lacks the module it imports.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix uses `/tmp/egm-venv/bin/python3` in the loop on the fresh VM and adds the Environment B pre-check (`python3 -c "import yaml"` must exit 0, interpreter path recorded). The C3 loop itself is byte-clean (verified by `od -c`); only the interpreter binding is missing. Shared edit R5-G (with Issues 12, 26).
*   ***Proposed Edit:***
    *   Location: §10.6 C3 (L382–385); C6 (shared edit R5-G part (2)).
    *   Change: Apply R5-G part (2).

### [Issue 28] [comprehension-5-1] - Severity: Major
*   **Affected Scope:** §8 D6, L220
*   **Discrepancy Description:** "Verify outputs" is defined twice, contradictorily, in the same paragraph. Same paragraph (single line L220) contains both "'Verify outputs' means the snapshot diff plus the three checks in §10.3.1 (line-existence, standard-name, memory-prohibition), nothing else" and later "'Verify outputs' means these two checks, nothing else." Second definition's "these two checks" has no clear antecedent — immediately preceding sentence names only the line-existence check. New evidence from round-4 E-C fix, which rewrote the first definition but left the second; not a re-raise of r4 Issue 19/39 (old single definition).
*   **Rationale:** The document's core verification term has two contradictory definitions 200 words apart in one paragraph.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; both sentences verified in L220, and "two checks" occurs nowhere else. The fix deletes the second (stale) definition and lets the first stand alone. Shared edit R5-D (with Issue 43).
*   ***Proposed Edit:***
    *   Location: §8 D6 (L220) (shared edit R5-D).
    *   Change: Apply R5-D.

### [Issue 29] [comprehension-5-2] - Severity: Major
*   **Affected Scope:** §1, L20
*   **Discrepancy Description:** Owner definition points at "§7's approval gates," but §7 defines no gates. L20: "'Owner' is the human user who owns the AEP repo and this environment — the same 'human' in §7's approval gates". §7 (L101–104) only mentions gates in passing ("the human (explicit approval gates before anything is built)") and defines none. Actual gates (readiness gate, section-approval gate) are defined in §10.3.2 (L352–356).
*   **Rationale:** A definition that points at a section that does not define what it points to misdirects the reader.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; verified — §7 defines no gates, §10.3.2 defines both. Shared edit R5-AH.
*   ***Proposed Edit:***
    *   Location: §1 (L20) (shared edit R5-AH).
    *   Change: Apply R5-AH.

### [Issue 30] [comprehension-5-3] - Severity: Major
*   **Affected Scope:** §2, L30
*   **Discrepancy Description:** "merged with conversation resolution" is undefined anywhere in the document. L30: "AEP PR — CI green including vendor-integrity + skills-freshness, merged with conversation resolution." Phrase appears nowhere else, never defined — not what a "conversation" is, not what counts as resolved, not who resolves it. Stated as a merge criterion.
*   **Rationale:** A merge criterion the reader cannot interpret is not a criterion.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid — the phrase is undefined and appears nowhere else. The fix defines it inline (every PR review thread resolved, per the repo's branch protection). Shared edit R5-AI.
*   ***Proposed Edit:***
    *   Location: §2 (L30) (shared edit R5-AI).
    *   Change: Apply R5-AI.

### [Issue 31] [comprehension-5-4] - Severity: Major
*   **Affected Scope:** §8 D4, L195–197
*   **Discrepancy Description:** "sync from live" and "the manifest" are used before either is defined. L197: "the gate proves the repo skills/ tree equals the manifest generated from the repo tree after the last sync from live". Term "live" is defined only later, in §10.2 (L336), and that definition is explicitly scoped — "('live' in this section means the local ~/workspace/custom-skills/ tree)" — so it does not cover this D4 use. "The manifest" is never defined at all; file .github/skills-manifest.sha256 is first named only in §11.3 (L422), with no explanation of what the manifest contains. Different occurrence from r4 Issue 42 (§10.2 use, now fixed), not a re-raise.
*   **Rationale:** A first use that relies on a later, narrowly scoped definition and an undefined file name cannot be followed by a fresh reader.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix names the manifest file at first use and defines "live" where D4 uses it. Shared edit R5-AJ.
*   ***Proposed Edit:***
    *   Location: §8 D4 (L195–197) (shared edit R5-AJ).
    *   Change: Apply R5-AJ.

### [Issue 32] [comprehension-5-5] - Severity: Major
*   **Affected Scope:** §8 D6, L220, and §12, L438
*   **Discrepancy Description:** "NeuroStrata MCP connector," "NeuroStrata store," and "AGENTS.md" are undefined in the target document. L220: "'Configured memory services' means the NeuroStrata MCP connector and any other configured memory; 'project instructions' means AGENTS.md and repo instruction files." L220 again: "no snapshot is taken of the NeuroStrata store". Target doc never defines NeuroStrata (only mention is §2, L38, pointing at companion doc), never expands/defines "MCP," never says what the connector is or where it lives, never explains what an AGENTS.md file is or whose it is. These terms carry the central safety prohibition.
*   **Rationale:** The terms carrying the central safety prohibition are undefined in the document that states the prohibition — a human reader cannot assess what is prohibited.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid, and not a "context only to satisfy a reviewer" case: a human reader needs these definitions to understand the D6 prohibition. The fix adds one defining sentence in D6. Shared edit R5-AK.
*   ***Proposed Edit:***
    *   Location: §8 D6 (L220) (shared edit R5-AK).
    *   Change: Apply R5-AK.

### [Issue 33] [comprehension-5-6] - Severity: Major
*   **Affected Scope:** §9.3, L288, vs §8 D3, L169
*   **Discrepancy Description:** Three mutually inconsistent literal forms for the Environment B bundle path. L288: "Example path strings a Path 2 skill contains: $HOME/egm/agents/design_critic.md; in Environment B the same string reads /home/hatch/workspace/egm/agents/design_critic.md." But §9.3 also says <install-root> defaults to $HOME (example /home/<user>) while Environment B sets <install-root> = ~/workspace — so $HOME/egm/... and ~/workspace/egm/... are different directories unless $HOME is /home/hatch/workspace. And D3 (L169) states the opposite of the L288 example: "Environment B uses the ~ form ~/workspace/egm/... in adapted files … the expanded form /home/hatch/workspace/egm/... never appears in a pilot adapted file." A naive reader cannot determine the literal string an Environment B skill file contains: $HOME/egm/..., ~/workspace/egm/..., or /home/hatch/workspace/egm/....
*   **Rationale:** Three mutually inconsistent literal forms for the same string leave the implementer unable to determine what an adapted file contains.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix rewrites L288 to the single consistent form (the `~` form, per D3) and removes the generic `skills/` layout entirely, so `<install-root>` has one binding. Shared edit R5-AL (with Issue 44).
*   ***Proposed Edit:***
    *   Location: §9.3 (L288); §9.3 bullets + install step 3 (shared edit R5-AL).
    *   Change: Apply R5-AL.

### [Issue 34] [comprehension-5-7] - Severity: Major
*   **Affected Scope:** §9.5 step 3, L308
*   **Discrepancy Description:** "a line-count design" is undefined; the fixture's subject is never explained. L308: "fixture design muse-wonder-1.0 (the upstream fixture name for the brainstorm → draft → review sequence; a line-count design, per the upstream Muse row in TESTING.md)" and the specified prompt: "'Run the EGM brainstorm → draft → review sequence (fixture muse-wonder-1.0, a line-count design) … brainstorm the design, draft it, then run an uninterrupted review.'" Nothing says what a "line-count design" is — a design for a line-counting tool? a design document measured in lines? — or what artifact the brainstorm/draft stages are supposed to produce beyond the filenames.
*   **Rationale:** The E2E gate's fixture subject is unexplained; the reader cannot tell what is being designed.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. TESTING.md at the pin (Muse row) calls it a "line-count design" without elaborating, so the doc states the subject plainly: the fixture designs a line-counting tool, and the draft stage produces a design document for it. Shared edit R5-AM.
*   ***Proposed Edit:***
    *   Location: §9.5 step 3 (L308) (shared edit R5-AM).
    *   Change: Apply R5-AM.

### [Issue 35] [comprehension-5-8] - Severity: Major
*   **Affected Scope:** §10.2, L336
*   **Discrepancy Description:** C2's resolve loop is claimed to run in CI, but no such CI step exists in the document. L336: "repo-side drift (wrappers vs bundle) is covered by check C2, whose resolve loop runs as a step in the vendor-integrity CI job on every PR". D4 gives the literal tenth vendor-integrity run: block (L183–190): sha256sum -c, unlisted-files check, broken-symlink check — no C2 resolve loop. No other section defines a CI step that runs C2; §10.5 step 4 defines C2's resolve loop only as a manual procedure.
*   **Rationale:** Same root cause as Issues 2 and 21: the claim and the specified CI block disagree.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. One consistent position for the cluster (R5-A): add the C2 step to the CI block. Shared edit R5-A (with Issues 2, 21, 39).
*   ***Proposed Edit:***
    *   Location: D4 (L183–191); §11.3 (L422) (shared edit R5-A).
    *   Change: Apply R5-A.

### [Issue 36] [comprehension-5-9] - Severity: Major
*   **Affected Scope:** §10.4, L367
*   **Discrepancy Description:** The literal cap/churn question asserts the cap was hit, but it is prescribed for churn too. L367: "on cap or churn the driver stops and asks the owner one question, literally: 'The loop hit its cap (5 rounds) with unsettled findings — how do you want to proceed?' (options: accept and proceed / continue past the cap / return to drafting)." Churn can trigger at any round (first occurrence), so a driver stopping on churn at round 2 would ask a question falsely asserting the 5-round cap was hit, and offer "continue past the cap" when there is no cap to continue past.
*   **Rationale:** Same defect as Issue 16: one literal question text cannot serve two triggers with different preconditions.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix gives churn its own literal question. Shared edit R5-H (with Issue 16).
*   ***Proposed Edit:***
    *   Location: §10.4 (L367) (shared edit R5-H).
    *   Change: Apply R5-H.

### [Issue 37] [comprehension-5-10] - Severity: Major
*   **Affected Scope:** §10.3.3, L359, and §2, L37
*   **Discrepancy Description:** "Ralph" and "the standing loop rule" are undefined. L359: "The Ralph per-iteration verifier (~/workspace/ralph/ loop — an independent, non-blocking verification subagent at the end of every iteration, per the standing loop rule) checks implementation against acceptance criteria". The gloss explains what the verifier does, but never says what Ralph is (a loop system? a tool? a skill?), and "the standing loop rule" is cited as authority with no location — it appears nowhere in the document or in GoldfishContext (the README mentions only "the Ralph autonomous loop" in passing). Same undefined "Ralph verifier" is a non-goal boundary in §2 (L37).
*   **Rationale:** An authority cited with no location and a system named but never defined cannot be checked by the reader.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix defines Ralph (the autonomous loop system in `~/workspace/ralph/`) and cites the rule's location — verified: `~/workspace/custom-skills/ralph_loop/SKILL.md` L57, "Independent verification (standing rule, 2026-10-17)". Shared edit R5-AN.
*   ***Proposed Edit:***
    *   Location: §10.3.3 (L359); §2 (L37) (shared edit R5-AN).
    *   Change: Apply R5-AN.

### [Issue 38] [zoom_out-5-1] - Severity: Major
*   **Affected Scope:** §10.5 step 3 (L373)
*   **Discrepancy Description:** A whole fresh-context agent to do a deterministic diff the Elephant can do itself — and it is uncounted in the cost bound. "An independent review subagent audits the consolidation: it verifies each recorded severity change against the filed report (original severity matches, reason present) and that no severity change went unrecorded." Deterministic comparison of two artifacts the Elephant itself holds — the filed reviewer reports and the consolidated report it just wrote. Elephant can perform it in its own consolidation pass at zero spawns; instead the design spends a fresh-context subagent per pilot (frequency unstated — once per pilot, or once per round, when severity changes happen per round's consolidation). A fresh-context agent adds non-determinism to a deterministic check, and it is invisible to the cost envelope: §6 (L93, L97) and §10.4 (L367) all state the bound as "at most 25 spawns per run" / "max 25 per run", counting reviewer spawns only — true maximum is 26 (once per pilot) or 30 (once per round). Note: §10.3 dropped the synthesizer in Environment B for simplicity ("flat dispatch keeps attribution simple"), while the round-4 fix (E-C) added an agent back for bookkeeping. New, not a re-raise of r4 Issue 54: Issue 54 complained the subagent duplicated checks (a)/(b); E-C fixed that duplication but preserved the agent by re-scoping it to a job that needs no agent at all.
*   **Rationale:** A deterministic check done by a fresh-context agent costs a spawn, adds non-determinism, and is invisible to the stated cost bound.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix deletes the audit subagent, folds the severity-change audit into the Elephant's consolidation pass, and states the spawn bound exactly (25 reviewer spawns, no other spawn made by the loop). Shared edit R5-AV.
*   ***Proposed Edit:***
    *   Location: §10.5 step 3 (L373); §6 (L93) (shared edit R5-AV).
    *   Change: Apply R5-AV.

### [Issue 39] [zoom_out-5-2] - Severity: Major
*   **Affected Scope:** §10.2 (L336)
*   **Discrepancy Description:** "Zero drift on the repo side" rests on a CI step that is not in the specified CI change. §10.2: "repo-side drift (wrappers vs bundle) is covered by check C2, whose resolve loop runs as a step in the vendor-integrity CI job on every PR (it reads only the repo tree). … Maximum tolerable drift window: one sync interval on the local side; zero on the repo side (C2 runs on every PR)." But the CI change the doc actually specifies contains no C2 step: D4's literal tenth vendor-integrity block (L183–190) is only sha256sum -c, the comm -23 unlisted-files check, and the broken-symlink loop — and §11.3 (L422) specifies the ci.yml change as exactly "tenth vendor-integrity run: block — literal block in D4." C2 exists only as a manual sync-time procedure (§10.5 step 4, L374; §10.6 C2, L381), which runs at sync time, not on every PR. The vendor-integrity block checks files inside reference/elephant-goldfish-model/; the wrapper files C2 resolves live in skills/egm-*/, outside that tree. So the "zero on the repo side" claim is unfounded as specified. New, not a re-raise of r4 Issue 9: Issue 9 asked for continuous detection; the r4 fix (E-V) claimed to provide it via C2-in-CI, but the claim and the specified CI block disagree.
*   **Rationale:** Same root cause as Issues 2, 21, and 35: the E-V fix claimed C2-in-CI but never added the step to the specified CI block.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. One consistent position for the cluster (R5-A): add the C2 step to the CI block as an eleventh `run:` block (it reads the repo root, so it covers the `skills/egm-*/` wrappers the tenth block's tree does not). Shared edit R5-A (with Issues 2, 21, 35).
*   ***Proposed Edit:***
    *   Location: D4 (L183–191); §11.3 (L422) (shared edit R5-A).
    *   Change: Apply R5-A.

### [Issue 40] [zoom_out-5-3] - Severity: Major
*   **Affected Scope:** §10.4 (L367)
*   **Discrepancy Description:** A token cap that does not exist yet is used to justify having no target-size cap now. §10.4: "A per-reviewer token cap bounds cost regardless of target-document size (token cost scales with target size, so the cap is the size bound); no separate maximum target size is set." The cap is created only by §14 decision 6 (L451), a pre-Phase-1 ruling ("Phase 1 does not start until decision 6 sets it"). During the pilot — currently in round 5 — neither a token cap nor a target-size cap exists; the pilot's actual bound is spawns × time (25 spawns × 30 minutes, L367), and a 30-minute reviewer can burn unbounded tokens on an unbounded target. The sentence asserts a control in the present tense and uses it to justify an in-force decision ("no separate maximum target size is set"), when the control comes into existence only after the pilot. New, not a re-raise of r4 Issue 55: Issue 55 complained the budget was deferred; the r4 fix (E-H) gated Phase 1 on decision 6 but inserted this sentence, which now misdescribes the pilot's own cost envelope.
*   **Rationale:** A future control is used to justify a present absence; the sentence misdescribes the pilot's actual cost envelope.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix rewords §10.4 to state the actual pilot envelope honestly (spawns × time only; no token cap, no target-size cap yet) and makes the decision-6 cap the Phase 1 size bound. Shared edit R5-B (with Issues 9, 22).
*   ***Proposed Edit:***
    *   Location: §10.4 (L367) (shared edit R5-B part (2)).
    *   Change: Apply R5-B part (2).

### [Issue 41] [zoom_out-5-4] - Severity: Major
*   **Affected Scope:** §11.3 (L422) et al.
*   **Discrepancy Description:** The vendored set is enumerated five times in prose while the generated .sha256 file is the allowlist. One vendored set enumerated in five places with three different formulations: §7 "Not vendored" exclusion list (L120); D4's exclusion + file list (L183); §9.3 step 2's copy-command list (L290); §10.5 step 2's diff-command list (L372); §11.3's arithmetic inventory (L422: "skills/ (38 files: … 7 × 5 = 35 — plus references/ in egm-bootstrap (2 files) and egm-draft (1 file): 35 + 2 + 1 = 38) … docs/ (33 files: 13 top-level, 18 under docs/designs/, 1 asset SVG, 1 under docs/verification/)"). Yet §11.3 itself states "the allowlist is the generated .github/vendor-elephant-goldfish-model.sha256 itself … and the vendor-integrity job enforces it" — the machine-enforced truth is the generated file, and the prose arithmetic is a second, hand-maintained source of truth that must be re-verified on every re-vendor or it contradicts the hash. The doc's own §5 argument against subset vendoring is that "maintaining a subset file list is its own drift risk" — that argument applies verbatim to maintaining a prose inventory of the same 90 paths.
*   **Rationale:** Five hand-maintained enumerations of one set, against the doc's own argument that maintaining such a list is itself a drift risk.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix deletes the §11.3 arithmetic inventory (keeping the 90-file total and the pointer to the generated .sha256 as the allowlist) and points §7's exclusion list at the §10.5 step 2 diff command as the authoritative included set. Shared edit R5-W (with Issue 49).
*   ***Proposed Edit:***
    *   Location: §11.3 (L422); §7 (L120) (shared edit R5-W).
    *   Change: Apply R5-W.

### [Issue 42] [zoom_out-5-5] - Severity: Major
*   **Affected Scope:** L24, L42, L84, L450
*   **Discrepancy Description:** The round-1 "65 findings" evidence is copied five times with no single source, and frozen at round 1. Same pilot statistic appears five times: L24 ("65 findings: 3 Blockers, 35 Majors, 27 Nits"), L42 twice ("found 65 findings" and "(65 findings) is evidence"), L84 ("the 65-finding pilot"), L450 ("the round-1 pilot: 65 findings including 3 Blockers"). It is load-bearing evidence for the §14 decision 5 pilot-value ruling (criterion (a), L450), yet it has no single source — the doc's D1 single-source-of-truth discipline covers the pin SHA but not its own evidence number — and it is frozen at round 1 while the loop has since completed rounds 2, 3, and 4 (round 4 alone: 56 findings, 52 fixes applied). Any correction to the count, or any decision to cite a later round, requires five coordinated edits across §§1, 3, 5, and 14. New, not a re-raise of r4 Issue 49 (which concerned specifying the full end state before the ruling): this concerns the evidence number's duplication and staleness.
*   **Rationale:** Load-bearing evidence with no single source, frozen at round 1 while the loop has completed four rounds.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the five occurrences on four lines are verified by grep. The fix keeps §3 as the single source, replaces the other four occurrences with pointers, and records the round-4 outcome in the same place. Shared edit R5-AW.
*   ***Proposed Edit:***
    *   Location: L24, L42, L84, L450 (shared edit R5-AW).
    *   Change: Apply R5-AW.

### [Issue 43] [zoom_out-5-6] - Severity: Major
*   **Affected Scope:** §10.3.1 (L351) / D6 (L220)
*   **Discrepancy Description:** 'Verify outputs' is defined twice in one paragraph with different content — the round-4 fix replaced one occurrence and missed the second. Line 220, a single D6 paragraph, contains both: "'Verify outputs' means the snapshot diff plus the three checks in §10.3.1 (line-existence, standard-name, memory-prohibition), nothing else." — and, later in the same paragraph: "'Verify outputs' means these two checks, nothing else." The only check named in the sentences immediately preceding the second definition is the line-existence check (plus the snapshot diff earlier in the paragraph), so "these two checks" reads as snapshot diff + line-existence — exactly the old definition the round-4 fix (E-C part 1) was supposed to replace. The fix corrected one occurrence and left its stale twin in the same paragraph, so the document's core verification term now has two contradictory definitions 200 words apart. New evidence about an incomplete fix, not a re-raise of r4 Issues 19/39 (whose §10.3.1 sentence was fixed).
*   **Rationale:** Same defect as Issue 28, stated from the zoom-out angle: the round-4 fix was incomplete in the same paragraph it fixed.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix deletes the second definition. Shared edit R5-D (with Issue 28).
*   ***Proposed Edit:***
    *   Location: §8 D6 (L220) (shared edit R5-D).
    *   Change: Apply R5-D.

### [Issue 44] [zoom_out-5-7] - Severity: Major
*   **Affected Scope:** §9.3 (L288–290)
*   **Discrepancy Description:** The generic Path 2 layout installs skills into a directory no specified harness reads. §9.3 (L288): "Generic Path 2 layout: bundle at <install-root>/egm/, skills at <install-root>/skills/egm-*/ … Path 2 is supported only for Muse, whose skill-discovery convention is custom-skills/ (Environment B). No generic harness skill-discovery convention is specified: a non-Muse harness has no supported Path 2 route until its skill directory and load mechanism are specified per harness in §9.2." Step 3 (L290) then instructs: "Adapt the 7 SKILL.md files per D3 into <install-root>/skills/egm-*/." The generic skills/ directory is explicitly not Muse's convention ("not the generic skills/", L288) and no other consumer is specified — so the generic install procedure, followed literally on a headless VM, lands loadable skills in a directory nothing is specified to read. The generic layout is an abstraction over a single instance (Environment B's custom-skills/), with no generic consumer. Distinct from the open zoom_out-1-1 ESCALATE (whether §9 belongs in the doc / its provisional scope); it is an internal defect of §9.3's specified layout.
*   **Rationale:** An install procedure that lands loadable skills in a directory nothing is specified to read is not an install procedure.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid, and distinct from the open ESCALATE (which concerns §9's scope, not its layout). The fix deletes the generic `<install-root>/skills/` layout and specifies Path 2 only in its one known form (`<install-root>` = `~/workspace`, skills in `custom-skills/`). Shared edit R5-AL (with Issue 33).
*   ***Proposed Edit:***
    *   Location: §9.3 (L288–290) (shared edit R5-AL).
    *   Change: Apply R5-AL.

### Nits

### [Issue 45] [design_critic-5-17] - Severity: Nit
*   **Affected Scope:** §10.6 C1 (L380)
*   **Discrepancy Description:** Routing-line and upstream-relative assertions reference `$f` outside any loop. `$f` is the loop variable of the preceding for loop, which has closed; standalone assertions have no binding for `$f`.
*   **Rationale:** Assertions that reference a closed loop's variable have no binding; run as written they test the wrong file or fail.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix wraps the assertions in their own per-file loop. (The assertion patterns themselves are byte-clean — correct single-backslash ERE, plain quotes — so only the binding is fixed.) Shared edit R5-E part (2) (with Issues 1, 3).
*   ***Proposed Edit:***
    *   Location: §10.6 C1 (L380) (shared edit R5-E part (2)).
    *   Change: Apply R5-E part (2).

### [Issue 46] [design_critic-5-18] - Severity: Nit
*   **Affected Scope:** §8 D6 (L220)
*   **Discrepancy Description:** Three snapshot imprecisions. (a) "one file per location, <n> = 1–4" but location (3) is "each ~/workspace/custom-skills/egm-*/ dir" (seven dirs sharing one slot); single-<dir> command form does not say one globbed find or seven files. (b) "The after-diff ignores files under ~/workspace/plans/ that did not exist at snapshot time" — no filter command given; plain diff will list the round's own report file. (c) Rollback "remove newly created untracked files (rm -- <paths>)" fails on newly created directories (rm without -r).
*   **Rationale:** Three small imprecisions in the core safety control, each of which makes the stated procedure unexecutable or wrong as written.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid on all three. The fix states location (3) is one snapshot file over the glob, gives the exclusion procedure, and uses `rm -rf`. Shared edit R5-U (with Issues 23, 68).
*   ***Proposed Edit:***
    *   Location: §8 D6 (L220) (shared edit R5-U).
    *   Change: Apply R5-U.

### [Issue 47] [design_critic-5-19] - Severity: Nit
*   **Affected Scope:** §11 rollout table (L401)
*   **Discrepancy Description:** Phase 1 Scope and Gate name different drift targets. Scope: "egm-drift-report run once against a live design doc"; Gate: target is "skills/README.md attribution table vs. skills/ tree" — not a design doc — and clean bill requires "the target's design-doc coverage stated", incoherent for an attribution-table target.
*   **Rationale:** Scope and Gate of the same phase name different targets, and the clean-bill criterion does not apply to the Gate's named target.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix aligns Scope with the Gate's named target and defines the coverage statement for it. Shared edit R5-J (with Issues 59, 69).
*   ***Proposed Edit:***
    *   Location: §11 Phase 1 row (L401) (shared edit R5-J).
    *   Change: Apply R5-J.

### [Issue 48] [design_critic-5-20] - Severity: Nit
*   **Affected Scope:** §11.3 (L422–424) vs §10.3.3 (L359)
*   **Discrepancy Description:** egm-bootstrap's named target has no scheduled run in any phase. "Both skills are deferred to Phase 1 with these named targets" — but Phase 1 runs only egm-drift-report; no phase schedules the egm-bootstrap run against reference/ tree documentation.
*   **Rationale:** A named target with no scheduled run is a deferred skill that never runs.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix schedules the bootstrap run in Phase 1 (alongside the drift-report run). Shared edit R5-V (with the §11 half in R5-J).
*   ***Proposed Edit:***
    *   Location: §10.3.3 (L359); §11 Phase 1 row (shared edits R5-V, R5-J).
    *   Change: Apply R5-V and the R5-J Scope text.

### [Issue 49] [design_critic-5-21] - Severity: Nit
*   **Affected Scope:** §11.3 (L422–424)
*   **Discrepancy Description:** "exact path list (allowlist)" is counts, not paths. "The pre-execution statement of its contents is the 90-path inventory above (38 + 10 + 7 + 33 + LICENSE + plugin.json)". Inventory gives counts, not paths: 13 top-level docs/ files and 18 docs/designs/ files never named, so generated .sha256 cannot be checked against the plan before execution — the gap r4 Issue 33(c) raised, now relabeled rather than closed.
*   **Rationale:** A path list that lists counts, not paths, cannot be checked against the generated hash it claims to state.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. Per the consistent position with Issue 41, the fix deletes the arithmetic inventory and drops the "exact path list" wording (the generated hash file is the allowlist), rather than listing all 90 paths in prose — which would create a third hand-maintained copy. Shared edit R5-W (with Issue 41).
*   ***Proposed Edit:***
    *   Location: §11.3 (L422–424) (shared edit R5-W).
    *   Change: Apply R5-W.

### [Issue 50] [design_critic-5-22] - Severity: Nit
*   **Affected Scope:** §14 decision 3 (L448)
*   **Discrepancy Description:** Appendix move creates inconsistent appendix naming. "§9 is moved to an appendix (new heading ## Appendix A — Environment A...)" while existing appendix remains unlettered "## Appendix — Sources". After move: "Appendix A" plus unlettered "Appendix"; renaming of §9.1–§9.5 cross-references unspecified.
*   **Rationale:** A move that leaves two appendices with inconsistent naming and unspecified subsection mapping creates the confusion it was meant to resolve.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix states Sources becomes Appendix B and specifies the §9.x → Appendix A §x mapping. Shared edit R5-K (with Issue 70).
*   ***Proposed Edit:***
    *   Location: §14 decision 3 (L448) (shared edit R5-K).
    *   Change: Apply R5-K.

### [Issue 51] [design_critic-5-23] - Severity: Nit
*   **Affected Scope:** §9.3 step 1 (L290), §10.5 step 2 (L372)
*   **Discrepancy Description:** Clone steps not re-runnable. Both clone into a fixed path (<install-root>/egm-checkout, /tmp/egm-upstream) with no rm -rf first; re-running fails because destination exists — same failure mode D6's rollback guards with rm -rf first.
*   **Rationale:** A verification procedure that fails on its second run is not re-runnable.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix adds the `rm -rf` cleanup to both steps, matching the doc's own D6 pattern. Shared edit R5-X.
*   ***Proposed Edit:***
    *   Location: §9.3 step 1 (L290); §10.5 step 2 (L372) (shared edit R5-X).
    *   Change: Apply R5-X.

### [Issue 52] [design_critic-5-24] - Severity: Nit
*   **Affected Scope:** §9.4 note (L301)
*   **Discrepancy Description:** Cursor/OpenCode-only VM route points at a Muse-only path. "a VM with only Cursor or OpenCode installed follows the headless row (Path 2, Muse only) or does not adopt". Path 2 is Muse-only, so a VM with only Cursor/OpenCode cannot follow the headless row — first alternative inapplicable without Muse.
*   **Rationale:** Same defect as Issue 63: the first alternative of the note is inapplicable to the VM it describes.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix routes Cursor/OpenCode-only VMs to "does not adopt" unless Muse is also present. Shared edit R5-I (with Issue 63).
*   ***Proposed Edit:***
    *   Location: §9.4 note (L301) (shared edit R5-I).
    *   Change: Apply R5-I.

### [Issue 53] [design_critic-5-25] - Severity: Nit
*   **Affected Scope:** §8 D1 (L138)
*   **Discrepancy Description:** 90-day staleness rule has no computation and fires only at sync time. "if upstream HEAD is more than 90 days newer than the pin, the sync record notes the pin as stale" — no computation stated (which dates, which command), and check fires only "on every sync", so a pin can go stale silently as long as no sync happens.
*   **Rationale:** A rule with no computation and a sync-only trigger cannot be applied and silently misses the case it exists for.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix specifies the date comparison (`git log -1 --format=%ci`, verified in the AEP repo) and adds a phase-gate trigger, accepting the between-gates window explicitly. Shared edit R5-Y.
*   ***Proposed Edit:***
    *   Location: §8 D1 (L138) (shared edit R5-Y).
    *   Change: Apply R5-Y.

### [Issue 54] [structural-5-3] - Severity: Nit
*   **Affected Scope:** §8 D4 L179–194; §10.6 L382–389
*   **Discrepancy Description:** Unindented fenced code blocks inside list items split the lists: D4 "- **Bundle:**" bullet (L179, continuations indented 2 spaces) contains a fence at column 0 (L185, L191); paragraph "Write reference/elephant-goldfish-model/PROVENANCE.md…" (L193, indent 0) sits outside the bullet; "- **Wrappers:**" (L194) starts a second list. §10.6 item "3. **C3 — skill.yaml parses:**" (L382) contains fence at column 0 (L384, L386); "Expected: exit 0, no MISMATCH lines)." (L388, indent 0) floats outside item 3; items 4–7 resume as a second list. Other fenced blocks (§9.2 L247–251, §10.2 L324–332) sit at top level and do not split anything.
*   **Rationale:** List items split by unindented fences render as separate lists with floating paragraphs — the document's structure is not what its numbering claims.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; the split-list structure is verified in the target. The fix indents both fences (and the C3 "Expected:" line) by the list-item continuation indent. Shared edit R5-AB.
*   ***Proposed Edit:***
    *   Location: D4 (L185, L191); §10.6 C3 (L384, L386, L388) (shared edit R5-AB).
    *   Change: Apply R5-AB.

### [Issue 55] [structural-5-4] - Severity: Nit
*   **Affected Scope:** §9.2, L264
*   **Discrepancy Description:** Lone H4 single-child subsection with a 107-char heading. "#### Native installs for the other harnesses (commands from the bundle's `docs/harnesses.md` install table)" is the only H4 under §9.2 and one of only five H4s (other four are §10.3.1–10.3.4 sibling set). Muse install content in same §9.2 (L245–262) has no parallel subheading; heading carries a source parenthetical that belongs in body text.
*   **Rationale:** A lone single-child subsection with a source parenthetical in its heading breaks the document's heading discipline.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix demotes it to a bold lead-in paragraph; promoting to H3 would cascade-renumber §9.3–§9.5 and cross-references. Shared edit R5-AC.
*   ***Proposed Edit:***
    *   Location: §9.2 (L264) (shared edit R5-AC).
    *   Change: Apply R5-AC.

### [Issue 56] [structural-5-5] - Severity: Nit
*   **Affected Scope:** §9.3 (L290), §10.2 (L336)
*   **Discrepancy Description:** Multi-step procedures formatted inconsistently: inline-numbered single paragraphs vs ordered lists. §9.3 (L290, 1,051 chars) packs six install steps into one paragraph; §10.2 (L336, 2,751 chars) packs five sync steps the same way. Parallel procedures in the same document are proper ordered lists: §9.5 steps 1–4 (L305–309), §10.5 steps 1–4 (L371–374), §10.6 checks C1–C7 (L380–392), §14 decisions 1–6 (L446–451).
*   **Rationale:** Parallel procedures in the same document should share a format; inline-numbered paragraphs hide step boundaries.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix reformats both passages as `N.` ordered lists matching §9.5/§10.5. Shared edit R5-AD.
*   ***Proposed Edit:***
    *   Location: §9.3 (L290); §10.2 (L336) (shared edit R5-AD).
    *   Change: Apply R5-AD.

### [Issue 57] [structural-5-6] - Severity: Nit
*   **Affected Scope:** Whole document (line wrap)
*   **Discrepancy Description:** Line-wrap inconsistency: 78 lines over 300 chars against a predominantly ~80-column wrap. Worst cases, all single-line normative paragraphs: L220 (4,828 chars, D6 read-only caveat), L363 (3,499 chars, §10.3.4 brief contents), L336 (2,751 chars, §10.2 sync steps), L308 (2,345 chars, §9.5 step 3), L213 (2,026 chars, D6 snapshot/rollback). Several are round-4 fix insertions applied as single lines (E-C, E-D, E-M). Recommendation: re-wrap the five lines above (and the other >1,000-char lines: L153, L171, L193, L305, L372, L374, L380, L422) to the document's prevailing ~80-column wrap. No wording change.
*   **Rationale:** Long single-line paragraphs are hard to read in source and inconsistent with the document's prevailing wrap.
*   ***AI Suggestion:*** DECLINE
*   ***Justification:*** The observation is true, but a bulk re-wrap of 13 long lines — several of which contain literal shell commands — is exactly the transcription-risky churn that corrupted the §10.5/§10.6 commands in round 4, for zero semantic gain: Markdown renders identically, and the lines remain readable in source. Recorded; not fixed.
*   ***Proposed Edit:***
    *   Location: n/a.
    *   Change: None (declined).

### [Issue 58] [implementation_readiness-5-10] - Severity: Nit
*   **Affected Scope:** §10.3.2 (L352)
*   **Discrepancy Description:** Readiness-gate file-existence verification has no command. "the target document exists, reviewers and standards resolve to existing files, and GoldfishContext is provided" — no existence-check command (e.g. `test -f` per path) is given for the Elephant to run before asking the gate question.
*   **Rationale:** A gate whose precondition check has no command cannot be run by the Elephant as written.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix gives the literal `test -f` loop over the brief's paths (run verbatim in sandbox). Shared edit R5-AG.
*   ***Proposed Edit:***
    *   Location: §10.3.2 (L352) (shared edit R5-AG).
    *   Change: Apply R5-AG.

### [Issue 59] [implementation_readiness-5-11] - Severity: Nit
*   **Affected Scope:** §11 Phase 1 gate (L401)
*   **Discrepancy Description:** Clean-bill criterion "coverage stated" is undefined. "produces a dated finding, or a clean bill with the target's design-doc coverage stated". What coverage, of what, in what form, is undefined — and the named target is the skills/README.md attribution table vs the skills/ tree, not a design doc, so "design-doc coverage" does not obviously apply.
*   **Rationale:** Same defect as Issues 47 and 69: the clean-bill criterion is undefined for its named target.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix defines the coverage statement (table row coverage, with counts recorded). Shared edit R5-J (with Issues 47, 69).
*   ***Proposed Edit:***
    *   Location: §11 Phase 1 Gate (L401) (shared edit R5-J).
    *   Change: Apply R5-J.

### [Issue 60] [comprehension-5-11] - Severity: Nit
*   **Affected Scope:** §8 D7, L224
*   **Discrepancy Description:** The trusted_enabled gloss is tautological. "the named egm/egm-* definitions report trusted_enabled (the status the harness reports for the named definition)". Parenthetical restates that it is a reported status without saying what trusted_enabled signifies — so the sentence's own puzzle (reports enabled, yet spawning is rejected with agent_definition_unavailable) is left unexplained.
*   **Rationale:** A gloss that restates the term without explaining it leaves the sentence's own puzzle unexplained.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix glosses the meaning (listed as trusted/available, though spawning is still rejected). Shared edit R5-AO.
*   ***Proposed Edit:***
    *   Location: §8 D7 (L224) (shared edit R5-AO).
    *   Change: Apply R5-AO.

### [Issue 61] [comprehension-5-12] - Severity: Nit
*   **Affected Scope:** §9.1, L240
*   **Discrepancy Description:** "PEP 668" is cited by number only. "a venv is used because PEP 668 externally-managed environments refuse bare pip install". Consequence explained, but "PEP 668" never expanded or identified as a Python packaging standard.
*   **Rationale:** A standard cited by number only, with no expansion, cannot be understood by a reader who does not already know it.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix expands it on first use. Shared edit R5-AP.
*   ***Proposed Edit:***
    *   Location: §9.1 (L240) (shared edit R5-AP).
    *   Change: Apply R5-AP.

### [Issue 62] [comprehension-5-13] - Severity: Nit
*   **Affected Scope:** §9.2, L269
*   **Discrepancy Description:** Antigravity "run /plugin" is unexplained. "**Antigravity App/IDEs:** run `/plugin`". No other line says what /plugin is — a slash command, a menu item, a keystroke — or what it does (opens the plugin installer?). Every other harness row gives an explicit command; this one gives an unexplained token.
*   **Rationale:** One unexplained token where every parallel row gives an explicit command.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix spells it out (the `/plugin` slash command to open the plugin installer). Shared edit R5-AQ.
*   ***Proposed Edit:***
    *   Location: §9.2 (L269) (shared edit R5-AQ).
    *   Change: Apply R5-AQ.

### [Issue 63] [comprehension-5-14] - Severity: Nit
*   **Affected Scope:** §9.4, L301
*   **Discrepancy Description:** Cursor/OpenCode row offers two outcomes with no selection rule. "a VM with only Cursor or OpenCode installed follows the headless row (Path 2, Muse only) or does not adopt." Two incompatible outcomes with no rule for which applies when — and the headless row is Path 2, "Muse only," so a VM with only Cursor installed arguably cannot follow it at all.
*   **Rationale:** Same defect as Issue 52: two incompatible outcomes with no selection rule, one of them inapplicable.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix states the rule (does not adopt; headless row applies only where Muse is present without its CLI). Shared edit R5-I (with Issue 52).
*   ***Proposed Edit:***
    *   Location: §9.4 (L301) (shared edit R5-I).
    *   Change: Apply R5-I.

### [Issue 64] [comprehension-5-15] - Severity: Nit
*   **Affected Scope:** §10.5 step 2, L372
*   **Discrepancy Description:** The 40-character SHA is never stated to be the same commit as the short pin. "`git rev-parse HEAD` must print exactly `e9e1f06aa4e26e95cd4ed37210a0632202c429e9`". The pin stated everywhere else (D1, §7, §11.3, §14 decision 1) is the 8-character e9e1f06a. Doc never says the 40-character string is the full expansion of the short pin.
*   **Rationale:** A reader cannot tell whether the 40-character expected hash is the same commit as the 8-character pin stated everywhere else.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix adds "(the full form of the `e9e1f06a` pin)". Shared edit R5-AR.
*   ***Proposed Edit:***
    *   Location: §10.5 step 2 (L372) (shared edit R5-AR).
    *   Change: Apply R5-AR.

### [Issue 65] [comprehension-5-16] - Severity: Nit
*   **Affected Scope:** §10.3.1, L351
*   **Discrepancy Description:** "before synthesizing" collides with "no synthesizer in Environment B". "Wait for actual completion before synthesizing; propagate failures and timeouts." But §10.3 role table (L347) says the synthesizer "in Environment B … is replaced by direct dispatch … with the Elephant consolidating findings." Reader cannot tell whether "synthesizing" is a leftover reference to the unused synthesizer role or a synonym for the Elephant's consolidation.
*   **Rationale:** A term that collides with a role the doc says is unused in this environment confuses the reader about who does the step.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix replaces "before synthesizing" with "before consolidating". Shared edit R5-AS.
*   ***Proposed Edit:***
    *   Location: §10.3.1 (L351) (shared edit R5-AS).
    *   Change: Apply R5-AS.

### [Issue 66] [comprehension-5-17] - Severity: Nit
*   **Affected Scope:** §14 decision 2, L447
*   **Discrepancy Description:** Two senses of "target" in one sentence. "The AEP repo is context (GoldfishContext), not the target: the Phase 2 PR … is the target state the pilot's evidence supports, not the artifact under review." Sentence uses "target" to mean both "the artifact under review" (which the PR is not) and "target state" (which the PR is).
*   **Rationale:** One word used in two senses in one sentence invites misreading of what the pilot's evidence supports.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix rewords to separate the senses ("artifact under review" vs "end state"). Shared edit R5-AT.
*   ***Proposed Edit:***
    *   Location: §14 decision 2 (L447) (shared edit R5-AT).
    *   Change: Apply R5-AT.

### [Issue 67] [comprehension-5-18] - Severity: Nit
*   **Affected Scope:** §5, L73 and L77
*   **Discrepancy Description:** "D3 rewrites docs/codex.md" misstates what D3 rewrites. L73 and L77 both say "D3 rewrites docs/codex.md, docs/claude.md, docs/harnesses.md". D3 rewrites *references to* those files inside adapted SKILL.md files; the bundle files themselves are never edited ("The pristine bundle is never edited," D3). As written, a reader would conclude the bundle's docs files are modified, contradicting the pristine-bundle rule.
*   **Rationale:** The wording contradicts the pristine-bundle rule it sits next to.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; both occurrences verified (L73, L77). The fix changes both to "rewrites references to". Shared edit R5-AU.
*   ***Proposed Edit:***
    *   Location: §5 (L73, L77) (shared edit R5-AU).
    *   Change: Apply R5-AU.

### [Issue 68] [comprehension-5-19] - Severity: Nit
*   **Affected Scope:** §8 D6, L220
*   **Discrepancy Description:** Snapshot file counting contradicts itself for location (3). "snapshot each scope location by content hash with the find form (… > /tmp/egm-snapshot-<run>-<n>.sha256, one file per location, <n> = 1–4 for the four locations in scope order …): (1) the target repo working tree, (2) ~/workspace/egm/, (3) each ~/workspace/custom-skills/egm-*/ dir, (4) ~/workspace/plans/." "One file per location" with <n> = 1–4 implies four files, but location (3) is "each … dir" — seven skill directories — which implies either one file covering all seven (unstated: the find form takes a single <dir>) or seven files (which breaks the 1–4 numbering).
*   **Rationale:** Same defect as Issues 23 and 46: the location-(3) snapshot form is ambiguous between one file and seven.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix states location (3) is one snapshot file over the glob. Shared edit R5-U (with Issues 23, 46).
*   ***Proposed Edit:***
    *   Location: §8 D6 (L220) (shared edit R5-U part (1)).
    *   Change: Apply R5-U part (1).

### [Issue 69] [comprehension-5-20] - Severity: Nit
*   **Affected Scope:** §11, L401
*   **Discrepancy Description:** "design-doc coverage" is undefined for an attribution-table target. Phase 1 gate: "drift report names its target in advance (skills/README.md attribution table vs. skills/ tree) and produces a dated finding, or a clean bill with the target's design-doc coverage stated". Named target is an attribution table, not a design doc — "design-doc coverage" has no meaning for it, and the term is defined nowhere.
*   **Rationale:** Same defect as Issues 47 and 59: a coverage criterion that does not apply to its named target.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix replaces "design-doc coverage" with the table's row coverage, defined with counts. Shared edit R5-J (with Issues 47, 59).
*   ***Proposed Edit:***
    *   Location: §11 Phase 1 Gate (L401) (shared edit R5-J).
    *   Change: Apply R5-J.

### [Issue 70] [comprehension-5-21] - Severity: Nit
*   **Affected Scope:** §14 decision 3, L449
*   **Discrepancy Description:** The Appendix A rename rule does not say how subsection references map. "§9 is moved to an appendix (new heading ## Appendix A — Environment A (general-purpose Linux VM) …; all §9 cross-references become Appendix A cross-references)". Doc cross-references §9.1, §9.2, §9.3, §9.4, §9.5 throughout; rule does not say whether those become "Appendix A §1," "Appendix A.1," or stay as §9.1 under a renamed heading.
*   **Rationale:** Same defect as Issue 50: the rename rule leaves subsection mapping unspecified.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix specifies the §9.x → Appendix A §x mapping and that Sources becomes Appendix B. Shared edit R5-K (with Issue 50).
*   ***Proposed Edit:***
    *   Location: §14 decision 3 (L448–449) (shared edit R5-K).
    *   Change: Apply R5-K.

### [Issue 71] [zoom_out-5-8] - Severity: Nit
*   **Affected Scope:** §10.3.3 (L359)
*   **Discrepancy Description:** The selection rule is stated twice in the same paragraph. Line 359 contains, in one paragraph: "Use EGM where a written standard and a configured panel add value (design docs, upstream PRs); keep the lighter tools for fast checks." — and later in the same paragraph: "Selection rule: use EGM when the artifact is a design document (or an upstream PR) that needs a written standard and a configured panel with filed reports; use grilling or roundtable_review for a fast single-session challenge with no filed report; …" The round-4 fix (E-T part 3) appended the selection rule to a paragraph that already stated it. The boundary is also restated in §5's overlap bullet and §2's non-goal. One rule, stated once.
*   **Rationale:** The round-4 fix appended a rule to a paragraph that already stated it, duplicating it in place.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix deletes the earlier "Use EGM where…" sentence and keeps the "Selection rule:" sentence. Shared edit R5-AY.
*   ***Proposed Edit:***
    *   Location: §10.3.3 (L359) (shared edit R5-AY).
    *   Change: Apply R5-AY.

### [Issue 72] [zoom_out-5-9] - Severity: Nit
*   **Affected Scope:** Whole document (definitions)
*   **Discrepancy Description:** Inline definitions are scattered across eight sections while §1 already has a Terminology paragraph. §1 (L20) already carries a Terminology paragraph (Muse / muse CLI / current Muse environment / Owner / Elephant / sync 'owner'), but the round-4 fixes added definitions elsewhere instead of there: D6 (L220) defines 'agent tool projections', 'Claude tool allowlists', 'configured memory services', 'project instructions', 'Verify outputs'; §10.2 (L336) defines 'live', 'sync record', 'Maximum tolerable drift window'; §10.4 (L367) defines 'Unsettled', 'substantially restate', SETTLED; §7 carries a 'Namespace note'; D5 (L213) defines 'Install notes'; §10.3.2 defines GoldfishContext; §14 decision 3 defines 'Documented-but-unexecuted'. Each round's comprehension fix adds another inline gloss where the term is first used, so defined terms are now spread across the whole document and two of them (§10.4's token cap, D6's 'Verify outputs' — see 5-3 and 5-6) have already drifted from their own definitions. A glossary that grows by accretion is itself a maintenance surface.
*   **Rationale:** Definitions scattered across eight sections have already drifted from each other; each round adds more inline glosses to new locations.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid. The fix consolidates all defined terms into a §1.1 Glossary and replaces inline definitions with pointers; new terms go in the glossary. Interactions with R5-B and R5-D are noted in R5-AZ. Shared edit R5-AZ.
*   ***Proposed Edit:***
    *   Location: §1 (L20) + D6, §10.2, §10.4, §7, D5, §10.3.2, §14 decision 3 (shared edit R5-AZ).
    *   Change: Apply R5-AZ.
