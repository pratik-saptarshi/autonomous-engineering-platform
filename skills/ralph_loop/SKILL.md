# Ralph Loop

Adapted from the Ralph agent ecosystem: a backlog-gated autonomous loop. Each trigger (a cron tick or a manual "run the loop" request) processes at most one task from a markdown backlog, verifies it with evidence, updates the backlog, and stops. The loop never runs open-ended.

## Keep a file backlog

- Keep the backlog at `~/workspace/ralph/backlog.md`. One H2 per task with an ID prefix, metadata in HTML comments, then description and acceptance criteria.
- Use exactly this shape:

```markdown
## RALPH-001: Short title
<!-- status: to-do -->
<!-- labels: needs-planning -->
<!-- priority: high -->
<!-- depends-on: RALPH-003 -->

What to do and why.

### Acceptance Criteria
- [ ] First checkable outcome
- [ ] Second checkable outcome
```

- Status is one of `to-do`, `in-progress`, `in-review`, `done`. Labels are free-form; useful ones are `needs-planning`, `needs-tests`, `ralph-blocked`, `ralph-failed`, `needs-input`.
- The backlog file is the source of truth for status. Never track task status in a separate file.
- A task is blocked while any of its `depends-on` tasks is not `done`. Never pick a blocked task.

## Run one iteration

- Pick the next task with `python3 ~/workspace/ralph/bin/backlog.py next`. It prints the highest-priority unblocked `to-do` task as JSON. If it prints nothing, there is no work: stop the loop.
- Before spawning the worker, search the live NeuroStrata backend for relevant past learnings: run `neurostrata_search_memory` through the custom.neurostrata connector (`python3 ~/workspace/custom-connectors/custom.neurostrata/bin/client.py call-tool --name neurostrata_search_memory --arguments-file <json>` with `query` built from the task title and key terms) in the `global` namespace and any project namespace the task belongs to. Put up to 5 relevant hits in the subagent brief so the worker does not relearn known lessons.
- Mark the task `in-progress` in the backlog before doing anything else.
- Spawn one subagent with `subagent.spawn` carrying the role brief from `references/roles.md` and the full task text. Give it exactly one task and instruct it to stop when finished.
- One iteration does one task. If the task turns out larger than one slice, the subagent aborts and the planner re-scopes it in a later iteration. Never split a task mid-iteration.

## Match each phase to its skill

- Each role maps to an installed skill. Invoke the matching skill before the role's core work, not after.
- Planner: apply brainstorming when requirements are unclear, then writing-plans to structure the plan for a blind implementer.
- Implementer: apply test-driven-development. Write the failing check first and watch it fail, then write the minimal implementation.
- Reviewer: apply receiving-review. Verify every concern against the actual diff before accepting it, and push back with reasoning when a concern is wrong.
- Tester: apply verification-before-completion. Run the exact acceptance check, read the full output, and claim a pass only on evidence.
- Debugging anywhere in the loop: apply systematic-debugging. Reproduce first, form one hypothesis, fix once, then re-verify.
- The iron law binds every role: never advance a backlog status without verification evidence from this session.

## Conventions

- **Conventional Commits everywhere** (standing rule): every commit message uses `type(scope): description` (e.g. `fix(scripts): signal all daemon PIDs`). Every PR title uses the same format. Every branch name follows `type/scope-short-description` (e.g. `fix/scripts-watchdog-signal-all-daemon-pids`).
- **Commit identity**: author and committer are `Musebot-Astro <6238157+pratik-saptarshi@users.noreply.github.com>` unless the repo's own AGENTS.md prescribes a different identity — repo guidance outranks this default, the user outranks all.
- **NeuroStrata daemon is on-demand** (2026-10-17): the MCP client starts it lazily on first use; the watchdog stops it after 60 min idle. Do not assume it is running — the client handles startup. At the end of a run, you may stop it explicitly via `pkill -TERM -f '[n]eurostrata-mcp daemon'` (bracket trick required), but the idle sweeper covers a missed stop.
- When a repo has CI checks for these conventions, a failing check blocks the merge like any other required check. When it does not, follow the convention anyway — the check may be added later.

## Verify before advancing

- Every role verifies with evidence. The implementer runs the checks, the reviewer reads the diff, the tester exercises the acceptance criteria.
- Move status forward only on evidence: `to-do` to `in-progress` to `in-review` to `done`. A failed check moves the task back to `to-do` with a dated comment explaining the failure.
- Independent verification (standing rule, 2026-10-17): after an iteration is verified and marked done, spawn one independent verification subagent per iteration. Brief it with the task ID, title, full acceptance criteria, and the changed files/evidence — and instruct it to verify each criterion independently against the actual repo/environment state, without trusting the worker's report. It reports VERIFIED or lists failed criteria with evidence. Spawn it and continue immediately (non-blocking); collect completed verdicts for the run report. On failed criteria, add a focused fix task to the backlog (failure evidence as acceptance criteria), or note it in the report if it needs Dano's decision. The verifier is a second check, never a replacement for the worker's own verification.
- End every iteration by updating the backlog: set the status, append a dated comment describing what happened, and adjust labels such as `needs-tests` or `ralph-blocked` when they apply.
- Append each run to `~/workspace/ralph/runs.md` with the date, task ID, role used, and outcome in one line.

## Reflect and watch the loop

- After each iteration, update `~/workspace/ralph/learnings.md` with reusable operational knowledge: at most 15 one-line rules, each with a `(seen: N)` counter. Increment the counter when a pattern recurs, decrement it when a rule proves irrelevant, and drop rules that reach zero. Keep project-specific facts like commands and URLs. Drop one-off ticket details.
- When a learning proves durable beyond one task, promote it following the neurostrata_memory skill: check for contradictions with `muse.memory_search`, then record it in `~/MEMORY.md` or the daily note. Never leave a promoted rule only in learnings.md where future sessions will not search. Inscribe it to the live NeuroStrata backend too: run `neurostrata_add_memory` through the custom.neurostrata connector with a concise fact or rule (`memory_type` fact or rule), the task's namespace (`global` when the lesson applies broadly), and `project_root` set to the workspace. Do this for every iteration that produced a durable lesson, not just the failures.
- If iterations stall, make no progress, or burn effort on the same failure, stop the loop and report to the user instead of retrying. Three failed attempts on one task means human arbitration, not a fourth attempt.
