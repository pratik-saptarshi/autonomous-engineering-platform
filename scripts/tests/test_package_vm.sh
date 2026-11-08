#!/usr/bin/env bash
# test_package_vm.sh — behavioral tests for scripts/package-vm.sh.
#
# Pins the N1 contract: the generated systemd unit must configure a
# verification root for the supervisor, the bundle must ship a payload
# that lands at that exact root, BOTH install routes the bundle ships
# (install.sh and the cloud-init user-data.yaml) must create/populate
# that path, and the payload must be a real, runnable tree — `aep
# verify` against it discovers >= 1 check and passes.
#
# The configured root is DERIVED from the generated unit (the --root on
# ExecStart, falling back to WorkingDirectory), never assumed; the
# assertions then check that derived path against every other artifact.
#
# STAGING (why this test touches real paths): the payload is a
# self-check of the INSTALLED system — its Makefile invokes
# /usr/local/bin/aep and reads /etc/aep/hardware-profile.conf by
# absolute path — so the runnable assertion can only execute against
# the real install locations. The test stages only the pieces that are
# missing (built binary, bundle config, payload at the configured
# root), and removes exactly what it created on exit; pre-existing
# installs are used as-is and never modified or removed. If it cannot
# stage (no root, no passwordless sudo), the runnable case FAILS
# loudly rather than passing vacuously.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PACKAGE_VM="$ROOT/scripts/package-vm.sh"
SB="$(mktemp -d /tmp/test-package-vm.XXXXXX)"
FAILURES=0

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
# --- Staging bookkeeping: only what this test created is removed. ---
CREATED_BIN=0
CREATED_CONF=0
CREATED_ROOT=0
ROOT_PATH=""
run_root() { # run_root <command...> — root directly, else sudo -n
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  else
    sudo -n "$@"
  fi
}
# shellcheck disable=SC2329 # cleanup is invoked via the EXIT trap below.
cleanup() {
  if [ "$CREATED_ROOT" -eq 1 ] && [ -n "$ROOT_PATH" ]; then
    run_root rm -rf "$ROOT_PATH" 2>/dev/null || true
    run_root rmdir "$(dirname "$ROOT_PATH")" 2>/dev/null || true
  fi
  if [ "$CREATED_CONF" -eq 1 ]; then
    run_root rm -f /etc/aep/hardware-profile.conf 2>/dev/null || true
    run_root rmdir /etc/aep 2>/dev/null || true
  fi
  if [ "$CREATED_BIN" -eq 1 ]; then
    run_root rm -f /usr/local/bin/aep 2>/dev/null || true
  fi
}
trap cleanup EXIT

# --- Build the binary and the bundle under test. ---
export GOTMPDIR="${GOTMPDIR:-$HOME/.gotmp}"
mkdir -p "$GOTMPDIR"
BIN="$SB/aep"
note "building aep and the VM bundle (sandbox $SB)"
if ! (cd "$ROOT" && go build -o "$BIN" ./cmd/aep) >"$SB/build.log" 2>&1; then
  echo "FATAL: go build failed; see $SB/build.log" >&2
  exit 1
fi
OUT="$SB/bundle"
if ! bash "$PACKAGE_VM" linux amd64 "$BIN" "$OUT" >"$SB/package.log" 2>&1; then
  echo "FATAL: package-vm.sh failed; see $SB/package.log" >&2
  exit 1
fi
UNIT="$OUT/systemd/aep-ralph.service"
check "bundle tarball produced" test -f "$OUT.tar.gz"
check "unit generated" test -f "$UNIT"

# --- Derive the configured verification root from the unit. ---
ROOT_PATH="$(sed -n 's/^ExecStart=.*--root[= ]\([^ ]*\).*/\1/p' "$UNIT" | head -1)"
if [ -z "$ROOT_PATH" ]; then
  ROOT_PATH="$(sed -n 's/^WorkingDirectory=//p' "$UNIT" | head -1)"
fi
note "configured verification root derived from unit: '${ROOT_PATH:-<none>}'"
if [ -n "$ROOT_PATH" ]; then
  ok "unit configures a verification root"
else
  fail "unit configures a verification root (no --root on ExecStart, no WorkingDirectory)"
fi
case "$ROOT_PATH" in
/*) ok "configured root is an absolute path" ;;
*) fail "configured root is an absolute path (got '$ROOT_PATH')" ;;
esac
check "configured root is the pinned /usr/local/lib/aep/verify" \
  test "$ROOT_PATH" = "/usr/local/lib/aep/verify"
check "unit WorkingDirectory matches the configured root" \
  grep -qF "WorkingDirectory=$ROOT_PATH" "$UNIT"
check "unit ExecStart carries --root for the configured root" \
  grep -qF -- "--root $ROOT_PATH" "$UNIT"
check "unit still pre-flights with aep boot" \
  grep -qF "ExecStartPre=/usr/local/bin/aep boot" "$UNIT"

# --- Both install routes must create/populate that exact path. ---
# With an empty derived root, grep -qF "$ROOT_PATH" matches every line
# and these checks would pass vacuously; fail each one instead.
if [ -z "$ROOT_PATH" ]; then
  fail "install.sh references the configured root (no root derived from the unit)"
  fail "install.sh clean-replaces the payload at the configured root (no root derived from the unit)"
  fail "install.sh copies the bundle payload to the configured root (no root derived from the unit)"
  fail "install.sh warns loudly (stderr) when make is missing (no root derived from the unit)"
  fail "user-data.yaml references the configured root (no root derived from the unit)"
  fail "user-data.yaml stages the payload from /tmp/aep-verify (no root derived from the unit)"
  fail "user-data.yaml installs make (payload dependency) (no root derived from the unit)"
else
  check "install.sh references the configured root" \
    grep -qF "$ROOT_PATH" "$OUT/install.sh"
  check "install.sh clean-replaces the payload at the configured root" \
    grep -qF "rm -rf $ROOT_PATH" "$OUT/install.sh"
  check "install.sh copies the bundle payload to the configured root" \
    grep -qF "cp -r \"\${DIR}/verify\" $ROOT_PATH" "$OUT/install.sh"
  check "install.sh warns loudly (stderr) when make is missing" \
    grep -q "WARNING: 'make' is not installed" "$OUT/install.sh"
  check "user-data.yaml references the configured root" \
    grep -qF "$ROOT_PATH" "$OUT/user-data.yaml"
  check "user-data.yaml stages the payload from /tmp/aep-verify" \
    grep -qF "cp -r /tmp/aep-verify $ROOT_PATH" "$OUT/user-data.yaml"
  check "user-data.yaml installs make (payload dependency)" \
    grep -qF "  - make" "$OUT/user-data.yaml"
fi

# --- The bundle payload itself. ---
PAYLOAD="$OUT/verify"
check "bundle carries the verify/ payload directory" test -d "$PAYLOAD"
check "payload is exactly one file, the Makefile" \
  test "$(find "$PAYLOAD" -type f | wc -l)" -eq 1
check "payload Makefile exists" test -f "$PAYLOAD/Makefile"
check "payload Makefile declares a test target" \
  grep -qE '^test:' "$PAYLOAD/Makefile"
TAB_LINES="$(grep -c '^	' "$PAYLOAD/Makefile")"
check "payload Makefile recipe lines use real TABs (3 recipe lines)" \
  test "$TAB_LINES" -eq 3
check "payload self-checks via the installed binary path" \
  grep -qF "/usr/local/bin/aep boot" "$PAYLOAD/Makefile"
check "payload self-checks the installed hardware profile" \
  grep -qF "test -r /etc/aep/hardware-profile.conf" "$PAYLOAD/Makefile"

# --- Runnable: stage what's missing, then verify for real. ---
note "staging the installed system (only missing pieces; removed on exit if created here)"
STAGE_OK=1
if [ ! -x /usr/local/bin/aep ]; then
  if run_root install -m 755 "$BIN" /usr/local/bin/aep; then
    CREATED_BIN=1
  else
    STAGE_OK=0
  fi
fi
if [ ! -r /etc/aep/hardware-profile.conf ]; then
  if run_root mkdir -p /etc/aep &&
    run_root cp "$OUT/config/hardware-profile.conf" /etc/aep/; then
    CREATED_CONF=1
  else
    STAGE_OK=0
  fi
fi
if [ -n "$ROOT_PATH" ] && [ ! -e "$ROOT_PATH/Makefile" ]; then
  if run_root mkdir -p "$(dirname "$ROOT_PATH")" &&
    run_root rm -rf "$ROOT_PATH" &&
    run_root cp -r "$PAYLOAD" "$ROOT_PATH"; then
    CREATED_ROOT=1
  else
    STAGE_OK=0
  fi
fi
if [ "$STAGE_OK" -eq 1 ]; then
  ok "installed system staged"
else
  fail "installed system staged (need root or passwordless sudo for the pinned install paths)"
fi

if [ "$STAGE_OK" -eq 1 ]; then
  note "case (a): aep verify against the bundle payload dir"
  if "$BIN" verify --root "$PAYLOAD" --min-mem 0 --timeout 30 --budget 60 \
    >"$SB/verify-payload.out" 2>&1; then
    ok "(a) verify passes against the bundle payload"
  else
    fail "(a) verify passes against the bundle payload"
    sed 's/^/    /' "$SB/verify-payload.out"
  fi
  check "(a) verify discovers >= 1 check in the payload" \
    grep -qE 'Discovered: [1-9]' "$SB/verify-payload.out"

  note "case (b): aep verify against the installed root itself"
  if "$BIN" verify --root "$ROOT_PATH" --min-mem 0 --timeout 30 --budget 60 \
    >"$SB/verify-root.out" 2>&1; then
    ok "(b) verify passes against the installed root"
  else
    fail "(b) verify passes against the installed root"
    sed 's/^/    /' "$SB/verify-root.out"
  fi
  check "(b) verify discovers >= 1 check at the installed root" \
    grep -qE 'Discovered: [1-9]' "$SB/verify-root.out"
fi

echo
if [ "$FAILURES" -eq 0 ]; then
  echo "test_package_vm: ALL PASS (sandbox $SB)"
  rm -rf "$SB"
  exit 0
fi
echo "test_package_vm: $FAILURES failure(s) (sandbox kept at $SB)"
exit 1
