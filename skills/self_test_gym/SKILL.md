# Self-Testing Gym

Adapted from the Self-Reinforced Testing Framework idea: treat a behavioral rule like code, run it against deterministic tests in isolation, and adopt only rules that verifiably pass. The native NeuroPlasticity runner needs Podman containers and a Rust toolchain, neither of which is available here, so this skill implements the same loop with trial subagents and `muse.exec` checks.

## Define the rule and the test

- Pick exactly one behavioral rule to test, such as "confirm the timezone before scheduling" or "never claim a booking succeeded without reading the confirmation".

- Write the rule in a scratch file at `~/workspace/self-tests/<test-name>/rule.md`, worded exactly as it would appear in your config.

- Write one deterministic check per expected behavior as a bash script in the same folder, runnable with `muse.exec`. Prefer checks a script can decide: file exists, JSON parses, output contains an exact string, exit code is zero.

- For judgments a script cannot make, write a rubric file with two to four yes/no questions instead of grading prose by feel.

- Keep the test small. One rule with two to four checks beats a broad suite you cannot interpret.

## Run the trial in isolation

- Spawn a trial subagent with `subagent.spawn` whose brief contains the candidate rule verbatim plus a task that exercises it. Never run the trial as yourself, since your own habits contaminate the result.

- Direct the subagent to write all artifacts to a scratch output folder, never to real user files.

- Run each check with `muse.exec` against the trial artifacts and record pass or fail per check in `results.md`.

- If a check errors for infrastructure reasons, such as a missing tool or a timeout, mark the run INDETERMINATE, fix the harness, and rerun. Never score a broken harness as a failure of the rule.

## Diagnose failures and write a scoped patch

- Read the trial transcript and the failing check output before theorizing, and quote the exact step where behavior diverged.

- Write the patch as a minimal rule change scoped to that failure: name the trigger, the required action, and the boundary. One failure earns one narrow rule, not a paragraph of general advice.

- If the failure came from ambiguous task wording rather than the rule, fix the test and rerun. Do not write rules that compensate for bad tests.

- Never soften a failing result. A run that failed, regressed, or stopped early is labeled FAILED in `results.md`, and its patch stays marked unverified.

## Adopt only what passes

- Rerun the full check suite with the patched rule in a fresh trial subagent, and adopt the rule only when every check passes.

- Store adopted rules in `~/workspace/self-tests/<test-name>/adopted.md` with the date, the checks run, and a reference to the transcript, so a later review can re-verify them.

- Propose config changes to `AGENTS.md`, `SOUL.md`, or `MEMORY.md` to the user with the evidence attached. Do not silently rewrite your own operating files.

- Treat safety, privacy, and permission rules as immutable. The gym optimizes work habits, never safeguards.
