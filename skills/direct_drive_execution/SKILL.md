# Direct-Drive Execution

## Keep coordination in the driving session

- Dispatch implementers and reviewers directly from the session that owns the plan, the ledger and the user relationship.

- Refuse to hand coordination to a coordinator subagent that would dispatch its own workers and wait on them in your place.

- Give each subagent one bounded task only, with a report file as its return path and no authority to spawn further agents.

- Record every dispatch in the ledger as you make it, with the task, the agent, the base commit and the expected report path.

## Detect a stall early

- Wait for dispatched work in bounded stretches and reconcile your live children against the ledger and `git log` at the end of each stretch.

- Declare a stall when two consecutive bounded waits pass with no report, no new commit and no ledger update from the work you are waiting on.

- Chase any child that finished without reporting before you dispatch anything new.

## Recover by changing shape

- Resume a stalled run from the ledger and `git log`, and never re-dispatch a task the ledger marks complete.

- Drive the remaining tasks directly for the rest of the run after the first nested coordinator stall, instead of appointing a replacement coordinator.

- Tell the user about the stall yourself in the session that owns the work, naming how long it lasted, the last ledger entry and the recovery you applied.

## Available connectors

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.

## Alternatives for better results

- Split an oversized plan into sequential phases that one driving session can finish, instead of adding a coordination layer to hold the whole plan.

- Use the overnight parallel lanes method when workstreams are truly independent, since it already carries per lane caps, fresh reviewers and a human merge gate.

- Shrink a task that keeps outliving its waits until its report fits one bounded dispatch, rather than lengthening the wait.
