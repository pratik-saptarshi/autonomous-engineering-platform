# Provenance — vendored NeuroStrata reference snapshot

- **Source (fork):** https://github.com/pratik-saptarshi/NeuroStrata
- **Upstream:** https://github.com/Cognilogical/NeuroStrata
- **Pinned commit:** `4f487f4724a0db226ac3c6f070bc751035f2bc71` ("Merge pull request #49 from pratik-saptarshi/fix/codex-remediation-pr140")
- **Snapshot date:** 2026-11-09
- **License:** MIT (copyright 2026 Kenton). `LICENSE` is preserved verbatim in this tree.
- **Excluded from the vendor:** `.git` (history — the snapshot was produced with `git archive`) and `web-ui/public/graph.json` (a symlink whose target, `../../.NeuroStrata/graph/graph.json`, is a runtime artifact outside the source repo; the symlink is broken in any vendored copy and would fail the CI symlink check).
- **Purpose:** reference snapshot of the Rust MCP memory daemon — the local memory layer (SynapticGraph graph/vector memory, task gate, behavioral-rule guard) that this environment's agents run on. Studied and built from, not executed from here.

## Updating this snapshot

This tree changes only by re-vendoring: replace it wholesale with a new pinned upstream snapshot and regenerate `.github/vendor-neurostrata.sha256` in the same change. Code or dependency edits made in place — including dependency-update PRs against this tree — are closed, not merged: a merged bump would leave the tree matching no upstream commit and falsify the provenance pinned above.

Branch note: the fork's default branch is `develop`, while upstream's default is `main`. This snapshot is the fork `develop` head at the pinned commit.

Version note: this snapshot's `Cargo.toml` declares version **1.16.1**. The daemon actually deployed on this VM is 1.9.0, installed separately (see `docs/neurostrata-reference.md`) — do not confuse the snapshot version with the deployed version.

## Update history

- 2026-11-09: regenerated at `4f487f4`, the remediated pin. This PR was
  originally submitted at `a7cc416` (entry below); the adversarial panel
  put that submission on HOLD over five Codex findings against the fork
  code in the snapshot and a only-partly-cleared vitest critical. The
  remediation landed fork-side as pratik-saptarshi/NeuroStrata PR #49 —
  F1 daemon double-lock tail removed, F2 restore overwrite fixed, F3
  store double-open removed, F4 ingest carry-forward failures now abort
  instead of publishing a partial generation, F5 duplicate
  `ingest_directory` call removed, and F6, the vitest residue (below),
  plus deletion of the fossil `plugins/openclaw/package.json.backup` —
  and merged into fork `develop` on 2026-11-09; `4f487f4` is that merge
  commit and the fork `develop` tip. This snapshot is regenerated at the
  remediated pin, not merged at any `a7cc416`-based head. **The vitest
  claim in the entry below is superseded: the GHSA-5xrq-8626-4rwp /
  CVE-2026-47429 vitest critical is now FULLY cleared at this pin** —
  zero vitest below 5.x is declared or resolved in any tracked manifest
  or lockfile (no lockfile resolves vitest at all; the only declarations
  are `^5.1.0` in `plugins/core/package.json` and
  `plugins/opencode/package.json`). The rustls attribution in the entry
  below stands: root `Cargo.lock` rustls 0.23.46 came from fork PR #56's
  RUSTSEC refresh; `src-tauri/Cargo.lock`'s 0.23.46 via fork PR #38.
  Manifest: `.github/vendor-neurostrata.sha256`, 549 files. The fork
  tracks the plugins' built `dist/` outputs (28 files); AEP's root
  `.gitignore` has a blanket `dist/` rule, so those files are force-added
  to keep the snapshot byte-faithful to the pin. One gitleaks false
  positive in the tree (prose in
  `docs/designs/2026-10-27-ranked-improvement-list.md`) is allowlisted in
  `.gitleaks.toml`, per the standing pattern of never editing the
  vendored tree for lint reasons.
- 2026-11-09: re-vendored at `a7cc416`. The fork's `develop` advanced ~880
  commits past `67c90c7`: the D2 sync (fork PR #35 merged upstream
  `main`@`8fdae4b` into `develop`, bringing the snapshot from 1.13.0 to
  1.16.1) plus the fork's own remediation and parity work, topped by fork
  PR #38 — vitest → `^5.1.0` in `plugins/opencode`, and rustls → 0.23.46
  in `src-tauri/Cargo.lock` (the root `Cargo.lock`'s 0.23.46 came from
  fork PR #56's RUSTSEC refresh). **Correction (2026-11-09, adversarial
  panel finding): the GHSA-5xrq-8626-4rwp / CVE-2026-47429 vitest
  critical is only partly cleared at this pin.** `plugins/openclaw`'s
  `package.json` no longer declares vitest, but its new
  `package-lock.json` still resolves vitest 1.6.1, and the new
  `plugins/core/package.json` declares vitest `^1.0.0`. The snapshot is
  byte-faithful to the fork; completing the fix is fork-side work,
  routed into the fork remediation already running. Manifest:
  `.github/vendor-neurostrata.sha256`, 550 files (was 294). The fork now
  tracks the plugins' built `dist/` outputs (28 files); AEP's root
  `.gitignore` has a blanket `dist/` rule, so those files are force-added
  to keep the snapshot byte-faithful to the pin. One gitleaks false
  positive in the new tree (prose in
  `docs/designs/2026-10-27-ranked-improvement-list.md`) is allowlisted in
  `.gitleaks.toml`, per the standing pattern of never editing the
  vendored tree for lint reasons.
- 2026-10-26: re-vendored at `67c90c7`. The web-ui security bumps — vite
  `^8.3.0` → `^8.3.5` (lockfile resolves 8.3.5) and source-map-js 1.2.1 →
  1.2.2 — landed in the fork via pratik-saptarshi/NeuroStrata PR #18 because
  AEP PR #50 (Dependabot) was closed rather than merged into the prior
  snapshot. This re-vendor also fast-forwards the snapshot from 1.11.0 across
  upstream 1.12/1.13 and the fork's remediation program. Manifest:
  `.github/vendor-neurostrata.sha256`, 294 files.

## Secret-scan annotation (2026-10-26; updated 2026-11-09)

This note supersedes the 2026-10-26 annotation, which described the scan
state of the `67c90c7` snapshot and is stale at this pin. At `4f487f4`
the credential-pattern gate (gitleaks, configured by `.gitleaks.toml`)
flags three paths in this tree — all three allowlisted:

- `src/secrets.rs` and `src/buffer.rs` — unchanged from the 2026-10-26
  note. Both are the `#[cfg(test)]` suites of NeuroStrata's own
  secret-redaction engine — the module that scrubs credentials out of
  stored memory — so their fixtures are token-shaped by design: a `ghp_`
  token built from a sequential alphabet+digits string, and the AWS
  documentation example keys (one line is annotated
  `// official AWS example`). Both files are allowlisted in
  `.gitleaks.toml`, mirroring the ESF `redact_test.go` precedent.
- `docs/designs/2026-10-27-ranked-improvement-list.md` — new since the
  2026-10-26 note (it arrived with the `a7cc416` tree). Line 15 is a
  prose sentence about secret/PII hit counts and duplicate detection
  whose wording trips the generic-api-key entropy heuristic. (The
  sentence is not quoted verbatim here: quoting it tripped the same
  heuristic in this file.) Not a credential; allowlisted in
  `.gitleaks.toml` on 2026-11-09.

The committed LanceDB store under `.neurostrata/` remains part of the
snapshot and was included in the scan: no credential patterns. No other
files in the vendored tree match the credential patterns.
