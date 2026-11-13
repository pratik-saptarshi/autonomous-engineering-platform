---
name: rust-pre-pr-gate
version: 1.0.0
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
