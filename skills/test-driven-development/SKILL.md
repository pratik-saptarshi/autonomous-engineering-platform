# Test-Driven Development

## Obey the iron law

- Never write production code or scripts before a failing check exists. Code written before the check gets deleted and you start over. Violating the letter of these rules is violating their spirit.

- Use this for new features, bug fixes, refactors, and behavior changes in any code or script you write, including workflow scripts and artifact code.

- The only exceptions are throwaway prototypes and generated code, and those need your human partner's agreement first.

## Run the red-green-refactor cycle

- Red: write one minimal check showing what should happen. Test one behavior with a clear name, against real code rather than mocks.

- Verify red: run it and watch it fail. Confirm it fails for the expected reason, meaning the feature is missing, not that the check has a typo. A check that passes immediately is testing existing behavior. Fix the check.

- Green: write the simplest code that makes the check pass. Add no features, no refactoring of other code, and no improvements beyond the check.

- Verify green: run it and watch it pass, then run the project's full suite. A green single check is not a green suite. Report any failure you see by name, even one you did not cause.

- Refactor: clean up only after green. Remove duplication, improve names, and extract helpers, keeping every check green and adding no behavior. Then repeat the cycle for the next behavior.

## Write honest checks

- Keep each check minimal. If the name contains and, split it.

- Name the production change that would make the check fail before you write it.

- Assert on real behavior, never on mock behavior. Keep test-only code out of production code.

- Understand a dependency's side effects before mocking it, and mock only when unavoidable.

## Watch for red flags

- Stop when you catch yourself writing code before the check, planning to test after, or keeping early code as reference. Delete it and start over.

- Stop when a check passes on the first run without implementation behind it. You never proved it can catch the bug.

- Stop when you think this is too simple to test or that manual testing is faster. Simple code breaks, and manual testing leaves no record and cannot be rerun.

- Stop when you think deleting hours of untested work is wasteful. That time is spent either way. Keeping code you cannot trust is the waste.

- Stop when you think tests written after achieve the same thing. Tests written after answer what the code does, while tests written first answer what it should do.

## Verify before marking complete

- Confirm every new behavior has a check, you watched each check fail first for the expected reason, you wrote minimal code to pass, the full suite passes with pristine output, and edge cases are covered.

- When a bug appears, write the failing check that reproduces it before fixing, following the systematic-debugging skill for the investigation.
