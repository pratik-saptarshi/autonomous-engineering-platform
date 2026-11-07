---
name: filing-validated-issues
description: Use when filing a GitHub issue that carries evidence — a defect report, a blocked-work tracking issue, or an audit or advisory finding — especially on an upstream or public repository you do not control, or when the draft cites tool output, live repository state, or findings from an earlier investigation
---

# Filing Validated Issues

## Overview

An evidence-carrying issue is a public record other people will act on. Every claim in it must trace to a primary source gathered this run, and the draft must survive a fresh validator before it files.

**Core principle:** Consent first, evidence before prose, no filing without a validator's pass.

Rules marked **[fleet]** are this fleet's standing rules. Unmarked rules generalize.

## When to Use

- Defect reports, blocked-work tracking issues, audit/advisory findings, on any repo.
- The stricter the venue (upstream / public / someone else's repo), the less optional each gate is.

**Not for:** discussion posts, feature wishes with no evidence, or comments on existing issues (those need their own consent, but not this workflow).

## Gate 0 — Consent and Venue **[fleet]**

- An issue on a repo the owner does not control needs the owner's **per-action consent naming that filing** (this issue, this repo). Consent for a related PR, a prior issue, or "ship the docs" does not transfer. Offline owner + waiting maintainer = pressure, not consent.
- **Fork-first venue:** work lands on the owner's fork by default. Upstream is the exception, chosen when the defect is upstream-owned or the tracking record belongs upstream (e.g. advisories carried by upstream's own lockfile). A blocker located in a third-party dependency does **not** move the venue to that dependency's repo — file the tracking issue where the affected state lives, and name the blocker inside it.
- No consent → prepare the draft and records, report "ready pending consent", stop.

## Evidence Before Prose

Gather first, draft second. For every factual claim, have in hand this run:

- The primary output itself (resolver, audit, tree, test, scanner), not a summary of it — including your own earlier summary. Re-check the source or drop the claim.
- Live state re-verified read-only at draft time: branch tips, related PR/issue states and heads. Notes from this morning are stale until re-read; a sibling lane may have moved everything.
- Registry/index scans scoped exactly as performed — say "full scan of all N published versions" only if that is what ran.
- An item you have not run the checks for is not filed as an "unverified report". Run its checks, or leave it out and say why in your report to the owner.

## Draft Shape (the recipe — the filed body IS these parts, in order)

1. Title in the target repo's existing issue-title style (read recent issues first).
2. **[fleet]** Upstream-facing: line 1 is the autonomy disclaimer, verbatim, its own line:
   `***Verification and validation was carried out autonomously with periodic human reviews.***`
3. **Summary** — what the issue is, what kind it is (action item vs tracking point), and the environment line: tree/commit + commands + tool versions.
4. **Evidence table** — one row per item: item / current state / identifier(s) / threshold or patched floor.
5. **Per-item sections**, each with: dependency path or provenance; primary-source quotes (see Accuracy); exposure or impact assessment; what unblocks or resolves it; an **observable completion/close criterion** (a command output or state anyone can re-check).
6. **Proposed handling** — what is and is not being asked of the maintainer; any offer from this side is conditional ("will be offered when X lands") and promises no timeline; the close condition.
7. **Relations** — links to the PRs/issues that carry the rest of the record, so the full state is accounted for between them, with nothing double-counted.

## Accuracy Disciplines

These four rules caught real errors in the workflow's first run (upstream issue #58):

| Rule | Test before filing |
|---|---|
| "Verbatim" means character-verbatim | Punctuation, typography, or OCR differed at all → the quote is a transcription; drop the label or re-capture the source |
| Evidence belongs to the item it was gathered for | A grep/tree/scan run for item X says nothing about item Y — never write "both" from one item's run |
| Exposure claims state what the command shows | Empty inverted tree under named target/feature sets = "no compiled code path **found**" — never "not compiled", never "not reachable" |
| No stale live-state claims | Every tip, head, and PR state in the draft was re-read this run, at draft time |

## Validation Gate — Mandatory Before Filing

Spawn a **fresh subagent that took no part in drafting**, in **paperthin reviewing mode**. It validates the exact draft:

- Every factual claim against its primary source and live state
- Tone and professional quality (factual, no blame toward third parties)
- Overstatement scan (Accuracy table above, applied line by line)
- Gate correctness: the draft asks for nothing beyond what the consent covers and promises nothing the owner has not owned

Verdicts: **VALIDATED** / **VALIDATED-WITH-NOTES** / **REJECTED**.

- File only on VALIDATED.
- VALIDATED-WITH-NOTES: apply **every** note. A note that changes a factual claim → re-show the changed draft to a fresh validator for confirmation before filing.
- REJECTED: do not file. Report the reasons to the owner.

Self-review, a co-drafter's review, and "the evidence is in the log" are not this gate.

## Filing Mechanics **[fleet]**

- All GitHub via ghg. Pre-flight with the correctly formed check, then run:
  `GHG_ACTOR=<slug> ~/go/bin/ghg check -- issue create --repo <owner>/<repo> --title <title> --body-file <file> [--label <label>]`
  `GHG_ACTOR=<slug> ~/go/bin/ghg run -- issue create --repo <owner>/<repo> --title <title> --body-file <file> [--label <label>]`
  A `ghg check` that errors on syntax, or runs with no command, is **not** a pre-flight — nothing was checked.
- Exit 75 or 403 from ghg: stop, report the exact stage reached. Never set `GHG_BYPASS=1`; that is operator-only.
- Labels: only from the repo's existing label set (read it first), only an obviously fitting one, else none. Never invent a label. For a verified advisory/security finding, `security` (when it exists) is the fitting label — not a generic `dependencies`.
- After filing, verify live before reporting success: issue number, URL, state OPEN, and the rendered body intact — including line 1 and the evidence tables.

## Records and Report

- Save the final filed body to the working goal/project's `hidden_files/` (or the repo-appropriate records location).
- Append the outcome — issue number/URL + validator verdict — to the source investigation's log.
- Report to the owner: issue number/URL, validator verdict, every claim adjusted during validation, and any deviation (e.g. a push or filing route outside the standard path).

## Rationalizations — Stop When You Hear These

| Excuse | Reality |
|---|---|
| "The owner consented to the related PR — close enough" | Consent is per-action. A PR consent never covers an issue filing. |
| "The maintainer is waiting; filing now unblocks discussion" | Urgency is not consent, and an unvalidated filing is a public record you cannot unpublish. |
| "The summary says item Y is the same as X" | Summaries are not sources. Run Y's checks or leave Y out. |
| "The quote matches word-for-word, so 'verbatim' is fair" | Word-identical ≠ character-verbatim. One punctuation difference removes the label. |
| "My morning notes are probably still right" | Tips and PR states are claims. Re-read them at draft time or mark them unverified — and unverified claims don't file. |
| "The blocker is crate Z, so file on Z's repo" | Venue follows where the affected state lives and where the owner consented to file — not where the blocker sits. |
| "I ran ghg check (it printed an error, but I ran it)" | A syntax-erroring or empty check checked nothing. Form it correctly or there was no pre-flight. |
| "I'll ask the maintainer to prioritise — it helps our case" | The consent was awareness. Asking for action, or promising a follow-up date, exceeds the gate the validator must enforce. |

## Red Flags

- Drafting before gathering, and citing the log instead of the output
- A validator who drafted, co-drafted, or only skimmed the sources
- Any timeline, priority request, or third-party blame in Proposed handling
- Filing from a worktree/repo state you have not re-read this run
