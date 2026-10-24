#!/usr/bin/env bash
# test_watchdog.sh — behavioral tests for scripts/watchdog-backup.sh.
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
WATCHDOG="$ROOT/scripts/watchdog-backup.sh"
SB="$(mktemp -d /tmp/test-watchdog.XXXXXX)"
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
# The steady state the watermark implies: staged artifacts exist (prune
# keeps the newest 3 of each kind). Pre-staging both kinds also routes
# the pre-fix script past prune_staging's empty-glob exits so case (a)
# reaches the defect this suite exists to pin (stop_daemon called before
# its definition).
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
    WATCHDOG_HEALTH_TIMEOUT=15 "$@" bash "$WATCHDOG" >"$OUT" 2>&1
  RC=$?
  CASE_RCS+=("$RC")
  CASE_OUTS+=("$OUT")
}

# ================= Cases =================

note "case (a): unchanged DB, daemon up — no stop, no backup, exit 0"
new_fixture a
set_unchanged
prestage_backup
set_last_use 1
start_fixture_daemon
DAEMON_PID_A="$(fixture_daemon_pids)"
run_watchdog
[ "$RC" -eq 0 ] && ok "(a) exit 0" || fail "(a) exit 0 (got $RC)"
check "(a) daemon never signalled" test ! -f "$(fixture_ns)/.stub-signals.log"
check "(a) daemon still running (same pid)" test "$(fixture_daemon_pids)" = "$DAEMON_PID_A"
check "(a) no new backup staged" test "$(ls "$(fixture_ns)/backups" | grep '^db-')" = "db-20000101-000000.db"
kill_fixture_daemons

note "case (b): unchanged DB, daemon down, no marker — restart it, exit 0"
new_fixture b
set_unchanged
run_watchdog
[ "$RC" -eq 0 ] && ok "(b) exit 0" || fail "(b) exit 0 (got $RC)"
check "(b) daemon restarted" daemon_running
check_not "(b) no backup staged" ls "$(fixture_ns)/backups"/db-*.db
kill_fixture_daemons

note "case (c): unchanged DB, daemon down, marker present — left down, exit 0"
new_fixture c
set_unchanged
touch "$FX/leave-down"
run_watchdog WATCHDOG_LEAVE_DOWN_MARKER="$FX/leave-down"
[ "$RC" -eq 0 ] && ok "(c) exit 0" || fail "(c) exit 0 (got $RC)"
check_not "(c) daemon left down" daemon_running
kill_fixture_daemons

note "case (d): changed DB, daemon up — stop, copy, verify, restart, exit 0"
new_fixture d
set_changed
set_last_use 1
start_fixture_daemon
run_watchdog
[ "$RC" -eq 0 ] && ok "(d) exit 0" || fail "(d) exit 0 (got $RC)"
check "(d) daemon received TERM" grep -q TERM "$(fixture_ns)/.stub-signals.log"
check "(d) backup staged" ls "$(fixture_ns)/backups"/db-*.db
STAGED="$(ls "$(fixture_ns)/backups"/db-*.db 2>/dev/null | head -1 || true)"
if [ -n "$STAGED" ]; then
  check "(d) backup bytes match DB" test "$(file_sha "$STAGED")" = "$(file_sha "$(fixture_db)")"
  check "(d) local watermark recorded" test "$(cat "$(fixture_ns)/.last-db-sha256")" = "$(file_sha "$(fixture_db)")"
fi
check "(d) daemon running after backup" daemon_running
kill_fixture_daemons

note "case (e): changed DB, daemon ignores TERM — exit 1, never 0"
new_fixture e
set_changed
set_last_use 1
touch "$(fixture_ns)/.stub-ignore-term"
start_fixture_daemon
run_watchdog
[ "$RC" -eq 1 ] && ok "(e) exit 1" || fail "(e) exit 1 (got $RC)"
check_not "(e) no backup staged" ls "$(fixture_ns)/backups"/db-*.db
check "(e) watermark untouched" test "$(cat "$(fixture_ns)/.last-db-sha256")" != "$(file_sha "$(fixture_db)")"
kill_fixture_daemons

note "case (g): changed DB, daemon down, no marker — copy while down, restart after, exit 0"
new_fixture g
set_changed
run_watchdog
[ "$RC" -eq 0 ] && ok "(g) exit 0" || fail "(g) exit 0 (got $RC)"
check "(g) backup staged" ls "$(fixture_ns)/backups"/db-*.db
STAGED="$(ls "$(fixture_ns)/backups"/db-*.db 2>/dev/null | head -1 || true)"
if [ -n "$STAGED" ]; then
  check "(g) backup bytes match DB" test "$(file_sha "$STAGED")" = "$(file_sha "$(fixture_db)")"
fi
check "(g) daemon running after backup" daemon_running
kill_fixture_daemons

note "case (h): daemon active (fresh last-use) — defers, touches nothing"
new_fixture h
set_changed
set_last_use "$(date +%s)"
start_fixture_daemon
DAEMON_PID_H="$(fixture_daemon_pids)"
SHA_BEFORE="$(cat "$(fixture_ns)/.last-db-sha256")"
run_watchdog
[ "$RC" -eq 0 ] && ok "(h) exit 0" || fail "(h) exit 0 (got $RC)"
check "(h) run reports the active gate" grep -q "daemon active" "$OUT"
check "(h) daemon never signalled" test ! -f "$(fixture_ns)/.stub-signals.log"
check "(h) daemon still running (same pid)" test "$(fixture_daemon_pids)" = "$DAEMON_PID_H"
check_not "(h) no backup staged" ls "$(fixture_ns)/backups"/db-*.db
check "(h) watermark untouched" test "$(cat "$(fixture_ns)/.last-db-sha256")" = "$SHA_BEFORE"
kill_fixture_daemons

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
  echo "test_watchdog: ALL PASS (sandbox $SB)"
  rm -rf "$SB"
  exit 0
fi
echo "test_watchdog: $FAILURES failure(s) (sandbox kept at $SB)"
exit 1
