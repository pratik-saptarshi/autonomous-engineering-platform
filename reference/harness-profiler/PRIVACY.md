# Privacy

harness-profiler runs on your machine and sends nothing to its author. There is no server, no telemetry, and no account.

## What it records

For each tool call in a Claude Code session, the hook writes one line with:

- the tool name, and the skill or agent name when there is one;
- when the call ended, how long it took, and whether it failed;
- the first 200 characters of its arguments and the first line of its result, up to 300 characters;
- the session id, the id of the context that made the call, and the git branch.

It also reads token usage numbers from Claude Code's transcript files on your machine. It does not copy the conversation.

Values that look like secrets (tokens, keys, passwords) are masked before a line is written. Masking works by pattern, so check a trace before you share it.

## Where it is stored

In your own repository, in `.harness-profile/<session-id>.jsonl`. The folder is added to `.git/info/exclude`, so traces stay out of commits.

## Where it goes

Nowhere, unless you send it. The hook makes no network requests.

There is one case where a trace leaves the machine it was recorded on. In a Claude Code cloud session, the `show-profile` skill publishes the rendered page as an artifact on your own claude.ai account, because the session's container is deleted when it ends. If the session can't publish an artifact, the skill commits the page and the trace to the session's branch. On your own machine the page opens as a local file.

## How to remove it

Delete the `.harness-profile/` folder. To stop recording, see [Turn it off](README.md#turn-it-off).

## Questions

Open an issue at https://github.com/afurmanov/harness-profiler/issues.
