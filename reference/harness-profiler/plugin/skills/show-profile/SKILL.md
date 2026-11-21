---
name: show-profile
description: Shows the harness-profiler trace of this session as a page the user can open. Use when the user asks to see the profile, the trace, the call tree, or what the session's skills and agents cost.
---

# Show the profile

Render this session's trace and put the page where the user can open it. The trace is the newest session in `.harness-profile/` at the git root.

## 1. Find the profiler

Use the first launcher that exists:

1. `../../libexec/hp.sh` relative to this skill's base directory (the plugin this skill came with).
2. `.claude/harness-profiler/hp.sh` at the git root (the hook `init` committed).

A repository can have both, and the committed copy can be older than the plugin, so the plugin's goes first.

Call it `HP` below and run it with `sh`.

## 2. Render

```
sh HP tree
sh HP tree --format html > "${TMPDIR:-/tmp}/harness-profile.html"
```

If `tree` says no calls were recorded, say so, run `sh HP doctor`, report what it prints, and stop.

## 3. Deliver the page

Pick the first case that applies. If its step fails or is refused, go on to the next one.

- **You run on the user's machine** (`CLAUDE_CODE_REMOTE` is not `true`): open the file with `open` (macOS), `xdg-open` (Linux) or `start` (Windows), and give its path. Don't publish it, even if you have a tool that can: the trace stays on the machine unless the user asks for a link.
- **A cloud session with a tool that publishes an HTML page as an artifact**: publish the file as a private artifact titled `Harness profile <first 8 characters of the session id>` and give the user the link.
- **Otherwise** (a cloud session with no artifact tool): the container is thrown away when the session ends, so commit the page and the trace to the current branch, under `harness-profile/` at the git root, as `<session id>.html` and `<session id>.jsonl`, and push. Running this skill is the user's request for that commit and push, because nothing else would save the trace. Tell the user the paths and that GitHub shows an HTML file as source, so they open it after `git pull`.

## 4. Answer

In two or three lines: how many calls and contexts, and the three most expensive contexts by duration with their tokens, read from the text tree. Then the link or path. Don't paste the tree.
