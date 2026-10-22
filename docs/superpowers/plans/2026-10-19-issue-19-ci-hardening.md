# CI Hardening (Issue #19) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the 5-job CI workflow in `.github/workflows/ci.yml` for determinism (pinned tools), least privilege (token permissions), and real coverage (boot-gate self-test actually runs).

**Architecture:** Six surgical edits to the existing workflow file plus one small `--self-test-stubs` mode in `scripts/boot-gate.sh` so the self-test can run in CI without the NeuroStrata binary. No new jobs, no restructuring — the workflow's shape stays identical.

**Tech Stack:** GitHub Actions (ubuntu-latest), markdownlint-cli2 (npm), shellcheck, shfmt, gitleaks, bash.

**Spec:** https://github.com/pratik-saptarshi/autonomous-engineering-platform/issues/19

## Global Constraints
- Conventional Commits for every commit; commit as `Musebot-Astro <6238157+pratik-saptarshi@users.noreply.github.com>`.
- The repo has no `.gitignore` — use exact-path `git add`, never `git add -A`.
- Checksum-verified installs are the standard; no unverified binaries.
- YAML must parse after every edit (validate locally before pushing).
- The workflow must stay green on the PR branch after each task — verify via `gh pr checks`.

## Review Focus
- A pinned tool version that doesn't exist (e.g. typo'd npm tag) red-bars CI with a confusing install error — the plan pins only fact-checked versions (markdownlint-cli2@0.18.1 and shellcheck v0.10.0 verified to exist 2026-10-19).
- The `--self-test-stubs` mode must not weaken the real self-test: stub cases must assert the same gate behavior, only the environment is faked.
- `permissions: contents: read` must not break any job — none of the five jobs write anything, but verify each job's log shows no permission error after the change.
- Shellcheck 0.10.0 may flag new warnings the apt version didn't — if it does, fix or justify-disable them; do not silently downgrade.
- A reviewer could reasonably ask "why not SHA-pin the actions too" — Task 6 covers it as an explicit hardening step, not an afterthought.

---

## File Structure

- Modify: `.github/workflows/ci.yml` — the only workflow file; all six hardening edits land here, one task per edit so each can be verified independently.
- Modify: `scripts/boot-gate.sh` — add `--self-test-stubs` mode (runs the 4 stub-based negative cases without requiring the real NeuroStrata binary or daemon).

Each task produces a green CI run on the PR branch as its test.

---

### Task 1: Least-privilege token permissions

**Files:**
- Modify: `.github/workflows/ci.yml` (top level, after the `on:` block)

**Interfaces:**
- Consumes: nothing (first task)
- Produces: workflow with `permissions: contents: read` — later tasks inherit this; none of them need write access.

- [ ] **Step 1: Add the permissions block**

In `.github/workflows/ci.yml`, after the `on:` block and before `jobs:`, insert:
```yaml
permissions:
  contents: read
```

- [ ] **Step 2: Validate YAML locally**

Run: `python3 -c "import yaml; d=yaml.safe_load(open('.github/workflows/ci.yml')); print(d['permissions'])"`
Expected: `{'contents': 'read'}`

- [ ] **Step 3: Commit and push, verify all 5 jobs still pass**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: declare least-privilege permissions (contents: read)"
git push origin feat/ci-platform-gates
```
Then: `gh pr checks 12 --watch` — all 5 jobs must pass (no job writes anything, so none should break; if a job fails on permissions, investigate before proceeding).

---

### Task 2: Pin markdownlint-cli2

**Files:**
- Modify: `.github/workflows/ci.yml` (docs-lint job)

**Interfaces:**
- Consumes: Task 1's permissions block (inherited)
- Produces: deterministic docs-lint job

- [ ] **Step 1: Pin the version**

Change:
```yaml
      - run: npx --yes markdownlint-cli2 "**/*.md"
```
to:
```yaml
      - run: npx --yes markdownlint-cli2@0.18.1 "**/*.md"
```
(`0.18.1` verified to exist on npm 2026-10-19; it is the version the issue suggested and it predates the 0.23.x line, minimizing rule-change risk against the v1 baseline config.)

- [ ] **Step 2: Validate YAML locally**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML-OK')"`

- [ ] **Step 3: Commit and push, verify docs-lint passes**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: pin markdownlint-cli2@0.18.1 for deterministic docs-lint"
git push origin feat/ci-platform-gates
```
Then: `gh pr checks 12 --watch` — docs-lint must pass (if 0.18.1 introduces new findings vs latest, fix them or document why; do not just disable more rules).

---

### Task 3: Pin shellcheck via checksum-verified tarball

**Files:**
- Modify: `.github/workflows/ci.yml` (shell-lint job)

**Interfaces:**
- Consumes: Tasks 1-2 (workflow state)
- Produces: shell-lint job with pinned, verified shellcheck v0.10.0

- [ ] **Step 1: Replace the apt install with a pinned tarball install**

Change:
```yaml
          sudo apt-get update -qq && sudo apt-get install -y -qq shellcheck
```
to:
```yaml
          curl -sSL --retry 3 -o /tmp/shellcheck.tar.xz https://github.com/koalaman/shellcheck/releases/download/v0.10.0/shellcheck-v0.10.0.linux.x86_64.tar.xz
          echo "<SHA256>  /tmp/shellcheck.tar.xz" | sha256sum -c -
          tar xJf /tmp/shellcheck.tar.xz -C /tmp && sudo install -m 755 /tmp/shellcheck-v0.10.0/shellcheck /usr/local/bin/shellcheck
```
(v0.10.0 and the `shellcheck-v0.10.0.linux.x86_64.tar.xz` asset verified to exist 2026-10-19. Koalaman publishes no checksums file, so: download the tarball over HTTPS, compute `sha256sum`, and embed the hash in place of `<SHA256>` — trust-on-first-use, documented in the step as such. This matches the repo's checksum-verified standard as closely as the upstream allows.)

- [ ] **Step 2: Validate YAML locally**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML-OK')"`

- [ ] **Step 3: Commit and push, verify shell-lint passes**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: pin shellcheck v0.10.0 via checksum-verified tarball"
git push origin feat/ci-platform-gates
```
Then: `gh pr checks 12 --watch` — shell-lint must pass. If shellcheck 0.10.0 flags new warnings the apt version didn't, fix the script or add a justified `# shellcheck disable=` (same standard as the existing SC2012 disables); do not downgrade the version to silence it.

---

### Task 4: Add --retry to the gitleaks download

**Files:**
- Modify: `.github/workflows/ci.yml` (security job)

**Interfaces:**
- Consumes: Tasks 1-3 (workflow state)
- Produces: security job resilient to transient network blips

- [ ] **Step 1: Add --retry to the curl**

Change:
```yaml
          curl -sSL -o /tmp/gitleaks.tar.gz https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/gitleaks_8.24.3_linux_x64.tar.gz
```
to:
```yaml
          curl -sSL --retry 3 --retry-delay 5 -o /tmp/gitleaks.tar.gz https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/gitleaks_8.24.3_linux_x64.tar.gz
```

- [ ] **Step 2: Validate YAML, commit, push, verify security job passes**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML-OK')"
git add .github/workflows/ci.yml
git commit -m "ci: add --retry to gitleaks download against transient network failures"
git push origin feat/ci-platform-gates
```
Then: `gh pr checks 12 --watch` — security must pass.

---

### Task 5: Run boot-gate --self-test-stubs in CI

**Files:**
- Modify: `scripts/boot-gate.sh` (add `--self-test-stubs` mode)
- Modify: `.github/workflows/ci.yml` (shell-lint job, add execution step)

**Interfaces:**
- Consumes: Tasks 1-4 (workflow state)
- Produces: CI actually executes the boot-gate correctness proof

**Why a new mode:** the full `--self-test` ends with a real-environment positive case requiring the NeuroStrata binary and daemon, which don't exist on GitHub runners. The 4 stub-based negative cases are self-contained. `--self-test-stubs` runs exactly those 4, so CI tests gate logic without the environment.

- [ ] **Step 1: Write the failing test — run stubs mode in a binary-less environment**

Run: `env -i PATH=/usr/bin:/bin HOME="$HOME" bash scripts/boot-gate.sh --self-test-stubs`
Expected: FAIL — `--self-test-stubs` is not a recognized flag (usage error, exit 2).

- [ ] **Step 2: Implement `--self-test-stubs` in `scripts/boot-gate.sh`**

Add a `STUBS_ONLY` variable (default empty). In `self_test()`, when `STUBS_ONLY` is set:
- Skip the real-environment positive case at the end.
- For the `gh-auth-fail` case (empty STUB_CASE), do NOT delegate to the real binary — instead handle a `healthy` stub case in the fake neurostrata-mcp that prints the healthy daemon line and a valid guard listing (3 memories incl. "Destructive GitHub actions"), so the gate passes daemon/guards and fails only on the stubbed `gh`.

Wire the CLI: add a `--self-test-stubs)` case that sets `STUBS_ONLY=1` then runs the same `self_test` flow. Update the usage line to `usage: $0 [--self-test | --self-test-stubs]`.

- [ ] **Step 3: Run the new mode locally without the real binaries**

Run: `env -i PATH=/usr/bin:/bin HOME="$HOME" bash scripts/boot-gate.sh --self-test-stubs`
Expected: `SELF-TEST: all ok` (4 stub cases pass, no real-environment case).

- [ ] **Step 4: Regression — full --self-test still passes in the real environment**

Run: `./scripts/boot-gate.sh --self-test`
Expected: `SELF-TEST: all ok` (4 stub cases + real-environment positive).

- [ ] **Step 5: Add the CI step**

In the shell-lint job, after the `shfmt` check, add:
```yaml
      - run: ./scripts/boot-gate.sh --self-test-stubs
```

- [ ] **Step 6: Validate, commit, push, verify**

```bash
bash -n scripts/boot-gate.sh && python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('OK')"
git add scripts/boot-gate.sh .github/workflows/ci.yml
git commit -m "ci: run boot-gate --self-test-stubs in shell-lint"
git push origin feat/ci-platform-gates
```
Then: `gh pr checks 12 --watch` — shell-lint must pass with the new step.

---

### Task 6: SHA-pin third-party actions (hardening)

**Files:**
- Modify: `.github/workflows/ci.yml` (all `uses:` lines)

**Interfaces:**
- Consumes: Tasks 1-5 (final workflow state)
- Produces: fully pinned action references

- [ ] **Step 1: Look up current SHAs and pin**

For each of `actions/checkout@v4` (3 occurrences) and `actions/setup-go@v5` (2 occurrences):
1. Resolve the tag to its commit SHA at implementation time: `gh api repos/actions/checkout/commits/v4 --jq .sha` (and likewise for setup-go).
2. Replace `actions/checkout@v4` with `actions/checkout@<sha> # v4` (keep the version as a comment so upgrades remain discoverable).

- [ ] **Step 2: Validate YAML, commit, push, verify all jobs pass**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML-OK')"
git add .github/workflows/ci.yml
git commit -m "ci: SHA-pin third-party actions against tag-rewrite attacks"
git push origin feat/ci-platform-gates
```
Then: `gh pr checks 12 --watch` — all 5 jobs must pass.

---

## Self-Review

**1. Spec coverage:** Issue #19 lists 6 items. Tasks map: permissions→T1, markdownlint pin→T2, shellcheck pin→T3, curl --retry→T4, boot-gate self-test→T5, SHA-pinning→T6. All covered.

**2. Step scan:** Each step is one action with a checkable result. The TOFU checksum step (T3) is explicit about what the implementer must do (download, hash, embed) rather than leaving a placeholder.

**3. Type consistency:** N/A (config-only changes; the one code change in T5 defines `STUBS_ONLY` once and uses it consistently).

**4. Review Focus:** Covered in the header — pinned-version existence verified, stubs-mode fidelity, permissions regression check, shellcheck version-drift handling, SHA-pinning made explicit.

**5. Proportion:** The plan is longer than the diff it describes, but the diff is 6 surgical edits whose correctness depends on exact versions, SHAs, and CI behavior — the plan carries those decisions, not the code.
