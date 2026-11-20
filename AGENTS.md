# AGENTS.md

Operating guide for agents working in this repository.

## Git and review

- Use Conventional Commit subjects for every commit (`type(scope): imperative summary`, e.g. `fix(scripts): signal all daemon PIDs when stopping for backup`).
- Name branches `type/scope-short-description` (e.g. `fix/scripts-watchdog-signal-all-daemon-pids`), matching the Conventional Commit type and scope of the change.
- Use Conventional Commit subjects for PR titles as well.
- Commit with your own identity; bots use their configured user.name/user.email (no hardcoded address).
- Keep changes focused; do not rewrite shared history. Require conversation resolution before merge. Never bypass branch protection.
- Plans that change autonomous-loop guards (iterations, strikes, leases) must change code + tests, not prompts alone.
- Sign all PR titles/descriptions and all PR/issue comment text from this session with the local name given in the agent's environment (e.g. in its IDENTITY.md), ending with a `— <local name>` signature line; if the environment gives no local name, sign as `Terminator3000-DarkCrouton`. This applies to every PR body and every review/issue comment posted in this session, including replies to review threads.
