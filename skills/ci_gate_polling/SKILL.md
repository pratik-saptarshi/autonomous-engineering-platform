# CI Gate Polling

## Pin the expected verdict before polling

- Record the pull request head SHA and the full expected check set before the first poll, taken from branch protection requirements or from a complete earlier run on the same head.

- Write down how many checks must report and which of them are gating, so a later count can be compared against a number fixed in advance.

- Treat the poller as a convenience reader of that set, never as the source of what the set should contain.

## Refuse vacuous completion

- Treat an empty check set, a query error, a malformed query and a result set whose SHA differs from the pinned head as UNKNOWN, never as complete or passing.

- Stop and fix the query when the poller returns fewer checks than the pinned expected count, and say plainly that the wait so far was blind for the missing checks.

- Restart the poll from a corrected query rather than extending trust to partial results gathered while the query was wrong.

## Held runs are a verdict, not a wait

- A check set can stall without failing: runs sit QUEUED or in-progress far beyond their observed norms on the same repository, or never start at all. A stall is a state to classify, not a reason to keep polling.

- Fork pull requests add a limbo of their own: a first-time contributor's runs can sit at `action_required` until a maintainer approves them. No amount of waiting releases that hold; classify it as HELD-FOR-MAINTAINER, distinct from pending CI, the moment the run state shows it.

- Keep three verdicts separate: RUNNING (progressing within observed norms), HELD (blocked on a named human or platform action), FAILED (terminal, unsuccessful). HELD is never reported as still-running, and a poll that ends on a held run says so.

- Report every held run with its release action named: who must do what (for example, a maintainer approving the workflow run on the pull request). A held run reported without its release action sends the reader back to investigate from zero.

- Never wait silently forever: when a run exceeds roughly two to three times its observed norm with no state change, re-read the run state directly, classify it, and report. LadybugDB/ladybug-rust PR #47 sat at `action_required` under the first-time-contributor gate while reading as ordinary pending CI; the esf and AEP waits of 2026-11-09/11 are the same trap in slower form.

## Verify directly before declaring

- Confirm the final state with a direct read of the check runs for the pinned head SHA before reporting CI complete, green or failed.

- Count terminal results against the pinned expected count and name any gating check that is still pending, missing or only report-only.

- Report the verdict with the head SHA, the number of gating checks seen and the number expected, so the claim can be checked against the same numbers.

- Label anything you could not read directly as unverified instead of folding it into a passing verdict.

## New-head baseline taxonomy

- After any re-pin or new head, rebuild the baseline before judging the change: run the full suite threaded, then re-run every failure solo.

- Classify each failure as (a) timing/load flake, (b) environmental/upstream-baseline, or (c) introduced by the change. The counts must sum to the failure total, and UNCLASSIFIED = 0 is the exit bar before any blocker work begins.

- Re-check judged-fix tests explicitly against the new baseline floor; a fix proven at an old head is not proven at the new one until its tests are located in the new run.

- Precedents: PR #120 Round 2 baseline 2630/15/8 — all 15 classified (a)3/(b)9/(c)3; Round 3 — 2638/18/8, (a)6/(b)11/(c)1, unclassified 0.

## Flake rulings are gated dispositions

- An out-of-baseline-set failure is neither auto-failed nor auto-ignored. Prove its mechanism in source, solo-pass it, and put the ruling to the panel.

- The panel seat rules the failure admissible or not; the judge accepts or rejects that ruling. A gate PASS may be made conditional on that acceptance, and is reported as conditional until it lands.

- Precedent: PR #120 combined gate — one out-of-set solo-passing flake, the testing seat's flake rulings accepted by the judge, gate PASS conditional on them.

## Coordinated-landing and self-healing failures are not defects

- Some failures clear only on a planned landing step: CodeQL SARIF uploads failing while the default setup is still enabled ("advanced configurations cannot be processed when the default setup is enabled"), or a gate-receipt check failing on a base-branch bootstrap that self-heals on merge.

- Classify these as coordinated-landing conditions, not defects. Keep them out of cycle scope, and HOLD any thread replies that depend on them until the post-push run confirms the condition resolved.

- Precedents: PR #182 Item 3 condition 3.2; PR #120 gate-receipt ×7 bootstrap, "zero signal".

## Failure-name-set invariant

- Where a baseline has pre-existing failures, save the failure NAMES ex ante and judge the post-change run by "zero new names" across two independent runs.

- Counts flake; name sets don't. A shifting failure count with a stable, subset-only name set is count flakiness, not regression.

- Precedent: PR #163 F1 — 49-name baseline; both post-fix runs' failure-name sets were strict subsets with zero new names, and the judge accepted the count-flakiness caveat on exactly this basis.

## Baseline attribution

- A failure is attributable to the change only if it does NOT reproduce identically on the pristine base / both parents. Identical-on-baseline is REFUTED as a change defect, however real it is as a repo defect.

- Name what the diagnosis does NOT explain; an attribution that silently covers unrelated failures is not an attribution.

- A "green" verdict on a head that predates the current vulnerability-DB or toolchain state is STALE, not clean. Re-check currency before citing it.

- When several sibling PRs fail the same check, treat the shared pattern as a possible shared cause, not as several independent change defects: test the base branch itself on that check before attributing anything to any PR's diff.

- If the base reproduces the failure, classify it as a base defect for every sibling it reproduces on; if it does not, return to per-PR attribution. Either way, report per PR by applying the two rules above to that PR: name what the base diagnosis does and does not explain for it, and treat any green it earned before the base went red as stale under the stale-green rule, to be re-earned rather than inherited.

- Precedents: PR #105 — all four failing legs log-verified pre-existing on same-day develop runs; dap go-security — PRs #211, #214 and #215 all failing the same check, main itself red on GO-2026-6859 at go1.27.3 (fixed in 1.27.4), so none of those failures was attributable to their diffs, and PR #213's clean status was stale.

## Available connectors

- [GitHub](/opt/hatch/connectors/github/CONNECTOR.md) for reading pull request check runs, review state and merge status for the pinned head.

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.

## Alternatives for better results

- Prefer the provider web view for the exact head commit when an API query keeps returning an implausible set, and reconcile the two counts before reporting.

- Re-derive the expected set from branch protection whenever protections or required checks changed during the pull request, instead of reusing the set pinned at the first poll.
