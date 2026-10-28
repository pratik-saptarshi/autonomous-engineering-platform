# Screen a Third-Party Skill Through the Security Gate

## Prerequisites

- A static skill scanner is installed in your environment, and a gate script
  can reach it. The bundled `scripts/scan-gate.sh` is the reference runner:
  it exits 0 only when the score is 50 or below with no HIGH or CRITICAL
  findings, and fails closed on any scan error. If your scanner lives
  somewhere other than where the gate script looks, point the script at it
  first.
- Know your agent's skills directory (where installed skills live).

## Run the pre-ingestion gate

- Scan the candidate skill with the gate script before copying it into your
  skills directory: `scripts/scan-gate.sh /path/to/skill/`.

- Treat the gate as fail closed: a score above 50 or any HIGH or CRITICAL
  finding blocks the install, and a scan error blocks it too.

- Record the score and the verdict in your report to the user, even when the
  scan passes. A score of 0 is LOW and SAFE, 21 to 50 is MEDIUM and CAUTION
  with findings to review.

## Read the full findings on a block

- Re-run the scan with `--format json` and read the `issues` list. Each entry
  carries an id, a severity, a confidence, and a file plus line location.

- Open every flagged location in context and quote the flagged text before
  deciding anything. Markdown prose is the usual attack surface, so a pattern
  id alone never tells you what fired.

- Refuse to infer the cause of a block from the skill's file layout or its
  feature list. Editing on a guessed trigger wastes a slow re-scan and can
  leave the real finding in place.

## Decide the verdict from the findings

- Install the skill on a SAFE verdict and move on. On CAUTION, review each
  finding, note any accepted-by-design behavior, and install only after
  triage.

- Stop on HIGH or CRITICAL and report the findings verbatim to the user. Do
  not surgically modify a third-party skill to dodge the scanner without
  knowing exactly which issues you are addressing.

- When the user directs a modification, fix the specific flagged issues, then
  re-scan and confirm those exact issue ids are gone. One passed scan never
  proves a different change would also pass.

## Alternatives for better results

- Baseline findings you have reviewed and accepted for your own skills with
  `skillspector baseline`, so re-scans surface only new findings.

- Remember the scanner runs static analysis only. A clean scan is necessary
  but not sufficient for a high-risk skill, so keep human judgment in the
  loop.

## Find related skills and connectors

- Use your agent framework's skill and connector search to find related
  skills before building something new.

- If nothing fits, look on the web for a maintained API or MCP server and
  set it up through your framework's connector flow, or build a custom
  connector.
