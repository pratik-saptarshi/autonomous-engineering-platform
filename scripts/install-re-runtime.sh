#!/usr/bin/env bash
# install-re-runtime.sh — fail-closed installer for the reverse-engineering
# bench: Temurin JDK 25, Ghidra 12.1.4, and radare2 6.2.6, codifying the
# hand-built bench recorded in TOOLS.md (2026-10-20 / 2026-11-07 installs).
#
# Everything installs under $HOME only (staging in $HOME/opt/dist, never
# /tmp); nothing requires root. Every artifact is pinned below and
# checksum- or commit-verified before use: an empty pin field aborts the
# run (assert_pins) and there is no bypass flag.
#
# Contract: prints "INSTALL-RE: <name> ok" per passing check; on the first
# failure prints "INSTALL-RE: <check> FAIL: <reason>" and exits 1
# immediately. It never warns-and-continues. node/npx presence is reported
# by preflight for operator visibility and is never fatal (the REA stage's
# SKIP rule, Task 4).
# Run with --self-test to execute the stub-based negative tests (each
# prints "SELF-TEST: <case> ok"). `--self-test --offline` runs the same
# fully self-contained stub cases, so it passes on a stock CI runner.
# --dry-run runs pins + preflight only (no lock, no writes) until Task 5
# gives it its plan-lines semantics.
#
# Pin bumps and rollback: a bump updates the pin block below in a reviewed
# PR, with dual-source evidence for the new value (local sha256sum over
# the staged artifact plus the upstream-published value). The full
# pin-bump and rollback procedure lands in Task 7 of the plan
# (docs/plans/2026-11-07-re-runtime-install.md); this skeleton is a branch
# state, never a releasable one.
set -euo pipefail

# --- Pin block (exact values from the plan's Pin Block table) ---
TEMURIN_VERSION="25.0.4.1+1"
TEMURIN_TARBALL="OpenJDK25U-jdk_x64_linux_hotspot_25.0.4.1_1.tar.gz"
TEMURIN_URL="https://github.com/adoptium/temurin25-binaries/releases/download/jdk-25.0.4.1+1/OpenJDK25U-jdk_x64_linux_hotspot_25.0.4.1_1.tar.gz"
TEMURIN_SHA256="dbb698396d478e7fa2b1e50f4103324b2a99b90569ee27c33f2261f9215cf41e"
GHIDRA_VERSION="12.1.4"
GHIDRA_ZIP="ghidra_12.1.4_PUBLIC_20260921.zip"
GHIDRA_URL="https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.4_build/ghidra_12.1.4_PUBLIC_20260921.zip"
GHIDRA_SHA256="ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db"
R2_VERSION="6.2.6"
R2_REPO="https://github.com/radareorg/radare2"
R2_COMMIT="06a7c9d35468676cc3fe6ea299885cf53aa8ad9b"
REA_PIN="rea-agents@6.5.0"

PIN_NAMES=(
  TEMURIN_VERSION TEMURIN_TARBALL TEMURIN_URL TEMURIN_SHA256
  GHIDRA_VERSION GHIDRA_ZIP GHIDRA_URL GHIDRA_SHA256
  R2_VERSION R2_REPO R2_COMMIT REA_PIN
)
# Every tool the component stages and this script itself require.
# pkg-config is a hard requirement of radare2's configure; flock and df
# serve the single-instance lock and the disk check.
REQUIRED_TOOLS=(curl git gcc make unzip sha256sum tar pkg-config flock df)

OFFLINE=0
DRY_RUN=0

fail() { # $1 = check name, $2 = reason
  echo "INSTALL-RE: $1 FAIL: $2"
  exit 1
}

ok() { # $1 = check name
  echo "INSTALL-RE: $1 ok"
}

assert_pins() {
  local name
  for name in "${PIN_NAMES[@]}"; do
    if [ -z "${!name:-}" ]; then
      fail pins "$name unpinned"
    fi
  done
  ok pins
}

acquire_lock() {
  # Held on fd 9 for the rest of the process lifetime; the lock file lives
  # directly under $HOME so acquiring it never forces a directory creation.
  exec 9>"$HOME/.install-re-runtime.lock"
  flock -n 9 || fail preflight "another install-re-runtime run holds the lock"
}

check_staging_dir() { # $1 = dir that must exist-or-be-creatable and writable
  local dir="$1" ancestor
  if [ -e "$dir" ] || [ -L "$dir" ]; then
    [ -d "$dir" ] || fail preflight "staging path $dir exists but is not a directory"
    [ -w "$dir" ] || fail preflight "staging directory $dir is not writable"
    return 0
  fi
  # Creatability test only — preflight creates nothing. Walk up to the
  # nearest existing ancestor and require it to be a writable directory.
  ancestor="$dir"
  while [ ! -e "$ancestor" ]; do
    ancestor="${ancestor%/*}"
    [ -n "$ancestor" ] || fail preflight "staging directory $dir is not creatable"
  done
  [ -d "$ancestor" ] || fail preflight "staging directory $dir is not creatable: $ancestor is not a directory"
  [ -w "$ancestor" ] || fail preflight "staging directory $dir is not creatable: $ancestor is not writable"
}

preflight() { # $1 = optional "--with-lock" (real runs only)
  local tool avail_kib meminfo_file mem_kib key value rest
  for tool in "${REQUIRED_TOOLS[@]}"; do
    command -v "$tool" >/dev/null 2>&1 || fail preflight "required tool '$tool' not found in PATH"
  done

  # Disk: at least 4 GiB free under $HOME (df -kP reports KiB in field 4).
  avail_kib=$(df -kP "$HOME" | awk 'NR == 2 {print $4}') ||
    fail preflight "disk: df failed for $HOME"
  case "$avail_kib" in
  '' | *[!0-9]*) fail preflight "disk: cannot parse df output for $HOME" ;;
  esac
  [ "$avail_kib" -ge 4194304 ] ||
    fail preflight "disk: only $((avail_kib / 1024)) MiB free under $HOME, need at least 4 GiB"

  # Memory: MemAvailable floor of 384 MiB (393216 KiB). The meminfo source
  # is overridable via INSTALL_RE_MEMINFO_FILE — the self-test's seam.
  meminfo_file="${INSTALL_RE_MEMINFO_FILE:-/proc/meminfo}"
  [ -r "$meminfo_file" ] || fail preflight "memory: cannot read $meminfo_file"
  mem_kib=""
  while read -r key value rest; do
    if [ "$key" = "MemAvailable:" ]; then
      mem_kib="$value"
      break
    fi
  done <"$meminfo_file"
  case "$mem_kib" in
  '' | *[!0-9]*) fail preflight "memory: MemAvailable not found in $meminfo_file" ;;
  esac
  [ "$mem_kib" -ge 393216 ] || fail preflight "memory below 384 MiB floor"

  check_staging_dir "$HOME/opt"
  check_staging_dir "$HOME/opt/dist"

  # node/npx: reported for operator visibility, never fatal (Task 4 SKIP).
  if command -v node >/dev/null 2>&1 && command -v npx >/dev/null 2>&1; then
    echo "INSTALL-RE: preflight node/npx present ($REA_PIN invocable)"
  else
    echo "INSTALL-RE: preflight node/npx absent (reported only, never fatal)"
  fi

  if [ "${1:-}" = "--with-lock" ]; then
    acquire_lock
  fi
  ok preflight
}

self_test() {
  local fails=0 pin out rc tool bindir holder tries
  local fixhome badhome goodbin lowbin mem_good mem_low lock_file
  # NB: selftest_root is intentionally global (not local) so the EXIT trap
  # can still see it under `set -u` after this function returns.
  selftest_root=$(mktemp -d)
  trap 'chmod -R u+w "$selftest_root" 2>/dev/null; rm -rf "$selftest_root"' EXIT

  if [ "$OFFLINE" -eq 1 ]; then
    echo "SELF-TEST: offline ok"
  fi

  fixhome="$selftest_root/home"
  badhome="$selftest_root/badhome"
  goodbin="$selftest_root/goodbin"
  lowbin="$selftest_root/lowbin"
  mem_good="$selftest_root/meminfo-good"
  mem_low="$selftest_root/meminfo-low"
  lock_file="$fixhome/.install-re-runtime.lock"
  mkdir -p "$fixhome/opt/dist" "$goodbin" "$lowbin"
  # Unwritable staging fixture: opt is mode-stripped and dist is a regular
  # file, so the staging check fails closed for any euid.
  mkdir -p "$badhome/opt"
  printf 'not a directory\n' >"$badhome/opt/dist"
  chmod a-w "$badhome/opt"
  printf 'MemTotal:        8000000 kB\nMemAvailable:    1048576 kB\n' >"$mem_good"
  printf 'MemTotal:        8000000 kB\nMemAvailable:      65536 kB\n' >"$mem_low"

  # Good stub bin: dummy executables for the required tools (preflight
  # only checks their presence; it executes only df, awk, and flock),
  # a df reporting 10 GiB free, and symlinks to the real awk and flock.
  for tool in curl git gcc make unzip sha256sum tar pkg-config; do
    printf '#!/bin/bash\nexit 0\n' >"$goodbin/$tool"
  done
  cat >"$goodbin/df" <<'EOF'
#!/bin/bash
printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\n'
printf '/dev/stub 104857600 1 10485760 1%% /stub\n'
EOF
  cat >"$lowbin/df" <<'EOF'
#!/bin/bash
printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\n'
printf '/dev/stub 104857600 104750000 104857 100%% /stub\n'
EOF
  chmod +x "$goodbin"/* "$lowbin/df"
  ln -s "$(command -v awk)" "$goodbin/awk"
  ln -s "$(command -v flock)" "$goodbin/flock"

  # Per-case preflight inputs, mutated by each case and read by run_pf
  # (bash dynamic scoping makes self_test's locals visible to it).
  local ST_HOME="$fixhome" ST_PATH="$goodbin:$PATH" ST_MEM="$mem_good" ST_LOCK=0

  run_pf() {
    (
      HOME="$ST_HOME"
      PATH="$ST_PATH"
      INSTALL_RE_MEMINFO_FILE="$ST_MEM"
      export HOME PATH INSTALL_RE_MEMINFO_FILE
      if [ "$ST_LOCK" = "1" ]; then
        preflight --with-lock
      else
        preflight
      fi
    )
  }

  expect_pf_fail() { # $1 = case label, $2 = expected substring of the FAIL line
    local label="$1" needle="$2" pf_out pf_rc
    pf_out=$(run_pf 2>&1) && pf_rc=0 || pf_rc=$?
    if [ "$pf_rc" -ne 0 ] && printf '%s\n' "$pf_out" | grep -qF "$needle"; then
      echo "SELF-TEST: $label ok"
    else
      echo "SELF-TEST: $label FAIL: expected non-zero exit naming '$needle' (rc=$pf_rc)"
      printf '%s\n' "$pf_out"
      fails=$((fails + 1))
    fi
  }

  # (a) Any pin variable emptied in a subshell aborts assert_pins, naming
  # the field as unpinned.
  local unpinned_fails=0
  for pin in "${PIN_NAMES[@]}"; do
    out=$(
      (
        declare -n _pin_ref="$pin"
        _pin_ref=""
        assert_pins
      ) 2>&1
    ) && rc=0 || rc=$?
    if [ "$rc" -ne 1 ] || [ "$out" != "INSTALL-RE: pins FAIL: $pin unpinned" ]; then
      echo "SELF-TEST: unpinned-pin FAIL: $pin (rc=$rc, out='$out')"
      unpinned_fails=$((unpinned_fails + 1))
    fi
  done
  if [ "$unpinned_fails" -eq 0 ]; then
    echo "SELF-TEST: unpinned-pin ok"
  else
    fails=$((fails + unpinned_fails))
  fi

  # Positive control: preflight passes against the good fixture set.
  out=$(run_pf 2>&1) && rc=0 || rc=$?
  if [ "$rc" -eq 0 ] && printf '%s\n' "$out" | grep -qF "INSTALL-RE: preflight ok"; then
    echo "SELF-TEST: preflight-ok ok"
  else
    echo "SELF-TEST: preflight-ok FAIL: expected exit 0 with 'INSTALL-RE: preflight ok' (rc=$rc)"
    printf '%s\n' "$out"
    fails=$((fails + 1))
  fi

  # (b) Stub df reporting < 4 GiB free under $HOME fails closed on disk.
  ST_PATH="$lowbin:$goodbin:$PATH"
  expect_pf_fail preflight-low-disk "INSTALL-RE: preflight FAIL: disk:"
  ST_PATH="$goodbin:$PATH"

  # (c) Each required tool removed from the PATH in turn fails closed,
  # naming the missing tool. The restricted bin holds stubs for every
  # other required tool plus the real awk; nothing else leaks in.
  local missing_fails=0
  for tool in "${REQUIRED_TOOLS[@]}"; do
    bindir="$selftest_root/nobin-$tool"
    mkdir -p "$bindir"
    local other
    for other in "${REQUIRED_TOOLS[@]}"; do
      [ "$other" = "$tool" ] && continue
      cp "$goodbin/$other" "$bindir/$other" 2>/dev/null ||
        ln -s "$(command -v "$other")" "$bindir/$other"
      chmod +x "$bindir/$other"
    done
    ln -s "$(command -v awk)" "$bindir/awk"
    ST_PATH="$bindir"
    out=$(run_pf 2>&1) && rc=0 || rc=$?
    if [ "$rc" -eq 0 ] || ! printf '%s\n' "$out" | grep -qF "required tool '$tool' not found in PATH"; then
      echo "SELF-TEST: preflight-missing-tool FAIL: $tool (rc=$rc)"
      printf '%s\n' "$out"
      missing_fails=$((missing_fails + 1))
    fi
  done
  ST_PATH="$goodbin:$PATH"
  if [ "$missing_fails" -eq 0 ]; then
    echo "SELF-TEST: preflight-missing-tool ok"
  else
    fails=$((fails + missing_fails))
  fi

  # (d) A second invocation while a first holds the lock fails closed,
  # naming the lock.
  # The holder execs sleep while holding the lock on fd 9, so killing it
  # releases the lock and leaves no orphan behind.
  bash -c 'exec 9>"$0"; flock -x 9; exec sleep 10' "$lock_file" >/dev/null 2>&1 &
  holder=$!
  tries=0
  while flock -n "$lock_file" true 2>/dev/null; do
    tries=$((tries + 1))
    if [ "$tries" -gt 50 ]; then
      break
    fi
    sleep 0.1
  done
  ST_LOCK=1
  expect_pf_fail preflight-held-lock "another install-re-runtime run holds the lock"
  ST_LOCK=0
  kill "$holder" 2>/dev/null || true
  wait "$holder" 2>/dev/null || true

  # (e) Stubbed MemAvailable below the 384 MiB floor fails closed on memory.
  ST_MEM="$mem_low"
  expect_pf_fail preflight-low-memory "memory below 384 MiB floor"
  ST_MEM="$mem_good"

  # (f) Fixture $HOME whose staging path is unwritable fails closed on
  # staging.
  ST_HOME="$badhome"
  expect_pf_fail preflight-unwritable-staging "staging"
  ST_HOME="$fixhome"

  return "$fails"
}

main() {
  assert_pins
  if [ "$DRY_RUN" -eq 1 ]; then
    # Dry runs short-circuit before the lock and create nothing; the full
    # plan-lines semantics land in Task 5. Until then the skeleton stays
    # fail-closed.
    preflight
    fail main "stages not yet implemented"
  fi
  preflight --with-lock
  fail main "stages not yet implemented"
}

case "${1:-}" in
--self-test)
  if [ "${2:-}" = "--offline" ]; then
    OFFLINE=1
  fi
  rc=0
  self_test || rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "SELF-TEST: $rc assertion(s) failed"
    exit 1
  fi
  echo "SELF-TEST: all ok"
  ;;
--dry-run)
  DRY_RUN=1
  main
  ;;
"")
  main
  ;;
*)
  echo "usage: $0 [--self-test [--offline]] [--dry-run]" >&2
  exit 2
  ;;
esac
