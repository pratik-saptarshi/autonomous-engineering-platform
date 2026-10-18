# Writing Plans

## Announce and set up

- Announce at the start that you are using the writing-plans skill to create the implementation plan.

- Save the plan to `~/workspace/plans/YYYY-MM-DD-<feature-name>.md` unless your human partner prefers another location, such as a goal workspace.

## Check the scope

- If the requirements cover multiple independent subsystems, split them into separate plans, one per subsystem. Each plan should produce something independently verifiable on its own.

- If the requirements were never broken down this way, propose the split before writing.

## Map the structure first

- Before defining tasks, map out what will be created or modified and what each piece is responsible for. Lock decomposition decisions here.

- Design pieces with clear boundaries and one responsibility each. Prefer smaller focused pieces over large ones that do too much.

- In existing work, follow established patterns. Do not restructure unilaterally, but planning a split of something that has grown unwieldy is reasonable.

## Right-size the tasks

- Make each task the smallest unit that carries its own verification and is worth a review gate. Fold setup and scaffolding into the task whose deliverable needs them.

- Split only where a reviewer could meaningfully reject one task while approving its neighbor.

- Write each step as one action with a checkable result. A step is done when the implementer can write exactly one reasonable thing from it.

## Use the plan document header

- Start every plan with a header naming the goal in one sentence, the approach in two to three sentences, the tools and materials involved, and the path to the design or spec it implements.

- Copy project-wide constraints into a Global Constraints section with exact values. Every task implicitly includes this section.

- Add a Review Focus section listing the five input classes or failure modes the spec implies but no task verifies that are most likely to bite a real user, most likely first. Then add a check for each to the task that owns that area.

## Define each task completely

- For each task, name the exact files or artifacts it creates or modifies and the exact interfaces it consumes from earlier tasks and produces for later ones. An implementer who sees only their own task learns neighboring names and formats from these blocks.

- Write steps in verification order. For work with tests, that means write the failing check, watch it fail, implement the minimum, watch it pass, then record or commit.

- Give each verification step the exact command or check to run and the exact output that means it passed.

- Never write lines that decide nothing, such as TBD, handle edge cases, or add appropriate validation. Every line either pins a decision or it goes.

## Self-review the plan

- Run this checklist yourself against the requirements before handing the plan over. Check coverage by pointing at the task that implements each requirement and list any gaps.

- Scan every step. Each step must let the implementer produce exactly one reasonable thing. A line that decides nothing is a gap, and a step that writes out what the signature and checks already determine is transcription. Fix both.

- Check consistency of names, formats, and interfaces across tasks. A name that changes between tasks is a bug.

- Check the Review Focus items each have their check added to the owning task. An empty section means you checked and found none.

- Check proportion. A plan several times longer than the requirements it implements has written the work instead of planning it. Replace bodies with signatures, names, and checks until each step is still unambiguous.

- Fix what you find inline and move on. If a requirement has no task, add the task.

## Hand off for execution

- Link the plan for your human partner to read. If they already chose an execution method, ask them to confirm the plan captures what they want, wait for that review, then use the preserved method.

- If no method was chosen, ask them to review the plan and choose one. Offer subagent-driven execution, where a fresh subagent implements each task and another reviews it before the next starts, and inline execution, where you implement every task yourself in this session with one review at the end. Recommend one with a one-sentence reason tied to the plan, such as how much tasks depend on each other and what a shipped mistake would cost.

- When they choose subagent-driven, use the subagent-driven-development skill. When they choose inline, use the executing-plans skill.
