# ghg — the GitHub gateway

## What ghg is

`ghg` is one lightweight, counted path to GitHub for every agent on
this VM. It exists because of the 2026-10-24 rate-limit incident:
roughly a dozen parallel agents, most of them running `gh run watch`
pollers against the shared classic-PAT budget (5,000 core requests
per hour), emptied that budget in minutes and every agent hard
stopped on HTTP 403.

ghg is a single Python 3 standard-library file (`ghg.py`) behind a
small shell shim (`bin/ghg`). There is no daemon and there are no
third-party dependencies. Calls routed through it are counted in a
SQLite ledger (one database in `$GHG_STATE_DIR`, default
`~/workspace/ghg-state/`) against self-imposed caps set below
GitHub's enforced limits, and run-watching is mechanically
coalesced: however many agents watch the same run, exactly one
process polls GitHub for it.

The standing discipline (one consolidated reader, sparse reads,
call caps — adopted 2026-10-24) remains the primary control. ghg is
its mechanical backstop, not its replacement.

## The honest guarantee

**This system governs callers who use it.** ghg does not and cannot
gate callers who invoke `/usr/bin/gh` directly, the GitHub MCP
connector, or the classic-connector helper; those known ungated
vectors are listed in the fence list below, and the unspendable
reserve (caps sit at 3,500 of GitHub's 5,000 core/hour) exists
partly because of them. What ghg does guarantee is conditional and
exact: calls that go through it are counted, capped on rolling
windows, and denied (exit 75) before they can exceed the
self-imposed caps; and `ghg watch` callers can never multiply
pollers for a run.

## The verbs

Entry point: `tools/ghg/bin/ghg` in this repository. After this
branch merges, the stable fleet entry point is a `~/go/bin/ghg`
symlink to the AEP main checkout's `tools/ghg/bin/ghg`, created as
a merge-time operator step (a symlink into a transient worktree
would silently rot, so it is deliberately not created before the
merge).

State resolves from `$GHG_STATE_DIR` (default
`~/workspace/ghg-state/`), never from the caller's checkout, so
every chat and worktree on the VM shares the one ledger.

- `ghg watch --repo OWNER/REPO --run ID [--interval SECONDS]
  [--timeout SECONDS]` — watch a workflow run to completion.
  Callers coalesce onto one epoch-fenced poller per run; a killed
  poller is replaced by a waiter within 2 × interval of lease
  expiry, and a displaced poller is fenced — it makes no further
  polls or writes. The poll interval floor is 45 s, enforced in
  code (a smaller request is raised to the floor, with a note on
  stderr). Default timeout 1800 s; on expiry every caller prints
  the timeout line and exits 1. On completion every caller prints
  `ghg watch: run <id> completed conclusion=<c>` and exits 0 if
  and only if the conclusion is `success`.
- `ghg run [--actor NAME] [--wait SECONDS] -- <gh args...>` — run
  one `gh` call through the budget gate: the call is classified
  into buckets, the charges are reserved atomically, the real `gh`
  executes inheriting stdio, and the reservation is finalized to
  `ok`/`error` from the child's exit code (which is the exit code
  you get). On denial nothing executes and the exit code is 75
  (see below). `ghg run -- run watch …` is refused by name (exit
  64) with a pointer to `ghg watch` — that is the incident vector.
- `ghg check -- <gh args...>` — flow pre-flight: classifies the
  given argv and exits 0 if all its charges fit current headroom,
  75 with the denial line otherwise. It executes nothing and writes
  no call or reservation rows. Multi-call publish flows (push →
  `pr create` → arm auto-merge) run `ghg check` for every planned
  gated step before step 1; if a call is still denied mid-flow,
  report the exact stage reached — a pushed branch or an unarmed
  PR is a named, recoverable state, never a silent one.
- `ghg status [--json]` — reconciliation: per bucket, the cap,
  rolling ledger spend, in-flight reservations, GitHub's own
  figures from the cached `rate_limit` snapshot, bypass counts,
  and the top 5 actors by spend. Core drift (GitHub `used` minus
  seed-adjusted ledger spend) is reported with its confounders
  named in the line itself: interactive and connector-path use
  are not ghg traffic. GraphQL drift is reported only as a coarse
  hour-scale figure — ghg charges GraphQL invocations flat while
  GitHub charges points, so a precise number would be a lie.
- `ghg prune` — deletes `calls` rows older than 30 days. Invoked
  by the scheduled drift check (see `DRIFT-CHECK.md`, a spec —
  installing that cron is a separate, gated operator step).

Actor attribution: `--actor` > `$GHG_ACTOR` > the basename of the
caller's git top-level > `unknown`. Briefs set
`GHG_ACTOR=<task-slug>` (see `BRIEF-SNIPPET.md`).

## Caps

All windows are rolling sums over ledger timestamps. GitHub's
`reset` epoch appears in messages and reconciliation only, never
in local window arithmetic.

| Bucket | Cap (rolling window) | GitHub's limit | Notes |
| --- | --- | --- | --- |
| `core` | 3,500 / 3,600 s | 5,000 / hr | The remainder is the unspendable reserve for ungated use. |
| `graphql` | 3,500 cost units / 3,600 s | 5,000 points / hr | Charged flat 2 per invocation, so the effective ceiling is 1,750 invocations/window. This bounds invocations as a proxy for points; it does not strictly bound points. |
| `search` | 20 / 60 s | 30 / min | Rolling, because fixed-window counting would allow 40 calls inside one rolling minute at a boundary. |
| `code_search` | 9 / 60 s | 10 / min | `gh search code` draws on this separate bucket. |
| `content` | 40 / 60 s and 300 / 3,600 s | 80 content-generating requests / min, 500 / hr | The throttle for mutating calls: PR/issue/comment-generating traffic is the class likeliest to trip GitHub's secondary limits. Charged alongside the primary bucket when a mutating signal is present (create/comment/merge/edit/close/reopen/review/label/upload/delete subcommands, `workflow run`, or `gh api` with a mutating method or any parameter flag). |

Fan-out modifier: an argv containing `--paginate`, `--log`, or
`--log-failed` multiplies its primary charge by 5 — a deliberate
conservative proxy, not a measurement (`--paginate` under-counts
unbounded page counts; `--log` over-counts the common
single-download case).

Fresh-database seeding: when the ledger database is created, its
first `rate_limit` snapshot records GitHub's current core `used`
as a seed, and until that window's reset the effective core spend
is the seed plus ledger spend accrued after it — a recreated
database never grants a fresh 3,500 inside a window GitHub counts
as already spent.

## Bypass

`GHG_BYPASS=1` skips the caps, still writes a ledger row with
outcome `bypass`, and warns on stderr. Bypasses are counted and
reported by `ghg status` and by the scheduled drift check. Agents
do not set `GHG_BYPASS` on their own instruction: bypass is an
operator decision, and its visibility has a consumer precisely so
it cannot quietly become the norm.

Denials: exit 75, with `ghg: DENIED bucket=<b> reset=<epoch>
cap=<n>` on stderr. `ghg run --wait SECONDS` sleeps in 30 s steps
until the denying bucket's rolling window frees the needed cost or
the bound expires, then denies.

## ghg is an accounting control, not an authorization control

ghg counts calls; it does not sanction them. A call that passes
the gate is within budget — nothing more. Pratik's merge,
deletion, and push authorization rules apply exactly as before,
and a gated call is never evidence that an action was authorized.

## Fail-open on gateway breakage, fail-closed on budget

Cap exhaustion denies (above). Gateway-internal failures — a
database error, a lock timeout after bounded retry, corrupt
state — never deny: the call passes through and is recorded with
outcome `ungated_error` (a lock/busy error is never surfaced as a
budget denial). When the ledger itself is the failure, the trace
is a line in `$GHG_STATE_DIR/fallback.log` instead.

The deepest layer is the shim: before exec'ing `ghg.py` it runs
`py_compile` on it (cache in the state dir). If compilation fails,
the shim falls back per verb, with argv translation: `run` strips
ghg's own arguments through `--` and execs the real `gh` with the
remainder; `watch` degrades to one single `gh run view` status
read (no loop) with a loud stderr warning; `check`/`status` exit
70 with a message (nothing to execute). Every fallback appends a
line to `$GHG_STATE_DIR/fallback.log`.

So `ungated_error` means: the call executed, GitHub saw it, but
the budget ledger could not account for it normally — the gateway
degraded rather than block the fleet. A rising `ungated_error`
count is a gateway-health problem (surfaced by the drift check),
not a spending spree.

If finalizing a ledger row fails *after* the real call ran, the
caller still sees the child's exit code, plus a loud stderr
warning — never a masked success that invites a duplicate create.

Privacy: argv is stored with the values of `--body`, `--title`,
`-m`/`--message`, and `--body-file` replaced by
`<redacted len=N>` at write time. Response bodies and credentials
are never stored.

## The fence — known ungated vectors, by name

The conditional guarantee above has named holes. These callers
and paths are deliberately left ungated today:

- **The GitHub MCP connector** — connected in this environment
  and does not shell out to `/usr/bin/gh`; a fleet-scale ungated
  vector. Gating it is not lightweight.
- **The classic-connector helper**
  (`~/workspace/custom-connectors/custom.github-classic/bin/ghc-api.py`)
  — same account, same core bucket, uncounted; low-volume today.
  If drift shows it mattering, folding it into the ledger is the
  first follow-up.
- **Pratik's interactive use** — same bucket; the ≥1,500
  unspendable reserve is the mitigation, and drift output names
  interactive use as a confounder rather than pretending the
  number is pure bypass.
- **Git transport** (push/fetch/clone) and `gh` credential-helper
  invocations — these consume no REST bucket by design. (Git LFS
  transfers, if ever used, draw on their own separate bucket.)
- **GitHub's CPU-time secondary limit** (90 s of CPU per 60 s,
  published) — unmodelled, like the other secondary shapes beyond
  the content throttle.
- **Prose mentions in skills** — `feature-pr-pipeline`,
  `re0-upgrade`, and `receiving-code-review` mention `gh`
  commands as instructions to future agents. They are prose, not
  unattended callers; the fleet-wide convention (AGENTS.md +
  `BRIEF-SNIPPET.md`) governs the agents who read them.
- **Prose mentions in side-chat charters** — e.g. the esf
  master-sync note (`gh repo sync … --branch master`) in a
  side-chat MEMORY.md: standing instruction text for supervised
  sessions, run rarely, not an unattended caller.

The two standing unattended callers found by the adoption census
— the DAP build crons `dap-build-check-3h` and `dap-nightly-build`
— are **not** in this fence: their conversions to `ghg run` (with
`ghg check` pre-flights) are prepared and land only on Pratik's
per-cron word, per the plan's gating rule.

## Escalation clause

A second exhaustion incident despite discipline + ghg is the
evidence that justifies the full-gateway design (PATH-level
enforcement, MCP gating, token partitioning) — build it then,
from that incident's shape. Until that evidence exists, those
designs are deliberately out of scope: the lightweight gateway is
the proportionate response to the incident that actually
happened.

## Tests

```sh
cd tools/ghg && python3 -m unittest discover -s tests -v
```

Stdlib `unittest` against fixture state dirs and counting stub
`gh` binaries; the suite never touches real GitHub. It covers the
coalescing watcher (including SIGKILL takeover, fencing, and the
interval floor), the ledger core (caps, rolling windows, seeding,
atomic multi-bucket reservation, redaction, reaping), the gated
pass-through (denial, bypass, fail-open, settle-failure), status
and drift, and the Task 5 fleet drill (12 watchers + 30 mixed
calls against the assembled system, the shim fallback on a broken
`ghg.py`, and the < 300 ms median gate-overhead measurement).
