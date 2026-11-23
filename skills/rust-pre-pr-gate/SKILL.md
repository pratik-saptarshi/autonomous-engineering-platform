---
name: rust-pre-pr-gate
version: 1.0.2
author: pratik-saptarshi
description: >-
  The standing pre-PR gate for Rust repos: before opening or pushing to a PR,
  run cargo fmt, clippy, deny, audit, and a Windows-target check via
  ~/workspace/bin/rust-pre-pr-gate.sh, installed as the pre-push hook in every
  Rust clone. Use before any push or PR in a Rust repository, and when setting
  up a new Rust clone.
---

# Rust Pre-PR Gate

Standing rule (owner-directed, 2026-11-10): before opening or pushing to a PR in any Rust repo, run the gate so CI passes cleanly on the first attempt. The gate is the script `~/workspace/bin/rust-pre-pr-gate.sh`; this skill is its calibration record.

## The five legs

| Leg | Command (via the script) | Calibration |
|-----|--------------------------|-------------|
| fmt | `cargo fmt --all -- --check` | **Blocking** |
| clippy | `cargo clippy --all-targets --locked` | Report-only until its baseline is remediated |
| deny | `cargo deny check` | Report-only until its baseline is remediated |
| audit | `cargo audit` | **Blocking**, with the plateau ignores below |
| windows | `cargo check --all-targets --locked --target x86_64-pc-windows-gnu` | **Blocking** when the toolchain is present |

- The audit leg ignores exactly two advisories: RUSTSEC-2026-0194 and RUSTSEC-2026-0195, the owner-accepted quick-xml plateau. Any other advisory blocks. Remove the ignores when the plateau clears — do not add new ones without an owner ruling.
- The Windows leg is a cross-compile check (the local stand-in for CI's `test (windows-latest)` job): it compiles the tree for Windows but does not execute tests there. A missing mingw toolchain or uninstalled target records TOOLCHAIN-MISSING, not a pass.
- `GATE_FULL=1` makes all five legs blocking — the end state once the clippy and deny baselines are remediated. `GATE_SOFT=1` makes the run informational; `GATE_SKIP=` and `--only` select legs for a focused re-run.

## Install in every new Rust clone

The script is the pre-push hook. On cloning or creating a Rust repo, install it before the first push:

```bash
ln -s ~/workspace/bin/rust-pre-pr-gate.sh <clone>/.git/hooks/pre-push
```

A clone without the hook is a gate that exists only on paper; check for the symlink when setting up the clone's local development environment.

## Run discipline

- Run the gate against the exact tree being pushed, from the repo root; the script refuses to run outside a Rust repo root.
- Fix blocking failures and re-run; report-only failures (clippy, deny) are surfaced in the PR context, not silently dropped and not treated as blockers until their baselines are remediated.
- **No concurrent cargo builds during long gate runs.** This VM has ~8 GB RAM; a release link was OOM-killed under concurrent cargo load on 2026-11-07. Before starting a long build or gate, check for running cargo/rustc processes and wait for a quiet window rather than racing another lane's build.

## The baseline-record verdict

- When the gate FAILS overall but every failing leg is proven identical-or-better against the pristine base head — the same failure reproduced on base, byte-compared where possible (fmt backlog counts, identical advisory set, the windows ort-sys prebuilt absence reproduced on base) — record the result explicitly as a BASELINE RECORD, alongside the judge's gate verdict.

- A baseline record is not a pass and not a merge-readiness finding. Never silently waive a failing leg, and never report a baseline record as PASS.

- Precedents: upstream PR #184's cycle gate record vs pristine c1fba663; PR #206 remediation "pre-PR gate baseline record"; the checkpoint fix's windows leg reproduced identically on pristine develop.

- Baselines are recorded per tree, not globally: each tree carries its own denied/advisory baseline set, and a failure attributable only to that tree's baselined set produces a baseline record for that tree — never a plain PASS. Worked values: the sled tree's denied set is empty (`{}`); the src-tauri tree's denied set is `{RUSTSEC-2026-0543}`. A set recorded for one tree does not baseline a failure in another tree, and the global quick-xml plateau ignores above are separate from any tree's own set.

- When a leg is baselined because its configured target has no prebuilt for the tree's toolchain, the baseline record names that target/toolchain cause — generalising the windows ort-sys prebuilt absence above from an example into a requirement. A baseline record for such a leg that does not name the cause is incomplete.

- Gate-fidelity cross-check: before any PR push, compare each local gate leg against CI's equivalent on the same tree. When a local leg passes while CI's equivalent fails on the same tree — the PR #120 re-pin shape, where the gate reported PASS while a direct `cargo fmt --check` showed diffs — report the discrepancy before pushing; the local pass does not stand until the discrepancy is explained. First-push case: where no CI run exists for the exact tree yet — the first push of a new PR, or a tree CI has never run — there is no CI result to compare and no discrepancy to report, so the cross-check does not block that push; the cross-check is deferred until that push triggers CI, and the comparison is then made against the resulting CI run and any discrepancy reported before the next push. Where CI has run on the same tree, the duty above applies in full and is not deferred.

- Held advisories: an advisory held at the owner's ruling — the RUSTSEC-2026-0592 shape — is reported as HELD. A held advisory is not silently baselined: it does not enter any tree's baseline set, and the gate report names it as held until the owner rules otherwise.

## Quiet-window discipline

- Before a long gate run, check for concurrent cargo/rustc processes and wait for a quiet window. This VM has ~6–8 GB RAM; a release link was OOM-killed under concurrent cargo load.

- If another lane starts mid-run anyway, DISCLOSE the load in the report and corroborate any flakes with solo re-runs rather than claiming the threaded result as clean evidence.
