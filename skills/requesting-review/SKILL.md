# Requesting Review

## Know when to request it

- Request a review after each task in subagent-driven development, after completing a major deliverable, and before anything merges, publishes, or ships.

- Also request one when you are stuck and want a fresh perspective, or after fixing a complex problem.

- Never skip review because the work looks simple. Simple work carries simple bugs.

## Dispatch a reviewer subagent

- Dispatch a fresh subagent with `subagent.spawn`. A reviewer needs your work product, never your session history. Reviewing inline burns the context you need to keep driving the work.

- Give the reviewer a self-contained brief: a short description of what was built, the requirements or plan it should satisfy, and the exact changes to review, described as file paths or a diff, never as pasted history.

- State what the review must verdict: whether the work meets the requirements and whether the quality is acceptable. Ask for findings ordered by severity: critical, important, minor.

## Act on the findings

- Fix critical findings immediately and important findings before proceeding. Note minor findings in your ledger or task notes for later.

- Push back when the reviewer is wrong, with technical reasoning and evidence from the work itself. Do not argue from authority or comfort.

- Never proceed with unfixed important findings still open.
