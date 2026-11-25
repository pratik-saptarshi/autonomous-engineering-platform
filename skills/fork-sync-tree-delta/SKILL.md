---
name: fork-sync-tree-delta
description: Verify a fork sync PR by exact tree delta against the upstream tip, not by commit count or PR title..
---

> Installed live 2026-11-23 from pattern-mining candidate A4, approved by Pratik in the Pattern mining lane (pattern-mining report, 2026-11-23).

# Fork-Sync Verification by Exact Tree Delta

## Rule

A sync PR is verified when — and only when — its tree differs from the upstream tip tree in exactly the enumerated standing deltas, and nothing else. Commit counts, PR titles, and branch names are not evidence; a titled tip and the actual tree have diverged in practice.

## Procedure

1. Before building: list the standing deltas (files the fork deliberately carries differently, e.g. workflow files) with a one-line reason each, and record the expected patch (or content hash) for each delta file. This is the expected delta set — filenames alone are not verification.
2. Build the sync, then diff the resulting tree directly against the upstream tip tree (`git diff <upstream-tip> <sync-head> --stat` on trees, not log ranges).
3. Compare the full diff, not `--stat`: the changed-path set must match the expected delta set exactly (no extra files, no missing deltas), and each standing-delta file's actual diff must match its recorded expected patch. Any surprise — a file, or different content inside an allowed filename — stops the sync for investigation; it usually means the base was not the tip it claimed to be.
4. Run the repo's required checks on the exact head. Record: upstream tip SHA, sync head SHA, the delta file list, check results.
5. At merge readiness, re-check the upstream tip SHA: if it has advanced since verification, rebuild or re-verify against the new tip before merging. Merge remains the owner's per-PR call; verification does not arm or imply a merge.

## Boundary

`filing-upstream-prs` covers filing work upstream. This skill covers the fork-internal mirror sync and its verification only.

## Evidence

- NeuroStrata fork, PR #100 (2026-11-12): tree differing from upstream tip only in four standing workflow files.
- PR #114 / PR #139 (2026-11-20 / 11-22): the first construction exposed that PR #114's tree was actually built at an older upstream commit than its title named; PR #139 rebuilt and verified at exactly the 4-file delta.
