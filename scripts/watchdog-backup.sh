#!/usr/bin/env bash
# watchdog-backup.sh — NeuroStrata daemon watchdog + change-detected DB backup.
#
# Every run:
#   1. Watchdog: if the daemon is down, restart it directly (nohup) —
#      unless the file named by WATCHDOG_LEAVE_DOWN_MARKER exists: then
#      the down state is intentional (e.g. an idle reaper shut it down
#      in an adapted deployment) and the run leaves it down.
#   2. Checksum the DB. If unchanged since the last backup, log and exit 0 —
#      the daemon is never stopped when there is nothing to back up — but
#      first run drive_catch_up: the Drive tier may be behind even when the
#      DB is unchanged (it was unconfigured or failed when this state was
#      backed up).
#   3. On change: SIGTERM the daemon (graceful checkpoint), copy the DB,
#      sha256-verify the copy against a hash taken immediately before the
#      copy, restart the daemon with HF_HUB_OFFLINE=1 and poll its health
#      (WATCHDOG_HEALTH_TIMEOUT, default 60s). Record the local checksum
#      (.last-db-sha256) independently of Drive.
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
# itself failed verification, a configured Drive upload failed, or the
# daemon would not stop for the copy.
set -euo pipefail

BIN="$HOME/workspace/neurostrata/bin/neurostrata-mcp"
DB="$HOME/.config/NeuroStrata/data/db/ladybug.db"
STAGE="$HOME/workspace/neurostrata/backups"
SHA_FILE="$HOME/workspace/neurostrata/.last-db-sha256"
DRIVE_SHA_FILE="$HOME/workspace/neurostrata/.last-drive-sha256"
FOLDER_ID_FILE="$HOME/workspace/neurostrata/.drive-database-folder-id"
LOG="$HOME/workspace/neurostrata/watchdog.log"
LOGS_DIR="$HOME/workspace/neurostrata/logs"
IDLE_SECS=3600
LAST_USE_FILE="$HOME/workspace/neurostrata/.last-daemon-use"
# Leave-down marker: when the file named here exists, a down daemon is
# down on purpose and is never restarted by this script (see step 1).
LEAVE_DOWN_MARKER="${WATCHDOG_LEAVE_DOWN_MARKER:-}"
# Health-poll budget after a (re)start; a cold start loads a ~547MB model
# and can exceed the old fixed 12s sleep under memory pressure.
HEALTH_TIMEOUT="${WATCHDOG_HEALTH_TIMEOUT:-60}"
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

leave_down_intentional() {
  [ -n "$LEAVE_DOWN_MARKER" ] && [ -f "$LEAVE_DOWN_MARKER" ]
}

start_daemon() {
  log "starting daemon"
  # 9>&-: the daemon must not inherit the flock fd, or it would hold the
  # lock for its whole lifetime and brick every future watchdog run.
  # Rotate (never truncate) the daemon log with a date-timestamp: a dying
  # daemon's stderr — Rust panic, OOM trace — must survive the restart.
  # Readiness is the caller's job (wait_healthy): a fixed sleep here
  # proved too short for a cold start and too long for a warm one.
  rotate_daemon_log "$HOME/workspace/neurostrata/daemon.log"
  nohup "$BIN" daemon 9>&- >"$HOME/workspace/neurostrata/daemon.log" 2>&1 &
}

daemon_healthy() {
  "$BIN" status 2>/dev/null | grep -q "status: healthy"
}

# Poll daemon_healthy every 5s until it passes or $1 seconds elapse
# (default: HEALTH_TIMEOUT).
wait_healthy() {
  local deadline=$((SECONDS + ${1:-$HEALTH_TIMEOUT}))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if daemon_healthy; then
      return 0
    fi
    sleep 5
  done
  daemon_healthy
}

start_and_wait() {
  start_daemon
  if wait_healthy; then
    log "daemon restarted, healthy"
  else
    log "ERROR: daemon still down after restart attempt — next watchdog run will retry"
  fi
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
  # shellcheck disable=SC2012 # filenames are machine-generated (db-*.db); ls -1t mtime sort is intended
  newest="$(ls -1t "$STAGE"/db-*.db 2>/dev/null | head -1 || true)"
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
  # The || true guards matter: under pipefail, an empty glob makes ls
  # fail and would otherwise kill the run from inside a cleanup helper.
  # shellcheck disable=SC2012 # filenames are machine-generated; ls -1t mtime sort is intended
  ls -1t "$STAGE"/db-*.db 2>/dev/null | tail -n +4 | xargs -r rm -f || true
  # shellcheck disable=SC2012 # filenames are machine-generated; ls -1t mtime sort is intended
  ls -1t "$STAGE"/logs-*.tar.gz 2>/dev/null | tail -n +4 | xargs -r rm -f || true
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

# Rotate a daemon log with a date-timestamp; prune to keep the 5 most recent.
rotate_daemon_log() {
  local src="$1" ts base
  [ -f "$src" ] && [ -s "$src" ] || return 0
  mkdir -p "$LOGS_DIR"
  ts="$(date +%Y%m%d-%H%M%S)"
  base="daemon-$ts.log"
  mv -f "$src" "$LOGS_DIR/$base"
  log "rotated daemon log -> logs/$base"
  # shellcheck disable=SC2012 # filenames are machine-generated (daemon-*.log); ls -1t mtime sort is intended
  ls -1t "$LOGS_DIR"/daemon-*.log 2>/dev/null | tail -n +6 | xargs -r rm -f
}

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

# --- EXIT trap: a run that stopped the daemon must never leave it down. ---
# If the run dies between the stop and the restart (copy failure, kill,
# set -e abort), the trap performs the restart — unless the leave-down
# marker says the down state is intentional.
RESTART_NEEDED=false
on_exit() {
  if $RESTART_NEEDED; then
    if leave_down_intentional; then
      log "exit trap: leave-down marker present — daemon stays down"
    else
      log "exit trap: ensuring daemon restart"
      start_and_wait
    fi
    RESTART_NEEDED=false
  fi
}
trap on_exit EXIT

# 1. Observe the daemon. The daemon-active gate runs first among the
# daemon-state checks: an actively-used daemon is left entirely alone.
# Every other decision waits for change detection (step 2), so a down
# daemon is never restarted just to be stopped again for the copy.
DAEMON_UP=false
if daemon_healthy; then
  DAEMON_UP=true
  log "daemon healthy"
  log_memory

  # Idle gate (verbatim semantics): a missing timestamp means the daemon
  # predates on-demand tracking — treat it as idle so the old always-on
  # instance is swept on the first run.
  now="$(date +%s)"
  last_use="$(cat "$LAST_USE_FILE" 2>/dev/null || true)"
  if [ -n "$last_use" ] && [ "$now" -lt "$((last_use + IDLE_SECS))" ]; then
    log "daemon active (last client use $((now - last_use))s ago) — leaving it running"
    exit 0
  fi
  log "daemon idle (last client use: ${last_use:-never}) — proceeding to backup decision"
fi

# 2. Change detection BEFORE any stop/restart decision: a live sha256sum
# read is safe here — it is only change detection. A torn read can only
# trigger a redundant backup cycle, never a missed one; the authoritative
# copy is still taken with the daemon stopped in step 5.
if [ ! -f "$DB" ]; then
  log "no DB file yet — nothing to back up"
  exit 0
fi

NOW_SHA="$(sha256sum "$DB" | awk '{print $1}')"
LAST_SHA="$(cat "$SHA_FILE" 2>/dev/null || true)"
DB_CHANGED=true
if [ -n "$LAST_SHA" ] && [ "$NOW_SHA" = "$LAST_SHA" ]; then
  DB_CHANGED=false
fi

# 3. Daemon-down lifecycle decision (the header's step 1, taken here —
# after change detection, per the deployed ordering).
if ! $DAEMON_UP; then
  if leave_down_intentional; then
    log "daemon down and leave-down marker present ($LEAVE_DOWN_MARKER) — down state is intentional, leaving it down"
    exit 0
  fi
  if ! $DB_CHANGED; then
    log "daemon down unexpectedly — restarting it (no DB changes to back up)"
    start_and_wait
    # The DB is unchanged, but the Drive tier may still be behind.
    if ! drive_catch_up "$NOW_SHA"; then
      exit 1
    fi
    log "done"
    exit 0
  fi
  log "daemon down — taking the backup while it is down; will restart after the copy"
fi

# 4. Unchanged DB, daemon up: never stop the daemon for nothing.
if ! $DB_CHANGED; then
  log "no DB changes (sha256 ${NOW_SHA:0:12}…) — skipping backup"
  # The DB is unchanged, but the Drive tier may still be behind (it was
  # unconfigured or failed when this state was backed up). Catch it up.
  if ! drive_catch_up "$NOW_SHA"; then
    exit 1
  fi
  prune_staging
  log "done"
  exit 0
fi

# 5. Changed DB: quiesce, copy, verify, restart.
if [ -z "$LAST_SHA" ]; then
  log "no previous checksum — taking first backup"
else
  log "DB changed (${LAST_SHA:0:12}… -> ${NOW_SHA:0:12}…) — stopping daemon for a consistent copy"
fi

# A daemon that will not stop fails the run loudly (exit 1): copying a
# live DB would produce exactly the torn backup this step exists to
# prevent, and silently skipping used to mask a wedged daemon forever.
if ! stop_daemon; then
  log "ERROR: daemon would not stop — backup skipped, daemon left running"
  exit 1
fi
# From here to the restart, the EXIT trap owes the daemon a restart.
RESTART_NEEDED=true

# Backup + verify: hash the exact bytes being copied, taken immediately
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

# Restart now that the copy is safe, and poll health (step 3 of the
# header): the daemon must never be left down by this script.
start_and_wait
RESTART_NEEDED=false

# Archive logs with the backup for forensics.
archive_logs "$TS"

# The local tier is complete: record it now, independently of Drive. A
# failing Drive upload must not force a redundant daemon stop/copy cycle on
# the next run — the catch-up path re-uploads from staging instead.
echo -n "$CP_SHA" >"$SHA_FILE"

# 6. Upload to Google Drive when configured. Drive is an optional tier: if
# the folder id file or hatch_gws_cli is missing, log a loud warning and
# keep the local backup as the only tier (exit 0) — but do NOT mark the
# Drive tier done, so a later run uploads this backup once Drive is
# configured (see drive_catch_up). Only a *configured but failing* upload
# exits 1.
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

# 7. Prune local staging, keep 3 most recent
prune_staging
log "done"
