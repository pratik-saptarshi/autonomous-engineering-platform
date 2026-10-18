# Grilling

Stress-test the user's thinking about a plan, decision, or idea through a relentless interview. Use when the user wants their thinking challenged, or uses a "grill" trigger phrase. This is adversarial on purpose: brainstorming explores what they want, grilling attacks whether it holds up.

## Map the design tree

- Treat every decision as a branch: each choice opens the decisions that hang off it.

- Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask now without guessing at unheard answers.

- Ask the whole frontier in one round. Number each question, give your recommended answer, and word each question so "yes" accepts your recommendation.

## Run a round

- Format a round with one block per question: the question title and body (choices included where they help), followed by your recommended answer.

- Finding facts is your job, never the user's. When a frontier question needs a fact from the environment, dispatch a `subagent.spawn` to find it; do not ask the user for anything you could look up yourself.

- Do not block on the lookup: a running exploration is an unsettled prerequisite, so only questions downstream of it wait; ask the rest of the frontier now.

- Decisions belong to the user. Put each to them and wait for answers before the next round.

## Advance the frontier

- Each round of answers reshapes the tree: settled decisions push the frontier outward and unblock dependent questions.

- Recompute the frontier and ask the next round. A question whose answer depends on one still open this round belongs to a later round, not this one.

- The session ends when the frontier is empty: every branch visited, nothing silently assumed. Do not act on the plan until the user confirms you share an understanding.
