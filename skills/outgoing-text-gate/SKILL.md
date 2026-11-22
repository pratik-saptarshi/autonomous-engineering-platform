---
name: outgoing-text-gate
version: 1.0.1
author: pratik-saptarshi
description: >-
  Composite publication gate for every text destined to be published —
  issue and PR descriptions, PR and issue comments, review comments.
  Orchestrates humanizer, factchk, and a conciseness pass under an
  independent validator, then checks mechanical rules before posting and
  verifies the live text after. Use before posting any material text to
  GitHub or another public surface, and for retro-pass audits of texts
  already published.
---

# Outgoing-Text Gate

**Announce at start:** "I'm using the outgoing-text-gate skill for this publication."

## When to Use

Use for every material text destined for publication: issue bodies, PR
descriptions, issue and PR comments, and review comments. Also use it in
Inward Audit Mode (below) on an existing PR body during a cycle.

Do NOT use for: private notes, internal plans, chat messages to the user, or
one-line acknowledgements with no factual content.

## Components

This skill is the composite orchestration only. It runs three existing
skills and adds validator independence, mechanical rules, and post-post
verification. It does not restate their internals — invoke each as written:

- `humanizer` — removes AI writing patterns from prose.
- `factchk` — traces every factual claim to a verified source.
- `debloat` — conciseness: reads for bloat and cuts what earns nothing.

## The Pipeline

```text
Draft → Humanize → Factcheck → Conciseness → Mechanical rules → Post → Verify live
```

### Step 1 — Draft

- The drafter writes the text for its destination: correct repo, correct
  thread or surface, Conventional Commits style for PR and issue titles.
- The draft stays unpublished until every later step passes.

### Step 2 — Humanizer pass

- Run `humanizer` over the full draft. Meaning and factual content do not
  change in this step; only the writing patterns do.

### Step 3 — Factcheck pass

- Run `factchk` over the humanized text: every factual claim — names,
  numbers, dates, line references, statuses, causal claims — is traced to a
  verified source available in the run's evidence.
- A claim that cannot be traced is **cut, not shipped**. It is never softened
  into vagueness and left in, and never kept on the drafter's say-so.

### Step 4 — Conciseness pass

- A validator runs `debloat` over the text: bloat, repetition, and
  throat-clearing are cut. Mechanical fixes found here are applied to the
  draft before posting, not noted for later.
- Disclosure: `debloat` is marked `disable-model-invocation: true`
  (user-invoked class) upstream. This gate invokes it deliberately, by
  name, through the independent validator (Step 5), on publication-bound
  text only — that explicit invocation is the intended use of this pass.
  It does not license invoking `debloat` as a standing reflex elsewhere.

### Step 5 — Validator independence

- Steps 2–4 are executed or audited by an **independent validator**, never
  solely by the drafter. The validator works from the draft plus the run's
  evidence, and reports per-step: passed, fixed (what changed), or blocked
  (what could not be verified).
- **Gate:** validator sign-off on all three passes, with every fix listed.

### Step 6 — Mechanical rules

Checked literally, every time, before posting:

- **Signature:** the text ends with a bottom signature line identifying
  Musebot-Astro (e.g. "— Musebot-Astro" or "Authored by Musebot-Astro.").
- **Identity scrubbing:** no personal name of the user anywhere in the text.
  Externally visible content uses synthetic or bot identities only.
- **No machine paths:** no local filesystem paths, hostnames, or local
  environment details.
- **Titles:** PR and issue titles follow Conventional Commits
  (`type(scope): description`).

- **Gate:** all four checks pass on the final text.

### Step 7 — Post and verify live

- Post the approved text. Then fetch the live text from the host and compare
  it against the approved draft. A mismatch is corrected by edit and
  re-verified — rendering and transport are not trusted.
- **Gate:** live text matches the approved draft.

## Retro-Pass Variant — Auditing Published Texts

Use when texts are already public and need the same standard applied after
the fact (for example, an audit sweep over a set of recently filed issues):

1. Fetch each published text and its live URL.
2. Run Steps 2–4 and Step 6 against it, producing a revised draft per text
   and a per-text list of what changed and why — factual corrections first,
   then conciseness and style.
3. **Owner approval gates any edit.** Present the revised drafts; nothing
   already published is altered without the owner's explicit approval of
   that text.
4. On approval, apply each edit on the host and re-verify the live text
   against the approved revision (Step 7).
5. Record the sweep in the run's plan directory: URLs, before/after verdicts,
   approvals, and verification results.

## Inward Audit Mode — Auditing an Existing PR Body During a Cycle

The gate also runs inward: on a PR body that already exists, mid-cycle,
when the body's claims need checking against what CI actually did.

1. **Extract every factual claim** in the body — statuses, counts, check
   outcomes, causal claims about why a leg passed or failed.
2. **Verify each claim against the actual CI job logs** — the per-job log
   output, not the summary rollup. A rollup's green/red does not establish
   what a job ran, skipped, or failed on.
3. **Grade each claim:**
   - **CONFIRMED** — the logs establish it as written.
   - **PARTIALLY CONFIRMED** — true as far as it goes, with a material
     omission; name the omission explicitly.
   - **REFUTED** — the logs contradict it.
4. **Reconcile local-gate wording against the CI leg.** A local gate result
   does not predict the corresponding CI leg; a body that conflates the two
   — stating a local result as if it were the CI outcome — is a correction,
   even when the local claim itself is accurate.
5. **Apply corrections as an artefact trio:** save the body as found
   (body-before), the corrected draft (body-after), and, after the edit is
   posted, the fetched live body (body-live) in the run's directory. The
   trio is the audit's record; an inward correction without it is not
   complete.
6. Precedents: PR #105's body cross-check graded claim 5.1 PARTIALLY
   CONFIRMED — materially incomplete for the CI leg — and the body was
   corrected; the #163/#184 cycles kept the body-before/body-after/body-live
   trio; panels on PRs #262/#263 graded body accuracy as findings (stale
   test counts, a carried-over sentence false at the current head).

## Hard Rules

- **No untraceable claims ship.** If a fact cannot be verified from the
  run's evidence, it is removed — the gate never publishes on confidence.
- **The drafter never self-approves.** Validator independence (Step 5) is
  structural, not a courtesy re-read by the author.
- **Approval is per-text.** Approval of one publication or one retro-pass
  revision does not carry over to another text, another repo, or a later
  edit of the same text.

## Stop Conditions

Stop and report: a load-bearing claim cannot be traced and cutting it would
change the text's purpose; the validator and drafter disagree on a fact and
the evidence does not settle it; the destination surface cannot be verified
after posting. Report what passed, what failed, and the exact claim or step
at issue — do not post a partially gated text.
