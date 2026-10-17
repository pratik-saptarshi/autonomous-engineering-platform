#!/usr/bin/env bash
# watchdog-backup.sh — NeuroStrata daemon watchdog + change-detected DB backup.
#
# Every run:
#   1. Watchdog: if the daemon is down, trigger one MCP spawn (auto-restart).
#   2. Checksum the DB once quiescent. If unchanged since the last backup, stop.
#   3. On change: SIGTERM the daemon (graceful checkpoint), copy + sha256-verify,
#      restart the daemon with HF_HUB_OFFLINE=1, upload the copy to Google Drive
#      (Musebot-Astro/database), record the new checksum, prune local staging.
#
# The upstream backup.sh needs systemd; this environment has no user D-Bus,
# so SIGTERM replaces `systemctl stop/start`. Exit 0 unless the backup itself failed.
set -euo pipefail

BIN="$HOME/workspace/neurostrata/bin/neurostrata-mcp"
CLIENT="$HOME/workspace/custom-connectors/custom.neurostrata/bin/client.py"
DB="$HOME/.config/NeuroStrata/data/db/ladybug.db"
STAGE="$HOME/workspace/neurostrata/backups"
SHA_FILE="$HOME/workspace/neurostrata/.last-db-sha256"
FOLDER_ID_FILE="$HOME/workspace/neurostrata/.drive-database-folder-id"
LOG="$HOME/workspace/neurostrata/watchdog.log"
export HF_HUB_OFFLINE=1

log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
mkdir -p "$STAGE"

# Concurrency guard: two overlapping runs must never SIGTERM/copy together.
exec 9>"$HOME/workspace/neurostrata/.watchdog.lock"
flock -n 9 || { log "another watchdog run in progress — exiting"; exit 0; }

# Preflight: without the Drive folder id (or the CLI) no upload is possible.
# Fail fast with a clear message instead of dying mid-run under set -e.
if [ ! -s "$FOLDER_ID_FILE" ]; then
  log "ERROR: Drive folder id file missing or empty ($FOLDER_ID_FILE) — cannot upload; fix and rerun"
  exit 2
fi
command -v /opt/hatch/bin/hatch_gws_cli >/dev/null || { log "ERROR: hatch_gws_cli not found — cannot upload"; exit 2; }

start_daemon() {
  log "starting daemon"
  nohup "$BIN" daemon > "$HOME/workspace/neurostrata/daemon.log" 2>&1 &
  sleep 12
}

# 1. Watchdog
if "$BIN" status 2>/dev/null | grep -q "status: healthy"; then
  log "watchdog: daemon healthy"
else
  log "watchdog: daemon down — triggering auto-restart via MCP spawn"
  python3 "$CLIENT" list-tools >/dev/null 2>&1 || true
  sleep 10
  if "$BIN" status 2>/dev/null | grep -q "status: healthy"; then
    log "watchdog: daemon recovered"
  else
    log "watchdog: ERROR — daemon still down after restart attempt"
  fi
fi

# 2. Quiesce: SIGTERM the daemon so the copy is checkpoint-consistent.
# RESTART_NEEDED + the EXIT trap guarantee the daemon comes back even if a
# later step fails (set -e would otherwise exit with the daemon down).
RESTART_NEEDED=false
on_exit() {
  if $RESTART_NEEDED; then
    log "exit trap: ensuring daemon is restarted"
    start_daemon
    RESTART_NEEDED=false
  fi
}
trap on_exit EXIT

PID="$(pgrep -f '[n]eurostrata-mcp daemon' | head -1 || true)"
if [ -n "$PID" ]; then
  log "stopping daemon (pid $PID) for a consistent copy"
  kill -TERM "$PID" || true
  for _ in $(seq 1 30); do
    pgrep -f '[n]eurostrata-mcp daemon' >/dev/null || break
    sleep 1
  done
  if pgrep -f '[n]eurostrata-mcp daemon' >/dev/null; then
    log "ERROR: daemon did not exit in 30s — skipping backup this run"
    exit 0
  fi
  log "daemon stopped"
  RESTART_NEEDED=true
fi

finish_restart() {
  if $RESTART_NEEDED; then
    start_daemon
    if "$BIN" status 2>/dev/null | grep -q "status: healthy"; then
      log "daemon restarted, healthy"
    else
      log "ERROR: daemon failed to restart — next watchdog run will retry"
    fi
    RESTART_NEEDED=false
  fi
}

if [ ! -f "$DB" ]; then
  log "no DB file yet — nothing to back up"
  finish_restart
  exit 0
fi

NOW_SHA="$(sha256sum "$DB" | awk '{print $1}')"
LAST_SHA="$(cat "$SHA_FILE" 2>/dev/null || true)"

if [ -n "$LAST_SHA" ] && [ "$NOW_SHA" = "$LAST_SHA" ]; then
  log "no DB changes (sha256 ${NOW_SHA:0:12}…) — skipping backup"
  finish_restart
  exit 0
fi

# 3. Backup + verify
TS="$(date +%Y%m%d-%H%M%S)"
STAGE_FILE="$STAGE/db-$TS.db"
cp -p "$DB" "$STAGE_FILE"
CP_SHA="$(sha256sum "$STAGE_FILE" | awk '{print $1}')"
if [ "$CP_SHA" != "$NOW_SHA" ]; then
  log "ERROR: backup checksum mismatch — bad copy deleted, source untouched"
  rm -f "$STAGE_FILE"
  finish_restart
  exit 1
fi
log "local backup OK: $STAGE_FILE"

finish_restart

# 4. Upload to Google Drive (Musebot-Astro/database).
# Record the checksum ONLY after a successful upload: if the upload fails,
# the checksum stays stale, so the next run repeats the full backup cycle
# (stop, copy, restart, re-upload) instead of treating the DB as backed up.
FOLDER_ID="$(cat "$FOLDER_ID_FILE")"
NAME="ladybug-$TS.db"
if /opt/hatch/bin/hatch_gws_cli drive +upload "$STAGE_FILE" --parent "$FOLDER_ID" --name "$NAME" >/dev/null 2>&1; then
  log "uploaded to Drive: Musebot-Astro/database/$NAME"
  echo -n "$NOW_SHA" > "$SHA_FILE"
else
  log "ERROR: Drive upload failed — local backup retained at $STAGE_FILE; will retry next run"
fi

# 5. Prune local staging, keep 3 most recent
ls -1t "$STAGE"/db-*.db 2>/dev/null | tail -n +4 | xargs -r rm -f
log "done"
