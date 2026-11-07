# Prompt Templates

This file contains the prompt skeletons referenced by `skills/overseer/SKILL.md`.
It is intentionally compact and public-safe: the skill file remains the source of
truth for orchestration behavior.

## Phase 2: Data Flow Tracer
Trace the important data paths, schemas, invariants, and boundary transforms.

## Phase 3: Independent Review
Review the work independently, with no cross-talk, and return findings with citations.

## Phase 4: Private Reflection
Re-read the source, rate confidence, and identify your most/least defensible findings.

## Phase 5: Debate
Respond to unresolved points only; call out new evidence and changed opinions.

## Phase 7: Blind Final
Give a final score, top issues, and recommendation without seeing other final scores.

## Phase 8: Completeness Audit
Look for missed edge cases, constants, and overlooked code paths.

## Phase 10: Claim Verification
Verify citations against source; mark verified, inaccurate, misattributed, hallucinated, or unverifiable.

## Phase 11: Severity Verification
Read the actual codebase, verify P0/P1 claims, and check for existing safety mechanisms.

## Phase 12b: Tier Refinement Advisor
Refine the draft tier table with supporting reasoning and suggested verification persona.

## Phase 13: Targeted Verification Agent
Verify one dispute/action item at a time, using the tiered budget and persona match.

## Phase 14: Supreme Judge
Arbitrate disagreements, validate coverage, and produce the final ruling.

## Phase 14.5: Post-Judge Verification
Re-check any judge-introduced P0/P1 claims against ground truth before report generation.

## Phase 15.2: Process History
Assemble a chronological, verbatim log of the run, including persona profiles.

## Phase 15.3: HTML Report Generation Prompt
Read the markdown report and process history from disk, then render a self-contained HTML dashboard. The binding rendering requirements live in this skill's `SKILL.md`, section "Phase 15.3: Interactive HTML Report" — read that section in full before rendering and follow it exactly. In summary, it mandates: a dashboard overview with stats row and charts; a Panel Gallery; expandable issue cards whose expanded state is the 10-section accordion (all 10 sections always present, with placeholders when empty); filtering by severity, tier, verdict, and epistemic label, plus sort controls; deep-linking, keyboard navigation, and expand/collapse-all controls; print styles; every Chart.js canvas wrapped in a height-bounded, position-relative div; the compressed-run banner when the source report carries one; and Tailwind CSS, Chart.js, and Prism.js loaded via CDN.

## Phase 16: Merge Agent Prompt
Deduplicate findings across runs, score stability, and produce the merged report.

## Required sections per phase output

The Phase 13.5 gate's required-headers check (SKILL.md, "Phase 13.5:
Pre-Judge Verification Gate") is defined here: one list per gated file
type. Every entry is the section's operative noun phrase, derived from
SKILL.md's section for that phase, the phase's prompt skeleton above, or
the gate text itself.

**Match semantics.** A required section is present when a header or
labeled block carries the entry's operative noun phrase, case-insensitive.
A multi-word phrase matches when its words appear in order within one
header, so "Score" matches "Final Score" or "Panel score". Alternatives
separated by `|` are satisfied by any one of them. An entry written as a
bracketed token (a severity tag, a classification label) matches that
literal token in the file's labeled content.

**Vocabulary entries.** An entry marked `(vocabulary)` in its description
names the label set for a per-item classification, not a set of outcomes
that must all occur: the entry is present when at least one label from
the set appears, and the gate fails if an item is classified with a
bracketed label outside the set. A file whose items all carry the same
label from the set is complete. Classifications are the labels the
report itself assigns to its items — for
`phase_10_claim_verification.md`, the labels in the verification table's
Verdict column (in a report without that table, the bracketed label
attached to each claim). Bracketed tokens quoted from other phases'
output or from the material under review are not classifications and
count neither way.

**Coverage.** These lists cover exactly the file types the gate's table
names. Phase 5 debate files for rounds 2 and 3 (`_phase_5_round2.md`,
`_phase_5_round3.md`) and the Phase 6 round summaries
(`phase_6_summary_*.md`) are NOT gated and have no list here.

### `reviewer_<name>_phase_3.md`
- `Score` — the review's score
- `Findings` — the findings section
- `[P0]|[P1]|[P2]|[P3]` — severity tags on the findings

### `reviewer_<name>_phase_4.md`
- `Confidence` — confidence rating per finding
- `New issues` — issues first noted in reflection
- `Most defensible` — the reviewer's most defensible finding
- `Least defensible` — the reviewer's least defensible finding

### `reviewer_<name>_phase_5_round1.md`
- `Unresolved points` — responses to the round's unresolved points
- `New evidence` — new evidence called out this round
- `Changed opinions` — opinions changed this round, with what changed them

### `reviewer_<name>_phase_7.md`
- `Score` — the final score (matches "Final Score")
- `Top points` — the top points / top issues
- `Recommendation` — the reviewer's recommendation
- `Verdict` — the one-line verdict

### `phase_8_audit.md`
- `Missed|Overlooked` — what the panel missed: overlooked details, edge cases, constants, code paths

### `phase_10_claim_verification.md`
- `[VERIFIED]|[INACCURATE]|[MISATTRIBUTED]|[HALLUCINATED]|[UNVERIFIABLE]` (vocabulary) — the classification of each claim: exactly one label from this set per claim (SKILL.md: "Classifies each as [VERIFIED], [INACCURATE], [MISATTRIBUTED], [HALLUCINATED], or [UNVERIFIABLE]"); any one label satisfies this entry, and a report whose claims all carry the same label is complete

### `phase_11_severity_verification.md`
- `Severity table` — the severity verification table (standard or extended)
- `[EXISTING_DEFECT]|[PLAN_RISK]` — the defect/risk classification of the verified findings
