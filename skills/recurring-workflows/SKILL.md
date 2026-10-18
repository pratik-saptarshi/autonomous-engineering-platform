# Recurring Workflows

Design specs for the recurring loops in the user's life so they can be delegated to automation. A **loop** is a repeated pattern: a morning routine, inbox triage, a weekly review. Picturing life as loops within loops reveals how predictable its activities are, which is what makes them worth automating.

## Find loops worth specifying

- Interview the user about their world: the tools they use, the channels they process, their own terminology. Keep raw notes in `~/workspace/workflows/NOTES.md` and sharpen fuzzy terms into canonical ones as they surface.

- Propose loops they have not noticed. Run the discovery through the grilling discipline: relentless rounds, one frontier at a time, a recommended answer per question.

## Write the workflow spec

- One spec per workflow in `~/workspace/workflows/<name>.md`, using only the vocabulary the spec needs:
  - **Trigger**: what fires each run. An **event** (a new email, a new file) or a **schedule** (every morning). Event-triggering is usually more efficient.
  - **Checkpoint**: a human-in-the-loop point where the user verifies or decides. Some workflows have none.
  - **Push right**: defer the checkpoint as far as it will go. Do maximal work before involving the human, so they are asked once, late, with everything prepared.
  - **Brief**: what a checkpoint presents. A tight, decision-ready summary (what was produced, why, and a link to the asset), never raw output.

- Mandate nothing structural: a workflow needs no schedule, no checkpoint, and no AI unless the grilling shows it does.

- A spec is done when an implementer could build it without asking a single question. Grill until then; nothing is done while a question remains.

## Implement it

- Map the spec onto real automation: `cron.add` for schedules, hooks for events.

- Never create a scheduled job or hook without the user's explicit approval of the schedule and scope.
