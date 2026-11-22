---
name: opencode-runner
version: 1.0.0
author: Musebot-Astro
description: >
  Delegate bounded, verifiable execution work to the OpenCode CLI
  (v2.3.0) as an independent runner/executor layer, using only
  OpenCode Go-plan and free models. Transport is the local server's
  HTTP API — never `opencode run`, which hangs nondeterministically
  in v2.3.0. Use when a task suits a second engine: parallel
  implementation lanes, independent verification passes, bulk
  mechanical edits, test-writing lanes. Enforces a hard model
  policy (Go + free only, Zen-metered denylist, family ban on all
  Pro / Claude / Gemini / Grok models, fail closed) and recognizes
  the three console org gates as account actions for the owner,
  never as errors to retry or route around.
---

# OpenCode Runner

Treat the OpenCode CLI as an independent executor: it does bounded
work in a throwaway worktree and returns artifacts (diffs, files,
logs, a self-report). Muse verifies everything before it lands.
The runner never pushes, posts, merges, or touches the owner's
accounts.

## When to use

- Independent implementation attempts on well-specified tasks.
- Second-opinion code generation and verification runs.
- Bulk mechanical edits, test-writing lanes, boilerplate.
- Probes and smoke checks on free models (zero marginal cost).

Not for: work needing the owner's accounts, secrets, or judgment
calls; anything whose output cannot be independently verified.

## Transport (Phase 0, verified 2026-11-15)

**Primary: the local server's HTTP API.** The background service
listens on `http://127.0.0.1:49374` (loopback only — never change
its network exposure). Drive it with `opencode api` from the
target working directory, or with direct loopback HTTP (Basic
auth, user `opencode`, password in
`~/.local/state/opencode/service.json` — read it programmatically,
never print it).

Session lifecycle (all sub-second, deterministic):

```bash
# create (model ref + explicit location are mandatory)
opencode api session.create --data '{
  "title": "<task slug>",
  "model": {"id": "glm-5.3-flash", "providerID": "opencode-go", "variant": "default"},
  "location": {"directory": "/abs/path/to/worktree"}
}'
# prompt (async; returns the queued user message)
opencode api session.prompt --param sessionID=<id> --data '{"text": "<task prompt>"}'
# wait for the terminal state
opencode api POST /api/experimental/session/<id>/wait --data '{}'
# read the transcript (assistant messages carry content or a structured error)
opencode api GET /api/session/<id>/message
```

One-shot completions (no session): `opencode api
experimental.generate.text --data '{"prompt": "...", "model":
{"id": "...", "providerID": "opencode-go", "variant": "default"}}'`
returns `{text, tokens, cost}`.

**Fallback: the direct Go API.** `POST
https://opencode.ai/zen/go/v1/chat/completions` with the stored
Console key (from `~/.local/share/opencode/auth.json`, read
programmatically, never printed), a stable `x-opencode-session`
header per conversation, and `User-Agent: opencode/2.3.0` (the
default Python UA is blocked by Cloudflare error 1010). Reference
implementation: `~/workspace/plans/2026-11-15-opencode-runner-skill/phase0/probe_go_api.py`.
Use the fallback only when the local server is down; it has no
session/tool machinery, so it suits one-shot completions only.

**Forbidden transports (v2.3.0):**

- `opencode run` — hangs nondeterministically on provider errors
  (identical invocations alternate between a clean JSON error and
  zero output until killed; shutdown then stalls ~10 s). Do not
  use it, and do not treat a hang as a task failure — switch to
  the server API.
- `opencode run --standalone` — its stdio server child never
  becomes ready.
- `opencode acp` — answers nothing to a bare JSON-RPC
  `initialize`; not a viable scripted surface as probed.

Timeouts: API calls answer in <1 s when healthy. Wrap calls in a
60 s outer timeout; silence beyond ~30 s means transport trouble —
check server health (`curl -s http://127.0.0.1:49374/api/info`
returns 401 without auth when up) before retrying anything.

## Model policy (hard — fail closed)

Only Go-plan and free models may ever be called for chat/agent
work, plus the System One decision models on their own endpoint
(owner-added 2026-11-15; see their section below). If a requested
model is not on the allowlist, stop and report — never fall back
to a metered or banned model, even if the task asks.

**Provider spelling is billing.** Go-plan models are spelled
`opencode-go/<model-id>` (providerID `opencode-go`). The bare
`opencode/<model-id>` spelling routes to the Console provider and
bills Zen pay-as-you-go; it returns 402 "Insufficient balance" on
a console with no credits and must never be used for Go models. Treat
any `opencode/`-prefixed ref as metered.

**Allowlist — Go plan (CLI provider `opencode-go`):**
deepseek-v4.1-flash, glm-5.3, glm-5.3-flash,
kimi-k2.7-code, qwen3.8-flash, qwen4-max.
(Removed 2026-11-16, weekly catalog check: gpt-6-luna, kimi-k3
and minimax-m3 no longer appear in the `opencode-go` catalog
or on the Go endpoint — struck from this allowlist. qwen4-max
is new in both and joins the allowlist; it is not family-banned.)

**Allowlist — Go-endpoint-only (direct API transport):**
mimo-v2.6-flash, minimax-m3.1-flash, qwen3.8-flash, qwen3.8-max,
step-5-preview. (muse-spark-1.2/1.3-contributor and
iceman-contributor-free are catalog-listed but policy-gated — see
the training gate below; do not use them for code work.)
(Removed 2026-11-16, weekly catalog check: glm-5.2, gpt-5.6-luna,
hy3, hy4, hy4-preview, longcat-2.0 and qwen3.7-plus no longer
appear on the Go endpoint or in the `opencode-go` catalog —
struck from this allowlist.)

**Allowlist — free:** beam-free, big-pickle,
deepseek-v4.1-flash-free, flint-40b-free, glm-5.3-flash-free,
hy4-flash-free, iceman-free, inkling-2-small-free, longcat-2.5-free,
mimo-v2.6-flash-free, minimax-m3.1-flash-free,
nemotron-3.5-lightning-free, nemotron-3.5-super-vl-free.
(Added 2026-11-16, weekly catalog check: hy4-flash-free is new
in the `opencode`, `opencode-go` and Go-endpoint catalogs and
joins the free allowlist; it is not family-banned. No prior free
allowlist model was removed.)

**Allowlist — System One decision models (Console API, separate
surface; owner-added 2026-11-15):** jev-1.13-free (free),
jev-1.13, gpt-6-luna-decision and gemini-decision-1 (Console,
billed per call).
These are NOT chat models: they live on
`https://opencode.ai/inference/systemone/v1/systemone`, take a
`state` plus typed questions (`noul` yes/no, `choice`,
`score`), and return values with probabilities — they generate
no text and cannot run agent sessions. Use them only for
judge/triage/classification plumbing, with the stored Console
key (Bearer auth, read programmatically, never printed). They
never appear in the CLI or Go catalogs. **Named exception
(owner-ruled 2026-11-15):** gemini-decision-1 is allowlisted
here despite the Gemini family ban below. The exception covers
ONLY that exact model ID on this System One endpoint — every
other Gemini model, including any future Gemini decision or
chat variant, remains banned.

**Family ban (owner-directed 2026-11-15) — pattern-encoded, so
future catalog additions in these families are banned by
default:**

- id ends in `-pro` (deepseek-v4-pro, kimi-k3.1-pro,
  mimo-v2.5-pro, mimo-v2.6-pro, gpt-5.5-pro, …)
- id starts with `claude-` (all Anthropic models)
- id starts with `gemini-` (all Gemini models; sole named
  exception: gemini-decision-1 on the System One endpoint,
  owner-ruled 2026-11-15 — see the System One allowlist above)
- id starts with `grok-` (all Grok models, incl. grok-build-0.1)

**Zen-metered denylist (never call):** claude-fable-5-1,
claude-fable-5-2, claude-opus-5-5, claude-sonnet-5-5,
gemini-3.1-pro, gemini-3.5-flash-lite, gemini-3.8-flash,
gemini-4-carbon, gemini-4-hydrogen, gpt-5.3-codex,
gpt-5.3-codex-spark, gpt-5.4-mini, gpt-5.4-nano, gpt-5.5,
gpt-5.5-pro, gpt-5.6-terra, gpt-6-astra, gpt-6.1-sol,
grok-build-0.1, mistral-large-4, muse-ember-1.0, muse-spark-1.3,
muse-wonder-1.0, qwen3.6-plus. (Most are also caught by the
family ban; the denylist is the belt to its suspenders.)

**Catalog update 2026-11-16 (weekly check):** the CLI catalog
grew from 60 to 85 models because two new Console providers
appeared — `console-google` (24 models) and `console-nvidia`
(26 models). Console-provider models are metered and are never
allowlisted, whatever their family. The `console-google`
additions are mostly `gemini-` models (20 flagged banned by the
family ban, including gemini-2.5-flash, gemini-3.5-flash,
gemini-3.8-flash, gemini-4-argon, gemini-4-carbon and
gemini-4-hydrogen) plus gemma and deep-research models; the
`console-nvidia` additions are namespaced metered models
(nvidia/, meta/, google/, openai/ and similar prefixes) and are
likewise not allowlisted. Separately, gemini-4-carbon newly
appeared in the `opencode` provider catalog — it was already on
the denylist above and remains banned. Also removed from the
`opencode-go` / Go-endpoint catalogs in this cycle (banned or
gated, never allowlisted): claude-haiku-5-5, gemini-4-argon and
grok-4.7. The Go endpoint shrank from 30 to 19 models.

**Defaults:** bulk/mechanical work → `glm-5.3-flash`; quality
lanes → `glm-5.3` or `kimi-k2.7-code`; probes → a free model. Go models
draw on per-model monthly allowances ($15–$100 of usage); be
mindful on long lanes. The interactive CLI default
(deepseek-v4.1-flash) is the owner's choice for his own sessions,
not the runner's bulk default.

## The three org gates (known blockers — account actions, not errors)

Completions for the stored key's org
(`org_01M58216WF9YHQCD0QTAQ1FDFY`) currently terminate at one of
three console gates. Recognize each error shape, report it as an
account action for the owner, and stop. Never retry in a loop,
never route around a gate with another provider, and never change
console settings — they are the owner's, and two of them are
privacy settings.

1. **Region gate** — 400: "This OpenCode Go model is hosted
   outside Europe and the United States. Select Global at
   …/settings/privacy#regions". Hits deepseek-v4.1-flash,
   longcat-2.0, longcat-2.5-free. Remedy (owner): set the org's
   privacy region to **Global**. Region is checked before
   subscription, so a model passing this gate may still hit
   gate 2.
2. **Subscription gate** — 403 "An active OpenCode Go
   subscription is required to use OpenCode Go models" (401
   "Invalid credential" at the minimax/qwen upstreams). Hits most
   other Go models. Meaning: the key's org carries no active Go
   entitlement; the owner's Go subscription likely sits on a
   different org than the key. Remedy (owner): verify which org
   holds the subscription; issue a key from the subscribed org if
   they differ.
3. **Training-consent gate** — 400: 'Turn on "Allow paid
   endpoints that train on request data"'. Hits the contributor
   models only. Remedy (owner-ruled 2026-11-15): PROVIDE consent
   for the free contributor versions — this supersedes the
   earlier standing recommendation to leave consent OFF.
   Consent status on the new org (see Live-trial status below)
   is untested; the runner still does not need these models for
   code work.

Other terminal shapes: **402** via an `opencode/` ref = wrong
provider spelling (fix the ref to `opencode-go/…`; do not top
up). **429 "Free usage limit reached"** = the account-level free
tier cap; it resets on its own (observed window ~2.4 h) — wait,
or use an entitled Go model.

**Live-trial status:** PROVEN (2026-11-15). The owner replaced
the API key; the new key belongs to org
`org_01M480D4DS54CBFWR9A6W6WWDA` — the workspace holding the Go
subscription, confirming the gate-2 mismatch hypothesis. Gates
1–2 no longer block on the new org, and the Phase 0 exit proof
passed: two consecutive Go-plan completions via the server API.
Both live trials then ran in a scratch fixture
(`~/workspace/opencode-runner-trials/`, 5 files, 9 occurrences
of a deprecated name) and passed independent verification:

- **Trial 1 — bulk edit, glm-5.3-flash** (session
  `ses_e1d63550effeLhBQRnFEwlZnPq`): renamed `legacy_fetch` →
  `fetch_v2` in place (alpha.py 3, beta.py 2, gamma.js 2,
  README.md 2, delta.txt 0). Verified by grep/diff against a
  pristine copy: zero occurrences remaining, and every file
  byte-identical to the pristine file with only the
  substitution applied — nothing else changed, no files
  created or deleted. PASS.
- **Trial 2 — verification lane, glm-5.3** (session
  `ses_e1d629f52ffe6c9P1M2h8LkDbz`): returned bare-JSON
  per-file `legacy_fetch`/`fetch_v2` counts for all 5 files;
  the parsed JSON matched grep ground truth on all 10 counts,
  and the session modified nothing. PASS.

Live use of the runner (server-API session transport,
allowlisted Go models) is now proven.

## Directory awareness

Sessions always carry an explicit `location.directory` — never
rely on the server's default location. (In v2.3.0 the default
resolves to the home project, `$HOME`, and does not follow
the service's working directory; a full service stop/start from
`~/workspace` left it unchanged. Explicit per-session location is
the mechanism that works.) The global config
(`~/.config/opencode/opencode.jsonc`) registers the typical
working set so cross-repo work isn't blocked by project-root
sandboxing: `permissions` rules allow `read` and
`external_directory` across `$HOME/workspace/*` and
`$HOME/.config/opencode/*`, and `references` name the main repos (aep,
dap, neurostrata, rocinante, esf, custom-skills, plans).
Verified 2026-11-15: sessions rooted at the AEP, dap, and
Rocinante repos and at `~/workspace/plans` each booted their
location services server-side and ran the agent loop in that
root (terminating at the region gate, like all completions
today). Edits belong in the session's own worktree (in-project),
not via external-directory reach into a live checkout.

## Local assets (configured 2026-11-15)

The global config also wires the owner's local assets into every
session (backup: `opencode.jsonc.bak-2026-11-15-access`):

- **Skills:** `skills: ["$HOME/workspace/custom-skills"]` (the
  config file itself carries the expanded absolute path) —
  the owner's skill library is discovered in place (109 skills
  enumerated via `GET /api/skill`, including OpenCode's built-ins;
  a few root files like the library README enumerate as noise
  entries). The library stays single-sourced; never copy skills
  into the opencode config dir. A `neurostrata` skill pre-exists in
  both default locations (`~/.agents/skills` and
  `~/.config/opencode/skills`) and logs a duplicate-name warning —
  pre-existing, harmless. `/opt/muse/skills` (Muse's bundled
  product skills) is deliberately NOT wired: those playbooks assume
  Muse's own connectors and tools.
- **MCP — neurostrata:** a `local` server entry spawning
  `~/workspace/neurostrata/bin/neurostrata-mcp` with no subcommand
  and `HF_HUB_OFFLINE=1` (the exact recipe the Muse connector's
  client.py uses), timeout 300000 ms (client.py's own spawn timeout
  is 300 s). Verified connected with 56 tools at a workspace
  location. Two operational facts: (1) **warm the daemon first** —
  with the daemon down, the first connect attempt timed out at
  ~128 s; with it up (`neurostrata-mcp status` healthy, or one
  `client.py list-tools` call), connects land in seconds. (2) The
  binary prints non-JSON-RPC lines on stdout; OpenCode logs
  "Invalid MCP stdio message" warnings and connects anyway.
  **Exposure note:** OpenCode sees all 56 server tools, including
  the task/guard/synaptic families that the Muse connector's
  8-tool ALLOWED_TOOLS deliberately holds back, and the memory
  write tools. **Owner-ruled 2026-11-15: the full 56-tool surface
  stands** — do not scope the runner to the connector's allowlist;
  the runner's own safety rules below (throwaway worktrees, no
  external state changes) are the governing constraints.
- **MCP — OpenConnector:** deliberately NOT wired (its MCP server
  mode is untested). The gateway is reachable from sessions via
  its CLI helper (`~/workspace/custom-connectors/custom.openconnector/bin/oc.py`)
  when a task needs it.
- **Plugins / commands / agents:** no local OpenCode plugins or
  custom commands/agents exist yet; the config keys (`plugins`,
  `commands`, `agents`) and the `~/.config/opencode/{plugin,commands,agents}`
  locations are the mechanisms when some are authored.

## Safety rules

- Work only in a throwaway git worktree/branch created for the
  task; the runner's output is a diff plus logs, never a commit
  on a shared branch.
- No secrets or credentials in prompts — not the API key, not
  vault material, not personal data. Prompts carry the task and
  the code it needs, nothing else.
- The runner never pushes, posts, merges, arms auto-merge, or
  changes any external state. Landing anything is Muse's step,
  after verification, under the usual owner-approval rules.
- Never change the server's network exposure (loopback only),
  console settings, or the stored credentials. Connecting an
  integration or restarting the local service for config reload
  is fine; widening access is not.
- Respect the model policy even under task pressure: a request
  for a banned or metered model is a stop-and-report, not an
  override.

## Output contract

A runner lane returns: (1) the session id and model used, (2)
what it changed (diff or file list), (3) test/build output it
ran, (4) a short self-report including anything it could not do.
Muse independently verifies — re-runs the tests, reads the diff —
before treating the output as done, exactly as with any subagent
lane. A lane that ends in an org-gate error returns the gate
shape verbatim; that is a reportable result, not a failure to
hide.

## Maintenance

The Go catalog and CLI change often. The weekly update check
(cron job `opencode-catalog-weekly-check`, homed in the
Engineering Platform & Skills chat; checker
`~/workspace/opencode-runner-watch/check_catalog.py`, baseline
state in `~/workspace/opencode-runner-watch/state.json`) re-pulls
both catalogs, diffs them against the tables above and the
MEMORY.md model map, re-applies the family ban to new entries,
re-runs the SkillSpector gate after any edit, and reports changes
to the owner. It also retests `opencode run` — if a future CLI
release fixes the hang, the preferred transport switches back to
the CLI and that change is reported.
