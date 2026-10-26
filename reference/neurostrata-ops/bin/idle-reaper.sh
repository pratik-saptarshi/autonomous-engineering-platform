#!/usr/bin/env bash
# idle-reaper.sh — NeuroStrata idle daemon reaper
# Created: 2026-10-19 (Task 2 of the idle-reaper plan, plan: ~/workspace/plans/2026-10-19-neurostrata-idle-reaper.md)
# Purpose: shut the NeuroStrata daemon down cleanly after it has sat idle,
#   freeing ~800MB RSS. Restart is on-demand and needs no new code:
#   - MCP stdio mode auto-spawns a detached daemon if none is running
#     (src/main.rs:1399, verified in source)
#   - the neurostrata-watchdog cron restarts a down daemon every 2h
# Task 1 cold-start gate: COLD_START_HEALTHY_S=5, FIRST_SEARCH=n/a, gate PASS
#   (cold start 5s << the ~30s MCP auto-start wait budget; rollout approved)
#
# Reaps ONLY when ALL hold (checked in this order):
#   1. watchdog lock is free
#   2. daemon is healthy (via `neurostrata-mcp status` — does NOT load the model)
#   3. zero established TCP connections on 127.0.0.1:34343
#   4. daemon uptime >= REAPER_MIN_UPTIME_MIN (default 45)
#   5. no other neurostrata-mcp CLI process is active
# Shutdown is ONLY via `neurostrata-mcp shutdown` (clean checkpoint) — never kill.
# Exit 0 on every path; one line per run to REAPER_LOG, silent otherwise.
set -u

BIN="$HOME/go/bin/neurostrata-mcp"
LOCK="${REAPER_LOCK_FILE:-$HOME/workspace/neurostrata/.watchdog.lock}"
LOG="${REAPER_LOG:-$HOME/workspace/neurostrata/reaper.log}"
MIN_UPTIME_MIN="${REAPER_MIN_UPTIME_MIN:-45}"
PORT=34343

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { printf '[%s] %s\n' "$(ts)" "$1" >> "$LOG"; }

# --- (1) watchdog lock: check-and-exit, never hold while doing anything else ---
exec 9>"$LOCK"
if ! flock -n 9; then
    log "SKIP lock-held (watchdog running)"
    exit 0
fi
# Close FD 9 immediately: nothing spawned below may inherit the flock FD,
# or later runs would falsely report "another run in progress" (see watchdog).
9>&-

# --- (2) daemon healthy? (`status` is model-load-free per Task 1) ---
if ! "$BIN" status 2>/dev/null | grep -q "status: healthy"; then
    log "SKIP daemon-not-running"
    exit 0
fi

# --- (3) any established client connections on the daemon port? ---
if ss -Htn state established "( dport = $PORT )" 2>/dev/null | grep -q .; then
    log "SKIP active-connections"
    exit 0
fi

# --- (4) daemon uptime >= threshold? ---
DAEMON_PID="$(pgrep -f "neurostrata-mcp daemon" 2>/dev/null | head -1)"
if [ -z "$DAEMON_PID" ]; then
    log "SKIP daemon-not-running (no daemon PID despite healthy status)"
    exit 0
fi
UPTIME_S="$(ps -o etimes= -p "$DAEMON_PID" 2>/dev/null | tr -d ' ')"
if [ -z "$UPTIME_S" ] || [ "$UPTIME_S" -lt $((MIN_UPTIME_MIN * 60)) ]; then
    log "SKIP uptime-too-low (uptime=${UPTIME_S:-?}s < $((MIN_UPTIME_MIN * 60))s)"
    exit 0
fi
UPTIME_MIN=$((UPTIME_S / 60))

# --- (5) any other neurostrata-mcp CLI process active? ---
# Exclude: the daemon PID, this script itself, and this script's children.
# (pgrep also excludes itself from matches by definition.)
SELF="$$"
CHILDREN="$(pgrep -P "$SELF" 2>/dev/null | tr '\n' ' ')"
OTHER=""
for pid in $(pgrep -f "neurostrata-mcp" 2>/dev/null); do
    [ "$pid" = "$DAEMON_PID" ] && continue
    [ "$pid" = "$SELF" ] && continue
    case " $CHILDREN " in
        *" $pid "*) continue ;;
    esac
    OTHER="$OTHER $pid"
done
if [ -n "$OTHER" ]; then
    log "SKIP cli-active (pids:$OTHER)"
    exit 0
fi

# --- (6) all clear: clean shutdown ---
if "$BIN" shutdown >/dev/null 2>&1; then
    log "REAPED uptime=${UPTIME_MIN}m conns=0"
else
    log "SKIP shutdown-failed (clean shutdown returned non-zero; daemon left alone)"
fi
exit 0
