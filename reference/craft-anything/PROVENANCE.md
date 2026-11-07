# Provenance — vendored Craft Anything reference snapshot

- **Upstream:** https://github.com/storytold/craft-anything
- **Pinned source:** Pratik's fork, https://github.com/pratik-saptarshi/craft-anything (a pristine sync-only mirror of upstream; AEP pins track the fork — Decision D2)
- **Pinned commit:** `2e4afc535cebb6ee556c5ea3f6b4e454487853f9` ("A plain HTML site passes the build check as it is, with nothing to build (#500)", 2026-11-02), read back via the GitHub API at snapshot time
- **Corresponding upstream release:** ≈ v0.3.0 + 73 main commits — the fork head is a descendant of tag v0.3.0 by 73 commits and 148 commits behind v0.4.0 (compare API, verified at snapshot time). It corresponds to no single release; v0.3.0 is the nearest release at or below the pin. Upstream's current release at snapshot time is v0.5.0 (2026-11-06).
- **Snapshot date:** 2026-11-07
- **License:** MIT OR Apache-2.0. `LICENSE-MIT` and `LICENSE-APACHE` are preserved verbatim in this tree. The ArtCraft brand assets are **not** covered by that license (see the brand strip below).
- **Excluded from the vendor:** `.git` (history) and the dispositioned files listed below. Nothing else was edited: apart from the relocations into `QUARANTINE/` and the strips, every file is byte-identical to the pinned commit.
- **Purpose:** pinned reference for the Study tooling surface (tool taxonomy and evidence-record discipline) under the craft-anything adoption plan (`docs/plans/2026-11-07-craft-anything-adoption-plan.html`, Phase 1). This snapshot is studied, not executed from here; it does not install the engine. Lane status language: "protocol adopted; engine not installed".
- **Tree census at pin:** 723 entries, 621 files, 13,601,548 bytes. After disposition: 599 files, plus this PROVENANCE.md = 600 files in `.github/vendor-craft-anything.sha256`.

## Disposition (applied before manifest generation)

The pinned tree carries agent/automation instruction surfaces and ArtCraft brand assets. Each was dispositioned — stripped, or quarantined under the mechanical definition below — before the manifest was generated, because the vendor-integrity completeness check fails on any post-manifest change.

**Quarantined** means: moved to `reference/craft-anything/QUARANTINE/`, relative path preserved, with an entry in this file naming the file and its rationale. Anything not meeting that definition was stripped. Quarantined files are inert reference data: they are not AEP's instructions, hooks, or CI, and nothing executes them in place.

### Quarantined — instruction surfaces (14 files)

Upstream's own agent/automation configuration. Retained as reference (how the upstream project directs its agents and automation is part of the Study surface) but relocated out of any position where tooling could mistake them for AEP's own configuration.

| File (original path) | Rationale |
|---|---|
| `AGENTS.md` | Upstream's agent instruction file; would be read as governing instructions if left at the snapshot root. |
| `CLAUDE.md` | Upstream's Claude session imports (imports `AGENTS.md` and `docs/pitfalls.md`); same reasoning. |
| `.coderabbit.yaml` | Upstream's CodeRabbit review-bot configuration; not AEP's review configuration. |
| `.githooks/pre-commit` | Upstream's commit hook (runs `cargo xtask secrets`); a hook script must not sit at an active-looking path in a vendored tree. |
| `.github/ISSUE_TEMPLATE/bug_report.md` | Upstream's issue templates; GitHub honors only the repository-root `.github/`, so these are inert here, but they are upstream's automation surface, not AEP's. |
| `.github/ISSUE_TEMPLATE/config.yml` | Same as above. |
| `.github/ISSUE_TEMPLATE/idea.md` | Same as above. |
| `.github/actionlint.yaml` | Upstream's workflow-lint configuration. |
| `.github/pull_request_template.md` | Upstream's PR template; not AEP's. |
| `.github/workflows/ci.yml` | Upstream's CI definition; retained as reference for the project's build/test process. Not AEP CI. |
| `.github/workflows/freebsd.yml` | Same as above. |
| `.github/workflows/packaging-lint.yml` | Same as above. |
| `.github/workflows/release.yml` | Upstream's release workflow; retained as reference for the published-package process. |
| `.github/workflows/windows-arm64.yml` | Same as above. |

### Stripped — brand assets (22 files)

Decision D3 (strip ArtCraft brand assets on vendor), which is also the brand license's own instruction: the ArtCraft Marks are not open source, are not covered by the MIT OR Apache-2.0 license, and a distributed modified/derived work must remove them (terms in the stripped `docs/brand/LICENSE-brand.txt`, summarized here from the pinned tree). The Craft Anything name and the ArtCraft name are retained in plain text only, as references (see nominative use below).

- `docs/brand/` — the ArtCraft Marks and their license text (5 files): `LICENSE-brand.txt`, `artcraft-logo.svg`, `artcraft-logo-white.svg`, `artcraft-mark.svg`, `artcraft-mark-black.svg`.
- `assets/app-icon/` — the app icon (the ArtCraft "raven"), which its own `LICENSE.txt` places on the same brand terms as the marks, covering the icon source and every derived file (15 files): `craft-anything.svg`, `craft-anything-1024.png`, `craft-anything.icns`, `craft-anything.ico`, `LICENSE.txt`, `README.md` (the icon's brand documentation), and `hicolor/` (8 PNG renders + the scalable SVG of the same icon). **Retained from this directory:** `trace.py` only — a tracing tool that its license text expressly covers under MIT OR Apache-2.0.
- `packaging/macos/dmg/background.svg` and `packaging/macos/dmg/background.tiff` — the macOS DMG background artwork, which embeds the app icon as its dominant visual (`background.svg` links `assets/app-icon/craft-anything.svg`; the TIFF is its raster render). Stripped as brand derivatives under the same D3 rule. The rest of `packaging/macos/dmg/` (`generate.py`, `DS_Store`, `README.md`) is code and documentation and is retained.

**Retained, with rationale — `docs/images/` (4 files):** `make.png`, `project-game.png`, `project-website.png`, `workbench.png` are documentation screenshots of the open-source application's own UI, referenced by the retained READMEs. They are not ArtCraft Marks (the brand license scopes the marks to `docs/brand/`) and not the app icon (scoped by `assets/app-icon/LICENSE.txt`); the product name visible in a UI screenshot is a depiction of the software, not a brand asset file. Retained as non-brand documentation content.

Retained snapshot files (READMEs, `ATTRIBUTION.md`, packaging scripts, `build.rs`) still reference some stripped paths in text and in build/packaging logic. Those references are upstream's own content, left byte-identical: a vendored snapshot is never edited in place, and the strip is recorded here and in the PR body instead.

## Nominative use

The names "Craft Anything" and "ArtCraft" appear in this snapshot's retained text and in AEP's own documents and the forthcoming `craft-anything-protocol` skill name. They are retained as plain-text references naming the upstream project and its authors — the use the brand license expressly permits ("you may say, in plain text, that your work is based on Craft Anything by the ArtCraft team") — never as AEP branding, logos, or icons.

## Sync-or-accept-staleness record (Decision D2)

At pin time the fork is **246 commits behind upstream, 0 ahead**, and the pin sits at the v0.3.0-era while upstream is at v0.5.0. **Recorded decision: ACCEPT-STALENESS.** The v0.3.0-era pin is vendored deliberately, as the ruling specifies (pin from the fork as it stands); the fork was not synced first.

Staleness budget (D2): the AEP lane coordinator checks upstream release state on each upstream release; a re-pin PR **or a recorded keep-decision** is due whenever upstream moves more than 2 releases past the pin. With the pin at v0.3.0-era and upstream already at v0.5.0, **the budget is at its boundary at first pin** — the first keep-or-re-pin decision comes due almost immediately, and this record is the baseline it is measured against.

## Dependabot / dependency-alert scoping

Recorded for this tree, per the adoption plan's Phase 1:

- **Version updates: pre-decided by existing repo posture.** `.github/dependabot.yml` scopes Dependabot version updates to `skills/archify` only; everything under `reference/` is intentionally omitted (omission, not an ignore entry, is the posture for byte-pinned snapshots). No change is made to `dependabot.yml` by this vendoring, and no version-update PRs should be opened against `reference/craft-anything/`.
- **Security updates: unchanged, and not this PR's call.** Dependabot security updates are governed by the repository Settings toggle (Code security), not by `dependabot.yml`. This vendoring changes no Settings; the toggle's state for this tree is the repository owner's item to decide and record separately.

## Updating this snapshot

This tree changes only by re-vendoring: replace it wholesale with a new pinned fork snapshot, re-apply the disposition above (instruction surfaces quarantined, brand stripped), and regenerate the manifest in the same change. Code or dependency edits made in place — including dependency-update PRs against this tree — are closed, not merged: a merged in-place edit would leave the tree matching no pinned commit and falsify the provenance recorded above.

Manifest regeneration is a single scripted step, run from the repository root against the final, dispositioned tree:

```sh
cd reference/craft-anything
find . -type f | LC_ALL=C sort | xargs sha256sum > ../../.github/vendor-craft-anything.sha256
```

## Adoption exit criteria (restated from the plan, Phase 2)

This snapshot (with the protocol skill) is removed via a removal PR owned by the AEP lane coordinator when any of these is evidenced:

- the protocol has no recorded use across two consecutive quarters (a recorded use is a work record — a lane note, a finding-ledger entry, or a PR — that cites the protocol skill as the governing protocol for a piece of reverse-engineering work);
- upstream changes its license or the brand terms in a way this snapshot cannot satisfy;
- upstream is abandoned (no release or push for 12 months) **and** the reference has no recorded use in that period; or
- a runtime-adoption plan supersedes the protocol outright.

## Issues

Issues about Craft Anything itself — defects, questions, requests — are filed on the fork or upstream (`pratik-saptarshi/craft-anything` / `storytold/craft-anything`), never on AEP. AEP issues are for AEP's own vendoring machinery (manifest, CI step, this provenance record).
