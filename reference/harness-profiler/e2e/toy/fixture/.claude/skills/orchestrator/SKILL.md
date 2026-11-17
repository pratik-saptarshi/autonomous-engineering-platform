---
name: orchestrator
description: Runs every new story in stories.md through planning, implementation and a pull request. Use when asked to run the epic.
---
Read stories.md. For each story marked `[new]`, start the process-story subagent with the story's line as its prompt and wait for it.

Reply with each story's verdicts.
