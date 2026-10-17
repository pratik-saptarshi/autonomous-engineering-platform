# AGENTS.md

Operating guide for agents working in this repository.

## Git and review

- Use Conventional Commit subjects for every commit (`type(scope): imperative summary`, e.g. `fix(scripts): signal all daemon PIDs when stopping for backup`).
- Name branches `type/scope-short-description` (e.g. `fix/scripts-watchdog-signal-all-daemon-pids`), matching the Conventional Commit type and scope of the change.
- Use Conventional Commit subjects for PR titles as well.
- Commit as `Musebot-Astro <6238157+pratik-saptarshi@users.noreply.github.com>` unless instructed otherwise.
- Keep changes focused; do not rewrite shared history. Require conversation resolution before merge. Never bypass branch protection.
