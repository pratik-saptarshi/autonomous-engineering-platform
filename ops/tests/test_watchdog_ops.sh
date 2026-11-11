#!/usr/bin/env bash
# test_watchdog_ops.sh — behavioral tests for ops/bin/watchdog-backup.sh.
#
# The watchdog under test is the live-derived direct-restart watchdog:
# the watchdog itself (re)starts the daemon (no MCP client exists in
# this deployment), an EXIT trap guarantees a restart after a backup
# stop, and a daemon left down by the idle reaper (see
# ops/bin/idle-reaper.sh) is left down. Cases below are specified per
# daemon state against that model (see ops/bin/WATCHDOG-DELTAS.md for
# how this file differs from the live script it was copied from).
#
# Every case runs the real watchdog against a fixture HOME: a stub
# neurostrata-mcp binary, a fixture DB, and (for up-cases) a REAL
# long-lived stub daemon process that the watchdog's own
# `pgrep -f '[n]eurostrata-mcp daemon'` can see. pgrep and sha256sum are
# never stubbed; `sleep` is stubbed on PATH to compress the watchdog's
# poll loops.
#
# ISOLATION (safety-critical): the watchdog signals processes whose
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
# The watchdog's BIN is $HOME/go/bin/neurostrata-mcp, so the stub lives
# there; it also needs $HOME/.local/share/neurostrata (the daemon log
# directory its start path redirects into).
FX=""
FH=""
new_fixture() {
  FX="$SB/case-$1"
  FH="$FX/home"
  mkdir -p "$FH/go/bin" "$FH/.local/share/neurostrata" "$FH/workspace/neurostrata" "$FH/.config/NeuroStrata/data/db"
  cp "$SB/stub/neurostrata-mcp" "$FH/go/bin/neurostrata-mcp"
  printf 'db-content-v1' >"$FH/.config/NeuroStrata/data/db/ladybug.db"
}
fixture_db() { echo "$FH/.config/NeuroStrata/data/db/ladybug.db"; }
fixture_ns() { echo "$FH/workspace/neurostrata"; }
fixture_bin() { echo "$FH/go/bin/neurostrata-mcp"; }
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
set_reaped() {
  printf '[2026-01-01 00:00:00] REAPED uptime=50m conns=0\n' >"$(fixture_ns)/reaper.log"
}

fixture_daemon_pids() {
  pgrep -f "$(fixture_bin) daemon" 2>/dev/null || true
}
start_fixture_daemon() {
  # HOME must be the fixture's: the stub resolves its pidfile under
  # $HOME, and so does every `status` call below.
  HOME="$FH" nohup "$(fixture_bin)" daemon >/dev/null 2>&1 &
  local i
  for i in $(seq 1 50); do
    if HOME="$FH" "$(fixture_bin)" status 2>/dev/null | grep -q "status: healthy"; then
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

# ================= Cases (direct-restart model) =================

note "case (a): daemon-up no-change — exit 0 leaving it running"
new_fixture a
set_unchanged
prestage_backup
start_fixture_daemon
DAEMON_PID_A="$(fixture_daemon_pids)"
run_watchdog
[ "$RC" -eq 0 ] && ok "(a) exit 0" || fail "(a) exit 0 (got $RC)"
check "(a) daemon never signalled" test ! -f "$(fixture_ns)/.stub-signals.log"
check "(a) daemon still running (same pid)" test "$(fixture_daemon_pids)" = "$DAEMON_PID_A"
check "(a) no new backup staged" test "$(ls "$(fixture_ns)/backups" | grep '^db-')" = "db-20000101-000000.db"
kill_fixture_daemons

note "case (b): daemon-down no-change, reaped by the idle reaper — left down, exit 0"
new_fixture b
set_unchanged
prestage_backup
set_reaped
run_watchdog
[ "$RC" -eq 0 ] && ok "(b) exit 0" || fail "(b) exit 0 (got $RC)"
check "(b) run reports leaving it down" grep -q "leaving it down" "$OUT"
check_not "(b) daemon was not started" daemon_running
check "(b) no new backup staged" test "$(ls "$(fixture_ns)/backups" | grep '^db-')" = "db-20000101-000000.db"
kill_fixture_daemons

note "case (c): daemon-down no-change, not reaped — watchdog restarts it, exit 0"
new_fixture c
set_unchanged
prestage_backup
run_watchdog
[ "$RC" -eq 0 ] && ok "(c) exit 0" || fail "(c) exit 0 (got $RC)"
check "(c) run reports unexpected down" grep -q "daemon down unexpectedly" "$OUT"
check "(c) run reports recovery" grep -q "daemon recovered" "$OUT"
check "(c) daemon running afterwards" daemon_running
check "(c) no new backup staged" test "$(ls "$(fixture_ns)/backups" | grep '^db-')" = "db-20000101-000000.db"
kill_fixture_daemons

note "case (d): daemon-down changed — backup taken, daemon started, exit 0"
new_fixture d
set_changed
run_watchdog
[ "$RC" -eq 0 ] && ok "(d) exit 0" || fail "(d) exit 0 (got $RC)"
check "(d) run reports DB changed" grep -q "DB changed" "$OUT"
check "(d) run reports daemon restarted healthy" grep -q "daemon restarted, healthy" "$OUT"
check "(d) backup staged" ls "$(fixture_ns)/backups"/db-*.db
STAGED="$(ls "$(fixture_ns)/backups"/db-*.db 2>/dev/null | head -1 || true)"
if [ -n "$STAGED" ]; then
  check "(d) backup bytes match DB" test "$(file_sha "$STAGED")" = "$(file_sha "$(fixture_db)")"
  check "(d) local watermark recorded" test "$(cat "$(fixture_ns)/.last-db-sha256")" = "$(file_sha "$(fixture_db)")"
fi
check "(d) daemon running afterwards" daemon_running
kill_fixture_daemons

note "case (e): daemon-up changed, Drive unconfigured — stop, backup, restart; exit 0, no Drive watermark"
new_fixture e
set_changed
# No folder-id file in the fixture: Drive is unconfigured by construction.
start_fixture_daemon
DAEMON_PID_E="$(fixture_daemon_pids)"
run_watchdog
[ "$RC" -eq 0 ] && ok "(e) exit 0" || fail "(e) exit 0 (got $RC)"
check "(e) daemon received TERM" grep -q TERM "$(fixture_ns)/.stub-signals.log"
check "(e) run warns Drive is not configured" grep -q "Drive upload not configured" "$OUT"
check "(e) backup staged" ls "$(fixture_ns)/backups"/db-*.db
check "(e) local watermark recorded" test "$(cat "$(fixture_ns)/.last-db-sha256")" = "$(file_sha "$(fixture_db)")"
check_not "(e) no Drive watermark recorded" test -f "$(fixture_ns)/.last-drive-sha256"
check "(e) daemon running afterwards (new pid)" test "$(fixture_daemon_pids)" != "$DAEMON_PID_E"
kill_fixture_daemons

note "case (g): staging prune — filename order (never mtime), watermark copy never pruned"
new_fixture g
set_changed
mkdir -p "$(fixture_ns)/backups"
# Oldest name carries the NEW DB's bytes: it is the copy the watermark
# will reference, so the prune must keep it despite its name sorting
# last. Its mtime is set furthest in the future and the newest-named
# prestaged copy's mtime furthest in the past, so an mtime-ordered
# prune keeps the wrong set and fails this case.
printf 'db-content-v2' >"$(fixture_ns)/backups/db-20190101-000000.db"
printf 'db-content-v1' >"$(fixture_ns)/backups/db-20200102-000000.db"
printf 'db-content-v1' >"$(fixture_ns)/backups/db-20200103-000000.db"
printf 'db-content-v1' >"$(fixture_ns)/backups/db-20200104-000000.db"
touch -d '2030-01-01' "$(fixture_ns)/backups/db-20190101-000000.db"
touch -d '2000-01-01' "$(fixture_ns)/backups/db-20200104-000000.db"
run_watchdog
[ "$RC" -eq 0 ] && ok "(g) exit 0" || fail "(g) exit 0 (got $RC)"
check "(g) prune kept the watermark copy" test -f "$(fixture_ns)/backups/db-20190101-000000.db"
check "(g) prune kept newest-named copies" test -f "$(fixture_ns)/backups/db-20200104-000000.db"
check "(g) prune kept third-newest copy" test -f "$(fixture_ns)/backups/db-20200103-000000.db"
check_not "(g) prune removed the fourth copy" test -f "$(fixture_ns)/backups/db-20200102-000000.db"
check "(g) exactly the new backup plus three survivors staged" test "$(ls "$(fixture_ns)/backups" | grep -c '^db-')" = "4"
check "(g) run logs the watermark keep" grep -q "referenced by .last-db-sha256" "$OUT"
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
  echo "test_watchdog_ops: ALL PASS (sandbox $SB)"
  rm -rf "$SB"
  exit 0
fi
echo "test_watchdog_ops: $FAILURES failure(s) (sandbox kept at $SB)"
exit 1
