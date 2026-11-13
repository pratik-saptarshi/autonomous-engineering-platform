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

## Available connectors

- [GitHub](/opt/hatch/connectors/github/CONNECTOR.md) for reading pull request check runs, review state and merge status for the pinned head.

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.

## Alternatives for better results

- Prefer the provider web view for the exact head commit when an API query keeps returning an implausible set, and reconcile the two counts before reporting.

- Re-derive the expected set from branch protection whenever protections or required checks changed during the pull request, instead of reusing the set pinned at the first poll.
