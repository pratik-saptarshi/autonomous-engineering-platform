# Executing Plans

## Know when to use this

- Use this when you have a plan from the writing-plans skill and your human partner chose inline execution, or when no subagent tool is available. Never fabricate a dispatch.

- Prefer subagent-driven-development when your partner wants a review gate on every task or the plan is long enough that later tasks would run on compacted context.

- The plan already did the thinking. Execute it exactly, prove each step with a check you watched fail and then pass, and leave a record that survives your own forgetting.

## Set up the workspace and ledger

- Work in an isolated workspace and never on the main branch without explicit consent, following the same setup and ledger rules as the subagent-driven-development skill. The ledger format is shared, so a plan can change executors mid-flight.

- Read the plan and its spec once, note the global constraints, and create one tracking item per task.

- Load the test-driven-development skill now, before Task 1. It governs every step of every task below.

- Scan the plan for conflicts between tasks that share interfaces, rule on each with the spec as authority, and record the rulings in the ledger before starting Task 1.

## Work the task loop

- Take one task at a time. Read its full text for every task, including ones you remember, because memory holds a summary while the text holds the exact values.

- Follow the steps in order under test-driven-development. Watching the check fail is a step, not a formality. A check that passes before the implementation exists is a finding about the check.

- Every verification step has an expected output. Run it, read the output, and compare. When the code is wrong, use the systematic-debugging skill and never patch the symptom to match the expected output. When the plan is wrong, rule on the smallest change that satisfies the spec, ledger the ruling, and continue.

- Record or commit as the plan says, then verify the completion contract with the verification-before-completion skill: every named check ran in this task and you read the output, the final run passed, every expected output was compared against real output, and every deviation has a ruling in the ledger.
- **Git conventions** (standing rule): every commit message uses Conventional Commits (`type(scope): description`); every branch name follows `type/scope-short-description`. Commit as `Musebot-Astro <6238157+pratik-saptarshi@users.noreply.github.com>` unless the repo's AGENTS.md prescribes otherwise.

- Append the completion line to the ledger in the same turn as the work, then move to the next task without pausing to check in.

## Run the final review

- After the last task, get a fresh review of the whole body of work. With a subagent tool, dispatch a reviewer with the plan, the spec, the Review Focus section verbatim, and a pointer to the ledger's rulings. Without one, perform that review yourself as a separate pass and write `Final review: self-review` to the ledger, telling your partner a self-review is weaker than a fresh one.

- Sort the findings yourself. Critical and important findings enter one fix pass, each verified by a failing check first and a green suite after. Minor findings go to the ledger as deferred and to your final message. A finding you decide not to fix becomes a ruling that reaches your partner.

- There is no second fix pass and no re-review dispatch. The covering checks and the green suite are the verification.

## Finish cleanly

- Collect every `Ruling:` line into your final message under "Rulings I made" with what each costs if wrong, and every deferred minor under "Deferred minors".

- Delete the plan workspace once the work has landed, leaving sibling workspaces alone.

## Avoid the rationalizations

- You remember a summary, not the task text. Read it.

- The plan's code looking right does not replace watching the check fail. Run it.

- A plan defect you silently work around is a decision made in secret. Ledger the ruling.

- Tests should pass is not evidence. The contract requires the command and its output.
