---
name: fork-fleet-maintenance
version: 1.0.2
author: pratik-saptarshi
description: >-
  Adjudicate the fork fleet under the fork model: license gate before any
  upstream sync, same-name mirror discipline, named exceptions for forks
  with substantial owner work, and unknown states reported as unknown. Use
  when a fork-sync check surfaces candidates, divergence, or license
  questions, or when deciding whether and how a fork may be pulled forward
  to its upstream. The recurring detection half already runs as the weekly
  fork-sync-check cron job; this skill is the decision half it feeds.
---

# Fork Fleet Maintenance

**Announce at start:** "I'm using the fork-fleet-maintenance skill for this fork adjudication."

## The model

- Every fork's default branch is `develop`. All owner changes land there.
- Each fork keeps a same-name branch mirroring the upstream's default branch. The mirror is a reference copy — it is never developed on.
- Divergence of `develop` from the mirror is informational only; it is the expected state, not a problem to fix.
- Detection is already automated: the weekly `fork-sync-check` cron job compares every on-model fork against this model and reports changes from baseline. This skill covers only the adjudication that follows its reports — do not rebuild the check.

Calibration (2026-11-08 baseline): 146 of 158 forks on the model; 12 outside it on license grounds.

## Adjudication procedures

### 1. License gate — before any sync

No fork is pulled forward until its license position is settled:

- First check whether the upstream license has **changed** versus upstream's latest state; a relicense changes the answer even for a long-held fork.
- Accepted licenses: **MIT, Apache-2.0, CC0**.
- A license the automated detector cannot identify is not a verdict — deep-check it by reading the actual license text (LICENSE, COPYING, NOTICE, package metadata) before ruling.
- If upstream has **no license text anywhere**: pull the fork forward to latest, and add an MIT LICENSE to the fork together with a NOTICE recording that the MIT file covers only the fork's own contributions, not upstream-authored code.
- A fork whose upstream license sits outside the accepted set is **excluded**: it is listed as excluded and is never a sync candidate, however far behind it falls.

### 2. Mirror discipline

- The same-name mirror may be **reset to upstream** when it carries no owner work.
- **Behind-only** (mirror is an ancestor of upstream, nothing extra): a sync candidate — proceed under the license gate.
- **Diverged or ahead** (the mirror carries commits upstream lacks): an owner decision, never auto-resolved. Present the divergence and stop.
- Before any mirror reset, preserve the fork's `develop` at its pre-reset head (branch or recorded SHA) so the owner's work is recoverable regardless of what the reset does.

### 3. Named exceptions

- Forks where the owner may have done substantial design work of their own — a port is the canonical case (e.g. tachi-rust, the owner's Rust port of its upstream) — are never reset without an explicit owner ruling naming that repo, however clean the mirror arithmetic looks.
- When in doubt about whether a fork carries substantial owner work, treat it as an exception and ask. A wrong reset destroys work; a delayed sync costs nothing.

### 4. Unknown means unknown

- A fork whose state cannot be established (unreachable upstream, ambiguous license text, detector disagreement) is reported as **unknown**, with the reason. Never guess a state to complete a table, and never let an unknown silently become a candidate or an exclusion.

### 5. State file as scope — a missing fork is invisible

- The sync checker scopes to its state file; it does not freshly enumerate the fleet. A fork missing from the file is therefore invisible forever — no run ever flags it — and the omission self-perpetuates into every downstream board built from the file.
- When a fork is found missing, correct the state file **first**, before any adjudication that relies on fleet totals: verify its parent, default branch, and mirror heads live via the API, and record the **true** ahead/behind counts — never assume 0/0 for an unmeasured fork.
- Read-back verify the corrected entry before the next run, and restate the fleet totals it changes.
- Precedent: the nuclei fork, on-model since 2026-11-13, was missing from `fork-sync-check-state.json`; corrected to 0 ahead / 1 behind from live measurement, returning the fleet to 147 covered.

### 6. Standing-exception encoding

- A flagged divergence is not closed on a verbal "by design". First verify it live as by-design, first-hand: the head, the authorizing PR, and the integration history.
- Once verified, close the monitor item and encode the exception durably in the checker's Known section. Future runs record the fork in the state file only — never as a finding — so the same divergence is not re-flagged and re-adjudicated every cycle.
- Precedent: the NeuroStrata fork's `main`, diverged by design as the integration branch under the 2026-11-04 ruling; the exception was encoded and read-back verified on 2026-11-15.

### 7. Mirror-sync execution proof

- Syncing a mirror is not done when the push succeeds. Afterwards, prove the divergence from upstream is **exactly** the fork's intentional files — as an exact line multiset / patch identity against upstream, not a file list recalled from memory.
- Re-run the fork's governance assertions on the merged tree; a sync that passes arithmetic but fails governance is not complete.
- Precedent: the PR #114 syncs — divergence was exactly 3 workflow files with zero Rust divergence, the patch was line-identical across pins, and governance assertions passed 4/4 on the merged tree.

### 8. Integration-branch exception — merge, never reset

- The standing-exception fork (NeuroStrata `main`) is pulled forward by **merge**, never by reset or force. It carries owner work by design, so the mirror-reset rule in §2 does not apply to it.
- Merge rules: upstream wins where only upstream changed; the fork's changes stand where upstream did not touch them; any both-sides-changed conflict **stops** for the owner's ruling — never resolve one unilaterally.
- Verify build and test in a quiet window before pushing, and prove `behind_by=0` by API afterwards.
- Precedent: the fork-main pull lane, PR #114.

### 9. Baseline-edit hygiene — read back before you report

- Any baseline or state file a maintenance run edits — the sync checker's state file, a baseline record, a totals snapshot — is read back **in full** after the edit and verified field-by-field against the intended values, **before the run reports**. An edit taken on trust is not verified, however careful the writer was.
- Aggregate values (fleet totals, covered counts) are verified against an **independently derived count**, not against the edit's own arithmetic: a faithfully written but wrong total verifies against itself and proves nothing.
- A mismatch blocks the report: surface the discrepancy, correct the file, and re-verify the corrected file before any report relying on it is issued. This generalizes §5's corrected-entry read-back, which remains the minimum for that case.
- Precedent: a baseline edit once recorded 146 forks where the fleet held 147; the error survived because the edit was taken on trust.

### 10. Job scope drift — flag it, never execute past it

- Before relying on a `fork-sync-check` run's results, compare the job body's **stated scope** against the scope the job **actually checks**. Job bodies drift as fleets and rules change; the stated scope is a claim, not a fact.
- A disagreement is **flagged in the report** — stated scope, actual scope, and the difference named — and the drifted run's results are not adjudicated on as if they covered the stated scope until the drift is dispositioned (job body corrected, or the actual scope accepted by ruling). Never silently execute past a scope drift.

## Output shape

Per adjudication round, report: sync candidates approved (with license evidence), exclusions (with the license found), exceptions held for ruling, unknowns (with reasons), and any mirror resets performed (with the preserved `develop` heads). Fleet totals close the report: on-model / excluded / exception / unknown, against the last baseline. The report also names every baseline/state file edited this round with its read-back verification result, and any job body-vs-scope drift flag.
