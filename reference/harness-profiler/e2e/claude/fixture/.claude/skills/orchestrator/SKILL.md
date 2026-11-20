---
name: orchestrator
description: Runs every new story in stories.md through planning and implementation. Use when asked to run the epic.
---
Do these in order:
1. Start the watcher subagent with `run_in_background: true`. Do not read stories.md yourself; the watcher finds the new stories.
2. Wait until the watcher reports back.
3. For each story the watcher reported: use the planner skill, then the implementor skill.

Reply with each story's verdict.
