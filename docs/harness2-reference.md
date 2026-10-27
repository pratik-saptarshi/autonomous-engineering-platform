# Harness² reference

## What it is

pratik-saptarshi/harness2 — Harness², a plug-and-play framework for recursive agent harnessing in an open world (the implementation behind the Harness² paper, arXiv 2610.14224). A *harness* is the system around a model — prompts, tools, memory, skills, orchestration — and *harnessing* is optimizing that system while model weights stay fixed. Harness² connects two levels of recursion: task-level recursion refines the execution harness for the current task through a contrastive Propose–Probe–Compose step (propose edits, probe their effects on the same task, compose a refined harness from behavioral contrasts, without ground-truth feedback), and harnessing-level recursion updates a persistent *improvement harness* with adopted harnesses and evidence-supported lessons from each task.

Vendored snapshot: [PROVENANCE.md](../reference/harness2/PROVENANCE.md) — upstream `https://github.com/pratik-saptarshi/harness2` (default branch `develop`) at `1cfe254e8d25b15f37048c3730134686abe60335` (2026-10-26, Apache License 2.0).

## Mapping to the AEP loop

| Harness² | AEP (this environment) |
|---|---|
| Propose–Probe–Compose task-level refinement | spike/prototype → verification gates before adoption |
| improvement harness — persistent, evidence-supported lessons | NeuroStrata inscription at task close (primary-memory rule) |
| benchmark suites (JobBench, Harvey LAB, WorkBuddy) as harness evidence | deterministic verification + review gates decide what ships |
| third_party runners pinned per benchmark | vendored reference snapshots pinned by commit + sha256 manifest |

## What runs on this VM

Nothing executes from the vendored tree — it is a study reference, like the ESF and NeuroStrata snapshots. The source repo is also cloned at `~/workspace/repos/harness2` (checked out detached at the pinned commit) for reading; no Harness² benchmark or setup run was performed as part of this vendoring.

## Caveats

- Just over half the snapshot's bytes are README media (`assets/harness2-video.mp4`, `assets/logo.png`, and the other pipeline/recursion figures). They are part of the pinned upstream tree and are preserved byte-exact like everything else.
- `third_party/` vendors the benchmark runners (job-bench, Harvey LAB, WorkBuddy) with their own licenses under `third_party/licenses/` and per-runner `LICENSE` files — preserved verbatim; the Apache-2.0 `LICENSE` at the snapshot root covers Harness² itself.
