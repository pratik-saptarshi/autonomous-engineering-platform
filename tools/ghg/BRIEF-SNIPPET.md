# BRIEF-SNIPPET — ghg rules for agent briefs

Copy the block below into any brief that will touch GitHub. It is
the whole contract; the README (`tools/ghg/README.md`) is the
reference behind it.

```markdown
## GitHub calls go through ghg — no exceptions

- Set `GHG_ACTOR=<task-slug>` in your environment first. Calls
  are attributed by it.
- Watching a workflow run: use
  `ghg watch --repo OWNER/REPO --run ID` — never raw
  `gh run watch` (`ghg run` refuses it by name; it is the
  2026-10-24 incident vector).
- Every other GitHub call: `ghg run -- <gh args...>`, e.g.
  `ghg run -- pr view 12 --repo OWNER/REPO`.
- Multi-call publish flows: pre-flight EVERY gated step with
  `ghg check -- <gh args...>` before step 1. If a call is denied
  mid-flow anyway (exit 75), STOP and report the exact stage
  reached (branch pushed? PR created? auto-merge armed?) — a
  named, recoverable state, never a silent one.
- On exit 75 (budget denial): stop and report. Do not retry
  around the gate, and do not set `GHG_BYPASS=1` yourself —
  bypass is an operator decision, it is recorded, and it is
  reported by the scheduled drift check.
- ghg is an accounting control, not an authorization control:
  passing the gate is never permission to push, merge, or
  delete. The task's own authorization rules apply unchanged.
```

Notes for the brief writer (not part of the copy-paste block):

- The fleet entry point after the ghg branch merges is
  `~/go/bin/ghg` (a symlink to the AEP main checkout's
  `tools/ghg/bin/ghg`, created as a merge-time operator step).
  Until then, invoke the checkout's `tools/ghg/bin/ghg` by path.
- `ghg check` executes nothing and writes no ledger rows — it is
  always safe to pre-flight.
- `ghg status` shows current spend, headroom, bypass counts, and
  drift if a brief needs the budget picture before planning a
  publish flow.
