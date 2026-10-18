# Verification Before Completion

## Follow the iron law

- Never claim work is complete, fixed, or passing without fresh verification evidence from this session. Violating the letter of this rule is violating its spirit.

- Before claiming any status or expressing satisfaction, identify the check that proves the claim, run it in full, read the complete output including the exit code, and confirm the output supports the claim. Skip any step and the claim is unverified.

- If the output does not confirm the claim, state the actual status with the evidence. If it does, state the claim with the evidence.

## Know what each claim requires

- Tests pass requires the test command output showing zero failures. A previous run or a belief it should pass is not enough.

- A check is clean requires running that exact check with zero errors. A different check passing proves nothing about this one.

- A bug is fixed requires reproducing the original symptom and watching it pass now. Changed code alone proves nothing.

- A regression test works requires watching it fail without the fix and pass with it. Passing once proves nothing.

- Delegated work is done requires inspecting what the subagent actually changed, such as the diff or the produced files. The subagent reporting success proves nothing.

- Requirements are met requires a line-by-line checklist against the plan or spec. Passing tests alone prove nothing about uncovered requirements.

## Watch for red flags

- Stop when you catch yourself writing should, probably, or seems to. Those words mean you have not verified.

- Stop when you feel satisfaction before verification. Do not write great, perfect, or done until the evidence is in.

- Never commit, publish, send, or move to the next task on an unverified claim.

- Never trust a subagent success report without checking its output yourself.

- Never treat a partial check as full verification.

- Never let tiredness or time pressure waive the rule. Exhaustion is not evidence.

## Answer the rationalizations

- When you think it should work now, run the verification.

- When you feel confident, remember confidence is not evidence.

- When you think just this once, remember there are no exceptions.

- When a related check passed, remember it is not the check you need.

- When the wording feels different enough that the rule might not apply, follow the spirit over the letter.
