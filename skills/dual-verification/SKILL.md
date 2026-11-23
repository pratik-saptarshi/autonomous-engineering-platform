---
name: dual-verification
description: Re-verify a delegated/external review verdict first-hand before publishing it..
---

> Installed live 2026-11-23 from pattern-mining candidate A2, approved by Pratik in the Pattern mining lane (pattern-mining report, 2026-11-23).

# Dual Verification of a Delegated Review Verdict

## Postulate

A delegated reviewer's verdict (ACCEPTED / CLEAN / PASS) is a claim, not a result. Nothing is published, pushed, or merged on the strength of it until the control plane re-checks it first-hand.

## Procedure

1. **Base reds, first-hand:** check out the base the reviewer used and reproduce the original failures yourself, in a scratch worktree. Attribute them: the failures must fail for exactly the charged reason, nothing else (debris-attribution control). If the review identifies no original failures (a clean review of new work), mark this leg not-applicable and record that determination — do not block on reproducing failures that do not exist.
2. **Head green, first-hand:** run the head's tests/refusal set yourself at the exact head SHA the reviewer reviewed. If the head's author or code is untrusted, run the head tests and the gate in a disposable, isolated worktree or sandbox with no credentials and restricted network — never in a credentialed checkout.
3. **Main-tree gate:** run the project's gate in the main tree, not the reviewer's worktree, checked out at the exact reviewed head SHA — a gate run at any other revision does not count. A gate the reviewer declined or was unable to run remains owed by this leg — say so explicitly.
4. **Detective checks:** confirm the reviewer changed nothing it shouldn't have: no push (remote ref unchanged), main tree untouched, no extra sessions/files.
5. **Non-blocking findings:** assess each one yourself — close by evidence (a probe, a source read) or carry it as an open item. Never silently drop a finding because the verdict was ACCEPTED.
6. **Publish only then.** Immediately before publishing, re-check the target head SHA; if it differs from the verified SHA, stop and re-verify — a recorded SHA does not make a stale verdict usable. Record: base SHA, head SHA, who verified, gate result, disposition of every non-blocking finding.

## Failure handling

Any leg failing stops publication. Report which leg, what differed from the reviewer's claim, and return the work to the owning lane — do not fix-and-publish in the verification leg unless the owner directs it.

## Boundary

`open-code-review-delegate` delegates the review; `subagent-driven-development` separates implementer/reviewer inside a task. This skill governs what happens *after* a delegated verdict returns, before its result is used.

## Evidence

replay-core / OpenChamber bridge waves 7, 8, 9 (2026-11-20, 11-21, 11-22): three bridge ACCEPTED verdicts, three dual verifications passed, each published only after this procedure.
