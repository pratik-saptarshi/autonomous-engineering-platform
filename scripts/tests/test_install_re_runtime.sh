#!/usr/bin/env bash
# test_install_re_runtime.sh — behavioral tests for
# scripts/install-re-runtime.sh.
#
# Every case runs the real installer against a fixture HOME with stub
# tools (curl/git/make/sha256sum) on the fixture PATH, covering what
# the script's stub-based --self-test cannot: end-to-end stage
# sequencing, --dry-run plan lines, and verify_all.
#
# Two rules are load-bearing (wringer amendment):
# - The script under test is launched by absolute path
#   (/bin/bash <script>), never via a stub-PATH bash — a stub bash
#   would intercept the launch itself.
# - No bash stub is ever placed on the fixture PATH, because a stubbed
#   `bash -lc` proves only that the words were invoked. Case (c) is
#   proven through the real /bin/bash -lc against the fixture HOME.
#
# Checksum seam: the sha256sum stub passes `-c` verification and
# delegates everything else to the real tool. The pin hashes cover the
# real upstream artifacts, which fixture tarballs cannot match;
# checksum integrity itself is covered by the script's --self-test
# mismatch/truncation cases, and this harness proves wiring.
#
# Fixture HOMEs live under the real $HOME, not /tmp: preflight
# requires >= 4 GiB free under $HOME and /tmp is a 512 MiB tmpfs.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT/scripts/install-re-runtime.sh"
SB="$(mktemp -d "$HOME/.test-install-re-runtime.XXXXXX")"
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

file_sha() { sha256sum "$1" | awk '{print $1}'; }

# Pinned values the fixture trees must print, read from the script's
# own pin block so a pin bump updates the fixtures with it.
pin_value() { grep "^$1=" "$SCRIPT" | head -1 | cut -d'"' -f2; }
TEMURIN_VERSION="$(pin_value TEMURIN_VERSION)"
GHIDRA_VERSION="$(pin_value GHIDRA_VERSION)"
R2_VERSION="$(pin_value R2_VERSION)"
R2_COMMIT="$(pin_value R2_COMMIT)"
TEMURIN_TARBALL="$(pin_value TEMURIN_TARBALL)"
GHIDRA_ZIP="$(pin_value GHIDRA_ZIP)"
TEMURIN_SHORT="${TEMURIN_VERSION%%+*}"

# --- Stub bin: curl/git/make/sha256sum. Never a bash stub. ---
mkdir -p "$SB/bin"
cat >"$SB/bin/curl" <<'EOF'
#!/bin/bash
[ -n "${HOME:-}" ] && printf 'curl %s\n' "$*" >>"$HOME/.stub-calls.log"
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
src="${STUB_SERVE_DIR:?}/${url##*/}"
[ -f "$src" ] || exit 22
cp "$src" "$out"
EOF
cat >"$SB/bin/git" <<'EOF'
#!/bin/bash
[ -n "${HOME:-}" ] && printf 'git %s\n' "$*" >>"$HOME/.stub-calls.log"
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
    printf '%s\n' "${STUB_R2_HEAD:?}"
  fi
  # Tag-presence form: rev-parse --verify -q refs/tags/<v> fails
  # while .stub-tag-absent is set — a clone that predates the
  # release: HEAD resolves (the reuse gate keeps it) but the tag
  # and its objects were never fetched.
  for arg in "$@"; do
    case "$arg" in
    refs/tags/*)
      [ ! -f "$dir/.stub-tag-absent" ] || exit 1
      ;;
    esac
  done
  ;;
fetch)
  [ -f "$dir/.stub-git-ok" ] || exit 128
  # fetch origin tag <v> brings in exactly that tag, clearing the
  # tag-absent state; .stub-fetch-fails models a network failure.
  if [ -f "$dir/.stub-fetch-fails" ]; then
    exit 1
  fi
  rm -f "$dir/.stub-tag-absent"
  ;;
checkout)
  [ -f "$dir/.stub-git-ok" ] || exit 128
  # While the tag is absent from the clone's refs, any checkout of
  # it fails with a pathspec error, forced or not (real git).
  if [ -f "$dir/.stub-tag-absent" ]; then
    printf "error: pathspec '%s' did not match any file(s) known to git\n" "${!#}" >&2
    exit 1
  fi
  # Working-tree model: a forced checkout discards tracked
  # modifications; a plain one leaves them in place (real-git
  # semantics). Untracked files survive either form.
  # Unrestorable state (.stub-unrestorable set): the forced
  # checkout still exits 0 but clears nothing — a restore that
  # reports success without healing the tree, as real git does
  # e.g. when clean -fd refuses an untracked nested git repo.
  for arg in "$@"; do
    if [ "$arg" = "-f" ] || [ "$arg" = "--force" ]; then
      if [ ! -f "$dir/.stub-unrestorable" ]; then
        rm -f "$dir/.stub-dirty-tracked"
      fi
    fi
  done
  ;;
clean)
  [ -f "$dir/.stub-git-ok" ] || exit 128
  # clean with a force flag removes untracked files; tracked
  # modifications are not clean's business. In the unrestorable
  # state (see checkout) it likewise exits 0 but removes nothing.
  for arg in "$@"; do
    case "$arg" in
    -*f*)
      if [ ! -f "$dir/.stub-unrestorable" ]; then
        rm -f "$dir/.stub-dirty-untracked"
      fi
      ;;
    esac
  done
  ;;
status)
  [ -f "$dir/.stub-git-ok" ] || exit 128
  if [ -f "$dir/.stub-dirty-tracked" ]; then
    printf ' M fixture.c\n'
  fi
  if [ -f "$dir/.stub-dirty-untracked" ]; then
    printf '?? fixture-new.c\n'
  fi
  ;;
*)
  exit 0
  ;;
esac
EOF
cat >"$SB/bin/make" <<'EOF'
#!/bin/bash
[ -n "${HOME:-}" ] && printf 'make %s\n' "$*" >>"$HOME/.stub-calls.log"
# Record the source tree's dirtiness at build time so a case can
# prove the build never consumed a dirty clone: make runs with the
# clone as its working directory.
if [ -n "${HOME:-}" ]; then
  built_dirty=0
  if [ -f ./.stub-dirty-tracked ] || [ -f ./.stub-dirty-untracked ]; then
    built_dirty=1
  fi
  printf 'make built-dirty=%s\n' "$built_dirty" >>"$HOME/.stub-calls.log"
fi
case " $* " in
*" install "*)
  mkdir -p "$HOME/opt"
  cp -r "${STUB_R2_TREE:?}" "$HOME/opt/radare2"
  ;;
esac
exit 0
EOF
cat >"$SB/bin/sha256sum" <<'EOF'
#!/bin/bash
# Fixture seam (see header): `-c` verification passes; every other
# invocation delegates to the real sha256sum.
if [ "${1:-}" = "-c" ]; then
  cat >/dev/null 2>&1 || true
  exit 0
fi
exec /usr/bin/sha256sum "$@"
EOF
chmod +x "$SB/bin"/*

# --- Fixture install trees (the stub tools print the pinned versions). ---
JDK_SRC="$SB/src/jdk-$TEMURIN_VERSION"
GHIDRA_SRC="$SB/src/ghidra_${GHIDRA_VERSION}_PUBLIC"
GHIDRA_BAD_SRC="$SB/src-bad/ghidra_${GHIDRA_VERSION}_PUBLIC"
R2_TREE="$SB/src/radare2-tree"
mkdir -p "$JDK_SRC/bin" "$JDK_SRC/lib/security" \
  "$GHIDRA_SRC/support" "$GHIDRA_BAD_SRC/support" \
  "$R2_TREE/bin" "$R2_TREE/lib" \
  "$R2_TREE/share/radare2/$R2_VERSION/fcnsign" \
  "$R2_TREE/share/radare2/$R2_VERSION/syscall"
cat >"$JDK_SRC/bin/java" <<EOF
#!/bin/bash
echo 'openjdk version "$TEMURIN_SHORT" 2025-10-21 LTS' >&2
echo 'OpenJDK Runtime Environment Temurin-$TEMURIN_VERSION (build $TEMURIN_SHORT+1-LTS)' >&2
exit 0
EOF
printf '#!/bin/bash\nexit 0\n' >"$JDK_SRC/bin/javac"
printf 'fixture trust store\n' >"$JDK_SRC/lib/security/cacerts"
# The analyzeHeadless stub mirrors the real tool's no-argument shape:
# it prints the Headless Analyzer usage text and exits 1.
cat >"$GHIDRA_SRC/support/analyzeHeadless" <<'EOF'
#!/bin/bash
echo 'Headless Analyzer Usage: analyzeHeadless <project_location> <project_name> [-import <directory|file>+] [options]'
exit 1
EOF
# The bad Ghidra stub passes the completeness probe (file present and
# executable, launch.sh present) but prints no usage text, so only
# verify_all can catch it — that divergence drives cases (d) and (e).
cat >"$GHIDRA_BAD_SRC/support/analyzeHeadless" <<'EOF'
#!/bin/bash
echo 'stub headless tool: no usage text here'
exit 1
EOF
printf '# fixture launch script\n' >"$GHIDRA_SRC/support/launch.sh"
printf '# fixture launch script\n' >"$GHIDRA_BAD_SRC/support/launch.sh"
# The fixture r2 exits 1 unless LD_LIBRARY_PATH contains the install
# lib dir — mirroring the real tools' libr_util.so failure.
cat >"$R2_TREE/bin/r2" <<EOF
#!/bin/bash
case ":\${LD_LIBRARY_PATH:-}:" in
*":\$HOME/opt/radare2/lib:"*) ;;
*) exit 1 ;;
esac
echo 'radare2 $R2_VERSION +1 abi:174 @ linux-x86_64'
EOF
cat >"$R2_TREE/bin/rabin2" <<EOF
#!/bin/bash
if [ "\${1:-}" = "-v" ]; then
  echo 'rabin2 $R2_VERSION +1 abi:174 @ linux-x86_64'
  exit 0
fi
if [ "\${1:-}" = "-I" ]; then
  printf 'arch     ELF64 x86_64\nbits     64\nclass    ELF64\n'
  exit 0
fi
exit 0
EOF
printf '#!/bin/bash\nexit 0\n' >"$R2_TREE/bin/radiff2"
printf '#!/bin/bash\nexit 0\n' >"$R2_TREE/bin/r2sdb"
printf 'fixture libr_util\n' >"$R2_TREE/lib/libr_util.so"
printf 'fixture fcnsign data\n' >"$R2_TREE/share/radare2/$R2_VERSION/fcnsign/fixture.sdb"
printf 'fixture syscall data\n' >"$R2_TREE/share/radare2/$R2_VERSION/syscall/fixture.sdb"
chmod +x "$JDK_SRC/bin/java" "$JDK_SRC/bin/javac" \
  "$GHIDRA_SRC/support/analyzeHeadless" "$GHIDRA_BAD_SRC/support/analyzeHeadless" \
  "$R2_TREE/bin/r2" "$R2_TREE/bin/rabin2" "$R2_TREE/bin/radiff2" "$R2_TREE/bin/r2sdb"

# --- Fixture archives, served by the stub curl. ---
SERVE_DIR="$SB/serve"
SERVE_BAD_DIR="$SB/serve-bad"
mkdir -p "$SERVE_DIR" "$SERVE_BAD_DIR"
# The tarball records root:root ownership explicitly: this suite runs
# as uid 0 on an idmapped home volume whose files read back as
# 0:65534, and tar-as-root (--same-owner by default) cannot chown to
# gid 65534 there, which would fail the extraction the harness exists
# to exercise.
tar --owner=0 --group=0 --numeric-owner -czf "$SERVE_DIR/$TEMURIN_TARBALL" -C "$SB/src" "jdk-$TEMURIN_VERSION"
(cd "$SB/src" && zip -qr "$SERVE_DIR/$GHIDRA_ZIP" "ghidra_${GHIDRA_VERSION}_PUBLIC")
cp "$SERVE_DIR/$TEMURIN_TARBALL" "$SERVE_BAD_DIR/$TEMURIN_TARBALL"
(cd "$SB/src-bad" && zip -qr "$SERVE_BAD_DIR/$GHIDRA_ZIP" "ghidra_${GHIDRA_VERSION}_PUBLIC")

printf 'MemTotal:        8000000 kB\nMemAvailable:    1048576 kB\n' >"$SB/meminfo-good"

# --- Runner: absolute-path launch, fixture HOME, stub PATH. ---
FH=""
OUT=""
RC=0
new_fixture() {
  FH="$SB/case-$1/home"
  mkdir -p "$FH"
}
run_installer() { # run_installer <serve-dir> [script args...]
  local serve_dir="$1"
  shift
  OUT="$FH/out.log"
  env HOME="$FH" PATH="$SB/bin:$PATH" \
    INSTALL_RE_MEMINFO_FILE="$SB/meminfo-good" \
    STUB_SERVE_DIR="$serve_dir" STUB_R2_HEAD="$R2_COMMIT" STUB_R2_TREE="$R2_TREE" \
    /bin/bash "$SCRIPT" "$@" >"$OUT" 2>&1
  RC=$?
}
stub_calls() { grep -c "^$1 " "$FH/.stub-calls.log" 2>/dev/null || true; }

# ================= Cases =================

note "case (a): --dry-run on an empty fixture HOME prints install plans, writes nothing"
new_fixture a
run_installer "$SERVE_DIR" --dry-run
[ "$RC" -eq 0 ] && ok "(a) exit 0" || fail "(a) exit 0 (got $RC)"
for comp in temurin ghidra radare2; do
  check "(a) plan line: $comp install" grep -qF "INSTALL-RE: plan $comp: install" "$OUT"
done
check "(a) no opt/ created" test ! -e "$FH/opt"
check "(a) no .bashrc created" test ! -e "$FH/.bashrc"
check "(a) no lock taken" test ! -e "$FH/.install-re-runtime.lock"

note "case (b): --dry-run with probe-passing stubs prints already installed, writes nothing"
new_fixture b
mkdir -p "$FH/opt"
cp -r "$JDK_SRC" "$FH/opt/"
cp -r "$GHIDRA_SRC" "$FH/opt/"
cp -r "$R2_TREE" "$FH/opt/radare2"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
BASHRC_SHA_BEFORE="$(file_sha "$FH/.bashrc")"
run_installer "$SERVE_DIR" --dry-run
[ "$RC" -eq 0 ] && ok "(b) exit 0" || fail "(b) exit 0 (got $RC)"
for comp in temurin ghidra radare2; do
  check "(b) plan line: $comp already installed" grep -qF "INSTALL-RE: plan $comp: already installed" "$OUT"
done
check "(b) .bashrc byte-identical" test "$(file_sha "$FH/.bashrc")" = "$BASHRC_SHA_BEFORE"
check "(b) no env backup written" test ! -e "$FH/.bashrc.install-re-runtime.bak"
check "(b) no .profile created" test ! -e "$FH/.profile"
check "(b) no lock taken" test ! -e "$FH/.install-re-runtime.lock"
check "(b) nothing downloaded" test ! -e "$FH/.stub-calls.log"

note "case (c): full stubbed run — verify_all's login-shell check runs via the real /bin/bash -lc"
new_fixture c
run_installer "$SERVE_DIR"
[ "$RC" -eq 0 ] && ok "(c) exit 0" || fail "(c) exit 0 (got $RC)"
for line in "INSTALL-RE: temurin ok" "INSTALL-RE: ghidra ok" "INSTALL-RE: radare2 ok" "INSTALL-RE: env ok" "INSTALL-RE: verify ok"; do
  check "(c) stage line: $line" grep -qxF "$line" "$OUT"
done
check "(c) verify ok is the last line" test "$(tail -1 "$OUT")" = "INSTALL-RE: verify ok"
check "(c) temurin tarball downloaded" test "$(stub_calls curl)" -ge 2
check "(c) radare2 cloned via stub git" grep -qF "git clone" "$FH/.stub-calls.log"
check "(c) radare2 built via stub make install" grep -qF "make install" "$FH/.stub-calls.log"
check "(c) env block written" grep -qxF "# >>> re-runtime >>>" "$FH/.bashrc"
check "(c) .profile created" test -f "$FH/.profile"
# Independent proof, outside the script: the real login shell, with a
# scrubbed environment, resolves the bench tools from the fixture
# .profile/.bashrc wiring alone.
LOGIN_PATHS="$(env -i HOME="$FH" /bin/bash -lc 'command -v java; command -v analyzeHeadless; command -v r2' 2>/dev/null)"
check "(c) login shell resolves java" grep -qxF "$FH/opt/jdk-$TEMURIN_VERSION/bin/java" <<<"$LOGIN_PATHS"
check "(c) login shell resolves analyzeHeadless" grep -qxF "$FH/opt/ghidra_${GHIDRA_VERSION}_PUBLIC/support/analyzeHeadless" <<<"$LOGIN_PATHS"
check "(c) login shell resolves r2" grep -qxF "$FH/opt/radare2/bin/r2" <<<"$LOGIN_PATHS"

note "case (d): skipped-but-broken Ghidra is rebuilt once by the verify cycle"
new_fixture d
mkdir -p "$FH/opt"
cp -r "$JDK_SRC" "$FH/opt/"
cp -r "$GHIDRA_BAD_SRC" "$FH/opt/"
cp -r "$R2_TREE" "$FH/opt/radare2"
run_installer "$SERVE_DIR"
[ "$RC" -eq 0 ] && ok "(d) exit 0" || fail "(d) exit 0 (got $RC)"
check "(d) first verify failed on ghidra" grep -qF "INSTALL-RE: verify FAIL:" "$OUT"
check "(d) ghidra reinstalled fresh (not skipped)" grep -qxF "INSTALL-RE: ghidra ok" "$OUT"
check "(d) final verify ok" test "$(tail -1 "$OUT")" = "INSTALL-RE: verify ok"
check "(d) rebuilt analyzeHeadless prints usage" grep -qF "Headless Analyzer" "$FH/opt/ghidra_${GHIDRA_VERSION}_PUBLIC/support/analyzeHeadless"

note "case (e): fresh-installed but verify-broken Ghidra exits 1 with no rebuild attempt"
new_fixture e
mkdir -p "$FH/opt"
cp -r "$JDK_SRC" "$FH/opt/"
cp -r "$R2_TREE" "$FH/opt/radare2"
run_installer "$SERVE_BAD_DIR"
[ "$RC" -eq 1 ] && ok "(e) exit 1" || fail "(e) exit 1 (got $RC)"
check "(e) verify failure names ghidra" grep -qF "(ghidra)" "$OUT"
check "(e) ghidra downloaded exactly once" test "$(grep -c "curl .*$GHIDRA_ZIP" "$FH/.stub-calls.log" 2>/dev/null || true)" = "1"
check "(e) ghidra ok stage line appears exactly once" test "$(grep -cxF "INSTALL-RE: ghidra ok" "$OUT" || true)" = "1"

note "case (f): stock-skel HOME — full run verifies green through the real login shell"
new_fixture f
cat >"$FH/.bashrc" <<'EOF'
# ~/.bashrc: executed by bash(1) for non-login shells.

# If not running interactively, don't do anything
case $- in
    *i*) ;;
      *) return;;
esac

# user content after the guard
export EDITOR=vim
EOF
cat >"$FH/.profile" <<'EOF'
# ~/.profile: executed by the command interpreter for login shells.
if [ -n "$BASH_VERSION" ]; then
    if [ -f "$HOME/.bashrc" ]; then
        . "$HOME/.bashrc"
    fi
fi
EOF
run_installer "$SERVE_DIR"
[ "$RC" -eq 0 ] && ok "(f) exit 0" || fail "(f) exit 0 (got $RC)"
check "(f) verify ok is the last line" test "$(tail -1 "$OUT")" = "INSTALL-RE: verify ok"
F_MARKER="$(grep -n -xF '# >>> re-runtime >>>' "$FH/.bashrc" | cut -d: -f1)"
F_GUARD="$(grep -n -xF "case \$- in" "$FH/.bashrc" | cut -d: -f1)"
check "(f) env block sits before the noninteractive guard" test "$F_MARKER" -lt "$F_GUARD"
LOGIN_PATHS="$(env -i HOME="$FH" /bin/bash -lc 'command -v java; command -v analyzeHeadless; command -v r2' 2>/dev/null)"
check "(f) login shell resolves java" grep -qxF "$FH/opt/jdk-$TEMURIN_VERSION/bin/java" <<<"$LOGIN_PATHS"
check "(f) login shell resolves analyzeHeadless" grep -qxF "$FH/opt/ghidra_${GHIDRA_VERSION}_PUBLIC/support/analyzeHeadless" <<<"$LOGIN_PATHS"
check "(f) login shell resolves r2" grep -qxF "$FH/opt/radare2/bin/r2" <<<"$LOGIN_PATHS"
F_BASHRC_SHA="$(file_sha "$FH/.bashrc")"
run_installer "$SERVE_DIR"
[ "$RC" -eq 0 ] && ok "(f) second run exit 0" || fail "(f) second run exit 0 (got $RC)"
check "(f) second run leaves .bashrc byte-identical" test "$(file_sha "$FH/.bashrc")" = "$F_BASHRC_SHA"

note "case (g): skel HOME with the block stranded after the guard is healed by relocation"
new_fixture g
mkdir -p "$FH/opt"
cp -r "$JDK_SRC" "$FH/opt/"
cp -r "$GHIDRA_SRC" "$FH/opt/"
cp -r "$R2_TREE" "$FH/opt/radare2"
cat >"$FH/.bashrc" <<'EOF'
# ~/.bashrc: executed by bash(1) for non-login shells.

# If not running interactively, don't do anything
case $- in
    *i*) ;;
      *) return;;
esac

# user content after the guard
export EDITOR=vim
EOF
cat >>"$FH/.bashrc" <<EOF
# >>> re-runtime >>>
# profile: pre-existing
export JAVA_HOME="\$HOME/opt/jdk-$TEMURIN_VERSION"
export GHIDRA_INSTALL_DIR="\$HOME/opt/ghidra_${GHIDRA_VERSION}_PUBLIC"
export PATH="\$JAVA_HOME/bin:\$GHIDRA_INSTALL_DIR/support:\$HOME/opt/radare2/bin:\$PATH"
export LD_LIBRARY_PATH="\$HOME/opt/radare2/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
# <<< re-runtime <<<
EOF
cat >"$FH/.profile" <<'EOF'
# ~/.profile: executed by the command interpreter for login shells.
if [ -n "$BASH_VERSION" ]; then
    if [ -f "$HOME/.bashrc" ]; then
        . "$HOME/.bashrc"
    fi
fi
EOF
run_installer "$SERVE_DIR"
[ "$RC" -eq 0 ] && ok "(g) exit 0" || fail "(g) exit 0 (got $RC)"
check "(g) verify ok is the last line" test "$(tail -1 "$OUT")" = "INSTALL-RE: verify ok"
G_MARKER="$(grep -n -xF '# >>> re-runtime >>>' "$FH/.bashrc" | cut -d: -f1)"
G_GUARD="$(grep -n -xF "case \$- in" "$FH/.bashrc" | cut -d: -f1)"
check "(g) env block relocated before the guard" test "$G_MARKER" -lt "$G_GUARD"
LOGIN_PATHS="$(env -i HOME="$FH" /bin/bash -lc 'command -v java; command -v analyzeHeadless; command -v r2' 2>/dev/null)"
check "(g) login shell resolves java" grep -qxF "$FH/opt/jdk-$TEMURIN_VERSION/bin/java" <<<"$LOGIN_PATHS"
check "(g) login shell resolves analyzeHeadless" grep -qxF "$FH/opt/ghidra_${GHIDRA_VERSION}_PUBLIC/support/analyzeHeadless" <<<"$LOGIN_PATHS"
check "(g) login shell resolves r2" grep -qxF "$FH/opt/radare2/bin/r2" <<<"$LOGIN_PATHS"
G_BASHRC_SHA="$(file_sha "$FH/.bashrc")"
run_installer "$SERVE_DIR"
[ "$RC" -eq 0 ] && ok "(g) second run exit 0" || fail "(g) second run exit 0 (got $RC)"
check "(g) second run leaves .bashrc byte-identical" test "$(file_sha "$FH/.bashrc")" = "$G_BASHRC_SHA"

note "case (h): a dirty staged radare2 clone is restored to the pinned tree before building"
new_fixture h
mkdir -p "$FH/opt/dist/radare2-src"
printf '#!/bin/bash\nexit 0\n' >"$FH/opt/dist/radare2-src/configure"
chmod +x "$FH/opt/dist/radare2-src/configure"
: >"$FH/opt/dist/radare2-src/.stub-git-ok"
: >"$FH/opt/dist/radare2-src/.stub-dirty-tracked"
: >"$FH/opt/dist/radare2-src/.stub-dirty-untracked"
run_installer "$SERVE_DIR"
check "(h) exit 0" test "$RC" -eq 0
check "(h) radare2 ok line" grep -qxF "INSTALL-RE: radare2 ok" "$OUT"
check "(h) verify ok is the last line" test "$(tail -1 "$OUT")" = "INSTALL-RE: verify ok"
check "(h) dirty-clone notice printed" grep -qF "INSTALL-RE: radare2 note: staged clone had local changes" "$OUT"
check "(h) working tree status checked" grep -qF "status --porcelain" "$FH/.stub-calls.log"
check "(h) tracked changes force-restored" grep -qF "checkout -f $R2_VERSION" "$FH/.stub-calls.log"
check "(h) untracked files cleaned" grep -qF "clean -fd" "$FH/.stub-calls.log"
H_STATUS_LN="$(grep -nF "status --porcelain" "$FH/.stub-calls.log" | head -1 | cut -d: -f1)"
H_MAKE_LN="$(grep -nF "make -j2" "$FH/.stub-calls.log" | head -1 | cut -d: -f1)"
check "(h) status check precedes the build" test "$H_STATUS_LN" -lt "$H_MAKE_LN"
check "(h) build saw a clean tree" grep -qF "built-dirty=0" "$FH/.stub-calls.log"
check "(h) build never saw a dirty tree" test -z "$(grep -F "built-dirty=1" "$FH/.stub-calls.log")"
check "(h) tracked dirt removed from the clone" test ! -e "$FH/opt/dist/radare2-src/.stub-dirty-tracked"
check "(h) untracked dirt removed from the clone" test ! -e "$FH/opt/dist/radare2-src/.stub-dirty-untracked"

note "case (i): an unrestorable dirty staged radare2 clone fails the run at radare2, naming the clone"
new_fixture i
mkdir -p "$FH/opt/dist/radare2-src"
printf '#!/bin/bash\nexit 0\n' >"$FH/opt/dist/radare2-src/configure"
chmod +x "$FH/opt/dist/radare2-src/configure"
: >"$FH/opt/dist/radare2-src/.stub-git-ok"
: >"$FH/opt/dist/radare2-src/.stub-dirty-tracked"
: >"$FH/opt/dist/radare2-src/.stub-dirty-untracked"
: >"$FH/opt/dist/radare2-src/.stub-unrestorable"
run_installer "$SERVE_DIR"
check "(i) exit 1" test "$RC" -eq 1
check "(i) temurin ok before radare2" grep -qxF "INSTALL-RE: temurin ok" "$OUT"
check "(i) ghidra ok before radare2" grep -qxF "INSTALL-RE: ghidra ok" "$OUT"
check "(i) dirty-clone notice printed" grep -qF "INSTALL-RE: radare2 note: staged clone had local changes" "$OUT"
check "(i) restore attempted via forced checkout" grep -qF "checkout -f $R2_VERSION" "$FH/.stub-calls.log"
check "(i) restore attempted via clean" grep -qF "clean -fd" "$FH/.stub-calls.log"
check "(i) radare2 FAIL names the staged clone" grep -qxF "INSTALL-RE: radare2 FAIL: staged clone $FH/opt/dist/radare2-src could not be restored to the pinned state" "$OUT"
check "(i) no radare2 ok line" test -z "$(grep -F "INSTALL-RE: radare2 ok" "$OUT" || true)"
check "(i) no verify ok line" test -z "$(grep -F "INSTALL-RE: verify ok" "$OUT" || true)"
check "(i) no make invocation for radare2" test -z "$(grep -E '^make ' "$FH/.stub-calls.log" || true)"
check "(i) no radare2 install tree built" test ! -e "$FH/opt/radare2"
check "(i) tracked dirt still in the clone" test -e "$FH/opt/dist/radare2-src/.stub-dirty-tracked"
check "(i) untracked dirt still in the clone" test -e "$FH/opt/dist/radare2-src/.stub-dirty-untracked"

note "case (j): a staged radare2 clone predating the pinned tag is healed by fetching the tag"
new_fixture j
mkdir -p "$FH/opt/dist/radare2-src"
printf '#!/bin/bash\nexit 0\n' >"$FH/opt/dist/radare2-src/configure"
chmod +x "$FH/opt/dist/radare2-src/configure"
: >"$FH/opt/dist/radare2-src/.stub-git-ok"
: >"$FH/opt/dist/radare2-src/.stub-tag-absent"
run_installer "$SERVE_DIR"
check "(j) exit 0" test "$RC" -eq 0
check "(j) radare2 ok line" grep -qxF "INSTALL-RE: radare2 ok" "$OUT"
check "(j) verify ok is the last line" test "$(tail -1 "$OUT")" = "INSTALL-RE: verify ok"
check "(j) missing tag fetched" grep -qF "fetch origin tag $R2_VERSION" "$FH/.stub-calls.log"
check "(j) clone reused, not re-cloned" test -z "$(grep -F "git clone" "$FH/.stub-calls.log" || true)"
J_FETCH_LN="$(grep -nF "fetch origin tag $R2_VERSION" "$FH/.stub-calls.log" | head -1 | cut -d: -f1)"
J_CHECKOUT_LN="$(grep -nF "checkout $R2_VERSION" "$FH/.stub-calls.log" | head -1 | cut -d: -f1)"
check "(j) fetch precedes the checkout" test "$J_FETCH_LN" -lt "$J_CHECKOUT_LN"
check "(j) tag present in the clone afterwards" test ! -e "$FH/opt/dist/radare2-src/.stub-tag-absent"

echo
if [ "$FAILURES" -eq 0 ]; then
  echo "test_install_re_runtime: ALL PASS (sandbox $SB)"
  rm -rf "$SB"
  exit 0
fi
echo "test_install_re_runtime: $FAILURES failure(s) (sandbox kept at $SB)"
exit 1
