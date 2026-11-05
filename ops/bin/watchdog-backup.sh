#!/usr/bin/env bash
# watchdog-backup.sh — NeuroStrata daemon watchdog + change-detected DB backup.
#
# Every run (on-demand model: the daemon is no longer always-on — the MCP
# client starts it lazily at the beginning of a coding loop, and this
# watchdog stops it after IDLE_SECS without use):
#   1. Daemon-down is the expected idle state, not an error: if the daemon
#      is down, still run change detection, and back up a changed DB as a
#      quiescent copy (no writer, so no stop ceremony is needed). The
#      daemon stays down afterwards; the MCP client restarts it on the
#      next coding loop. This script never restarts the daemon itself.
#   2. Checksum the DB. If unchanged since the last backup, log and exit 0 —
#      except on the daemon-down path, where a failed Drive catch-up exits
#      1 — but first run drive_catch_up: the Drive tier may be behind even
#      when the DB is unchanged (it was unconfigured or failed when this
#      state was backed up). Note: on the idle path, the daemon IS stopped
#      by design after the no-change check.
#   3. On change with the daemon up: SIGTERM the daemon (graceful
#      checkpoint), copy the DB, sha256-verify the copy against a hash
#      taken immediately before the copy, and record the local checksum
#      (.last-db-sha256) independently of Drive. The daemon stays down
#      afterwards; the MCP client restarts it.
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
# itself failed verification, a configured Drive upload failed, or (on the
# daemon-down no-change path) Drive catch-up failed.
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
flock -n 9 || {
  log "another watchdog run in progress — exiting"
  exit 0
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
  newest="$(find "$STAGE" -maxdepth 1 -type f -name 'db-*.db' -printf '%T@ %p\0' 2>/dev/null | sort -znr | head -z -n 1 | cut -z -d ' ' -f 2- | tr -d '\0' || true)"
  if [ -z "$newest" ]; then
    log "WARNING: Drive catch-up wanted (sha ${want_sha:0:12}…) but no staged backup exists — clearing local watermark so the next run takes a fresh backup"
    rm -f "$SHA_FILE"
    return 0
  fi
  fsha="$(sha256sum "$newest" | awk '{print $1}')"
  if [ "$fsha" != "$want_sha" ]; then
    log "WARNING: newest staged backup (${fsha:0:12}…) does not match DB (${want_sha:0:12}…) — clearing local watermark so the next run takes a fresh backup"
    rm -f "$SHA_FILE"
    return 0
  fi
  folder_id="$(cat "$FOLDER_ID_FILE")"
  name="$(basename "$newest")"
  if upload_diag="$(/opt/hatch/bin/hatch_gws_cli drive +upload "$newest" --parent "$folder_id" --name "$name" 2>&1)"; then
    log "uploaded to Drive (folder ${folder_id:0:12}…): $name"
    echo -n "$want_sha" >"$DRIVE_SHA_FILE"
  else
    log "ERROR: Drive catch-up upload failed (${upload_diag:0:200}) — will retry next run"
    return 1
  fi
}

prune_staging() {
  find "$STAGE" -maxdepth 1 -type f -name 'db-*.db' -printf '%T@ %p\0' 2>/dev/null | sort -znr | tail -z -n +4 | cut -z -d ' ' -f 2- | xargs -0 -r rm -f
  find "$STAGE" -maxdepth 1 -type f -name 'logs-*.tar.gz' -printf '%T@ %p\0' 2>/dev/null | sort -znr | tail -z -n +4 | cut -z -d ' ' -f 2- | xargs -0 -r rm -f
}

# Archive the daemon and watchdog logs (the latter carries the memory
# telemetry) alongside each DB backup, so a backup always ships with the
# logs needed for forensics.
archive_logs() {
  # $1 = timestamp string for the archive name
  local ts="$1" archive
  archive="$STAGE/logs-$ts.tar.gz"
  tar -czf "$archive" -C "$HOME/workspace/neurostrata" \
    daemon.log watchdog.log logs 2>/dev/null || true
  if [ -f "$archive" ]; then
    log "logs archived: $archive"
  else
    log "WARNING: log archive failed (non-fatal)"
  fi
}

# Memory telemetry, logged on every run: a rising daemon-RSS trend
# distinguishes a memory leak from external OOM pressure.
log_memory() {
  local pid rss avail
  pid="$(pgrep -f '[n]eurostrata-mcp daemon' | head -1 || true)"
  rss=""
  if [ -n "$pid" ]; then
    rss="$(ps -o rss= -p "$pid" 2>/dev/null | tr -d ' ' || true)"
  fi
  avail="$(awk '/MemAvailable/ {print $2; exit}' /proc/meminfo 2>/dev/null || true)"
  log "memory: daemon_rss_kb=${rss:-unknown} mem_available_kb=${avail:-unknown}"
}

LOGS_DIR="$HOME/workspace/neurostrata/logs"
IDLE_SECS=3600
LAST_USE_FILE="$HOME/workspace/neurostrata/.last-daemon-use"

# Rotate a daemon log with a date-timestamp; prune to keep the 5 most recent.
rotate_daemon_log() {
  local src="$1" ts base
  [ -f "$src" ] && [ -s "$src" ] || return 0
  mkdir -p "$LOGS_DIR"
  ts="$(date +%Y%m%d-%H%M%S)"
  base="daemon-$ts.log"
  mv -f "$src" "$LOGS_DIR/$base"
  log "rotated daemon log -> logs/$base"
  find "$LOGS_DIR" -maxdepth 1 -type f -name 'daemon-*.log' -printf '%T@ %p\0' 2>/dev/null | sort -znr | tail -z -n +6 | cut -z -d ' ' -f 2- | xargs -0 -r rm -f
}

daemon_healthy() {
  "$BIN" status 2>/dev/null | grep -q "status: healthy"
}

# 1. On-demand model (2026-10-17): the daemon is no longer always-on. The MCP
# client starts it lazily at the beginning of a coding loop; this watchdog
# stops it after IDLE_SECS without use. If it is down, that is the expected
# idle state — but the DB can still drift between daemon sessions (2026-10-23:
# a change from Oct 18 sat ~5 days unbacked-up because change detection only
# ran when the daemon was up). So daemon-down runs still do change detection
# and back up when the DB moved. With the daemon down there is no writer, so
# the DB is quiescent and the copy needs no stop/copy ceremony — a plain
# verified copy is consistent.
if ! daemon_healthy; then
  log "daemon down (on-demand idle) — running change detection anyway"
  if [ ! -f "$DB" ]; then
    log "no DB file yet — nothing to back up"
    exit 0
  fi
  NOW_SHA="$(sha256sum "$DB" | awk '{print $1}')"
  LAST_SHA="$(cat "$SHA_FILE" 2>/dev/null || true)"
  if [ -n "$LAST_SHA" ] && [ "$NOW_SHA" = "$LAST_SHA" ]; then
    log "no DB changes (sha256 ${NOW_SHA:0:12}…) — skipping backup"
    # The DB is unchanged, but the Drive tier may still be behind.
    if ! drive_catch_up "$NOW_SHA"; then
      exit 1
    fi
    prune_staging
    log "done (daemon idle, unchanged)"
    exit 0
  fi
  log "DB changed while daemon was down (sha256 ${NOW_SHA:0:12}…) — backing up quiescent copy"
  # Unclean-death caveat: if the daemon died without checkpointing, -wal/-shm
  # may hold uncheckpointed frames this copy would miss. Log it loudly; the
  # copy is still the best available state.
  if [ -f "$DB-wal" ] || [ -f "$DB-shm" ]; then
    log "WARNING: daemon left -wal/-shm behind — copy may miss uncheckpointed frames"
  fi
  TS="$(date +%Y%m%d-%H%M%S)"
  STAGE_FILE="$STAGE/db-$TS.db"
  cp -p "$DB" "$STAGE_FILE"
  CP_SHA="$(sha256sum "$STAGE_FILE" | awk '{print $1}')"
  if [ "$CP_SHA" != "$NOW_SHA" ]; then
    log "ERROR: backup checksum mismatch (copy ${CP_SHA:0:12}… vs source ${NOW_SHA:0:12}…) — bad copy deleted, source untouched"
    rm -f "$STAGE_FILE"
    exit 1
  fi
  log "local backup OK: $STAGE_FILE"
  archive_logs "$TS"
  echo -n "$CP_SHA" >"$SHA_FILE"
  if ! drive_configured; then
    log "WARNING: Drive upload not configured — local backup is the only tier"
  else
    FOLDER_ID="$(cat "$FOLDER_ID_FILE")"
    NAME="ladybug-$TS.db"
    if upload_diag="$(/opt/hatch/bin/hatch_gws_cli drive +upload "$STAGE_FILE" --parent "$FOLDER_ID" --name "$NAME" 2>&1)"; then
      log "uploaded to Drive (folder ${FOLDER_ID:0:12}…): $NAME"
      echo -n "$CP_SHA" >"$DRIVE_SHA_FILE"
    else
      log "ERROR: Drive upload failed (${upload_diag:0:200}) — local backup retained at $STAGE_FILE; will retry next run"
      exit 1
    fi
  fi
  prune_staging
  log "done (daemon idle, backup taken)"
  exit 0
fi
log "daemon healthy"
log_memory

stop_daemon() {
  local PIDS PID
  PIDS="$(pgrep -f '[n]eurostrata-mcp daemon' || true)"
  if [ -z "$PIDS" ]; then
    log "daemon already stopped"
    return 0
  fi
  # The binary forks on start, so pgrep can return a parent/zombie plus the
  # real daemon. Signalling only the first PID (head -1) can miss the live
  # daemon and brick the backup cycle — signal every match.
  log "stopping daemon (pids $(echo "$PIDS" | tr '\n' ' '))"
  for PID in $PIDS; do kill -TERM "$PID" 2>/dev/null || true; done
  for _ in $(seq 1 30); do
    pgrep -f '[n]eurostrata-mcp daemon' >/dev/null || break
    sleep 1
  done
  if pgrep -f '[n]eurostrata-mcp daemon' >/dev/null; then
    log "ERROR: daemon did not exit in 30s — leaving it running, backup skipped"
    return 1
  fi
  log "daemon stopped"
}

# 2. Idle check: an actively-used daemon is left alone; an idle one is
# backed up (if changed) and stopped. A missing timestamp means the daemon
# predates on-demand tracking — treat it as idle so the old always-on
# instance is reaped on the first sweep.
now="$(date +%s)"
last_use="$(cat "$LAST_USE_FILE" 2>/dev/null || true)"
if [ -n "$last_use" ] && [ "$now" -lt "$((last_use + IDLE_SECS))" ]; then
  log "daemon active (last client use $((now - last_use))s ago) — leaving it running"
  exit 0
fi
log "daemon idle (last client use: ${last_use:-never}) — backing up and stopping"

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
  log "no DB changes (sha256 ${NOW_SHA:0:12}…) — skipping backup"
  # The DB is unchanged, but the Drive tier may still be behind (it was
  # unconfigured or failed when this state was backed up). Catch it up.
  if ! drive_catch_up "$NOW_SHA"; then
    exit 1
  fi
  prune_staging
  stop_daemon
  log "done (daemon stopped, idle)"
  exit 0
fi

# 3. Quiesce: SIGTERM the daemon so the copy is checkpoint-consistent.
# On-demand model: the daemon stays down after this — the MCP client
# restarts it on the next coding loop.

stop_daemon || exit 0

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
  exit 1
fi
log "local backup OK: $STAGE_FILE"

# Daemon stays down (on-demand model) — the MCP client restarts it next run.

# Archive logs with the backup for forensics.
archive_logs "$TS"

# The local tier is complete: record it now, independently of Drive. A
# failing Drive upload must not force a redundant daemon stop/copy cycle on
# the next run — the catch-up path re-uploads from staging instead.
echo -n "$CP_SHA" >"$SHA_FILE"

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
    echo -n "$CP_SHA" >"$DRIVE_SHA_FILE"
  else
    log "ERROR: Drive upload failed (${upload_diag:0:200}) — local backup retained at $STAGE_FILE; will retry next run"
    exit 1
  fi
fi

# 6. Prune local staging, keep 3 most recent
prune_staging
log "done"
