# Provenance — vendored harness-profiler reference snapshot

- **Upstream:** https://github.com/afurmanov/harness-profiler
- **Pinned commit:** `847bd8f6ab2a0348fd7b7057c1943e4c2fa861e8` ("Show a background call with no end yet as running") — the commit `package.json` publishes as `harness-profiler` **v0.2.2**
- **Snapshot date:** 2026-11-17
- **License:** MIT (copyright 2026 Aleksandr Furmanov — see `LICENSE`). `LICENSE` is preserved verbatim at the tree root and again at `plugin/LICENSE`; both are part of the pinned upstream tree.
- **Excluded from the vendor:** `.git` (history). The snapshot was produced from GitHub's tarball API with `--strip-components=1`, so the upstream tree is otherwise complete: 79 files, 21 of them Markdown, 2.4 MB on disk. There are no symlinks in the tree.
- **Purpose:** reference snapshot of a session profiler for Claude Code / Codex agent harnesses: a hook-based recorder plus a renderer that turns recorded calls into a call tree (contexts nested by subagent/skill, timings, token spend). AEP consumes the pin's own record builder, serializer, masker and renderers from `plugin/libexec/hp.js` to profile opencode sessions; it does not execute the upstream Claude Code hook install path.

## What AEP uses and what it ignores

Used (imported as a library by the Phase B translator and the `profile-tree` wrapper): `plugin/libexec/hp.js` exports `buildRecord`, `buildEventRecord`, `serialize`, `mask`, `contextsOf`, `renderTree`, `renderHtml`, `buildForest`, `spentTokens`, and `contextSpend`. The record format (`v: 2`), the 4096-byte line budget, and the renderer's context-nesting rules are taken from this pin, not reimplemented.

Ignored: `.claude-plugin/` and `plugin/hooks/hooks.json` (Claude Code plugin-marketplace wiring), `plugin/skills/show-profile/` (Claude Code skill wrapper), and `e2e/` (playwright screenshot run — the vendored unit suite is run without playwright, and no npm dependency is installed). The snapshot is never installed, linked, or executed from `reference/`; nothing in it governs this repository. AEP's own `AGENTS.md` does.

## Updating this snapshot

This tree changes only by re-vendoring: replace it wholesale with a new pinned upstream tarball and regenerate `.github/vendor-harness-profiler.sha256` in the same change. Code or dependency edits made in place are closed, not merged: a merged edit would leave the tree matching no upstream commit and falsify the provenance pinned above. `PROVENANCE.md` — this file — is the only file added to the upstream tree, and it is part of the manifest.

## Secret-scan annotation (2026-11-17)

Secret scan: gitleaks v8.24.3 with the default rules — the same engine and version the repo CI security job installs — over the working tree (`gitleaks detect --source . --no-git`). **This snapshot is not claimed leak-free.** The pin ships two synthetic fixtures in the unit tests for its own masker, both in `test/capture.test.js`, and both are **allowlisted by path** in `.gitleaks.toml`:

1. `test/capture.test.js:155` — `curl-auth-header`: a fake bearer value (12 alphabetic characters) used as *input* to `mask()` to assert it redacts to `[redacted]`.
2. `test/capture.test.js:160` — `generic-api-key`: a fake `token=` value (12 characters) in a `tool_response` used to assert the record's `result` is masked.

Neither is a credential; both exist to prove the masker works. No other file in the snapshot is allowlisted, and no credential files exist in the tree. The `test/capture.test.js` file also contains a fake PAT-shaped string in the same masking test; gitleaks v8.24.3's default rules do not flag that line, so the two findings above are the complete set.

<!-- vendor-freshness: {"branch": "main", "decision_date": "2026-11-19", "parent": null, "parent_branch": null, "pin": "847bd8f", "policy": "repin", "repo": "afurmanov/harness-profiler", "review_due": "2026-12-19", "tree": "harness-profiler"} -->
