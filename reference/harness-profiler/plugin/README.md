# harness-profiler

A profiler for a Claude Code setup of skills and subagents. It records every skill, agent, and tool call of a session through hooks, and shows which calls share a context and what each one costs in tokens.

## Install

In Claude Code:

```
/plugin install harness-profiler --marketplace afurmanov/harness-profiler
```

## Use

At the end of a session, run:

```
/harness-profiler:show-profile
```

You get one self-contained page: a lifeline per context, an arrow per call with the result it returned, and the token counts next to each context.

It works in Claude Code only. Claude chat and Cowork don't run plugin hooks, so there the plugin installs but records nothing. It needs Node 18 or newer and git.

Traces stay in `.harness-profile/` in your repository. The hook makes no network requests.

Documentation, the design notes, and the tests are in the [repository](https://github.com/afurmanov/harness-profiler).
