# AGENTS.md

Operating guide for agents working in this repository.

## Git and review

- Use Conventional Commit subjects for every commit (`type(scope): imperative summary`, e.g. `fix(scripts): signal all daemon PIDs when stopping for backup`).
- Name branches `type/scope-short-description` (e.g. `fix/scripts-watchdog-signal-all-daemon-pids`), matching the Conventional Commit type and scope of the change.
- Use Conventional Commit subjects for PR titles as well.
- Commit with your own identity; bots use their configured user.name/user.email (no hardcoded address).
- Keep changes focused; do not rewrite shared history. Require conversation resolution before merge. Never bypass branch protection.
- Plans that change autonomous-loop guards (iterations, strikes, leases) must change code + tests, not prompts alone.
