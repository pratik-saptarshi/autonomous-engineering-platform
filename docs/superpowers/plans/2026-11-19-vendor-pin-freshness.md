# Vendor Pin Freshness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the AEP-owned forks that trail their true upstreams up to date, re-vendor the affected pins, and make drift *detectable within seven days by an owned issue* — not merely "measured once." This plan does not promise permanent currency: upstream can move after any sync, and the weekly detector reports that drift rather than fixing it.

**Architecture:** Single source of truth. Each `reference/<tree>/PROVENANCE.md` gains a one-line machine-readable `vendor-freshness` block holding its pin/repo/branch/upstream/policy. A stdlib Python script enumerates those blocks, derives the graph *at execution time* (no frozen numbers), calls the GitHub compare API, and emits a deterministic report. The one-time migration side: back up each fork, perform only the syncs that are real at execution time, merge upstream forward into the working branch preserving fork-only content, re-vendor each affected tree wholesale with a quarantine/disposition gate, and rewrite its provenance (which updates the freshness block in the same PR). A weekly non-gating workflow opens or updates one owned tracking issue.

**Tech Stack:** GitHub CLI (`gh repo sync`, `gh api`), git, bash, Python 3 (stdlib), GitHub Actions.

**Spec:** the 2026-11-19 audit (13 vendor manifests on `origin/develop@d34bf26`) plus `reference/<tree>/PROVENANCE.md`. All numbers in this plan are *the state at drafting* and must be re-derived at execution time by Task 1 — the audit was already stale within one session (humanizer moved from 8 behind to 0 behind; craft-anything's fork moved from pristine to 3 behind upstream).

## Global Constraints

- **Owner decision (2026-11-19): sync the forks first.** Where a fork genuinely trails its upstream, pull upstream in, then pin the re-vendor at the synced fork head. Do not pin a trailing fork as-is. A fork already at upstream head is re-pinned as-is (no no-op sync theater).
- **Single source of truth:** `PROVENANCE.md` per tree. No parallel JSON/SSOT file. The freshness block lives *inside* the provenance file that every re-vendor already rewrites, so it cannot be born stale.
- **Execution-time derivation:** the script computes pin/fork/upstream/divergence from GitHub, not from numbers copied into this plan. Frozen numbers are illustrative only.
- **Fork-first, non-destructive:** mirror branch (`master`/`main`) ← upstream via `gh repo sync` (identical names only); then `--no-ff` merge forward into the working branch (`develop`/`main`). No force-push to any working branch. Before any external mutation: preserve objects (mirror clone or bundle + timestamped backup tag) and re-run the compare as a last-second guard.
- **Substantive preservation:** a merge passes only if every pre-existing fork-only remediation is present *by content at the higher version* (e.g. esf: filelock 4.2.9, certifi 2026.10.23, vite 8.3.5, undici 8.12.3; docs-mcp-server: follow-redirects 1.16.2, minimatch `^11.0.5`, lockfile 3.4.1). Ancestry alone is not evidence.
- **Disposition on re-vendor:** enumerate instruction surfaces (`AGENTS.md`, `CLAUDE.md`, `.claude/`, `.githooks/`, `.github/workflows/`, plugin manifests, deps with lifecycle scripts), quarantine per `craft-anything`'s definition, document each, and exclude consistently from the manifest. A new secret-shaped hit must be proven synthetic (input-and-assertion fixture, annotated) before a path allowlist — never allowlist by convenience.
- **Byte-fidelity:** a vendored tree matches exactly one pinned commit minus documented exclusions; regenerate the manifest from the final tree in the same change. Never edit a vendored file in place.
- **Durability claim bounded:** detection + an owned issue with a 7-day SLA; the workflow is non-gating and never auto-syncs. Owner of the tracking issue: the AEP maintainer (repo owner), recorded in the issue body.
- **Signing:** all PR titles/bodies and issue/comment text signed `— Terminator3000-DarkCrouton` per `AGENTS.md`.

## Review Focus

1. **Content loss during merge** — a conflict resolution can keep a fork-only commit as an ancestor while dropping its patch. Tasks 3–4 diff remediation versions before/after; Acceptance Criteria gate on content, not ancestry.
2. **Irreversible external mutation** — a mis-aimed sync destroys public fork commits. Task 1 preserves objects and emits an executable rollback runbook before any mutation; Task 2 pre-flights every target.
3. **New upstream content as instruction/secret surface** — incoming AGENTS.md/hooks/workflows could govern AEP if left live. Tasks 5–8 include a disposition gate and synthetic-fixture verification before any allowlist.
4. **A detector that silently skips** — missing metadata, a changed repo/branch, or a removed tree must produce a finding. Task 10 enumerates expected trees from `reference/*/` and mutation-tests each failure path in CI (`--self-test`).
5. **Stale-at-birth data** — humanizer and craft-anything moved during the audit. Task 1 re-derives everything live; no task trusts a froze-table value.

---

## Phase 0 — Execution-time ground truth and safety harness (no external writes)

### Task 1: Derive the live graph and record a rollback harness

**Files:**
- Create: `scripts/vendor_graph.py` (stdlib; prints JSON of tree→{pin, repo, branch, parent, parent_branch, divergence, policy})
- Create: `docs/vendor-sync-preflight-2026-11-19.md` (generated report + rollback runbook)
- Modify: `.github/workflows/ci.yml` (validate freshness blocks)
- Test: `scripts/tests/test_vendor_graph.py`

- [ ] **Step 1:** Write a failing test that, with mocked `gh api` responses, asserts the parser reads the `vendor-freshness` block from every `reference/*/PROVENANCE.md` (13 top-level files) and returns exactly 13 entries, with `neurostrata-ops` as `{"pin":null,"policy":"local"}` and the 3 nested `harness2/third_party/*/PROVENANCE.md` files ignored.
- [ ] **Step 2:** Run it; confirm failure on the missing module/blocks.
- [ ] **Step 3:** Implement `vendor_graph.py`: glob `reference/*/PROVENANCE.md`; parse a one-line HTML comment `<!-- vendor-freshness: {…} -->` with `json.loads`; fields `tree, pin, repo, branch, parent, parent_branch, policy, decision_date, review_due`. For each entry with a `pin`, call `gh api repos/<repo>/compare/<pin>...<branch>` (pin vs fork head) and, when `parent` is set, `gh api repos/<parent>/compare/<parent_branch>...<owner>:<branch>` (fork vs upstream). Output deterministic JSON.
- [ ] **Step 4:** Run the test; confirm it passes. Add a test that a malformed or missing block produces a finding (not a skip).
- [ ] **Step 5:** Run `vendor_graph.py` **live** and commit its output as `docs/vendor-sync-preflight-2026-11-19.md`. This is the authoritative starting state; if it disagrees with this plan's tables, the live output wins and Task 2 reclassifies accordingly.
- [ ] **Step 6:** For each fork that will be mutated, preserve objects: `git clone --mirror <fork> /tmp/vendor-backup-<tree>-2026-11-19.git` and `git -C <clone> tag backup/pre-sync-2026-11-19 <working-sha> <mirror-sha>`; record the commands and resulting SHAs in the preflight doc. Write the executable rollback runbook (revert the merge commit on the working branch; separately-authorized restore of a mirror from the bundle) into that doc.
- [ ] **Step 7:** Add a CI step validating that every `reference/*/PROVENANCE.md` has a parseable freshness block and that its `pin` matches the commit named in the prose. Count-assert 13 entries and assert the presence of the `local` entry — content, not just counts.
- [ ] **Step 8:** Commit.

### Task 2: Pre-flight each fork and classify actions

**Files:**
- Create: `scripts/vendor_sync.sh` (helpers: `verify-target`, `merge-forward`, `assert-content`, `rollback-plan`)
- Test: `scripts/tests/test_vendor_sync.sh` (wired into `script-tests` in `ci.yml`)

- [ ] **Step 1:** Write failing fixture tests (local git repos, no network): mirror FF from upstream; `--no-ff` forward merge preserving a fork-only commit; `assert-content` failing when a remediation version is downgraded; `verify-target` failing when a branch/SHA does not match the preflight.
- [ ] **Step 2:** Run them; confirm failures.
- [ ] **Step 3:** Implement the helpers. `verify-target` re-runs the compare API and refuses to act if the live state differs from the preflight. `merge-forward`: clone fork, add upstream remote, fetch mirror + working, `git checkout <working> && git merge --no-ff upstream/<mirror>`, assert every pre-sync fork-only SHA is an ancestor, then `assert-content`, then push. `rollback-plan` prints the runbook commands for the target.
- [ ] **Step 4:** Make the tests pass. Wire `bash scripts/tests/test_vendor_sync.sh` explicitly into the `script-tests` job in `.github/workflows/ci.yml` (that job enumerates scripts; there is no auto-discovery for `.sh`).
- [ ] **Step 5:** Run `verify-target` for all four candidate forks and record the action classification in the preflight doc. Expected shape (re-derived live): `install` → real FF of `main` + no working merge (mirror == working); `docs-mcp-server` and `esf` → mirror already == upstream, so **forward merge only**; `humanizer` → fork == upstream and == working, so **no sync**, reclassify to `repin` (pin ~27 behind fork head).
- [ ] **Step 6:** Commit.

---

## Phase A — Fork mutations (only the actions Task 2 proves are real)

Each task: re-run `verify-target`; back up; perform the classified action; run `assert-content`; record the new head. A missing remediation or an unresolved conflict **stops the task** and reports back — no silent resolution.

### Task 3: Sync `pratik-saptarshi/install`

- [ ] **Step 1:** `verify-target` (fork `main` behind `Homebrew/install/main`); confirm 0 fork-only commits.
- [ ] **Step 2:** `gh repo sync pratik-saptarshi/install --branch main --source Homebrew/install` (mirror == working, so no separate merge).
- [ ] **Step 3:** Assert fork `main` == upstream head; record new SHA.

### Task 4: Forward-merge upstream into `pratik-saptarshi/docs-mcp-server@develop`

- [ ] **Step 1:** `verify-target`; confirm fork `main` already == `arabold/main`, and list the 10 fork-only commits on `develop`.
- [ ] **Step 2:** `merge-forward` (merge fork `main` into `develop` with `--no-ff`). No mirror sync needed.
- [ ] **Step 3:** `assert-content`: follow-redirects 1.16.2, minimatch `^11.0.5`, `patternMatcher.ts` off the removed `makeRe` API, lockfile root 3.4.1 must all still be present at >= their pre-sync versions. Record the resolution log.
- [ ] **Step 4:** Assert all 10 fork-only SHAs and the upstream head are ancestors. **Stop if any is missing.**

### Task 5: Forward-merge upstream into `pratik-saptarshi/esf@develop`

- [ ] **Step 1:** `verify-target`; confirm fork `master` already == `mitkox/master`, and list the 11 fork-only commits on `develop`.
- [ ] **Step 2:** `merge-forward` (57 incoming upstream commits). Review every conflict; keep fork remediations at the higher version.
- [ ] **Step 3:** `assert-content`: filelock 4.2.9, certifi 2026.10.23, vite 8.3.5, undici 8.12.3, litellm 1.108.3 present at >= pre-sync versions. Record each conflict resolution.
- [ ] **Step 4:** Assert all 11 fork-only SHAs and the upstream head are ancestors. **Stop if any is missing.**

---

## Phase B — Re-vendor the affected trees

One PR per tree. Every task includes the disposition gate and manifest regeneration. Canonical manifest command (from inside the tree): `find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > ../../.github/vendor-<tree>.sha256`, then CI's `sha256sum -c` + unlisted-files `comm` check must pass.

### Task 6: Re-vendor `homebrew-install` at synced fork `main`

- [ ] **Step 1:** Fetch the synced head; enumerate instruction surfaces and secrets in the new tree; quarantine/document per Global Constraints.
- [ ] **Step 2:** Replace `reference/homebrew-install/` wholesale (exclude `.git`; no symlinks per existing provenance).
- [ ] **Step 3:** Regenerate `.github/vendor-homebrew-install.sha256`; verify tree↔commit byte-fidelity against a fresh `git archive` of the pin (exclusions aside).
- [ ] **Step 4:** Rewrite `PROVENANCE.md`: new pin, snapshot date, sync record, freshness block with `policy: repin`. Keep `.env.example`-style faithful content; secret scan clean.
- [ ] **Step 5:** Run `vendor-integrity`, `security`, `docs-lint`. Commit, push, open PR, link it.

### Task 7: Re-vendor `humanizer` at fork head (reclassified `repin`, no sync)

- [ ] **Step 1–5:** as Task 6. Preserve the note that AEP's `skills/humanizer/` carries local amendments that never land in the reference tree; verify that directory is untouched. Confirm the `feat/scope-and-file-mode-amendments` branch SHA is unchanged.
- [ ] **Step 6:** Record that the fork is now identical to upstream, so this is a re-pin, not a sync.

### Task 8: Re-vendor `docs-mcp-server` at synced fork `develop`

- [ ] **Step 1–5:** as Task 6. Keep `.env.example`. Update the branch note with the forward-merge record and the dependency deltas; verify no dependency was downgraded (`assert-content` output attached to the PR).

### Task 9: Re-vendor `esf` at synced fork `develop`

- [ ] **Step 1:** Fetch the synced head; disposition gate (instruction surfaces, lifecycle-script deps).
- [ ] **Step 2:** Replace `reference/esf/` wholesale; exclude `.git` and `bin/` (current manifest has 0 `bin/` entries).
- [ ] **Step 3:** Regenerate `.github/vendor-esf.sha256`; verify byte-fidelity.
- [ ] **Step 4:** Update `PROVENANCE.md` with the new pin, the 57-commit forward-merge record, the update-history entry, and the freshness block.
- [ ] **Step 5:** Re-run the secret scan. The allowlisted synthetic fixtures in `internal/factory/redact_test.go` / `evidence_test.go` must still be the only hits; any new hit must be proven synthetic (input-and-assertion, annotated) before a path allowlist. Commit, push, PR, link.

### Task 10: Re-pin pins that trail a current fork (no sync needed)

**Files:** `reference/elephant-goldfish-model/`, `reference/grim-prompter/`, `reference/ub-mode/` (+ manifests + provenance).

- [ ] **Step 1:** For each, re-run the live compare. If a fork has drifted behind upstream since the audit, stop and route it to the sync path instead.
- [ ] **Step 2:** Re-vendor the documented subset per tree, regenerate manifests, verify byte-fidelity.
- [ ] **Step 3:** Update `PROVENANCE.md` (new pin, date, sync record, freshness block). `elephant-goldfish-model`: drop the "pure mirror" note only if no longer true. `ub-mode`: re-confirm "License: NONE"; if a license appeared, stop and report rather than leave a stale note. `grim-prompter`: re-confirm the clean secret-scan annotation.
- [ ] **Step 4:** Run `vendor-integrity`, `security`, `docs-lint` for each. Commit, push, one PR per tree, link each.

---

## Phase C — Durable detection

### Task 11: Normalize provenance into the single source of truth

**Files:** all 13 top-level `reference/*/PROVENANCE.md` (the 3 nested `harness2/third_party/*` files are NOT independently pinned and are out of scope).

- [ ] **Step 1:** Add the one-line `vendor-freshness` block to each of the 13 files. For the 12 pinned trees: `tree, pin, repo, branch, parent, parent_branch, policy, decision_date, review_due`. For `neurostrata-ops`: `{"tree":"neurostrata-ops","pin":null,"policy":"local"}`.
- [ ] **Step 2:** Add `**True upstream:** <parent>` to `reference/esf/PROVENANCE.md` and `reference/harness2/PROVENANCE.md` (they currently label the fork as "Upstream" without naming `mitkox/esf` / `google-research/harness2`). Normalize `craft-anything` to `**Source (fork):** …` while retaining the `storytold` upstream line.
- [ ] **Step 3:** Add a `## Freshness` section explaining the block, the owner (repo maintainer), and the 7-day SLA. For `craft-anything`, record that the D2 keep decision is **due for review now** (fork is no longer a pristine mirror — it moved 3 behind upstream mid-audit): `policy: keep` with `review_due: 2026-11-19`, not a silent permanent exemption. For `neurostrata`, record the intentional 604-ahead divergence with a quarterly `review_due`.
- [ ] **Step 4:** Run the Task 1 CI validator; confirm 13 parseable blocks. docs-lint clean. Commit, push, PR, link.

### Task 12: Add the weekly detector (non-gating, issues: write)

**Files:**
- Create: `scripts/vendor_freshness.py`
- Create: `.github/workflows/vendor-freshness.yml`
- Test: `scripts/tests/test_vendor_freshness.py`

- [ ] **Step 1:** Write failing tests: (a) stale pin → finding with behind count; (b) fork behind parent → finding; (c) a tree in `reference/*/` with no freshness block → finding, not skip; (d) current pin → no finding; (e) `local` entry ignored; (f) `policy: keep` past `review_due` → "decision due" finding, not silent pass; (g) total test count asserted.
- [ ] **Step 2:** Run them; confirm failures.
- [ ] **Step 3:** Implement `vendor_freshness.py` using `vendor_graph.py` for live data. Emit deterministic JSON + a Markdown issue body with a stable marker. `--self-test` runs all mutation cases in CI.
- [ ] **Step 4:** Make all tests pass, including the missing-block mutation. Deleting a provenance block must produce a finding — prove it in the test.
- [ ] **Step 5:** Add `.github/workflows/vendor-freshness.yml`: `schedule: cron` weekly + `workflow_dispatch`; **permissions: `contents: read` and `issues: write` (and nothing else)** — the repo's `dependabot-reference-guard.yml` and `actionlint.yml` use this exact pattern because issue creation is a write; a read-only token would 403 and the non-gating job would silently die. Opens or updates one tracking issue keyed by a stable marker; reopens a closed issue; concurrency group prevents duplicate runs. No required check, no auto-merge, no PR creation.
- [ ] **Step 6:** actionlint the workflow. Verify by `workflow_dispatch`: first run creates the issue, second updates the same issue. Commit, push, PR, link.

---

## Phase D — Close out

### Task 13: Baseline and verify

- [ ] **Step 1:** After all PRs merge, run `vendor_freshness.py` on `develop` and save `docs/vendor-freshness-baseline-2026-11-19.md`.
- [ ] **Step 2:** Verify the post-sync content assertions (Tasks 3–5) still hold on each fork's working branch, read-only.
- [ ] **Step 3:** Verify all 13 manifests match their trees and all 12 pinned trees match their commits.
- [ ] **Step 4:** Every PR merges only with required checks green and all review threads resolved; all text signed per `AGENTS.md`.
- [ ] **Step 5:** File follow-up issues for deferred items (e.g. `craft-anything` D2 re-review; any fork that drifted again during the migration).

---

## Test Plan

- **Fixture-based sync tests (Task 2):** local repos; mirror FF, forward merge, fork-commit preservation, `assert-content` downgrade failure, `verify-target` mismatch failure. Wired explicitly into `script-tests`.
- **Graph/parse tests (Task 1):** 13 top-level blocks parsed, nested files ignored, malformed/missing block → finding.
- **Content gates (Tasks 3–5):** explicit version assertions for every known remediation; a downgrade fails the merge even when ancestry passes.
- **Byte-fidelity (Tasks 6–10):** manifest regenerated from the final tree, then compare to a fresh `git archive` of the pin (exclusions aside). CI's `vendor-integrity` must pass.
- **Detector tests (Task 12):** 7 cases incl. missing-block, keep-past-due, and a count assertion; run as CI `--self-test`, not a one-off manual mutation.
- **Workflow smoke (Task 12):** real `workflow_dispatch` proves issue create + update with `issues: write`.

## Acceptance Criteria

1. `vendor_graph.py` parses freshness blocks from all 13 top-level provenance files; nested third-party provenances are ignored; `neurostrata-ops` is `policy: local`.
2. Every fork mutation that Task 2 classified as real is complete; its working branch contains the upstream head **and** all pre-sync fork-only commits **and** all known remediation content at >= prior versions. No-op syncs are not performed.
3. The re-vendored trees (`homebrew-install`, `humanizer`, `docs-mcp-server`, `esf`, `elephant-goldfish-model`, `grim-prompter`, `ub-mode` — final list per Task 1/2 live data) each match a single pinned commit byte-for-byte (exclusions aside), with regenerated manifests and passing `vendor-integrity`.
4. All 13 provenance files carry a parseable freshness block; `esf`/`harness2` name their true upstreams; `craft-anything` records `review_due: 2026-11-19` as a decision due, not a permanent keep.
5. `vendor_freshness.py` passes its 7 tests incl. mutations; the weekly workflow has `issues: write`, is non-gating, and demonstrably creates/updates one owned issue.
6. No PR merges with an unresolved review thread or failing required check; all PR/issue text signed per `AGENTS.md`.
7. A post-merge baseline report exists and an executable rollback runbook was committed before any external mutation.

## Out of Scope

- Editing any `reference/` tree in place; installing/executing vendored code.
- A parallel SSOT JSON file — provenance is the only source of truth.
- Re-pinning `craft-anything` or `neurostrata` in this plan: both are recorded keep decisions surfaced as due-for-review findings, not silent exemptions. `craft-anything`'s D2 re-review is explicitly deferred to a follow-up issue.
- `neurostrata-ops` freshness (local snapshot, no commit pin).
- License changes (`ub-mode` "License: NONE"), brand-asset policy, Dependabot scoping, required-check changes.
- Promising permanent currency; the detector reports drift with a 7-day SLA and never auto-fixes.
