# Operations

## Scheduler

Job id `ralph-loop`, interval 2 h, timeout 2 h. Definition: `~/workspace/cron.d/hourly/ralph-loop__interval@2h.md` (read-only copy; manage via the cron tools).

```text
cron.list                 # all schedules
cron.view   {id: ralph-loop}
cron.run    {id: ralph-loop, reason: "..."}   # manual run
cron.remove {id: ralph-loop}
```

Runs report to chat only when tasks were completed or attention is needed. An empty backlog ends the run with a one-line result in run history.

## NeuroStrata daemon

```bash
~/workspace/neurostrata/bin/neurostrata-mcp status   # health, lock, store size
tail -20 ~/workspace/neurostrata/daemon.log          # startup / model load
# restart:
pkill -f 'neurostrata-mcp daemon'
nohup ~/workspace/neurostrata/bin/neurostrata-mcp daemon > ~/workspace/neurostrata/daemon.log 2>&1 &
```

If the daemon is down, the next MCP client spawn restarts it automatically.

## Memory backend

All operations go through the stdio client:

```bash
BIN=~/workspace/custom-connectors/custom.neurostrata/bin/client.py
python3 $BIN list-tools
python3 $BIN call-tool --name neurostrata_search_memory --arguments-file search.json  # {query, namespace}
python3 $BIN call-tool --name neurostrata_add_memory    --arguments-file add.json     # {content, namespace, project_root}
python3 $BIN call-tool --name neurostrata_get_memory    --arguments-file get.json     # {id, namespace}
python3 $BIN call-tool --name neurostrata_archive_memory --arguments-file a.json      # {id, namespace}
python3 $BIN call-tool --name neurostrata_list_namespaces --arguments-file empty.json # {}
```

Namespace convention: `global` for broadly-applicable lessons, project namespaces for project-specific ones. Prefer `neurostrata_supersede_memory` over archiving when a correction matters.

## beads

Per-repo issue tracking. Each repo carries its own database at `<repo>/.beads/embeddeddolt`.

```bash
cd <repo> && bd init
bd create "Title" --type task --priority 2
bd list / bd show <id> / bd close <id> / bd search "text"
bd status   # overview
```

Commit `.beads/` to version issues with the repo, or gitignore it to keep issues local.

## open-code-review

Delegation mode needs no API key:

```bash
cd <repo>
ocr delegate preview --format json
ocr delegate rule --format json <files>
```

Full `ocr review` / `ocr scan` require a configured LLM API key.

## open-connector

```bash
bash ~/workspace/custom-connectors/custom.openconnector/bin/start.sh   # ~20 s
python3 .../bin/oc.py list <service>
python3 .../bin/oc.py doc <action.id>
python3 .../bin/oc.py run <action.id> '<input-json>'
bash .../bin/stop.sh
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Daemon fails: `invalid peer certificate: UnknownIssuer` | TLS-intercepting proxy; binary does not trust the proxy CA | Pre-seed the model cache (runbook section 2); the binary never downloads on a cache hit |
| MCP client: invalid JSON-RPC message | Server emits `{}` after `notifications/initialized` | Tolerate non-JSON-RPC stdout lines; do not fail on them |
| `bd doctor`: "not yet supported in embedded mode" | Expected | Use `bd doctor --check={artifacts,conventions,pollution}`, `bd ping` |
| Provider calls fail from open-connector | Egress guard | Allowlist the host via `OOMOL_CONNECT_EGRESS_TRUSTED_HOSTS` |
| `neurostrata-mcp status`: "down" | Daemon died (e.g. VM restart) | Restart via nohup, or just call the MCP client — it auto-starts |
| Cron run reports "backlog empty" | No to-do tasks | Add tasks to `~/workspace/ralph/backlog.md` |
| Loop works an example task | Backlog still has seed examples | Replace `RALPH-001`/`RALPH-002` with real work or mark them done |
