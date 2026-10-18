# Memory Hygiene

Distilled from NeuroStrata, a long-term memory system for AI agents. Its core insight is that memory fails when agents treat it as a dumping ground. You extract facts deliberately, inscribe them before finishing work, and keep retrieval clean.

## Extract facts proactively

- Listen for decisions, rules, corrections, and explanations of why something is done a certain way.

- Trigger phrases include "let's go with", "always use", "never do", "from now on", "actually let's change that to", and "the reason we do this is".

- Sort each fact into one of eight buckets before saving: system architecture and technical constraints, domain and business logic, workflows and processes, project goals, tooling and environment preferences, security and compliance, known anti-patterns and workarounds, or user preferences and interaction style.

- Save only durable facts. A one-off typo fix or a transient error that will never recur is not a memory.

## Inscribe before you finish

- Before you close a task, finish a report, or tell the user something is done, ask yourself what you learned: a command that worked, a hallucination you corrected, a bug root cause, or something that took many tool calls to figure out.

- If the answer is nothing durable, save nothing. If something qualifies, record it before you report completion.

- Treat this like a commit. Work is not done until the knowledge is inscribed.

## Harvest mistakes and expensive work

- When you or a subagent go down a wrong path, hallucinate an API, or hit a tooling trap, record the failed path and the correct resolution. Future sessions will have the same wrong instinct.

- When you spend many turns tracing a variable, reverse engineering a system, or mapping an undocumented module, save the synthesized conclusion immediately. Do not make the next session pay the same cost to relearn it.

## Supersede instead of contradicting

- Before saving, run `muse.memory_search` with two or three phrasings to check whether a related or contradictory memory already exists.

- If an old memory is outdated, record the new one so it explicitly names what it replaces, for example "replaces the earlier rule that X". The memory system keeps the replacement chain.

- Never leave two contradictory memories standing without marking which one wins.

## Route each memory to the right place

- Durable facts about the user go in `~/MEMORY.md` under Facts or Preferences. Keep entries tight and merge related lines instead of appending duplicates.

- Day-to-day detail goes in `~/memory/<YYYY-MM-DD>.md` as dated notes. Per-person or per-group context goes on their page under `~/memory/people/` or `~/memory/groups/`.

- Read the target file with `muse.read` before editing it with `muse.edit`, and keep standing files lean. Raw detail stays in daily notes, never in `~/MEMORY.md`.

## Keep retrieval working

- Write memories with the words a future search would use. Include concrete names, tools, and error strings, not just abstractions.

- Prefer pointers over dumps. If the full detail lives in a file or a daily note, the memory should say where in one line rather than copying the whole thing.

## Use the live backend for project memory

- A local NeuroStrata MCP server is registered as the `custom.neurostrata` connector: vector + full-text search over namespaced memories, with add, search, fetch, supersede, and archive operations. Its connector doc holds the exact commands.

- Keep user facts and preferences in the file system (`~/MEMORY.md`, daily notes). Use the MCP backend for project-scoped architectural rules, patterns, and anything worth retrieving by semantic search.

- The two stores do not sync on their own. When you inscribe something important in one, decide whether it belongs in the other too.
