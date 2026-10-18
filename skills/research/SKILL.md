# Research

Delegate investigation to a background agent so you keep working while it reads.

## Brief the researcher

- Spin up the work with `subagent.spawn`, giving it the exact question and what the findings are for.

- Tell it to investigate against **primary sources** (official docs, source code, specs, first-party APIs), not secondary write-ups. Every claim must trace back to the source that owns it.

- Instruct it to write findings to a single Markdown file, with each claim citing its source.

## Place the findings

- Save the file where such notes already live for the task at hand: a goal's `files/` directory, or `~/workspace/research/<slug>.md` when there is no existing convention.

- Report back the path and a short summary of the key findings, with the strongest sources named.

## What not to do

- Never present un-cited claims as established fact. If the researcher could not verify something, say so plainly.

- Do not use this for facts a quick search or a single page read can settle; reserve it for reading legwork worth delegating.
