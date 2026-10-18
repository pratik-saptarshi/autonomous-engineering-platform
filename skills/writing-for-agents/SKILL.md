# Writing for Agents

Write documents an agent consumes: a skill, an `AGENTS.md`, a doc reached by a pointer. The packaging differs; the writing does not. Use this when creating or editing skills, or modifying `AGENTS.md`, `SOUL.md`, or `MEMORY.md`.

## Context pointers

- A **context pointer** is a reference held in the agent's context that names out-of-context material and encodes when to reach it. A skill's description is one; a line in `AGENTS.md` naming a doc is the same object.

- The pointer's wording, not its target, decides when the agent reaches the material and how reliably. A must-have target behind a weakly worded pointer is a variance bug: sharpen the wording first, inline the material only if sharpening fails.

- A pointer states what the material is and lists the **branches** that trigger reaching it (distinct cases the document handles). Front-load the leading word, keep one trigger per branch, and cut identity the body already carries.

## The two loads

- Every document spends one of two budgets. **Context load** is the cost of always-loaded material on every turn: an `AGENTS.md` line, a skill description. **Cognitive load** is the cost on the human of knowing which documents exist.

- Material reached only through a pointer escapes context load at the price of the pointer's own line. Keep always-loaded pointers ruthlessly pruned.

## Information hierarchy

- Build from **steps** (ordered actions) and **reference** (definitions, rules consulted on demand), placed on a ladder: in-file steps first, in-file reference second, disclosed reference (a separate file behind a pointer) third.

- Push too little down and the top bloats; push too much and you hide what the agent needs. Inline what every branch needs; disclose what only some branches reach.

- **Co-location** keeps a concept's definition, rules, and caveats under one heading so reading one part brings its neighbors.

## Steps and completion criteria

- End every step on a **completion criterion** the agent can check. Vague bounds invite premature completion: the agent ends the step before it is genuinely done.

- Sharpen the bound first; it is local and cheap. Demand drives legwork: "every modified model accounted for" forces thorough work where "produce a change list" does not.

## Leading words

- A **leading word** is a compact concept from the model's pretraining that anchors a whole region of behavior in one token: _red_ for a binary failing state, _tight_ for a fast deterministic loop.

- Hunt restatements begging to collapse into a token. Coining your own works only with a clear definition, and it recruits no priors, so reach for an existing word first.

## Pruning

- Keep each meaning in a **single source of truth**. Duplication costs maintenance and inflates prominence past a meaning's real rank.

- The environment is a source of truth too: config files, directory layout, `--help` output. A document restating them is a cache; cache only what the agent cannot find by looking.

- Hunt **no-ops** sentence by sentence: an instruction the model already obeys by default pays load to say nothing. Delete the whole sentence when it fails the test.

- State the target behavior positively. Steering by prohibition drags the forbidden behavior into context; a ban reads half as an instruction to do the thing.
