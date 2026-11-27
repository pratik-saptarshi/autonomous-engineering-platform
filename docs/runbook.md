# Runbook: reproducing the environment

Exact steps to rebuild this platform on a fresh persistent Linux VM (x86_64). All paths are under `$HOME`, which must persist across restarts. Components that are designed but not built are collected in [Appendix: Planned / not yet implemented](#appendix-planned--not-yet-implemented) and are not part of the steps below.

Evidence labels used below: "checked 2026-11-25" means verified against the upstream project or in a clean x86_64 container while preparing this version. "VM record" means an earlier session recorded it from the VM and it was not re-verified here.

## Prerequisites

- `python3`, `node` 20+, `git`, `curl`, and network egress.
- The GitHub CLI (`gh`) installed and authenticated as the user that will run the jobs. `scripts/boot-gate.sh` check 4 runs `gh auth status`, so a fresh host cannot pass the gate without it. Section 1 installs and authenticates it.
- `gcc` and the ICU development headers (`libicu-dev` on Debian and Ubuntu), because `bd` is built with CGO and links ICU (section 1). Without the headers the build stops with `unicode/uregex.h: No such file or directory` (checked 2026-11-25).
- glibc 2.39 or newer (Ubuntu 24.04 or newer) to run `neurostrata-mcp`. On Debian 12 the v1.9.0 binary refuses to start with `GLIBC_2.38 not found` (checked 2026-11-25).
- The Go toolchain: Go 1.27.x under `~/sdk/go`. The VM runs go1.27.2 and CI pins 1.27.4. Section 1 installs it.
- `~/go/bin` on `PATH`. Every binary in this runbook installs there.
- `GOTMPDIR` set to a directory under `$HOME`. On the VM `/tmp` is a small tmpfs (512 MB, VM record), and a large `go install` can fail in the linker with "no space left on device" if it builds there. Section 1 sets it.

## 1. Binary tools

### Go toolchain and PATH

Install Go under `~/sdk/go`, put `~/sdk/go/bin` and `~/go/bin` on `PATH`, and point `GOTMPDIR` at a directory under `$HOME`:

```bash
mkdir -p ~/sdk ~/go/bin ~/.gotmp
cd /tmp
curl -fsSL -o go1.27.2.linux-amd64.tar.gz https://go.dev/dl/go1.27.2.linux-amd64.tar.gz
echo "ecbadb99091a3f46e31f5f934b068b1864eafa7995211b39eaddf76996045fe5  go1.27.2.linux-amd64.tar.gz" | sha256sum -c -
rm -rf ~/sdk/go && tar -C ~/sdk -xzf go1.27.2.linux-amd64.tar.gz
echo 'export PATH="$HOME/sdk/go/bin:$HOME/go/bin:$PATH"' >> ~/.bashrc
echo 'export GOTMPDIR="$HOME/.gotmp"' >> ~/.bashrc
export PATH="$HOME/sdk/go/bin:$HOME/go/bin:$PATH" GOTMPDIR="$HOME/.gotmp"
go version   # go version go1.27.2 linux/amd64
```

The checksum is the one go.dev lists for `go1.27.2.linux-amd64.tar.gz` (checked 2026-11-25). Any Go 1.27.x works. The VM runs go1.27.2 and CI pins 1.27.4.

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

`bd` installs from source into `~/go/bin`. The VM record of 2026-10-19 says this is how the VM's copy was built. It needs Go and `gcc` from the prerequisites. Keep the default CGO build: the upstream README's `CGO_ENABLED=0` recipe is reported to produce a broken embedded database (VM record, not re-tested here).

```bash
go install github.com/steveyegge/beads/cmd/bd@v1.3.1
bd --version   # bd version 1.3.1 (dev), the (dev) suffix is expected for a source build
```

Checked 2026-11-25: on arm64 (the x86_64 emulator crashed the Go runtime before the build finished, so x86_64 was not exercised) with Go 1.27.3 and `libicu-dev` installed, this command built `bd version 1.3.1 (dev)`, and `bd init`, `bd ping`, and `bd create` worked in a scratch repo.

The upstream repo moved from `steveyegge/beads` to `gastownhall/beads`, but the module path inside the v1.3.1 tag is still `github.com/steveyegge/beads`, so the command above is correct for that tag (checked against the tag's `go.mod` on 2026-11-25). Upstream also publishes a v1.3.1 release with a `linux_amd64` tarball and a `checksums.txt`. That is a pinned, checksum-verified alternative to the source build. The VM does not use it. The asset names were checked against the release on 2026-11-25:

```bash
cd /tmp
curl -fsSL -O https://github.com/gastownhall/beads/releases/download/v1.3.1/beads_1.3.1_linux_amd64.tar.gz
curl -fsSL -O https://github.com/gastownhall/beads/releases/download/v1.3.1/checksums.txt
grep beads_1.3.1_linux_amd64.tar.gz checksums.txt | sha256sum -c -
tar xzf beads_1.3.1_linux_amd64.tar.gz bd && install -m 755 bd ~/go/bin/bd
bd --version   # bd version 1.3.1 (<commit>)
```

Checked 2026-11-25: in an x86_64 Ubuntu 24.04 container the checksum passed and the extracted binary printed `bd version 1.3.1 (c1c4b642a)`. The tarball avoids the ICU build requirement. Its binary was only run for `--version` there.

Belt and braces: run `bd metrics off` explicitly — it is idempotent, and it covers environments where the pre-seed path differed; the expected status output shows metrics OFF:

```bash
bd metrics off
bd metrics   # expect: "Anonymous usage metrics: OFF"
```

Verify: `bd ping` returns ok; `bd init` in a scratch git repo, then create/show/close one issue.

### open-code-review (diff review)

`ocr` is a prebuilt Linux x86_64 binary (an ELF file), installed as a real file at `~/go/bin/ocr`. Do not symlink an npm package: the earlier npm-package recipe never matched what runs on the VM. The VM install of v1.13.1 is a VM record from 2026-10-16. The asset names below were checked against the upstream `alibaba/open-code-review` release list on 2026-11-25:

```bash
cd /tmp
curl -fsSL -O https://github.com/alibaba/open-code-review/releases/download/v1.13.1/opencodereview-linux-amd64
curl -fsSL -O https://github.com/alibaba/open-code-review/releases/download/v1.13.1/sha256sum.txt
grep opencodereview-linux-amd64 sha256sum.txt | sha256sum -c -
install -m 755 opencodereview-linux-amd64 ~/go/bin/ocr
ocr --version  # open-code-review v1.13.1 (<commit>) linux/amd64
```

Checked 2026-11-25: in an x86_64 container the checksum passed and `ocr --version` printed `open-code-review v1.13.1 (8eb8334) linux/amd64`. `file` reports a statically linked x86-64 ELF.

Verify (no API key needed): in a scratch git repo, `ocr delegate preview --format json` and `ocr delegate rule --format json <files>` return review specs.

### GitHub CLI (gh)

`gh` is required by `scripts/boot-gate.sh` (check 4) and by the review/issue workflows. Install it from the official GitHub apt repository, then authenticate the user that owns the checkout and will run scheduled jobs:

```bash
sudo mkdir -p -m 755 /etc/apt/keyrings
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
  | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg >/dev/null
sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
  | sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null
sudo apt update && sudo apt install -y gh
gh auth login          # device flow or a token; run as the job user, not root
gh auth status         # must exit 0; boot-gate check 4 runs exactly this
```

For a non-interactive host, set `GH_TOKEN` (a fine-grained token with the scopes the jobs need) in the job user's environment instead of `gh auth login`. `gh auth status` must pass for the same user the boot gate runs as; authenticating root does not help a job that runs as the operator.

### NeuroStrata engine (memory backend)

The v1.9.0 release tarball installs to `~/go/bin/neurostrata-mcp` (the VM install is a VM record from 2026-10-16 with a SHA-256 check). The binary sits at `dist/linux/neurostrata-mcp` inside the tarball (checked 2026-11-25). The data and log directory is `~/workspace/neurostrata`:

```bash
mkdir -p ~/workspace/neurostrata
cd /tmp
curl -fsSL -O https://github.com/Cognilogical/NeuroStrata/releases/download/v1.9.0/neurostrata-mcp-linux-amd64.tar.gz
curl -fsSL -O https://github.com/Cognilogical/NeuroStrata/releases/download/v1.9.0/SHA256SUMS
grep neurostrata-mcp-linux-amd64.tar.gz SHA256SUMS | sha256sum -c -
tar xzf neurostrata-mcp-linux-amd64.tar.gz dist/linux/neurostrata-mcp
install -m 755 dist/linux/neurostrata-mcp ~/go/bin/neurostrata-mcp
neurostrata-mcp --version  # neurostrata-mcp 1.9.0
```

Checked 2026-11-25: in an x86_64 Ubuntu 24.04 container the checksum passed and the binary printed `neurostrata-mcp 1.9.0`.

### OpenChamber (optional OpenCode workspace)

OpenChamber is a multi-surface workspace (web/PWA, desktop, VS Code, mobile) layered over OpenCode — a UI and session manager, not a runtime. Here it runs in external-attach mode against the existing OpenCode background service instead of spawning its own server. Optional; skip unless you want a browser workspace over the local OpenCode sessions.

**Prerequisites**

- **OpenCode already installed and set up** — the binary is at `~/.opencode/bin/opencode`, version >= 2.2.4 (v2.4.2 verified). This section attaches to an existing install; it does not install OpenCode.
- **A connected provider** — at least one provider is authenticated in OpenCode (here: OpenCode Go, connected via `opencode auth login`). Without a provider, the workspace opens but sessions cannot run a model. Provider credentials are operator-supplied and never live in this repo.
- **The OpenCode background service configured** — its state is at `~/.local/state/opencode/service.json`; OpenChamber does not read a password from that file (its auth is covered in the launch note below). The service does not survive VM restarts; wake it before launching, as described in the launch note below.
- **Node.js and Bun on PATH** — the CLI launches under Node (v24 verified), and the daemon runs under Bun (1.4 verified). Both ship in the Muse VM image; on any other machine, install Node >= 20 and Bun first.
- **Network access to the npm registry** for the install step below. The vendored snapshot under `reference/openchamber/` is a source reference, NOT an install path: running from it would require a Bun dependency install and build (not documented here), and it deliberately omits one credential-bearing file (see its `PROVENANCE.md` for the declared exclusion and local-regeneration instructions).
- **Your own UI password** — set `OPENCHAMBER_UI_PASSWORD` to an operator-chosen value and store it locally in a chmod-600 file; never commit it.

Install the published npm package `@openchamber/web` (prebuilt; no monorepo build) into a local app dir:

```bash
mkdir -p ~/workspace/openchamber/app && cd ~/workspace/openchamber/app
npm install @openchamber/web@2.8.1
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

OpenChamber does not read the service password from `~/.local/state/opencode/service.json` — in the vendored OpenChamber 2.7.3 code, no code path reads a password from that file (in the local file it sits as a top-level field), and the file's env map (variables set via `opencode service set env`) does not carry it. OpenChamber's auth initializes from its own process environment when set, preferring `OPENCODE_PASSWORD` over `OPENCODE_SERVER_PASSWORD` when both are present — the launch block therefore unsets `OPENCODE_PASSWORD`, so the service password is the credential used; its managed local OpenCode instance generates its own password. Against a password-protected background service, the documented launch MUST export the service's password as `OPENCODE_SERVER_PASSWORD`, read from `~/.local/state/opencode/service.json` at launch time as shown in the launch block: without it, OpenChamber's readiness and event probes receive 401s and health reports `openCodeRunning: false` even though the service is up (verified 2026-11-23). The exported password is a launch-time snapshot — OpenChamber reads it once at startup. A plain service restart does not change it (the service persists its password in `service.json`), but if the service password is ever regenerated, relaunch OpenChamber: until then its probes receive 401s and health again reports `openCodeRunning: false`. The password value is never printed, logged, or committed. Pairing: OpenCode >= 2.2.4 required, upstream tests against 2.3.2; v2.3.0 verified attached with no warnings (2026-11-19); v2.4.0 verified attached with no warnings (2026-11-23); v2.4.1 verified attached with no warnings (2026-11-23); v2.4.2 verified attached with no warnings (2026-11-27).

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
mkdir -p ~/workspace/neurostrata
HF_HUB_OFFLINE=1 nohup neurostrata-mcp daemon >> ~/workspace/neurostrata/daemon.log 2>&1 &
sleep 15
neurostrata-mcp status
# expect: "status: healthy" (the same response also prints "daemon: listening ... answering"; scripts/boot-gate.sh accepts that pair and the watchdog accepts either)
```

Append with `>>`, never `>`. A truncating redirect destroys the previous run's log, which is the only evidence of an unexpected death (see `docs/limitation-analysis.md` section 1). `HF_HUB_OFFLINE=1` is required because the binary cannot download its model through a TLS-intercepting proxy (see section 2).

The daemon log must show the embedder initializing from cache with no download attempt. The store is created at `~/.config/NeuroStrata/data/db/ladybug.db`.

Note: the binary ships systemd user units, but they cannot be enabled where no user D-Bus exists. `nohup` is the supported fallback; a dead daemon does *not* reliably come back via MCP spawn (verified 2026-10-16). Restart it directly with the `nohup` command above — the canonical watchdog (`ops/bin/watchdog-backup.sh`) captures crash evidence and backs up the DB, and never restarts the daemon itself.

**Idle reaping and the activity marker.** The watchdog stops a healthy daemon only when `~/workspace/neurostrata/.last-daemon-use` exists, is numeric, is older than its `IDLE_SECS` (3600), and `ss` shows no established loopback connection to the daemon port. A missing or unreadable marker means "activity unknown", and the watchdog leaves the daemon running rather than risk killing a session. A job started through `ops/bin/cron-with-boot-gate.sh` refreshes the marker for the whole run (override the path with `AEP_DAEMON_ACTIVITY_FILE`). A direct MCP client that never writes the marker is covered by the connection check when `ss` is installed; without `ss`, the marker is the only evidence, so on such a host the daemon is not reaped until something writes the marker. The watchdog exits 0 without stopping anything when it cannot prove idleness, which means a backup may be postponed; that is deliberate.

**Daemon forking behavior.** The binary forks on startup: briefly after launch, `pgrep -f 'neurostrata-mcp daemon'` returns two PIDs (the forking parent plus the live daemon). Any stop logic must signal *all* matching PIDs, not just the first — `pgrep ... | head -1` can pick the stale parent, leaving the live daemon running until the stop times out (observed 2026-10-17: `ERROR: daemon did not exit in 30s`, backup skipped, unclean-shutdown WAL warning on next start). Use the `[n]` bracket trick (`pgrep -f '[n]eurostrata-mcp daemon'`) so pgrep never matches its own command line, and loop `kill -TERM` over every returned PID. The canonical `ops/bin/watchdog-backup.sh` (and legacy `scripts/watchdog-backup.sh`) implement this.

### Seed the guard namespace

`scripts/boot-gate.sh` check 3 (guards) needs at least three `guard_rule` memories in the `guard` namespace, and one of them must contain "Destructive GitHub actions". On a fresh VM the namespace is empty and the gate fails closed with `BOOT-GATE: guards FAIL`. Seed it once the daemon is healthy (or stopped — the seeder handles both):

```bash
scripts/seed-boot-guards.sh --dry-run   # report what would be seeded, write nothing
scripts/seed-boot-guards.sh             # seed every canonical rule that is absent
scripts/seed-boot-guards.sh --check     # same test as boot-gate check 3, write nothing
```

The script is idempotent. It matches each canonical rule by a short key phrase inside an actual `guard_rule` record, so a rule worded differently on an older host still counts, an ordinary memory that merely mentions the phrase does not, and a second run changes nothing. The NeuroStrata store has a single-writer lock and `neurostrata-mcp add` only works while no daemon holds it: when the daemon is answering, the seeder stops it with `neurostrata-mcp shutdown`, seeds, verifies against the store, and restarts it with the `nohup` command from section 3. An EXIT trap restarts it even when a seed step fails, so the seeder never leaves a running daemon stopped. If the daemon was already stopped, it is left stopped. The script fails loudly (exit 1) when `neurostrata-mcp` is missing, when the daemon is busy or will not stop, or when the add fails. Concurrent seed runs are serialized with `flock` (or a lock directory where `flock` is unavailable).

It seeds three rules. The first is universal: destructive GitHub actions (branch deletion, force-push, history rewrite, repository deletion) each need the user's explicit per-action authorization. The second and third are specific to the document-accessibility-pipeline repo (no push without authorization, and the PR merge rule). If you replace the repo-specific rules, keep at least three `guard_rule` memories in the namespace.

Verify the result with the gate itself:

```bash
neurostrata-mcp list guard      # expect: Found 3 memories (or more)
scripts/boot-gate.sh            # expect: BOOT-GATE: guards ok
```

## 4. MCP client registration

The memory backend is consumed over MCP stdio. The wiring in the VM record of 2026-10-19 is the OpenCode config at `~/.config/opencode/opencode.json`. This repo does not ship that file, so the block below is a record and was not re-read in this change. Use the absolute path of your own `~/go/bin/neurostrata-mcp`:

```json
"mcp": {
  "neurostrata": {
    "type": "local",
    "command": ["/home/<user>/go/bin/neurostrata-mcp"],
    "enabled": true
  }
}
```

The daemon must already be running. A bare MCP spawn does not reliably start it (verified 2026-10-16), so start it as in section 3 before a session. Verify with the CLI, which needs no client:

```bash
neurostrata-mcp status          # expect: status: healthy
neurostrata-mcp list guard      # lists the guard namespace (seeded in section 3)
```

From an OpenCode session with the server enabled, the `neurostrata_list_namespaces` tool returns the namespace list.

## 5. Skill library

The canonical skill library is `skills/` in this repo (see the component status table in `README.md`). The deployed copy lives at `~/workspace/custom-skills/<name>/`, each skill holding `SKILL.md` and `skill.yaml`. Adapt upstream repos to local conventions. Skip harness-specific plugins, anything that needs unavailable credentials, and anything that duplicates an existing skill. Record the source of each skill. `docs/paperthin-skills.md` catalogs the paperthin skills.

Two local integrations to apply after install:

- `ralph_loop/SKILL.md`: before spawning the worker, search the memory backend for relevant past learnings and include the top hits in the brief. After each iteration, record durable outcomes in the loop's `learnings.md` only. Promotion to NeuroStrata happens only as a curator proposal the owner approves, carried out outside the loop, never as a direct write by a loop role. The skill exists in this repo, but the scheduler and backlog it drives are planned, not built (see the Planned appendix).
- `systematic-debugging/SKILL.md`: after a verified fix, inscribe root causes that teach beyond the session as rules.

## 6. Egress domain blocks

Some provider domains (`dolthub.com`, `gastownhall-eventsapi.com`) are bypassed from the egress proxy through `NO_PROXY` in `/etc/environment` and then dropped at the firewall. Apply the drops after every boot and after any VM replacement, because iptables rules do not survive either:

```bash
sudo scripts/apply-domain-blocks.sh
```

The script needs root. It exits non-zero with a `FATAL:` line when it is not root, when `iptables`, `getent`, `ip`, or `flock` is missing, or when a domain resolves to no address, and in each of those cases it changes nothing. It resolves the addresses at apply time with `getent ahostsv4` and `getent ahostsv6`, so no address is hardcoded. It inserts each DROP at the head of `OUTPUT` (`-I OUTPUT 1`) so an earlier ACCEPT rule cannot match first, and verification checks both presence and that ordering. When the host has an IPv6 default route or a domain publishes an AAAA record, it also writes `ip6tables` rules, and a missing `ip6tables` is a hard failure. `ip` is required so the IPv6 default route is always checked; without it the script fails closed rather than assuming the host is IPv4-only. A failed insert or verification rolls back the rules added by that run, and concurrent runs are serialized with `flock`. It re-checks every rule with `-C` before it prints `Domain blocks applied and verified: ...`, so that line means the rules exist and are ordered ahead of the ACCEPT rules.

The rules are only as current as the DNS answer at the moment of the run. Re-run the script after a DNS rotation, for example from a daily cron entry owned by root. The script records the DROP rules it actually installed in `/run/aep-domain-blocks/managed-rules` (override the directory with `AEP_BLOCK_STATE_DIR`) and removes a DROP on the next run when the address it was built from has rotated away, so an address later reused by an unrelated service is not left blocked. A DROP that was already present before the first run is not recorded as owned, so reconciliation never deletes an administrator's rule. To block other domains, set `AEP_BLOCK_DOMAINS` to a space-separated list.

Verify:

```bash
sudo iptables -S OUTPUT | grep DROP    # one DROP rule per resolved IPv4 address
sudo ip6tables -S OUTPUT | grep DROP   # present when IPv6 is active
```

## 7. Verification checklist

- [ ] `go version` reports a go1.27.x toolchain and `command -v bd ocr neurostrata-mcp` lists three paths under `~/go/bin`
- [ ] `bd ping` ok; issue lifecycle (create/show/close) works; per-repo isolation confirmed
- [ ] `bd` metrics OFF, proven by BOTH signals: `bd metrics` reports OFF, **and** `~/.config/bd/config.yaml` carries `disabled: true` under `metrics:` — assert with `grep -A2 '^metrics:' ~/.config/bd/config.yaml | grep -q 'disabled: true'` (exits non-zero when the flag is absent). If either check fails, setup has FAILED — stop and fix before continuing onboarding. A future bd version that moves the setting or changes the default must break setup visibly here, not silently phone home
- [ ] `ocr delegate preview` returns a review spec with no API key
- [ ] `neurostrata-mcp status` reports `status: healthy` and `scripts/boot-gate.sh` prints `BOOT-GATE: daemon ok` (the CLI prints `daemon: listening ... answering` in the same healthy response; `boot-gate.sh` checks that pair and the watchdog accepts either phrase)
- [ ] `scripts/seed-boot-guards.sh --check` exits 0 and `scripts/boot-gate.sh` prints `BOOT-GATE: guards ok`
- [ ] `sudo scripts/apply-domain-blocks.sh` prints `Domain blocks applied and verified:` and `sudo iptables -S OUTPUT` lists a DROP rule for each blocked domain
- [ ] `ops/bin/deploy-watchdog.sh --check` exits 0 (the deployed watchdog matches `ops/bin/watchdog-backup.sh`)
- [ ] The scheduler lists the `neurostrata-watchdog` job (every 2 h, see `ops/crons/CRONS.md`)
- [ ] (Optional) OpenChamber: `curl -s http://127.0.0.1:3411/health` reports `"openCodeRunning":true` with `"openCodePort":49374`, and the UI session list shows the background service's existing sessions

## Appendix: Planned / not yet implemented

These subsystems were designed and are not built, so none of the steps above depend on them. The text is kept as design reference. Do not follow it expecting a working result. The README component status table is the source of truth for what exists.

### A.1 Ralph loop and scheduler

```bash
mkdir -p ~/workspace/ralph/bin
```

- `backlog.md`: tasks as H2 sections with an ID prefix; metadata (`status`, `labels`, `priority`, `depends-on`) in HTML comments under the heading. Statuses: `to-do`, `in-progress`, `in-review`, `done`.
- `bin/backlog.py`: `list` and `next` commands (next = highest-priority unblocked to-do task, as JSON).
- Schedule: one job, id `ralph-loop`, interval 2 h, timeout 7200 s. Body instructs the worker to read the skill, run at most 6 iterations, stop on stall or triple failure, report only when work was done or attention is needed, and write observations to the daily log (never `MEMORY.md`).

### A.2 open-connector gateway (optional)

```bash
cd ~/workspace/open-connector && npm install   # 536 packages; generates the catalog
```

Start on demand (`start.sh`, ~20 s), discover actions (`oc.py list <service>` / `oc.py doc <action.id>`), execute (`oc.py run <action.id> '<json>'`), stop with `stop.sh`. If provider calls fail on egress, allowlist the host via `OOMOL_CONNECT_EGRESS_TRUSTED_HOSTS`.

### A.3 Custom stdio MCP client

Planned: a hand-written JSON-RPC client at `~/workspace/custom-connectors/custom.neurostrata/bin/client.py` with `list-tools` and `call-tool --name --arguments-file` commands. It is not built. Section 4 uses the OpenCode MCP wiring and the CLI instead. The design notes are kept for anyone who writes one. The server speaks MCP over stdio (protocol version `2024-11-05`). Two protocol quirks to handle:

- After `notifications/initialized`, the server emits a bare `{}` line on stdout. Tolerate non-JSON-RPC lines instead of failing.
- Maintain an `ALLOWED_TOOLS` allowlist, populated only with tool names reviewed from `list-tools` output. Suggested initial set: `neurostrata_add_memory`, `neurostrata_get_memory`, `neurostrata_search_memory`, `neurostrata_list_namespaces`, `neurostrata_get_snapshot`, `neurostrata_supersede_memory`, `neurostrata_archive_memory`, `neurostrata_append_log`.

Planned end-to-end check: `client.py list-tools`, add a test memory, search it back (this exercises the embedding model), fetch it by id, then archive the test record. `add_memory` requires `content`, `namespace`, `project_root`. Set `create_new_namespace: true` only for a genuinely new namespace.
