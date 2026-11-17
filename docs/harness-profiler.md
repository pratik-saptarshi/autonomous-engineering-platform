# harness-profiler operator guide

How to turn on the opencode session profiler, find its traces, render them, and
diagnose a capture that wrote nothing. This is the operator page; the pinned
snapshot, its provenance, and the masking implementation are documented in the
[harness-profiler reference](harness-profiler-reference.md).

## Scope: development host only

The profiler is a **development-host** tool. It needs three things that the
shipped image does not have:

- Node 18+ in the process that runs the capture;
- the vendored `reference/harness-profiler/` tree (the renderer and the record
  library are read from it, never reimplemented);
- the `.opencode/plugins/harness-profile.js` plugin loaded by opencode.

The image ships no Node and no `reference/` tree, so neither capture nor
rendering works there. Do not add the profiler to a deployment; it is not part
of the runtime contract.

## How capture is wired

- `.opencode/plugins/harness-profile.js` is the opencode 2.3 entry point. It is
  thin: it subscribes once, forwards every event to
  `tools/harness-profile/handle.js`, and disposes the subscription.
- `tools/harness-profile/translate.js` maps the opencode event shapes to the
  payload the vendored record builder consumes; the pin decides nesting and
  spend.
- `reference/harness-profiler/plugin/libexec/hp.js` is the renderer. It is
  invoked as `node …/hp.js tree …`; nothing executes from the reference tree
  during capture.

The long-lived `opencode serve` process loads `.opencode/plugins/harness-profile.js`
from this checkout, so there is no plugin install step. The environment is
different: see the next section.

## Enable

Capture is **opt-in and inert by default**. Every event returns immediately when
`AEP_HARNESS_PROFILE` is unset, empty, `0`, `false`, `off`, or `no`.

To enable it:

1. Put `AEP_HARNESS_PROFILE=1` in the environment of the **service** that runs
   `opencode serve` — the unit, supervisor, or shell that owns that process.
2. Start the service, or restart it if it is already running, so the process
   inherits the variable.
3. Run a session in this repository. Traces appear after the first event.

A shell export in your interactive terminal does **not** reach an already
running `opencode serve`: that process captured its environment when it
started. The plugin is loaded from this checkout without an install step; a
process's environment is fixed at start. Restarting the service is an operator
action; do it deliberately, outside this repository's tooling.

## Disable

Unset `AEP_HARNESS_PROFILE` (or set it to `0`) in the service environment and
restart the service. Existing traces stay on disk until retention prunes them;
disabling capture never deletes the trace directory.

## Trace location and file shape

With no override, traces go to `<git-root>/.harness-profile/`, where the git
root is found by walking up from the session's working directory:

- `ses_<rootSessionId>.jsonl` — one JSON record per line, mode `0600`, one file
  per root session;
- `ses_<rootSessionId>.parentage.json` — a debug sidecar, written only when
  `AEP_HARNESS_PROFILE_DEBUG` is truthy.

Set `AEP_HARNESS_PROFILE_DIR` to send traces to an explicit directory instead
(relative values resolve against the session's working directory). The override
wins even outside a git repository, which is the escape hatch for ad-hoc
capture. A destination whose **final path** (symlinks resolved) is inside a git
work tree is accepted only when that repository's root `.gitignore` or the
common `info/exclude` names it; otherwise the trace would show up in
`git status`, so capture refuses it (see
[refusals](#when-capture-writes-nothing-refusals-are-logged)). A symlink is
judged by its target: a link outside the repository that points into it is
refused, and a link whose target is outside captures there. The directory is
created if needed; records are appended one complete line at a time.

The trace directory is excluded from git through the repository's own
`.git/info/exclude`. The entry is written on the first event and read back from
disk before any record is written. A committed `.gitignore` entry is the second
layer but is not substituted for the runtime check. In this checkout both layers
exist, and `git check-ignore -v` names the committed `.gitignore` (a
per-directory file outranks `info/exclude`); that is correct, not a fault. The
next section shows how to read the attribution.

## Retention

The first event of each long-lived process bounds the trace directory:

- files older than **14 days** (by modification time) are removed;
- the directory is held to **32 MiB** by deleting the oldest files first.

Only this handler's own `ses_*.jsonl` and `ses_*.parentage.json` files are
counted or removed. A shared explicit directory keeps everything else.

| Variable | Default | Effect |
|---|---|---|
| `AEP_HARNESS_PROFILE_RETENTION_DAYS` | `14` | age bound in days; `0` disables it |
| `AEP_HARNESS_PROFILE_MAX_BYTES` | `33554432` (32 MiB) | byte ceiling; `0` disables it |

An invalid value falls back to the default. Pruning runs once per process, so
growth is bounded across process starts rather than continuously inside one
long-running service.

**Pruning is destructive and this is the only retention boundary.** A trace that
passes either bound is deleted, not archived, and cannot be recovered from the
profiler afterwards. `0` disables that bound rather than emptying the directory:
`AEP_HARNESS_PROFILE_RETENTION_DAYS=0` leaves age alone, and
`AEP_HARNESS_PROFILE_MAX_BYTES=0` leaves size alone — setting both to `0` means
the directory grows without limit until an operator removes files. Disabling
capture deletes nothing.

## Render a trace

Use the wrapper rather than calling the vendored file by hand:

```bash
bash scripts/profile-tree.sh tree
bash scripts/profile-tree.sh tree --verbose
bash scripts/profile-tree.sh tree --branch docs/harness-profiler-adoption
bash scripts/profile-tree.sh tree --format html > /tmp/profile.html
```

The wrapper walks up from its own directory (not your current directory) until
it finds `reference/harness-profiler/plugin/libexec/hp.js`, then runs that
renderer from the repository root. It works from `scripts/` or any directory in
a source checkout, and it never copies or reimplements the renderer. `--help`
prints the same contract.

`node 18+ required for profiling; install Node or skip` is the wrapper's
message when no `node` is on `PATH`; it exits non-zero instead of printing a
shell traceback. `--help` does not need Node.

The wrapper sets `CLAUDE_PROJECT_DIR` to the repository it discovered on the
default path, so a value inherited from another checkout cannot silently
redirect the read to a different project's traces. An
explicit `AEP_HARNESS_PROFILE_DIR` is renderable only when its final path is a
`.harness-profile` directory **outside any git work tree**. A destination
inside one is rejected by the wrapper with the reason and both remedies —
without that guard the renderer silently reads the repository root's own
`.harness-profile` instead, reporting "No traces" or rendering the wrong
directory. A destination with another name is likewise rejected rather than
silently rendering a different directory.

## When capture writes nothing: refusals are logged

Capture **fails closed**. It writes no record, and never fails the session,
when the trace cannot be shown to be excluded from git:

- no git repository above the session's working directory, with
  `AEP_HARNESS_PROFILE_DIR` unset;
- a `.git` that does not resolve to a real git directory (a malformed pointer,
  a missing target);
- an `info/exclude` that cannot be written or read back (for example
  `EACCES`/`EPERM`, or a redirected path);
- an explicit `AEP_HARNESS_PROFILE_DIR` whose final path (symlinks resolved)
  lies inside a git work tree but is named by neither that repository's root
  `.gitignore` nor its common `info/exclude` — the trace would be committable
  there;
- an explicit `AEP_HARNESS_PROFILE_DIR` that cannot be resolved to a real path
  at all (a symlink loop, an unreadable component), since capture cannot then
  prove which side of the work tree it is on;
- a destination with a nested `.gitignore` anywhere above it, because a nested
  rule can negate the root rule and this guard does not evaluate precedence;
- a default `.harness-profile` that is a symlink whose resolved target is inside
  the work tree and not ignored (the link's name is not what git sees).

## Memory in a long-lived service

Capture holds only what an unfinished call needs. Once a call's records are
written, its input and its step's tokens are released, and completed sessions
are evicted least-recently-active first beyond 200 retained trees. Eviction is
safe because a resumed session reseeds its cumulative spend from the trace on
disk; a session with a pending step or an open spawn is never evicted.

## Service restart and cumulative spend

A restarted `opencode serve` starts a fresh process against an existing trace.
Before the first record of a session is built, capture restores that session's
cumulative spend from the trace already on disk (the newest few MiB), so the
next root stop is the running total rather than a per-process subtotal. Without
this the renderer would keep only the latest stop and silently drop everything
captured before the restart.

On the first refused event, the handler records the reason once, and the plugin
writes it once per process to the `opencode serve` log:

```text
[aep-harness-profile] trace capture skipped: <reason>, so the trace could not be excluded from git; set AEP_HARNESS_PROFILE_DIR to capture in an explicit directory
```

For the in-repository override the line names the directory and both remedies:

```text
[aep-harness-profile] trace capture skipped: AEP_HARNESS_PROFILE_DIR=<dir> is inside the git work tree at <root> but not ignored by <root>/.gitignore or <common>/info/exclude, so the trace would be committable; move the directory outside the repository, or add an ignore rule for it (for example `<relative>/` in .gitignore) and retry
```

That line is the operator surface. It appears in the service's stderr (the
service's own log destination — the unit, the pane, or the file that captures
its output), not in a CLI and not in the trace directory. A quiet absence of
`ses_*.jsonl` with no such line means either capture is disabled, or no event
has reached the handler yet.

To diagnose manually, from the session's working directory:

```bash
git rev-parse --show-toplevel          # is there a repository at all?
git rev-parse --git-common-dir        # worktrees share info/exclude here
git check-ignore -v .harness-profile/x
ls -ld "$(git rev-parse --git-common-dir)/info"
test -w "$(git rev-parse --git-common-dir)/info/exclude" && echo writable
```

`git check-ignore -v` naming `.gitignore:10:/.harness-profile/` in this
checkout is the expected answer, not a missing runtime entry. Two ignore layers
exist, and a per-directory `.gitignore` outranks `$GIT_DIR/info/exclude`, so
when both name the trace git reports the committed file. The handler's
`info/exclude` line is still written unconditionally and read back from disk
before the first record; E10 proves that attribution in a throwaway repository
whose `.gitignore` contains only `dist/`. The command confirms the trace is
ignored: the file it names tells you which layer answered, and either layer is
sufficient.

If the exclusion cannot be made to work, set `AEP_HARNESS_PROFILE_DIR` to a
directory you control, restart the service with it, and capture there. The
wrapper renders only a directory whose final path component is exactly
`.harness-profile` (`scripts/profile-tree.sh`), so name the destination that
way — for example `/Users/you/aep-profile/.harness-profile`; any other name
still captures, but `bash scripts/profile-tree.sh tree` refuses to render it. A
destination whose resolved path is inside the repository must also be named by
`.gitignore` or `info/exclude`, or capture refuses it. Do not work around the
refusal by pre-creating `.harness-profile/` in an unprotected tree: the next
`git add -A` would commit it.

The in-repository check asks **git itself** (`git check-ignore`) whether the
resolved destination is ignored, so nested `.gitignore` files, negations such
as `!trace[s]/`, character classes and global excludes are evaluated with git's
own precedence rather than a reimplementation. Any non-ignored answer, and any
failure to obtain one (including git being unavailable), refuses the
destination: capture never approves a path it cannot prove git ignores.

The remedy for both shapes is the same: prefer the default destination
(`<git-root>/.harness-profile/`, protected through `info/exclude`) or point
`AEP_HARNESS_PROFILE_DIR` at a directory outside the repository. The refusal
warning names the resolved path when it differs from the configured one, for
example `AEP_HARNESS_PROFILE_DIR=/tmp/link (resolves to /repo/traces)`, so a
symlinked destination is not mistaken for an out-of-repo one.

## Masking caveats

Records are masked at write time by the pin's `mask`, preceded by the
translator's bounded credential rule (`tools/harness-profile/translate.js`).
The rule covers key names containing `SECRET`, `TOKEN`, `PASSWORD`, `PASSWD`,
`CREDENTIAL`, `ACCESS_KEY`/`ACCESS-KEY`, `API_KEY`/`APIKEY`/`API-KEY` in any
case, in `KEY=value`, `KEY: value`, and `--flag value` shapes. It keeps the key
name and separator and replaces only the value. The same name rule is applied to
structured payloads: every object key is tested, so nested
`AWS_SECRET_ACCESS_KEY`, `NEUROSTRATA_API_KEY`, `dbPassword` and `client_secret`
keys each lose their whole value (`[redacted]`) — for example
`{"env":{"AWS_SECRET_ACCESS_KEY":"[redacted]"}}` — while a benign nested key
such as `{env:{input_tokens:5}}` survives. A credential key's value is replaced
without recursing into it, so an object-valued credential leaves no readable
body.

This is a redactor for the common shapes, **not a hardened secret scanner**.
Treat a trace as sensitive: tool arguments and results, paths, prompts, and
output fragments are recorded (clipped to the record budget).

**Accepted over-redactions** (fail-closed by design, not bugs):

- `tokens_per_sec=12` loses its value — the key contains `TOKEN`;
- `cache_read_tokens=2048` and `cache_write_tokens=512` lose their values, and
  the hyphenated `input-tokens=5` does too (the sparing rule is underscore-only);
- a JSON `{"token":"<id>"}` loses the id;
- an object value is clipped at its first `{` (`{"token":{"x":1}}` leaves the
  object body), because record fields are strings.

The profiler's own keys — `input_tokens=`, `output_tokens=`, `total_tokens=`,
`num_tokens=`, `max_tokens=`, `prompt_tokens=`, `completion_tokens=`,
`tokenizer=` — are spared by a whole-name skip, in the text rule and in the
object-key test alike. `INPUT_TOKENS=` is spared too; the skip is
case-insensitive.

See the [reference page](harness-profiler-reference.md#caveats-carried-by-the-adoption)
for the rule-level detail and the upstream pin's own three patterns.

## Non-goals

This adoption deliberately does **not** deliver:

- a cost-per-verified-task metric, or any join to `runs.jsonl`;
- a Codex adapter (upstream documents no skill call and no tool failures
  there);
- a Go `aep profile` subcommand (dropped: it cannot work in the shipped image,
  which has no Node and no `reference/` tree);
- an upstream pull request for opencode support;
- `.claude/` hooks, a plugin-marketplace install, or `npx` execution of the
  profiler.

The capture/render substrate is the deliverable. Promotion to production wiring
is a separate owner decision.
