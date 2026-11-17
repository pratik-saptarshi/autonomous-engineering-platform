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
- `mask` covers three patterns; `GITHUB_TOKEN=`, `AWS_SECRET_ACCESS_KEY=`, `client_secret=`, `secretKey=`, `dbPassword=` and `--password x` shapes are among those that pass through. The translator adds one bounded, case-insensitive rule — `CREDENTIAL` in `redactSecrets` (`tools/harness-profile/translate.js`) — and the pin's `mask` then runs on the translated text. The rule matches a key name **containing** `SECRET`, `TOKEN`, `PASSWORD`, `PASSWD`, `CREDENTIAL`, `ACCESS_KEY` or `API_KEY`/`APIKEY`, at the start, middle or end of the name and in any case, before `:`/`=` (`GITHUB_TOKEN=`, `AWS_SECRET_ACCESS_KEY=`, `client_secret=`, `secretKey=`, `awsSecretAccessKey=`, `credential=`, `access_key=`) or, for a flag, followed by whitespace (`--password x`). It keeps the key name and its separator and replaces only the value; a value written as a quoted string (either quote) is replaced whole with the quote character kept, so `GITHUB_TOKEN="a b"` loses both words and a serialized `tool_input` keeps its JSON shape. Containment (rather than a suffix or an uppercase env shape) is what restores the mixed-case coverage the three-rule version lost.
- The keys a profiler exists to report are spared by a callback skip, not by lookarounds: a match whose captured name satisfies `/^(?:(?:input|output|total|num|max|prompt|completion)_?tokens?|tokenizer)$/i` is returned unchanged, so `input_tokens=`, `output_tokens=`, `total_tokens=`, `max_tokens=` and `tokenizer=` survive while `secretKey=` does not. The skip is a whole-name test, so any *other* name containing `TOKEN` is still redacted, and these over-redactions are accepted fail-closed by design: `tokens_per_sec=12` loses its value, so do `cache_read_tokens=2048` and `cache_write_tokens=512`, and a JSON `{"token":"<id>"}` loses the id. `INPUT_TOKENS=` is spared too — the skip is case-insensitive. Both name runs are bounded (`{0,64}`) and the separator (`[ \t]*`) and every value alternative (`[^"\n]*`, `[^'\n]*`, `[^\s"'&,}]+`) are single-character-class repeats, so the whole pattern is linear: an unbounded name run on both sides of the alternation backtracks cubically on one long token blob with no separator — 8 KB of repeated `TOKEN` took 14.4 s, and this rule runs inside a capture hook — against ~0.01 ms bounded. The translator's fixtures plant deliberately inert short values (`GITHUB_TOKEN=x1`, `secretKey=abc`, `Authorization: Bearer fakebear`) so they exercise the rule without tripping the `security` job's gitleaks scan — no allowlist entry covers our own fixtures.
- The renderer derives spend from `context_tokens`, `child_spend` / `SubagentStop.spend`, **and** — when a record names a transcript file — the transcript read through `spentTokens` (`hp.js:318-332`). A translator that omits the fields *and* the transcript path renders empty cost columns; the three sources are not interchangeable.

## Operator doc

Enable, disable, trace location, retention, and the masking caveat are documented for operators in the [harness-profiler operator guide](harness-profiler.md), added in Phase D of the adoption plan (`docs/superpowers/plans/2026-11-17-harness-profiler-adoption.md`). This page is the pinned-snapshot reference; that page is how to run it.
