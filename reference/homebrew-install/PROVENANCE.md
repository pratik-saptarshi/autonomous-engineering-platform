# Provenance — vendored homebrew-install reference snapshot

- **Source (fork):** https://github.com/pratik-saptarshi/install
- **Upstream:** https://github.com/Homebrew/install
- **Pinned commit:** `3ef3676f8028811d38eae05d3b3b4f97d72a0f61` ("Merge pull request #1172 from Homebrew/sync-shared-config")
- **Snapshot date:** 2026-11-19 (re-vendor; first snapshot 2026-11-12 at `7986efa`)
- **License:** BSD 2-Clause (Copyright (c) 2009-present, Homebrew contributors). `LICENSE.txt` is preserved verbatim in this tree. The license was read from the tree itself, not from the GitHub API.
- **Excluded from the vendor:** `.git` (history — the snapshot was produced with `git archive`). The source tree contains no symlinks and no export-ignore attributes, so nothing else was excluded: the snapshot is the complete tracked tree at the pin (19 files).
- **Purpose:** reference snapshot of Homebrew's official installer — the `install.sh` / `uninstall.sh` bootstrap scripts and their Ruby test suite (`tests/test_install.rb`) for the Homebrew package manager on macOS and Linux. It is the canonical example of the curl-pipe bootstrap installer: environment detection, privilege and toolchain checks, and a guarded, idempotent installation flow, kept here as a study reference for installer/bootstrap mechanics and their trust surface. Studied, not executed from here: nothing in this snapshot is installed, linked, or run, and a live run would execute from a live checkout of the fork, not from `reference/`, the same treatment as the other vendored trees.

## Updating this snapshot

This tree changes only by re-vendoring: replace it wholesale with a new pinned snapshot and regenerate `.github/vendor-homebrew-install.sha256` in the same change. Code edits made in place are closed, not merged: a merged edit would leave the tree matching no source commit and falsify the provenance pinned above.

Branch note: the fork (`pratik-saptarshi/install`) currently carries a single branch, `main`, which is a pristine upstream mirror — at this pin it is identical to upstream `main` at `3ef3676` — the fork was synced from `Homebrew/install` on 2026-11-19 before this re-vendor (6 upstream commits pulled in: actionlint workflow, Ruby version and installer/tests updates). Upstream updates are pulled into the fork's `main` (`gh repo sync --branch main`); if the fork ever carries its own changes, they land fork-first (a `develop` branch on the fork, per the pattern used for the NeuroStrata and ESF forks) and a re-vendor pins that state instead, with the delta recorded here.

<!-- vendor-freshness: {"branch": "main", "decision_date": "2026-11-19", "parent": "Homebrew/install", "parent_branch": "main", "pin": "3ef3676f8028811d38eae05d3b3b4f97d72a0f61", "policy": "sync-then-repin", "repo": "pratik-saptarshi/install", "review_due": "2026-12-19", "tree": "homebrew-install"} -->

## Freshness

This file is the single source of truth for this tree's pin. The one-line `vendor-freshness` block above is machine-readable and is parsed by `scripts/vendor_graph.py` and `scripts/vendor_freshness.py`. Every re-vendor updates the block's `pin` in the same PR.

- **Current state:** **sync-then-repin** — re-vendored at the current fork head on 2026-11-19; next freshness review 2026-12-19.
- **Owner:** the AEP maintainer (repository owner).
- **SLA:** a weekly non-gating detector opens or updates one tracking issue within 7 days of detected drift; it never auto-syncs or auto-merges.
- **Known out-of-scope drift for this lane:** `harness2` (2 behind upstream), `neurostrata` (170 behind, 604 ahead), and `craft-anything` (decision due) are reported by the detector, not fixed by the 2026-11-19 migration.
