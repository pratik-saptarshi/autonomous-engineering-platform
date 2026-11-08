#!/usr/bin/env bash
# test_verify_signals.sh — signal-cleanup tests for `aep verify`.
#
# Pins the N8 contract: interrupting a long-running `aep verify` with
# SIGINT or SIGTERM must cancel the verification, let process-group
# cleanup complete, print the result, and exit 1 — with ZERO
# verification processes surviving. runVerify originally passed
# context.Background() to RunVerification (runSupervisor wires a
# signal.NotifyContext; verify never did), so the CLI died BY the
# signal instantly (exit status 130/143) and every check — each in its
# own process group via Setpgid, so the terminal's foreground-group
# interrupt never reaches it — was orphaned, with the per-command
# timeouts and the total budget dying with the CLI.
#
# Exit status is pinned at exactly 1, not 128+signal: verify's
# contract is 0 iff PASS, 1 otherwise, and after the fix the CLI
# catches the signal, cleans up, prints the partial result, and exits
# deliberately. 130/143 would mean it died by the signal and no
# cleanup ran.
#
# Method: build ./cmd/aep, point it at a fixture whose only check
# sleeps (a distinctive duration, in its own process group), launch
# the CLI via `env --default-signal` so it starts with default signal
# dispositions exactly like an interactive foreground launch (a bare
# `&` launch from a script inherits SIGINT=SIG_IGN, which would mask
# the behavior under test), signal the CLI pid alone, then census the
# fixture's process group by exact pid. A probe that cannot run
# FAILS — it never skips silently. Leftover fixture processes are
# killed by exact pid whatever the outcome.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SB="$(mktemp -d /tmp/test-verify-signals.XXXXXX)"
BIN="$SB/aep"
FIX="$SB/fixture"
FAILURES=0

# Exact pids this test has spawned or discovered, for trap cleanup.
CLEANUP_PIDS=()

note() { echo "# $*"; }
ok() { echo "ok - $*"; }
fail() {
  echo "FAIL - $*"
  FAILURES=$((FAILURES + 1))
}

# shellcheck disable=SC2329 # cleanup is invoked via the EXIT trap below.
cleanup() {
  local p
  for p in "${CLEANUP_PIDS[@]}"; do
    kill -9 "$p" 2>/dev/null
  done
  if [ "$FAILURES" -eq 0 ]; then
    rm -rf "$SB"
  fi
}
trap cleanup EXIT

# --- Fixture: one discovered check (make test) that sleeps. The
# sleep duration is distinctive so survivor detection keys on this
# fixture's own process group, never on unrelated sleeps. ---
mkdir -p "$FIX"
printf 'test:\n\t@sleep 117 & sleep 117\n' >"$FIX/Makefile"

note "build ./cmd/aep (sandbox $SB)"
if ! (cd "$ROOT" && GOTMPDIR="${GOTMPDIR:-$HOME/.gotmp}" go build -o "$BIN" ./cmd/aep); then
  fail "go build ./cmd/aep could not run"
  echo "test_verify_signals: $FAILURES failure(s) (sandbox kept at $SB)"
  exit 1
fi

run_case() { # run_case <SIGINT|SIGTERM>
  local sig="$1"
  local label="verify + $sig"
  env --default-signal=INT --default-signal=TERM \
    "$BIN" verify --root "$FIX" --min-mem 0 --timeout 300 --budget 600 \
    >"$SB/out-$sig.log" 2>&1 &
  local cli=$!
  CLEANUP_PIDS+=("$cli")

  # Give the fixture's check time to actually start before signaling.
  sleep 2
  local make_pid fixture_pids
  make_pid="$(pgrep -P "$cli" | head -1)"
  fixture_pids="$(ps -eo pid,pgid | awk -v g="$make_pid" '$2==g {print $1}')"
  if [ -z "$fixture_pids" ]; then
    fail "$label: fixture check never started (probe could not run)"
    kill -9 "$cli" 2>/dev/null
    return
  fi
  # shellcheck disable=SC2206 # word splitting is the pid list
  CLEANUP_PIDS+=($fixture_pids)

  kill -"$sig" "$cli"
  local exited=""
  for _ in $(seq 1 20); do
    kill -0 "$cli" 2>/dev/null || {
      exited=1
      break
    }
    sleep 0.5
  done

  if [ -z "$exited" ]; then
    fail "$label: CLI did not exit within 10s of the signal"
    kill -9 "$cli" 2>/dev/null
    return
  fi
  ok "$label: CLI exited within 10s of the signal"

  local status
  wait "$cli" 2>/dev/null
  status=$?
  if [ "$status" = "1" ]; then
    ok "$label: CLI exit status 1 (deliberate exit after cleanup)"
  else
    fail "$label: CLI exit status $status (want 1; 130/143 = died by the signal)"
  fi

  if grep -q 'Verification Summary' "$SB/out-$sig.log"; then
    ok "$label: verification summary printed"
  else
    fail "$label: no verification summary printed (cleanup/result path never ran)"
  fi

  sleep 1
  local alive="" p
  for p in $fixture_pids; do
    kill -0 "$p" 2>/dev/null && alive="$alive $p"
  done
  # Evidence + cleanup by exact pid, whatever the outcome.
  for p in $alive; do kill -9 "$p" 2>/dev/null; done
  if [ -z "$alive" ]; then
    ok "$label: zero fixture processes survived the CLI"
  else
    fail "$label: fixture processes survived the CLI:$alive"
  fi
}

run_case INT
sleep 1
run_case TERM

echo
if [ "$FAILURES" -eq 0 ]; then
  echo "test_verify_signals: ALL PASS"
  exit 0
fi
echo "test_verify_signals: $FAILURES failure(s) (sandbox kept at $SB)"
exit 1
