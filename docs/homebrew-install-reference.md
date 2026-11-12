# Homebrew-install reference

## What it is

pratik-saptarshi/install (fork of Homebrew/install) — Homebrew's official installer: the `install.sh` and `uninstall.sh` shell scripts that bootstrap (and remove) the Homebrew package manager on macOS and Linux, plus the Ruby test suite that exercises them (`tests/test_install.rb`). The scripts do environment detection (OS, architecture, Xcode CLT / gcc presence), privilege checks, and a guarded, staged installation into the Homebrew prefix — the canonical curl-pipe bootstrap installer, and the trust decision that comes with it, in one small tree (19 files).

Vendored snapshot: [PROVENANCE.md](../reference/homebrew-install/PROVENANCE.md) — fork `https://github.com/pratik-saptarshi/install`, its `main` head at `7986efac25016e41eed7e471666140c06f9d97cf` (snapshot 2026-11-12, BSD 2-Clause). Upstream: `https://github.com/Homebrew/install`. The fork's `main` is a pristine upstream mirror and is identical to upstream `main` at this pin; if the fork ever carries its own changes they land fork-first and a re-vendor pins that state.

## Mapping to the AEP loop

| homebrew-install | AEP (this environment) |
|---|---|
| a bootstrap script fetched and executed on trust — the archetypal supply-chain decision | vendored snapshots pinned by commit and sha256 manifest; content is reviewed at a pin, never fetched-and-run from a moving branch |
| staged install with preflight checks (OS, toolchain, permissions) that abort before mutating anything | gated pipelines: pre-flight checks (`ghg check`, hygiene gates) decide before any publish step runs |
| idempotent, re-runnable installer steps | re-vendor and sync operations that can be re-run safely against a pinned state |
| a first-class uninstaller mirroring the installer | reversibility discipline: deletions and removals are deliberate, recorded operations, not side effects |

## Where it differs from the other vendored trees

Most vendored trees here are libraries, method corpora, or servers. This one is a pair of operational shell scripts and their tests — the smallest tree in `reference/`, and the only one whose entire purpose is machine mutation (installing and removing a package manager). That is exactly why it is kept as inert reference data: its mechanics are the study material, and they are never exercised from this snapshot.

## What runs on this VM

Nothing executes from the vendored tree. A real Homebrew installation or removal would run from a live checkout of the fork, not from `reference/`.

## Upstream-automation caveat

The snapshot carries the source project's own automation (`.github/workflows` — its test, actionlint, and stale-issue workflows — plus a CodeRabbit config and a CodeQL extension file) addressed to contributors working *in that repository*. As vendored reference data none of it runs here; AEP's CI only verifies the snapshot's integrity against the vendor manifest.
