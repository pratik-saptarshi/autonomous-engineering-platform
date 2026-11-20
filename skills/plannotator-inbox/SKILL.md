---
name: plannotator-inbox
version: 1.0.0
author: pratik-saptarshi
description: >-
  Batch agent decision questions to the owner through the locally pinned,
  hardened Plannotator Inbox and route the owner's answers back to the
  asking session. Use when several related rulings can be answered together
  without holding a lane open, especially the pilot ruling batch. The Inbox
  is an asynchronous decision queue, not a plan-approval gate and not a
  general substitute for explicit authorization.
---

# Plannotator Inbox

Use the Inbox to make owner decisions batchable and traceable. Ask fewer, better questions; let the owner answer them together; apply each answer exactly as given.

## Adoption boundary

- The local tool is pinned at Plannotator **0.28.63** and is in pilot posture.
- Until broader adoption is separately approved, use the Inbox only for the designated pilot in `~/workspace/plannotator-pilot/`.
- Muse is listed upstream as supported through the Inbox MCP entry. That supports question delivery and replies; it does not by itself prove that a Muse session can be mechanically held at a plan gate. Keep that distinction explicit.
- The adoption setup did **not** register an MCP server or modify agent-host configuration. Registering `plannotator inbox mcp` with a host is a separate configuration step requiring the owner's approval.

## Only the hardened launcher

Start or configure the Inbox only through:

```bash
~/workspace/bin/plannotator
```

The MCP command, when a host has been approved and configured to use the launcher, is:

```bash
~/workspace/bin/plannotator inbox mcp
```

Never invoke the versioned binary directly or run the upstream installer. The launcher disables the daily ping, AI features, sharing, remote mode, Jina fetching, git-remote checks, and automatic updates.

Never expose the Inbox through remote mode or a `--tailscale` surface. It is a local, single-operator queue.

## What belongs in the Inbox

Good Inbox items are decisions the owner can make from a compact brief:

- a choice among named options;
- approval or rejection of a bounded proposal;
- a priority, threshold, or scope ruling;
- a request to review a plan, file, or diff as background for one of those decisions.

Do not use the Inbox to dump unresolved research, raw logs, secrets, credentials, or an entire project history. Link or name the local artifact instead.

## Batch format

Give every item:

1. **Stable label** — project plus a short decision name.
2. **Asking context** — project, lane or session, and why the decision is needed.
3. **Question** — one decision, stated so it can be answered directly.
4. **Options and consequences** — the realistic choices and what each one changes.
5. **Recommendation** — the agent's recommendation and its main reason, clearly marked as a recommendation rather than the decision.
6. **Blocking scope** — what can continue without the answer and what must wait.
7. **Deadline or trigger** — when the answer becomes stale, if applicable.

Batch related questions together. For the pilot, the ruling batch must contain at least five questions.

## Submission and routing

1. Submit the batch through the connected session's Inbox tools.
2. Record the item labels in the lane's normal work record so an answer can be matched even if the session restarts.
3. Do not hold the asking lane open solely to wait. Continue independent work or park the dependent branch cleanly.
4. When the owner answers, route the answer back to the asking session or recover it from the Inbox before acting.
5. Acknowledge the ruling in the lane record, including its scope. Apply it exactly; if it is ambiguous or appears to conflict with a later instruction, ask a focused follow-up rather than broadening it by inference.

## Decision authority

- An Inbox answer decides the question asked. It does not expand the project scope by implication.
- An answer is not a plan approval unless the item explicitly presented the plan for approval and the applicable gate workflow was used.
- Merges, pushes, publications, purchases, deletions, credential changes, and other irreversible actions still require the authorization demanded by their governing workflow.
- Silence is not consent. An unanswered item remains pending.

## Failure rules

- If MCP is unavailable or a reply does not route, report the failure and use the normal chat ruling path. Do not install a plugin, run the upstream installer, or change host configuration without approval.
- If a session ends before an answer arrives, recover the thread from the Inbox and the lane record before acting; do not ask the owner to repeat the ruling unless both are unavailable.
- If the version is not 0.28.63 or a surface binds beyond loopback, stop and report it.
- Keep questions free of credentials and unnecessary personal or proprietary detail. The archive is local, but it is still a record that should contain only what the decision needs.

## Pilot evidence

Record submission and answer times, routing success, batch size, decision latency, whether the archive made the ruling recoverable, any lane stall, and any unexpected network behaviour. The pilot record is `~/workspace/plannotator-pilot/README.md`.
