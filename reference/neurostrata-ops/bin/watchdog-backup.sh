#!/usr/bin/env bash
# watchdog-backup.sh — NeuroStrata daemon watchdog + change-detected DB backup.
#
# Adapted for this VM from the autonomous-engineering-platform reference
# (~/workspace/repos/autonomous-engineering-platform/scripts/watchdog-backup.sh).
# Differences from the reference:
#   - Binary lives at ~/go/bin/neurostrata-mcp (not ~/workspace/neurostrata/bin).
#   - No MCP client exists here; the watchdog restarts the daemon directly
#     with nohup instead of triggering an MCP spawn.
#   - Daemon log is ~/.local/share/neurostrata/daemon.log (appended, kept).
#   - Google Drive upload is OPTIONAL: it runs only when
#     ~/workspace/neurostrata/.drive-database-folder-id exists and is non-empty
#     (and hatch_gws_cli is present). Otherwise the local backup is the only
#     tier and the run still exits 0.
#   - Change detection runs BEFORE stopping the daemon: an unchanged DB means
#     no stop at all, and no restart unless the daemon is unexpectedly down
#     (a daemon cleanly reaped by the idle reaper is left down).
#
# Every run:
#   1. Watchdog: observe daemon state. Change detection runs before any
#      restart decision: the old order restarted a reaped daemon only to
#      stop it again for the backup copy.
#   2. sha256 the DB. If unchanged since .last-db-sha256:
#      - daemon up: log, catch up the Drive tier, exit 0.
#      - daemon down via idle-reaper: leave it down (restarts on demand),
#        catch up the Drive tier, exit 0.
#      - daemon down unexpectedly: restart it, catch up Drive, exit 0.
#   3. On change: SIGTERM the daemon if running (graceful checkpoint), wait
#      up to 30s, copy the DB with cp -p, sha256-verify the copy against the
#      hash taken immediately before the copy. On mismatch: delete the copy,
#      exit 1. An EXIT trap guarantees the daemon is restarted even if later
#      steps fail (unless the run intentionally left a reaped daemon down).
#   4. Restart the daemon with HF_HUB_OFFLINE=1 and poll health up to 60s
#      (cold start loads a 547MB model and can exceed the old 12s window).
#   5. Optional Drive upload with one in-run retry (never fails the run).
#   6. Record the checksum, prune staging to the 3 newest copies.
#
# Exit 0 unless the backup copy itself failed verification.
set -euo pipefail

BIN="$HOME/go/bin/neurostrata-mcp"
DB="$HOME/.config/NeuroStrata/data/db/ladybug.db"
DAEMON_LOG="$HOME/.local/share/neurostrata/daemon.log"
STAGE="$HOME/workspace/neurostrata/backups"
SHA_FILE="$HOME/workspace/neurostrata/.last-db-sha256"
DRIVE_SHA_FILE="$HOME/workspace/neurostrata/.last-drive-sha256"
FOLDER_ID_FILE="$HOME/workspace/neurostrata/.drive-database-folder-id"
LOG="$HOME/workspace/neurostrata/watchdog.log"
LOCK="$HOME/workspace/neurostrata/.watchdog.lock"
REAPER_LOG="$HOME/workspace/neurostrata/reaper.log"
GWS_CLI="/opt/hatch/bin/hatch_gws_cli"
export HF_HUB_OFFLINE=1
# Pin UTC so every timestamp this script writes and every timestamp it
# compares (watchdog.log, reaper.log) shares one timezone. The cron
# environment already runs UTC; without this, a manual run under a local TZ
# would write mixed-timezone lines and corrupt recency comparisons.
export TZ=UTC

log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
mkdir -p "$STAGE"

# Concurrency guard: two overlapping runs must never SIGTERM/copy together.
exec 9>"$LOCK"
flock -n 9 || { log "another watchdog run in progress — exiting"; exit 0; }

daemon_healthy() { "$BIN" status 2>/dev/null | grep -q "status: healthy"; }

drive_configured() { [ -x "$GWS_CLI" ] && [ -s "$FOLDER_ID_FILE" ]; }

# Upload the newest staged backup to Drive and record it. Runs both after a
# fresh backup and on no-change runs, so a backup taken while Drive was
# unconfigured (or failed) is uploaded once Drive becomes available — the
# local checksum alone must never mark the Drive tier done.
drive_catch_up() {
  # $1 = sha256 of the DB state the staged backup must match
  local want_sha="$1" drive_sha newest fsha folder_id name upload_diag
  drive_configured || return 0
  drive_sha="$(cat "$DRIVE_SHA_FILE" 2>/dev/null || true)"
  if [ -n "$drive_sha" ] && [ "$drive_sha" = "$want_sha" ]; then
    return 0
  fi
  # "Newest" = greatest filename-embedded timestamp (db-YYYYMMDD-HHMMSS.db
  # sorts chronologically), never greatest mtime: staged copies are made
  # with cp -p, so a copy of a restored DB carries the old backup's mtime
  # and mtime ordering would pick a stale copy. (Overseer A2, 2026-10-26.)
  newest="$(ls -1 "$STAGE"/db-*.db 2>/dev/null | sort -r | head -1 || true)"
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
  if upload_diag="$("$GWS_CLI" drive +upload "$newest" --parent "$folder_id" --name "$name" 2>&1)"; then
    log "uploaded to Drive (folder ${folder_id:0:12}…): $name"
    echo -n "$want_sha" > "$DRIVE_SHA_FILE"
  else
    # One transient Google-side 500 hit on 2026-10-21; retry in-run before
    # paging — a single failure should not become a chat alert.
    log "WARNING: Drive catch-up upload failed (${upload_diag:0:200}) — retrying once in 30s"
    sleep 30
    if upload_diag="$("$GWS_CLI" drive +upload "$newest" --parent "$folder_id" --name "$name" 2>&1)"; then
      log "uploaded to Drive on retry (folder ${folder_id:0:12}…): $name"
      echo -n "$want_sha" > "$DRIVE_SHA_FILE"
    else
      log "ERROR: Drive catch-up upload failed twice (${upload_diag:0:200}) — will retry next run"
      return 1
    fi
  fi
}

start_daemon() {
  log "starting daemon (HF_HUB_OFFLINE=1)"
  # Rotate the daemon log before (re)start so crash evidence is preserved
  # across restarts instead of growing unboundedly in one file.
  # (2026-10-21, #21 investigation Task 1 — reversible by deleting this block.)
  if [ -f "$DAEMON_LOG" ]; then
    mv "$DAEMON_LOG" "$DAEMON_LOG.$(date +%Y%m%d-%H%M%S)"
  fi
  # keep the last 10 rotations
  # Guarded (|| true): with no rotations present (fresh instance, cleared
  # logs) ls exits 2, and under set -euo pipefail that aborted start_daemon()
  # before the daemon ever spawned — the zero-rotation state is exactly the
  # fresh-instance state this function exists to recover. (Overseer C1,
  # 2026-10-26; same failure class as the 2026-10-22 ulimit abort below.)
  ls -1t "$DAEMON_LOG".* 2>/dev/null | tail -n +11 | xargs -r rm -f || true
  # 9>&- : do NOT let the daemon inherit the flock FD — otherwise every future
  # run sees the lock as held by the live daemon and refuses to start.
  # Enable core dumps for #21 diagnosis: a native abort leaves a core file
  # in the daemon's cwd (the daemon's working directory, per core_pattern); SIGKILL leaves none.
  # The canary (watch-daemon-death.sh) uses this to tell them apart.
  # (2026-10-22, #21 — reversible by deleting this line.)
  # 2026-10-22 late fix: guarded — this VM's hard core limit is 0 and an
  # unprivileged shell cannot raise it, so the bare call failed under set -e
  # and aborted start_daemon() before the daemon ever spawned (daemon down
  # after 2 watchdog attempts, 23:01 CDT run). Core dumps stay off here;
  # the canary cannot use core files on this VM.
  ulimit -c unlimited 2>/dev/null || true
  HF_HUB_OFFLINE=1 nohup "$BIN" daemon >> "$DAEMON_LOG" 2>&1 9>&- &
}

# Poll daemon_healthy every 5s until it passes or $1 seconds elapse
# (default 60). The old fixed 12s sleep proved too short: cold start loads a
# 547MB embedding model and sometimes needs 12-14s+ under memory pressure,
# which produced false "daemon still down after restart attempt" ERRORs.
wait_healthy() {
  local deadline=$(( SECONDS + ${1:-60} ))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if daemon_healthy; then
      return 0
    fi
    sleep 5
  done
  if daemon_healthy; then
    return 0
  fi
  return 1
}

# The idle reaper (every 15 min) clean-shuts the daemon after 45 idle minutes,
# so "down at start" is usually expected, not a failure. The down state is
# reaper-expected iff the most recent REAPED line in the reaper log is newer
# than the watchdog's most recent daemon start — i.e. nothing restarted the
# daemon since the reaper shut it down. Timestamps are compared as UTC
# epochs (TZ is pinned above) so mixed-timezone log lines cannot corrupt
# the comparison. Defaults to false (restart) when the evidence is missing
# or ambiguous: an unexpectedly crashed daemon must always be restarted.
reaped_expected() {
  local r w re we
  # The || true guards keep a no-match grep (a legitimate state) from
  # aborting the caller under set -euo pipefail: this function must return
  # its classification, never kill the script, whatever context calls it.
  r="$(grep "REAPED" "$REAPER_LOG" 2>/dev/null | tail -1 | sed 's/^\[//;s/\].*//' || true)"
  w="$(grep -E "starting daemon|daemon (restarted, healthy|recovered)" "$LOG" 2>/dev/null | tail -1 | sed 's/^\[//;s/\].*//' || true)"
  if [ -z "$r" ]; then
    return 1
  fi
  if [ -z "$w" ]; then
    return 0
  fi
  re="$(date -d "$r" +%s 2>/dev/null || echo 0)"
  we="$(date -d "$w" +%s 2>/dev/null || echo 0)"
  [ "$re" -gt "$we" ]
}

# --- EXIT trap: the daemon must never be left down by this script. ---
RESTART_NEEDED=false
on_exit() {
  if $RESTART_NEEDED; then
    log "exit trap: ensuring daemon restart"
    start_daemon
    if wait_healthy; then
      log "exit trap: daemon restarted, healthy"
    else
      log "exit trap: ERROR — daemon still down; next watchdog run will retry"
    fi
    RESTART_NEEDED=false
  fi
}
trap on_exit EXIT

# 1. Watchdog: observe state first. The restart decision comes after change
# detection (step 2): the old order restarted a reaped daemon only to stop
# it again for the backup copy.
DAEMON_WAS_UP=false
if daemon_healthy; then
  DAEMON_WAS_UP=true
fi
REAPED_DOWN=false
if ! $DAEMON_WAS_UP && reaped_expected; then
  REAPED_DOWN=true
fi

# 2. Change detection (live read; no stop needed when unchanged)
if [ ! -f "$DB" ]; then
  log "no DB file yet — nothing to back up"
  exit 0
fi
NOW_SHA="$(sha256sum "$DB" | awk '{print $1}')"
LAST_SHA="$(cat "$SHA_FILE" 2>/dev/null || true)"
if [ -n "$LAST_SHA" ] && [ "$NOW_SHA" = "$LAST_SHA" ]; then
  if $DAEMON_WAS_UP; then
    log "watchdog: daemon healthy; no DB changes (sha256 ${NOW_SHA:0:12}…) — skipping backup"
  elif $REAPED_DOWN; then
    # The idle reaper intentionally shut the daemon down and nothing needs
    # it. Leave it down — MCP demand-spawn or a later watchdog restarts it.
    log "watchdog: daemon down (reaped by idle-reaper, expected); no DB changes — leaving it down"
  else
    log "watchdog: daemon down unexpectedly — restarting directly"
    start_daemon
    if wait_healthy; then
      log "watchdog: daemon recovered"
    else
      log "watchdog: ERROR — daemon still down after restart attempt"
    fi
  fi
  # The DB is unchanged, but the Drive tier may still be behind (it was
  # unconfigured or failed when this state was backed up). Catch it up.
  if ! drive_catch_up "$NOW_SHA"; then
    exit 1
  fi
  exit 0
fi
if [ -z "$LAST_SHA" ]; then
  log "no previous checksum — taking first backup"
else
  log "DB changed (${LAST_SHA:0:12}… -> ${NOW_SHA:0:12}…) — stopping daemon for a consistent copy"
fi

# 3. Stop the daemon for a checkpoint-consistent copy
PID="$(pgrep -f '[n]eurostrata-mcp daemon' | head -1 || true)"
if [ -n "$PID" ]; then
  log "stopping daemon (pid $PID)"
  kill -TERM "$PID" || true
  for _ in $(seq 1 30); do
    pgrep -f '[n]eurostrata-mcp daemon' >/dev/null || break
    sleep 1
  done
  if pgrep -f '[n]eurostrata-mcp daemon' >/dev/null; then
    log "ERROR: daemon did not exit in 30s — skipping backup this run (daemon left running)"
    exit 0
  fi
  log "daemon stopped"
  RESTART_NEEDED=true
else
  log "daemon was not running — will start it after the backup"
  RESTART_NEEDED=true
fi

# 4. Copy + verify against the hash of the exact bytes copied
TS="$(date +%Y%m%d-%H%M%S)"
STAGE_FILE="$STAGE/db-$TS.db"
SRC_SHA="$(sha256sum "$DB" | awk '{print $1}')"
cp -p "$DB" "$STAGE_FILE"
CP_SHA="$(sha256sum "$STAGE_FILE" | awk '{print $1}')"
if [ "$CP_SHA" != "$SRC_SHA" ]; then
  log "ERROR: backup checksum mismatch (copy ${CP_SHA:0:12}… vs source ${SRC_SHA:0:12}…) — bad copy deleted"
  rm -f "$STAGE_FILE"
  exit 1
fi
log "local backup OK: $STAGE_FILE (sha256 ${CP_SHA:0:12}…)"

# 5. Restart the daemon now that the copy is safe
start_daemon
if wait_healthy; then
  log "daemon restarted, healthy"
else
  log "ERROR: daemon failed to restart — next watchdog run will retry"
fi
RESTART_NEEDED=false

# The local tier is complete: record it now, independently of Drive.
echo -n "$CP_SHA" > "$SHA_FILE"

# 6. Optional Google Drive upload (never fails the run). Two watermarks:
# .last-db-sha256 = a verified local copy exists; .last-drive-sha256 = that
# state was uploaded. Never mark the Drive tier done without a success —
# drive_catch_up repairs the gap on a later run.
if drive_configured; then
  FOLDER_ID="$(cat "$FOLDER_ID_FILE")"
  NAME="ladybug-$TS.db"
  if upload_diag="$("$GWS_CLI" drive +upload "$STAGE_FILE" --parent "$FOLDER_ID" --name "$NAME" 2>&1)"; then
    log "uploaded to Drive (folder ${FOLDER_ID:0:12}…): $NAME"
    echo -n "$CP_SHA" > "$DRIVE_SHA_FILE"
  else
    log "WARNING: Drive upload failed (${upload_diag:0:200}) — retrying once in 30s"
    sleep 30
    if upload_diag="$("$GWS_CLI" drive +upload "$STAGE_FILE" --parent "$FOLDER_ID" --name "$NAME" 2>&1)"; then
      log "uploaded to Drive on retry (folder ${FOLDER_ID:0:12}…): $NAME"
      echo -n "$CP_SHA" > "$DRIVE_SHA_FILE"
    else
      log "ERROR: Drive upload failed twice (${upload_diag:0:200}) — local backup retained at $STAGE_FILE; will retry next run"
    fi
  fi
else
  log "WARNING: Drive upload not configured — local backup is the only tier"
fi

# 8. Prune staging to the 3 newest copies. Ordering is by the timestamp
# embedded in the filename (db-YYYYMMDD-HHMMSS.db sorts chronologically),
# never by mtime: copies are made with cp -p, so a staged copy of a
# restored DB carries the old backup's mtime, and mtime ordering pruned
# the newest backup first — right after its checksum was recorded in
# .last-db-sha256. (Overseer A2, 2026-10-26.) The copy the local
# watermark references (matched by content hash — the watermark stores
# a sha256, not a filename) is never pruned. Guarded (|| true) like the
# rotation prune in start_daemon(): an empty staging dir is a no-op,
# not an abort under set -euo pipefail. (Overseer A1.)
WM_SHA="$(cat "$SHA_FILE" 2>/dev/null || true)"
ls -1 "$STAGE"/db-*.db 2>/dev/null | sort -r | tail -n +4 | while IFS= read -r old; do
  if [ -n "$WM_SHA" ] && [ "$(sha256sum "$old" | awk '{print $1}')" = "$WM_SHA" ]; then
    log "prune: keeping $(basename "$old") — referenced by .last-db-sha256"
    continue
  fi
  rm -f "$old"
done || true
log "done"
exit 0
