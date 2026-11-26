#!/usr/bin/env bash
# watchdog-backup.sh — NeuroStrata daemon watchdog + change-detected DB backup.
#
# Every run (on-demand model; requires Linux /proc, flock, and GNU coreutils):
#   1. Daemon-down is the expected idle state, not an error: if the daemon
#      is down, still run change detection, and back up a changed DB as a
#      quiescent copy (no writer, so no stop ceremony is needed). The
#      daemon stays down afterwards; restart it directly with nohup when
#      needed (a bare MCP spawn does not reliably start the daemon). This
#      script never restarts the daemon itself.
#   2. Checksum the DB. If unchanged since the last backup, log and exit 0 —
#      except on the daemon-down path, where a failed Drive catch-up exits
#      1 — but first run drive_catch_up: the Drive tier may be behind even
#      when the DB is unchanged (it was unconfigured or failed when this
#      state was backed up). Note: on the idle path, the daemon IS stopped
#      by design after the no-change check, but only when its activity marker
#      exists and is older than IDLE_SECS and it has no established client
#      connection; see "Activity" below.
#   3. On change with the daemon up: SIGTERM the daemon (graceful
#      checkpoint), copy the DB, sha256-verify the copy against a hash
#      taken immediately before the copy, and record the local checksum
#      (.last-db-sha256) independently of Drive. The daemon stays down
#      afterwards; restart it directly with nohup when needed (never
#      rely on a bare MCP spawn).
#   4. Upload the copy to Google Drive when configured (folder id file +
#      hatch_gws_cli present) and record .last-drive-sha256; otherwise the
#      local backup is the only tier and the run still succeeds — the Drive
#      checksum stays stale so a later run uploads this backup once Drive
#      is configured. Prune staging.
#
# Activity: stopping a daemon someone is using is worse than postponing a
# backup. The watchdog stops a healthy daemon only when
# ~/workspace/neurostrata/.last-daemon-use exists, is numeric, is older than
# IDLE_SECS, and `ss` shows no established loopback connection to the daemon
# port. A missing or unreadable marker means "activity unknown", so the daemon
# is left running. ops/bin/cron-with-boot-gate.sh heartbeats the marker for
# the duration of a gated job; a direct MCP client that does not write the
# marker is covered by the connection check when `ss` is available.
#
# Crash evidence: this script never restarts the daemon, but it must not let
# a restart destroy the evidence of a death either. A down daemon is
# "unexpected" when this watchdog did not stop it: it saw the daemon healthy
# (.daemon-seen-up), a client used it after the last accounted stop
# (.last-daemon-use newer than .daemon-down-accounted), or daemon.log was
# written after the last accounted stop (a start-and-die between runs with no
# client hook), and no intentional stop was recorded since. On an unexpected
# death, and ONLY then, it writes logs/crash-<UTC>.log (owner-only) and moves
# daemon.log aside to daemon.log.<UTC>.pre-restart (also owner-only). Both are
# capped at 10 files. An idle stop by this script is intentional and never
# produces a bundle. If the bundle cannot be created, the run leaves the death
# unaccounted so the next run retries.
#
# Two watermarks, two tiers: .last-db-sha256 = a verified local copy exists;
# .last-drive-sha256 = that state was uploaded. Never mark the Drive tier
# done without a successful upload.
#
# The upstream backup.sh needs systemd; this environment has no user D-Bus,
# so SIGTERM replaces `systemctl stop/start`. Exit 0 unless the backup copy
# itself failed verification, a configured Drive upload failed, (on the
# daemon-down no-change path) Drive catch-up failed, or the daemon would
# not stop (a wedged daemon fails loudly — never a silent skip).
set -euo pipefail
umask 077

DB="$HOME/.config/NeuroStrata/data/db/ladybug.db"
STAGE="$HOME/workspace/neurostrata/backups"
SHA_FILE="$HOME/workspace/neurostrata/.last-db-sha256"
DRIVE_SHA_FILE="$HOME/workspace/neurostrata/.last-drive-sha256"
FOLDER_ID_FILE="$HOME/workspace/neurostrata/.drive-database-folder-id"
LOG="$HOME/workspace/neurostrata/watchdog.log"
export HF_HUB_OFFLINE=1

log() {
  local msg
  msg="[$(date '+%F %T')] $*"
  printf '%s\n' "$msg" | tee -a "$LOG" 2>/dev/null || printf '%s\n' "$msg"
}
mkdir -p "$STAGE"

resolve_bin() {
  if [ -n "${AEP_MCP_BIN:-}" ]; then
    if [ -x "$AEP_MCP_BIN" ]; then
      BIN="$AEP_MCP_BIN"
      return 0
    fi
    log "ERROR: AEP_MCP_BIN ($AEP_MCP_BIN) is not executable"
    return 1
  fi
  if [ -x "$HOME/go/bin/neurostrata-mcp" ]; then
    BIN="$HOME/go/bin/neurostrata-mcp"
    return 0
  fi
  if [ -x "$HOME/workspace/neurostrata/bin/neurostrata-mcp" ]; then
    BIN="$HOME/workspace/neurostrata/bin/neurostrata-mcp"
    return 0
  fi
  if command -v neurostrata-mcp >/dev/null 2>&1; then
    BIN="$(command -v neurostrata-mcp)"
    return 0
  fi
  log "ERROR: neurostrata-mcp not found in ~/go/bin, ~/workspace/neurostrata/bin, or PATH"
  return 1
}

BIN=""
resolve_bin

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
    chmod 600 "$archive" 2>/dev/null || true
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
DAEMON_LOG="$HOME/workspace/neurostrata/daemon.log"
# Written when a healthy daemon is observed, removed once a down state is
# accounted for. Its presence on a down daemon means "it was up and nobody
# stopped it".
SEEN_UP_FILE="$HOME/workspace/neurostrata/.daemon-seen-up"
# "<epoch> <reason>", written when a down state is accounted for (an
# intentional stop by this script, a captured death, or a bootstrap).
ACCOUNTED_FILE="$HOME/workspace/neurostrata/.daemon-down-accounted"
CRASH_KEEP=10
PRE_RESTART_KEEP=10

# Keep the newest $3 files matching glob $2 in directory $1 (by mtime).
prune_newest() {
  find "$1" -maxdepth 1 -type f -name "$2" -printf '%T@ %p\0' 2>/dev/null | sort -znr | tail -z -n +"$(($3 + 1))" | cut -z -d ' ' -f 2- | xargs -0 -r rm -f
}

# Accounting for a down state: remember when, and why, so a later run can tell
# an intentional stop from a death. Best-effort: never aborts a backup run.
mark_down_accounted() {
  rm -f "$SEEN_UP_FILE" 2>/dev/null || true
  if ! echo "$(date +%s) $1" >"$ACCOUNTED_FILE" 2>/dev/null; then
    log "WARNING: cannot write $ACCOUNTED_FILE — crash classification degraded"
  fi
}

# True when the daemon is down and this watchdog did not stop it. With no
# history at all (a first run, or a fresh deploy) it never guesses: it records
# the baseline and reports "not unexpected".
daemon_died_unexpectedly() {
  local last_use accounted log_mtime
  [ -f "$SEEN_UP_FILE" ] && return 0
  if [ ! -f "$ACCOUNTED_FILE" ]; then
    mark_down_accounted bootstrap
    return 1
  fi
  accounted="$(cut -d ' ' -f 1 "$ACCOUNTED_FILE" 2>/dev/null || true)"
  case "$accounted" in
  '' | *[!0-9]*) return 1 ;;
  esac
  last_use="$(cat "$LAST_USE_FILE" 2>/dev/null || true)"
  case "$last_use" in
  '' | *[!0-9]*) last_use=0 ;;
  esac
  if [ "$last_use" -gt "$accounted" ]; then return 0; fi
  # No client hook wrote .last-daemon-use, but daemon.log was appended to
  # after the last accounted down state: a daemon started and died between
  # watchdog observations. An idle daemon writes nothing to this log.
  log_mtime="$(stat -c %Y "$DAEMON_LOG" 2>/dev/null || stat -f %m "$DAEMON_LOG" 2>/dev/null || echo 0)"
  case "$log_mtime" in
  '' | *[!0-9]*) log_mtime=0 ;;
  esac
  [ "$log_mtime" -gt "$accounted" ]
}

# Move daemon.log aside before anything restarts the daemon. The old restart
# command truncated it (`> daemon.log`), which destroyed the only evidence of
# an overnight death. The rotated copy is never touched by a restart.
rotate_daemon_log() {
  local ts target n
  [ -s "$DAEMON_LOG" ] || return 0
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  target="$DAEMON_LOG.$ts.pre-restart"
  n=1
  while [ -e "$target" ]; do
    target="$DAEMON_LOG.$ts-$n.pre-restart"
    n=$((n + 1))
  done
  if ! mv -f "$DAEMON_LOG" "$target" 2>/dev/null; then
    log "WARNING: pre-restart log rotation failed (non-fatal)"
    return 0
  fi
  # The retained log may have been group- or world-readable; umask does not
  # apply to a file that already existed. Restrict it now that it holds crash
  # evidence.
  chmod 600 "$target" 2>/dev/null || true
  log "preserved pre-restart daemon log: $target"
  prune_newest "$(dirname "$DAEMON_LOG")" 'daemon.log.*.pre-restart' "$PRE_RESTART_KEEP" || true
}

run_probe() {
  if command -v timeout >/dev/null 2>&1; then
    timeout 10 "$@"
  else
    "$@"
  fi
}

# One crash bundle per unexpected death. Every probe is best effort: a probe
# that fails is recorded as such and never fails the watchdog run.
capture_death_diagnostics() {
  local ts out tmp n captured=0
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  if [ -L "$LOGS_DIR" ] || ! mkdir -p "$LOGS_DIR" 2>/dev/null; then
    log "WARNING: cannot use $LOGS_DIR — crash bundle skipped"
  else
    out="$LOGS_DIR/crash-$ts.log"
    n=1
    while [ -e "$out" ]; do
      out="$LOGS_DIR/crash-$ts-$n.log"
      n=$((n + 1))
    done
    tmp="$(mktemp "$LOGS_DIR/.crash-$ts.XXXXXX" 2>/dev/null || true)"
    if [ -n "$tmp" ]; then
      (
        umask 077
        {
          echo "crash bundle captured $(date -u +%Y-%m-%dT%H:%M:%SZ)"
          echo "== last 100 lines of daemon.log =="
          tail -n 100 "$DAEMON_LOG" 2>&1 || echo "(daemon.log unreadable)"
          echo "== kernel OOM hints (dmesg) =="
          { run_probe dmesg 2>&1 || echo "(dmesg unreadable)"; } | { grep -iE 'out of memory|oom-kill|oom_reaper|killed process|memory cgroup|neurostrata|unreadable' || echo "(no OOM hints found)"; } | tail -n 50
          echo "== free -m =="
          run_probe free -m 2>&1 || echo "(free unavailable)"
          echo "== df -h =="
          run_probe df -h 2>&1 || echo "(df unavailable)"
          echo "== ulimit -a =="
          ulimit -a 2>&1 || echo "(ulimit unavailable)"
          echo "== neurostrata-mcp --version =="
          run_probe "$BIN" --version 2>&1 || echo "(version unavailable)"
        } >"$tmp" 2>&1
      ) || true
      chmod 600 "$tmp" 2>/dev/null || true
      if mv -f "$tmp" "$out" 2>/dev/null; then
        log "crash diagnostics: $out"
        captured=1
      else
        rm -f "$tmp" 2>/dev/null || true
        log "WARNING: failed to finalize crash bundle $out"
      fi
    else
      log "WARNING: cannot create temp crash bundle in $LOGS_DIR"
    fi
    if [ "$captured" -eq 1 ]; then
      prune_newest "$LOGS_DIR" 'crash-*.log' "$CRASH_KEEP" || true
    fi
  fi
  if [ "$captured" -eq 1 ]; then
    rotate_daemon_log
    mark_down_accounted captured
  else
    # Do not rotate or mark: leave .daemon-seen-up in place so the next run
    # sees the same death and retries the missing evidence.
    log "WARNING: crash diagnostics incomplete — the next run will retry capture"
  fi
}

daemon_healthy() {
  local out
  out="$("$BIN" status 2>/dev/null || true)"
  # The CLI prints "daemon: listening ... answering" and, when it is also the
  # build on disk, "status: healthy". Accept either half so a live daemon is
  # never mistaken for a dead one: copying under a live writer is the failure
  # this predicate exists to prevent, and a false "healthy" only delays a stop.
  case "$out" in
  *"status: healthy"*) return 0 ;;
  *"daemon: listening"*"answering"*) return 0 ;;
  esac
  return 1
}

# Best-effort second activity signal: an established loopback connection to
# the daemon port means a client is attached even when no hook has touched
# .last-daemon-use recently. Missing ss returns "no clients" (fail-open for
# reaping, which is the caller's existing behavior for hosts without ss).
daemon_has_clients() {
  command -v ss >/dev/null 2>&1 || return 1
  [ -n "$(ss -Htn state established '( dport = :34343 or sport = :34343 )' 2>/dev/null || true)" ]
}

# Idle only when a numeric marker is older than IDLE_SECS and no client is
# attached. Missing/unreadable means "unknown", which is not idle.
daemon_idle() {
  local now last_use
  now="$(date +%s)"
  last_use="$(cat "$LAST_USE_FILE" 2>/dev/null || true)"
  case "$last_use" in
  '' | *[!0-9]*) return 1 ;;
  esac
  [ "$now" -ge "$((last_use + IDLE_SECS))" ] || return 1
  ! daemon_has_clients
}

stop_daemon() {
  local PIDS PID
  PIDS="$(pgrep -f '[n]eurostrata-mcp daemon' || true)"
  if [ -z "$PIDS" ]; then
    # Healthy a moment ago, no process now: it died between the check and this
    # stop. Do not record an intentional stop; the caller captures the death.
    log "daemon was already gone when this run tried to stop it"
    return 2
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
  mark_down_accounted intentional
  return 0
}

# 1. On-demand model (2026-10-17): the daemon is no longer always-on. This
# watchdog stops it after IDLE_SECS without use and never restarts it. If it
# is down, that is the expected idle state — but the DB can still drift
# between daemon sessions (2026-10-23: a change from Oct 18 sat ~5 days
# unbacked-up because change detection only ran when the daemon was up). So
# daemon-down runs still do change detection and back up when the DB moved.
# With the daemon down there is no writer, so the DB is quiescent and the
# copy needs no stop/copy ceremony — a plain verified copy is consistent.
if ! daemon_healthy; then
  if daemon_died_unexpectedly; then
    log "WARNING: daemon is down and this watchdog did not stop it — capturing crash diagnostics"
    capture_death_diagnostics
  fi
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
  # Recheck immediately before the copy: an operator may have restarted the
  # daemon after the check at the top of this branch. Apply the same activity
  # gate as the healthy path: a daemon that just came up with a fresh marker
  # or an attached client is in use, so defer the backup instead of stopping
  # the session that just started.
  if daemon_healthy; then
    if ! daemon_idle; then
      log "daemon came up after the down check and is in use — deferring the backup"
      exit 0
    fi
    log "daemon came up after the down check — stopping it before the copy"
    stop_rc=0
    stop_daemon || stop_rc=$?
    case "$stop_rc" in
    0) ;;
    2) capture_death_diagnostics ;;
    *)
      log "ERROR: daemon would not stop — backup skipped, daemon left running"
      exit 1
      ;;
    esac
    NOW_SHA="$(sha256sum "$DB" | awk '{print $1}')"
  fi
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
if ! date +%s >"$SEEN_UP_FILE" 2>/dev/null; then
  log "WARNING: cannot write $SEEN_UP_FILE — crash detection degraded"
fi
log_memory

# 2. Idle check: an actively-used daemon is left alone; an idle one is
# backed up (if changed) and stopped. A missing or unreadable marker cannot
# prove the daemon is idle, so it is treated as active: stopping a daemon an
# operator or an unwired MCP client is using is worse than postponing a
# backup. An established client connection is a second activity signal for a
# marker that only looks stale.
now="$(date +%s)"
last_use="$(cat "$LAST_USE_FILE" 2>/dev/null || true)"
case "$last_use" in
'' | *[!0-9]*)
  log "daemon activity marker missing/unreadable ($LAST_USE_FILE) — cannot prove it is idle, leaving it running"
  exit 0
  ;;
esac
if [ "$now" -lt "$((last_use + IDLE_SECS))" ]; then
  log "daemon active (last client use $((now - last_use))s ago) — leaving it running"
  exit 0
fi
if daemon_has_clients; then
  log "daemon marker is stale but a client connection is established — leaving it running"
  exit 0
fi
log "daemon idle (last client use: ${last_use}) — backing up and stopping"

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
  stop_rc=0
  stop_daemon || stop_rc=$?
  case "$stop_rc" in
  0) ;;
  2) capture_death_diagnostics ;;
  *)
    log "ERROR: daemon would not stop — leaving it running"
    exit 1
    ;;
  esac
  log "done (daemon idle, unchanged)"
  exit 0
fi

# 3. Quiesce: SIGTERM the daemon so the copy is checkpoint-consistent.
# On-demand model: the daemon stays down after this; restart it directly
# with nohup when needed (a bare MCP spawn does not reliably start it).
# A daemon that will not stop fails the run loudly (exit 1): copying a
# live DB would produce exactly the torn backup this step exists to
# prevent, and silently skipping used to mask a wedged daemon forever.
# rc=2 means it vanished between the healthy check and the signal: capture
# that death instead of pretending this run stopped it.
stop_rc=0
stop_daemon || stop_rc=$?
case "$stop_rc" in
0) ;;
2) capture_death_diagnostics ;;
*)
  log "ERROR: daemon would not stop — backup skipped, daemon left running"
  exit 1
  ;;
esac

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

# Daemon stays down (on-demand model); restart it directly with nohup when needed.

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
