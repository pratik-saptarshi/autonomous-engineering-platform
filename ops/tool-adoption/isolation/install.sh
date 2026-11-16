#!/bin/sh
# Pinned, verifying installer for the isolation stack — the adopt-as-tool
# pattern instance described in ops/tool-adoption/isolation/ADOPTION.md.
#
# What this script does, in order:
#   1. Runs the substrate prerequisite checks for THIS runtime class
#      (systemd as PID 1; unshare/systemd-run/git/python3 present;
#      /dev/kvm noted). Two substrate facts are checked and reported
#      LOUDLY, because silently assuming them is how the pilot's
#      criterion 2 failed:
#        - if /sys/fs/cgroup/cgroup.controllers is empty, NO cgroup
#          resource cap is enforceable on this runtime — the script
#          prints the standing warning from ADOPTION.md and continues
#          (the stack is adopted as a confinement boundary there,
#          never as a resource-capped one);
#        - if /dev/kvm is absent, gVisor runs on systrap and
#          microVM-class boundaries are unavailable.
#   2. Composite (default boundary): verifies the committed artefacts
#      against the SHA256 pins below BEFORE placing anything, builds
#      the sandbox-gate binary from its pinned source, places the
#      launchers and inner.sh, renders the criterion-1 probe with the
#      local operator home, and smoke-tests the gate end-to-end plus
#      the launcher's fail-closed usage path.
#   3. gVisor (opt-in boundary): if the pinned runsc is already
#      installed and its binary hash matches the pin, does nothing.
#      Otherwise downloads the PINNED release tarball and its .sha512
#      sidecar, verifies the SHA512 (sidecar + the constant pinned in
#      this script) BEFORE extraction, and only executes runsc
#      (--version smoke) after the extracted binary's SHA256 matches
#      the pin. Never execute an unverified binary.
#   4. nsjail (additional profile): the Homebrew route (see
#      ADOPTION.md — the earlier apt authorization went unused; NO
#      system packages are installed by this script). Ensures the
#      unprivileged linuxbrew user + Homebrew prefix exist, pours the
#      pinned dependency set as bottles, clones nsjail at the pinned
#      tag and verifies the commit, builds it with the recorded
#      wiring, places the profile template and the sibling launcher,
#      and smoke-tests with a --dry-run render (payload NOT executed).
#   5. Incus: there is deliberately NO step. Incus is
#      adopted-in-pattern, blocked on this runtime class (ADOPTION.md,
#      component 4). The script prints that fact and moves on.
#
# Idempotent: re-running verifies installed copies against the pins
# and skips work whose results already match.
#
# Layout (PREFIX defaults to $HOME; override with ISOLATION_PREFIX):
#   $PREFIX/workspace/bin/sandbox-run            composite launcher
#   $PREFIX/workspace/bin/sandbox-run-nsjail     nsjail launcher
#   $PREFIX/workspace/bin/sandbox-gate           built gate binary
#   $PREFIX/workspace/isolation-pilot/inner.sh   sandbox root builder
#   $PREFIX/workspace/isolation-pilot/probes/    criterion probes
#   $PREFIX/workspace/gvisor/bin/                pinned runsc layout
#   $PREFIX/workspace/nsjail/                    nsjail source + profile
#   /home/linuxbrew/.linuxbrew                   Homebrew prefix (nsjail deps)
# For an isolated test install, point HOME and ISOLATION_PREFIX at a
# scratch directory: every $PREFIX path above follows. (The linuxbrew
# prefix is fixed by the Homebrew setup and does not follow PREFIX.)
#
# Usage: install.sh [--check] [--component composite|gvisor|nsjail]...
#   --check        run all checks and report component state; change
#                  nothing. Exit status is non-zero if a hard
#                  prerequisite is missing.
#   --component    restrict to the named component(s); repeatable.
#                  Default: all three.
#
# Tested on the origin runtime (Ubuntu 24.04, kernel 7.0.0-44, systemd
# 255, x86_64). Other runtimes of this class are handled by the checks
# failing loudly, not by silent adaptation.

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

# --- pins (verified first-hand at adoption time, 2026-11-14) ---------------

SHA_sandbox_run="7374076c471053159f8dfb56b9e084b418fe5d9fafd59a50d674c1c1a6f4095d"
SHA_sandbox_run_nsjail="1387caac25e705d29eec152e63b860aa15fe3130214a35b6b63600200582d3be"
SHA_inner_sh="66de07ba99ad6f50e71c380289ec61dadeed47f8214b746c7cc1558933f63fff"
SHA_gate_source="d1a9bdea0480d19280c6def5ac7f2145dfc1de9d4706f5a45e37d087b9d716f1"
# Origin build of the gate (gcc -O2 -static). Informational: if the
# installed binary matches, the build is skipped; a fresh build's hash
# is reported, and may differ under a different toolchain.
SHA_gate_binary_origin="0e23eb3bd54e660743cfe1c2f0ccc2e2cad5f8e7bff848c6573ff0470ccd9762"
SHA_probe_reads_tmpl="2c5490304aca06d884e8039d6e8f71bf10c10f3a604bd97604b8b5c189b23cc2"
SHA_probe_layers="d5b4c521d24d037df8f55dae79d680a76bbf6911bf39fd1160e184521710053b"
SHA_hog="9cae2de8b9ac786d5368e25187fcd1e5079a1d5a42c2dcc3a57b30138ac29dff"
SHA_nsjail_cfg_tmpl="ed4204a87ed53e0cc6f478b298dce30e94f362bd6609c2473c7a0690fad99f04"

RUNSC_RELEASE="release-20261109.0"
RUNSC_TARBALL="gvisor.tar.bz2"
RUNSC_BASE="https://storage.googleapis.com/gvisor/releases/release/20261109.0/x86_64"
RUNSC_SHA512="1a6b8f74c37b4931ef473f67ec1f601690855bedc52ac709f2fac965c69677aa0426ef44598d8eee1aed72cfdb9df87a2a5f352cb3348880fc61a7732bc10f2a"
SHA_runsc_binary="c58f1dc2a3855487bf3bedc2edf074123ad433f1d98fb7f451f56790e87b5c9f"

NSJAIL_REPO="https://github.com/google/nsjail"
NSJAIL_TAG="3.6"
NSJAIL_COMMIT="f78475530b46d0186111a9096b30725f816b55fe"
BREW_PREFIX="/home/linuxbrew/.linuxbrew"
BREW_USER="linuxbrew"
# Recorded bottle versions at adoption time. Drift is warned about
# loudly (a version bump is a new adoption), not silently accepted.
BREW_PIN_protobuf="36.2"
BREW_PIN_libnl="3.12.0"
BREW_PIN_flex="2.6.11"
BREW_PIN_bison="3.8.2"
BREW_PIN_autoconf="2.73"
BREW_PIN_automake="1.20"
BREW_PIN_libtool="2.6.2"
BREW_PIN_pkgconf="3.0.10"

PREFIX="${ISOLATION_PREFIX:-$HOME}"
WS="$PREFIX/workspace"
BIN_DIR="$WS/bin"
PILOT_DIR="$WS/isolation-pilot"
GVISOR_DIR="$WS/gvisor"
NSJAIL_DIR="$WS/nsjail"

CHECK_ONLY=0
COMPONENTS=""
# simple arg parse (sh has no arrays)
prev=""
for arg in "$@"; do
  if [ "$prev" = "--component" ]; then
    COMPONENTS="$COMPONENTS $arg"
  fi
  case "$arg" in
    --check) CHECK_ONLY=1 ;;
    --component) ;;
    composite | gvisor | nsjail) ;;
    *) printf '%s\n' "install: WARNING: ignoring unrecognised argument: $arg" >&2 ;;
  esac
  prev="$arg"
done
[ -n "$COMPONENTS" ] || COMPONENTS=" composite gvisor nsjail"
want() { case "$COMPONENTS" in *" $1"*) return 0 ;; *) return 1 ;; esac }

say() { printf '%s\n' "install: $*"; }
die() { printf '%s\n' "install: ERROR: $*" >&2; exit 1; }
HARD_FAIL=0
hard() { printf '%s\n' "install: MISSING PREREQUISITE: $*" >&2; HARD_FAIL=1; }

sha_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    die "no sha256 tool (sha256sum / shasum) available; cannot verify artefacts"
  fi
}

sha512_of() {
  if command -v sha512sum >/dev/null 2>&1; then
    sha512sum "$1" | awk '{print $1}'
  else
    die "no sha512sum available; cannot verify the gVisor tarball"
  fi
}

fetch() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --retry 2 -o "$2" "$1"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$2" "$1"
  else
    die "neither curl nor wget is available; cannot download the gVisor release"
  fi
}

warn_no_controllers() {
  cat >&2 <<'EOF'
install: ================================================================
install: WARNING — NO CGROUP CONTROLLERS ARE DELEGATED ON THIS RUNTIME
install: /sys/fs/cgroup/cgroup.controllers is empty, so NO cgroup
install: resource cap is enforceable here: systemd-run MemoryMax,
install: nsjail cgroup limits, and gVisor OCI resources are recorded
install: but enforced by nothing. This stack is a CONFINEMENT
install: boundary on this runtime, NOT a resource-capped one.
install: See ops/tool-adoption/isolation/ADOPTION.md (criterion 2).
install: ================================================================
EOF
}

# --- substrate checks --------------------------------------------------------

substrate_checks() {
  say "substrate checks (this runtime class)"
  [ "$(uname -s)" = "Linux" ] || hard "not Linux: $(uname -s)"
  [ "$(uname -m)" = "x86_64" ] || hard "not x86_64: $(uname -m) (pins in this instance are x86_64)"
  pid1="$(ps -p 1 -o comm= 2>/dev/null | tr -d ' ' || true)"
  if [ "$pid1" = "systemd" ]; then
    say "ok: systemd is PID 1"
  else
    hard "PID 1 is '${pid1:-unknown}', not systemd — the composite's systemd-run scopes assume systemd as PID 1"
  fi
  for tool in unshare systemd-run git python3; do
    command -v "$tool" >/dev/null 2>&1 || hard "required tool missing: $tool"
  done
  controllers=""
  [ -f /sys/fs/cgroup/cgroup.controllers ] && controllers="$(cat /sys/fs/cgroup/cgroup.controllers)"
  if [ -z "$controllers" ]; then
    warn_no_controllers
  else
    say "ok: cgroup controllers delegated: $controllers (caps may be enforceable here — re-run the hog test to prove it)"
  fi
  if [ -e /dev/kvm ]; then
    say "note: /dev/kvm present (gVisor still runs on the pinned systrap platform)"
  else
    say "note: no /dev/kvm — gVisor uses systrap; microVM-class boundaries are unavailable on this runtime"
  fi
}

# --- placement helper ---------------------------------------------------------
# verify_artefact <file> <expected-sha256> — die on mismatch, always before use.
verify_artefact() {
  [ -f "$1" ] || die "committed artefact missing: $1"
  actual="$(sha_of "$1")"
  [ "$actual" = "$2" ] || die "artefact hash mismatch: $1 (computed $actual, pinned $2); aborting, nothing placed from it"
}

# ensure_dir <dir> — create an install-tree directory with an explicit
# 0755 mode. Installed directories must not inherit the caller's umask:
# under a restrictive umask (e.g. 077) a plain mkdir -p leaves them
# 0700, and the dropped-privilege payload uid (65534) then cannot
# traverse them to read the artefacts placed inside.
ensure_dir() {
  mkdir -p "$1"
  chmod 755 "$1"
}

# place <src> <dst> [mode] — idempotent copy; skips when identical.
place() {
  if [ -f "$2" ] && [ "$(sha_of "$1")" = "$(sha_of "$2")" ]; then
    say "already in place and verified: $2"
    return 0
  fi
  ensure_dir "$(dirname "$2")"
  cp "$1" "$2"
  chmod "${3:-755}" "$2"
  say "placed $2 (sha256 $(sha_of "$2"))"
}

# --- composite ---------------------------------------------------------------

install_composite() {
  say "component: rank-1 composite + sandbox-gate"
  verify_artefact "$SCRIPT_DIR/bin/sandbox-run" "$SHA_sandbox_run"
  verify_artefact "$SCRIPT_DIR/bin/inner.sh" "$SHA_inner_sh"
  verify_artefact "$SCRIPT_DIR/gate/sandbox-gate.c" "$SHA_gate_source"
  verify_artefact "$SCRIPT_DIR/probes/probe_reads.py" "$SHA_probe_reads_tmpl"
  verify_artefact "$SCRIPT_DIR/probes/probe_layers.py" "$SHA_probe_layers"
  verify_artefact "$SCRIPT_DIR/probes/hog.py" "$SHA_hog"
  say "all committed artefacts match their pins"

  GATE_BIN="$BIN_DIR/sandbox-gate"
  if [ -f "$GATE_BIN" ] && [ "$(sha_of "$GATE_BIN")" = "$SHA_gate_binary_origin" ]; then
    say "sandbox-gate already built and matches the origin build hash; skipping build"
  else
    cc_bin=""
    for c in gcc cc; do command -v "$c" >/dev/null 2>&1 && { cc_bin="$c"; break; }; done
    [ -n "$cc_bin" ] || die "no C compiler (gcc/cc) available; cannot build sandbox-gate from its pinned source"
    ensure_dir "$BIN_DIR"
    tmp_bin="$(mktemp)"
    # shellcheck disable=SC2086
    "$cc_bin" -O2 -static -o "$tmp_bin" "$SCRIPT_DIR/gate/sandbox-gate.c" ||
      die "sandbox-gate build failed (a static libc is required for 'gcc -O2 -static')"
    chmod 755 "$tmp_bin"
    mv "$tmp_bin" "$GATE_BIN"
    say "sandbox-gate built from pinned source (sha256 $(sha_of "$GATE_BIN"); origin build was $SHA_gate_binary_origin)"
  fi

  place "$SCRIPT_DIR/bin/sandbox-run" "$BIN_DIR/sandbox-run" 755
  place "$SCRIPT_DIR/bin/inner.sh" "$PILOT_DIR/inner.sh" 755
  place "$SCRIPT_DIR/probes/probe_layers.py" "$PILOT_DIR/probes/probe_layers.py" 755
  place "$SCRIPT_DIR/probes/hog.py" "$PILOT_DIR/probes/hog.py" 755

  # probe_reads.py is rendered: @OPERATOR_HOME@ -> the local PREFIX.
  rendered="$(mktemp)"
  sed "s|@OPERATOR_HOME@|$PREFIX|g" "$SCRIPT_DIR/probes/probe_reads.py" > "$rendered"
  if grep -q '@OPERATOR_HOME@' "$rendered"; then
    rm -f "$rendered"; die "probe_reads render left the placeholder unsubstituted"
  fi
  place "$rendered" "$PILOT_DIR/probes/probe_reads.py" 755
  rm -f "$rendered"

  # Smoke 1: the gate end-to-end on a scratch dir (Landlock + uid drop
  # + /bin/true as the payload), with a rule set shaped like the real
  # launcher's — an under-ruled smoke fails with EACCES on the payload
  # exec, which is the gate working, not a smoke pass. Fail-closed
  # means a Landlock-less kernel fails HERE, loudly, not on first
  # real use.
  smoke_dir="$(mktemp -d)"
  if ( cd "$smoke_dir" && "$GATE_BIN" --uid=65534 --gid=65534 \
        --rule=/:root --rule=/usr:ro --rule="$smoke_dir:rw" \
        -- /bin/true ) 2>"$smoke_dir/err"; then
    say "smoke test: sandbox-gate confines and execs a payload (exit 0)"
  else
    cat "$smoke_dir/err" >&2 || true
    rm -rf "$smoke_dir"
    die "smoke test failed: sandbox-gate could not confine a trivial payload (Landlock unavailable on this kernel?)"
  fi
  rm -rf "$smoke_dir"

  # Smoke 2: the launcher refuses cleanly with no arguments (exit 64).
  set +e
  HOME="$PREFIX" "$BIN_DIR/sandbox-run" >/dev/null 2>&1
  rc=$?
  set -e
  [ "$rc" -eq 64 ] || die "smoke test failed: sandbox-run with no arguments exited $rc, expected 64 (fail-closed usage)"
  say "smoke test: sandbox-run no-args exits 64 (fail-closed)"
}

# --- gVisor --------------------------------------------------------------------

install_gvisor() {
  say "component: gVisor / runsc ($RUNSC_RELEASE, systrap)"
  RUNSC_BIN="$GVISOR_DIR/bin/runsc"
  if [ -f "$RUNSC_BIN" ] && [ "$(sha_of "$RUNSC_BIN")" = "$SHA_runsc_binary" ]; then
    say "runsc already installed; binary matches the pin (not re-executing it for this check)"
    return 0
  fi
  staging="$(mktemp -d)"
  trap 'rm -rf "$staging"' EXIT INT TERM
  say "downloading $RUNSC_TARBALL and its .sha512 sidecar"
  fetch "$RUNSC_BASE/$RUNSC_TARBALL" "$staging/$RUNSC_TARBALL"
  fetch "$RUNSC_BASE/$RUNSC_TARBALL.sha512" "$staging/$RUNSC_TARBALL.sha512"
  computed="$(sha512_of "$staging/$RUNSC_TARBALL")"
  ( cd "$staging" && sha512sum -c "$RUNSC_TARBALL.sha512" >/dev/null ) ||
    die "SHA512 mismatch against the published sidecar (computed $computed); aborting, nothing installed"
  [ "$computed" = "$RUNSC_SHA512" ] ||
    die "SHA512 mismatch against the value pinned in this installer (computed $computed); aborting, nothing installed"
  say "tarball verified (sha512 $computed) before extraction"
  mkdir -p "$staging/extract"
  tar -xjf "$staging/$RUNSC_TARBALL" -C "$staging/extract"
  [ -f "$staging/extract/runsc" ] || die "tarball did not contain runsc at its expected path; aborting"
  bin_sha="$(sha_of "$staging/extract/runsc")"
  [ "$bin_sha" = "$SHA_runsc_binary" ] ||
    die "extracted runsc hash mismatch (computed $bin_sha, pinned $SHA_runsc_binary); aborting, nothing installed"
  ensure_dir "$GVISOR_DIR"
  ensure_dir "$GVISOR_DIR/bin"
  cp -a "$staging/extract/." "$GVISOR_DIR/bin/"
  say "runsc layout placed in $GVISOR_DIR/bin (runsc sha256 $bin_sha)"
  # First execution happens only now, after both verifications.
  version_out="$("$RUNSC_BIN" --version | awk '/^runsc version/{print $3}')"
  [ "$version_out" = "$RUNSC_RELEASE" ] ||
    die "smoke test failed: runsc --version printed '$version_out', expected $RUNSC_RELEASE"
  say "smoke test: runsc --version -> $RUNSC_RELEASE"
  trap - EXIT INT TERM
  rm -rf "$staging"
}

# --- nsjail --------------------------------------------------------------------

brew_as_user() {
  # brew_as_user <command...> — run as the linuxbrew user from its home.
  runuser -u "$BREW_USER" -- env HOME="/home/$BREW_USER" \
    HOMEBREW_NO_ANALYTICS=1 HOMEBREW_NO_AUTO_UPDATE=1 "$@"
}

install_nsjail() {
  say "component: nsjail $NSJAIL_TAG (Homebrew route; no system packages)"
  verify_artefact "$SCRIPT_DIR/nsjail/eval-lane.cfg.tmpl" "$SHA_nsjail_cfg_tmpl"
  verify_artefact "$SCRIPT_DIR/bin/sandbox-run-nsjail" "$SHA_sandbox_run_nsjail"

  SRC="$NSJAIL_DIR/src"
  if [ -d "$SRC/.git" ] && [ -f "$SRC/nsjail" ]; then
    head_rev="$(git -C "$SRC" rev-parse HEAD)"
    [ "$head_rev" = "$NSJAIL_COMMIT" ] ||
      die "existing nsjail source is at $head_rev, not the pinned $NSJAIL_COMMIT — refusing to move a pin silently"
    say "nsjail already built at the pinned commit; skipping brew/build steps"
  else
    # Homebrew user + prefix (container-style setup; brew refuses root).
    if ! id "$BREW_USER" >/dev/null 2>&1; then
      [ "$(id -u)" -eq 0 ] ||
        die "user '$BREW_USER' does not exist and this script is not running as root to create it. As root, run: useradd -m -d /home/linuxbrew -s /bin/bash linuxbrew"
      useradd -m -d "/home/$BREW_USER" -s /bin/bash "$BREW_USER"
      say "created unprivileged user $BREW_USER"
    fi
    command -v runuser >/dev/null 2>&1 ||
      die "runuser is required to invoke brew as $BREW_USER; not found"
    if [ ! -x "$BREW_PREFIX/bin/brew" ]; then
      mkdir -p "$BREW_PREFIX"
      chown -R "$BREW_USER:$BREW_USER" "/home/$BREW_USER"
      brew_as_user git clone https://github.com/Homebrew/brew "$BREW_PREFIX/Homebrew"
      brew_as_user mkdir -p "$BREW_PREFIX/bin"
      brew_as_user ln -sf ../Homebrew/bin/brew "$BREW_PREFIX/bin/brew"
      say "Homebrew cloned into $BREW_PREFIX"
    fi
    brew_as_user "$BREW_PREFIX/bin/brew" install \
      protobuf libnl flex bison autoconf automake libtool pkgconf
    versions="$(brew_as_user "$BREW_PREFIX/bin/brew" list --versions \
      protobuf libnl flex bison autoconf automake libtool pkgconf || true)"
    say "brew dependency versions: $versions"
    versions_flat="$(printf '%s' "$versions" | tr '\n' ' ')"
    drift=""
    for pair in "protobuf $BREW_PIN_protobuf" "libnl $BREW_PIN_libnl" \
                "flex $BREW_PIN_flex" "bison $BREW_PIN_bison" \
                "autoconf $BREW_PIN_autoconf" "automake $BREW_PIN_automake" \
                "libtool $BREW_PIN_libtool" "pkgconf $BREW_PIN_pkgconf"; do
      # pair is "name version"
      set -- $pair
      case " $versions_flat " in
        *" $1 $2 "*) ;;
        *) drift="$drift $1(expected $2)" ;;
      esac
    done
    [ -z "$drift" ] ||
      printf '%s\n' "install: WARNING: brew dependency drift vs the adoption record:$drift — a version bump is a new adoption; record it before relying on the build" >&2

    # Pinned source build.
    ensure_dir "$NSJAIL_DIR"
    if [ ! -d "$SRC/.git" ]; then
      git clone "$NSJAIL_REPO" "$SRC"
    fi
    git -C "$SRC" checkout --quiet "$NSJAIL_TAG"
    head_rev="$(git -C "$SRC" rev-parse HEAD)"
    [ "$head_rev" = "$NSJAIL_COMMIT" ] ||
      die "nsjail checkout is at $head_rev after selecting tag $NSJAIL_TAG, not the pinned $NSJAIL_COMMIT; aborting"
    git -C "$SRC" submodule update --init kafel
    (
      cd "$SRC"
      PATH="$BREW_PREFIX/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
      PKG_CONFIG_PATH="$BREW_PREFIX/lib/pkgconfig" \
      LDFLAGS="-Wl,-rpath,$BREW_PREFIX/lib" \
        make -j4
    )
    [ -x "$SRC/nsjail" ] || die "nsjail build finished without a binary at $SRC/nsjail"
    say "nsjail built at pin $NSJAIL_TAG (binary sha256 $(sha_of "$SRC/nsjail"))"
  fi

  place "$SCRIPT_DIR/nsjail/eval-lane.cfg.tmpl" "$NSJAIL_DIR/eval-lane.cfg.tmpl" 644
  place "$SCRIPT_DIR/bin/sandbox-run-nsjail" "$BIN_DIR/sandbox-run-nsjail" 755

  # Smoke: --dry-run renders the config; the payload is NOT executed.
  smoke_work="$(mktemp -d)"; smoke_out="$(mktemp -d)"
  HOME="$PREFIX" NSJAIL_HOME="$NSJAIL_DIR" "$BIN_DIR/sandbox-run-nsjail" \
    --work "$smoke_work" --out "$smoke_out" --dry-run -- /bin/true >/dev/null 2>&1 ||
    die "smoke test failed: sandbox-run-nsjail --dry-run did not render a config"
  rm -rf "$smoke_work" "$smoke_out"
  say "smoke test: sandbox-run-nsjail --dry-run renders the profile (payload not executed)"
}

# --- state report (--check) -----------------------------------------------------

check_one() {
  if [ -f "$1" ]; then
    if [ "$(sha_of "$1")" = "$2" ]; then say "ok (pin match): $1"; else say "present, hash DIFFERS from pin: $1"; fi
  else
    say "absent: $1"
  fi
}

report_state() {
  say "state report (nothing changed)"
  want composite && {
    check_one "$BIN_DIR/sandbox-run" "$SHA_sandbox_run"
    check_one "$BIN_DIR/sandbox-gate" "$SHA_gate_binary_origin"
    check_one "$PILOT_DIR/inner.sh" "$SHA_inner_sh"
  }
  want gvisor && check_one "$GVISOR_DIR/bin/runsc" "$SHA_runsc_binary"
  want nsjail && {
    check_one "$BIN_DIR/sandbox-run-nsjail" "$SHA_sandbox_run_nsjail"
    check_one "$NSJAIL_DIR/eval-lane.cfg.tmpl" "$SHA_nsjail_cfg_tmpl"
    if [ -d "$NSJAIL_DIR/src/.git" ]; then
      say "nsjail source HEAD: $(git -C "$NSJAIL_DIR/src" rev-parse HEAD) (pin $NSJAIL_COMMIT)"
    else
      say "absent: $NSJAIL_DIR/src"
    fi
  }
  say "incus: adopted-in-pattern, blocked on this runtime — no installed state exists or is expected (ADOPTION.md component 4)"
}

# --- main ------------------------------------------------------------------------

say "isolation stack -> $PREFIX (components:$COMPONENTS)"
substrate_checks
if [ "$CHECK_ONLY" -eq 1 ]; then
  report_state
  [ "$HARD_FAIL" -eq 0 ] || die "hard prerequisites missing (see above)"
  say "check complete"
  exit 0
fi
[ "$HARD_FAIL" -eq 0 ] || die "hard prerequisites missing (see above); nothing installed"

ensure_dir "$WS"
ensure_dir "$BIN_DIR"

want composite && install_composite
want gvisor && install_gvisor
want nsjail && install_nsjail

say "incus: SKIPPED by design — adopted-in-pattern, blocked on this runtime (ADOPTION.md component 4); no installer step exists"
say "done: isolation stack installed and verified under $PREFIX"
