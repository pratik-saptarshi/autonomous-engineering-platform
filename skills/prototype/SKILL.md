# Prototype

Build a throwaway prototype to answer a design question fast. Use when the user wants to sanity-check whether a state model or logic feels right, or explore what something should look like.

## Pick a branch

- First identify which question is being answered, from the request or by asking:
  - "Does this logic or state model feel right?" → build a single shareable HTML file with free-play controls plus a guided walkthrough that pushes the state machine through hard-to-reason-about cases, drivable by a non-developer.
  - "What should this look like?" → generate several radically different variations, switchable in one view.

- If the question is genuinely ambiguous, default to whichever branch better matches the surrounding context and state the assumption up front.

## Rules for both branches

- **Throwaway from day one, clearly marked.** Keep prototypes under `~/workspace/prototypes/`, named so a casual reader sees they are not production.

- **Trivial to run.** Build with the artifact or widget tools so the user opens it directly; no setup, no thinking required.

- **No persistence by default.** State lives in memory. Persistence is what the prototype is checking, not something it should depend on.

- **Skip the polish.** No tests, no error handling beyond runnable, no abstractions. The point is to learn something fast.

- **Surface the state.** After every action or variant switch, show the full relevant state so the user sees what changed.

- **Capture it when done.** Fold any validated decision into the real work, then record the verdict and the question it settled alongside it. Delete the prototype once its answer is captured.
