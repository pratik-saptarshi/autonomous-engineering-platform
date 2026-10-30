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

- A local NeuroStrata MCP server is registered as the `custom.neurostrata` connector: search by vector distance (`array_distance`) with bounded graph-evidence expansion and capped usage/source boost over namespaced memories, with add, search, fetch, supersede, and archive operations. Its connector doc holds the exact commands.

- **NeuroStrata is the primary memory system for this entire runtime (Pratik's standing instruction, 2026-10-25).** Learnings, patterns, decisions, and project memory across ALL lanes are inscribed into the lane's NeuroStrata namespace as the work closes; retrieval starts from NeuroStrata when a session picks up a lane. User facts and preferences still surface in `~/MEMORY.md` (the harness loads it), but as the pointer/summary layer — the substantive learning is inscribed in NeuroStrata with a pointer back to its source.

- The two stores do not sync on their own. Inscription into NeuroStrata is the default, not the exception: if a learning is worth a file entry, it is worth a NeuroStrata entry first.

## Lesson-entry gate for NeuroStrata inscriptions (adopted 2026-10-26)

- Every NeuroStrata inscription must carry all three fields: **cue** (the situation that should trigger recall), **lesson** (the transferable claim), and **evidence** (a pointer to the artifact/record that proves it). Presence of all three is the minimum; write each field explicitly (labelled `Cue:` / `Lesson:` / `Evidence:` is the clearest form) so a later scorer does not have to infer them.
- Missing any field → do not inscribe yet. Rejection defers, never deletes: append the partial lesson, with the missing field named, to the lane's `pending-inscriptions.md` (`<lane goal>/hidden_files/pending-inscriptions.md`, created at first use) and name it in the close-out. Pending entries are revisited at the lane's next close-out; a pending entry completed there is inscribed then.
- Co-storage exclusion: NeuroStrata stores pointers by design, so Harness²'s artifact-co-storage half does not transfer and is not imitated — the evidence field is a pointer to the artifact/record, never a copy of the artifact stored alongside the lesson.
- Volume check (the gate's safety valve): the check is evaluated at every AEP lane close-out (the Task A6 cadence — the close-out evaluation defined in `docs/harness-method-trigger.md` in the AEP repo). The first close-out ≥30 days after this gate lands (landed 2026-10-26; ≥30 days = on or after 2026-11-25) compares inscription volume (all namespaces) against the 30 days before the gate landed. If no close-out occurs by day 45 (2026-12-10), the check becomes a standing item in the lane's session-start checklist until performed, with the AEP lane coordinator session as fallback owner. If volume dropped >50%, the gate auto-downgrades to warn-only (inscribe anyway, name the missing field in the close-out) and the downgrade is surfaced to Pratik as a decision item. The check and its outcome are recorded in the AEP goal timeline either way.
