# Provenance — vendored OpenChamber reference snapshot

- **Source (fork):** https://github.com/pratik-saptarshi/openchamber
- **Upstream:** https://github.com/openchamber/openchamber
- **Pinned commit:** `cf18602cc77146f35e26e103dbee1ab8e218b663` ("release v2.7.3")
- **Snapshot date:** 2026-11-19 (first snapshot)
- **License:** MIT (copyright 2025 Bohdan Triapitsyn). `LICENSE` is preserved verbatim in this tree. The license was read from the tree itself, not from the GitHub API.
- **Excluded from the vendor:** `.git` (history — the snapshot was produced with `git archive`), and one file: `packages/web/server/lib/quota/providers/google/oauth.ts`, excluded by owner direction on 2026-11-19 because upstream ships Google OAuth client credentials in it at the pin and GitHub Push Protection rejects it (see the push-protection record below; the file is regenerable locally from the pin, per the instructions there, and is never to be committed back). Everything else is preserved byte-exact, including the tree's media and bundled assets (Electron icon catalogs, documentation images, the ghostty font and wasm under `packages/ui/src/lib/ghostty/`). The source tree contains 24 symlinks, all under `.claude/skills/` and all pointing at `../../.agents/skills/` inside the tree; they are preserved as symlinks, and — following the `reference/esf` precedent — symlinks are not listed in the sha256 manifest, which covers the tree's 9,571 regular files plus this file (CI additionally verifies that every symlink in the tree resolves).
- **Purpose:** reference snapshot of OpenChamber 2.7.3 (version per its root `package.json`) — a multi-surface workspace (desktop / web-PWA / VS Code / mobile) layered over OpenCode: it spawns or attaches to an `opencode serve` instance and reverse-proxies its HTTP/SSE API to the UI. Studied and built from, not executed from here: nothing in this snapshot is installed, linked, or run. The live trial in this environment runs the published npm package (`@openchamber/web@2.7.3`) in external-attach mode against the OpenCode background service — see the OpenChamber section of `docs/runbook.md` — never from `reference/`, the same treatment as the other vendored trees.

## Updating this snapshot

This tree changes only by re-vendoring: replace it wholesale with a new pinned upstream snapshot and regenerate `.github/vendor-openchamber.sha256` in the same change. Code or dependency edits made in place — including dependency-update PRs against this tree — are closed, not merged: a merged bump would leave the tree matching no upstream commit and falsify the provenance pinned above.

Branch note: the fork's default branch is `main`, the same as upstream's. The fork was created on 2026-11-19 as a pristine mirror, and at this pin its `main` is identical to upstream `main`: `cf18602` is upstream's own v2.7.3 release commit and the fork carries no local changes on top of it.

## Secret-scan annotation (2026-11-19)

A supplementary credential-pattern grep (GitHub/AWS token shapes, private-key headers, `sk-` keys, password/key assignments) over the full pinned tree found hits confined to upstream's own test and fixture material: the credential/git test suites under `packages/web/server/lib/` (credential-resolver, credential-broker, redaction, gatekeeper and journey tests) and an embedded key-shaped block in `packages/web/server/lib/spaces/places/escape-suite.ts`. All are upstream-authored content at the pinned commit, preserved byte-exact as part of the faithful snapshot; no credential material is introduced by this vendoring, which was produced mechanically with `git archive`. If the repo CI security scan (gitleaks) flags these fixtures when this PR is gated, the remedy is an allowlist entry for this tree — the treatment earlier trees' synthetic fixtures received — not an edit to the tree.

**Gitleaks outcome (2026-11-20, PR #181 CI):** the scan flagged 20 findings in 13 files of this tree, each verified by hand as a non-credential: nine test suites carry synthetic fixtures (seeded gatekeeper tokens in curl headers in the spaces/places docker tests, sequential hex keys such as `0123456789abcdef`, literal upload secrets in the gitlab/labels/project-upload tests); `packages/mobile/ios/App/Podfile.lock` is a CocoaPods spec checksum; `packages/web/bin/lib/cli-network.ts` holds the UI-password character set (an alphabet string, not a key); `packages/mobile/android/app/google-services.json` is upstream's shipped Firebase client config (a public app identifier by design); and `packages/web/server/lib/linear/auth.ts` line 81 is upstream's Linear OAuth client **ID** — a public identifier the `linear-client-secret` rule mislabels (the secret itself is read from the environment in that file). All 13 paths are allowlisted in the repo's `.gitleaks.toml`, following the ESF/NeuroStrata/harness-profiler precedent; the tree itself is untouched. The one production file at the pin that does carry credential values (`oauth.ts`) is excluded from the snapshot entirely — see the push-protection record below.

**Push-protection finding and owner-directed exclusion (2026-11-19):** the supplementary grep above did not flag one production source file, and GitHub Push Protection did: `packages/web/server/lib/quota/providers/google/oauth.ts` carries upstream's built-in Google OAuth client ID and client secret values (lines 5–10, two pairs) — credential-shaped values in upstream's own shipped source at the pinned commit. GitHub rejected the first push of this snapshot (GH013) over those four locations. The tree was deliberately NOT edited to remove them — an in-place edit would falsify the pin — and the repository owner (Pratik, 2026-11-19) directed that the file be **excluded** from the snapshot rather than edited or allowed through GitHub's push-protection unblock flow. The exclusion is declared in the **Excluded** line above and the manifest was regenerated without the file.

**Regenerating the excluded file locally.** At the pin, the excluded file's sha256 is `fd505c51c6a84d6289224c6dbcec1e75a865fdb382288c0be0368ad30698c4a2` (3,024 bytes). To restore it into a local copy of this tree, fetch it from the fork at the pinned commit and verify the digest (run from the AEP repository root):

```bash
git clone https://github.com/pratik-saptarshi/openchamber.git /tmp/openchamber-src
git -C /tmp/openchamber-src show cf18602cc77146f35e26e103dbee1ab8e218b663:packages/web/server/lib/quota/providers/google/oauth.ts > reference/openchamber/packages/web/server/lib/quota/providers/google/oauth.ts
echo "fd505c51c6a84d6289224c6dbcec1e75a865fdb382288c0be0368ad30698c4a2  reference/openchamber/packages/web/server/lib/quota/providers/google/oauth.ts" | sha256sum -c -
```

Regeneration is a local-only act: the file carries upstream's OAuth client credentials, so it must never be committed back into AEP — Push Protection will reject it.

<!-- vendor-freshness: {"branch": "main", "decision_date": "2026-11-19", "parent": "openchamber/openchamber", "parent_branch": "main", "pin": "cf18602cc77146f35e26e103dbee1ab8e218b663", "policy": "keep", "repo": "pratik-saptarshi/openchamber", "review_due": "2026-12-19", "tree": "openchamber"} -->

## Freshness

This file is the single source of truth for this tree's pin. The one-line `vendor-freshness` block above is machine-readable and is parsed by `scripts/vendor_graph.py` and `scripts/vendor_freshness.py`. Every re-vendor updates the block's `pin` in the same PR.

- **Current state:** **Keep** — at this snapshot the fork is a pristine upstream mirror (0 behind, 0 ahead of upstream `main`); no sync needed. Next review 2026-12-19.
- **Owner:** the AEP maintainer (repository owner).
- **SLA:** a weekly non-gating detector opens or updates one tracking issue within 7 days of detected drift; it never auto-syncs or auto-merges.
