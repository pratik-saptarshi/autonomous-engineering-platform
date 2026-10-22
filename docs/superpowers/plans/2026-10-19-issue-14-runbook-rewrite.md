# Runbook Rebuild-Correctness Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `docs/runbook.md`'s "exact steps to rebuild this platform on a fresh persistent Linux VM" actually work — correct binary paths and install commands, the load-bearing Go toolchain documented, aspirational subsystems moved to a marked appendix, and a verification checklist containing only checkable items.

**Architecture:** Section-by-section rewrite against verified install records (TOOLS.md, `~/memory/2026-10-16.md`, live environment). The main numbered sections (§§1–5, §8) become fully executable on a fresh VM; §§6–7 move to a new "Appendix A: Planned components" with their design content preserved but clearly marked not-yet-implemented. Docs-only; no code, script, or CI changes.

**Tech Stack:** Markdown (bash code blocks). CI gate: markdownlint (v1 baseline in `.markdownlint.yaml` stays in effect).

**Spec:** https://github.com/pratik-saptarshi/autonomous-engineering-platform/issues/14

## Global Constraints

- Docs-only change: `docs/runbook.md` only. No code, scripts, or CI config modifications.
- Conventional Commits: e.g. `docs(runbook): rewrite binary installs against verified state`.
- Commit as Musebot-Astro <6238157+pratik-saptarshi@users.noreply.github.com>.
- Exact-path `git add docs/runbook.md` only — never `git add -A` (repo has no .gitignore; `.superpowers/` is untracked).
- Public repo: no credentials, tokens, or generated real config values.
- markdownlint must pass after the edit.
- Install commands must be copied from the verified records cited in each task (TOOLS.md, `~/memory/2026-10-16.md`), not invented. Where the exact upstream URL is not on record, document the verified outcome (binary name, version, install path, checksum practice) rather than a guessed URL.
- The checksum-verified-install standard applies to every download documented: each install block must include a SHA256 verification step.

## Review Focus

The five rebuild-breaking failure modes most likely to bite, most likely first — each gets its pinning test in the owning task:

1. An install command targets a path that won't exist → every `mkdir`/`install`/`ln` target's parent must be created in the same block, and the final binary path must match the Location the README inventory claims. *Test: path-consistency grep across README + runbook (Task 1, Step 5).*
2. A prerequisite is missing → the build fails three sections later with an inscrutable error. *Test: the prerequisites line must name every toolchain a later section's commands require (Task 2, Step 3).*
3. A version pin doesn't match what's deployed → the reproducer gets a different artifact. *Test: every version string must match `<binary> --version` on the live box (Task 1, Step 5).*
4. A "planned" section leaks into the executable flow → the reproducer follows it and fails. *Test: after the move, no `## N.` numbered section may reference a path that doesn't exist (Task 3, Step 4).*
5. A checklist item has no pass/fail command → it can never be checked off honestly. *Test: every checklist item must name an exact command and expected output (Task 5, Step 3).*

---

### Task 1: Rewrite §1 Binary tools and fix §3 daemon binary paths

**Files:**
- Modify: `docs/runbook.md:5-44` (§1, three install blocks + PATH setup)
- Modify: `docs/runbook.md:65-78` (§3, two `~/workspace/neurostrata/bin/neurostrata-mcp` occurrences)

**Interfaces:**
- Consumes: verified install records (TOOLS.md for bd/Go; `~/memory/2026-10-16.md` for neurostrata-mcp and ocr)
- Produces: corrected §1 and §3 that install to real paths

- [ ] **Step 1: Replace the PATH setup block (docs/runbook.md:7-10)**

Replace `mkdir -p ~/workspace/bin` + `~/workspace/bin` PATH export with the real convention (verbatim):
```bash
# Binaries live in ~/go/bin (created if missing); Go toolchain at ~/sdk/go.
mkdir -p ~/go/bin
echo 'export PATH="$HOME/sdk/go/bin:$HOME/go/bin:$PATH"' >> ~/.bashrc
export PATH="$HOME/sdk/go/bin:$HOME/go/bin:$PATH"
```
Rationale for the implementer: `~/go/bin` is where every binary actually lives (verified 2026-10-19: bd, gh, neuroplasticity, neurostrata-mcp, ocr, shfmt); the `export` line makes it effective in the current shell, not just future ones.

- [ ] **Step 2: Rewrite the beads install block**

Delete the `gastownhall/beads` tarball block. Replace with the verified method from TOOLS.md (verbatim, including the CGO note):
```bash
# bd is built from source (github.com/steveyegge/beads); the README's
# CGO_ENABLED=0 recipe produces a broken embedded DB — use the default CGO build.
# Requires Go (see Prerequisites) and gcc.
go install github.com/steveyegge/beads/cmd/bd@latest
bd --version   # bd version 1.3.1 (dev) — the (dev) suffix is expected: source build
```
Keep the existing Verify line (`bd ping`, `bd init` lifecycle) — it is correct.

- [ ] **Step 3: Rewrite the open-code-review install block**

Delete the npm-fetch + symlink block (`@alibaba-group/ocr-linux-x64`, `~/workspace/open-code-review/`, `ln -s ... ~/workspace/bin/ocr`) — none of those paths were ever used. Replace with the verified install (verbatim):
```bash
# ocr v1.13.1 (Apache-2.0): linux-amd64 binary from the alibaba/open-code-review
# GitHub release. Verify SHA256 against the release's sha256sum.txt, then
# install to ~/go/bin/ocr (a real binary, not a symlink).
# (Skip if ~/go/bin/ocr --version already reports v1.13.1 — installed 2026-10-16.)
cd /tmp
gh release download v1.13.1 --repo alibaba/open-code-review \
  --pattern 'opencodereview-linux-amd64' --pattern 'sha256sum.txt'
sha256sum -c sha256sum.txt --ignore-missing  # must report OK for opencodereview-linux-amd64
install -m 755 opencodereview-linux-amd64 ~/go/bin/ocr
~/go/bin/ocr --version  # open-code-review v1.13.1 linux/amd64
```
Keep the existing Verify lines (`ocr delegate preview/rule`) — they are correct.

- [ ] **Step 4: Rewrite the NeuroStrata engine block and fix §3 paths**

In §1, replace `mkdir -p ~/workspace/neurostrata/bin` + extract-to-there with (verbatim):
```bash
cd /tmp
# neurostrata-mcp-linux-amd64.tar.gz from the v1.9.0 release
# (https://github.com/Cognilogical/NeuroStrata); verify SHA256 against the
# release's SHA256SUMS, then:
tar xzf neurostrata-mcp-linux-amd64.tar.gz neurostrata-mcp
install -m 755 neurostrata-mcp ~/go/bin/neurostrata-mcp
~/go/bin/neurostrata-mcp --version  # neurostrata-mcp 1.9.0
```
In §3 (`docs/runbook.md:65-78`), replace both `~/workspace/neurostrata/bin/neurostrata-mcp` occurrences with `~/go/bin/neurostrata-mcp`, and add `HF_HUB_OFFLINE=1` to the daemon start line (required: the binary cannot download through the TLS-intercepting proxy — see limitation-analysis.md §2):
```bash
HF_HUB_OFFLINE=1 nohup ~/go/bin/neurostrata-mcp daemon > ~/workspace/neurostrata/daemon.log 2>&1 &
sleep 15
~/go/bin/neurostrata-mcp status
# expect: "status: healthy -- one daemon is serving every console"
```

- [ ] **Step 5: Verify paths, versions, and README consistency (Review Focus 1, 3)**

```bash
# No stale paths remain:
grep -n "workspace/bin" docs/runbook.md; echo "---"; grep -n "gastownhall/beads\|@alibaba-group/ocr-linux-x64\|workspace/open-code-review" docs/runbook.md
# Expected: no hits (the neurostrata/bin watchdog path is untouched — that's a different dir usage).
# README inventory Locations must match the paths documented here:
grep -n "go/bin" README.md | head -5   # informational; full alignment is issue #13's job, but do not contradict it
```
Expected: zero stale-path hits.

- [ ] **Step 6: Commit**

```bash
git add docs/runbook.md
git commit -m "docs(runbook): rewrite binary installs against verified state"
```

---

### Task 2: Add the Go toolchain to prerequisites

**Files:**
- Modify: `docs/runbook.md:3` (the Prerequisites line)

**Interfaces:**
- Consumes: TOOLS.md (Go install record)
- Produces: prerequisites line covering every toolchain §§1–5 need

- [ ] **Step 1: Extend the prerequisites line**

Replace `Prerequisites: \`python3\`, \`node\` 20+, \`git\`, \`curl\`, network egress.` with (verbatim):
`Prerequisites: \`python3\`, \`node\` 20+, \`git\`, \`curl\`, Go 1.27.2 (\`~/sdk/go\`, on PATH), \`gcc\` (for the CGO \`bd\` build), network egress.`
Then append this note verbatim after the line:
`Go install: download the go1.27.2 linux-amd64 tarball, extract to \`~/sdk/go\`, and export \`PATH="$HOME/sdk/go/bin:$PATH"\` (already covered by the §1 PATH block). \`/tmp\` is a 512M tmpfs on this VM — set \`GOTMPDIR=$HOME/.gotmp\` (mkdir it first) before big \`go install\`/build steps or the linker can fail with "no space left on device".`

- [ ] **Step 2: Verify every later section's toolchain is named (Review Focus 2)**

```bash
grep -n "go install\|go build\|go vet\|gcc" docs/runbook.md
```
Expected: the `go install` (bd) and any `go` usage are covered by the prerequisites line. `python3` (backlog.py was removed — see Task 3), `node` (§7 moved — see Task 3), `curl` (§2) are covered.

- [ ] **Step 3: Commit**

```bash
git add docs/runbook.md
git commit -m "docs(runbook): document Go toolchain prerequisite"
```

---

### Task 3: Move §§6–7 to a "Planned components" appendix

**Files:**
- Modify: `docs/runbook.md:109-125` (§§6–7), `docs/runbook.md:127-137` (§8, checklist items — see Task 5)

**Interfaces:**
- Consumes: Task 1 (confirms ralph/open-connector absent)
- Produces: appendix section; main flow §§1–5 all executable

- [ ] **Step 1: Cut §§6–7 into a new appendix**

Delete `## 6. Ralph loop and scheduler` (lines 109-117) and `## 7. open-connector gateway (optional)` (lines 119-125) from the numbered flow. Append at the end of the file a new section (verbatim heading):
```markdown
## Appendix A: Planned components (not yet implemented)

The following were designed but are not installed. They are preserved here as
design reference — do not follow these steps expecting them to work.
```
Then paste the §6 and §7 content verbatim under it, each demoted one heading level (`### A.1 Ralph loop and scheduler`, `### A.2 open-connector gateway`). Keep the `backlog.md`/`backlog.py`/cron-body design text unchanged — it is the spec for when these get built.

- [ ] **Step 2: Fix the §5 cross-reference**

`docs/runbook.md` §5 says "The inventory in the README lists all 58 skills" — that count is issue #13's scope; leave it. But §5's `ralph_loop/SKILL.md` integration note references the loop design — append `(see Appendix A)` to that bullet so the reader knows it's planned.

- [ ] **Step 3: Verify no numbered section references a non-existent path (Review Focus 4)**

```bash
# After the move, sections ## 1. through ## 5. and ## 8. must not mention:
grep -n "workspace/ralph\|workspace/open-connector" docs/runbook.md | grep -v "Appendix A"
```
Expected: no hits outside the appendix.

- [ ] **Step 4: Commit**

```bash
git add docs/runbook.md
git commit -m "docs(runbook): move ralph loop and open-connector to planned appendix"
```

---

### Task 4: Rewrite §4 to document the actual MCP integration

**Files:**
- Modify: `docs/runbook.md:80-98` (§4, "MCP client and connector registration")

**Interfaces:**
- Consumes: live `~/.config/opencode/opencode.json` (verified 2026-10-19)
- Produces: §4 describing what exists

- [ ] **Step 1: Replace the DIY client.py design with the real integration**

Decision (do not relitigate): the hand-rolled JSON-RPC `client.py` was never built (`~/workspace/custom-connectors/custom.neurostrata/` does not exist). Document what actually works — the OpenCode MCP stdio wiring. Replace the section body with the following (note the 4-backtick outer fence — the content contains its own fenced block):

````markdown
## 4. MCP client registration

No hand-rolled client is needed. The memory backend is consumed via MCP over
stdio; the working integration is the OpenCode config at
`~/.config/opencode/opencode.json`:

```json
"mcp": {
  "neurostrata": {
    "type": "local",
    "command": [ "/home/hatch/go/bin/neurostrata-mcp" ],
    "enabled": true
  }
}
```

The server speaks MCP over stdio (protocol version `2024-11-05`).
Two protocol quirks for anyone writing a custom client:
- After `notifications/initialized`, the server emits a bare `{}` line on stdout. Tolerate non-JSON-RPC lines instead of failing.
- Maintain an `ALLOWED_TOOLS` allowlist, populated only with tool names reviewed from `list-tools` output. Suggested initial set: `neurostrata_add_memory`, `neurostrata_get_memory`, `neurostrata_search_memory`, `neurostrata_list_namespaces`, `neurostrata_get_snapshot`, `neurostrata_supersede_memory`, `neurostrata_archive_memory`, `neurostrata_append_log`.

Verify end to end: with the daemon running (`neurostrata-mcp status` healthy),
add a test memory and search it back through the MCP client; then archive the
test record. `add_memory` requires `content`, `namespace`, `project_root`.
````

- [ ] **Step 2: Verify the documented config matches reality**

```bash
python3 -c "import json; c=json.load(open('/home/hatch/.config/opencode/opencode.json')); print(c['mcp']['neurostrata']['command'])"
```
Expected: `['/home/hatch/go/bin/neurostrata-mcp']` — the exact command array quoted in the doc.

- [ ] **Step 3: Commit**

```bash
git add docs/runbook.md
git commit -m "docs(runbook): document actual OpenCode MCP integration"
```

---

### Task 5: Fix the §8 verification checklist

**Files:**
- Modify: `docs/runbook.md:127-137` (§8, checklist)

**Interfaces:**
- Consumes: Tasks 1–4 (know what's real)
- Produces: checklist with only checkable items

- [ ] **Step 1: Rewrite the checklist**

Replace the checklist with items that each name an exact command and expected output (Review Focus 5). Keep the real ones, drop the fictional ones, fix paths:
```markdown
## 8. Verification checklist

- [ ] `bd ping` returns ok; `bd init` in a scratch repo, then create/show/close one issue
- [ ] `ocr delegate preview --format json` returns a review spec with no API key
- [ ] `~/go/bin/neurostrata-mcp status` reports healthy; MCP store/search/fetch/archive round-trip passes
- [ ] Scheduler shows the `neurostrata-watchdog` job with a next run time; a manual run backs up to Google Drive on DB change
- [ ] `go version` reports go1.27.2
```
Dropped (with reason, for the commit message): `backlog.py next` (no backlog.py — Appendix A), `ralph-loop` scheduler check (no such job), empty-backlog run behavior (no loop).

- [ ] **Step 2: Verify every checklist item is checkable (Review Focus 5)**

For each item, confirm the command exists and the expected output is stated. `neurostrata-watchdog` job existence was verified 2026-10-18 — re-confirm at implementation time if the scheduler is reachable.

- [ ] **Step 3: Final markdownlint check and commit**

```bash
npx --yes markdownlint-cli2 docs/runbook.md 2>/dev/null || echo "markdownlint not available locally; CI will check"
git add docs/runbook.md
git commit -m "docs(runbook): verification checklist covers only real components"
```

---

## Self-review notes (factchk validation applied 2026-10-19)

- Section line numbers cited (runbook §§1–8) verified via `grep -n "^## "` on the worktree file @ e73cafe.
- Install records traced to citable sources, not intuition: bd `go install` + CGO note ← `~/TOOLS.md` ("Go toolchain" section); neurostrata-mcp tarball + SHA256SUMS + `~/go/bin` ← `~/memory/2026-10-16.md` (NeuroStrata install entry); ocr v1.13.1 ELF + sha256sum.txt verification ← `~/memory/2026-10-16.md` (Parallel repo reviews entry); Go 1.27.2 + `~/sdk/go` + `GOTMPDIR` workaround ← `~/TOOLS.md`; MCP stdio config ← live `~/.config/opencode/opencode.json` (command array verified by reading the file).
- Absence claims re-verified live 2026-10-19: `~/workspace/ralph`, `~/workspace/open-connector`, `~/workspace/bin`, `~/workspace/custom-connectors/custom.neurostrata` all absent; `~/go/bin/` contains bd, gh, neuroplasticity, neurostrata-mcp, ocr, shfmt.
- Flagged judgment call (not silently decided): the ocr download URL is intentionally not specified — the plan documents the verified outcome (version, path, checksum practice) and cites the install record, rather than asserting a URL from memory.
- Scope boundary: README inventory alignment is issue #13's job — Task 1 Step 5 checks for contradiction only, not full alignment, to avoid diff overlap.
- The `grep -v "Appendix A"` filter in Task 3 Step 3 assumes the appendix heading contains "Appendix A" — the Step 1 verbatim heading guarantees this.
- Nested code fences in Task 4 Step 1 use 4-backtick outer fencing — verified the plan file renders the verbatim block correctly.
