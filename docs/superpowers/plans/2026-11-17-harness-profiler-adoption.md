# harness-profiler Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a session profiler AEP can trust: opencode sessions become schema-v2 records that the byte-pinned upstream renderer reads, with correct context nesting and token spend — and with a hard stop before vendoring if the translation cannot be faithful.

**Architecture:** The vendored tree (`reference/harness-profiler/`) is never edited and never reimplemented. AEP writes a **translator**: opencode events → the Claude-shaped payload that the pin's own `buildRecord` consumes, then `serialize` for the line, then `mask` for secrets. Records carry `context_tokens` and `child_spend` because the renderer derives spend from those, or from a transcript when a record names one (`hp.js:318-332`). A shell wrapper exposes `tree`; a Go subcommand is deferred.

**Tech Stack:** Node 18+ CommonJS (`node --test`), opencode v2.3 event API, Bash wrapper, sha256 vendor checks.

**Spec:** `docs/plans/2026-11-17-harness-profiler-evaluation.md`. Pin: `v0.2.2` = `847bd8f6ab2a0348fd7b7057c1943e4c2fa861e8`.

**Execution model:** spec-first (the evaluation is authority; this plan argues from it); eval-driven (every claim maps to an eval); TDD (RED recorded per eval); SDD (implementer + fresh reviewer per task, ledger under `.superpowers/sdd/`).

**Effort (panel estimate):** 5–6 implementer-days, 8–10 with per-task review.

## Adjudication record (six reviewers, 2026-11-17)

Panels: feasibility ×2, code-quality, risk ×2, devil ×2. All six returned proceed-with-changes; two devils rejected the first draft as written. Where they disagreed:

| Dispute | Ruling | Evidence |
|---|---|---|
| Manifest recipe produces `././path` | **Refuted.** Command emits one `./`, matching `vendor-harness2.sha256:1`. Keep it; add `-print0`/`xargs -0` for future trees with spaces. | Ran both variants: `86ad…  ./.claude-plugin/marketplace.json`. |
| `ctx.session.context({sessionID})` vs `{params:{sessionID}}` | **Avoided.** Do not use it; tokens come from events. | Conflict between reviewers; removing the call settles it. |
| `tool.execute` hooks | **Removed.** v2.3 exposes `session.tool.called/success/failed`, `session.step.ended`, `message.part.updated`. Phase 0 observed 1,990 events: `session.created` never fired, so parentage comes from `ctx.session.get().parentID`, not an event. | opencode 2.3.0 spike log + docs. |
| Go CLI before the gate | **Dropped from scope.** Shell wrapper for M4; Go subcommand filed as a follow-up. `aep profile` cannot work in the shipped image (no Node, no `reference/` in `Containerfile:37-57`). | Containerfile read; devil P1. |
| `context_tokens` sufficient for spend columns | **No.** `contextSpend` reads `child_spend`, `SubagentStop.spend`, or transcripts only. | `hp.js:318-332`; three reviewers reproduced empty columns. |
| Manifest proves byte-identity | **No.** It proves tree==manifest, the same bounded claim the skills gate makes at `ci.yml:164-166`. Byte-identity is shown by a second extraction + `diff -r --exclude=PROVENANCE.md`. | Bounded-claim comment; diff excludes the one added file. |
| Masking reimplemented in the adapter | **Rejected.** Reuse the pin's `mask`/`serialize`/`buildRecord` (exported, `hp.js:960`), plus additive, bounded, intent-specific credential rules ahead of it. | 18 exports verified by `require`. |
| Which trace file a child session writes to | **Decided:** every record in a session tree goes to the root session's file; a child in its own file renders as an orphan. | `hp.js:602-628`; independent reviewer P1. |
| Root-context spend | **Emitted explicitly** as a `SubagentStop`-shaped record with `agent_id: "main"` and `spend`; `contextSpend` reads only that or `child_spend`. | `hp.js:318-332`, `hp.js:535-537`. |
| Node 20 for vendored tests | **Node 22**; 18 and 20 are past EOL as of 2026-11. | Node release schedule; local runtime is 26.13.1. |

**Independent reviewer (fresh context): APPROVED-WITH-CHANGES.** All five P1s are folded into the sections above: child-record file placement, byte-identity diff excluding the one added file, root spend emission, plugin-shape eval so M3 cannot go green dead, and E14's concrete RED. It also refuted three claims from the drafting pass (a locale/collation difference that does not reproduce, a `ci.yml` line citation, and `ci.yml`-style bounded-claim wording) — those are corrected rather than carried.

**Phase 0 result (2026-11-17, reviewed): PROCEED-WITH-CONDITIONS.** Observed from 1,990 live events: `at` (envelope `created`), `session` (`data.sessionID`), `tool_use_id` (`data.id`), `duration_ms` (derived `success.created − called.created`), and prompt-side tokens (`session.step.ended.data.tokens`, arithmetic verified `14 + 109312 + 0 = 109326`). Translation is mandatory: native `subagent` yields two roots; mapping to `Agent` plus omitting root `agent_id` is what nests. Conditions carried to Phase C: (a) live parent→child linkage was never observed — the nesting demo used an API-created empty session, so E8 must accept the `ctx.session.get().parentID` path and prove it against a real spawn; (b) the `assistantMessageID` join between `session.step.ended` and a tool call was never exercised; (c) `cache.write` was `0` in all 28 samples, so that term needs a non-zero test case; (d) plain `{id, setup}` is a 2.3.0 loader fact, so the shape test pins to 2.3.x and asserts a callable `setup` with exactly one subscription plus disposer, never `Plugin.define` deep-equality.

## Global Constraints

- The vendored tree is never edited; the only added file is `PROVENANCE.md`, written **before** the manifest is generated so the unlisted-file guard sees it.
- No `npx`, no `npm install`, no telemetry at runtime. Zero adapter dependencies.
- Capture is opt-in and inert by default; disabling leaves no files and no directories.
- Capture never fails a session: every handler path returns.
- Traces never enter git: `.gitignore` entry **and** the common git dir's `info/exclude`, written unconditionally and idempotently; new trace files mode `0600`.
- Records: schema v2, one JSON object per line, ≤ 4096 bytes, fields per `hp.js:335-370`.
- `context_tokens` means prompt-side only: `input + cache.read + cache.write` (`hp.js:238`); never `tokens.total`, never `+ output`.
- Root-context records omit `agent_id`; emitting it makes `contextsOf` create a phantom second root (`hp.js:547-575`).
- Conventional Commit subjects; merge only on green CI with conversation resolution.

## Review Focus

- Translator maps `skill`→`Skill` and `subagent`/`task`→`Agent`; any other spelling renders an empty tree because `visible()` filters on `PARENT_TOOLS` (`hp.js:635-637`).
- Root records carry no `agent_id`, or the tree prints `general-purpose … parent not recorded`.
- Spend columns only appear when `child_spend`/`SubagentStop.spend` exist; `context_tokens` alone renders blanks.
- A secret survives masking: `GITHUB_TOKEN=`, `AWS_SECRET_ACCESS_KEY=`, `NEUROSTRATA_API_KEY=`, `client_secret=`, `--password x` all escape the pin's three patterns (`hp.js:42-46`).
- Trace writes when `.harness-profile/` already exists, or when `.git` is absent — the pin calls exclusion only on first creation (`hp.js:418-431`).
- A worktree capture is invisible to `tree` run from the main checkout (`hp.js:793`), and nothing prunes traces.
- The M2 gate passing because the same agent authored both the fixture and the expected output.

---

## Phase 0 — Translation spike (M0): do not vendor before this passes

### Task 0: Prove opencode can feed the pin

**Files:** create `.superpowers/sdd/2026-11-17-harness-profiler-adoption/spike-translate.js` (scratch, not committed), `spike-notes.md`.

**Interfaces:** consumes the local pin at `/tmp/hprof-pin` (or a temp extraction); produces a decision: PROCEED or PRINCIPLES-ONLY.

- [ ] **Step 1 (RED):** write a scratch script that `require`s the pin's `buildRecord`, feeds one synthesized event-derived payload, and prints the record. Run it against a **real** opencode session's events captured with `for await (… of ctx.event.subscribe({signal}))`. Expect it to fail or produce a record the renderer cannot nest.
- [ ] **Step 2:** confirm by observation, not assumption: which event carries the tool call (`session.tool.called`?), which carries completion (`session.tool.success`/`failed`), which carries per-step tokens (`session.step.ended.data.tokens`), which carries child-parent (`session.created.data.parentID`), whether tool parts expose `state.time`/`state.output`, **which trace file a child session's records must land in for the renderer to see one tree**, and **what plugin export shape the v2.3 server actually accepts** (a throwaway `.opencode/plugins/spike.js` that logs from `setup` settles plain-object vs `Plugin.define`).
- [ ] **Step 3 (decision):** if the five fields needed by the record (`at`, `session`, `tool_use_id`, `duration_ms`, prompt-side tokens) are all obtainable, record PROCEED and write the observed payload shapes into `spike-notes.md`. If any is unavailable, record PRINCIPLES-ONLY and stop the adoption here — no vendoring.
- [ ] **Step 4:** commit nothing; the spike notes go in the ledger.

## Phase A — Evidence freeze (M1)

### Task A1: Vendor the pinned snapshot, CI-green

**Files:** create `reference/harness-profiler/**`; create `reference/harness-profiler/PROVENANCE.md`; create `.github/vendor-harness-profiler.sha256`; modify `.github/workflows/ci.yml` (vendor-integrity step **and** `docs-lint` exclusion, and a `vendor-tests` job); modify `.gitleaks.toml`; create `docs/harness-profiler-reference.md`.

**Interfaces:** produces the tree Phase B imports and the CI gates every later commit rides on.

- [ ] **Step 1 (RED):** `cd reference/harness-profiler && sha256sum -c ../../.github/vendor-harness-profiler.sha256` → fails, no such file.
- [ ] **Step 2:** extract with an explicit pipeline (the API has no strip flag): `gh api repos/afurmanov/harness-profiler/tarball/847bd8f6ab2a0348fd7b7057c1943e4c2fa861e8 | tar xz --strip-components=1 -C reference/harness-profiler`; write `PROVENANCE.md` in the `reference/harness2/PROVENANCE.md` shape, and **do not** claim "no leaks": record the two synthetic fixtures at `test/capture.test.js:155,160` explicitly.
- [ ] **Step 3:** allowlist exactly that file in `.gitleaks.toml` `[allowlist] paths`, with a comment naming both synthetic fixtures (precedent: the ESF/NeuroStrata entries).
- [ ] **Step 4:** add `"!reference/harness-profiler/**/*.md"` to the `docs-lint` linter argument in `ci.yml` — the pin ships 21 `.md` files and `docs/design.md` has 14 MD029 errors.
- [ ] **Step 5:** generate the manifest (after `PROVENANCE.md` exists):

  ```bash
  cd reference/harness-profiler && find . -type f -print0 | xargs -0 shasum -a 256 | sort > ../../.github/vendor-harness-profiler.sha256
  ```

  Plain `sort` matches the CI guard's own `find … | sort`; the set comparison is collation-consistent either way on this corpus (measured: locale and `LC_ALL=C` orders are identical here, 0 differing lines).

  Verify locally with the CI triple before committing: `sha256sum -c`, the `comm -23` unlisted guard, the broken-symlink loop.
- [ ] **Step 6:** add a `vendor-tests` job (`actions/setup-node` Node 22 — Node 18 and 20 are past end-of-life as of 2026-11; upstream's floor stays `engines >=18`), `node --test reference/harness-profiler/test/*.test.js` (the explicit glob; Node 22 treats a positional `--test` argument as a glob pattern and fails on the bare directory), timeout 5 min. No `npm install`; the suite runs 51/51 without playwright.
- [ ] **Step 7 (GREEN):** manifest check clean; upstream suite green from the tree; `gitleaks detect --source . --no-git` clean; `markdownlint-cli2` over the repo clean; and byte-identity shown by extracting the tarball a second time into a temp dir and `diff -r --exclude=PROVENANCE.md` — the excluded file is the one addition, and the step asserts exactly that.
- [ ] **Step 8:** write `docs/harness-profiler-reference.md` (pin, purpose, what AEP uses vs ignores, link to the operator doc).
- [ ] **Step 9:** commit `chore(vendor): add harness-profiler v0.2.2 snapshot`.

## Phase B — Translator and gate (M2)

### Task B1: Translator onto the pin's own record builder

**Files:** create `tools/harness-profile/translate.js`, `translate.test.js`, `testdata/events/*.json`.

**Interfaces:** `toPayload(event, state) → hpPayload`; `buildRecord(event, state) → record` (delegates to the pin's `buildRecord`, then sets `context_tokens`, and for spawning calls `child_spend`); `writeRecord(traceDir, record, rootSessionId)` (delegates to the pin's `serialize`). All exported for tests.

**Record placement (decided here, because the renderer assumes it):** every record in a session tree — parent and every child — is appended to the **root session's** `<rootSessionId>.jsonl`. Child records carry `agent_id = <child session id>`; the spawning parent call carries `child_agent_id = <child session id>` and `child_spend`. A child written to its own file renders as an orphan (`hp.js:602-628`).

Evals: **E1** field contract, **E2** name mapping, **E3** root `agent_id` omission, **E4** token formula, **E4b** root-context spend.

- [ ] **Step 1 (RED):** tests assert, against fixture events: `v:2`, `harness:"opencode"`, `at`, `session`, `tool_use_id`, `duration_ms`; `skill`→`Tool:"Skill"` and `subagent`→`"Agent"`; root record has no `agent_id`; `context_tokens === input + cache.read + cache.write`; `serialize` ≤ 4096 bytes. Run `node --test tools/harness-profile/translate.test.js` → fails (module absent).
- [ ] **Step 2:** implement by delegation: build the Claude-shaped payload (`hook_event_name`, `tool_name`, `tool_input`, `tool_response`, `tool_use_id`, `session_id`, `duration_ms`, `cwd`), call the pin's `buildRecord`, then attach `context_tokens` and `child_spend = {new: input + cache.write, cached: cache.read, out: output, calls}`. At session end, also emit one `SubagentStop`-shaped record with `agent_id: "main"` and `spend: {new, cached, out, calls}` for the root context — `contextSpend` reads `SubagentStop.spend` keyed by `agent_id` (`hp.js:318-332`), and the root id is literally `main` (`hp.js:535-537`).
- [ ] **Step 3 (GREEN):** all pass.
- [ ] **Step 4:** commit `feat(profile): translate opencode events into harness-profile records`.

### Task B2: The M2 gate — renderer judges translator output

**Files:** create `tools/harness-profile/gate.test.js`, `testdata/nested-session.json`.

Eval **E5**: nested contexts, no placeholder, inline marker, non-zero spend — asserted through the pin's `contextsOf`/`renderTree`/`renderHtml` **on records read back from the trace file the translator wrote**, never on the translator's in-memory objects alone.

- [ ] **Step 1 (RED):** the test runs the translator over a recorded event fixture into a temp trace dir (via `writeRecord`, so file placement and serialization are exercised), then calls the pin's `contextsOf(records)` and `renderTree` over the parsed file, and asserts: exactly two contexts; the child's parent is `main`; output contains no `parent not recorded`; an inline `Skill` marker exists; child spend is non-zero; root spend is non-zero. Run → fails until B1 is complete.
- [ ] **Step 2:** fix the translator, never the fixture, until the gate passes. Any change to expected output requires a recorded reason in the ledger.
- [ ] **Step 3 (GREEN + M2):** pass; paste the tree output into the ledger.
- [ ] **Step 4:** commit `test(profile): gate translator output through the vendored renderer`.

**Stop rule:** if Step 3 cannot pass because the pin requires something the translator cannot synthesize, stop. Write the principles-only decision into the evaluation, file the fallback as its own plan, and do not start Phase C.

## Phase C — Live capture and hygiene (M3)

### Task C1: Opt-in opencode plugin

**Files:** create `tools/harness-profile/handle.js` (CommonJS, the tested logic), `.opencode/plugins/harness-profile.js` (thin ESM default export, no logic), `tools/harness-profile/handle.test.js`.

Evals: **E6** inertness, **E7** duration pairing, **E8** parent linkage on live capture (spawn response, else the `ctx.session.get().parentID` path — `session.created` never fires, per Phase 0), **E9** trace-dir override, **E9b** plugin shape.

- [ ] **Step 1 (RED):** with `AEP_HARNESS_PROFILE` unset, `handleEvent` returns `null` and writes nothing; with it set, a recorded sequence yields one record per call, paired durations, and `child_agent_id` on the spawning call. Two Phase-0 conditions are asserted here: the `assistantMessageID` join that attributes `session.step.ended` tokens to a specific call (fixture with a non-zero `cache.write`), and parentage resolved through `ctx.session.get().parentID` when no spawn response carries it. Separately, a shape test dynamically imports `.opencode/plugins/harness-profile.js` and asserts what v2.3 accepts: an object default export with a non-empty string `id` and a callable `setup` (or `effect`) that registers exactly one subscription and returns a disposer — never `Plugin.define` deep-equality. This is what stops M3 from going green while the plugin is dead. Run → fails.
- [ ] **Condition carried from B1:** `testdata/events/subagent.json` is synthetic and its spawn input `{agent, description, prompt}` is unverified; C1's live smoke must dispatch one **real** subagent and assert `child_agent_id` and a non-empty `name` on that real spawning call, not just on the fixture.
- [ ] **Step 2:** implement `handle.js` over the translator; the ESM plugin only subscribes and calls it. Resolve the trace dir from `AEP_HARNESS_PROFILE_DIR`, else the git root; write exclusion unconditionally; `chmod 0600`; keep the ledger out of `git status` — `.superpowers/` is already ignored (`.gitignore:3-4`, added in `143cd38`), so this step verifies the entry rather than adding one.
- [ ] **Step 3 (GREEN):** suites pass; one live session (non-gating smoke) renders through the wrapper.
- [ ] **Step 4:** commit `feat(profile): capture opencode sessions when opted in`.

### Task C2: Hygiene evals

**Files:** create `tools/harness-profile/hygiene.test.js`; modify `.gitignore`.

Evals: **E10** pre-existing trace dir still excluded; **E11** no-`.git` directory gets no exclusion and is documented; **E12** two concurrent writers produce well-formed lines; **E13** retention: prune older than N days, documented size budget.

- [ ] **Step 1 (RED):** each case fails against the naive implementation (reproduced failures: exclude skipped when the dir exists, `0644` files).
- [ ] **Step 2:** fix; document retention in the operator doc.
- [ ] **Step 3 (GREEN):** all pass; `git check-ignore -v .harness-profile/x` names `info/exclude` (not merely `.gitignore`).
- [ ] **Step 4:** commit `fix(profile): make trace exclusion idempotent and bound growth`.

## Phase D — Operator surface (M4)

### Task D1: Shell wrapper and docs

**Files:** create `scripts/profile-tree.sh`; create `docs/harness-profiler.md`; modify `docs/harness-profiler-reference.md`.

Eval **E14**: wrapper resolves the repo root by walking up for `reference/harness-profiler/plugin/libexec/hp.js` when run from `scripts/`; **E14b**: with `PATH` lacking `node`, it prints an actionable message (`node 18+ required for profiling; install Node or skip`) and exits non-zero; **E14c**: `--help` documents both.

- [ ] **Step 1 (RED):** run `bash scripts/profile-tree.sh tree` from `scripts/` with `PATH` stripped of `node` → the current failure is a raw `sh: node: not found` with no guidance. That is the RED.
- [ ] **Step 2:** implement root discovery, the Node check, `--help`, and the message; document enable/disable (including the service-restart requirement, since a shell-exported env var does not reach a running `opencode serve`), trace location, retention, masking caveat, and dev-host scope.
- [ ] **Step 3 (GREEN):** wrapper works from a subdirectory; markdownlint clean; `shellcheck`/`shfmt` clean.
- [ ] **Step 4:** commit `feat(profile): add profile-tree wrapper and operator docs`.

## Phase E — Promotion (M5)

- [ ] **E-1:** run every eval on one head; record commands and outputs.
- [ ] **E-2:** decision pack: evals, live-smoke output, risks carried (masking gaps, trace growth, dev-host scope), non-goals.
- [ ] **E-3:** owner rules adopt / dormant / principles-only. No production wiring before the ruling.

## Non-goals (explicit)

- Cost per verified task, and any join to `runs.jsonl` — this plan delivers a capture/render substrate, not the metric.
- Codex adapter. Upstream documents no skill call and no tool failures there.
- A Go `aep profile` subcommand — deferred follow-up; it cannot work in the shipped image.
- Upstream PRs (`capture opencode`). Filings are the owner's call.
- `.claude/` hooks, plugin marketplace install, `npx` execution.

## Test Plan

| Eval | Command | Pass condition |
|---|---|---|
| E1–E4b | `node --test tools/harness-profile/translate.test.js` | fields, name mapping, root omission, token formula, root spend |
| E5 | `node --test tools/harness-profile/gate.test.js` | records read back from disk: two contexts, correct parent, no placeholder, inline marker, child+root spend |
| E6–E9b | `node --test tools/harness-profile/handle.test.js` | inertness, durations, linkage, dir override, plugin shape |
| E10–E13 | `node --test tools/harness-profile/hygiene.test.js` | exclusion idempotent, concurrent writes, retention |
| E14–E14c | `bash scripts/profile-tree.sh` from `scripts/`; `PATH` without node | root resolved, actionable error, help |
| Upstream | `node --test reference/harness-profiler/test/*.test.js` (CI `vendor-tests`, Node 22) | 51/51 |
| Integrity | `sha256sum -c .github/vendor-harness-profiler.sha256` + unlisted + symlink | all clean |
| Secrets | `gitleaks detect --source . --no-git` | clean, with the one allowlisted fixture file |

## Acceptance Criteria

- [ ] M0: the five fields are observed from real opencode events; PROCEED recorded before any vendoring, or the adoption ends as principles-only.
- [ ] M1: manifest, unlisted-file guard and symlink check green; `docs-lint` and `security` green; upstream suite green in a CI job; byte-identity proven by second-extraction `diff -r`.
- [ ] M2: E1–E5 green with recorded RED; the pin's `contextsOf`/`renderTree` prove nesting and spend **on records read back from the written trace file**; no `parent not recorded` output; root and child spend both non-zero.
- [ ] M3: E6–E13 green; capture inert by default; the plugin's export shape is verified against the v2.3 server; exclusion idempotent and verified via `git check-ignore -v`; growth bounded; `git status` clean with the ledger present.
- [ ] M4: E14 green; docs state dev-host scope, the service-restart requirement, and the masking gaps.
- [ ] M5: owner ruling recorded before production wiring.
- [ ] Every task SDD-executed: implementer + fresh reviewer, ledger entries, no completion on self-review alone.

## Follow-ups (filed, not executed here)

- Go `aep profile` subcommand, scoped to source checkouts, with `--root` walking up.
- Codex translator, after an upstream release exposes skill calls.
- `capture opencode` upstream contribution.
- Cost-per-verified-task join, once `runs.jsonl` exists.
