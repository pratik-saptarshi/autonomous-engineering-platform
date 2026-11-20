# OpenChamber reference

## What it is

openchamber/openchamber — OpenChamber, a multi-surface workspace for the OpenCode AI agent: desktop, web/PWA, VS Code, and mobile surfaces over one server. OpenChamber is not an agent runtime; it spawns (or attaches to) an `opencode serve` instance, manages its lifecycle, and reverse-proxies the server's HTTP/SSE API to the UI, adding session and project management, worktree-per-session isolation, diff review, a classifier-mediated permission safety net, and remote access via tunnels or an end-to-end-encrypted relay.

Vendored snapshot: [PROVENANCE.md](../reference/openchamber/PROVENANCE.md) — upstream `https://github.com/pratik-saptarshi/openchamber` (default branch `main`) at `cf18602cc77146f35e26e103dbee1ab8e218b663` (2026-11-19, MIT License). The fork is a pristine mirror: the pin is upstream's own v2.7.3 release commit.

## Mapping to the AEP loop

| OpenChamber | AEP (this environment) |
| --- | --- |
| managed/external `opencode serve` lifecycle | the OpenCode background service on 127.0.0.1:49374, driven through its API |
| worktree-per-session isolation | one git worktree per task/branch in the feature-to-PR workflow |
| permission safety net — classifier-mediated approvals that fail closed | approval cards and the ghg pre-flight gate for GitHub effects |
| diff review + changes walkthrough | paperthin review skills and the Codex final-head gate |

## What runs on this VM

Nothing executes from the vendored tree — it is a study reference, like the other snapshots. What does run is the published npm package (`@openchamber/web@2.7.3`, the same version as this pin) in external-attach mode against the existing OpenCode background service, trialled and verified on 2026-11-19: its health endpoint reported the service on port 49374 running, its proxied session list returned the service's own pre-existing sessions, and no second `opencode serve` was spawned. Setup, verification, and stop/relaunch are documented in the OpenChamber section of the [runbook](runbook.md).

## Caveats

- This is by a wide margin the largest vendored snapshot (~116 MB, 9,572 regular files): a full TypeScript/Bun monorepo with desktop, VS Code, and mobile packages. The bulk is source assets — Electron icon catalogs, documentation images, and the ghostty terminal's font and wasm — preserved byte-exact like every other tree.
- The tree carries 24 symlinks under `.claude/skills/` pointing at `../../.agents/skills/` inside the tree. They are preserved as symlinks and resolve in-tree; per the `reference/esf` precedent they are not listed in the sha256 manifest, which covers regular files only.
- A signed-in OpenChamber session is effectively full machine access (upstream's own threat model in its `SECURITY.md`): any deployment belongs on localhost, a tailnet, or its E2EE relay — never port-forwarded. The trial here binds 127.0.0.1 only.
- Upstream releases every few days and tests against a specific OpenCode pairing (2.3.2; floor 2.2.4). This environment's OpenCode v2.3.0 attached with no warnings, but the pairing gap is the first thing to re-check at any re-vendor.
