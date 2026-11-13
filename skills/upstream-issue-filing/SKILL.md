---
name: upstream-issue-filing
version: 1.0.0
author: pratik-saptarshi
description: >-
  File a defect issue in an upstream or fork repository only after the defect
  has been reproduced with controls, the correct target repo identified, and
  duplicates ruled out. Use when a verified bug belongs to another repo —
  a library binding vs its engine, a fork vs its upstream — and must be
  reported there with severity, priority, and a minimal reproduction.
---

# Upstream Issue Filing

**Announce at start:** "I'm using the upstream-issue-filing skill for this filing."

## When to Use

Use when a defect found during local work lives in code owned by another
repository and needs a durable, actionable report there: a binding layer vs
its engine, a fork vs its upstream, a vendored component vs its origin.

Do NOT use for: defects in the current repo (file locally), feature requests
with no observed defect, or candidates that are only plausible — see the
confirmed-only rule below.

## Prerequisites

- A working reproduction environment for the target component, at a known
  commit or version.
- The `outgoing-text-gate` skill — Stage 6 runs it before anything posts.
- Access to search the target repo's existing issues.

## The Stages

```
Stage 1: Reproduce      → defect shown with positive + negative controls
Stage 2: Target         → the repo where the defect lives is identified
Stage 3: Deduplicate    → existing issues searched three ways
Stage 4: Draft          → symptom, repro, expected vs actual, severity
Stage 5: Validate       → fresh reviewer checks every claim in the draft
Stage 6: File           → post through the outgoing-text gate
Stage 7: Verify live    → posted body fetched and compared byte-for-byte
Stage 8: Record         → filed record written to the run's plan directory
```

### Stage 1 — Reproduce with controls

- Build the smallest reproduction that shows the defect, and run it against
  the target at a recorded commit or version.
- Run both controls: a **positive control** (input that should trigger the
  defect path and does) and a **negative control** (nearby input that should
  not, and does not). A reproduction with no negative control has not isolated
  the defect.
- Record exact inputs, observed output, and environment. If the defect does
  not reproduce, stop: there is nothing to file.
- **Gate:** reproduction script and both control results are on record.

### Stage 2 — Determine the target repo

- File where the defect lives, not where it was noticed. Decide explicitly:
  binding vs engine, fork vs upstream, wrapper vs library.
- If a defect spans two repos (e.g. a binding precondition over an engine
  bug), file in the repo that owns the fix, and cross-reference the sibling
  repo in the issue body.
- **Gate:** one target repo named, with the ownership reasoning in one
  sentence.

### Stage 3 — Duplicate check

- Search the target repo's open and closed issues three ways before drafting:
  by **symptom** (the user-visible behaviour), by **component** (file, type,
  or function named in the reproduction), and by **error text** (exact strings
  from the observed output).
- If a matching issue exists, do not file a new one. Add the reproduction as
  a comment only if it adds new evidence, via Stage 6's gate, or stop.
- **Gate:** all three searches run; results recorded, match or no match.

### Stage 4 — Draft the issue

The draft contains, in this order:

1. **Symptom** — what goes wrong, in one or two sentences.
2. **Minimal reproduction** — the Stage 1 script or steps, with versions.
3. **Expected vs actual** — both stated plainly.
4. **Severity and priority** — each with its reasoning (impact, reach,
  data-loss or crash potential), not just a label.
5. **Classification** — defect class and the layer that owns it.
6. **Scoping notes** — what is explicitly NOT claimed: untested variants,
  unverified severities, sibling behaviours left unexamined.

- **Gate:** every section present; scoping notes name at least one thing the
  issue does not claim, or state that the claim is fully bounded.

### Stage 5 — Independent validator pass

- A fresh reviewer — never the drafter — checks every factual claim in the
  draft against the Stage 1–3 evidence: line references, version strings,
  reproduction outputs, severity reasoning.
- Every discrepancy is fixed in the draft or the claim is struck. This step
  exists because it has caught factual errors in our own drafts before
  filing; it is never skipped for a "simple" issue.
- **Gate:** validator reports zero unverified claims remaining.

### Stage 6 — File through the outgoing-text gate

- Run the `outgoing-text-gate` skill on the title and body (humanizer,
  factcheck, conciseness, mechanical rules), then post.
- Title follows Conventional Commits style where the target repo uses it.
- **Gate:** gate passed; issue URL returned by the host.

### Stage 7 — Byte-verify the live text

- Fetch the posted issue body from the host and compare it against the
  approved draft. Rendering or transport can alter text; a mismatch is
  corrected by edit and re-verified, never assumed away.
- **Gate:** live body matches the approved draft byte-for-byte.

### Stage 8 — Write the filed record

- In the run's plan directory, record: issue URL, title and body as filed,
  target repo and commit/version, reproduction and control evidence pointers,
  validator outcome, and any cross-references to sibling repos.
- **Gate:** record file exists and names the live URL.

## Hard Rules

- **Confirmed-only filing.** A defect is filed only after Stage 1
  reproduction. Plausible candidates are parked in the run's notes — never
  filed, and never mentioned in a filed issue as if they were findings.
- **Identity scrubbing.** Filed text uses only synthetic or bot identities.
  Never include the user's personal name, local machine paths, or local
  environment details in an issue.
- **Signature.** Every filed issue ends with the bottom signature line
  identifying Musebot-Astro (e.g. "— Musebot-Astro").
- **No scope inflation.** The filed claim is exactly the reproduced claim.
  Adjacent suspicions found during the work go to the run's notes, not the
  issue.

## Stop Conditions

Stop and report: the defect does not reproduce; a duplicate already covers
it; the target repo cannot be determined between two owners; the validator
and drafter disagree on a factual claim and the evidence does not settle it.
In each case, report what was established and what is missing — do not file
a partial or speculative issue to close the task.
