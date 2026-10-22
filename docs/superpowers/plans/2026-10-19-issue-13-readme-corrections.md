# README Component Inventory Corrections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the README describe the environment that actually exists — correct paths, versions, and counts; non-existent components explicitly marked "Planned — not installed" instead of "Installed; verified".

**Architecture:** Surgical rewrite of the README's claims sections (component inventory table, two mermaid diagrams, skill counts, limitations bullets) against a verified ground-truth table built in Task 1. Docs-only; no code, script, or CI changes. Fictional components keep their rows but get honest status labels; the design intent is preserved, the false "verified" claims are removed.

**Tech Stack:** Markdown, Mermaid diagrams. CI gate: markdownlint (v1 baseline in `.markdownlint.yaml` stays in effect).

**Spec:** https://github.com/pratik-saptarshi/autonomous-engineering-platform/issues/13

## Global Constraints

- Docs-only change: README.md only. No code, scripts, or CI config modifications.
- Conventional Commits: e.g. `docs(readme): correct component inventory against verified state`.
- Commit as Musebot-Astro <6238157+pratik-saptarshi@users.noreply.github.com>.
- Exact-path `git add README.md` only — never `git add -A` (repo has no .gitignore; `.superpowers/` is untracked).
- Public repo: no credentials, tokens, or generated real config values.
- markdownlint must pass after the edit (run `npx --yes markdownlint-cli2 README.md` if available, else rely on CI).
- Every factual claim (path, version, count, cron name) must be re-verified against the live environment at implementation time — use the verification commands in Task 1, not the values quoted here, in case the environment changed.

## Review Focus

The five reader-facing failure modes most likely to bite, most likely first — each gets its pinning test in the owning task:

1. A `Location` path in the inventory doesn't exist → the reader concludes the environment is broken. *Test: every path in the table must pass `test -e` (Task 2, Step 4).*
2. A version string doesn't match the installed binary → the reader fetches the wrong artifact. *Test: every version must match `<binary> --version` output (Task 2, Step 4).*
3. A named cron job doesn't exist in the scheduler → the reader waits for runs that never happen. *Test: every named job must appear in the scheduler job list (Task 2, Step 4).*
4. A component marked "Installed" was never installed → the reader tries to use fiction. *Test: no row may carry "Installed"/"verified" unless its verification command passes (Task 2, Step 5).*
5. A mermaid diagram has broken syntax after editing → the docs render as raw text. *Test: visual render check of both diagrams after edit (Tasks 3-4, final steps).*

---

### Task 1: Build the verified ground-truth table

**Files:**
- Modify: none (research task; the table below is the deliverable, confirmed live)

**Interfaces:**
- Consumes: live environment (filesystem, binaries, scheduler)
- Produces: ground-truth table consumed by Tasks 2–6. Every later task copies values from this table verbatim — it does not re-derive them.

- [ ] **Step 1: Run the verification commands and record actual results**

Run each command; record the real output. Do not copy the values quoted below without re-running — the environment may have changed since 2026-10-19.

```bash
# Component existence
for d in ~/workspace/ralph ~/workspace/open-connector ~/workspace/bin ~/workspace/custom-connectors/custom.neurostrata; do [ -d "$d" ] && echo "EXISTS: $d" || echo "absent: $d"; done
ls ~/go/bin/                       # expect: bd gh neuroplasticity neurostrata-mcp ocr shfmt
~/go/bin/bd --version              # expect: bd version 1.3.1 (dev)
~/go/bin/ocr --version             # expect: open-code-review v1.13.1
~/go/bin/neurostrata-mcp --version # expect: neurostrata-mcp 1.9.0
~/sdk/go/bin/go version            # expect: go version go1.27.2 linux/amd64
ls -d ~/workspace/worktrees/aep-ci-pr/skills/*/ | wc -l   # expect: 30
ls ~/workspace/custom-skills/ | wc -l                     # expect: ~62 (record exact)
du -sh ~/.cache/neuro/models/fastembed 2>/dev/null        # model cache size
ls ~/.config/NeuroStrata/data/db/ladybug.db               # memory store exists
```

- [ ] **Step 2: Confirm the scheduler job list**

Check which of `ralph-loop`, `neurostrata-watchdog`, `neurostrata-tls-validation`, `neurostrata-export` actually exist as scheduled jobs. Record which are present.

- [ ] **Step 3: Write the ground-truth table**

Produce a table with columns: Component | Version (from `--version`) | Location (verified path) | Status (Installed / Not installed — planned). This table is the single source of truth for Tasks 2–6. Reference values observed 2026-10-19: ralph loop absent; open-connector absent; custom.neurostrata client absent; `~/workspace/bin` absent; binaries in `~/go/bin/`; repo `skills/` = 30 dirs; `~/workspace/custom-skills/` = 62 entries; `neurostrata-watchdog` + `neurostrata-export` exist; `ralph-loop` + `neurostrata-tls-validation` do not.

---

### Task 2: Rewrite the component inventory table (README.md:65-78)

**Files:**
- Modify: `README.md:65-78` (the `## Component inventory` table)

**Interfaces:**
- Consumes: ground-truth table from Task 1 (copy values verbatim)
- Produces: corrected inventory table

- [ ] **Step 1: Rewrite each row from the ground-truth table**

Replace the table body. Decisions (do not relitigate): keep one row per component including the non-existent ones, but set their Status to `Planned — not installed` (never `Installed`/`verified`). Correct rows:
  - Skill library → location stays `~/workspace/custom-skills/`, version becomes the Task-1 count, status `Installed`
  - Ralph loop → status `Planned — not installed` (no `~/workspace/ralph/`, no cron)
  - NeuroStrata engine → location `~/workspace/neurostrata/` (data/log dir), binary note `~/go/bin/neurostrata-mcp`, v1.9.0, status `Installed`
  - NeuroStrata MCP connector → status `Planned — not installed` (no stdio client; note the OpenCode MCP wiring exists at `~/.config/opencode/opencode.json` if Task 1 confirms it)
  - Embedding model cache / Memory store → keep, verify paths from Task 1
  - beads → location `~/go/bin/bd`, version `1.3.1 (dev)`, status `Installed`
  - open-code-review → location `~/go/bin/ocr`, version `1.13.1`, status `Installed`
  - open-connector → status `Planned — not installed`
  - Scheduler → list only jobs confirmed in Task 1 Step 2 (expect `neurostrata-watchdog` 2h, `neurostrata-export` weekly; drop `ralph-loop` and `neurostrata-tls-validation`)

  - [ ] **Step 2: Fix the table's Status vocabulary**

The only allowed Status values after this task: `Installed`, `Installed; verified` (only where a verification command in the runbook passes), or `Planned — not installed`. No other wording.

- [ ] **Step 3: Verify every path, version, and cron name (Review Focus 1–4)**

```bash
# Every Location path in the table must exist:
grep -oP '(?<=`)[~/][^`]+(?=`)' README.md | while read -r p; do eval test -e "$p" && echo "OK: $p" || echo "MISSING: $p"; done
# Every version must match --version output; every cron name must be in the scheduler list from Task 1.
# No row may say Installed/verified unless verified. Fail the task if any check fails.
```
Expected: all paths OK, all versions match, no unverified "Installed".

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): correct component inventory against verified state"
```

---

### Task 3: Fix the Ecosystem mermaid diagram (README.md:5-43)

**Files:**
- Modify: `README.md:5-43` (the `## Ecosystem` mermaid `graph TB` block)

**Interfaces:**
- Consumes: ground-truth table from Task 1
- Produces: diagram showing only real components

- [ ] **Step 1: Redraw the diagram without fictional nodes**

Decisions (do not relitigate): delete the entire `Control` subgraph (`CRON` ralph-loop node) and the entire `Loop` subgraph (`BL`, `RL`, `PY` nodes) — the ralph loop does not exist. Delete the `OC` open-connector node. Fix the Tools nodes: `BD["beads 1.3.1<br/>~/go/bin/bd"]`, `OCR["open-code-review 1.13.1<br/>~/go/bin/ocr"]`. Keep Skills (update count from Task 1), Memory (`NS`, `DB`) subgraphs with real values. Remove all edges touching deleted nodes.

- [ ] **Step 2: Add a one-line planned-component note below the diagram**

Text (verbatim): `> The execution loop (ralph) and open-connector gateway are planned but not yet installed — see the component inventory.`

- [ ] **Step 3: Verify the diagram renders (Review Focus 5)**

Visually confirm the mermaid block parses (no dangling node references — every node referenced in an edge must be defined). Check: `grep -oP '^\s+\w+(?=\[)' README.md` node definitions cover all edge endpoints.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): redraw ecosystem diagram without fictional components"
```

---

### Task 4: Fix the "Continuous loop cycle" section (README.md:45-63)

**Files:**
- Modify: `README.md:45-63` (`## Continuous loop cycle` + mermaid `flowchart LR`)

**Interfaces:**
- Consumes: Task 1 (confirms no loop exists)
- Produces: honestly-labeled planned section

- [ ] **Step 1: Retitle and disclaim the section**

Decision (do not relitigate): keep the flowchart as design reference but retitle the heading to `## Planned: continuous loop cycle` and prepend this disclaimer verbatim:
```
> **Not yet implemented.** This is the design for the autonomous execution loop. No scheduler job currently runs this cycle; `backlog.py` and the `ralph-loop` cron do not exist.
```

- [ ] **Step 2: Verify the disclaimer is present and the diagram is untouched**

```bash
grep -n "Planned: continuous loop cycle" README.md && grep -n "Not yet implemented" README.md
```
Expected: both lines found.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): mark continuous loop cycle as planned, not implemented"
```

---

### Task 5: Correct skill counts and the Skill sources table (README.md:17, 80-97)

**Files:**
- Modify: `README.md:17` (Ecosystem diagram `Skill library · 58 skills` node), `README.md:80-97` (`### Skill sources` table)

**Interfaces:**
- Consumes: Task 1 skill counts (repo `skills/` dirs, `~/workspace/custom-skills/` entries)
- Produces: consistent counts everywhere

- [ ] **Step 1: Update the counts**

Set the Ecosystem `Skills` subgraph label and the inventory-adjacent claims to the Task-1 verified count of `~/workspace/custom-skills/` (observed 62 on 2026-10-19 — re-verify, do not copy blindly). In the `### Skill sources` section, add one clarifying line verbatim:
```
The repo's `skills/` directory carries a 30-skill curated subset; the full library lives at `~/workspace/custom-skills/`.
```
Verify the 30-dir count: `ls -d skills/*/ | wc -l`.

- [ ] **Step 2: Check count consistency across the file**

```bash
grep -n "58 skills\|58-skill" README.md; grep -n "12 upstream" README.md
```
Expected: no stale `58` or `12 upstream` claims remain (update or remove each hit).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): correct skill counts (62 local, 30 vendored)"
```

---

### Task 6: Fix Known limitations bullets for non-existent components (README.md:113-123)

**Files:**
- Modify: `README.md:113-123` (`## Known limitations`)

**Interfaces:**
- Consumes: Task 1 (confirms open-connector absent)
- Produces: limitations that describe real components

- [ ] **Step 1: Fix the open-connector bullet**

The bullet beginning "The open-connector gateway does not survive VM restarts" describes a component that isn't installed. Decision: replace it with a single honest line verbatim: `- open-connector is not installed; the gateway persistence limitation does not currently apply.`

- [ ] **Step 2: Do NOT touch the daemon auto-restart wording**

The bullets mentioning MCP auto-spawn contradict `docs/limitation-analysis.md` — that is issue #16's scope, not this task's. Leave them byte-identical here so #16's diff stays clean. (If #16 is already fixed when you implement this, skip this step's caution and just don't reintroduce the contradiction.)

- [ ] **Step 3: Verify no other bullet names a non-existent component**

```bash
grep -n "ralph\|open-connector\|custom.neurostrata\|workspace/bin" README.md | grep -vi "planned\|not installed\|not yet"
```
Expected: no hits outside the Task-2 table and the Task-3/4 disclaimers.

- [ ] **Step 4: Final markdownlint check and commit**

```bash
npx --yes markdownlint-cli2 README.md 2>/dev/null || echo "markdownlint not available locally; CI will check"
git add README.md
git commit -m "docs(readme): fix limitations bullets for non-existent components"
```

---

## Self-review notes (factchk validation applied 2026-10-19)

- Line numbers cited (README.md:5-43, 45-63, 65-78, 80-97, 113-123) verified via `grep -n` on the worktree file @ e73cafe.
- Ground-truth values verified live 2026-10-19: `~/workspace/ralph`, `~/workspace/open-connector`, `~/workspace/bin`, `~/workspace/custom-connectors/custom.neurostrata` all absent; `~/go/bin/` holds bd, gh, neuroplasticity, neurostrata-mcp, ocr, shfmt; `bd --version` → `1.3.1 (dev)`; `ocr --version` → `open-code-review v1.13.1`; `neurostrata-mcp --version` → `1.9.0`; `go version` → `go1.27.2`; repo `skills/` = 30 dirs; `~/workspace/custom-skills/` = 62 entries; `~/workspace/neurostrata/bin/` holds only `watchdog-backup.sh`.
- Scheduler state (no `ralph-loop`, no `neurostrata-tls-validation`; `neurostrata-watchdog` + `neurostrata-export` exist) verified via scheduler job list on 2026-10-18 — Task 1 Step 2 re-verifies at implementation time.
- Scope boundary with issue #16 (daemon auto-restart contradiction) is explicit in Task 6 Step 2 to avoid diff conflicts.
- The `test -e` grep in Task 2 Step 3 will also match `~/.cache` and `~/.config` paths — those exist; fine.
