#!/usr/bin/env bash
# Issue #17: ops/bin/cron-with-boot-gate.sh runs scripts/boot-gate.sh before a
# scheduled job and refuses to start the job when the gate fails.
#
# The gate is a stub selected through AEP_BOOT_GATE_BIN, so these cases never
# touch a real daemon, gh, or policy. The "canary" is a command that creates a
# file: a failing gate must leave the canary absent.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WRAPPER="$ROOT/ops/bin/cron-with-boot-gate.sh"
SB="$(mktemp -d)"
trap 'rm -rf "$SB"' EXIT
FAILURES=0

ok() { echo "ok - $*"; }
fail() {
  echo "FAIL - $*"
  FAILURES=$((FAILURES + 1))
}
t() { # t <description> <test args...>: ok when `[ <test args> ]` holds
  local desc="$1"
  shift
  if [ "$@" ]; then ok "$desc"; else fail "$desc (rc=${RC:-})"; fi
}
has() { # has <description> <needle>: ok when $OUT contains the needle
  case "$OUT" in *"$2"*) ok "$1" ;; *) fail "$1: output was: $OUT" ;; esac
}
lacks() { # lacks <description> <needle>
  case "$OUT" in *"$2"*) fail "$1: output was: $OUT" ;; *) ok "$1" ;; esac
}
exists() { if [ -e "$1" ]; then echo yes; else echo no; fi; }

CANARY="$SB/canary"
ARGS="$SB/args"
GATE_RAN="$SB/gate-ran"

# Stub gates.
cat >"$SB/gate-pass" <<EOF
#!/usr/bin/env bash
echo ran >>"$GATE_RAN"
echo "BOOT-GATE: guards ok"
echo "BOOT-GATE-RESULT: POLICY-OK"
exit 0
EOF
cat >"$SB/gate-fail" <<EOF
#!/usr/bin/env bash
echo ran >>"$GATE_RAN"
echo "BOOT-GATE: guards FAIL: only 0 guard_rule entries found, need >= 3"
exit 7
EOF
chmod +x "$SB/gate-pass" "$SB/gate-fail"

# Stub job: records its arguments one per line.
cat >"$SB/job" <<EOF
#!/usr/bin/env bash
: >"$ARGS"
for a in "\$@"; do printf '%s\n' "\$a" >>"$ARGS"; done
touch "$CANARY"
exit "\${JOB_RC:-0}"
EOF
chmod +x "$SB/job"

reset() { rm -f "$CANARY" "$ARGS" "$GATE_RAN" "$SB/cron-gate.log" "$SB/activity"; }
run() { # run <env GATE> <wrapper args...>
  OUT="$(AEP_DAEMON_ACTIVITY_FILE="$SB/activity" bash "$WRAPPER" "$@" 2>&1)"
  RC=$?
}

echo "# case 1: a passing gate forwards arguments and propagates the exit code"
reset
AEP_BOOT_GATE_BIN="$SB/gate-pass" run nightly -- "$SB/job" "first arg" second "third  spaced"
t "passing gate exits 0 when the job exits 0" "$RC" -eq 0
t "the gate ran" "$(exists "$GATE_RAN")" = yes
t "the job ran" "$(exists "$CANARY")" = yes
t "arguments are forwarded intact" "$(cat "$ARGS")" = "$(printf 'first arg\nsecond\nthird  spaced')"
lacks "a passing gate prints no ABORT" "CRON-GATE: ABORT"
has "a passing gate's result lines reach the log" "BOOT-GATE: guards ok"
has "a passing gate's result token reaches the log" "BOOT-GATE-RESULT: POLICY-OK"
t "the activity marker was written" "$(test -s "$SB/activity" && echo yes || echo no)" = yes
case "$(cat "$SB/activity" 2>/dev/null)" in
'' | *[!0-9]*) fail "the activity marker holds an epoch" ;;
*) ok "the activity marker holds an epoch" ;;
esac
t "the activity marker is recent" "$(($(date +%s) - $(cat "$SB/activity")))" -lt 300
reset
JOB_RC=42 AEP_BOOT_GATE_BIN="$SB/gate-pass" run nightly -- "$SB/job"
t "the job's exit code 42 is propagated" "$RC" -eq 42
t "the job ran for the exit-42 case" "$(exists "$CANARY")" = yes

echo "# case 2: a failing gate aborts the job"
reset
AEP_BOOT_GATE_BIN="$SB/gate-fail" run nightly -- "$SB/job" arg
t "failing gate exits non-zero" "$RC" -ne 0
t "failing gate exits with the gate's own status" "$RC" -eq 7
t "the canary job never ran" "$(exists "$CANARY")" = no
has "the abort line names the job and the gate status" "CRON-GATE: ABORT nightly rc=7"
has "the gate's own reason is shown" "BOOT-GATE: guards FAIL"

echo "# case 3: a missing gate binary fails closed"
reset
AEP_BOOT_GATE_BIN="$SB/no-such-gate" run nightly -- "$SB/job"
t "missing gate exits non-zero" "$RC" -ne 0
t "the canary job never ran without a gate" "$(exists "$CANARY")" = no
has "the abort line carries rc=127" "CRON-GATE: ABORT nightly rc=127"
has "the missing path is named" "$SB/no-such-gate"
printf 'not executable\n' >"$SB/gate-noexec"
reset
AEP_BOOT_GATE_BIN="$SB/gate-noexec" run nightly -- "$SB/job"
t "a non-executable gate fails closed" "$RC" -ne 0
t "the canary job never ran for a non-executable gate" "$(exists "$CANARY")" = no

echo "# case 4: a missing '-- <command>' is a usage error and runs nothing"
reset
AEP_BOOT_GATE_BIN="$SB/gate-pass" run nightly
t "no separator exits 2" "$RC" -eq 2
reset
AEP_BOOT_GATE_BIN="$SB/gate-pass" run nightly --
t "separator with no command exits 2" "$RC" -eq 2
reset
AEP_BOOT_GATE_BIN="$SB/gate-pass" run
t "no arguments exits 2" "$RC" -eq 2
reset
AEP_BOOT_GATE_BIN="$SB/gate-pass" run nightly "$SB/job"
t "a command without '--' exits 2" "$RC" -eq 2
t "usage errors never run the gate" "$(exists "$GATE_RAN")" = no
t "usage errors never run the job" "$(exists "$CANARY")" = no

echo "# case 5: the default gate is scripts/boot-gate.sh beside the wrapper"
FIX="$SB/repo"
mkdir -p "$FIX/ops/bin" "$FIX/scripts"
cp "$WRAPPER" "$FIX/ops/bin/cron-with-boot-gate.sh" 2>/dev/null || true
cp "$SB/gate-fail" "$FIX/scripts/boot-gate.sh"
reset
OUT="$(env -u AEP_BOOT_GATE_BIN bash "$FIX/ops/bin/cron-with-boot-gate.sh" nightly -- "$SB/job" 2>&1)"
RC=$?
t "the fixture's default gate is used and aborts" "$RC" -eq 7
t "the default-gate abort never ran the job" "$(exists "$CANARY")" = no
cp "$SB/gate-pass" "$FIX/scripts/boot-gate.sh"
reset
OUT="$(env -u AEP_BOOT_GATE_BIN bash "$FIX/ops/bin/cron-with-boot-gate.sh" nightly -- "$SB/job" 2>&1)"
RC=$?
t "the fixture's default gate passing runs the job" "$RC" -eq 0
t "the job ran after the default gate passed" "$(exists "$CANARY")" = yes

echo "# case 6: AEP_CRON_GATE_LOG records the abort"
reset
AEP_CRON_GATE_LOG="$SB/cron-gate.log" AEP_BOOT_GATE_BIN="$SB/gate-fail" run nightly -- "$SB/job"
t "the log file exists" "$(exists "$SB/cron-gate.log")" = yes
t "the log holds the abort line" "$(grep -c 'CRON-GATE: ABORT nightly rc=7' "$SB/cron-gate.log")" -eq 1

if [ "$FAILURES" -ne 0 ]; then
  echo "test_cron_boot_gate: $FAILURES failure(s)"
  exit 1
fi
echo "test_cron_boot_gate: ALL PASS"
