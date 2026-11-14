# Informational — credential census (consumer: the P1 watch trigger)

Plan §2: a bounded census of which providers' credentials agents actually
use, at what scope. The P1 revisit trigger fires only if the census (or an
incident) names **a second provider with repeated broad standing-credential
use** from agents. Metadata only — no credential values were read.

## What agents actually hold or use (2026-11-13)

| Provider / credential | How agents touch it | Standing? | Broad? |
|---|---|---|---|
| GitHub (gh auth store, `~/.config/gh/hosts.yml`) | Exclusively via ghg pass-through: ghg classifies argv, reserves budget, execs the real `gh`; the token never transits the agent (panel R2, executed) | Yes (operator's PAT) | Scoped by ghg caps + branch protection; agent never possesses it |
| SSH key (`~/.ssh/id_ed25519`) | git transport for clones/fetches | Yes | Single key, repo-scoped by GitHub |
| Platform connectors (Gmail, Google Workspace, Plaid, Muse Mail, 1Password, Shop Pay, Tailscale, …) | OAuth/connection managed by the platform; agents call connector tools and never see credentials | n/a | Per-connector scopes |
| AI provider subscriptions (Claude, ChatGPT, Gemini, Perplexity, OpenCode, DeepSeek, Kimi, Qwen) | Consumed through the harness / vendor apps; agent shell env contains **no** provider API keys (env census: only runtime-internal `JARVIS_*` names match credential patterns) | n/a | n/a |
| ESF harness keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `TEMPORAL_API_KEY`) | Named as configuration surface in ESF's example config only. ESF has executed **zero runs** in this environment (G-P7), so recorded use is zero | Would be standing in `environment` mode | Would be broad (see G-P7) |

## Trigger assessment

**Not fired.** GitHub dominates agent credential use and is already behind
the strongest pattern in the set (pass-through; the agent never holds the
secret). No second provider shows repeated, broad, standing-credential use
by agents: connector providers are platform-held, AI subscriptions are
harness-consumed, and the one surface that *would* create standing-key use
(ESF `environment` mode) has never run here. P1 stays rejected under its
watch trigger; this census is the dated baseline a future census or
incident is compared against.
