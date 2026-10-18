# Plan Review Integrator

Fold structured review findings into an implementation plan with full traceability. Use after a roundtable review, or any review with severity-rated findings, when the findings belong in the plan rather than scattered comments.

## Gather and extract

- Collect three inputs: the review report, the plan document, and domain context such as memory files, configs, and related docs. Domain context is what lets you catch a reviewer prescribing the wrong fix.

- If the review has no actionable findings, stop here: report that the plan is unchanged and skip the rest.

- Extract each finding with an ID, severity, source reviewer, one-line summary, full detail with citations, the reviewer's prescribed fix, and whether it was consensus, disputed, or unilateral.

## Cross-reference and classify

- Match each finding against the plan and categorize it: already addressed (the plan handles it and the reviewer missed it), gap (the plan should address it), correction (the plan addresses it but contains an error), new concern (affects scope or timeline), or pre-existing (valid but not introduced or worsened by the plan).

- Remember that panels often identify correct symptoms but prescribe wrong fixes. Validate every prescribed fix against domain constraints, override the fix when it is wrong, and record the override.

- Score actionability and groundedness for each finding from 0 to 1. Drop findings below 0.3 actionability, flag the 0.3 to 0.5 range for human review, and cap any finding with groundedness below 0.3 at MEDIUM severity regardless of its original rating.

- Classify with epistemic-weighted severity: a VERIFIED CRITICAL is a P0 must-fix, a SINGLE-SOURCE or DISPUTED CRITICAL is a P1 for human review, and a VERIFIED HIGH outranks a SINGLE-SOURCE CRITICAL. When in doubt, surface the conflict instead of auto-resolving.

## Apply edits with governance

- Respect the governance gates: a P0 or P1 touching security, privacy, data integrity, or destructive operations cannot be silently deferred, a fix that expands scope or timeline needs explicit user confirmation, and a disputed critical finding is never auto-applied.

- Apply the minimum necessary edit per finding, preserving the plan's voice and structure, and link each edit to its finding ID.

- After each substantive edit, re-read the surrounding section. If the edit breaks coherence, rephrase it first. If rephrasing fails, revert the edit and mark the finding as requiring manual integration. A flagged finding beats a corrupted plan.

- Keep edits sequential so rollback and coherence checks always see the current document state.

## Produce the traceability summary

- Present a table of every finding with its severity, category, and the action taken, plus statistics in this shape: total findings, must-fix count, bundled count, deferred count, informational count.

- Include the key decisions, such as why a reviewer fix was overridden, and a dissent ledger for disputed items with positions, evidence, and the decision owner.

- End with a final recommendation state: auto-applied when everything was clean, applied with caveats when caveats or dissent remain, human review required when a P0, P1, dispute, or scope expansion needs a decision, or blocked when a verified high-risk finding cannot be integrated safely.

## Available connectors

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.
