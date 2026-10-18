# Roundtable Review

Run a multi-agent adversarial review panel over code, plans, or docs when you need several independent perspectives before a decision, not one opinion. For a single quick review, use the requesting-review skill instead.

## Set up the panel

- Classify the work first: pure code, pure plan or design, mixed content with code snippets, or documentation. The classification picks the personas and the review mode.

- Use Precise mode for code: every finding must cite a file and line number or a code snippet, and findings without concrete evidence are demoted to UNVERIFIED. Use Exhaustive mode for plans and docs: broader risk identification is allowed without line citations.

- Pick four reviewers from the registry below, matching the classification. Always include the Code Quality Auditor when the work contains any code, SQL, or config snippets.

- Gather context before launching anyone: scan the reviewed files' parent directory for docs and configs, trace imports and cross-file references, and grep for existing safety mechanisms such as guards, idempotency checks, and dry-run flags. When a finding claims something is missing, the first check is whether it already exists.

- Check git state when reviewing a branch: find how many commits behind the default branch it is and what merged since, and warn reviewers to check the default branch before claiming code is missing.

Persona registry: Correctness Hawk (bugs, logic errors, edge cases), Architecture Critic (design, coupling, extensibility), Security Auditor (vulnerabilities, injection, auth), Devil's Advocate (challenges assumptions, proposes alternatives), Feasibility Analyst (timeline and delivery realism for plans), Stakeholder Advocate (business value and user impact), Risk Assessor (failure modes, dependencies, rollout risk), Code Quality Auditor (line-by-line scrutiny of snippets), Clarity Editor (readability for docs), Technical Accuracy Reviewer (factual claims in docs), Completeness Checker (missing sections and edge cases).

- Give each persona a reasoning strategy in its brief: systematic enumeration for correctness reviewers, backward reasoning from the desired outcome for architecture and feasibility, adversarial simulation ("imagine you are an attacker") for security and risk, analogical reasoning against known failure patterns for the Devil's Advocate, and first-principles questioning for stakeholder and clarity roles.

## Run independent review, then debate

- Launch all reviewers in parallel with `subagent.spawn` in a single turn, giving each the same work content, review mode, persona, and reasoning strategy. Reviewers must not see each other's output: isolation is what makes the panel an ensemble rather than one shared-context review.

- Have each reviewer write its full review to a state file under the task workspace and return only a short summary, so the orchestrator window stays usable.

- Run a private reflection round: each reviewer re-reads the source, rates confidence per finding as High, Medium, or Low, and names its most and least defensible findings.

- Run up to three debate rounds in parallel batches, each reviewer seeing the others' feedback plus unresolved points. Stop early when all disputes are minor or stylistic, and never run more than three rounds.

- After each round, summarize what resolved, what is still disputed with short source excerpts, and what is newly discovered. If a reviewer's claim cannot be traced to a source location, tag it as source not cited.

- Watch for sycophancy: if more than half of position changes move toward the majority without new evidence, say so in the next round's prompt.

- Finish with a blind final: each reviewer independently gives a score, its top three points, and a one-line verdict without seeing the others'.

## Verify claims before the judge

- Run a completeness audit with one dedicated subagent that hunts only for what the whole panel missed: overlooked details, edge cases, constants, and especially temporal scope errors. When a claim excludes a time period, count every instance in the full date range and verify each one is handled.

- Verify every citation: check each reviewer claim against the source and label it VERIFIED, INACCURATE, MISATTRIBUTED, HALLUCINATED, or UNVERIFIABLE.

- Verify severity by reading the actual code behind every P0 and P1: classify each as an existing defect in current code or a plan risk that only materializes if the plan is implemented. P0 requires an existing defect, and a plan risk is at most P1. Downgrade anything overstated.

- Label every surviving finding with an epistemic label: VERIFIED, CONSENSUS, SINGLE-SOURCE, UNVERIFIED, or DISPUTED. A VERIFIED HIGH outranks a SINGLE-SOURCE CRITICAL.

- For disputes that survive debate, dispatch one verification subagent per dispute point with a budget matched to the claim: a quick grep-level check for simple facts, multi-file tracing for logic disputes, and web research only for claims depending on external domain knowledge.

## Deliver the verdict and report

- Let a final judge subagent arbitrate everything, including the verification results. The judge must reference the verification tables when ruling on disagreements.

- Re-verify any P0 or P1 the judge itself introduces against ground truth before it lands in the report.

- Write two files in the task workspace: a markdown report with the verdict, findings by severity with epistemic labels, action items, and dissent notes, plus a process log with the per-phase summaries for auditability.

- Present the verdict and the top findings to the user with the evidence attached. Never present a unanimous panel as infallible: shared-model bias means all reviewers can be wrong the same way.

## Available connectors

- [GitHub](/opt/hatch/connectors/github/CONNECTOR.md) for reviewing pull requests and diffs.

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.
