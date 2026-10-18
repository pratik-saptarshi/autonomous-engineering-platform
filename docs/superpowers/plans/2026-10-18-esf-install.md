# ESF Install + AEP Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install mitkox/esf (Engineering Software Factory) from a pinned commit on this VM as far as local resources allow, and add it to the autonomous-engineering-platform repo as a vendored reference implementation with provenance.

**Architecture:** Two phases. Phase A (install, Tasks 1–4): clone at pinned SHA into `~/workspace/repos/esf`, build the Go factory binaries with the local Go 1.27.2 toolchain, run `make lint` and `make test-unit`, and exercise `factory init` / `config validate` / `doctor` in a scratch directory — stopping honestly where missing infra (Docker, Temporal, CubeSandbox, PostgreSQL) blocks live runs. Phase B (addition, Tasks 5–7): vendor the source tree (minus `.git`) into the AEP repo at `reference/esf/` with a `PROVENANCE.md`, wire it into the AEP docs, and commit on a local branch. No push without explicit authorization.

**Tech Stack:** Go 1.27.2 (`go.mod` pins `go 1.27.2`), ESF `cmd/factory` CLI, Temporal Go SDK v1.49.0 and CubeSandbox Go SDK v0.7.3 (build-time dependencies only — no live services on this VM).

**Spec:** Upstream `https://github.com/mitkox/esf` at commit `d41535d86a13e55fe2357d9e0a108566d68ce1b9` (HEAD as of 2026-10-18; "Add durable sf turn executor with Cube checkpoints and permissions (#40)"). A persistent local spec copy is created in Task 1 at `~/workspace/repos/esf`. Background: ESF is the active Go implementation descended from the mitkox/ecdf TypeScript design pass; 7 ADRs under `docs/adr/` (CubeSandbox-as-fabric, Temporal-for-workflows, harness abstraction, deterministic verification, artifact model, control-plane security boundary, defense-in-depth).

## Global Constraints

- Go toolchain is exactly go1.27.2 at `~/sdk/go`; `go.mod` requires `go 1.27.2`. Run Go commands with `export PATH="$HOME/sdk/go/bin:$HOME/go/bin:$PATH"` and `GOTOOLCHAIN=local`. Do not upgrade or downgrade.
- Node on this VM is v24.20.0; ESF wants Node 26.12.0 for the web frontend. `make frontend` and `make test-frontend` are OUT OF SCOPE here.
- No Docker, no Temporal, no CubeSandbox, no PostgreSQL on this VM. `make test-integration`, `make temporal-up`, and any live `factory run` are OUT OF SCOPE — record as blocked, do not work around with half-configured services.
- ESF is MIT-licensed (copyright 2026 Owain Lewis via the Machinist lineage; fork by mitkox). `LICENSE` must be preserved verbatim in the vendored tree.
- The AEP repo (`pratik-saptarshi/autonomous-engineering-platform`) is public. No credentials, tokens, or `.env` content may enter it. Any `factory.toml` generated during install stays in scratch, never in the repo.
- Commits follow Conventional Commits, matching repo history (`docs:`, `chore:`).
- NEVER push to the AEP repo or any remote without Pratik's explicit per-action authorization. This plan ends with a local branch; pushing is a separate approved step.

## Review Focus

- Go module downloads may be slow or blocked through the egress proxy; `make build` must complete or fail fast with the exact error recorded — it must not hang indefinitely. (Pinned by Task 2's build step.)
- `factory init` writes `factory.toml` containing placeholder endpoints; a later reader could mistake placeholders for real config. (Pinned by Task 4's placeholder-assertion step.)
- The vendored tree must not carry secrets (`.env`, `factory.toml`, key material, tokens) into the public AEP repo. (Pinned by Task 5's grep gate.)
- Skipping `make frontend` must stay visible: docs must not imply the web UI was built or verified on this VM. (Pinned by Task 6's explicit non-built statement.)
- The pinned SHA must be traceable from the vendored copy alone. (Pinned by Task 5's `PROVENANCE.md` + SHA verification step.)

---

## File Structure

- Create: `~/workspace/repos/esf/` — persistent pinned clone; the install target (outside the AEP repo).
- Create: `~/workspace/repos/esf/bin/` — built binaries (`factory`, `machinist`, `cube-smoke`, `cube-netprobe`, `cube-agent-spike`).
- Create in AEP repo: `reference/esf/**` — vendored tree, everything except `.git` (~8M).
- Create in AEP repo: `reference/esf/PROVENANCE.md` — upstream URL, pinned SHA, snapshot date, license/attribution, exclusions.
- Create in AEP repo: `docs/esf-reference.md` — what ESF is, how it maps to the AEP architecture, what runs here vs what needs infra.
- Modify in AEP repo: `README.md` — one bullet linking `docs/esf-reference.md`.
- Create in AEP repo: `docs/superpowers/plans/2026-10-18-esf-install.md` — this plan.

---

### Task 1: Clone and pin ESF

**Files:**
- Create: `~/workspace/repos/esf/`

**Interfaces:**
- Consumes: nothing (first task)
- Produces: pinned clone at `~/workspace/repos/esf`; HEAD SHA `d41535d86a13e55fe2357d9e0a108566d68ce1b9` for Tasks 2 and 5.

- [ ] **Step 1: Clone at depth 20**

Run: `git clone --depth 20 https://github.com/mitkox/esf.git ~/workspace/repos/esf`
Expected: exit 0; `~/workspace/repos/esf/go.mod` exists.

- [ ] **Step 2: Verify the pinned HEAD**

Run: `git -C ~/workspace/repos/esf rev-parse HEAD`
Expected: `d41535d86a13e55fe2357d9e0a108566d68ce1b9` exactly. If it differs, STOP and report — do not proceed on a different commit.

- [ ] **Step 3: Record spec facts**

Run: `git -C ~/workspace/repos/esf log -1 --format='%H %s' && head -2 ~/workspace/repos/esf/LICENSE && head -3 ~/workspace/repos/esf/go.mod`
Expected: SHA matches Step 2; LICENSE begins `MIT License`; `go.mod` begins `module github.com/mitkox/esf` with `go 1.27.2`.

### Task 2: Build the factory binaries

**Files:**
- Create: `~/workspace/repos/esf/bin/` (build output)

**Interfaces:**
- Consumes: Task 1 clone at `~/workspace/repos/esf`
- Produces: `bin/factory`, `bin/machinist` (+ `bin/cube-smoke`, `bin/cube-netprobe`, `bin/cube-agent-spike`) for Task 4.

- [ ] **Step 1: Build**

Run: `cd ~/workspace/repos/esf && export PATH="$HOME/sdk/go/bin:$HOME/go/bin:$PATH" && GOTOOLCHAIN=local make build`
Expected: exit 0; `bin/factory` and `bin/machinist` exist and are executable. If module downloads fail, record the exact error verbatim and STOP — do not hand-vendor modules.

- [ ] **Step 2: Smoke-test the CLI**

Run: `~/workspace/repos/esf/bin/factory --help | head -20`
Expected: usage text prints; no panic, no stack trace.

### Task 3: Lint and unit tests (no live services)

**Files:** none (verification only)

**Interfaces:**
- Consumes: Task 2 built tree
- Produces: lint + unit-test verdict for the plan record.

- [ ] **Step 1: Lint**

Run: `cd ~/workspace/repos/esf && export PATH="$HOME/sdk/go/bin:$HOME/go/bin:$PATH" && GOTOOLCHAIN=local make lint`
Expected: exit 0.

- [ ] **Step 2: Unit tests only**

Run: `cd ~/workspace/repos/esf && export PATH="$HOME/sdk/go/bin:$HOME/go/bin:$PATH" && GOTOOLCHAIN=local make test-unit`
Expected: exit 0. Do NOT run `make test` (includes frontend), `make test-integration` (needs live CubeSandbox), or `make temporal-up` (needs Docker) — all out of scope per Global Constraints.

### Task 4: Exercise init / validate / doctor in scratch

**Files:**
- Create: `/tmp/esf-scratch/` (disposable; deleted after)

**Interfaces:**
- Consumes: Task 2 `bin/factory`
- Produces: recorded `doctor` output showing the fail-closed posture on this VM.

- [ ] **Step 1: Initialize factory config in scratch**

Run: `mkdir -p /tmp/esf-scratch && cd /tmp/esf-scratch && ~/workspace/repos/esf/bin/factory init`
Expected: `factory.toml` created in `/tmp/esf-scratch`.

- [ ] **Step 2: Assert placeholders only, no secrets**

Run: `cd /tmp/esf-scratch && grep -ciE 'your-|example\.com|placeholder|changeme' factory.toml && ! grep -rEi 'ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}' factory.toml`
Expected: first grep count > 0 (placeholders present); second grep finds nothing (exit 0 from the `!` negation).

- [ ] **Step 3: Validate config and run doctor**

Run: `cd /tmp/esf-scratch && ~/workspace/repos/esf/bin/factory config validate; ~/workspace/repos/esf/bin/factory doctor`
Expected: commands run to completion; output shows unconfigured Cube/Temporal endpoints and the fail-closed posture. Record the output verbatim in the task log. Do NOT set `hardening.acknowledge_open_egress=true` or invent endpoints to force a green board.

- [ ] **Step 4: Clean up scratch**

Run: `rm -rf /tmp/esf-scratch`
Expected: directory gone. No `factory.toml` may remain anywhere except the deleted scratch dir.

### Task 5: Vendor ESF into the AEP repo

**Files:**
- Create: `~/workspace/repos/autonomous-engineering-platform/reference/esf/**`
- Create: `~/workspace/repos/autonomous-engineering-platform/reference/esf/PROVENANCE.md`

**Interfaces:**
- Consumes: Task 1 SHA `d41535d86a13e55fe2357d9e0a108566d68ce1b9`
- Produces: vendored tree + provenance for Tasks 6–7.

- [ ] **Step 1: Copy the tree minus `.git`**

Run: `rsync -a --exclude=.git --exclude=bin ~/workspace/repos/esf/ ~/workspace/repos/autonomous-engineering-platform/reference/esf/`
Expected: `reference/esf/LICENSE`, `reference/esf/go.mod`, `reference/esf/README.md`, `reference/esf/docs/adr/` all exist; `reference/esf/.git` does not exist.

- [ ] **Step 2: Verify the vendored tree matches the pinned SHA**

Run: `git -C ~/workspace/repos/esf rev-parse HEAD && du -sh ~/workspace/repos/autonomous-engineering-platform/reference/esf`
Expected: SHA is `d41535d86a13e55fe2357d9e0a108566d68ce1b9`; size ≈ 8M.

- [ ] **Step 3: Write `reference/esf/PROVENANCE.md`**

Content (exact fields): upstream URL `https://github.com/mitkox/esf`; pinned commit SHA; snapshot date `2026-10-18`; license `MIT (copyright 2026 Owain Lewis; fork by mitkox — see docs/upstream.md)`; excluded: `.git` only; purpose: "reference implementation for the AEP factory lane — studied and built from, not executed from here"; note that `bin/` build output is NOT vendored (built locally in Task 2).
Expected: file exists with all six fields.

- [ ] **Step 4: Secret grep gate**

Run: `cd ~/workspace/repos/autonomous-engineering-platform && grep -rEi 'ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----' reference/esf/ -l`
Expected: empty output. If `testdata/` fixtures trip the grep, verify each hit is a documented fake, list it in `PROVENANCE.md`, and re-run to confirm nothing else matches.

### Task 6: Wire into AEP docs

**Files:**
- Create: `~/workspace/repos/autonomous-engineering-platform/docs/esf-reference.md`
- Modify: `~/workspace/repos/autonomous-engineering-platform/README.md` (one bullet)

**Interfaces:**
- Consumes: Task 5 vendored tree + `PROVENANCE.md`
- Produces: discoverable docs for Task 7.

- [ ] **Step 1: Write `docs/esf-reference.md`**

Sections (keep terse): what ESF is (self-hosted software factory: Task → Temporal → CubeSandbox microVM → coding agent → deterministic verification → patch + evidence); upstream + pinned SHA (link `reference/esf/PROVENANCE.md`); mapping to the AEP README execution loop (factory runs ≈ the ralph-loop lane, verification gates ≈ TDD/review gates, evidence ≈ build ledger); what runs on this VM (build + `make lint` + `make test-unit`, from the Task 1–3 record); what needs infra (Temporal, CubeSandbox deployment, Docker — all absent here); explicit statement that the web UI was NOT built here (Node 24.20.0 vs required 26.12.0); pointer to `reference/esf/docs/adr/` for the 7 ADRs.
Expected: file exists; contains the literal strings `Temporal`, `CubeSandbox`, and `was not built on this VM`.

- [ ] **Step 2: Link from README**

In `README.md`, under the Ecosystem section, add one bullet: `- [ESF reference](docs/esf-reference.md) — vendored snapshot of mitkox/esf (Engineering Software Factory) with build/verification notes.`
Expected: `grep -c 'docs/esf-reference.md' README.md` returns `1`.

- [ ] **Step 3: Link check**

Run: `cd ~/workspace/repos/autonomous-engineering-platform && grep -oE '\(docs/[^)]+\)|\(reference/[^)]+\)' README.md docs/esf-reference.md | sed 's/.*(\(.*\))/\1/' | sort -u | while read f; do test -e "$f" || echo "MISSING: $f"; done`
Expected: no `MISSING` lines.

### Task 7: Commit on a branch (no push)

**Files:** none new (stages Tasks 5–6 output + this plan)

**Interfaces:**
- Consumes: Tasks 5–6 files; this plan at `docs/superpowers/plans/2026-10-18-esf-install.md`
- Produces: local branch `docs/esf-reference` ready for review.

- [ ] **Step 1: Create branch and stage only intended paths**

Run: `cd ~/workspace/repos/autonomous-engineering-platform && git checkout -b docs/esf-reference && git add reference/esf docs/esf-reference.md README.md docs/superpowers/plans/2026-10-18-esf-install.md && git status --short | awk '{print $2}' | cut -d/ -f1 | sort -u`
Expected: output lists only `reference`, `docs`, `README.md`.

- [ ] **Step 2: Commit**

Run: `git commit -m "docs: vendor ESF reference snapshot with provenance and integration plan"`
Expected: exit 0; `git log -1 --format=%s` prints the message above.

- [ ] **Step 3: STOP — report, do not push**

Run: `git log -1 --stat | head -15`
Expected: report the branch name and stat to the user. Do NOT run `git push`. Pushing is a separate explicitly-authorized action.
