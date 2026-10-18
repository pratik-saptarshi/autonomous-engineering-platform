# Code Explorer

Adapted from the FastContext Explorer pattern (Jakevin/fastcontext-agent-tools, wrapping Microsoft FastContext): separate repository exploration from code solving. A read-only explorer answers one narrow question, which files and line ranges to inspect, and you verify the citations yourself before acting.

## Delegate exploration

- Spawn an explorer with `subagent.spawn`. Give it exactly one narrow question naming the behavior, subsystem, or failure to locate, plus the repository root.

- Instruct it to be read-only: use `muse.read` and `muse.exec` (grep, glob, find) only, issue independent searches in parallel, and never edit, move, or run code.

- Require the answer as compact file-and-line citations, one per line, such as `src/router.py:42-58`. Ask for citations, not a prose summary and not proposed fixes.

- Shape the question around behavior and intent: "Find where OAuth access tokens are refreshed and which tests cover expired token handling." Never ask the explorer to solve or patch; "Fix the upload bug" is not an exploration question.

## Verify before acting

- Treat citations as candidate evidence, not proof. Read the cited ranges and surrounding context yourself with `muse.read`.

- Confirm the cited code actually controls the requested behavior. When citations reveal a symbol but not all call sites, search locally for the rest.

- When citations are sparse or off-target, refine the question once with concrete terms from the task: the error string, the subsystem name, or nearby filenames.

## When not to use

- You already read the exact file and its surroundings in this session.

- One known file and one obvious search answers the question.

- The task is pure writing or generation with no repository to explore.

- The task is not about code.

## Note on the upstream tooling

- The original implementation is an MCP server (`fastcontext-mcp`) that needs a FastContext-compatible model endpoint, an API key, and an MCP client. None of those exist in this environment, and its pinned upstream dependency is currently unreachable, so the server is not installed here. This skill keeps the methodology, which needs nothing but a subagent.
