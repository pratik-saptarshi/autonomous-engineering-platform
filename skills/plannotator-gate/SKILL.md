---
name: plannotator-gate
version: 1.0.0
author: pratik-saptarshi
description: >-
  Route supported plan approvals through the locally pinned, hardened
  Plannotator gate: the owner reviews and annotates a plan before the agent
  proceeds, a denial returns structured feedback for revision, and the local
  archive preserves the decision. Use for the Plannotator pilot and, only
  after separate adoption approval, other interactive plan reviews. Do not
  use it to gate unattended lanes or as a substitute for explicit approval
  of merges, pushes, purchases, or other irreversible actions.
---

# Plannotator Gate

Plannotator supplies the mechanical decision point; this skill supplies the local policy around it. The owner is always the approver.

## Adoption boundary

- The local tool is pinned at Plannotator **0.28.63** and is in pilot posture.
- Until the owner separately approves broader adoption, use the gate only in the designated scratch project: `~/workspace/plannotator-pilot/`.
- Do not wire it into AEP production workflows, Ralph or overnight lanes, or any unattended workflow. A blocking gate can hold a session for days.
- The mechanical `ExitPlanMode` interception is a supported-harness feature. Whether a Muse session can be mechanically gated, rather than reached through the Inbox, is an open pilot question — do not claim it works until the pilot proves it.

## Only the hardened launcher

Always invoke:

```bash
~/workspace/bin/plannotator
```

Never invoke the versioned binary directly and never run the upstream installer. The launcher pins the verified binary and enforces:

- `NO_ANON_PING=1` — the default daily anonymous ping is off.
- `PLANNOTATOR_AI=disabled` — Plannotator must not spawn agent CLIs or send plan context to an AI provider.
- `PLANNOTATOR_SHARE=disabled` — no share links or paste-service uploads.
- `PLANNOTATOR_REMOTE=0` — local mode only, even in an SSH environment.
- `PLANNOTATOR_JINA=0` and `PLANNOTATOR_GIT_REMOTE_CHECK=0` — no third-party page fetch or git-remote probe for review.
- `PLANNOTATOR_AUTO_UPDATE=0` — the pin does not move by itself.

Never use remote mode or a `--tailscale` surface. Remote mode is unauthenticated and exposes decision and repository actions to anyone who can reach the port.

## Preconditions

Before routing a plan through the gate:

1. The supported harness hook must already be configured for the scratch project. The adoption setup deliberately did **not** install hooks or modify agent configuration. If the hook is absent, stop and report that the gate is not wired; changing harness configuration needs the owner's approval.
2. The plan must be concrete enough to approve: goal, scope, material risks, verification method, and explicit out-of-scope items.
3. Work that does not depend on the decision should be identified in advance, so the lane can continue elsewhere while the owner decides.

## Decision flow

1. The agent presents the plan through the configured plan-mode hook.
2. The owner reviews it in Plannotator and either approves or denies it with annotations.
3. **Approval** authorizes the agent to proceed with the plan as presented. A material change to scope, mechanism, or risk requires re-presentation; approval does not silently expand.
4. **Denial** is a revision request, not a dead end. The agent addresses the annotations, revises the plan, and presents the revision for a fresh decision. Use the plan diff to show what changed.
5. **No decision** means no gated implementation proceeds. Park that lane, continue independent work, and report the pending decision in the normal status channel.
6. A gate approval is not a merge, push, publication, purchase, or external-action approval unless the approved plan explicitly names that action and the governing workflow also permits it.

## Archive and provenance

- Browse the local decision history with `~/workspace/bin/plannotator archive`.
- Treat the Plannotator archive as supporting evidence, not the operation's only record. Record each material decision and the owner's rationale in the project's normal record or memory system.
- If the archive and the project record disagree, stop and reconcile them before relying on either.

## Failure rules

- If the surface binds anything other than loopback, stop the session and report it.
- If the version is not 0.28.63, stop; do not silently accept an update.
- If annotations are ambiguous, ask for clarification through the Inbox or the normal chat. Do not infer an approval from silence.
- If the hook stalls an interactive lane beyond its useful window, report the stall with the session state; do not bypass the gate by changing the launcher or invoking the binary directly.

## Pilot evidence

During the pilot, record decision latency, whether approval/denial feedback was actionable, archive usefulness, any lane stall, and any network behaviour beyond the documented GitHub release check. The pilot record is `~/workspace/plannotator-pilot/README.md`.
