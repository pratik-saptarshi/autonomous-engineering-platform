# Dispatching Parallel Agents

## Decide whether work is parallelizable

- Dispatch parallel subagents when you face two or more independent tasks with no shared state and no sequential dependency. Independent investigations, independent research threads, and independent build tasks all qualify.

- Keep the work with a single agent when the tasks are related and fixing one might fix the others, when understanding needs the full system state, or when agents would interfere by editing the same files or resources.

## Group into independent domains

- Group the work by problem domain before dispatching. Name each domain by what is broken or what it must produce.

- Give each domain to exactly one subagent. One agent per domain keeps scopes from overlapping.

## Write a focused brief for each agent

- Make each brief self-contained. A subagent never inherits your session context, so paste in every fact, error message, file path, and constraint it needs. Nothing else.

- Keep the brief focused on one clear problem domain with one clear goal.

- State the constraints explicitly, such as which files it may touch and what it must not change.

- State exactly what to return, such as a summary of the root cause and the changes made.

- Keep briefs lean. Everything you paste into a dispatch stays in your context for the rest of the session, so hand over file paths rather than pasted file contents where a path will do.

## Dispatch in the same turn

- Issue all the `subagent.spawn` calls in a single turn so the agents run concurrently. One dispatch per turn runs them sequentially.

- Never dispatch multiple agents against the same files or the same shared resource at the same time.

## Integrate the results

- Read each returned summary and check whether any agents touched the same code.

- Run the full verification yourself after they return. Spot-check the work because agents can make systematic errors.

- Report the integrated result with evidence, following the verification-before-completion skill.

## Avoid the common mistakes

- Do not brief too broadly. Fix all the tests leaves an agent lost, while fix the failures in this one file keeps it focused.

- Do not brief without context. Paste the error messages and names, not just fix the race condition.

- Do not brief without constraints, or the agent may refactor everything around the problem.

- Do not accept a vague return. Ask for the root cause and the changes so you know what actually happened.
