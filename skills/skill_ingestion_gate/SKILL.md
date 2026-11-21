# Screen a Third-Party Skill Through the Security Gate

## Run the pre-ingestion gate

- Scan the candidate skill with `~/workspace/skillspector/scan-gate.sh /path/to/skill/` before copying it into `~/workspace/custom-skills/`.

- Treat the gate as fail closed: a score above 50 or any HIGH or CRITICAL finding blocks the install, and a scan error blocks it too.

- Record the score and the verdict in your report to the user, even when the scan passes. A score of 0 is LOW and SAFE, 21 to 50 is MEDIUM and CAUTION with findings to review.

## Read the full findings on a block

- Re-run the scan with `--format json` and read the `issues` list. Each entry carries an id, a severity, a confidence, and a file plus line location.

- Open every flagged location in context and quote the flagged text before deciding anything. Markdown prose is the usual attack surface, so a pattern id alone never tells you what fired.

- Refuse to infer the cause of a block from the skill's file layout or its feature list. Editing on a guessed trigger wastes a slow re-scan and can leave the real finding in place.

## Decide the verdict from the findings

- Install the skill on a SAFE verdict and move on. On CAUTION, review each finding, note any accepted-by-design behavior, and install only after triage.

- Stop on HIGH or CRITICAL and report the findings verbatim to the user. Do not surgically modify a third-party skill to dodge the scanner without knowing exactly which issues you are addressing.

- When the user directs a modification, fix the specific flagged issues, then re-scan and confirm those exact issue ids are gone. One passed scan never proves a different change would also pass.

## Diagnose a fail-closed block per target

- A full-tree scan exiting 1 is a BLOCK, not a findings verdict. Do not conclude anything about the skill as a whole from it.

- Re-scan per target to isolate which subtree errors or scores, and score each part separately before forming a verdict on any part.

- Precedent: the Modern Web Guidance package — the full-tree scan exited 1 after ~10 min because the generated `gen/` index errors the scanner outright. Per-target, the CLI scored 41 MEDIUM and the skill itself was clean.

## Contain a capability-text HIGH with a wrapper allowlist

- When a HIGH finding's flagged evidence is the tool's own capability or help text — for example a "self-modification" rule matched on the CLI's `--help` text — the control is NOT editing the vendored code.

- The control is a hard wrapper allowlist: only the approved subcommands run, everything else is refused, and the refusal is negative-tested. Record a baseline exception in `~/workspace/skillspector/baselines/<name>.json` naming the finding and its justification.

- Precedent: `~/workspace/bin/modern-web-guidance` enforces search/retrieve/list only; install/update/legacy-scan are refused with exit 2, negative-tested. The exception is recorded in `baselines/modern-web-guidance.json`.

## Verify bundled-runner scope, then clean-room test

- A skill is consumed at FOLDER scope, not repo scope. If its text claims a bundled runner (e.g. `scripts/scan-gate.sh`), verify the runner exists inside the skill's own folder.

- A runner that exists only at repo-root scope is a scope error: fail-closed if the root copy is used, fail-confused if a consumer improvises one. A missing runner counts as a scan error — never improvise a runner.

- Fix by bundling a generalized copy whose verdict logic is byte-identical to the reference runner, and prove it with a verdict-logic diff. Then prove the skill standalone in a clean room: the folder alone passes, fails closed on an induced failure, and preserves its fallback path.

- Precedent: the ingestion-gate bundling gap, fixed under option (c) 2026-11-14 at head 0a990b1, verified by re-scan score 0, a clean-room execution test, and a verdict-logic diff.

## Available connectors

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.

## Alternatives for better results

- Baseline findings you have reviewed and accepted for your own skills with `~/workspace/skillspector/venv/bin/skillspector baseline`, so re-scans surface only new findings.

- Remember the scanner runs static analysis only here. A clean scan is necessary but not sufficient for a high-risk skill, so keep human judgment in the loop.