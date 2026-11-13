---
name: fork-fleet-maintenance
version: 1.0.0
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

## Output shape

Per adjudication round, report: sync candidates approved (with license evidence), exclusions (with the license found), exceptions held for ruling, unknowns (with reasons), and any mirror resets performed (with the preserved `develop` heads). Fleet totals close the report: on-model / excluded / exception / unknown, against the last baseline.
