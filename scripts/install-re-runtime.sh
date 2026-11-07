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

# Set by fetch_and_verify: the verified artifact path for this run.
# A global (not stdout) so a fail inside fetch_and_verify prints its
# INSTALL-RE line to the run's stdout instead of a capture buffer.
FETCHED_PATH=""

checksum_ok() { # $1 = file, $2 = expected sha256; silent, exit status only
  printf '%s  %s\n' "$2" "$1" | sha256sum -c - >/dev/null 2>&1
}

fetch_and_verify() { # $1 = url, $2 = sha256, $3 = dest name (upstream asset name)
  local url="$1" sha="$2" dest_name="$3"
  local dist="$HOME/opt/dist" dest part
  dest="$dist/$dest_name"
  part="$dest.part"
  mkdir -p "$dist"
  if [ -e "$dest" ]; then
    if checksum_ok "$dest" "$sha"; then
      FETCHED_PATH="$dest"
      return 0
    fi
    rm -f "$dest"
  fi
  rm -f "$part"
  curl --fail -L -o "$part" "$url" || {
    rm -f "$part"
    fail download "$dest_name download failed"
  }
  if ! checksum_ok "$part" "$sha"; then
    rm -f "$part"
    fail checksum "$dest_name sha256 mismatch"
  fi
  mv "$part" "$dest"
  FETCHED_PATH="$dest"
}

# Probes verify completeness, not presence; they print nothing and exit
# 0 only for a complete install (see the per-component notes below).
probe_temurin() {
  local dir="$HOME/opt/jdk-$TEMURIN_VERSION" version_out
  [ -x "$dir/bin/java" ] || return 1
  [ -x "$dir/bin/javac" ] || return 1
  # A bare java -version passes on a tar interrupted before the trust
  # store landed, so cacerts is part of the probe, not an afterthought.
  [ -e "$dir/lib/security/cacerts" ] || return 1
  version_out=$("$dir/bin/java" -version 2>&1) || return 1
  case "$version_out" in
  *"${TEMURIN_VERSION%%+*}"*) return 0 ;;
  *) return 1 ;;
  esac
}

install_temurin() {
  local dir="$HOME/opt/jdk-$TEMURIN_VERSION"
  if probe_temurin; then
    echo "INSTALL-RE: temurin ok (already installed)"
    return 0
  fi
  # Partial installs are rebuilt, never patched in place.
  rm -rf "$dir"
  mkdir -p "$HOME/opt"
  fetch_and_verify "$TEMURIN_URL" "$TEMURIN_SHA256" "$TEMURIN_TARBALL"
  tar -xzf "$FETCHED_PATH" -C "$HOME/opt" ||
    fail temurin "extraction failed for $TEMURIN_TARBALL"
  probe_temurin || fail temurin "installed tree failed the completeness probe"
  ok temurin
}

probe_ghidra() {
  local dir="$HOME/opt/ghidra_${GHIDRA_VERSION}_PUBLIC"
  [ -x "$dir/support/analyzeHeadless" ] || return 1
  # launch.sh sits ~24 zip entries after analyzeHeadless; an extraction
  # killed in that window otherwise leaves a probe-passing Ghidra that
  # cannot boot, so it is part of the probe.
  [ -e "$dir/support/launch.sh" ] || return 1
  return 0
}

install_ghidra() {
  local dir="$HOME/opt/ghidra_${GHIDRA_VERSION}_PUBLIC"
  if probe_ghidra; then
    echo "INSTALL-RE: ghidra ok (already installed)"
    return 0
  fi
  # Partial installs are rebuilt, never patched in place.
  rm -rf "$dir"
  mkdir -p "$HOME/opt"
  fetch_and_verify "$GHIDRA_URL" "$GHIDRA_SHA256" "$GHIDRA_ZIP"
  unzip -q -o "$FETCHED_PATH" -d "$HOME/opt" ||
    fail ghidra "extraction failed for $GHIDRA_ZIP"
  probe_ghidra || fail ghidra "installed tree failed the completeness probe"
  ok ghidra
}

probe_radare2() {
  local dir="$HOME/opt/radare2" version_out
  [ -x "$dir/bin/r2" ] || return 1
  # r2sdb is laid down last by the install target and the data tree
  # after binr, so a bin+lib-only tree passes r2 -v while missing both;
  # they are part of the probe, not afterthoughts.
  [ -x "$dir/bin/r2sdb" ] || return 1
  [ -d "$dir/share/radare2/$R2_VERSION/fcnsign" ] || return 1
  [ -d "$dir/share/radare2/$R2_VERSION/syscall" ] || return 1
  # Without LD_LIBRARY_PATH every r2 tool fails to load libr_util.so,
  # so the probe sets it — a healthy install must not look broken.
  version_out=$(LD_LIBRARY_PATH="$HOME/opt/radare2/lib" "$dir/bin/r2" -v 2>&1) || return 1
  case "$version_out" in
  *"$R2_VERSION"*) return 0 ;;
  *) return 1 ;;
  esac
}

install_radare2() {
  local dir="$HOME/opt/radare2" src="$HOME/opt/dist/radare2-src" head
  if probe_radare2; then
    echo "INSTALL-RE: radare2 ok (already installed)"
    return 0
  fi
  # Partial installs are rebuilt, never patched in place.
  rm -rf "$dir"
  mkdir -p "$HOME/opt/dist"
  # Reuse an existing clone only when its HEAD resolves; a corrupt or
  # partial clone left by a crashed run is removed and re-cloned, so it
  # cannot fail every future run.
  if [ -e "$src" ] && ! git -C "$src" rev-parse HEAD >/dev/null 2>&1; then
    rm -rf "$src"
  fi
  if [ ! -e "$src" ]; then
    git clone "$R2_REPO" "$src" || fail radare2 "clone failed for $R2_REPO"
  fi
  git -C "$src" checkout "$R2_VERSION" ||
    fail radare2 "checkout failed for tag $R2_VERSION"
  head=$(git -C "$src" rev-parse HEAD) ||
    fail radare2 "cannot resolve HEAD in $src"
  if [ "$head" != "$R2_COMMIT" ]; then
    fail radare2 "HEAD $head != pinned $R2_COMMIT"
  fi
  (cd "$src" && ./configure --prefix="$dir") ||
    fail radare2 "configure failed"
  (cd "$src" && make -j2) || fail radare2 "build failed (make -j2)"
  (cd "$src" && make install) || fail radare2 "make install failed"
  probe_radare2 || fail radare2 "installed tree failed the completeness probe"
  ok radare2
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

  # --- Task 2: Temurin/Ghidra download stages ---
  # Fixture archives are built from fixture install trees and served by a
  # stub curl; the stage functions run against a fixture $HOME with the
  # pin hashes overridden (in the stage subshell only) to the fixture
  # hashes, while tar/unzip/sha256sum stay real via symlinks.
  local stagehome serve_dir serve_trunc stagebin curl_log
  local jdk_src ghidra_src temurin_sha ghidra_sha tarball_size pass
  stagehome="$selftest_root/stagehome"
  serve_dir="$selftest_root/serve"
  serve_trunc="$selftest_root/serve-trunc"
  stagebin="$selftest_root/stagebin"
  curl_log="$selftest_root/curl.log"
  jdk_src="$selftest_root/src/jdk-$TEMURIN_VERSION"
  ghidra_src="$selftest_root/src/ghidra_${GHIDRA_VERSION}_PUBLIC"
  mkdir -p "$stagehome/opt/dist" "$serve_dir" "$serve_trunc" "$stagebin" \
    "$jdk_src/bin" "$jdk_src/lib/security" "$ghidra_src/support"
  cat >"$jdk_src/bin/java" <<'EOF'
#!/bin/bash
echo 'openjdk version "25.0.4.1" 2025-10-21 LTS' >&2
EOF
  printf '#!/bin/bash\nexit 0\n' >"$jdk_src/bin/javac"
  printf 'fixture trust store\n' >"$jdk_src/lib/security/cacerts"
  printf '#!/bin/bash\nexit 0\n' >"$ghidra_src/support/analyzeHeadless"
  printf '# fixture launch script\n' >"$ghidra_src/support/launch.sh"
  chmod +x "$jdk_src/bin/java" "$jdk_src/bin/javac" "$ghidra_src/support/analyzeHeadless"
  tar -czf "$serve_dir/$TEMURIN_TARBALL" -C "$selftest_root/src" "jdk-$TEMURIN_VERSION"
  if command -v zip >/dev/null 2>&1; then
    (cd "$selftest_root/src" && zip -qr "$serve_dir/$GHIDRA_ZIP" "ghidra_${GHIDRA_VERSION}_PUBLIC")
  else
    python3 -c 'import shutil, sys; shutil.make_archive(sys.argv[1], "zip", root_dir=sys.argv[2], base_dir=sys.argv[3])' \
      "${serve_dir}/${GHIDRA_ZIP%.zip}" "$selftest_root/src" "ghidra_${GHIDRA_VERSION}_PUBLIC"
  fi
  temurin_sha=$(sha256sum "$serve_dir/$TEMURIN_TARBALL" | awk '{print $1}')
  ghidra_sha=$(sha256sum "$serve_dir/$GHIDRA_ZIP" | awk '{print $1}')
  tarball_size=$(stat -c %s "$serve_dir/$TEMURIN_TARBALL")
  head -c "$((tarball_size / 2))" "$serve_dir/$TEMURIN_TARBALL" >"$serve_trunc/$TEMURIN_TARBALL"

  # Stub curl: serves fixture archives from $STAGE_SERVE_DIR by URL
  # basename and records every invocation in $STAGE_CURL_LOG.
  cat >"$stagebin/curl" <<'EOF'
#!/bin/bash
[ -n "${STAGE_CURL_LOG:-}" ] && printf '%s\n' "$*" >>"$STAGE_CURL_LOG"
out=""
url=""
while [ $# -gt 0 ]; do
  case "$1" in
  -o)
    out="$2"
    shift 2
    ;;
  -*)
    shift
    ;;
  *)
    url="$1"
    shift
    ;;
  esac
done
src="${STAGE_SERVE_DIR:?}/${url##*/}"
[ -f "$src" ] || exit 22
cp "$src" "$out"
EOF
  chmod +x "$stagebin/curl"
  for tool in tar unzip sha256sum; do
    ln -s "$(command -v "$tool")" "$stagebin/$tool"
  done

  # Per-case stage inputs, mutated by each case and read by run_stage
  # (bash dynamic scoping makes self_test's locals visible to it).
  local STG_HOME="$stagehome" STG_SERVE="$serve_dir" STG_TSHA="$temurin_sha" STG_GSHA="$ghidra_sha"

  run_stage() { # $1 = stage function name
    (
      HOME="$STG_HOME"
      PATH="$stagebin:$PATH"
      STAGE_SERVE_DIR="$STG_SERVE"
      STAGE_CURL_LOG="$curl_log"
      TEMURIN_SHA256="$STG_TSHA"
      GHIDRA_SHA256="$STG_GSHA"
      export HOME PATH STAGE_SERVE_DIR STAGE_CURL_LOG
      "$1"
    )
  }

  reset_stage() {
    rm -rf "$stagehome"
    mkdir -p "$stagehome/opt/dist"
    : >"$curl_log"
    STG_SERVE="$serve_dir"
    STG_TSHA="$temurin_sha"
    STG_GSHA="$ghidra_sha"
  }

  report_stage() { # $1 = case label, $2 = 1 on pass, 0 on fail
    if [ "$2" = "1" ]; then
      echo "SELF-TEST: $1 ok"
    else
      echo "SELF-TEST: $1 FAIL (rc=$rc)"
      printf '%s\n' "$out"
      fails=$((fails + 1))
    fi
  }

  # (a) Probe-pass: a complete fixture Temurin tree is skipped with the
  # already-installed line and curl is never invoked.
  reset_stage
  cp -a "$jdk_src" "$stagehome/opt/"
  out=$(run_stage install_temurin 2>&1) && rc=0 || rc=$?
  pass=0
  if [ "$rc" -eq 0 ] &&
    printf '%s\n' "$out" | grep -qF "INSTALL-RE: temurin ok (already installed)" &&
    [ ! -s "$curl_log" ]; then
    pass=1
  fi
  report_stage temurin-probe-skip "$pass"

  # (b) Wrong recorded hash: the run aborts at the checksum check, nothing
  # is extracted, and no .part or dest file survives in staging.
  reset_stage
  STG_TSHA="0000000000000000000000000000000000000000000000000000000000000000"
  out=$(run_stage install_temurin 2>&1) && rc=0 || rc=$?
  pass=0
  if [ "$rc" -ne 0 ] &&
    printf '%s\n' "$out" | grep -qF "INSTALL-RE: checksum FAIL: $TEMURIN_TARBALL sha256 mismatch" &&
    [ ! -e "$stagehome/opt/jdk-$TEMURIN_VERSION" ] &&
    [ ! -e "$stagehome/opt/dist/$TEMURIN_TARBALL" ] &&
    [ ! -e "$stagehome/opt/dist/$TEMURIN_TARBALL.part" ]; then
    pass=1
  fi
  report_stage temurin-checksum-mismatch "$pass"

  # (c) Truncated download (served file cut in half, hash recorded over
  # the full fixture): same checksum abort and clean staging as (b).
  reset_stage
  STG_SERVE="$serve_trunc"
  out=$(run_stage install_temurin 2>&1) && rc=0 || rc=$?
  pass=0
  if [ "$rc" -ne 0 ] &&
    printf '%s\n' "$out" | grep -qF "INSTALL-RE: checksum FAIL: $TEMURIN_TARBALL sha256 mismatch" &&
    [ ! -e "$stagehome/opt/jdk-$TEMURIN_VERSION" ] &&
    [ ! -e "$stagehome/opt/dist/$TEMURIN_TARBALL" ] &&
    [ ! -e "$stagehome/opt/dist/$TEMURIN_TARBALL.part" ]; then
    pass=1
  fi
  report_stage temurin-truncated-download "$pass"

  # (d) A pre-existing unrelated file in staging survives a full
  # (downloading) install run untouched.
  reset_stage
  printf 'do not touch\n' >"$stagehome/opt/dist/keepme.txt"
  out=$(run_stage install_temurin 2>&1) && rc=0 || rc=$?
  pass=0
  if [ "$rc" -eq 0 ] &&
    printf '%s\n' "$out" | grep -qxF "INSTALL-RE: temurin ok" &&
    [ -s "$curl_log" ] &&
    [ "$(cat "$stagehome/opt/dist/keepme.txt")" = "do not touch" ] &&
    [ -e "$stagehome/opt/jdk-$TEMURIN_VERSION/lib/security/cacerts" ]; then
    pass=1
  fi
  report_stage staging-preserves-unrelated "$pass"

  # fetch_and_verify reuse leg: a staged artifact that verifies is reused
  # with no download.
  reset_stage
  cp "$serve_dir/$TEMURIN_TARBALL" "$stagehome/opt/dist/$TEMURIN_TARBALL"
  out=$(run_stage install_temurin 2>&1) && rc=0 || rc=$?
  pass=0
  if [ "$rc" -eq 0 ] &&
    printf '%s\n' "$out" | grep -qxF "INSTALL-RE: temurin ok" &&
    [ ! -s "$curl_log" ]; then
    pass=1
  fi
  report_stage fetch-verified-reuse "$pass"

  # fetch_and_verify replace leg: a staged artifact that fails
  # verification is deleted and downloaded fresh.
  reset_stage
  printf 'corrupt staged bytes\n' >"$stagehome/opt/dist/$TEMURIN_TARBALL"
  out=$(run_stage install_temurin 2>&1) && rc=0 || rc=$?
  pass=0
  if [ "$rc" -eq 0 ] &&
    printf '%s\n' "$out" | grep -qxF "INSTALL-RE: temurin ok" &&
    [ -s "$curl_log" ] &&
    [ "$(sha256sum "$stagehome/opt/dist/$TEMURIN_TARBALL" | awk '{print $1}')" = "$temurin_sha" ]; then
    pass=1
  fi
  report_stage fetch-replaces-corrupt-staged "$pass"

  # (e) Partial-install healing, Temurin: java -version reports the right
  # version but the trust store is gone — the probe must fail and the
  # stage must rebuild, not skip.
  reset_stage
  cp -a "$jdk_src" "$stagehome/opt/"
  rm "$stagehome/opt/jdk-$TEMURIN_VERSION/lib/security/cacerts"
  out=$(run_stage install_temurin 2>&1) && rc=0 || rc=$?
  pass=0
  if [ "$rc" -eq 0 ] &&
    printf '%s\n' "$out" | grep -qxF "INSTALL-RE: temurin ok" &&
    [ -s "$curl_log" ] &&
    [ -e "$stagehome/opt/jdk-$TEMURIN_VERSION/lib/security/cacerts" ]; then
    pass=1
  fi
  report_stage temurin-partial-healing "$pass"

  # Probe-pass, Ghidra: a complete fixture tree is skipped with the
  # already-installed line and curl is never invoked.
  reset_stage
  cp -a "$ghidra_src" "$stagehome/opt/"
  out=$(run_stage install_ghidra 2>&1) && rc=0 || rc=$?
  pass=0
  if [ "$rc" -eq 0 ] &&
    printf '%s\n' "$out" | grep -qF "INSTALL-RE: ghidra ok (already installed)" &&
    [ ! -s "$curl_log" ]; then
    pass=1
  fi
  report_stage ghidra-probe-skip "$pass"

  # (e) Partial-install healing, Ghidra: analyzeHeadless is present and
  # executable but launch.sh is gone — the probe must fail and the stage
  # must rebuild, not skip.
  reset_stage
  cp -a "$ghidra_src" "$stagehome/opt/"
  rm "$stagehome/opt/ghidra_${GHIDRA_VERSION}_PUBLIC/support/launch.sh"
  out=$(run_stage install_ghidra 2>&1) && rc=0 || rc=$?
  pass=0
  if [ "$rc" -eq 0 ] &&
    printf '%s\n' "$out" | grep -qxF "INSTALL-RE: ghidra ok" &&
    [ -s "$curl_log" ] &&
    [ -x "$stagehome/opt/ghidra_${GHIDRA_VERSION}_PUBLIC/support/analyzeHeadless" ] &&
    [ -e "$stagehome/opt/ghidra_${GHIDRA_VERSION}_PUBLIC/support/launch.sh" ]; then
    pass=1
  fi
  report_stage ghidra-partial-healing "$pass"

  # --- Task 3: radare2 source-build stage ---
  # Stub git and make in r2bin serve a fixture build: git clone
  # materializes a source dir whose ./configure is a no-op stub, and
  # make install copies the complete fixture install tree
  # ($STAGE_R2_TREE) into $HOME/opt/radare2. Every git/make invocation
  # is appended to the build log.
  local r2bin r2_tree build_log
  r2bin="$selftest_root/r2bin"
  r2_tree="$selftest_root/src/radare2-tree"
  build_log="$selftest_root/build.log"
  mkdir -p "$r2bin" "$r2_tree/bin" \
    "$r2_tree/share/radare2/$R2_VERSION/fcnsign" \
    "$r2_tree/share/radare2/$R2_VERSION/syscall"
  # The fixture r2 exits 1 unless LD_LIBRARY_PATH contains the install
  # lib dir — mirroring the real tools' libr_util.so failure — so a
  # passing probe proves the probe sets it (case (c)).
  cat >"$r2_tree/bin/r2" <<'EOF'
#!/bin/bash
case ":${LD_LIBRARY_PATH:-}:" in
*":$HOME/opt/radare2/lib:"*) ;;
*) exit 1 ;;
esac
echo 'radare2 6.2.6 +1 abi:174 @ linux-x86_64'
EOF
  printf '#!/bin/bash\nexit 0\n' >"$r2_tree/bin/r2sdb"
  printf 'fixture fcnsign data\n' >"$r2_tree/share/radare2/$R2_VERSION/fcnsign/fixture.sdb"
  printf 'fixture syscall data\n' >"$r2_tree/share/radare2/$R2_VERSION/syscall/fixture.sdb"
  chmod +x "$r2_tree/bin/r2" "$r2_tree/bin/r2sdb"

  cat >"$r2bin/git" <<'EOF'
#!/bin/bash
[ -n "${STAGE_BUILD_LOG:-}" ] && printf 'git %s\n' "$*" >>"$STAGE_BUILD_LOG"
if [ "${1:-}" = "clone" ]; then
  dest="${!#}"
  mkdir -p "$dest"
  printf '#!/bin/bash\nexit 0\n' >"$dest/configure"
  chmod +x "$dest/configure"
  : >"$dest/.stub-git-ok"
  exit 0
fi
dir="$2"
shift 2
case "${1:-}" in
rev-parse)
  [ -f "$dir/.stub-git-ok" ] || exit 128
  if [ "${2:-}" = "HEAD" ]; then
    printf '%s\n' "${STAGE_R2_HEAD:?}"
  fi
  ;;
checkout)
  [ -f "$dir/.stub-git-ok" ] || exit 128
  ;;
*)
  exit 0
  ;;
esac
EOF

  cat >"$r2bin/make" <<'EOF'
#!/bin/bash
[ -n "${STAGE_BUILD_LOG:-}" ] && printf 'make %s\n' "$*" >>"$STAGE_BUILD_LOG"
case " $* " in
*" install "*)
  mkdir -p "$HOME/opt"
  cp -a "${STAGE_R2_TREE:?}" "$HOME/opt/radare2"
  ;;
esac
exit 0
EOF
  chmod +x "$r2bin/git" "$r2bin/make"

  # Per-case radare2 inputs, mutated by each case and read by run_r2
  # (bash dynamic scoping makes self_test's locals visible to it).
  local STG_R2HEAD="$R2_COMMIT"

  run_r2() { # $1 = stage function name
    (
      HOME="$STG_HOME"
      PATH="$r2bin:$PATH"
      STAGE_BUILD_LOG="$build_log"
      STAGE_R2_HEAD="$STG_R2HEAD"
      STAGE_R2_TREE="$r2_tree"
      export HOME PATH STAGE_BUILD_LOG STAGE_R2_HEAD STAGE_R2_TREE
      "$1"
    )
  }

  reset_r2() {
    reset_stage
    : >"$build_log"
    STG_R2HEAD="$R2_COMMIT"
  }

  # (c) Probe case: the fixture r2 fails without the lib dir in
  # LD_LIBRARY_PATH, so a silent exit-0 probe proves the probe sets it.
  reset_r2
  cp -a "$r2_tree" "$stagehome/opt/radare2"
  out=$(run_r2 probe_radare2 2>&1) && rc=0 || rc=$?
  pass=0
  if [ "$rc" -eq 0 ] && [ -z "$out" ]; then
    pass=1
  fi
  report_stage radare2-probe-ld-library-path "$pass"

  # Probe-pass: a complete fixture radare2 tree is skipped with the
  # already-installed line and git/make are never invoked.
  out=$(run_r2 install_radare2 2>&1) && rc=0 || rc=$?
  pass=0
  if [ "$rc" -eq 0 ] &&
    printf '%s\n' "$out" | grep -qF "INSTALL-RE: radare2 ok (already installed)" &&
    [ ! -s "$build_log" ]; then
    pass=1
  fi
  report_stage radare2-probe-skip "$pass"

  # (a) A HEAD other than the pinned commit after checkout aborts,
  # naming the got commit against the pin, before any build step.
  reset_r2
  STG_R2HEAD="1111111111111111111111111111111111111111"
  out=$(run_r2 install_radare2 2>&1) && rc=0 || rc=$?
  pass=0
  if [ "$rc" -ne 0 ] &&
    printf '%s\n' "$out" | grep -qF "INSTALL-RE: radare2 FAIL: HEAD 1111111111111111111111111111111111111111 != pinned $R2_COMMIT" &&
    ! grep -q '^make ' "$build_log"; then
    pass=1
  fi
  report_stage radare2-head-mismatch "$pass"

  # Fresh install: clone, pinned checkout, configure, build, install,
  # re-probe — ending in the plain ok line.
  reset_r2
  out=$(run_r2 install_radare2 2>&1) && rc=0 || rc=$?
  pass=0
  if [ "$rc" -eq 0 ] &&
    printf '%s\n' "$out" | grep -qxF "INSTALL-RE: radare2 ok"; then
    pass=1
  fi
  report_stage radare2-fresh-install "$pass"

  # (b) The build invocation in the log is make -j2 exactly: present as
  # a whole line, never a bare make line, never an nproc-derived -j.
  pass=0
  if grep -qxF "make -j2" "$build_log" &&
    ! grep -qxF "make" "$build_log" &&
    ! grep -qF "nproc" "$build_log"; then
    pass=1
  fi
  report_stage radare2-make-j2 "$pass"

  # (d) The fresh install above cloned the upstream repo named by the
  # pin, and the script text carries no packaged radare2 path and no
  # fork source (patterns are bracket-escaped so they cannot match
  # this check's own line).
  pass=0
  if grep -qF "git clone $R2_REPO " "$build_log" &&
    [ "$R2_REPO" = "https://github.com/radareorg/radare2" ] &&
    ! grep -Eq 'ap[t](-get)?[[:space:]]' "$0" &&
    ! grep -Eq 'pratik-saptarshi/radare[2]' "$0"; then
    pass=1
  fi
  report_stage radare2-upstream-source "$pass"

  # (e) Partial-install healing: r2 -v works but r2sdb and the whole
  # share/ data tree are gone — the probe must fail and the stage must
  # rebuild, not skip (the bin+lib-only tree from the wringer probe).
  reset_r2
  cp -a "$r2_tree" "$stagehome/opt/radare2"
  rm "$stagehome/opt/radare2/bin/r2sdb"
  rm -rf "$stagehome/opt/radare2/share"
  out=$(run_r2 install_radare2 2>&1) && rc=0 || rc=$?
  pass=0
  if [ "$rc" -eq 0 ] &&
    printf '%s\n' "$out" | grep -qxF "INSTALL-RE: radare2 ok" &&
    [ -s "$build_log" ] &&
    [ -x "$stagehome/opt/radare2/bin/r2sdb" ] &&
    [ -d "$stagehome/opt/radare2/share/radare2/$R2_VERSION/fcnsign" ] &&
    [ -d "$stagehome/opt/radare2/share/radare2/$R2_VERSION/syscall" ]; then
    pass=1
  fi
  report_stage radare2-partial-healing "$pass"

  # Corrupt-clone healing: a leftover clone dir whose HEAD does not
  # resolve is removed and re-cloned, not failed on forever.
  reset_r2
  mkdir -p "$stagehome/opt/dist/radare2-src"
  printf 'partial clone debris\n' >"$stagehome/opt/dist/radare2-src/README"
  out=$(run_r2 install_radare2 2>&1) && rc=0 || rc=$?
  pass=0
  if [ "$rc" -eq 0 ] &&
    printf '%s\n' "$out" | grep -qxF "INSTALL-RE: radare2 ok" &&
    grep -qF "git clone $R2_REPO " "$build_log" &&
    [ -x "$stagehome/opt/radare2/bin/r2sdb" ]; then
    pass=1
  fi
  report_stage radare2-corrupt-clone-healing "$pass"

  # Clone reuse: with the install tree removed but a valid clone left
  # by the run above, a second run checks the tag out again without
  # re-cloning.
  rm -rf "$stagehome/opt/radare2"
  : >"$build_log"
  out=$(run_r2 install_radare2 2>&1) && rc=0 || rc=$?
  pass=0
  if [ "$rc" -eq 0 ] &&
    printf '%s\n' "$out" | grep -qxF "INSTALL-RE: radare2 ok" &&
    ! grep -qF "git clone " "$build_log" &&
    grep -qF "git -C $stagehome/opt/dist/radare2-src checkout $R2_VERSION" "$build_log"; then
    pass=1
  fi
  report_stage radare2-clone-reuse "$pass"

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
