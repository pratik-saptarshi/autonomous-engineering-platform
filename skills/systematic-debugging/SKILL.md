# Systematic Debugging

## Obey the iron law

- Never propose a fix before completing the root cause investigation. Symptom fixes are failure. Violating the letter of this process is violating its spirit.

- Use this for any bug, test failure, unexpected behavior, or performance problem. Use it especially under time pressure, when a quick fix looks obvious, or when previous fixes failed.

## Phase 1: Investigate the root cause

- Read error messages completely before anything else. Read stack traces to the end and note line numbers, file paths, and error codes.

- Reproduce the problem consistently. Record the exact steps. If you cannot trigger it reliably, gather more data instead of guessing.

- Check what changed recently. Look at diffs, recent commits, new dependencies, and configuration or environment differences.

- In multi-component systems, add diagnostic logging at each component boundary before proposing fixes. Log what enters and exits each component, then run once and let the evidence show which layer breaks.

- Trace bad values backward through the call stack. Ask where the bad value originates and what called it with that value. Keep tracing up until you find the source, then fix at the source and not at the symptom.

## Phase 2: Analyze the pattern

- Find working examples of similar code in the same project and compare them against the broken case.

- List every difference between working and broken, however small. Do not assume a difference cannot matter.

- Read any reference implementation completely before applying its pattern. Do not skim and adapt.

- Map the dependencies. Record what the broken piece needs, what it assumes, and what settings it depends on.

## Phase 3: Form and test one hypothesis

- State a single specific hypothesis in writing, naming the suspected root cause and the reason.

- Make the smallest possible change that tests that hypothesis, changing one variable at a time.

- If the test confirms it, move to Phase 4. If not, form a new hypothesis from the new information. Never stack more fixes on top of a failed one.

- When you do not understand something, say so plainly instead of guessing. Research more or ask for help.

## Phase 4: Implement the fix

- Write the simplest possible failing reproduction first, as an automated test when a framework exists and as a one-off script when it does not. Follow the test-driven-development skill for the test itself.

- Implement one fix that addresses the root cause. Make one change at a time with no bundled refactoring or while-you-are-here improvements.

- Verify the fix with the verification-before-completion skill. Confirm the reproduction passes, the rest of the suite is still green, and the original issue is resolved.

- When the root cause teaches something beyond this session (environment quirks, misleading errors, wrong-pattern signals, non-obvious fixes), inscribe it to the live NeuroStrata backend: run `neurostrata_add_memory` through the custom.neurostrata connector with the root cause and the fix as a concise rule, `memory_type` rule, and the project's namespace (`global` for environment-wide quirks). Future debugging sessions search the backend before investigating.

- If the fix does not work, count your attempts. Below three, return to Phase 1 with the new information. At three or more, stop fixing and question the architecture, because repeated fixes in different places signal a wrong pattern rather than a wrong hypothesis. Discuss the architecture with your human partner before attempting more fixes.

## Handle the no-root-cause case

- If systematic investigation shows the issue is truly environmental, timing dependent, or external, document what you investigated, implement appropriate handling such as retries or clear error messages, and add logging for the next investigation.

- Treat 95 percent of no-root-cause conclusions as incomplete investigation and keep digging first.

## Watch for red flags

- Stop when you think quick fix now and investigate later, or just try changing something to see. Return to Phase 1.

- Stop when you think you will skip the test and verify manually. Write the test.

- Stop when you think it is probably one thing and reach to fix it. Seeing symptoms is not understanding the cause.

- Stop when you are on fix attempt three or more and think one more try. Question the architecture instead.

- Listen for your human partner redirecting you with phrases like stop guessing or is that not happening. Those mean you assumed without verifying. Return to Phase 1.
