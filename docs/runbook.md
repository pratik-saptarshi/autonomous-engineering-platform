# Runbook — reproducing the environment

Exact steps to rebuild this platform on a fresh persistent Linux VM (x86_64). Prerequisites: `python3`, `node` 20+, `git`, `curl`, network egress. All paths are under `$HOME`, which must persist across restarts.

## 1. Binary tools

```bash
mkdir -p ~/workspace/bin
echo 'export PATH="$HOME/workspace/bin:$PATH"' >> ~/.bashrc
```

### beads (issue tracker)

```bash
cd /tmp
curl -sL -o beads.tar.gz https://github.com/gastownhall/beads/releases/download/v1.3.1/beads_1.3.1_linux_amd64.tar.gz
curl -sL -o checksums.txt https://github.com/gastownhall/beads/releases/download/v1.3.1/checksums.txt
grep linux_amd64 checksums.txt | sha256sum -c -
tar xzf beads.tar.gz bd && install -m 755 bd ~/workspace/bin/bd
bd --version   # bd version 1.3.1
```

Verify: `bd ping` returns ok; `bd init` in a scratch git repo, then create/show/close one issue.

### open-code-review (diff review)

Fetch the platform package `@alibaba-group/ocr-linux-x64` (v1.13.1) from npm, extract `package/bin/opencodereview`, and link it:

```bash
ln -s ~/workspace/open-code-review/package/bin/opencodereview ~/workspace/bin/ocr
ocr --version  # open-code-review v1.13.1
```

Verify (no API key needed): in a scratch git repo, `ocr delegate preview --format json` and `ocr delegate rule --format json <files>` return review specs.

### NeuroStrata engine (memory backend)

```bash
mkdir -p ~/workspace/neurostrata/bin
cd /tmp
# neurostrata-mcp-linux-amd64.tar.gz from the v1.9.0 release; verify SHA256
tar xzf neurostrata-mcp-linux-amd64.tar.gz -C ~/workspace/neurostrata/bin
~/workspace/neurostrata/bin/neurostrata-mcp --version  # neurostrata-mcp 1.9.0
```

## 2. Embedding model cache (proxy workaround)

Skip this section unless outbound TLS is intercepted by a proxy the binary does not trust. The binary (rustls/webpki via fastembed 7.0.1 + hf-hub 0.5.0) checks its local cache before any network call, so pre-seeding the exact hf-hub layout avoids the download entirely.

Needed files from `nomic-ai/nomic-embed-text-v1.5` at commit `e9b6763023c676ca8431644204f50c2b100d9aab`:
`tokenizer.json`, `config.json`, `special_tokens_map.json`, `tokenizer_config.json`, `onnx/model.onnx`.

```bash
SHA=e9b6763023c676ca8431644204f50c2b100d9aab
BASE=~/.cache/neuro/models/fastembed/models--nomic-ai--nomic-embed-text-v1.5
mkdir -p "$BASE/refs" "$BASE/snapshots/$SHA/onnx"
echo -n "$SHA" > "$BASE/refs/main"
cd "$BASE/snapshots/$SHA"
for f in tokenizer.json config.json special_tokens_map.json tokenizer_config.json onnx/model.onnx; do
  curl -sL --retry 2 -o "$f" "https://huggingface.co/nomic-ai/nomic-embed-text-v1.5/resolve/main/$f"
done
# expect: 5 files, model.onnx ~522 MB
```

## 3. Start the daemon

```bash
nohup ~/workspace/neurostrata/bin/neurostrata-mcp daemon > ~/workspace/neurostrata/daemon.log 2>&1 &
sleep 15
~/workspace/neurostrata/bin/neurostrata-mcp status
# expect: "status: healthy -- one daemon is serving every console"
```

The daemon log must show the embedder initializing from cache with no download attempt. The store is created at `~/.config/NeuroStrata/data/db/ladybug.db`.

Note: the binary ships systemd user units, but they cannot be enabled where no user D-Bus exists. `nohup` is the supported fallback; any MCP spawn restarts a dead daemon automatically.

## 4. MCP client and connector registration

The server speaks MCP over stdio (protocol version `2024-11-05`). Write a minimal JSON-RPC client with `list-tools` and `call-tool --name --arguments-file` commands. Two protocol quirks to handle:

- After `notifications/initialized`, the server emits a bare `{}` line on stdout. Tolerate non-JSON-RPC lines instead of failing.
- Maintain an `ALLOWED_TOOLS` allowlist, populated only with tool names reviewed from `list-tools` output. Suggested initial set: `neurostrata_add_memory`, `neurostrata_get_memory`, `neurostrata_search_memory`, `neurostrata_list_namespaces`, `neurostrata_get_snapshot`, `neurostrata_supersede_memory`, `neurostrata_archive_memory`, `neurostrata_append_log`.

Verify end to end:

```bash
client.py list-tools
# add a test memory
client.py call-tool --name neurostrata_add_memory --arguments-file add.json
# search it back (exercises the embedding model)
client.py call-tool --name neurostrata_search_memory --arguments-file search.json
# fetch by id, then archive the test record
```

`add_memory` requires `content`, `namespace`, `project_root`. Set `create_new_namespace: true` only for a genuinely new namespace.

## 5. Skill library

Install each skill as `~/workspace/custom-skills/<name>/` containing `SKILL.md` and `skill.yaml`. Adapt upstream repos to local conventions; skip harness-specific plugins, anything needing unavailable credentials, and anything that duplicates an existing skill. Record the source of each skill. The inventory in the README lists all 29 skills and their 11 upstream sources.

Two local integrations to apply after install:

- `ralph_loop/SKILL.md`: before spawning the worker, search the memory backend for relevant past learnings and include the top hits in the brief; after each iteration, inscribe durable outcomes via `neurostrata_add_memory` (`global` namespace for broadly-applicable lessons, project namespaces otherwise).
- `systematic-debugging/SKILL.md`: after a verified fix, inscribe root causes that teach beyond the session as rules.

## 6. Ralph loop and scheduler

```bash
mkdir -p ~/workspace/ralph/bin
```

- `backlog.md`: tasks as H2 sections with an ID prefix; metadata (`status`, `labels`, `priority`, `depends-on`) in HTML comments under the heading. Statuses: `to-do`, `in-progress`, `in-review`, `done`.
- `bin/backlog.py`: `list` and `next` commands (next = highest-priority unblocked to-do task, as JSON).
- Schedule: one job, id `ralph-loop`, interval 2 h, timeout 7200 s. Body instructs the worker to read the skill, run at most 6 iterations, stop on stall or triple failure, report only when work was done or attention is needed, and write observations to the daily log (never `MEMORY.md`).

## 7. open-connector gateway (optional)

```bash
cd ~/workspace/open-connector && npm install   # 536 packages; generates the catalog
```

Start on demand (`start.sh`, ~20 s), discover actions (`oc.py list <service>` / `oc.py doc <action.id>`), execute (`oc.py run <action.id> '<json>'`), stop with `stop.sh`. If provider calls fail on egress, allowlist the host via `OOMOL_CONNECT_EGRESS_TRUSTED_HOSTS`.

## 8. Verification checklist

- [ ] `bd ping` ok; issue lifecycle (create/show/close) works; per-repo isolation confirmed
- [ ] `ocr delegate preview` returns a review spec with no API key
- [ ] `neurostrata-mcp status` healthy; MCP store/search/fetch/archive round-trip passes
- [ ] `backlog.py next` returns the expected task as JSON
- [ ] Scheduler shows the `ralph-loop` job with a next run time
- [ ] A scheduled run with an empty backlog ends quietly; a run with tasks reports a summary
