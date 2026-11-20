# Evaluation: harness-profiler for AEP

**Status:** review complete, adoption not started. Per `skills/adopting-external-skills/SKILL.md:3`, a review-only ask is answered as a review; a run starts only when the owner directs adoption.

**Candidate:** [afurmanov/harness-profiler](https://github.com/afurmanov/harness-profiler) at tag `v0.2.2`, commit `847bd8f6ab2a0348fd7b7057c1943e4c2fa861e8` (2026-11-16T00:46:03Z).
**Evaluated:** 2026-11-17. **Reviewer:** controller session, evidence cited inline.

## What it is

A profiler for coding-agent sessions. A hook records every tool call, skill call, subagent start/stop, session start and compaction as one JSON line; `tree` renders those lines as a text call tree or a single-file HTML UML sequence diagram, and attributes token spend to each context (one conversation history).

| Fact | Value | Evidence |
|---|---|---|
| License | MIT | `LICENSE`, `package.json` |
| Size | 79 files, 2.4 MB; capture/render logic in one 960-line dependency-free Node file | `plugin/libexec/hp.js` |
| Runtime | Node 18+, `sh` launcher | `package.json` engines, `plugin/libexec/hp.sh` |
| Maturity | Created 2026-11-15; v0.2.2; 3 releases in 24 h; 34 stars; single author | GitHub API |
| CI | None; tests exist (`node --test`, per-harness fixtures) | no `.github/workflows`; `test/` |
| Install | Claude Code plugin marketplace, or `npx -y github:…` | `README.md#install` |
| Capture surface | `PostToolUse`, `PostToolUseFailure`, `SubagentStop`, `SessionStart`, `PreCompact` → `.harness-profile/<session>.jsonl` | `README.md#how-it-works` |
| Harness support | Claude Code only; Codex documented "not done"; opencode absent | `docs/design.md#not-done`, `README.md#constraints` |

## The gap it fills in AEP

AEP meters no agent session today. The only telemetry is `tools/ghg/telemetry.py` (optional OTel spans for the GitHub gateway). The improvement plan's Phase 2 asks for verified-completion rate and cost per verified task; this supplies per-context token spend and the parent/child call graph those metrics need. It is not a scorecard itself and does not claim to be.

## Fit with AEP's own findings

Adopting it as shipped would deepen the harness coupling the architecture panel already raised as a P1 (21 files referencing one harness). AEP runs opencode as a first-class harness, so "supports opencode" is an adoption condition, not a nicety.

## Portability: what the code actually requires

Read separately, the capture and render halves have different assumptions.

**Render half is record-shaped, with Claude vocabulary in nesting and visibility.** `tree` consumes records only:
- `agent_id` / `child_agent_id` establish context parenting (`hp.js:473-495`).
- `context_tokens` per record; the Claude transcript is read only for records that lack it (`hp.js:269-282`).
- `tool === "Skill"` marks an inline skill (`hp.js:586`); `SubagentStop` ends a subagent call (`hp.js:489`).
- nesting and default visibility branch on the Claude tool names in `PARENT_TOOLS` (`hp.js:29`, `visible()` at `hp.js:635-637`); an adapter must map its spawning tools onto `Skill`/`Agent`.
- `harness` is a plain record field; the render path never branches on it.

**Capture half is Claude-shaped.** `buildRecord` reads `payload.tool_name`, `tool_use_id`, `session_id`, `tool_response.agentId`, `duration_ms`, `transcript_path` (`hp.js:335-375`). Token enrichment parses Claude's undocumented transcript `usage` keys (`hp.js:231-301`).

**Consequence:** an adapter that writes `context_tokens` itself never touches a Claude transcript and maps its spawning tools onto `Skill`/`Agent`; the renderer then accepts its records unchanged. The adapter is the whole port.

**Opencode supplies the pieces** (v2.3.0, plugin API): `ctx.event.subscribe()`, `ctx.session.context({sessionID})` returning messages, and assistant messages that report `tokens` and `cost` in the same shape `session.generate` returns. Hook payloads do not carry per-call duration, so the adapter measures it between `tool.execute` events itself.

**Known mapping gaps, all adapter-local:** skill invocation is a tool call in one harness and a `Skill` call in the other; subagent parenting is `child session` vs `agentId`; token attribution is per assistant message vs per tool call, so a call's `context_tokens` is the usage of the assistant message that emitted it.

**Codex:** upstream documents no skill call at all (it infers skill use from a shell command reading `SKILL.md`), no tool failures, and mis-parenting risk when two spawns run concurrently. Codex support is therefore a subsequent adapter with known, stated degradation — not part of this adoption.

## Risks

1. **Capture of secrets.** Records carry the first 200 chars of arguments and the first line of results, masked by regex. Upstream's privacy page says to check a trace before sharing; AEP's cron loops handle credentials in env. Mitigation: planted-secret negative test, traces never committed.
2. **Vendored code executing.** The vendor tree is Node code AEP would run. Precedent exists (`reference/esf` is Go source vetted in CI), but it must be stated, and the vendored tests should run to prove the snapshot is functional.
3. **Supply chain.** One-day-old repo, no CI, single author, `npx github:` install path. Mitigation: pin by commit, byte-pin via manifest, never `npx` from GitHub.
4. **Undocumented transcript format.** Token numbers degrade silently if Claude's format changes; documented upstream. Acceptable because the adapter will supply tokens directly.
5. **Version churn.** Three releases in 24 h. Mitigation: pin, treat as a snapshot, re-vendor deliberately.
6. **Trace location in worktrees.** Traces land at the git root and are added to `info/exclude`. `hp.js:96-125` explicitly handles worktrees via `commondir`, which downgrades this risk; a test should still pin it.

## Options considered

| Option | Verdict |
|---|---|
| Install the plugin as shipped | **Reject.** Claude-only; executes from GitHub; writes `.claude/` settings into the repo; deepens harness coupling. |
| Fork and patch upstream | **Defer.** Nothing to patch yet; AEP's `FORK.md` conventions exist if the adapter cannot stay additive. |
| Vendor pinned tree + AEP-owned adapter | **Recommended.** Upstream stays byte-identical, AEP owns the multi-harness capture, and the renderer is reused unmodified. |
| Principles-only (model, no code) | **Fallback.** Correct if the opencode adapter probe fails: take "context as participant" into `runs.jsonl` and drop the dependency. |

## Recommended shape

1. Vendor `reference/harness-profiler` at the pin, byte-identical, with sha256 manifest, `vendor-integrity` entry and a reference doc. No `.claude/` files, no plugin install, no `npx`.
2. Build an AEP-owned emitter that writes schema-v2 records from an opencode plugin, filling `context_tokens` at capture time.
3. Gate promotion on a behavioural probe: the vendored `tree` must render the adapter's records with correct parents and token sums on a fixture with a planted nested-subagent tree. Failure stops at principles-only.
4. Only then wire `aep profile tree`, and later join traces to verified-task outcomes for the scorecard.
5. File `capture opencode` upstream so the adapter can retire; upstream filings are the owner's call.

## Owner decisions this evaluation leaves open

1. Verdict: adopt dormant (vendor + probe), principles-only, or reject.
2. Adapter venue: AEP-local emitter first, or upstream contribution first.
3. Pin: `v0.2.2` now, or wait for a release that supports a second harness.
