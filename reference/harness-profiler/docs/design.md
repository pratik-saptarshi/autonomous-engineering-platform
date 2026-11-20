# Design

Why harness-profiler is built the way it is: what Claude Code's hooks report, the decisions that follow, and what was tried and rejected. What the tool does and how to use it is in the [README](../README.md). How to record the end-to-end run is in [e2e/README.md](../e2e/README.md).

## What the hooks report

Recorded on Claude Code 2.1.322, with the payloads in [test/fixtures/](../test/fixtures/). Claude Code on the web and the CLI send the same data.

| Boundary | How the hook sees it |
| --- | --- |
| Main context | Calls with no `agent_id` |
| Fresh subagent (`Agent` of any type but `fork`, forked `Skill`) | `agentId` in the response; `agentType` on `Agent` only |
| Copy of the parent (`Agent` with `subagent_type: "fork"`) | `agentType: "fork"` in the response |
| Inline skill | `Skill` response with only `commandName` and `success`; where its work ends is not reported |
| Background subagent | `status: "async_launched"` and `agentId`, about 28 ms after launch, with no `agentType` |
| Background forked skill | `status: "forked"`, `background: true`, `agentId`, and `result: "Running in the background as @<name>"`, which is a launch notice, not a result |
| Subagent end | `SubagentStop` with `agent_type` and `last_assistant_message` |
| Compaction | `PreCompact` and `PostCompact` with `trigger`, then `SessionStart` with `source: "compact"`, same `session_id` |

Three things the table doesn't show:

- A background subagent with children of its own fires `SubagentStop` more than once. It stops while it waits, each child's report wakes it, and it stops again. Its last stop holds the verdict.
- A background subagent reports to its caller with a `SubagentHandback` tool call that carries the report as `message`. The stop that follows has an empty `last_assistant_message`, and a later completion notice can wake the subagent for one more stop whose message is a remark ("the notice adds nothing new").
- `SubagentStop` also fires for the compaction's own summarizer, with no `agent_type` and no call that started it.
- The hooks never say how full a context is or what it spent. Claude Code's transcript does: each assistant message carries `usage`, and a subagent writes its own transcript under `<session>/subagents/agent-<id>.jsonl`. The format is undocumented.

## Decisions

### Capture

1. **One readable Node file, no dependencies.** [plugin/libexec/hp.js](../plugin/libexec/hp.js) holds `capture`, `tree`, `init`, and `doctor`. People install hooks they can read. The POSIX launcher [plugin/libexec/hp.sh](../plugin/libexec/hp.sh) finds `node` with shell builtins only, because a hook can run with a bare `PATH`.
2. **A broken capture doesn't break the session.** `capture` exits 0 with no output whatever happens, and without Node the launcher does the same. A profiler must not break or slow the session it watches.
3. **`PostToolUse` and `PostToolUseFailure`, async.** Both carry `duration_ms`, so there is no `PreToolUse` pairing. The hook costs about 33 ms per call, mostly Node's startup. `async: true` takes that off the tool call.
4. **The harness comes from the command line** (`hp capture claude`), not from the payload's shape.
5. **Traces go to the git root**, in `.harness-profile/<session>.jsonl`, excluded through `.git/info/exclude`. `CLAUDE_PROJECT_DIR` can sit below the git root, and `hp tree` must find the trace from anywhere in the repository. Each record is one `appendFileSync` of at most 4096 bytes, so concurrent hooks don't interleave. To fit, `result` shrinks first, then `args`.
6. **`result` is the first line of the response.** There are no project-specific verdict patterns. A report that leads with its verdict shows it.
7. **A background call ends at its last `SubagentStop`.** The call records `background` and no result. The tree takes the end and spend from the stop, and the result from the subagent's `SubagentHandback` call, or from the stop when there is none. Until the first stop arrives, the call shows as `running` with no duration and no return, because the duration recorded so far is the launch. A trace captured before background skills were recognized holds the launch notice as its result, and the tree reads that as a background call too.

### Tree

8. **Parents come from ids, not from time.** A call whose `agent_id` matches a call's `agentId` is its child. A call without one is in main. Interval containment misfiles a main call that runs while a subagent works. A call whose parent was not recorded goes under a placeholder.
9. **A context is one conversation history**: main or a subagent, with a parent and a kind, `root`, `fresh`, or `copy`. Inline skills and compactions are markers inside one. `contextsOf` computes this once for both outputs.
10. **The text tree names contexts in words, and color is extra.** A call that starts a subagent says `new context <id>`, plus `copy of <parent>` or `background`. The word "fork" is not used, because it is also a subagent type.
11. **The name leads and the kind follows**: `review (skill)`, `counter (agent)`. A harness is read by its skills and agents. Which of the two a call is matters second.
12. **Tokens are shown per context and by kind**: `new`, `cached`, and `out`, summed from the transcripts. They cost different amounts, and how a subscription counts them isn't published, so the views show counts and no price. `Agent`'s `totalTokens` is not shown: it is the subagent's final history, not its spend. A transcript that is missing or in another format leaves the numbers out.

### Page

13. **`tree --format html` is a UML sequence diagram.** A context is a participant. A call that opens a context is a message to its lifeline, and the dashed return carries the result and duration. A background call has UML's open arrowhead. Rows are in time order, not to scale.
14. **Color follows history.** A copy keeps its parent's color and a fresh context gets a new one, in the page and in the text tree.
15. **Contexts that never overlap share a column**, to save width: a context takes the first column right of its caller's whose last context has ended. A shared column's header holds one chip per context, in the color of its bar.
16. **The page is one file**, [plugin/libexec/view.html](../plugin/libexec/view.html), with the trace inlined as JSON. It loads nothing from the network and inserts trace text escaped.

### Install

17. **On the web, the hook is committed to the repository.** Cloud sessions don't install plugins enabled in a repository's settings, so `init` copies the launcher, `hp.js` and `view.html` into `.claude/harness-profiler/` and merges the hook entries into `.claude/settings.json`. A re-run replaces what an older `init` wrote.
18. **A repository can have the plugin and a committed hook.** Both record, so `tree` drops repeated `tool_use_id`s and repeated events. `doctor` reports a committed copy that misses events, is not async, or differs from the copy that runs it.
19. **A `show-profile` skill delivers the page.** A cloud session's container is thrown away, and GitHub shows a committed `.html` as source. The skill opens the page in the browser on the user's machine, publishes it as an artifact in a cloud session that can, and otherwise commits it. A local session can have an artifact tool too, and a trace must not leave the machine unasked. It uses the plugin's launcher before the committed one, because the committed copy can be older.
20. **The plugin is the `plugin/` folder, not the repository.** Claude Code copies only that folder, and the plugin directory scans only that folder, so tests, fixtures, and recorded sessions stay out of what a user installs. The launcher is named `hp.sh` because the directory wants a file's name to match the interpreter that starts it. `init` replaces a hook committed under the old name, `hp`.
21. **One CLI name, `harness-profiler`.** The README uses `npx -y github:afurmanov/harness-profiler` until there is an npm release.

## Rejected

- **Go binaries per OS**: a blob nobody reads, and five builds per release.
- **Fetching the tool on first run**: breaks behind cloud network policies.
- **A plugin `bin/` directory**: claude.ai refuses plugins that have one.
- **A Stop hook that pushes the trace to a side branch**: a push on every turn, and some setups allow pushes only to the session's branch.
- **Perfetto (`--format chrome`)**: it colors slices by name, and it sends the reader to a third-party site.
- **Timelines** (Gantt lanes, a flame chart per thread): to scale, but readers took layout artifacts for calls, such as overlapping calls stacked like nesting. A sequence diagram answers who started whom and what came back.
- **One token total per context, or one number weighted by API prices**: a total hides that a copy's tokens are mostly cheap cache reads, and API prices are not how a subscription counts.
- **Compaction sizes from `context_tokens`**: a live session sends none, and a resumed one reported the size from before the compaction.
- **A solid gray header for a shared column**: it matched no bar's color, and readers took two contexts under it for one.

## Constraints

- No npm dependencies, Node 18+.
- No top-level `bin/`.
- Fixtures come from a neutral demo harness, such as [e2e/claude/fixture/](../e2e/claude/fixture).
- Every claim about a harness rests on a recorded payload or a cited doc.

## Not done

- **Codex.** The schema and `tree` carry over. Recorded on Codex 0.166 ([codex-local-raw.jsonl](../test/fixtures/codex-local-raw.jsonl)): there is no `duration_ms`, so capture pairs `PreToolUse` and `PostToolUse` by `tool_use_id`. A subagent's id first shows on `SubagentStart`, so its parent is the latest unmatched `spawn_agent` before it. What a user needs to know is in the README's [Constraints](../README.md#constraints).
- **Windows** is untested.
