# Subagent-Driven Development

## Know when to use this

- Use this when you have an implementation plan with mostly independent tasks and your human partner chose subagent-driven execution at the handoff.

- Prefer executing-plans when your partner chose inline execution. Do not use this without a written plan. Brainstorm or plan first.

## Set up the workspace and ledger

- Do the work in an isolated workspace. For file work in a git repo, set up a separate directory and never start on the main branch without explicit consent. For non-repo work, use a dedicated directory under `~/workspace/`.

- Conversation memory does not survive compaction, so track progress in a ledger file, not only in chat. Create one ledger per plan at `<workspace>/progress.md` with the plan path as its first line.

- When resuming, trust the ledger over your recollection. Tasks with a `Task <N>: complete` line are done. Do not re-dispatch them.

- Read the plan and its spec once at setup. Note the global constraints. Scan for conflicts between tasks that share files or interfaces, rule on each with the spec as the binding authority, and record every ruling in the ledger as `Ruling:` followed by what you decided, why, and what it costs if wrong.

## Keep executing without stalling

- Narrate at most one short line between tool calls. The ledger and tool results carry the record.

- Never pause to check in between tasks. Your partner asked you to execute the plan, so execute it.

- Decide conflicts, ambiguities, and plan defects yourself with the spec as authority. Record every ruling in the ledger and keep going. A wrong ruling costs visible rework, while a parked session costs your partner their day.

- Stop and ask only for irreversible or destructive operations, security-sensitive actions, side effects outside the workspace that norms say you ask about first, or a plan so broken that every path forward is a guess.

## Run the task loop

- Dispatch one fresh subagent per task with `subagent.spawn`. Write a brief that is self-contained: one line on where the task fits, the exact task text with exact values, interfaces and decisions from earlier tasks it needs, and the report contract stating what to return. Never paste the whole plan or accumulated history from earlier tasks.

- Never dispatch multiple implementation subagents in parallel against overlapping files. Batch small same-shape edits across files into one dispatch instead of one subagent per task.

- The implementer never dispatches its own subagents or reviewers. Review arrives from you after the report.

- Handle the report by its status. On done, describe the changes and dispatch a task reviewer subagent with the task text, the report, and the change description. On concerns, read them before proceeding. On blocked, change something real before re-dispatching: more context, a clearer brief, or a smaller task.

## Review every task

- Never skip the task review and never accept a report missing either verdict. Check both spec compliance and work quality.

- Give the reviewer the task text, the implementer's report, the exact changes, and the global constraints verbatim. Do not pre-judge findings for the reviewer and never tell it what not to flag.

- Run at most five fix rounds per task. Resume the original implementer for early rounds and dispatch a fresh one for later rounds. Each round ends with a scoped re-review of the fix. Record minor findings in the ledger as deferred and point the final review at them.

- When the cap trips with findings still open, adjudicate each yourself. Park contestable or non-load-bearing findings with a ruling. Rule on the smallest change for load-bearing ones and carry it into the next task. Record everything in the ledger.

- Mark the task complete in the ledger only when the review is clean or every open finding is parked with a ruling.

- Completion also requires mechanical evidence (AEP verification receipts). Before writing the `Task <N>: complete` line, the controller — never the implementer — runs `python3 <AEP checkout>/scripts/mechanical_verify.py verify --root <task worktree> --task <N> --receipts <workspace>/receipts.jsonl` and requires exit 0, or validates receipts it generated earlier in this run with `python3 <AEP checkout>/scripts/mechanical_verify.py check-receipts --receipts <workspace>/receipts.jsonl --task <N> --root <task worktree>` (exit 0 required). The root names the directory whose tree the task's verification commands cover — the worktree root when discovery finds the task's commands there, otherwise the subdirectory that does (in this repo, `<task worktree>/scripts`: root-level discovery finds no commands in the AEP repo itself). Use the same root for `verify`, for `check-receipts`, and as the segment's binding. Receipts segments are bound to the tree at their recorded HEAD, and completion requires a default-mode `check-receipts` PASS: the segment's bound head equals the worktree's current HEAD and the tree is clean. On resume, `check-receipts --receipts <workspace>/receipts.jsonl --task <N> --root <task worktree> --historical` validates a segment as evidence about its own recorded head, but `--historical` never completes a task by itself. Exit 2 from `check-receipts` means the segment is UNBOUND (pre-binding format) or UNVERIFIABLE (its recorded commit is unreadable); it is never evidence. An implementer-produced receipts file is an audit artifact, not evidence. Exit 2 from `verify` (no discoverable commands) must be recorded next to the completion line as `mechanical evidence: none available`; `verify` also exits 2 when it refuses a receipts file tracked by git inside the root — that is a refusal, not missing evidence: point `--receipts` at an untracked path and re-run.

## Run the final review and finish

- After the last task, dispatch one final reviewer over the whole body of work, pointing it at the ledger's deferred minors and parked findings.

- Fix its critical and important findings in one pass, each verified by a failing check first and a green suite after. Record each fix in the ledger. There is no second fix wave. Residual findings become rulings.

- Before finishing, collect every ledger line containing `Ruling:` into your final message under "Rulings I made", in order, each with what it costs if wrong, plus deferred minors under "Deferred minors".

- Clean up the plan workspace once the work has landed, leaving sibling workspaces alone.

## Avoid the rationalizations

- Close enough on spec compliance is not done. Fix it, hit the cap and adjudicate, or record the ruling. Those are the only exits.

- Fixing it yourself instead of dispatching pollutes your context and skips review. Resume the implementer.

- Ledger bookkeeping is not overhead. The ledger is what survives compaction.
