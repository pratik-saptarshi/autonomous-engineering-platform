#!/usr/bin/env bash
# cron-with-boot-gate.sh: run a scheduled job only when the boot gate passes.
#
# Usage:
#   ops/bin/cron-with-boot-gate.sh <job-name> -- <command...>
#
# Runs the gate first (AEP_BOOT_GATE_BIN, default scripts/boot-gate.sh in this
# repo). When the gate passes, the wrapper replaces itself with <command...>
# through exec, so the job's own exit status reaches the scheduler unchanged.
# When the gate fails, or cannot be run at all, the wrapper logs
# "CRON-GATE: ABORT <job-name> rc=<rc>" on stderr and exits with the gate's
# status without starting the job. A missing or non-executable gate counts as
# a failure with rc=127: the wrapper never runs a job it could not gate.
#
# AEP_CRON_GATE_LOG, when set, is a file that also receives the ABORT line.
# Exit 2 is a usage error and runs neither the gate nor the job.
#
# Do NOT wrap the NeuroStrata watchdog job (neurostrata-watchdog). The gate
# needs an answering daemon, and the watchdog is the job that backs up and
# captures crash evidence while the daemon is down. It never restarts the
# daemon (restart it directly with nohup when needed), so gating it would block
# crash capture and quiescent backups without enabling any recovery.
# See ops/crons/CRONS.md.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATE="${AEP_BOOT_GATE_BIN:-$HERE/../../scripts/boot-gate.sh}"
# The watchdog stops a healthy daemon only when its activity marker exists and
# is stale. A gated job touches the marker at start and heartbeats it while the
# job runs, so a long job cannot be mistaken for an idle daemon and reaped.
ACTIVITY_FILE="${AEP_DAEMON_ACTIVITY_FILE:-$HOME/workspace/neurostrata/.last-daemon-use}"

usage() {
  echo "usage: $0 <job-name> -- <command...>" >&2
  exit 2
}

[ "$#" -ge 3 ] || usage
JOB="$1"
[ -n "$JOB" ] || usage
[ "$2" = "--" ] || usage
shift 2

abort() { # $1 = rc, $2 = optional detail
  local line="CRON-GATE: ABORT $JOB rc=$1"
  if [ -n "${2:-}" ]; then line="$line ($2)"; fi
  echo "$line" >&2
  if [ -n "${AEP_CRON_GATE_LOG:-}" ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $line" >>"$AEP_CRON_GATE_LOG" || true
  fi
  exit "$1"
}

if [ ! -f "$GATE" ] || [ ! -x "$GATE" ]; then
  abort 127 "boot gate not found or not executable: $GATE"
fi

rc=0
out=$("$GATE" 2>&1) || rc=$?
if [ "$rc" -ne 0 ]; then
  printf '%s\n' "$out" >&2
  abort "$rc"
fi

# A passing gate's per-check results belong in the scheduler log too.
printf '%s\n' "$out"

touch_activity() {
  mkdir -p "$(dirname "$ACTIVITY_FILE")" 2>/dev/null || true
  date +%s >"$ACTIVITY_FILE" 2>/dev/null || true
}

touch_activity

# Run the job as a child (not exec) so the activity marker can be refreshed
# for the whole run. Exit status and stdio still reach the scheduler unchanged.
"$@" &
job_pid=$!
(
  while kill -0 "$job_pid" 2>/dev/null; do
    touch_activity
    sleep 60
  done
) &
hb_pid=$!
trap 'kill "$hb_pid" 2>/dev/null || true; kill -TERM "$job_pid" 2>/dev/null || true' INT TERM

job_rc=0
wait "$job_pid" || job_rc=$?
kill "$hb_pid" 2>/dev/null || true
wait "$hb_pid" 2>/dev/null || true
touch_activity
exit "$job_rc"
