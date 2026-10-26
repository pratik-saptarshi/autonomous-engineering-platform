# NeuroStrata operations (this VM)

## Paths

| What | Path |
|---|---|
| Binary | `~/go/bin/neurostrata-mcp` (v1.9.0) |
| Daemon log | `~/.local/share/neurostrata/daemon.log` |
| Database | `~/.config/NeuroStrata/data/db/ladybug.db` |
| Model cache | `~/.cache/neuro/models/fastembed/` (nomic-embed-text-v1.5, ~523 MB) |
| Watchdog script | `~/workspace/neurostrata/bin/watchdog-backup.sh` |
| Watchdog log | `~/workspace/neurostrata/watchdog.log` |
| Last DB checksum | `~/workspace/neurostrata/.last-db-sha256` |
| Last Drive-upload checksum | `~/workspace/neurostrata/.last-drive-sha256` |
| Local DB backups | `~/workspace/neurostrata/backups/db-<timestamp>.db` (newest 3 kept) |
| Model tarball | `~/workspace/neurostrata/model-cache-backup.tar.gz` (+ `.sha256`) |

## Status and restart

```bash
~/go/bin/neurostrata-mcp status        # healthy => "status: healthy"
# restart: stop it, then start it exactly as in "Restore the DB from a
# backup" below (log rotation + 9>&- + poll for health) — never a bare
# nohup relaunch.
pkill -f 'neurostrata-mcp daemon'
```

This VM has no user D-Bus, so the shipped systemd units are inert; the daemon
runs as a plain background process. There is no MCP client here — restarts are
direct, never via an MCP spawn.

## watchdog-backup.sh

One run does: (1) observe the daemon's state and classify it (healthy / down
via the idle reaper / down unexpectedly) — no restart yet: change detection
runs before any restart decision (the old revive-first order restarted a
reaped daemon only to stop it again for the copy); (2) sha256 the DB — if
unchanged since `.last-db-sha256`, act on the classification: daemon up →
log and skip; down via the reaper → leave it down (it restarts on demand);
down unexpectedly → restart it and poll for health (up to 60 s), logging
ERROR if it stays down; then run Drive catch-up (below) and exit (exit 1
if catch-up fails twice); (3) on change, SIGTERM the daemon (30 s grace), `cp -p` the DB,
sha256-verify the copy against a fresh pre-copy hash, delete it and exit 1 on
mismatch; (4) restart the daemon with `HF_HUB_OFFLINE=1` (an EXIT trap
guarantees the restart even if a later step fails); (5) record the local
checksum in `.last-db-sha256` immediately after the verified copy — a failing
Drive upload never forces a redundant stop/copy cycle; (6) optional Google
Drive upload, tracked separately in `.last-drive-sha256`; (7) prune staging to
3 copies.

Two watermarks: `.last-db-sha256` = a verified local copy exists;
`.last-drive-sha256` = that DB state was uploaded to Drive. `drive_catch_up`
runs on the no-change path: if Drive is configured but its watermark is stale,
it uploads the newest staged backup (hash-checked against the DB first)
without stopping the daemon, and no-ops when already in sync or Drive is
unconfigured.

Run it by hand any time: `~/workspace/neurostrata/bin/watchdog-backup.sh`.
Cron `neurostrata-watchdog` runs it every 2 h (owner
`goal:environment-maintenance-daemon-watchdog-backups`).

## Restore the DB from a backup

```bash
pkill -f 'neurostrata-mcp daemon'
sleep 3; pgrep -f '[n]eurostrata-mcp daemon' && echo "STILL RUNNING — stop first" && exit 1
cp -p ~/workspace/neurostrata/backups/db-<timestamp>.db ~/.config/NeuroStrata/data/db/ladybug.db
# restart the way watchdog-backup.sh's start_daemon does: rotate the daemon
# log first (keeps the last 10), close any inherited flock FD (9>&-), then
# poll for health — a cold start loads the embedding model and can exceed
# the old fixed 12 s wait.
DAEMON_LOG=~/.local/share/neurostrata/daemon.log
[ -f "$DAEMON_LOG" ] && mv "$DAEMON_LOG" "$DAEMON_LOG.$(date +%Y%m%d-%H%M%S)"
ls -1t "$DAEMON_LOG".* 2>/dev/null | tail -n +11 | xargs -r rm -f || true
ulimit -c unlimited 2>/dev/null || true
HF_HUB_OFFLINE=1 nohup ~/go/bin/neurostrata-mcp daemon >> "$DAEMON_LOG" 2>&1 9>&- &
for i in $(seq 1 12); do ~/go/bin/neurostrata-mcp status 2>/dev/null | grep -q "status: healthy" && break; sleep 5; done
~/go/bin/neurostrata-mcp status | grep "status: healthy"
```

### Restore rehearsal — 2026-10-26 (was-down backup): RESTORE PROVEN

Rehearsed the newest staged backup, `backups/db-20261026-040153.db`, in a
sandbox under `/tmp` (copies only; the live daemon was not touched). The
backup is a **was-down** copy — the daemon was already down when the
watchdog copied the DB, so no watchdog-controlled stop/checkpoint preceded
the copy. Log proof (`watchdog.log`, 2026-10-26 04:01:53): `DB changed
(bd15932b1b80… -> c89d390c03e1…)`, then `daemon was not running — will
start it after the backup`, then `local backup OK …
db-20261026-040153.db (sha256 c89d390c03e1…)`. That is the normal class
here, not an edge case: the idle reaper keeps the daemon down at watchdog
cadence, and all three staged backups at rehearsal time were was-down.

Verdict: the lone copied file opens clean with no sidecars (after the
battery the sandbox DB dir held only `ladybug.db` and the CLI's own lock
file — no `.wal` demanded, no new `wal.unclean` marker generated);
`doctor` counts matched the live store exactly, **156/156 across all
eight namespaces** (aep 15, dap 95, environment 12, global 9, guard 9,
jobs 4, life 3, neurostrata 9); content queries returned genuine memories
(`list environment`; `export-graph` exported all 156 nodes); the embedder
initializes offline against the restored store (BGESmallENV15Q, from the
model cache). The AMBER on logical completeness of was-down copies is
retired for the was-down-after-clean-shutdown class — the only class this
system currently produces.

Two operator rules this rehearsal established:

- **Validate restores by doctor counts, NOT by sha against the live
  file.** At rehearsal time the live DB's sha (`c15d9eae…`) differed from
  its own newest backup (`c89d390c…`) at identical logical content —
  checkpoint layout noise moves the bytes (the improvement-#5
  phenomenon). The byte check that means something is the staged backup's
  sha against the watchdog log line and the `.last-db-sha256` watermark;
  both matched.
- **The nine `ladybug.db.wal.unclean.*` markers in the live store dir are
  42-byte flag stubs, not data.** All nine are byte-identical (single md5
  `356a54fc55226b3cd5e6ec33da41597a`); 42 identical bytes cannot carry
  memory payloads, no data-bearing `ladybug.db.wal` has ever been
  observed here, and the watchdog copies exactly one file — backups
  neither carry nor need sidecars. Boundary: if a store dir ever shows a
  non-trivial `ladybug.db.wal`, this verdict does not extend to it —
  rehearse again before trusting the single-file copy.

One boundary on the proof: daemon-level semantic search was deliberately
not exercised — a sandbox daemon would bind the production port
(127.0.0.1:34343), where production MCP clients could auto-connect and
write into the rehearsal copy. Retrieval is proven at the CLI
list/export-graph level and the embedding model demonstrably loads; a
daemon-level search test belongs in a maintenance window or on a second
host.

To repeat the rehearsal (~10 min, read-only against live state; work on
copies, never the live store):

```bash
SB=/tmp/rehearsal-a10
mkdir -p $SB/home/.config/NeuroStrata/data/db $SB/home/.config/neurostrata $SB/home/.cache
cp ~/workspace/neurostrata/backups/db-<timestamp>.db \
   $SB/home/.config/NeuroStrata/data/db/ladybug.db
cp ~/.config/neurostrata/embedders.json $SB/home/.config/neurostrata/embedders.json
ln -s ~/.cache/neuro $SB/home/.cache/neuro        # model cache, read-only use
B=~/go/bin/neurostrata-mcp   # captured BEFORE the redirect — ~ would follow the new HOME after it
export HOME=$SB/home XDG_CONFIG_HOME=$SB/home/.config XDG_CACHE_HOME=$SB/home/.cache
export HF_HUB_OFFLINE=1
$B status          # store path must show the sandbox path, not the live one
$B doctor          # counts must match the live store, namespace by namespace
$B list <namespace>   # and: $B export-graph — content spot-checks
# NEVER start a sandbox daemon (port collision, above).
```

Judge the backup's class from `watchdog.log` first: the `daemon was not
running` line after a `DB changed` banner marks a was-down copy.

## Restore the model cache from the tarball

```bash
sha256sum -c ~/workspace/neurostrata/model-cache-backup.sha256
tar -xzf ~/workspace/neurostrata/model-cache-backup.tar.gz -C ~/.cache/neuro/models
```

## TLS proxy quirk

The binary's rustls client ignores `SSL_CERT_FILE` and rejects this network's
egress-proxy MITM certificate (`UnknownIssuer`). Model/file downloads must go
through `curl` (which honors the proxy CA), never through the tool's own
downloader. `HF_HUB_OFFLINE=1` is exported by the watchdog and set on the
daemon so a model-cache miss fails fast with a clear error instead of an
opaque TLS failure.

## Google Drive upload (optional)

Create `~/workspace/neurostrata/.drive-database-folder-id` containing the
target Drive folder ID (single line). The script then uploads each new backup
via `/opt/hatch/bin/hatch_gws_cli drive +upload <file> --parent <id> --name
ladybug-<timestamp>.db`, and records completion in `.last-drive-sha256`
(separate from the local `.last-db-sha256`). If Drive was unconfigured when a
backup was taken, the next run's `drive_catch_up` uploads it without stopping
the daemon. Without the folder-id file it logs "Drive upload not configured"
and keeps the local backup — the run still succeeds.

## 2026-10-21 — Daemon log rotation (#21 investigation, Task 1)

- **What changed:** `bin/watchdog-backup.sh` `start_daemon()` now rotates `$DAEMON_LOG`
  (`~/.local/share/neurostrata/daemon.log`) before every (re)start: the existing
  log is moved to `daemon.log.<YYYYMMDD-HHMMSS>`, keeping the last 10 rotations.
- **Why:** the daemon log is the only crash evidence for the #21 unclean-shutdown
  investigation. It was append-only and unbounded; rotation preserves per-restart
  evidence so a WAL warning can be matched to the shutdown that caused it.
- **Reversible:** delete the rotation block in `start_daemon()` (marked with the
  date and issue reference). No restart/backup behavior was changed.

## 2026-10-23 — Canary reaper-correlation fix (#21)

- **What:** Rewrote the death-classification block in `bin/watch-daemon-death.sh`.
  Replaced the string-prefix date match (`cut -c1-15`, which was a 10-minute
  bucket) with epoch arithmetic; matched all four watchdog shutdown phrases
  (`restarting directly`, `starting daemon`, `stopping daemon for a consistent
  copy`, `daemon was not running`); removed early-`continue` so reaper and
  watchdog correlations are both evaluated before a verdict (overlap logged as
  ambiguous); kept the core-file check as best-effort gated on `ulimit -Hc`
  (no-op on this VM, where the hard core limit is 0).
- **Why:** the canary false-positived on 2026-10-22 21:56 CDT — PID gone with
  no core was logged "SIGKILL likely", but reaper.log showed a clean HTTP
  `REAPED` 28s earlier. Clean supervisor shutdowns also leave no core.
  The adversarial panel (planning-wringer) verified the draft's window logic
  was broken in both directions and the watchdog grep missed two phrases.
- **Honesty label:** `*** UNEXPLAINED DEATH` now means "not either known
  supervisor" (diagnosis by exclusion), not "confirmed external kill".
- **Known limitations:** (1) no supervision for the canary itself — if it dies
  silently, check manually with `pgrep -f watch-daemon-death`; (2) poll-based
  correlation has an irreducible race window (death between a supervisor's log
  write and the canary's 30s poll can be misattributed); the 120s window
  shrinks but does not eliminate it.
- **Reversible:** restore the previous `watch-daemon-death.sh` from backup or
  re-apply the old classification block. The canary never touches the daemon.
