---
name: watch-loop-template
version: 1.0.0
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

## Dark window

- A watch may declare a dark window (for example overnight hours). Runs inside it still observe and log, but deliver nothing and do not advance the marker.
- The first run after the window covers the whole gap, because the marker never moved.

## Authority: report-only by default

- A watch observes and reports. It does not fix, post, push, merge, or reconfigure unless the owner has explicitly granted that specific authority to that specific watch.
- Where a watch feeds a larger process (verification, remediation planning), state that hand-off in its spec; the watch itself still stops at the report.

## Instantiating a watch

Fill in, in the new watch's job definition:

- **Surface**: what is polled (repo + item type, file pair, fleet), with sources pinned explicitly.
- **Cadence**: interval, and the dark window if any.
- **Marker fields**: which per-item IDs/timestamps/hashes the watermark stores.
- **Flag conditions**: the exact changes that count as news.
- **Report destination and shape**: which chat, and the per-item format above.
- **Authority**: report-only, or the specific extra grant, quoted from the owner.

Existing instantiations: `pr-watch` (dap PR review threads, CI, auto-merge state), `aep-pr-comment-watch` (AEP PR comments feeding Verified Remediation Cycle intake), `fork-sync-check` (fork fleet divergence against a versioned baseline), `ops-watchdog-drift-check` (live watchdog script vs the repo `ops/` copy).
