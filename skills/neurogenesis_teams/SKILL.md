# Design High-Integrity Agent Teams

Assemble a small team of specialized subagents for work that is complex, high-stakes, or easy to get subtly wrong. Use the maker-checker pattern and adversarial review so mistakes get caught before they reach the user.

## Confirm the goal first

- Before building the team, confirm the goal and constraints with the user: offer a fast lane of three questions or a deeper interview, and do not start briefing subagents until the target is clear.

- Name the failure you are buying insurance against: the bad migration, the missed constraint, the fabricated result. If you cannot name it, you do not need a team.

- Stay solo for simple lookups, single-file edits, and anything where review would cost more than the mistake itself.

## Set the integrity baseline

- Paste the integrity blocks from `references/integrity-blocks.md` into every subagent brief: the pre-response integrity gate, the absolute invariants, and the evidence ledger requirement.

- Treat those blocks as non-negotiable. A subagent brief that cannot carry them is the wrong shape for the job.

- Run the integrity gate on your own final summary too: re-read any document that constrains the answer, quote only tool output you actually saw, and label guesses as guesses.

## Design the roles

- Keep three archetypes in mind: the maker who does the work, the checker who verifies it, and the critic who tries to break it.

- Give the maker a narrow role and one clear deliverable. A maker that both plans and judges its own plan will rubber-stamp itself.

- Brief the checker as read-only by instruction: it reads files and tool output, returns a verdict, and never mutates state. Enforcement here is by instruction rather than tool restriction, so state it explicitly in the brief.

- Add a critic only for high-stakes calls such as architecture, security, money, or compliance. Its job is falsification, not approval.

### Maker-checker verdict contract

- Require the checker to answer in strict JSON with one of three verdicts: APPROVED with a reason, REJECTED with a reason and a remediation, or NEEDS_HUMAN with a reason.

- Let the maker proceed only on APPROVED. On REJECTED it fixes the cited issue and resubmits. On NEEDS_HUMAN it stops and you bring the question to the user.

- Track rejections. After three failed rounds on the same deliverable, halt the loop, summarize the disagreement, and ask the user to arbitrate.

## Write handoff contracts

- Spawn each subagent with `subagent.spawn` and a brief built as a handoff contract, not a chatty request.

- State the input state: exact file paths, current status, and the constraints the work must respect.

- State the expected behavior: the concrete steps to take and what done looks like in observable terms.

- State the validation criteria: the exact check that proves success, such as tests to run or output to produce.

- State the failure protocol: what to do when a step fails. Revert and report beats blind retry.

- Forbid scope expansion in the brief: the subagent does exactly what the contract says and reports blockers instead of redesigning the plan.

## Distill domain heuristics

- Before briefing specialists, ground them with a few minutes of research: use `browser.search` to pull two or three authoritative sources for the domain, such as OWASP for web security or the official docs for the stack in use.

- Distill the findings into a short block: three anti-patterns to avoid, three edge cases or failure modes, and the concrete constraints with their sources.

- Paste that block into each specialist brief. Generic one-line context produces generic work.

## Run adversarial panels for big decisions

- For decisions with real downside, convene a panel: two or three subagents with opposing jobs, one defending the proposal, one attacking it, and one judging.

- Give the panel a strict JSON output contract with a verdict, a list of blockers, and a list of risks, so the result is machine-readable and honest.

- Let a security or compliance critic veto unilaterally. A veto must cite the violated rule, never a vibe.

- Record the panel verdict and its reasons alongside the decision so a later session can audit why the call was made.

## Keep the team honest over time

- Re-read the constraint documents when the project changes and update the briefs to match, instead of letting them drift.

- If a checker keeps rejecting, treat the pattern as a signal: the brief is usually wrong, not the subagent.
