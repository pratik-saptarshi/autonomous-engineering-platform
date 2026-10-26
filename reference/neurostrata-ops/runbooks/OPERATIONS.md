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
# restart (always with HF_HUB_OFFLINE=1):
pkill -f 'neurostrata-mcp daemon'
HF_HUB_OFFLINE=1 nohup ~/go/bin/neurostrata-mcp daemon >> ~/.local/share/neurostrata/daemon.log 2>&1 &
```

This VM has no user D-Bus, so the shipped systemd units are inert; the daemon
runs as a plain background process. There is no MCP client here — restarts are
direct, never via an MCP spawn.

## watchdog-backup.sh

One run does: (1) revive a dead daemon; (2) sha256 the DB — if unchanged since
`.last-db-sha256`, run Drive catch-up (below) and exit without touching the
daemon; (3) on change, SIGTERM the daemon (30 s grace), `cp -p` the DB,
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
HF_HUB_OFFLINE=1 nohup ~/go/bin/neurostrata-mcp daemon >> ~/.local/share/neurostrata/daemon.log 2>&1 &
sleep 12; ~/go/bin/neurostrata-mcp status | grep "status: healthy"
```

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
