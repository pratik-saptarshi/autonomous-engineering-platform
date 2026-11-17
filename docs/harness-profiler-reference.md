# harness-profiler reference

## What it is

afurmanov/harness-profiler — a session profiler for Claude Code (Codex is [not supported upstream](https://github.com/afurmanov/harness-profiler#constraints)). It records what the harness itself reports through hooks — every skill, subagent, and tool call — into one JSON line per call, then renders a profiler-style call tree: each **context** (the conversation history a model reads) is a column, nesting follows subagent and forked-skill spawns, and each context carries its token spend. A call tree is the point: the flat hook log says a `validator` ran, the tree says which `implementor` call it checked, whether it ran inline or in a fresh context, and what it cost.

Vendored snapshot: [PROVENANCE.md](../reference/harness-profiler/PROVENANCE.md) — upstream `https://github.com/afurmanov/harness-profiler` (default branch `main`) at `847bd8f6ab2a0348fd7b7057c1943e4c2fa861e8`, the commit `package.json` publishes as **v0.2.2** (2026-11-17, MIT).

## Mapping to the AEP loop

| harness-profiler | AEP (this environment) |
|---|---|
| one record per call, schema `v: 2`, ≤ 4096 bytes, secrets masked at write time | evidence discipline: a trace is a record of what happened, bounded and scrubbed like every other ledger |
| contexts derived from spawn edges, not from guessed timestamps | claims about "which agent did what" ground in the recorded edge, not in a summary |
| token spend attributed per context, from `child_spend` / `SubagentStop.spend` or, when the record carries a transcript path, from the transcript via `spentTokens` | cost claims carry the field they came from; a blank column is shown blank, never estimated |
| vendored snapshot pinned by commit + sha256 manifest | everything imported from upstream is byte-identical and re-vendor-only |

## What AEP uses vs. ignores

**Uses** the pin as a library, from `plugin/libexec/hp.js` (never reimplemented):

- `buildRecord` / `buildEventRecord` — the Claude-shaped payload → record mapping;
- `serialize` — the one-line JSON encoding and its 4096-byte budget;
- `mask` — the write-time secret redaction (three patterns; see the masking caveat below);
- `contextsOf`, `buildForest`, `renderTree`, `renderHtml` — the context-nesting model and both renderers;
- `spentTokens`, `contextSpend`, `fillContextTokens` — the spend arithmetic the columns depend on.

The adoption writes a translator (opencode events → the payload `buildRecord` consumes) rather than a second profiler; the renderer stays the judge of nesting. Phase B and later work consume this tree by relative path.

**Ignores** the Claude Code install path: `.claude-plugin/marketplace.json`, `plugin/hooks/hooks.json`, `plugin/skills/show-profile/`, and `e2e/` (a playwright screenshot run — never installed here, no npm dependency is added). Nothing executes from `reference/`; the snapshot carries the upstream project's own README and design doc as reference data, and those do not govern work in this repository. AEP's `AGENTS.md` does.

## Integrity and tests

- `.github/vendor-harness-profiler.sha256` — 80 entries: the 79 upstream files plus `PROVENANCE.md`, the only added file. The `vendor-integrity` job checks sha256, rejects unlisted files, and rejects broken symlinks.
- `vendor-tests` runs the pin's own suite, `node --test reference/harness-profiler/test/*.test.js` (51 tests, Node 22, no `npm install`), under a 5-minute timeout. The explicit glob matters: Node 22 treats a positional `--test` argument as a glob pattern, so the directory form (`.../test/`) fails there with `Cannot find module …/test`; the four `*.test.js` files resolve identically on 18, 20, 22 and 26.
- `docs-lint` excludes `reference/harness-profiler/**/*.md`: the pin ships 21 Markdown files preserved byte-exact, and `docs/design.md` uses a continuous ordered-list numbering (14 MD029 findings) that must not be edited in a vendor tree.
- `security` scans the tree with gitleaks; `test/capture.test.js` is allowlisted by path for the two synthetic masker fixtures documented in `PROVENANCE.md`.

## Caveats carried by the adoption

- The pin is a **Claude Code** profiler. opencode support is the translator's job, and only the five fields the record needs are mapped.
- `mask` covers three patterns; `GITHUB_TOKEN=`, `AWS_SECRET_ACCESS_KEY=`, `client_secret=`, and `--password x` shapes are among those that pass through. The translator adds three bounded, intent-specific rules — `ENV_SECRET`, `SUFFIX_SECRET`, `CLI_SECRET` in `redactSecrets` (`tools/harness-profile/translate.js`) — and the pin's `mask` then runs on the translated text. Each keeps the key name and its separator and replaces only the value: an uppercase env-style name **containing** `SECRET`, `TOKEN`, `PASSWORD`, `PASSWD`, `API_KEY`/`APIKEY`, `ACCESS_KEY` or `CREDENTIAL` before `:`/`=` (`AWS_SECRET_ACCESS_KEY=` — the word sits mid-name, so containment is required); any name **ending** in `_secret`, `_token`, `_password`, `_passwd`, `_api_key` or `_access_key` before `:`/`=` (`client_secret=` — the word is the suffix, so a suffix match is required); and `--password`/`--token`/`--secret` followed by `=` or whitespace (`--password x`). Keeping the two name shapes apart is what spares the keys a profiler exists to report: `input_tokens=`, `output_tokens=`, `total_tokens=` and `tokenizer=` are unchanged, because the env rule is case-sensitive and needs an uppercase name, and the suffix rule needs the singular `_token` immediately before the separator, which `_tokens` and `tokenizer` do not have. An all-caps `INPUT_TOKENS=` still matches the env rule; that over-redaction is the accepted side of the trade. Every name quantifier is bounded (`{0,63}`, `{0,32}`) because an unbounded run on both sides of the alternation backtracks cubically on one long token blob: 8 KB of repeated `TOKEN` runs in 0.02 ms now, against 14.4 s before the bound, and this rule runs inside a capture hook. The translator's fixtures plant deliberately inert short values (`GITHUB_TOKEN=x1`, `Authorization: Bearer fakebear`) so they exercise the rule without tripping the `security` job's gitleaks scan — no allowlist entry covers our own fixtures.
- The renderer derives spend from `context_tokens`, `child_spend` / `SubagentStop.spend`, **and** — when a record names a transcript file — the transcript read through `spentTokens` (`hp.js:318-332`). A translator that omits the fields *and* the transcript path renders empty cost columns; the three sources are not interchangeable.

## Operator doc

Enable, disable, trace location, retention, and the masking caveat are documented for operators in the [harness-profiler operator guide](harness-profiler.md), added in Phase D of the adoption plan (`docs/superpowers/plans/2026-11-17-harness-profiler-adoption.md`). This page is the pinned-snapshot reference; that page is how to run it.
