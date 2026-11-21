---
name: watch-loop-template
version: 1.0.1
author: pratik-saptarshi
description: >-
  Template for periodic watch loops that monitor an external surface (open
  PRs, fork divergence, live-vs-repo script drift) and report only on change:
  a seen-state watermark file, a silent first-run baseline, flag-on-change
  only, silent-when-clean, report-only authority by default, dark-window
  support, and delivered-advances / suppressed-holds marker discipline. Use
  when creating or revising a recurring watch such as pr-watch,
  aep-pr-comment-watch, fork-sync-check, or ops-watchdog-drift-check.
---

# Watch-Loop Template

A watch loop polls a surface on a cadence and speaks only when something changed. Its whole value is the discipline below; a watch that pages history, repeats itself, or acts beyond its grant is worse than no watch.

## State: one watermark file

- Keep a single state file per watch (JSON) recording, per watched item, the newest seen identifiers and timestamps (comment IDs, thread states, head SHAs, content hashes) plus a one-line run log.
- The state file is the watch's only memory between runs. Anything not written there will be re-reported or lost.
- The watermark names what has been *seen and handled*, never merely what existed at a wall-clock time — per-item markers survive items arriving out of order.

## First run: silent baseline

- When no state file exists, snapshot the current state of every watched item into the watermark and deliver nothing.
- History is never paged: pre-existing items are the baseline, not news, however alarming they look. They become reportable only when they change.

## Each run: diff, flag, report

- Fetch current state and diff it against the watermark. Only items newer than, or changed since, their marker are candidates.
- Flag on change only: a new comment, a state flip, a hash that moved, a check that turned. Unchanged items are not re-described.
- Silent when clean: if the diff is empty, deliver nothing at all. "All quiet" messages train the owner to ignore the watch.
- Report shape: per flagged item — what it is, what changed, the evidence link, and what (if anything) needs the owner's decision. End with a current-status line.

## Marker discipline

- A delivered report advances the watermark past every item it covered.
- A suppressed report does not advance the marker: if a run computed a report but did not deliver it (dark window, delivery failure), the items stay pending and the next delivered report still carries them. Never mark as reported what the owner never saw.
- Record the run in the log either way, so a silent run is distinguishable from a run that never happened.

## Delivered-once, never re-report

- An item already delivered is not re-reported unless its state materially changed. A repeat with no material change is noise, however important the item still is.
- Unchanged flags persist silently in the watermark and run log; they stay tracked without being re-delivered.
- Silent runs still update the watermark and the run log, so the record shows the watch ran and held the item, not that it missed it.

## Dark window

- A watch may declare a dark window (for example overnight hours). Runs inside it still observe and log, but deliver nothing and do not advance the marker.
- The first run after the window covers the whole gap, because the marker never moved.

## Authority: report-only by default

- A watch observes and reports. It does not fix, post, push, merge, or reconfigure unless the owner has explicitly granted that specific authority to that specific watch.
- Where a watch feeds a larger process (verification, remediation planning), state that hand-off in its spec; the watch itself still stops at the report.

## Watch-side verification protocol

- A watch does not merely relay reviewer findings. For each new actionable item, run intake verification at the PR's current head before reporting it as a finding.
- Reproduce where feasible, using the synthetic-reproduction triplet: the claim shape must exhibit the defect (e.g. exit 0 where it should be caught); a direct control must be caught (exit 2); and a precision control must NOT false-positive (exit 0). A claim that cannot clear the triplet is not confirmed.
- Classify each item CONFIRMED, REFUTED, or NEEDS-INFO, with concrete evidence (file:line, exit codes) — never a verdict on the reviewer's authority alone.
- Label every verdict with its proof depth: unit-reproduced, E2E-reproduced, or trace-only. A trace-only verdict is reported as trace-only, never dressed as a reproduction.
- For CONFIRMED items, draft the remediation plan and STOP. The watch makes no code changes, posts, pushes, or merges; execution gates on the owner's ruling.
- Precedent: the AEP PR-comment watch's ~108 in-window runs — attack exit 0 vs control 2, precision 0 across dozens of Codex P2 verifications.

## Self-terminating probe-by-attempt watcher

- When no read-only detection exists for an external toggle, the watcher's probe may be the operation itself — but only if the attempt is proven harmless while the toggle is off: verified to change no external state and to fail with a known code.
- The watcher stays silent while the probe fails with that known code. On success it performs the pending action, verifies the result, and REMOVES ITSELF.
- It also self-removes, with a report, if the watched objects merge or close first and the pending action is moot.
- It never performs the dangerous sibling operation (e.g. never `gh stack merge`); the probe authorizes only the one pending action it was set to complete.
- Precedent: the daily gh-stack watcher — probe `gh stack link 55 56` exits 9 while Stacked PRs is disabled; on enablement it would link, verify the bases, and remove itself.

## Instantiating a watch

Fill in, in the new watch's job definition:

- **Surface**: what is polled (repo + item type, file pair, fleet), with sources pinned explicitly.
- **Cadence**: interval, and the dark window if any.
- **Marker fields**: which per-item IDs/timestamps/hashes the watermark stores.
- **Flag conditions**: the exact changes that count as news.
- **Report destination and shape**: which chat, and the per-item format above.
- **Authority**: report-only, or the specific extra grant, quoted from the owner.

Existing instantiations: `pr-watch` (dap PR review threads, CI, auto-merge state), `aep-pr-comment-watch` (AEP PR comments feeding Verified Remediation Cycle intake), `fork-sync-check` (fork fleet divergence against a versioned baseline), `ops-watchdog-drift-check` (live watchdog script vs the repo `ops/` copy).
