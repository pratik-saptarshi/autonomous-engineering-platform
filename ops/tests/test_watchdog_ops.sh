#!/usr/bin/env bash
# test_watchdog_ops.sh — behavioral tests for ops/bin/watchdog-backup.sh.
#
# The watchdog under test is the live-derived on-demand watchdog: the
# daemon is no longer always-on, it stays down after backup, and the MCP
# client restarts it. Cases below are specified per daemon state against
# that model (see ops/bin/WATCHDOG-DELTAS.md for how this file differs
# from the live script it was copied from).
#
# Every case runs the real watchdog against a fixture HOME: a stub
# neurostrata-mcp binary, a fixture DB, and (for up-cases) a REAL
# long-lived stub daemon process that the watchdog's own
# `pgrep -f '[n]eurostrata-mcp daemon'` can see. pgrep and sha256sum are
# never stubbed; `sleep` is stubbed on PATH to compress the watchdog's
# poll loops.
#
# ISOLATION (safety-critical): the watchdog signals every process whose
# cmdline matches the daemon pattern. On a machine with a real daemon
# running, an un-isolated test run could SIGTERM it. The suite therefore
# re-executes itself inside a PID namespace (unshare -pf --mount-proc)
# where only fixture processes are visible. If namespaces are
# unavailable it refuses to run while any daemon-pattern process exists.
set -uo pipefail

SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
if [ -z "${TEST_WATCHDOG_NS:-}" ]; then
  if command -v unshare >/dev/null 2>&1 && unshare -pf --mount-proc true 2>/dev/null; then
    TEST_WATCHDOG_NS=1 exec unshare -pf --mount-proc bash "$SELF" "$@"
  fi
  if pgrep -f '[n]eurostrata-mcp daemon' >/dev/null 2>&1; then
    echo "FATAL: a neurostrata-mcp daemon process is visible and PID-namespace" >&2
    echo "isolation is unavailable — refusing to run (the watchdog under test" >&2
    echo "signals by pgrep pattern and must never reach a real daemon)." >&2
    exit 1
  fi
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WATCHDOG="$ROOT/ops/bin/watchdog-backup.sh"
SB="$(mktemp -d /tmp/test-watchdog-ops.XXXXXX)"
FAILURES=0
CASE_RCS=()
CASE_OUTS=()

note() { echo "# $*"; }
ok() { echo "ok - $*"; }
fail() {
  echo "FAIL - $*"
  FAILURES=$((FAILURES + 1))
}
check() { # check <description> <command...>
  local desc="$1"
  shift
  if "$@" >/dev/null 2>&1; then ok "$desc"; else fail "$desc"; fi
}
check_not() { # check_not <description> <command...>
  local desc="$1"
  shift
  if "$@" >/dev/null 2>&1; then fail "$desc"; else ok "$desc"; fi
}

file_sha() { sha256sum "$1" | awk '{print $1}'; }

# --- PATH stub: sleep returns immediately (poll loops compress). ---
mkdir -p "$SB/bin"
printf '#!/bin/sh\nexit 0\n' >"$SB/bin/sleep"
chmod +x "$SB/bin/sleep"

# --- Stub neurostrata-mcp (copied into each fixture HOME). ---
# `status` reports healthy iff the stub daemon's pidfile names a live
# process with a non-empty cmdline (a zombie's cmdline reads back empty;
# note /proc cmdline always stats as size 0, so read the bytes, never -s).
# `daemon` becomes the long-lived daemon: records TERM deliveries to
# .stub-signals.log, or ignores TERM entirely when .stub-ignore-term
# exists. Uses /usr/bin/sleep by absolute path — never the PATH stub.
mkdir -p "$SB/stub"
cat >"$SB/stub/neurostrata-mcp" <<'STUB'
#!/usr/bin/env bash
set -uo pipefail
NS_DIR="$HOME/workspace/neurostrata"
PID_FILE="$NS_DIR/.stub-daemon.pid"
SIG_FILE="$NS_DIR/.stub-signals.log"
case "${1:-}" in
  status)
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "$pid" ] && [ -n "$(tr -d '\0' <"/proc/$pid/cmdline" 2>/dev/null)" ]; then
      echo "status: healthy"
    else
      echo "status: stopped"
    fi
    ;;
  --version)
    echo "neurostrata-mcp 0.0.0-stub"
    ;;
  daemon)
    echo $$ >"$PID_FILE"
    if [ -f "$NS_DIR/.stub-ignore-term" ]; then
      trap '' TERM
    else
      trap 'echo TERM >>"$SIG_FILE"; rm -f "$PID_FILE"; exit 0' TERM
    fi
    while :; do
      /usr/bin/sleep 0.2 &
      wait $!
    done
    ;;
  *)
    echo "stub neurostrata-mcp: unknown command ${1:-}" >&2
    exit 2
    ;;
esac
STUB
chmod +x "$SB/stub/neurostrata-mcp"

# --- Fixture helpers. FX/FH point at the current case's fixture. ---
FX=""
FH=""
new_fixture() {
  FX="$SB/case-$1"
  FH="$FX/home"
  mkdir -p "$FH/workspace/neurostrata/bin" "$FH/.config/NeuroStrata/data/db"
  cp "$SB/stub/neurostrata-mcp" "$FH/workspace/neurostrata/bin/neurostrata-mcp"
  printf 'db-content-v1' >"$FH/.config/NeuroStrata/data/db/ladybug.db"
}
fixture_db() { echo "$FH/.config/NeuroStrata/data/db/ladybug.db"; }
fixture_ns() { echo "$FH/workspace/neurostrata"; }
set_unchanged() { file_sha "$(fixture_db)" >"$(fixture_ns)/.last-db-sha256"; }
prestage_backup() {
  mkdir -p "$(fixture_ns)/backups"
  cp "$(fixture_db)" "$(fixture_ns)/backups/db-20000101-000000.db"
  printf 'logs' >"$(fixture_ns)/backups/logs-20000101-000000.tar.gz"
}
set_changed() {
  printf 'db-content-v2' >"$(fixture_db)"
  printf 'db-content-v1' | sha256sum | awk '{print $1}' >"$(fixture_ns)/.last-db-sha256"
}
set_last_use() { echo "$1" >"$(fixture_ns)/.last-daemon-use"; }

fixture_daemon_pids() {
  pgrep -f "$(fixture_ns)/bin/neurostrata-mcp daemon" 2>/dev/null || true
}
start_fixture_daemon() {
  # HOME must be the fixture's: the stub resolves its pidfile under
  # $HOME, and so does every `status` call below.
  HOME="$FH" nohup "$(fixture_ns)/bin/neurostrata-mcp" daemon >/dev/null 2>&1 &
  local i
  for i in $(seq 1 50); do
    if HOME="$FH" "$(fixture_ns)/bin/neurostrata-mcp" status 2>/dev/null | grep -q "status: healthy"; then
      return 0
    fi
    /usr/bin/sleep 0.1
  done
  echo "fixture daemon did not become healthy" >&2
  return 1
}
daemon_running() { [ -n "$(fixture_daemon_pids)" ]; }
kill_fixture_daemons() {
  local pids i
  pids="$(fixture_daemon_pids)"
  if [ -n "$pids" ]; then
    # shellcheck disable=SC2086 # word splitting is the point: pid list
    kill -KILL $pids 2>/dev/null || true
  fi
  for i in $(seq 1 50); do
    [ -z "$(fixture_daemon_pids)" ] && return 0
    /usr/bin/sleep 0.1
  done
}

run_watchdog() { # run_watchdog [VAR=value ...] — records RC + OUT
  OUT="$FX/out.log"
  env HOME="$FH" PATH="$SB/bin:/usr/local/bin:/usr/bin:/bin" \
    "$@" bash "$WATCHDOG" >"$OUT" 2>&1
  RC=$?
  CASE_RCS+=("$RC")
  CASE_OUTS+=("$OUT")
}

# ================= Cases (on-demand model) =================

note "case (a): active-daemon no-change — exit 0 leaving it running"
new_fixture a
set_unchanged
prestage_backup
set_last_use "$(date +%s)"
start_fixture_daemon
DAEMON_PID_A="$(fixture_daemon_pids)"
run_watchdog
[ "$RC" -eq 0 ] && ok "(a) exit 0" || fail "(a) exit 0 (got $RC)"
check "(a) daemon never signalled" test ! -f "$(fixture_ns)/.stub-signals.log"
check "(a) daemon still running (same pid)" test "$(fixture_daemon_pids)" = "$DAEMON_PID_A"
check "(a) no new backup staged" test "$(ls "$(fixture_ns)/backups" | grep '^db-')" = "db-20000101-000000.db"
kill_fixture_daemons

note "case (b): idle-daemon no-change — stops it by design, exit 0"
new_fixture b
set_unchanged
prestage_backup
set_last_use 1
start_fixture_daemon
run_watchdog
[ "$RC" -eq 0 ] && ok "(b) exit 0" || fail "(b) exit 0 (got $RC)"
check "(b) daemon received TERM" grep -q TERM "$(fixture_ns)/.stub-signals.log"
check_not "(b) daemon stopped" daemon_running
check "(b) no new backup staged" test "$(ls "$(fixture_ns)/backups" | grep '^db-')" = "db-20000101-000000.db"
kill_fixture_daemons

note "case (c): daemon-down no-change — change detection runs, nothing to stop, exit 0"
new_fixture c
set_unchanged
prestage_backup
run_watchdog
[ "$RC" -eq 0 ] && ok "(c) exit 0" || fail "(c) exit 0 (got $RC)"
check "(c) run reports no DB changes" grep -q "no DB changes" "$OUT"
check "(c) no new backup staged" test "$(ls "$(fixture_ns)/backups" | grep '^db-')" = "db-20000101-000000.db"
kill_fixture_daemons

note "case (d): daemon-down changed — quiescent backup taken, exit 0"
new_fixture d
set_changed
run_watchdog
[ "$RC" -eq 0 ] && ok "(d) exit 0" || fail "(d) exit 0 (got $RC)"
check "(d) run reports quiescent backup" grep -q "DB changed while daemon was down" "$OUT"
check "(d) backup staged" ls "$(fixture_ns)/backups"/db-*.db
STAGED="$(ls "$(fixture_ns)/backups"/db-*.db 2>/dev/null | grep -v "db-20000101-000000.db" | head -1 || true)"
if [ -z "$STAGED" ]; then
  STAGED="$(ls "$(fixture_ns)/backups"/db-*.db 2>/dev/null | head -1 || true)"
fi
if [ -n "$STAGED" ]; then
  check "(d) backup bytes match DB" test "$(file_sha "$STAGED")" = "$(file_sha "$(fixture_db)")"
  check "(d) local watermark recorded" test "$(cat "$(fixture_ns)/.last-db-sha256")" = "$(file_sha "$(fixture_db)")"
fi
kill_fixture_daemons

note "case (e): Drive-unconfigured — local-tier success, exit 0, no Drive watermark"
new_fixture e
set_changed
# No folder-id file in the fixture: Drive is unconfigured by construction.
run_watchdog
[ "$RC" -eq 0 ] && ok "(e) exit 0" || fail "(e) exit 0 (got $RC)"
check "(e) run warns Drive is not configured" grep -q "Drive upload not configured" "$OUT"
check "(e) backup staged" ls "$(fixture_ns)/backups"/db-*.db
check_not "(e) no Drive watermark recorded" test -f "$(fixture_ns)/.last-drive-sha256"
kill_fixture_daemons

note "case (g): wedged daemon on changed-DB path — loud failure, no backup"
new_fixture g
set_changed
set_last_use 1
touch "$(fixture_ns)/.stub-ignore-term"
start_fixture_daemon
run_watchdog
[ "$RC" -ne 0 ] && ok "(g) nonzero exit on stop failure (got $RC)" || fail "(g) nonzero exit on stop failure (got $RC)"
check "(g) run reports stop failure" grep -q "would not stop" "$OUT"
check "(g) no backup staged" test -z "$(ls "$(fixture_ns)/backups"/db-*.db 2>/dev/null || true)"
kill_fixture_daemons

note "case (h): unexpected death — pre-restart log survives a truncating restart"
new_fixture h
set_unchanged
prestage_backup
set_last_use "$(date +%s)"
start_fixture_daemon
run_watchdog # healthy and active: the watchdog records that the daemon was up
echo "SENTINEL-H-last-words-before-death" >"$(fixture_ns)/daemon.log"
kill_fixture_daemons # SIGKILL: no TERM, no intentional stop
run_watchdog
[ "$RC" -eq 0 ] && ok "(h) exit 0" || fail "(h) exit 0 (got $RC)"
PRE_H="$(find "$(fixture_ns)" -maxdepth 1 -name 'daemon.log.*.pre-restart' | head -n 1)"
check "(h) a daemon.log.<UTC-ts>.pre-restart file exists" test -n "$PRE_H"
check "(h) the pre-restart file holds the sentinel" grep -q "SENTINEL-H-last-words-before-death" "$PRE_H"
case "$(basename "${PRE_H:-none}")" in
daemon.log.[0-9]*T[0-9]*Z*.pre-restart) ok "(h) pre-restart name carries a UTC timestamp" ;;
*) fail "(h) pre-restart name carries a UTC timestamp ($PRE_H)" ;;
esac
# The old restart command truncated daemon.log: it must no longer destroy the evidence.
: >"$(fixture_ns)/daemon.log"
check "(h) sentinel survives an old-style truncating restart" grep -q "SENTINEL-H-last-words-before-death" "$PRE_H"

note "case (i): unexpected death — a crash bundle is written, owner-only"
CRASH_I="$(find "$(fixture_ns)/logs" -maxdepth 1 -name 'crash-*.log' 2>/dev/null | head -n 1)"
check "(i) crash-<UTC-ts>.log exists under logs/" test -n "$CRASH_I"
check "(i) run says it captured diagnostics" grep -q "crash diagnostics" "$OUT"
check "(i) bundle has a UTC timestamp" grep -Eq '^crash bundle captured [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z' "$CRASH_I"
check "(i) bundle holds the daemon.log tail" grep -q "SENTINEL-H-last-words-before-death" "$CRASH_I"
check "(i) bundle has a dmesg section" grep -q "== kernel OOM hints" "$CRASH_I"
check "(i) bundle has free -m" grep -q "== free -m ==" "$CRASH_I"
check "(i) bundle has df -h" grep -q "== df -h ==" "$CRASH_I"
check "(i) bundle has ulimit -a" grep -q "== ulimit -a ==" "$CRASH_I"
check "(i) bundle records the binary version" grep -q "neurostrata-mcp 0.0.0-stub" "$CRASH_I"
MODE_I="$(stat -c '%a' "$CRASH_I" 2>/dev/null || stat -f '%Lp' "$CRASH_I")"
check "(i) bundle is owner-only (600)" test "$MODE_I" = "600"
run_watchdog
check "(i) a second run does not capture the same death again" test "$(find "$(fixture_ns)/logs" -maxdepth 1 -name 'crash-*.log' | wc -l | tr -d ' ')" = "1"
kill_fixture_daemons

note "case (j): retention cap holds over 15 unexpected deaths"
new_fixture j
set_unchanged
prestage_backup
for n in $(seq 1 15); do
  # The marker stands in for "a healthy run saw the daemon up" so 15 deaths
  # run quickly. Case (h) covers the real healthy-then-killed flow.
  date +%s >"$(fixture_ns)/.daemon-seen-up"
  echo "SENTINEL-J-$n" >"$(fixture_ns)/daemon.log"
  run_watchdog
done
check "(j) at most 10 crash bundles kept" test "$(find "$(fixture_ns)/logs" -maxdepth 1 -name 'crash-*.log' | wc -l | tr -d ' ')" = "10"
check "(j) at most 10 pre-restart logs kept" test "$(find "$(fixture_ns)" -maxdepth 1 -name 'daemon.log.*.pre-restart' | wc -l | tr -d ' ')" = "10"
check "(j) the newest pre-restart log is kept" grep -rq "SENTINEL-J-15" "$(fixture_ns)" --include='daemon.log.*.pre-restart'
check_not "(j) the oldest pre-restart log was pruned" grep -rq "SENTINEL-J-1$" "$(fixture_ns)" --include='daemon.log.*.pre-restart'

note "case (k): intentional idle stop emits NO crash bundle"
new_fixture k
set_unchanged
prestage_backup
set_last_use 1
start_fixture_daemon
echo "SENTINEL-K" >"$(fixture_ns)/daemon.log"
run_watchdog # idle daemon: the watchdog stops it on purpose
[ "$RC" -eq 0 ] && ok "(k) idle stop exits 0" || fail "(k) idle stop exits 0 (got $RC)"
check_not "(k) daemon stopped" daemon_running
run_watchdog # daemon is now down because the watchdog stopped it
[ "$RC" -eq 0 ] && ok "(k) next run exits 0" || fail "(k) next run exits 0 (got $RC)"
check_not "(k) no crash bundle after an intentional stop" test -n "$(find "$(fixture_ns)/logs" -maxdepth 1 -name 'crash-*.log' 2>/dev/null)"
check_not "(k) no pre-restart log after an intentional stop" test -n "$(find "$(fixture_ns)" -maxdepth 1 -name 'daemon.log.*.pre-restart' 2>/dev/null)"
check "(k) daemon.log is left in place" grep -q "SENTINEL-K" "$(fixture_ns)/daemon.log"
kill_fixture_daemons

note "case (l): classification without a prior healthy run"
new_fixture l
set_unchanged
prestage_backup
set_last_use "$(date +%s)"
run_watchdog # daemon down, no history at all: never guess a crash
check_not "(l) first-ever down run (no history) emits no crash bundle" test -n "$(find "$(fixture_ns)/logs" -maxdepth 1 -name 'crash-*.log' 2>/dev/null)"
echo 100 >"$(fixture_ns)/.last-daemon-use"
echo "50 intentional" >"$(fixture_ns)/.daemon-down-accounted"
run_watchdog # client used the daemon after the last accounted stop, now it is down
check "(l) client use after the last accounted stop counts as unexpected" test -n "$(find "$(fixture_ns)/logs" -maxdepth 1 -name 'crash-*.log' 2>/dev/null)"

note "case (m): BIN SSOT prefers ~/go/bin/neurostrata-mcp (runbook path) and fails loudly if missing"
new_fixture m
rm -f "$(fixture_ns)/bin/neurostrata-mcp"
mkdir -p "$FH/go/bin"
cp "$SB/stub/neurostrata-mcp" "$FH/go/bin/neurostrata-mcp"
set_changed
set_last_use 1
HOME="$FH" nohup "$FH/go/bin/neurostrata-mcp" daemon >/dev/null 2>&1 &
sleep 0.1
for _ in $(seq 1 50); do
  [ -s "$(fixture_ns)/.stub-daemon.pid" ] && break
  /usr/bin/sleep 0.05
done
run_watchdog
[ "$RC" -eq 0 ] && ok "(m) ~/go/bin-only host exits 0" || fail "(m) ~/go/bin-only host exits 0 (got $RC)"
check "(m) ~/go/bin-only host saw daemon healthy" grep -q "daemon healthy" "$OUT"
check "(m) ~/go/bin-only host staged backup" ls "$(fixture_ns)/backups"/db-*.db
kill_fixture_daemons
rm -f "$FH/go/bin/neurostrata-mcp"
PATH="$SB/bin:/usr/bin:/bin" run_watchdog
[ "$RC" -ne 0 ] && ok "(m) missing binary fails loudly (got $RC)" || fail "(m) missing binary fails loudly (got $RC)"
check "(m) missing binary logs ERROR" grep -q "neurostrata-mcp not found" "$OUT"

note "case (n): unwritable crash-evidence state files never abort backups (best-effort)"
new_fixture n1
set_changed
set_last_use 1
mkdir -p "$(fixture_ns)/.daemon-seen-up"
start_fixture_daemon
run_watchdog
[ "$RC" -eq 0 ] && ok "(n1) unwritable .daemon-seen-up still exits 0" || fail "(n1) unwritable .daemon-seen-up still exits 0 (got $RC)"
check "(n1) warns on .daemon-seen-up write failure" grep -q "cannot write .*daemon-seen-up" "$OUT"
check "(n1) backup still taken despite .daemon-seen-up failure" ls "$(fixture_ns)/backups"/db-*.db
kill_fixture_daemons

new_fixture n2
set_changed
date +%s >"$(fixture_ns)/.daemon-seen-up"
mkdir -p "$(fixture_ns)/.daemon-down-accounted"
run_watchdog
[ "$RC" -eq 0 ] && ok "(n2) unwritable .daemon-down-accounted still exits 0" || fail "(n2) unwritable .daemon-down-accounted still exits 0 (got $RC)"
check "(n2) warns on .daemon-down-accounted write failure" grep -q "cannot write .*daemon-down-accounted" "$OUT"
check "(n2) quiescent backup still taken despite accounted-file failure" ls "$(fixture_ns)/backups"/db-*.db

note "case (f): regression pins over every run above — no 127, no 'command not found'"
F_OK=1
for rc in "${CASE_RCS[@]}"; do
  [ "$rc" -eq 127 ] && F_OK=0
done
for out in "${CASE_OUTS[@]}"; do
  if grep -q "command not found" "$out"; then F_OK=0; fi
done
[ "$F_OK" -eq 1 ] && ok "(f) no exit 127 and no 'command not found' in any run" ||
  fail "(f) no exit 127 and no 'command not found' in any run"

echo
if [ "$FAILURES" -eq 0 ]; then
  echo "test_watchdog_ops: ALL PASS (sandbox $SB)"
  rm -rf "$SB"
  exit 0
fi
echo "test_watchdog_ops: $FAILURES failure(s) (sandbox kept at $SB)"
exit 1
