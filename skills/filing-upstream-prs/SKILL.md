---
name: filing-upstream-prs
description: Use when taking a change that landed or is landing on a fork and filing it as a pull request against the upstream repository — especially a public or maintainer-controlled upstream, or when the change carries separable extras, behavioural trades, or tests that touch real credential or state files
---

# Filing Upstream PRs

## Overview

An upstream PR asks a maintainer to adopt your fork's work into their canonical record. It files only when the owner consented to this filing, a live assessment says the change still fits upstream, and the body presents the finished decision — never the process that produced it.

**Core principle:** Consent first, assess against live upstream, file the outcome — never the deliberation, never an inflated claim.

Rules marked **[fleet]** are this fleet's standing rules. Unmarked rules generalize. Companion skill: **filing-validated-issues** (issues upstream); the gates and mechanics here mirror it.

## When to Use

- Porting a fork fix or feature to the upstream repository it forked from.
- Any PR against a repo the owner does not control.

**Not for:** PRs within the owner's own repos (use the repo's own pipeline), or upstream issues (use filing-validated-issues).

## Gate 0 — Venue and Consent **[fleet]**

- Work lands on the owner's fork by default. An upstream PR needs the owner's **explicit per-action consent naming this filing** (this change, this upstream). Consent for the fork PR, a related issue, or "we should upstream this eventually" does **not** transfer.
- That consent is conditioned on a positive Gate 1 assessment. Consent given, assessment fails → no filing; the deliverable is the assessment.
- No consent → prepare the branch and draft locally, report "ready pending consent", stop. A waiting maintainer, a fresh upstream release, and the owner's silence are pressure, not consent.

## Gate 1 — Assessment Against Live Upstream

Fetch upstream fresh and verify first-hand. The fork's mirror branch, tree, and memory are hypotheses, never evidence. All four must hold:

| # | Check | Evidence required |
|---|---|---|
| a | Target present | The defect / change target is still present and substantially identical in upstream's **current** code — cite upstream file, function, and line state at the fetched tip |
| b | Not already covered | Search upstream issues **and** PRs (open and closed) for the defect; nothing already files or fixes it |
| c | Invariants hold | Every invariant the fork design leans on still holds upstream — name them per change (e.g. an ordering guarantee in upstream's startup path), verified in upstream's code, not the fork's |
| d | Value transfers | The change bites upstream users the same way, through upstream's own startup / usage paths — not only via a fork-only surface |

Also check for a canonical upstream implementation of the concept; a port introducing a second one is a defect-in-waiting.

**Stop conditions:** divergence breaks the clean port; upstream already fixed or filed it; an invariant fails; value does not transfer. Any stop → the written assessment alone is the deliverable. Never improvise a redesign to save the filing.

## Ground Rules for Everything Upstream-Facing

**Outcomes, not deliberations.** Upstream material presents what the final fork version *is*: the chosen shape and its rationale, rejected alternatives in one line each where they change how a maintainer should judge the diff, and honest benefit claims. Internal deliberation machinery scoped to the fork work — adversarial panels, judges, wringers, review rounds, their verdicts and costs — is never narrated, cited, or leaned on upstream. The maintainer judges the diff and its evidence; process archaeology is not evidence.

**Honest claims.** Every benefit claim must survive re-derivation, at the strength stated, in the title, the commits, the body, and every later comment. Where an effect is a relocation rather than a reduction, say exactly that and nowhere stronger. Worked example: cutting a readiness-poll cap from 30s to 20s *"moves up to ~10 nominal seconds of waiting from process startup into the per-request startup wait, and surfaces a daemon-never-starts failure that much earlier; it does not reduce time-to-first-response on any start where the daemon eventually comes up."* A title or summary that upgrades this to "10s faster startup" fails this rule even if the body is honest.

## Port Shape

- Branch on the **fork**, based on the **live upstream default-branch tip** fetched at Gate 1 — never on the fork's base branch, never on the mirror.
- Commits in order, each independently reviewable:
  1. **Tests first** — discriminating: they fail *behaviourally* on the pre-fix upstream code (a test that passes either way is not evidence; state both rows — defect in: FAIL, fix in: PASS).
  2. **The fix.**
  3. **Separable extras, one commit each.**
- **Bundling constraint, in writing** (commit body and PR body): an extra that is only safe because the fix lands must never ship without the fix. The extra's commit may be dropped independently; the fix may never be dropped while keeping the extra.
- Conventional Commit subjects; the repo's author conventions. Baseline-relative cleanliness: no new warnings over upstream's base; format only the lines the change adds — never whole-file-format a repo that is not format-clean.
- Never regenerate a tracked, compiler-embedded artifact in CI to make a build pass — the compile is the check; if the port needs it, track it.

## Tests That Touch Real Credential or State Files

When a test must exercise a real operator file (a credential the code reads from its real path), any save/restore guard meets this floor:

- Snapshot **contents and permissions** (mode) — or absence — before the test touches anything.
- Every write — replacements and restore alike — is **atomic at the original restrictive mode**: sibling temp file created at 0600, renamed over the target. A plain truncate-write recreates a deleted 0600 file as 0644 under a normal umask, silently leaving the live credential world-readable after the test passes.
- Restore on drop, panic included, leaves the file exactly as found — bytes and mode — or absent if it was absent.
- One test pins the guard itself: contents **and** mode after a delete/recreate cycle, failing on a contents-only guard.
- Serialise tests sharing the real path (module lock or serial runner), so guards cannot snapshot each other's replacements.

## PR Body — The Recipe

The filed body IS these parts, in order:

1. Title in upstream's existing PR-title style (read recent merged PRs first); no claim in the title stronger than the body proves.
2. **[fleet]** Line 1 is the autonomy disclaimer, verbatim, its own line:
   `***Verification and validation was carried out autonomously with periodic human reviews.***`
3. **Problem** — the mechanism, explained against upstream's code with file/function references at the assessed tip; how it manifests for users.
4. **Fix** — the chosen shape and rationale; rejected alternatives in one line each where they matter.
5. **Separable extras** — each labelled, with its honest wording and its bundling constraint, and the note that its commit can be dropped without affecting the fix.
6. **Disclosed trades** — every behavioural trade of the fix, stated, not buried (worked example: deleting the token file mid-session now 401s a running proxy immediately, instead of coasting on the construction-time snapshot).
7. **Tests** — what each test pins and *why it discriminates* (which assertion fails on the pre-fix code).
8. **Evidence** — tree + command + environment for every claim. Fork-side results are labelled fork evidence; upstream CI is this PR's own venue; local success is never upgraded into fresh-checkout or CI proof.
9. **Provenance** — where the defect was found, where the change landed first (fork PR link), that this is a port of that landed version.

If a fact in the title or body later becomes false, edit the artifact itself and every surface carrying the claim — a correction left only in a comment is not a correction.

## Filing Mechanics **[fleet]**

- All GitHub via ghg. Pre-flight multi-call flows with `ghg check` before step 1; every other call via `ghg run -- <gh args...>`; CI via `ghg watch --repo <owner>/<repo> --run <id>`, never raw `gh run watch`:
  `GHG_ACTOR=<slug> ~/go/bin/ghg check -- pr create --repo <upstream> --base <default> --head <fork>:<branch> --title <title> --body-file <file>`
  `GHG_ACTOR=<slug> ~/go/bin/ghg run -- pr create --repo <upstream> --base <default> --head <fork>:<branch> --title <title> --body-file <file>`
  A `ghg check` that errors on syntax, or runs with no command, is **not** a pre-flight.
- Exit 75 or 403 from ghg: stop, report the exact stage reached. Never set `GHG_BYPASS=1`; that is operator-only.
- Push via the worktree's already-wired git route. Open the PR **READY** unless upstream's own conventions say otherwise.
- **Filing only.** Merging upstream is the maintainer's act, never the filer's — including when the maintainer invites you to merge it yourself, and including when you hold the technical access. Decline in one line and leave it open for them to land.

## After Filing

- **Census before any status claim**, on the exact head: head SHA, upstream CI on that SHA (gating vs report-only distinguished, failures baseline-compared against upstream's base), the complete untruncated thread list, automated-reviewer state. A reviewer that has not posted is a **no-show / pending — never a pass**.
- Status language: "filed (not merged)" until a merge actually lands. Tending, rebases, green CI, and a maintainer's "looks good" are not a merge and not approval to merge.
- Every review finding gets a per-thread disposition: **"Fixed in `<sha>`"** + locus + invariant preserved + the pinning test — or a written, evidenced rebuttal. A pointer to another PR is a disposition, not a resolution, until that PR lands or the maintainer accepts the pointer.
- Scope changes requested in review that go beyond the consented change re-enter Gate 0.

## Records and Report

- Save the assessment and the final filed body to the working goal/project's `hidden_files/` (or the repo-appropriate records location); append the outcome — PR number/URL + census — to the source investigation's log.
- Report to the owner: assessment verdict with its decisive evidence, PR number/URL, exact head, censused CI and reviewer state, and any deviation from this standard.

## Rationalizations — Stop When You Hear These

| Excuse | Reality |
|---|---|
| "The owner said 'upstream this eventually' — close enough" | Consent is per-action and names this filing. "Eventually" is a direction, not consent. |
| "The maintainer is online and waiting; delay loses the window" | Urgency is not consent; an unassessed filing is a public record you cannot unpublish. |
| "The fork's mirror branch shows the code byte-identical" | A mirror describes the last sync, not upstream now. Fetch and cite the live tip. |
| "It's ~10 seconds faster — the body explains the nuance" | A claim lives at the strength of its strongest surface. If the title overstates, the filing overstates. |
| "Describing our panel/judge process shows rigor" | Upstream judges the diff and its evidence. Fork-scoped deliberation is neither — it reads as process archaeology. |
| "The guard restores the contents — permissions are a detail" | A contents-only restore recreates a 0600 credential as 0644. The detail *is* the finding (a real Codex P1). |
| "CI is green and the maintainer said merge it" | Merging upstream is the maintainer's act. Access and invitation do not transfer it. |
| "No Codex review appeared, so no findings" | Absence is a no-show, recorded as pending — never a pass. |
| "Upstream refactored a bit; I can adapt as I go" | Divergence breaking the clean port is a stop condition. Deliverable: the assessment; a redesign is a new decision. |

## Red Flags

- Filing from a branch based on anything but the freshly fetched upstream tip
- Any surface (title, commit, comment) claiming a benefit the body only supports in weaker form
- A PR body that narrates fork-side panels, judges, or review rounds
- A test guard that writes a real credential file with a plain truncate-write
- Calling the PR merge-ready, approved, or merged on tending, green CI, or reviewer silence

## Worked Example (compact)

Fork PR #30 (NeuroStrata token race) → upstream, 2026-11-08. Gate 0: the owner's explicit request, conditioned on assessment. Gate 1: snapshot construction verified present in live upstream `server.rs`; no upstream issue/PR covered it; the token-creation-before-bind invariant verified in upstream's daemon startup; the 401-until-restart failure reaches upstream's MCP proxy users identically. Port: tests commit (appears-after-build, rotation — both fail pre-fix at the second forwarded request), Fix A commit (resolve the token at forward time), Fix B commit (readiness-poll cap 30s→20s) with the relocation wording and bundling constraint. Disclosed trade: mid-session token deletion 401s the running proxy. The test guard carries the contents+permissions, atomic-0600 standard — added after a Codex P1 caught the contents-only version on the fork PR.
