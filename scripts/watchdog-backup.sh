#!/usr/bin/env bash
# watchdog-backup.sh — NeuroStrata daemon watchdog + change-detected DB backup.
#
# Every run:
#   1. Watchdog: if the daemon is down, restart it directly (nohup).
#   2. Checksum the DB. If unchanged since the last backup, log and exit 0 —
#      the daemon is never stopped when there is nothing to back up.
#   3. On change: SIGTERM the daemon (graceful checkpoint), copy the DB,
#      sha256-verify the copy against a hash taken immediately before the
#      copy, restart the daemon with HF_HUB_OFFLINE=1.
#   4. Upload the copy to Google Drive when configured (folder id file +
#      hatch_gws_cli present); otherwise the local backup is the only tier
#      and the run still succeeds. Record the new checksum, prune staging.
#
# The upstream backup.sh needs systemd; this environment has no user D-Bus,
# so SIGTERM replaces `systemctl stop/start`. Exit 0 unless the backup copy
# itself failed verification or a configured Drive upload failed.
set -euo pipefail

BIN="$HOME/workspace/neurostrata/bin/neurostrata-mcp"
DB="$HOME/.config/NeuroStrata/data/db/ladybug.db"
STAGE="$HOME/workspace/neurostrata/backups"
SHA_FILE="$HOME/workspace/neurostrata/.last-db-sha256"
FOLDER_ID_FILE="$HOME/workspace/neurostrata/.drive-database-folder-id"
LOG="$HOME/workspace/neurostrata/watchdog.log"
export HF_HUB_OFFLINE=1

log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
mkdir -p "$STAGE"

# Concurrency guard: two overlapping runs must never SIGTERM/copy together.
# NOTE: fd 9 must not leak into the daemon (see 9>&- in start_daemon) — an
# inheriting daemon would hold the lock forever and brick future runs.
exec 9>"$HOME/workspace/neurostrata/.watchdog.lock"
flock -n 9 || { log "another watchdog run in progress — exiting"; exit 0; }

start_daemon() {
  log "starting daemon"
  # 9>&-: the daemon must not inherit the flock fd, or it would hold the
  # lock for its whole lifetime and brick every future watchdog run.
  nohup "$BIN" daemon 9>&- > "$HOME/workspace/neurostrata/daemon.log" 2>&1 &
  sleep 12
}

# 1. Watchdog: revive via direct start. (A bare MCP spawn was tried here
# previously, but the stdio server does not reliably auto-start the daemon —
# verified: it hangs with no output and no daemon. Direct nohup is the
# proven path.)
if "$BIN" status 2>/dev/null | grep -q "status: healthy"; then
  log "watchdog: daemon healthy"
else
  log "watchdog: daemon down — restarting directly"
  start_daemon
  if "$BIN" status 2>/dev/null | grep -q "status: healthy"; then
    log "watchdog: daemon recovered"
  else
    log "watchdog: ERROR — daemon still down after restart attempt"
  fi
fi

# 2. Change detection BEFORE stopping anything: a live sha256sum read is safe
# here — it is only change detection. A torn read can only trigger a
# redundant backup cycle, never a missed one; the authoritative copy is
# still taken with the daemon stopped in step 3. Previously the daemon was
# SIGTERMed on every run even when the DB was unchanged.
if [ ! -f "$DB" ]; then
  log "no DB file yet — nothing to back up"
  exit 0
fi

NOW_SHA="$(sha256sum "$DB" | awk '{print $1}')"
LAST_SHA="$(cat "$SHA_FILE" 2>/dev/null || true)"

if [ -n "$LAST_SHA" ] && [ "$NOW_SHA" = "$LAST_SHA" ]; then
  log "no DB changes (sha256 ${NOW_SHA:0:12}…) — skipping backup, daemon untouched"
  exit 0
fi

# 3. Quiesce: SIGTERM the daemon so the copy is checkpoint-consistent.
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
  RESTART_NEEDED=true
  log "daemon stopped"
else
  log "daemon not running at stop time — will start it after the backup"
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

# 4. Backup + verify: hash the exact bytes being copied, taken immediately
# before cp, and verify the copy against THAT — not against the earlier
# change-detection hash, which describes the DB as it was before the stop.
TS="$(date +%Y%m%d-%H%M%S)"
STAGE_FILE="$STAGE/db-$TS.db"
SRC_SHA="$(sha256sum "$DB" | awk '{print $1}')"
cp -p "$DB" "$STAGE_FILE"
CP_SHA="$(sha256sum "$STAGE_FILE" | awk '{print $1}')"
if [ "$CP_SHA" != "$SRC_SHA" ]; then
  log "ERROR: backup checksum mismatch (copy ${CP_SHA:0:12}… vs source ${SRC_SHA:0:12}…) — bad copy deleted, source untouched"
  rm -f "$STAGE_FILE"
  finish_restart
  exit 1
fi
log "local backup OK: $STAGE_FILE"

finish_restart

# 5. Upload to Google Drive when configured. Drive is an optional tier: if the
# folder id file or hatch_gws_cli is missing, log a loud warning and keep the
# local backup as the only tier (exit 0). Only a *configured but failing*
# upload keeps the checksum stale so the next run retries it.
if [ ! -s "$FOLDER_ID_FILE" ] || ! command -v /opt/hatch/bin/hatch_gws_cli >/dev/null; then
  log "WARNING: Drive upload not configured (missing folder id file or hatch_gws_cli) — local backup is the only tier"
  echo -n "$CP_SHA" > "$SHA_FILE"
else
  FOLDER_ID="$(cat "$FOLDER_ID_FILE")"
  NAME="ladybug-$TS.db"
  if upload_diag="$(/opt/hatch/bin/hatch_gws_cli drive +upload "$STAGE_FILE" --parent "$FOLDER_ID" --name "$NAME" 2>&1)"; then
    log "uploaded to Drive (folder ${FOLDER_ID:0:12}…): $NAME"
    echo -n "$CP_SHA" > "$SHA_FILE"
  else
    log "ERROR: Drive upload failed (${upload_diag:0:200}) — local backup retained at $STAGE_FILE; will retry next run"
    exit 1
  fi
fi

# 6. Prune local staging, keep 3 most recent
ls -1t "$STAGE"/db-*.db 2>/dev/null | tail -n +4 | xargs -r rm -f
log "done"
