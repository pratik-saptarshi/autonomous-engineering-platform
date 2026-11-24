---
name: disk-triage
version: 1.0.0
author: pratik-saptarshi
description: >-
  Survey storage on this VM read-only first, reconcile du against df,
  categorize every deletion candidate, delete only under an explicit owner
  ruling naming the category, and verify exclusions and physical reclaim
  afterwards. Use when disk pressure, EDQUOT, or accumulating Rust target/
  caches require a governed cleanup, or when planning deletions across
  clones and worktrees.
---

# Disk Triage

**Announce at start:** "I'm using the disk-triage skill to survey storage and govern deletions on this VM."

## When to Use

Disk use is rising, a programme has halted on EDQUOT, or build caches have accumulated across clones and worktrees and a cleanup is being considered. The goal is a survey the owner can rule on, deletions limited to exactly what was ruled, and an honest account of physical space reclaimed.

Do NOT use for: deleting a single known file at the owner's direct instruction (just delete it), or any deletion without a survey and ruling — an unruled cleanup is not authorized by this skill.

Establish the filesystem's accounting model before trusting any number: check whether the home filesystem is overlayfs or a compressing filesystem (e.g. btrfs with zstd) via `df -T` and `mount`. On overlayfs with `metacopy=on`, files report full `st_blocks` while consuming ~nothing, and compression shrinks real blocks — `du` can overstate physical occupancy several-fold. Trust `df` for capacity; use `du` only for ranking consumers. Recently written build output tracks `du` much more closely than old checked-out source. A recurring pressure source is build caches (e.g. Rust `target/` directories) accumulating across many clones and worktrees.

## Procedure

### Step 1 — Survey read-only first

- Record a `df` baseline before anything else.
- Rank consumers by `du`. Do not delete, move, or truncate anything in this step.
- Write the survey to the run's SDD directory under `~/.superpowers/sdd/<project>/`, never `/tmp` — a service restart wipes `/tmp`.
- State the `du`-vs-`df` reconciliation explicitly in the survey: total `du`, total `df` used, and why they differ (metacopy and compression, per the facts above). No later reader should mistake `du` for physical use.

### Step 2 — Categorize every candidate

Assign every candidate path to exactly one class:

- **(a) Regenerable build caches** — safe by construction: `target/` directories of stale worktrees and clones, toolchain caches, anything reproducible by rebuilding.
- **(c) Duplicates** — content provably held elsewhere, verified by checksum before listing (e.g. a tarball also in cloud backup).
- **(f) Ambiguous** — closed-programme logs and scratch that may still carry record value. Needs owner judgement; never present as safe.
- **KEEP — never a deletion candidate:** records, ledgers, and verdicts; live-lane trees; anything with uncommitted or unmirrored work. A tree holding a parked uncommitted change or a local-only branch is KEEP even if its build cache inside it is category (a) — the cache may go, the tree may not.

### Step 3 — Get a ruling

- Present the categories with refreshed, first-hand numbers. Figures from an earlier survey predate any intervening deletion round — re-measure before asking.
- Nothing is deleted without an explicit owner ruling naming the category.
- State holds and exclusions in the ruling ask itself, and honour them regardless of the answer. A ruling on one category does not extend to another.

### Step 4 — Execute only the ruled categories

- Measure `du` immediately before each deletion and record it.
- **Skip fail-closed:** skip any path whose state has changed against its survey description and report it — do not argue the change away. Example: logs touched within 24h suggest a live writer.
- Hold out shared and live tooling — package registries, browser caches — unless the ruling names them explicitly.

### Step 5 — Verify and log

- Confirm every deleted path is absent.
- Confirm every exclusion and KEEP tree is intact, including `git status` of trees with parked changes.
- Record `df` after against the Step 1 baseline. Report physical reclaim honestly: it will be far less than the `du` nominal when compression and metacopy inflation dominate — say so, and do not headline the `du` number.
- Log deletions in the survey directory: path, `du` before deletion, before/after `df`, and the verification result for each path.

### Step 6 — Emergency mode (EDQUOT halt)

When a running programme halts on quota, the order changes — preservation before freeing:

1. Stop. Record the exact uncommitted diff and the resume shape in the programme's ledger **before** freeing anything.
2. Free only an owner-authorized enumerated list: build caches and closed-programme scratch, never records.
3. Verify the in-flight diff survived exactly.
4. Resume under a fresh coordinator.

Precedent: 2026-11-19 — ~40G reclaimed from enumerated caches and scratch, both programmes' ledgers verified intact, the halted cycle's uncommitted fix survived exactly, and the cycle resumed.

## Evidence Standard

A completed triage reports: the survey path, the `df` baseline and closing `df`, the ruling received (categories named), paths deleted per category with their pre-deletion `du`, physical space reclaimed, any fail-closed skips, and verification that exclusions and KEEP trees are intact. Precedents: survey 2026-11-19 (`~/.superpowers/sdd/2026-11-19-disk-survey/survey.md`); category (a) executed 2026-11-20 — 34 paths, 68G physically reclaimed, `df` 99G→31G used; categories (c)+(f) executed the same day under a follow-on ruling — 7 paths, ~2G physical, where `du` had suggested ~8.6G.

## Stop Conditions

Stop and report: no owner ruling naming the category to delete; a candidate cannot be categorized or its duplicate claim cannot be checksum-verified; a path's state changed against its survey description (skip that path, per Step 4); an emergency free would touch records, ledgers, or verdicts; the in-flight diff in emergency mode does not verify as intact after freeing.
