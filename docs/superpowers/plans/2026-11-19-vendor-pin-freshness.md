# Vendor Pin Freshness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the four AEP-owned forks that trail their true upstreams up to date, re-vendor the affected pins (plus the pins that trail a current fork), make provenance able to answer "is this pin current?", and add a non-gating weekly freshness check so the answer stays true.

**Architecture:** Two layers. (1) A one-time migration: sync four forks fork-first (pristine mirror branch ← upstream, then merge forward into the fork's `develop`/`main` preserving fork-only commits), then re-vendor each affected `reference/<tree>/` snapshot wholesale at the new fork head, regenerate its manifest, re-apply dispositions, and rewrite provenance. (2) A durable guard: a machine-readable source-of-truth file plus a weekly scheduled workflow that compares every pin to both its fork head and its true upstream head and opens/updates an issue when behind. Vendored trees are never edited in place.

**Tech Stack:** GitHub CLI (`gh repo sync`, `gh api`), git, bash, Python 3 (stdlib), Node 18+ only where existing gates require it, GitHub Actions.

**Spec:** the audit in the 2026-11-19 session (13 vendor manifests on `origin/develop@d34bf26`) plus each `reference/<tree>/PROVENANCE.md`. Ground truth was re-verified with `gh api` this session; numbers below are from that check and must be re-read at execution time.

## Global Constraints

- **Owner decision (2026-11-19): sync the forks first.** For `esf`, `humanizer`, `install`, `docs-mcp-server`, pull upstream into the fork, then pin the re-vendor at the synced fork head. Do not pin the forks as they stand today.
- **Fork-first discipline:** upstream changes land on the pristine mirror branch first (`master`/`main`), then merge forward into the fork's working branch (`develop`/`main`). Fork-only commits must remain ancestors of the new working-branch head. No force-push to a working branch.
- **Byte-fidelity:** a vendored tree matches exactly one pinned commit, minus documented exclusions. Regenerate the manifest from the final tree in the same change. Never edit a vendored file in place — such edits are closed, not merged.
- **Dispositions preserved:** per-tree exclusions (e.g. `neurostrata` symlink, `elephant-goldfish-model` subset), quarantines (`craft-anything`), and gitleaks path allowlists survive re-vendoring. A new snapshot's secret scan must be clean or allowlisted by path with rationale.
- **No unrelated scope:** no in-place dependency edits, no executing/installing vendored code, no license renegotiation, no Dependabot scoping changes, no re-pinning `craft-anything` or `neurostrata`.
- **Signing:** all PR titles, bodies and issue/comment text signed `— Terminator3000-DarkCrouton` per `AGENTS.md`.

## Review Focus

1. **Losing fork-only commits during sync** — a merge that drops the 11 `esf` / 10 `docs-mcp-server` / 9 `grim-prompter`-style fork commits silently reverts AEP-maintained remediation. Task 1 records pre-sync SHAs and gates on ancestry before and after; tasks 2–5 assert the same.
2. **Syncing the wrong branch** — syncing `develop` directly from a differently-named upstream branch can corrupt the mirror pattern. Task 1 encodes the per-fork mirror/working branch pair verified by API.
3. **A re-vendor that is not byte-identical to its pin** — a stale manifest makes `vendor-integrity` lie. Every re-vendor task regenerates the manifest and verifies tree↔commit fidelity, not just manifest↔tree.
4. **A freshness check that always reports green** — if it parses prose or silently skips missing metadata, it never opens an issue. Task 7 mutation-tests the checker (stale pin, stale parent, missing source) and count-asserts the suite.
5. **New upstream commits landing during the migration** — a fork synced at T0 can be behind again at T1. Task 8 records a freshness baseline at merge time and the weekly check owns subsequent drift; the plan does not promise perpetual currency.

---

## Phase A — Ground truth and source-of-truth (before any mutation)

### Task 1: Record the pin/fork/upstream graph as machine-readable SSOT

**Files:**
- Create: `.github/vendor-sources.json`
- Modify: `.github/workflows/ci.yml` (validate SSOT against provenance)
- Test: `scripts/tests/test_vendor_sources.py`

**Verified graph (re-read at execution time):**

| Tree | Pinned commit | Referenced repo | Ref branch | True upstream | Upstream branch | Ref-branch vs upstream |
|---|---|---|---|---|---|---|
| craft-anything | `2e4afc535ceb…` | `pratik-saptarshi/craft-anything` | develop | `storytold/craft-anything` | main | fork 1354 ahead of pin; pin 1391 behind upstream main |
| docs-mcp-server | `506f27b` | `pratik-saptarshi/docs-mcp-server` | develop | `arabold/docs-mcp-server` | main | 4 behind / 10 ahead |
| elephant-goldfish-model | `e9e1f06aa4e2…` | `pratik-saptarshi/elephant-goldfish-model` | develop | `google/elephant-goldfish-model` | main | 0/0, pin 45 behind fork head |
| esf | `388583d` | `pratik-saptarshi/esf` | develop | `mitkox/esf` | master | 57 behind / 11 ahead |
| grim-prompter | `076ec0d32c9e…` | `pratik-saptarshi/grim-prompter` | develop | `jmanico/grim-prompter` | main | 0/0, pin 9 behind fork head |
| harness-profiler | `847bd8f6ab2a…` | `afurmanov/harness-profiler` | main | — (third party) | — | pin = head |
| harness2 | `e5cda48c48d1…` | `pratik-saptarshi/harness2` | develop | `google-research/harness2` | main | 0 behind / 2 ahead, pin = fork head |
| homebrew-install | `7986efa` | `pratik-saptarshi/install` | main | `Homebrew/install` | main | 6 behind / 0 ahead |
| humanizer | `0ef9fe5bc357…` | `pratik-saptarshi/humanizer` | develop | `blader/humanizer` | main | 8 behind / 0 ahead |
| neurostrata | `0754125bd0c7…` | `pratik-saptarshi/NeuroStrata` | develop | `Cognilogical/NeuroStrata` | main | 170 behind / 604 ahead (intentional) |
| security-audit-skill | `c1c8a8c14710…` | `pratik-saptarshi/security-audit-skill` | develop | `cloudflare/security-audit-skill` | main | 0/0, pin = fork head |
| ub-mode | `57a8bdd28e45…` | `pratik-saptarshi/ub-mode` | develop | `unclebob/ub-mode` | master | 0/0, pin 1 behind fork head |
| neurostrata-ops | — | local `~/workspace/neurostrata/` | — | — | — | no commit pin (explicitly excluded from freshness checks) |

Each entry: `tree`, `pin`, `repo`, `branch`, `parent` (nullable), `parent_branch`, `policy` (`sync-then-repin` | `repin` | `keep`), `rationale`.

- [ ] **Step 1:** Write a failing test that loads `.github/vendor-sources.json` and asserts: 13 entries; every entry has the required keys; the 4 sync-first trees have `policy: sync-then-repin`; `craft-anything` and `neurostrata` have `policy: keep` with a non-empty rationale; `neurostrata-ops` is absent.
- [ ] **Step 2:** Run it; confirm it fails on the missing file.
- [ ] **Step 3:** Create `.github/vendor-sources.json` from the table above.
- [ ] **Step 4:** Run the test; confirm it passes.
- [ ] **Step 5:** Add a CI step validating that every tree with a manifest has an SSOT entry and vice versa (count-asserted), and that `pin` matches the 40-hex/7-hex commit in that tree's `PROVENANCE.md`.
- [ ] **Step 6:** Commit.

### Task 2: Snapshot pre-sync state and prove fork-only commits are identifiable

**Files:**
- Create: `scripts/vendor-sync.sh` (shared helpers: `snapshot`, `mirror`, `merge-forward`, `verify-ancestry`)
- Test: `scripts/tests/test_vendor_sync.sh`

- [ ] **Step 1:** Write a failing test that, given a local fixture fork (mirror branch + working branch with a synthetic "fork-only" commit) and a synthetic upstream with new commits, runs the helpers and asserts: the working branch contains the fork-only commit and the upstream commits; the mirror branch equals upstream head; a deliberately dropped fork-only commit fails the ancestry gate.
- [ ] **Step 2:** Run it; confirm it fails.
- [ ] **Step 3:** Implement `snapshot` (print `{repo,branch,sha}` for mirror, working, upstream), `merge-forward` (merge mirror into working with `--no-ff`, never force), and `verify-ancestry` (assert every pre-sync working-only commit is an ancestor of the post-sync head).
- [ ] **Step 4:** Run the test; confirm it passes.
- [ ] **Step 5:** Run `snapshot` against all 4 real forks and save output to `docs/vendor-sync-snapshot-2026-11-19.md` (the rollback record).
- [ ] **Step 6:** Commit.

---

## Phase B — Sync the four forks (owner decision: sync first)

For each fork, branch pairs verified this session:

| Fork | Mirror branch | Working branch (default) | Upstream / branch | Fork-only commits to preserve |
|---|---|---|---|---|
| `pratik-saptarshi/install` | `main` | `main` | `Homebrew/install/main` | 0 |
| `pratik-saptarshi/humanizer` | `main` | `develop` | `blader/humanizer/main` | 0 (amendments live on `feat/scope-and-file-mode-amendments` — leave untouched) |
| `pratik-saptarshi/docs-mcp-server` | `main` | `develop` | `arabold/docs-mcp-server/main` | 10 |
| `pratik-saptarshi/esf` | `master` | `develop` | `mitkox/esf/master` | 11 |

Each task: (1) verify mirror is pristine and snapshot heads; (2) sync mirror from upstream; (3) merge mirror into working; (4) assert upstream head reachable and every fork-only commit still ancestor; (5) inspect content delta; (6) record new head. A conflict that cannot be resolved without dropping a fork commit **stops the task** and reports back — no silent force push.

### Task 3: Sync `pratik-saptarshi/install`

- [ ] **Step 1:** Snapshot `main` SHA (fork) and `Homebrew/install/main` SHA.
- [ ] **Step 2:** `gh repo sync pratik-saptarshi/install --branch main --source Homebrew/install`.
- [ ] **Step 3:** Assert fork `main` == upstream head; 0 fork-only commits before/after.
- [ ] **Step 4:** Record new `main` SHA in the snapshot doc.
- [ ] **Step 5:** Commit the doc update.

### Task 4: Sync `pratik-saptarshi/humanizer`

- [ ] **Step 1:** Snapshot fork `main`, fork `develop`, upstream `main`, and the amendments branch SHAs.
- [ ] **Step 2:** Sync fork `main` from `blader/humanizer/main`.
- [ ] **Step 3:** Merge `main` into `develop` (`--no-ff`); assert upstream head is an ancestor of `develop`.
- [ ] **Step 4:** Assert `feat/scope-and-file-mode-amendments` SHA unchanged.
- [ ] **Step 5:** Record new `develop` SHA. Commit.

### Task 5: Sync `pratik-saptarshi/docs-mcp-server`

- [ ] **Step 1:** Snapshot fork `main`, fork `develop`, upstream `main`; list the 10 fork-only commits on `develop`.
- [ ] **Step 2:** Sync fork `main` from `arabold/docs-mcp-server/main`.
- [ ] **Step 3:** Merge `main` into `develop` (`--no-ff`); resolve conflicts by keeping both sides where they touch different files; where the fork's dependency bump and upstream's touch the same manifest, keep the higher version and record the choice.
- [ ] **Step 4:** Assert all 10 recorded fork-only SHAs are ancestors of new `develop`; assert upstream head is an ancestor. **Stop and report if any is missing.**
- [ ] **Step 5:** Record new `develop` SHA and conflict resolutions. Commit.

### Task 6: Sync `pratik-saptarshi/esf`

- [ ] **Step 1:** Snapshot fork `master`, fork `develop`, upstream `master`; list the 11 fork-only commits on `develop`.
- [ ] **Step 2:** Sync fork `master` from `mitkox/esf/master`.
- [ ] **Step 3:** Merge `master` into `develop` (`--no-ff`). 57 upstream commits carry real conflict risk: review every conflict, keep fork security remediations (filelock/litellm/vite/certifi) at their higher version, and record each resolution.
- [ ] **Step 4:** Assert all 11 fork-only SHAs and the upstream head are ancestors of new `develop`. **Stop and report if any is missing.**
- [ ] **Step 5:** Record new `develop` SHA and resolution log. Commit.

---

## Phase C — Re-vendor at the synced heads

One PR per tree. Each task is a self-contained deliverable that a reviewer can reject independently.

### Task 7: Re-vendor `homebrew-install` at new fork `main`

- [ ] **Step 1:** Fetch the synced fork `main` head; verify full tree is available.
- [ ] **Step 2:** Replace `reference/homebrew-install/` wholesale with the pinned tree; exclude `.git` only (no symlinks per existing provenance).
- [ ] **Step 3:** Regenerate `.github/vendor-homebrew-install.sha256` from the final tree.
- [ ] **Step 4:** Confirm tree matches the pinned commit byte-for-byte (exclusions aside) and `vendor-integrity` passes.
- [ ] **Step 5:** Update `PROVENANCE.md`: pin, snapshot date, freshness block, note that the fork was synced from `Homebrew/install` first.
- [ ] **Step 6:** Run gitleaks + docs-lint; confirm clean. Commit, push, open PR, link it.

### Task 8: Re-vendor `humanizer` at new fork `develop`

- [ ] **Step 1–6:** as Task 7, for `humanizer`. Preserve the note that AEP's `skills/humanizer/` carries local amendments and that those never land in the reference tree. Verify `skills/humanizer/` is untouched.

### Task 9: Re-vendor `docs-mcp-server` at new fork `develop`

- [ ] **Step 1–6:** as Task 7, for `docs-mcp-server`. Keep `.env.example` (faithful snapshot). Update the branch note to record the sync of fork `main` and merge into `develop`, and list the new dependency deltas vs the previous pin.

### Task 10: Re-vendor `esf` at new fork `develop`

- [ ] **Step 1:** Fetch the synced head.
- [ ] **Step 2:** Replace `reference/esf/` wholesale; exclude `.git` and `bin/` (per existing provenance).
- [ ] **Step 3:** Regenerate `.github/vendor-esf.sha256`.
- [ ] **Step 4:** Verify byte-fidelity and `vendor-integrity`.
- [ ] **Step 5:** Update `PROVENANCE.md` with the new pin, sync record, and the update-history entry (57 upstream commits merged).
- [ ] **Step 6:** Re-run the secret scan. The allowlisted synthetic fixtures in `internal/factory/redact_test.go` / `evidence_test.go` must still be the only hits; any new finding gets a path allowlist with rationale. Commit, push, open PR, link it.

---

## Phase D — Re-pin the pins that trail a current fork (no sync needed)

These forks are already at their upstream heads (0 behind); only the vendored pin is stale. Re-pin at the current fork head.

### Task 11: Re-pin `elephant-goldfish-model` (45 commits behind fork head)

- [ ] **Step 1:** Confirm fork `develop` == upstream `main` at execution time (re-run compare; if drift appeared, stop and route to the sync path).
- [ ] **Step 2:** Re-vendor the documented subset (`skills/`, `agents/`, `resources/`, `docs/`, `LICENSE`, `plugin.json`), regenerate `.github/vendor-elephant-goldfish-model.sha256`.
- [ ] **Step 3:** Update `PROVENANCE.md` (new pin, date, freshness block), preserving the "pure mirror" note only if still true.
- [ ] **Step 4:** Verify byte-fidelity, `vendor-integrity`, gitleaks, docs-lint. Commit, push, PR, link.

### Task 12: Re-pin `grim-prompter` (9 commits behind fork head)

- [ ] **Step 1–4:** as Task 11. All-Markdown tree; re-confirm the secret-scan annotation is still accurate.

### Task 13: Re-pin `ub-mode` (1 commit behind fork head)

- [ ] **Step 1–4:** as Task 11. Re-confirm the "License: NONE" note is still accurate at the new head; if a license appeared upstream, stop and report rather than silently leaving the note stale.

---

## Phase E — Make provenance answer the question, and keep it answered

### Task 14: Normalize provenance headers and add freshness blocks

**Files:** modify the 12 `reference/*/PROVENANCE.md` files (skip `neurostrata-ops` or add a local-source note only).

- [ ] **Step 1:** Add `**True upstream:** <parent>` to `reference/esf/PROVENANCE.md` and `reference/harness2/PROVENANCE.md` (currently label the fork as "Upstream" without naming `mitkox/esf` / `google-research/harness2`).
- [ ] **Step 2:** Normalize `craft-anything` to `**Source (fork):** …` while retaining the `storytold/craft-anything` upstream line.
- [ ] **Step 3:** Add a `## Freshness` block to every provenance file: `Pinned commit`, `Pin date`, `Referenced repo @ pin`, `True upstream @ pin`, `Last freshness check`, `Policy`, and a pointer to `.github/vendor-sources.json`.
- [ ] **Step 4:** For `craft-anything` and `neurostrata`, state the keep decision verbatim in the freshness block (D2 at boundary; intentional 604-ahead divergence), so a future auditor does not misread them as forgotten.
- [ ] **Step 5:** Run docs-lint; confirm clean. Commit, push, PR, link.

### Task 15: Add the weekly freshness check (non-gating)

**Files:**
- Create: `scripts/vendor_freshness.py`
- Create: `.github/workflows/vendor-freshness.yml`
- Test: `scripts/tests/test_vendor_freshness.py`

- [ ] **Step 1:** Write failing tests: (a) stale pin → reported behind by N; (b) fork behind parent → reported; (c) missing SSOT entry → reported, not skipped; (d) a current pin → no finding; (e) `neurostrata-ops` ignored; (f) total test count asserted.
- [ ] **Step 2:** Run them; confirm failures.
- [ ] **Step 3:** Implement `vendor_freshness.py`: read `.github/vendor-sources.json`; for each entry with a `pin` and `repo`, call `gh api repos/<repo>/compare/<pin>...<branch>` for pin-vs-fork-head and, when `parent` is set, `gh api repos/<parent>/compare/<parent_branch>...<owner>:<branch>` for fork-vs-upstream. Emit a deterministic JSON report plus a Markdown issue body. `policy: keep` entries are reported as "recorded keep", not as failures.
- [ ] **Step 4:** Make the tests pass, including the mutation cases. Remove the checker's SSOT entry and confirm the test that expects a finding fails — proving the checker does not silently skip.
- [ ] **Step 5:** Add `.github/workflows/vendor-freshness.yml`: `schedule: cron` weekly, `workflow_dispatch`, read-only `GITHUB_TOKEN`, no required check, opens or updates one tracking issue keyed by a stable marker. No auto-merge, no PR creation.
- [ ] **Step 6:** actionlint the workflow; run the full test suite; commit, push, PR, link.

---

## Phase F — Close out

### Task 16: Record the freshness baseline and verify everything

- [ ] **Step 1:** After all re-vendor PRs merge, run `vendor_freshness.py` against `develop` and save the report to `docs/vendor-freshness-baseline-2026-11-19.md`.
- [ ] **Step 2:** Verify every sync target's working branch contains the pre-sync fork-only commits and the upstream head (Task 2's helper, read-only mode).
- [ ] **Step 3:** Verify all 13 manifests match their trees (`vendor-integrity`) and all pinned trees match their commits.
- [ ] **Step 4:** Run the full AEP required-check set on each PR before merge; do not merge any PR with an unresolved review thread.
- [ ] **Step 5:** File follow-up issues for anything deliberately deferred (e.g. a fork that drifted again during the migration).

---

## Test Plan

- **Fixture-based sync tests** (Task 2): local git repos, no network; prove mirror sync, forward merge, fork-commit preservation, and the ancestry gate's failure case.
- **Byte-fidelity checks** (Tasks 7–13): manifest regenerated from the final tree, then compare the tree to a fresh `git archive` of the pinned commit (excluding documented exclusions). A stale manifest is a failure even if `vendor-integrity` passes.
- **Freshness checker tests** (Task 15): 6 cases including two mutations (stale pin, missing SSOT) and one negative (current pin). Count-asserted so deleting a test cannot make the suite pass.
- **CI gates** (Tasks 1, 7–15): `vendor-integrity`, `security`, `docs-lint`, `shell-lint`, `script-tests`, `actionlint` on every PR; the new freshness workflow is scheduled and never required.
- **Manual gates** (Tasks 5, 6): conflict-resolution logs reviewed before a synced fork is trusted; fork-only SHA ancestry asserted mechanically.

## Acceptance Criteria

1. `.github/vendor-sources.json` exists, covers all 12 pinned trees, and matches each provenance pin.
2. `esf`, `humanizer`, `install`, `docs-mcp-server` working branches contain their true upstream head and 100% of their pre-sync fork-only commits (11, 0, 0, 10 respectively).
3. The 7 re-vendored trees (`esf`, `humanizer`, `install`, `docs-mcp-server`, `elephant-goldfish-model`, `grim-prompter`, `ub-mode`) each match a single pinned commit byte-for-byte (exclusions aside), with regenerated manifests and passing `vendor-integrity`.
4. All 12 provenance files carry a `## Freshness` block; `esf` and `harness2` name their true upstreams; `craft-anything` and `neurostrata` record keep decisions.
5. `vendor_freshness.py` passes its 6 tests, including mutations; the scheduled workflow is non-gating and opens/updates one issue when drift is detected.
6. No PR merges with an unresolved review thread or a failing required check; every PR body and comment is signed per `AGENTS.md`.
7. A post-merge baseline report exists and records the freshness state of all 13 trees.

## Out of Scope

- Editing any `reference/` tree in place, or installing/executing vendored code.
- Re-pinning `craft-anything` (D2 ACCEPT-STALENESS at its budget boundary) or `neurostrata` (intentional 604-ahead divergence) — both are recorded keep decisions, not forgotten pins.
- `neurostrata-ops` (local snapshot, no commit pin) — documented as excluded from freshness checks.
- License changes (notably `ub-mode`'s "License: NONE"), brand-asset policy (`craft-anything`), Dependabot scoping, or CI required-check changes.
- Promising permanent currency: the weekly checker detects subsequent drift; it does not sync or re-vendor automatically.
