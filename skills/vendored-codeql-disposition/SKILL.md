---
name: vendored-codeql-disposition
version: 1.0.0
author: pratik-saptarshi
description: >-
  Disposition CodeQL alerts that originate in vendored snapshots of other
  repos: pin the attributed set from check annotations, classify each alert
  by origin repo, verify it first-hand, file confirmed defects and refuted
  false positives at the origin, label owned origins, then dismiss at the
  vendor repo with cited tracking. Use when a CodeQL check fails or files
  threads on a PR whose changed tree includes vendored code under
  reference/ or an equivalent snapshot directory.
---

# Vendored CodeQL Disposition

**Announce at start:** "I'm using the vendored-codeql-disposition skill for this CodeQL alert set."

## Why this exists

A repo that vendors snapshots of other repos (`reference/<name>/`, each with a `PROVENANCE.md` pin) gets those trees scanned by CodeQL as if they were first-party code. A large re-vendor diff makes pre-existing alerts in the snapshot look newly introduced by the PR, and the scanner's summary attributes them to the change. The alerts are real records, but the framing is wrong: the code is a pinned snapshot, it is never edited in place at the vendor repo, and its defects belong to the origin repo. This skill is the standing disposition procedure, executed first on AEP PR #144 (2026-11-12).

## The procedure

### 1. Pin the attributed set

- Take the alert set from the failing check run's **annotations**, and cross-check it against the code-scanning API on the PR ref (`refs/pull/<n>/head`, state open).
- Never trust the check summary's count or rule names — summaries paraphrase; annotations and the API don't. (On PR #144 the summary implied a URL-substring alert; the sixth attributed alert was actually a cleartext-logging hit in a different file.)
- Record per alert: number, rule id, scanner severity, file path, line.

### 2. Classify each alert by origin

- A path under a vendored tree (`reference/<name>/...`) belongs to that snapshot's origin repo — read it from the tree's `PROVENANCE.md`, not from memory.
- A first-party path belongs to the repo hosting the PR.
- The classification decides where everything downstream is filed.

### 3. Verify each alert first-hand

- Read the flagged code and judge the claim on its merits; reproduce where the rule admits it (timing runs for ReDoS, data-flow tracing for injection/logging rules). Never carry the scanner's framing into a filing.
- Expect most attributed alerts on a re-vendor to be false positives. The PR #144 census: 1 confirmed of 6 — a genuine polynomial ReDoS — and 5 refuted, all `rust/cleartext-logging` firing on test code: `assert!` failure messages and a test asserting that credentials do **not** leak.
- Record a verdict per alert: CONFIRMED or REFUTED, with the evidence (file:line reading, reproduction numbers) that settles it.

### 4. File at the origin

- **Confirmed defects:** open an issue on the origin repo with priority (scanner severity tempered by the verification result and real exploitability), severity, classification, and the reproduction evidence. Request the fix at the origin so a future re-vendor clears the alert downstream.
- **Refuted alerts:** open a false-positive classification record issue at the origin, plainly labelled as such in the title or first line — never present a refuted alert as a defect.
- **Upstream-behind-a-fork:** when the origin is itself a fork vendored from a true upstream, compare the flagged code against the upstream. If the defect exists byte-identical there, file on the true upstream too — on the owner's direction — so the fix lands where it propagates.
- Every filed text passes the outgoing-text gate (humanizer + factcheck + conciseness) and carries the publication signature.

### 5. Label owned origins

- On origin repos the owner owns, apply a helpful classification label to each filed issue; create `codeql-vendored` if no existing label fits.
- Never attempt labels on third-party repos.

### 6. Dismiss at the vendor repo, with cited tracking

- **Confirmed alerts:** dismiss as "won't fix", citing the origin issue link(s) and the pinned-snapshot rule — vendored trees are never edited in place; the alert clears when the origin fix is re-vendored.
- **Refuted alerts:** dismiss as "false positive", citing the classification record link.
- Dismissal comments are capped at 280 characters by GitHub — keep them terse and let the linked issues carry the detail.

### 7. Close the PR threads

- Reply to each alert's review thread on the PR with the same disposition (verdict, origin filing, dismissal rationale) and resolve the thread.

### 8. Verify the gate clears

- Confirm the CodeQL check re-concludes **SUCCESS** with the dismissals holding, and no attributed alert remains undispositioned, before any merge proceeds. A dismissal that the check does not honor is not a disposition — report it and stop.

## Stop conditions

Stop and ask the owner: a confirmed alert whose exploitability or severity is genuinely ambiguous; an origin repo that cannot be identified from its `PROVENANCE.md`; any proposal to edit vendored code in place (never permitted — that is what this skill exists to avoid).
