# Branch Protection Evidence

> **Status:** descriptive. This document records the live branch-protection
> state read from the GitHub API on the retrieval date below. It is evidence,
> not policy: hand-copied settings drift, so re-verify with the commands
> in the retrieval stamp before relying on any row.

## Retrieval stamp

- Retrieved: 2026-11-16 (UTC).
- Repository default branch: `develop` (verified via
  `gh api repos/pratik-saptarshi/autonomous-engineering-platform`
  with `--jq '{default_branch, visibility}'`).
- Exact commands to re-verify (run from the repo root, authenticated `gh`):

```text
gh auth status
gh api repos/pratik-saptarshi/autonomous-engineering-platform/branches/main/protection
gh api repos/pratik-saptarshi/autonomous-engineering-platform/branches/develop/protection
gh api repos/pratik-saptarshi/autonomous-engineering-platform/branches/main/protection/required_pull_request_reviews
gh api repos/pratik-saptarshi/autonomous-engineering-platform/branches/develop/protection/required_pull_request_reviews
cat .github/CODEOWNERS
ls .github/workflows/
```

## Protection table (live state on 2026-11-16)

| Setting | `main` | `develop` (default) |
|---|---|---|
| Required status checks (strict) | `true` | `true` |
| Required checks | `docs-lint`, `shell-lint`, `script-tests`, `go-checks`, `security`, `vendor-integrity`, `skills-freshness`, `skills-routing-check` | Same 8 as `main`, plus `policy-delta` |
| Required approving reviews | 1 | 1 |
| Dismiss stale reviews | `false` | `false` |
| Require code-owner reviews | `false` | `false` |
| Require conversation resolution | `true` | `true` |
| Allow force pushes | `false` | `false` |
| Allow deletions | `false` | `false` |
| Enforce admins | `false` | `true` |
| Require linear history | `false` | `true` |
| Required signatures | `false` | `false` |
| Auto-merge | No mechanism exists (see below) | No mechanism exists (see below) |

Notes:

- The `develop` branch carries one extra required check (`policy-delta`)
  that `main` does not. Both branches otherwise share the same eight
  required checks, which match the `ci.yml` job IDs.
- CODEOWNERS (`.github/CODEOWNERS`) is `* @pratik-saptarshi`, but
  require-code-owner-reviews is `false` on both branches, so ownership
  does not gate merge today.

## Auto-merge status

No auto-merge mechanism exists in `.github/workflows/`. The directory
contains only `actionlint.yml`, `ci.yml`, `dependency-review.yml`, and
`secret-scan.yml`, and a case-insensitive search for
`auto-merge|auto_merge|automerge` across that directory returns zero
matches (verified 2026-11-16). The only auto-merge mechanism in the repo
is prose in `skills/feature-pr-pipeline/SKILL.md`, which is documentation,
not an enforced workflow. A follow-up issue proposes a docs-only
auto-merge guardrail once a pipeline workflow file exists; until such a
file lands there is no regex or workflow target to edit, so this task
makes no workflow change.
