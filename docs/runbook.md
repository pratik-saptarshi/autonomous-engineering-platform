# Runbook — reproducing the environment

Exact steps to rebuild this platform on a fresh persistent Linux VM (x86_64). Prerequisites: `python3`, `node` 20+, `git`, `curl`, network egress. All paths are under `$HOME`, which must persist across restarts.

## 1. Binary tools

```bash
mkdir -p ~/workspace/bin
echo 'export PATH="$HOME/workspace/bin:$PATH"' >> ~/.bashrc
```

### beads (issue tracker)

`bd` collects anonymous usage metrics **on by default**, and events are captured from the very first command — so the opt-out config must exist *before* `bd` is ever invoked, including the version check right after install. Pre-seed it with exactly the block `bd metrics off` writes (this config location is bd v1.3.1 behavior; a future version may move it):

```bash
mkdir -p ~/.config/bd
cat > ~/.config/bd/config.yaml <<'EOF'
metrics:
    disabled: true
    endpoint: https://gastownhall-eventsapi.com/mp/collect
    notice_shown: true
EOF
```

```bash
cd /tmp
curl -sL -o beads.tar.gz https://github.com/gastownhall/beads/releases/download/v1.3.1/beads_1.3.1_linux_amd64.tar.gz
curl -sL -o checksums.txt https://github.com/gastownhall/beads/releases/download/v1.3.1/checksums.txt
grep linux_amd64 checksums.txt | sha256sum -c -
tar xzf beads.tar.gz bd && install -m 755 bd ~/workspace/bin/bd
bd --version   # bd version 1.3.1
```

Belt and braces: run `bd metrics off` explicitly — it is idempotent, and it covers environments where the pre-seed path differed; the expected status output shows metrics OFF:

```bash
bd metrics off
bd metrics   # expect: "Anonymous usage metrics: OFF"
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

### OpenChamber (optional OpenCode workspace)

OpenChamber is a multi-surface workspace (web/PWA, desktop, VS Code, mobile) layered over OpenCode — a UI and session manager, not a runtime. Here it runs in external-attach mode against the existing OpenCode background service instead of spawning its own server. Optional; skip unless you want a browser workspace over the local OpenCode sessions.

**Prerequisites**

- **OpenCode already installed and set up** — the binary is at `~/.opencode/bin/opencode`, version >= 2.2.4 (v2.3.0 verified). This section attaches to an existing install; it does not install OpenCode.
- **A connected provider** — at least one provider is authenticated in OpenCode (here: OpenCode Go, connected via `opencode auth login`). Without a provider, the workspace opens but sessions cannot run a model. Provider credentials are operator-supplied and never live in this repo.
- **The OpenCode background service configured** — its state is at `~/.local/state/opencode/service.json`; OpenChamber does not read a password from that file (its auth is covered in the launch note below). The service does not survive VM restarts; wake it before launching, as described in the launch note below.
- **Node.js and Bun on PATH** — the CLI launches under Node (v24 verified), and the daemon runs under Bun (1.4 verified). Both ship in the Muse VM image; on any other machine, install Node >= 20 and Bun first.
- **Network access to the npm registry** for the install step below. The vendored snapshot under `reference/openchamber/` is a source reference, NOT an install path: running from it would require a Bun dependency install and build (not documented here), and it deliberately omits one credential-bearing file (see its `PROVENANCE.md` for the declared exclusion and local-regeneration instructions).
- **Your own UI password** — set `OPENCHAMBER_UI_PASSWORD` to an operator-chosen value and store it locally in a chmod-600 file; never commit it.

Install the published npm package `@openchamber/web` (prebuilt; no monorepo build) into a local app dir:

```bash
mkdir -p ~/workspace/openchamber/app && cd ~/workspace/openchamber/app
npm install @openchamber/web@2.7.3
```

The background service must be up first: it does not survive VM restarts, and any `opencode api` call wakes it (e.g. `opencode api GET /api/session`). Launch in attach mode, bound to localhost only:

```bash
cd ~/workspace/openchamber/app
export OPENCODE_HOST=http://127.0.0.1:49374            # the background service
export OPENCODE_SKIP_START=true                        # attach; never spawn a second server
export OPENCODE_BINARY="$HOME/.opencode/bin/opencode"  # required even with SKIP_START; launch exits without it
export OPENCHAMBER_UI_PASSWORD='<set your own>'        # keep it in a chmod-600 file; never commit it
unset OPENCODE_PASSWORD  # when both are set, OpenChamber prefers OPENCODE_PASSWORD over OPENCODE_SERVER_PASSWORD
# The background service is password-protected, and OpenChamber's probes
# authenticate only from its own process environment. Read the password
# from the service state file at launch; never print, log, or commit it.
set +x  # while the password is loaded: a traced (set -x) export would print its value
OPENCODE_SERVER_PASSWORD="$(python3 -c 'import json,os; print(json.load(open(os.path.expanduser("~/.local/state/opencode/service.json")))["password"])')"
export OPENCODE_SERVER_PASSWORD
test -n "$OPENCODE_SERVER_PASSWORD" || echo "error: could not load the OpenCode service password from ~/.local/state/opencode/service.json — not launching" >&2
test -n "$OPENCODE_SERVER_PASSWORD" && node node_modules/@openchamber/web/build/bin/cli.js serve --hostname 127.0.0.1 --port 3411
```

OpenChamber does not read the service password from `~/.local/state/opencode/service.json` — in the vendored OpenChamber 2.7.3 code, no code path reads a password from that file (in the local file it sits as a top-level field), and the file's env map (variables set via `opencode service set env`) does not carry it. OpenChamber's auth initializes from its own process environment when set, preferring `OPENCODE_PASSWORD` over `OPENCODE_SERVER_PASSWORD` when both are present — the launch block therefore unsets `OPENCODE_PASSWORD`, so the service password is the credential used; its managed local OpenCode instance generates its own password. Against a password-protected background service, the documented launch MUST export the service's password as `OPENCODE_SERVER_PASSWORD`, read from `~/.local/state/opencode/service.json` at launch time as shown in the launch block: without it, OpenChamber's readiness and event probes receive 401s and health reports `openCodeRunning: false` even though the service is up (verified 2026-11-23). The exported password is a launch-time snapshot — OpenChamber reads it once at startup. A plain service restart does not change it (the service persists its password in `service.json`), but if the service password is ever regenerated, relaunch OpenChamber: until then its probes receive 401s and health again reports `openCodeRunning: false`. The password value is never printed, logged, or committed. Pairing: OpenCode >= 2.2.4 required, upstream tests against 2.3.2; v2.3.0 verified attached with no warnings (2026-11-19); v2.4.0 verified attached with no warnings (2026-11-23); v2.4.1 verified attached with no warnings (2026-11-23).

Security: a signed-in OpenChamber session is effectively full machine access (upstream's own threat model). Bind to 127.0.0.1 only; reach it remotely via tailnet or its built-in E2EE relay — never port-forward it.

Verify attach — the session list in the UI must show the service's existing sessions, proving attach rather than a fresh instance:

```bash
curl -s http://127.0.0.1:3411/health   # expect "openCodeRunning":true, "openCodePort":49374
```

Stop (OpenChamber only, not the OpenCode service) and relaunch by repeating the launch block:

```bash
cd ~/workspace/openchamber/app
node node_modules/@openchamber/web/build/bin/cli.js stop -p 3411
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

Note: the binary ships systemd user units, but they cannot be enabled where no user D-Bus exists. `nohup` is the supported fallback; a dead daemon does *not* reliably come back via MCP spawn (verified 2026-10-16) — restart it directly or wait for the watchdog cron.

**Daemon forking behavior.** The binary forks on startup: briefly after launch, `pgrep -f 'neurostrata-mcp daemon'` returns two PIDs (the forking parent plus the live daemon). Any stop logic must signal *all* matching PIDs, not just the first — `pgrep ... | head -1` can pick the stale parent, leaving the live daemon running until the stop times out (observed 2026-10-17: `ERROR: daemon did not exit in 30s`, backup skipped, unclean-shutdown WAL warning on next start). Use the `[n]` bracket trick (`pgrep -f '[n]eurostrata-mcp daemon'`) so pgrep never matches its own command line, and loop `kill -TERM` over every returned PID. `scripts/watchdog-backup.sh` implements this.

### Seed the guard namespace

`scripts/boot-gate.sh` check 3 (guards) needs at least three `guard_rule` memories in the `guard` namespace, and one of them must contain "Destructive GitHub actions". On a fresh VM the namespace is empty and the gate fails closed with `BOOT-GATE: guards FAIL`. Seed it once the daemon is healthy:

```bash
scripts/seed-boot-guards.sh --dry-run   # report what would be seeded, write nothing
scripts/seed-boot-guards.sh             # seed every canonical rule that is absent
scripts/seed-boot-guards.sh --check     # same test as boot-gate check 3, write nothing
```

The script is idempotent. It matches each canonical rule by a short key phrase, so a rule worded differently on an older host still counts and is never duplicated, and a second run changes nothing. It fails loudly (exit 1) when `neurostrata-mcp` is missing or the daemon is not answering, and it never starts the daemon.

It seeds three rules. The first is universal: destructive GitHub actions (branch deletion, force-push, history rewrite, repository deletion) each need the user's explicit per-action authorization. The second and third are specific to the document-accessibility-pipeline repo (no push without authorization, and the PR merge rule). If you replace the repo-specific rules, keep at least three `guard_rule` memories in the namespace.

Verify the result with the gate itself:

```bash
neurostrata-mcp list guard      # expect: Found 3 memories (or more)
scripts/boot-gate.sh            # expect: BOOT-GATE: guards ok
```

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

Install each skill as `~/workspace/custom-skills/<name>/` containing `SKILL.md` and `skill.yaml`. Adapt upstream repos to local conventions; skip harness-specific plugins, anything needing unavailable credentials, and anything that duplicates an existing skill. Record the source of each skill. The inventory in the README lists all 58 skills and their 12 upstream sources.

Two local integrations to apply after install:

- `ralph_loop/SKILL.md`: before spawning the worker, search the memory backend for relevant past learnings and include the top hits in the brief; after each iteration, record durable outcomes in the loop's `learnings.md` only — promotion to NeuroStrata happens only as a curator proposal the owner approves, carried out outside the loop, never as a direct write by a loop role.
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

## 8. Egress domain blocks

Some provider domains (`dolthub.com`, `gastownhall-eventsapi.com`) are bypassed from the egress proxy through `NO_PROXY` in `/etc/environment` and then dropped at the firewall. Apply the drops after every boot and after any VM replacement, because iptables rules do not survive either:

```bash
sudo scripts/apply-domain-blocks.sh
```

The script needs root. It exits non-zero with a `FATAL:` line when it is not root, when `iptables` or `getent` is missing, or when a domain resolves to no address, and in each of those cases it changes nothing. It resolves the addresses at apply time with `getent ahostsv4` and `getent ahostsv6`, so no address is hardcoded. When the host has an IPv6 default route or a domain publishes an AAAA record, it also writes `ip6tables` rules, and a missing `ip6tables` is a hard failure. It re-checks every rule with `-C` before it prints `Domain blocks applied and verified: ...`, so that line means the rules exist.

The rules are only as current as the DNS answer at the moment of the run. Re-run the script after a DNS rotation, for example from a daily cron entry owned by root. Rules for addresses that have rotated away stay in place and are harmless. To block other domains, set `AEP_BLOCK_DOMAINS` to a space-separated list.

Verify:

```bash
sudo iptables -S OUTPUT | grep DROP    # one DROP rule per resolved IPv4 address
sudo ip6tables -S OUTPUT | grep DROP   # present when IPv6 is active
```

## 9. Verification checklist

- [ ] `bd ping` ok; issue lifecycle (create/show/close) works; per-repo isolation confirmed
- [ ] `bd` metrics OFF, proven by BOTH signals: `bd metrics` reports OFF, **and** `~/.config/bd/config.yaml` carries `disabled: true` under `metrics:` — assert with `grep -A2 '^metrics:' ~/.config/bd/config.yaml | grep -q 'disabled: true'` (exits non-zero when the flag is absent). If either check fails, setup has FAILED — stop and fix before continuing onboarding. A future bd version that moves the setting or changes the default must break setup visibly here, not silently phone home
- [ ] `ocr delegate preview` returns a review spec with no API key
- [ ] `neurostrata-mcp status` healthy; MCP store/search/fetch/archive round-trip passes
- [ ] `scripts/seed-boot-guards.sh --check` exits 0 and `scripts/boot-gate.sh` prints `BOOT-GATE: guards ok`
- [ ] `sudo scripts/apply-domain-blocks.sh` prints `Domain blocks applied and verified:` and `iptables -S OUTPUT` lists a DROP rule for each blocked domain
- [ ] `backlog.py next` returns the expected task as JSON
- [ ] Scheduler shows the `ralph-loop` job with a next run time
- [ ] Scheduler shows the `neurostrata-watchdog` job; a manual run backs up to Google Drive on DB change
- [ ] A scheduled run with an empty backlog ends quietly; a run with tasks reports a summary
- [ ] (Optional) OpenChamber: `curl -s http://127.0.0.1:3411/health` reports `"openCodeRunning":true` with `"openCodePort":49374`, and the UI session list shows the background service's existing sessions
