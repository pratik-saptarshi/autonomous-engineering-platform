# Agent Operations

Distilled from the 12-factor agents principles (humanlayer/12-factor-agents, CC BY-SA 4.0), adapted for Muse. It covers the operational factors not handled by other skills: gather-before-act, deliberate context assembly, structured human contact, compact failure handling, and deterministic control flow.

Factors already covered elsewhere: small focused agents live in dispatching-parallel-agents, memory as the state store lives in neurostrata_memory, triggers and schedules live in recurring-workflows, prompt craft lives in writing-for-agents.

## Gather context before acting

- Before starting a task, fetch everything you are likely to need: read the relevant files, search memory with `muse.memory_search`, and check the calendar or inbox when the task touches them.

- Do not discover missing context mid-task. If the first step obviously needs a file, read it before planning, not after the plan stalls.

- Keep gathered context dense. Summarize long outputs into the few facts the task needs instead of pasting raw dumps.

- When a subagent will do the work, put the gathered context in its brief. Never make it re-fetch what you already hold.

## Contact the human with structure

- Ask the user when the task is ambiguous, irreversible, or expensive, and only then. Routine reversible steps do not need permission.

- For bounded choices, use `muse.create_options` with two or three concrete replies instead of an open question.

- Batch related questions into one message instead of drip-feeding them across turns.

- Before any irreversible action such as sending, buying, deleting, or publishing, state exactly what will happen and wait for explicit approval. Approval of a preview covers that preview only.

- Match urgency to the interruption. Routine questions ride along with the next update, while blocking decisions get asked immediately.

## Fail compactly, then escalate

- When a tool call fails, read the error and retry with a fix, but never paste the raw stack trace back into your reasoning. Carry forward a one-line summary of what failed and why.

- Cap retries at three attempts for the same call. A fourth identical attempt is not persistence, it is a loop.

- After the cap, change strategy: try a different tool or route, and if none exists, escalate to the user with what you tried and what you need.

- Once an error is resolved, drop it from your working context. Do not keep narrating past failures.

## Keep control flow deterministic

- You decide the next step, and deterministic mechanisms execute the repetition. Anything that must happen on a schedule or in a fixed sequence belongs in `cron.add`, hooks, or a workflow, not in your working memory.

- For handoffs between subagents, define the expected output shape up front: fields, format, and file path. Vague briefs produce vague results.

- Separate selection from invocation for high-stakes actions: decide what to do, present it for approval, then do it. Never merge deciding and doing into one step.

- Record durable state in the designated stores as you go, using todo lists, tracking items, and goal workspaces, so an interrupted run can resume instead of restarting.
