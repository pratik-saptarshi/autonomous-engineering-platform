#!/usr/bin/env bash
# watchdog-backup.sh — NeuroStrata daemon watchdog + change-detected DB backup.
#
# Every run:
#   1. Watchdog: if the daemon is down, restart it directly (nohup).
#   2. Checksum the DB. If unchanged since the last backup, log and exit 0 —
#      the daemon is never stopped when there is nothing to back up — but
#      first run drive_catch_up: the Drive tier may be behind even when the
#      DB is unchanged (it was unconfigured or failed when this state was
#      backed up).
#   3. On change: SIGTERM the daemon (graceful checkpoint), copy the DB,
#      sha256-verify the copy against a hash taken immediately before the
#      copy, restart the daemon with HF_HUB_OFFLINE=1. Record the local
#      checksum (.last-db-sha256) independently of Drive.
#   4. Upload the copy to Google Drive when configured (folder id file +
#      hatch_gws_cli present) and record .last-drive-sha256; otherwise the
#      local backup is the only tier and the run still succeeds — the Drive
#      checksum stays stale so a later run uploads this backup once Drive
#      is configured. Prune staging.
#
# Two watermarks, two tiers: .last-db-sha256 = a verified local copy exists;
# .last-drive-sha256 = that state was uploaded. Never mark the Drive tier
# done without a successful upload.
#
# The upstream backup.sh needs systemd; this environment has no user D-Bus,
# so SIGTERM replaces `systemctl stop/start`. Exit 0 unless the backup copy
# itself failed verification or a configured Drive upload failed.
set -euo pipefail

BIN="$HOME/workspace/neurostrata/bin/neurostrata-mcp"
DB="$HOME/.config/NeuroStrata/data/db/ladybug.db"
STAGE="$HOME/workspace/neurostrata/backups"
SHA_FILE="$HOME/workspace/neurostrata/.last-db-sha256"
DRIVE_SHA_FILE="$HOME/workspace/neurostrata/.last-drive-sha256"
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

drive_configured() {
  [ -s "$FOLDER_ID_FILE" ] && command -v /opt/hatch/bin/hatch_gws_cli >/dev/null
}

# Upload the newest staged backup to Drive and record it. Used both after a
# fresh backup and on no-change runs to catch up a Drive tier that was
# unconfigured (or failed) when the backup was taken: without this, a backup
# taken while Drive was unavailable would never be uploaded once Drive
# returns, because the DB checksum would already be marked done.
drive_catch_up() {
  # $1 = sha256 of the DB state the staged backup must match
  local want_sha="$1" drive_sha newest fsha folder_id name upload_diag
  drive_configured || return 0
  drive_sha="$(cat "$DRIVE_SHA_FILE" 2>/dev/null || true)"
  if [ -n "$drive_sha" ] && [ "$drive_sha" = "$want_sha" ]; then
    return 0
  fi
  newest="$(ls -1t "$STAGE"/db-*.db 2>/dev/null | head -1 || true)"
  if [ -z "$newest" ]; then
    log "WARNING: Drive catch-up wanted (sha ${want_sha:0:12}…) but no staged backup exists"
    return 0
  fi
  fsha="$(sha256sum "$newest" | awk '{print $1}')"
  if [ "$fsha" != "$want_sha" ]; then
    log "WARNING: newest staged backup (${fsha:0:12}…) does not match DB (${want_sha:0:12}…) — skipping Drive catch-up"
    return 0
  fi
  folder_id="$(cat "$FOLDER_ID_FILE")"
  name="$(basename "$newest")"
  if upload_diag="$(/opt/hatch/bin/hatch_gws_cli drive +upload "$newest" --parent "$folder_id" --name "$name" 2>&1)"; then
    log "uploaded to Drive (folder ${folder_id:0:12}…): $name"
    echo -n "$want_sha" > "$DRIVE_SHA_FILE"
  else
    log "ERROR: Drive catch-up upload failed (${upload_diag:0:200}) — will retry next run"
    return 1
  fi
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
  # The DB is unchanged, but the Drive tier may still be behind (it was
  # unconfigured or failed when this state was backed up). Catch it up.
  if ! drive_catch_up "$NOW_SHA"; then
    exit 1
  fi
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

# The local tier is complete: record it now, independently of Drive. A
# failing Drive upload must not force a redundant daemon stop/copy cycle on
# the next run — the catch-up path re-uploads from staging instead.
echo -n "$CP_SHA" > "$SHA_FILE"

# 5. Upload to Google Drive when configured. Drive is an optional tier: if the
# folder id file or hatch_gws_cli is missing, log a loud warning and keep the
# local backup as the only tier (exit 0) — but do NOT mark the Drive tier
# done, so a later run uploads this backup once Drive is configured (see
# drive_catch_up). Only a *configured but failing* upload exits 1.
if ! drive_configured; then
  log "WARNING: Drive upload not configured (missing folder id file or hatch_gws_cli) — local backup is the only tier"
else
  FOLDER_ID="$(cat "$FOLDER_ID_FILE")"
  NAME="ladybug-$TS.db"
  if upload_diag="$(/opt/hatch/bin/hatch_gws_cli drive +upload "$STAGE_FILE" --parent "$FOLDER_ID" --name "$NAME" 2>&1)"; then
    log "uploaded to Drive (folder ${FOLDER_ID:0:12}…): $NAME"
    echo -n "$CP_SHA" > "$DRIVE_SHA_FILE"
  else
    log "ERROR: Drive upload failed (${upload_diag:0:200}) — local backup retained at $STAGE_FILE; will retry next run"
    exit 1
  fi
fi

# 6. Prune local staging, keep 3 most recent
ls -1t "$STAGE"/db-*.db 2>/dev/null | tail -n +4 | xargs -r rm -f
log "done"
