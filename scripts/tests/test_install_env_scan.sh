#!/usr/bin/env bash
# test_install_env_scan.sh — fixture-HOME tests for the env-scan parser in
# scripts/install-re-runtime.sh (issues #118-#123 from the PR #112 census).
#
# Each case sources the installer with its trailing CLI dispatch removed, so
# install_env_block / ensure_profile run in isolation against a fixture HOME.
# The component is run twice per fixture where the issue calls for a
# fixed-point check. The stat stub supplies GNU `stat -L -c %a` semantics on
# macOS so the same harness runs on both platforms.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT/scripts/install-re-runtime.sh"
SB="$(mktemp -d "$HOME/.test-install-env-scan.XXXXXX")"
LIB="$SB/lib.sh"
FAILURES=0
CHECKS=0

note() { echo "# $*"; }
ok() {
  CHECKS=$((CHECKS + 1))
  echo "ok - $*"
}
fail() {
  echo "FAIL - $*"
  FAILURES=$((FAILURES + 1))
}
check() { # check <description> <command...>
  local desc="$1"
  shift
  if "$@" >/dev/null 2>&1; then ok "$desc"; else fail "$desc"; fi
}
check_out() { # check_out <description> <pattern> <file>
  local desc="$1" pattern="$2" file="$3"
  if grep -qF "$pattern" "$file" >/dev/null 2>&1; then
    ok "$desc"
  else
    fail "$desc"
  fi
}
check_no_out() {
  local desc="$1" pattern="$2" file="$3"
  if grep -qF "$pattern" "$file" >/dev/null 2>&1; then
    fail "$desc"
  else
    ok "$desc"
  fi
}
file_sha() { shasum -a 256 "$1" 2>/dev/null | awk '{print $1}' || sha256sum "$1" | awk '{print $1}'; }

# A functions-only copy: the last `case "${1:-}" in` is the CLI dispatch.
DISPATCH_LINE="$(grep -n '^case "\${1:-}" in' "$SCRIPT" | tail -1 | cut -d: -f1)"
head -n $((DISPATCH_LINE - 1)) "$SCRIPT" >"$LIB"

mkdir -p "$SB/bin"
cat >"$SB/bin/stat" <<'EOF'
#!/bin/bash
if [ "$1" = "-L" ] && [ "$2" = "-c" ] && [ "$3" = "%a" ]; then
  /usr/bin/stat -c %a "$4" 2>/dev/null || /usr/bin/stat -f %Lp "$4"
else
  /usr/bin/stat "$@"
fi
EOF
chmod +x "$SB/bin/stat"

FH=""
OUT=""
RC=0
new_home() { # new_home <case-name>
  FH="$SB/case-$1/home"
  mkdir -p "$FH"
  OUT="$SB/case-$1/out"
}
run_env() { # run_env <function-name>; RUN_PATH_PREFIX / RUN_UMASK optionally prepend a PATH dir / set a umask
  (
    HOME="$FH"
    PATH="${RUN_PATH_PREFIX:+$RUN_PATH_PREFIX:}$SB/bin:$PATH"
    export HOME PATH
    [ -z "${RUN_UMASK:-}" ] || umask "$RUN_UMASK"
    # shellcheck disable=SC1090 # the fixture library is generated above
    source "$LIB"
    set +eu
    "$1"
  ) >"$OUT" 2>&1
  RC=$?
}
marker_count() { grep -cxF "# $1 re-runtime $1" "$FH/.bashrc" 2>/dev/null || true; }
line_of() { grep -nF "$1" "$FH/.bashrc" | head -1 | cut -d: -f1; }
last_line_of() { grep -nF "$1" "$FH/.bashrc" | tail -1 | cut -d: -f1; }

TEMURIN_VERSION="$(grep '^TEMURIN_VERSION=' "$SCRIPT" | head -1 | cut -d'"' -f2)"

# ================= #118: heredoc-aware splitter =================

note "#118a: exact marker pair inside a heredoc body is data, not the block"
new_home 118a
cat >"$FH/.bashrc" <<'EOF'
cat >/dev/null <<'DOC'
# >>> re-runtime >>>
export SENTINEL_BODY_LINE=1
# <<< re-runtime <<<
DOC
export AFTER=1
EOF
run_env install_env_block
check "118a rc 0" test "$RC" -eq 0
check "118a heredoc body line kept" grep -qxF 'export SENTINEL_BODY_LINE=1' "$FH/.bashrc"
check "118a following user export kept" grep -qxF 'export AFTER=1' "$FH/.bashrc"
# The body markers are data and must survive; only the new block is
# composed, so the file holds the original pair plus one canonical pair.
check "118a body markers kept plus one new block" test "$(marker_count '>>>')" -eq 2 -a "$(marker_count '<<<')" -eq 2
SENTINEL_LINE="$(line_of 'export SENTINEL_BODY_LINE=1')"
FAKE_MARKER_LINE="$(line_of '# >>> re-runtime >>>')"
check "118a body line still inside its heredoc pair" test "$SENTINEL_LINE" -gt "$FAKE_MARKER_LINE"
BLOCK_LINE="$(last_line_of '# >>> re-runtime >>>')"
DOC_LINE="$(line_of 'DOC')"
check "118a block appended after heredoc terminator" test "$BLOCK_LINE" -gt "$DOC_LINE"
BODY_SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "118a second run rc 0" test "$RC" -eq 0
check "118a fixed point" test "$(file_sha "$FH/.bashrc")" = "$BODY_SHA"

note "#118b: lone start marker in a heredoc body must not tear the file"
new_home 118b
cat >"$FH/.bashrc" <<'EOF'
cat >/dev/null <<'DOC'
# >>> re-runtime >>>
export FROM_BODY=1
DOC
export AFTER=1
EOF
run_env install_env_block
check "118b rc 0" test "$RC" -eq 0
check "118b heredoc terminator kept" grep -qxF 'DOC' "$FH/.bashrc"
check "118b following user export kept" grep -qxF 'export AFTER=1' "$FH/.bashrc"
check "118b body content kept" grep -qxF 'export FROM_BODY=1' "$FH/.bashrc"
check "118b body marker kept plus one new block" test "$(marker_count '>>>')" -eq 2
check "118b kept content parses" bash -n "$FH/.bashrc"
BLOCK_LINE="$(last_line_of '# >>> re-runtime >>>')"
DOC_LINE="$(line_of 'DOC')"
check "118b block after heredoc terminator" test "$BLOCK_LINE" -gt "$DOC_LINE"

note "#118c: an export inside a heredoc body is not adoption evidence"
new_home 118c
cat >"$FH/.bashrc" <<'EOF'
cat >/dev/null <<'DOC'
export JAVA_HOME=/somewhere/else
DOC
export AFTER=1
EOF
run_env install_env_block
check "118c rc 0" test "$RC" -eq 0
check_no_out "118c no false adoption SKIP" 'unmarked RE exports present' "$OUT"
check_out "118c env ok" 'INSTALL-RE: env ok' "$OUT"
check "118c block written" test "$(marker_count '>>>')" -eq 1
JAVA_VAL="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
check "118c live export is the pinned one" test "$JAVA_VAL" = "$FH/opt/jdk-$TEMURIN_VERSION"

note "#118d: an orphan end marker is kept as user data"
new_home 118d
printf '# orphan debris\n# <<< re-runtime <<<\nexport AFTER=1\n' >"$FH/.bashrc"
run_env install_env_block
check "118d rc 0" test "$RC" -eq 0
check "118d orphan end marker kept" test "$(marker_count '<<<')" -eq 2
check "118d following user export kept" grep -qxF 'export AFTER=1' "$FH/.bashrc"

# ================= #119: effective guard spellings =================

guard_fixture() { # guard_fixture <case> <guard-text>
  local name="$1" guard="$2" marker after_line val sha
  new_home "$name"
  {
    printf 'export BEFORE_GUARD=1\n'
    printf '%s\n' "$guard"
    printf 'export AFTER=1\n'
  } >"$FH/.bashrc"
  run_env install_env_block
  check "$name rc 0" test "$RC" -eq 0
  check_out "$name env ok" 'INSTALL-RE: env ok' "$OUT"
  check_no_out "$name no adoption SKIP" 'unmarked RE exports present' "$OUT"
  marker="$(line_of '# >>> re-runtime >>>')"
  after_line="$(line_of 'export AFTER=1')"
  check "$name block before the guard" test "$marker" -lt "$after_line"
  val="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
  check "$name block reachable in a noninteractive source" test "$val" = "$FH/opt/jdk-$TEMURIN_VERSION"
  sha="$(file_sha "$FH/.bashrc")"
  run_env install_env_block
  check "$name second run rc 0" test "$RC" -eq 0
  check "$name fixed point" test "$(file_sha "$FH/.bashrc")" = "$sha"
}

note "#119a: stock / Fedora / Arch / PS1 controls still match"
guard_fixture 119a-stock $'case $- in\n  *i*) ;;\n  *) return;;\nesac'
guard_fixture 119a-fedora $'case "$-" in\n  *i*) ;;\n  *) return;;\nesac'
guard_fixture 119a-arch '[[ $- != *i* ]] && return'
guard_fixture 119a-ps1 '[ -z "$PS1" ] && return'

note "#119b: braced and multi-line guard spellings are recognized"
guard_fixture 119b-braced-case $'case ${-} in\n  *i*) ;;\n  *) return;;\nesac'
guard_fixture 119b-if-dollar $'if [[ $- != *i* ]]; then\n  return\nfi'
guard_fixture 119b-if-ps1 $'if [ -z "$PS1" ]; then\n  return\nfi'
guard_fixture 119b-braced-ps1 '[ -z "${PS1:-}" ] && return'
guard_fixture 119b-tab-case $'case\t$- in\n  *i*) ;;\n  *) return;;\nesac'
guard_fixture 119b-ps1-case $'case "$PS1" in\n  *)\n    return;;\nesac'
# The mid-line form needs its own fixture because case needs a body.
new_home 119b-midcase-body
printf 'export BEFORE_GUARD=1\ntrue; case $- in\n  *i*) ;;\n  *) return;;\nesac\nexport AFTER=1\n' >"$FH/.bashrc"
run_env install_env_block
check "119b-midcase-body rc 0" test "$RC" -eq 0
MID_MARKER="$(line_of '# >>> re-runtime >>>')"
MID_AFTER="$(line_of 'export AFTER=1')"
check "119b-midcase-body block before the guard" test "$MID_MARKER" -lt "$MID_AFTER"
MID_VAL="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
check "119b-midcase-body block reachable" test "$MID_VAL" = "$FH/opt/jdk-$TEMURIN_VERSION"

# ================= #120: guards nested in functions/conditionals =================

note "#120a: a guard inside a function body is not the file's guard"
new_home 120a
cat >"$FH/.bashrc" <<'EOF'
ensure_interactive() {
  case $- in
    *i*) ;;
    *) return;;
  esac
}
export EDITOR=vim
EOF
run_env install_env_block
check "120a rc 0" test "$RC" -eq 0
check_out "120a env ok" 'INSTALL-RE: env ok' "$OUT"
FUNC_END="$(line_of '}')"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
check "120a block after the function body" test "$BLOCK_LINE" -gt "$FUNC_END"
check "120a user export kept" grep -qxF 'export EDITOR=vim' "$FH/.bashrc"
JAVA_VAL="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
check "120a block reachable in a noninteractive source" test "$JAVA_VAL" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "120a second run rc 0" test "$RC" -eq 0
check "120a fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

note "#120b: a guard inside a top-level if body is not the file's guard"
new_home 120b
# The outer condition is false in the scrubbed source, so the nested
# guard-shaped lines are inert data for reachability; the point of the
# case is where the scanner puts the block.
cat >"$FH/.bashrc" <<'EOF'
if [ "${AEP_NEVER_SET:-0}" = 1 ]; then
  case $- in
    *i*) ;;
    *) return;;
  esac
fi
export EDITOR=vim
EOF
run_env install_env_block
check "120b rc 0" test "$RC" -eq 0
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
FI_LINE="$(line_of 'fi')"
check "120b block after the conditional body" test "$BLOCK_LINE" -gt "$FI_LINE"
JAVA_VAL="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
check "120b block reachable" test "$JAVA_VAL" = "$FH/opt/jdk-$TEMURIN_VERSION"

# ================= PR #191 F1: closers followed by comments =================

note "PR191-F1: unit-level closer grammar (comment pops, glued # does not)"
closer_pops() { # closer_pops <line> <closer>
  (
    # shellcheck disable=SC1090 # the fixture library is generated above
    source "$LIB"
    set +eu
    ctrl_closer_line "$1" "$2"
  ) >/dev/null 2>&1
}
closer_stuck() { ! closer_pops "$1" "$2"; }
check "F1 bare fi pops" closer_pops 'fi' 'fi'
check "F1 fi; pops" closer_pops 'fi;' 'fi'
check "F1 fi; # comment pops (pre-existing ; rescue)" closer_pops 'fi; # comment' 'fi'
check "F1 fi # comment pops" closer_pops 'fi # comment' 'fi'
check "F1 fi #comment pops (comment starts at #)" closer_pops 'fi #comment' 'fi'
check "F1 fi <tab># comment pops" closer_pops "$(printf 'fi\t# comment')" 'fi'
check "F1 esac # end case pops" closer_pops 'esac # end case' 'esac'
check "F1 } # end func pops" closer_pops '} # end func' '}'
check "F1 fi# comment does not pop (# glued to the word)" closer_stuck 'fi# comment' 'fi'
check "F1 fi extra does not pop" closer_stuck 'fi extra' 'fi'
check "F1 fi # comment does not pop for esac" closer_stuck 'fi # comment' 'esac'

note "PR191-F1a: a conditional closing with 'fi # comment' does not strand the block"
new_home f1a
cat >"$FH/.bashrc" <<'EOF'
if [ -f "$HOME/.optional" ]; then
  . "$HOME/.optional"
fi # optional setup
case $- in
  *i*) ;;
  *) return;;
esac
export AFTER=1
EOF
run_env install_env_block
check "F1a rc 0" test "$RC" -eq 0
check_out "F1a env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
GUARD_LINE="$(line_of 'case $- in')"
check "F1a block before the guard" test "$BLOCK_LINE" -lt "$GUARD_LINE"
JAVA_VAL="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
check "F1a block reachable in a noninteractive source" test "$JAVA_VAL" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "F1a second run rc 0" test "$RC" -eq 0
check "F1a fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

note "PR191-F1b: a function closing with '} # comment' does not strand the block"
new_home f1b
cat >"$FH/.bashrc" <<'EOF'
myhelper() {
  export INSIDE=1
} # end helper
case $- in
  *i*) ;;
  *) return;;
esac
export AFTER=1
EOF
run_env install_env_block
check "F1b rc 0" test "$RC" -eq 0
check_out "F1b env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
GUARD_LINE="$(line_of 'case $- in')"
check "F1b block before the guard" test "$BLOCK_LINE" -lt "$GUARD_LINE"
JAVA_VAL="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
check "F1b block reachable in a noninteractive source" test "$JAVA_VAL" = "$FH/opt/jdk-$TEMURIN_VERSION"

# ================= PR #191 R2-F1: elif is not an if opener =================

note "PR191-R2F1: unit-level opener grammar (elif/xif do not open, plain if does)"
opener_eq() { # opener_eq <line> <expected-output-or-empty>
  local got
  got="$(
    (
      # shellcheck disable=SC1090 # the fixture library is generated above
      source "$LIB"
      set +eu
      ctrl_opener_closer "$1" || true
    ) 2>/dev/null
  )"
  test "$got" = "$2"
}
check "R2F1 plain if opens fi" opener_eq 'if [ -f "$HOME/.optional" ]; then' 'fi'
check "R2F1 elif does not open" opener_eq 'elif [ -f "$HOME/.other" ]; then' ''
check "R2F1 xif does not open" opener_eq 'xif [ a ]; then' ''
check "R2F1 function form opens }" opener_eq 'foo() {' '}'
check "R2F1 function keyword form opens }" opener_eq 'function foo {' '}'
check "R2F1 case opens esac" opener_eq 'case $- in' 'esac'
check "R2F1 while does not open (no loop openers, unchanged)" opener_eq 'while true; do' ''
check "R2F1 residual#1 discharged by R3T8: if with trailing comment opens" opener_eq 'if [ -f "$HOME/.optional" ]; then # comment' 'fi'
check "R2F1 residual#1 discharged by R3T8: function with trailing comment opens" opener_eq 'foo() { # comment' '}'
check "R2F1 residual#1 discharged by R3T8: case with trailing comment opens" opener_eq 'case $- in # comment' 'esac'

note "PR191-R2F1a: an if/elif/fi conditional before the stock guard does not strand the block"
new_home r2f1a
cat >"$FH/.bashrc" <<'EOF'
if [ -f "$HOME/.optional" ]; then
  . "$HOME/.optional"
elif [ -f "$HOME/.other" ]; then
  . "$HOME/.other"
fi
case $- in
  *i*) ;;
  *) return;;
esac
export AFTER=1
EOF
run_env install_env_block
check "R2F1a rc 0" test "$RC" -eq 0
check_out "R2F1a env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
GUARD_LINE="$(line_of 'case $- in')"
check "R2F1a block before the guard" test "$BLOCK_LINE" -lt "$GUARD_LINE"
JAVA_VAL="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
check "R2F1a block reachable in a noninteractive source" test "$JAVA_VAL" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "R2F1a second run rc 0" test "$RC" -eq 0
check "R2F1a fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

# ================= PR #191 R3-T5: closers after preceding commands =================

note "PR191-R3T5: unit-level closer grammar (a closer after a command separator pops)"
check "R3T5 :; } pops" closer_pops ':; }' '}'
check "R3T5 command; fi pops" closer_pops 'true; fi' 'fi'
check "R3T5 command; esac pops" closer_pops 'true; esac' 'esac'
check "R3T5 command; done pops" closer_pops 'true; done' 'done'

note "PR191-R3T5a: a function ending ':; }' does not strand the block"
new_home r3t5a
cat >"$FH/.bashrc" <<'EOF'
myhelper() {
:; }
case $- in
  *i*) ;;
  *) return;;
esac
export AFTER=1
EOF
run_env install_env_block
check "R3T5a rc 0" test "$RC" -eq 0
check_out "R3T5a env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
GUARD_LINE="$(line_of 'case $- in')"
check "R3T5a block before the guard" test "$BLOCK_LINE" -lt "$GUARD_LINE"
JAVA_VAL="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
check "R3T5a block reachable in a noninteractive source" test "$JAVA_VAL" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "R3T5a second run rc 0" test "$RC" -eq 0
check "R3T5a fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

# ================= PR #191 R3-T8: openers inside comments =================

note "PR191-R3T8: unit-level opener grammar (comment text opens nothing)"
check "R3T8 colon comment case does not open" opener_eq ': # case foo in' ''
check "R3T8 trailing comment case does not open" opener_eq 'echo hi # case foo in' ''
check "R3T8 assignment comment case does not open" opener_eq 'x=1 # case $- in' ''
check "R3T8 glued hash is not a comment and case still opens" opener_eq 'case $# in' 'esac'

note "PR191-R3T8a: a comment mentioning 'case ... in' does not strand the block"
new_home r3t8a
cat >"$FH/.bashrc" <<'EOF'
: # case foo in
case $- in
  *i*) ;;
  *) return;;
esac
export AFTER=1
EOF
run_env install_env_block
check "R3T8a rc 0" test "$RC" -eq 0
check_out "R3T8a env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
GUARD_LINE="$(line_of 'case $- in')"
check "R3T8a block before the guard" test "$BLOCK_LINE" -lt "$GUARD_LINE"
JAVA_VAL="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
check "R3T8a block reachable in a noninteractive source" test "$JAVA_VAL" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "R3T8a second run rc 0" test "$RC" -eq 0
check "R3T8a fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

# ================= PR #191 R4-F1: guard return on the closing line =================

note "PR191-R4F1a: a guard ending '*) return;; esac' on one line is recognized"
new_home r4f1a
cat >"$FH/.bashrc" <<'EOF'
case $- in
  *i*) ;;
  *) return;; esac
export AFTER=1
EOF
run_env install_env_block
check "R4F1a rc 0" test "$RC" -eq 0
check_out "R4F1a env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
GUARD_LINE="$(line_of 'case $- in')"
check "R4F1a block before the guard" test "$BLOCK_LINE" -lt "$GUARD_LINE"
JAVA_VAL="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
check "R4F1a block reachable in a noninteractive source" test "$JAVA_VAL" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "R4F1a second run rc 0" test "$RC" -eq 0
check "R4F1a fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

note "PR191-R4F1b: an if-guard whose return shares the 'fi' closing line is recognized"
new_home r4f1b
cat >"$FH/.bashrc" <<'EOF'
if [ -z "$PS1" ]; then
  return; fi
export AFTER=1
EOF
run_env install_env_block
check "R4F1b rc 0" test "$RC" -eq 0
check_out "R4F1b env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
GUARD_LINE="$(line_of 'if [ -z "$PS1" ]')"
check "R4F1b block before the guard" test "$BLOCK_LINE" -lt "$GUARD_LINE"
JAVA_VAL="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
check "R4F1b block reachable in a noninteractive source" test "$JAVA_VAL" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "R4F1b second run rc 0" test "$RC" -eq 0
check "R4F1b fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

# ================= #121: formatted marker recognition =================

note "#121a: indented markers are recognized and normalized"
new_home 121a
cat >"$FH/.bashrc" <<EOF
# user bashrc
  # >>> re-runtime >>>
  # profile: pre-existing
  export JAVA_HOME="\$HOME/opt/jdk-$TEMURIN_VERSION"
  export GHIDRA_INSTALL_DIR="\$HOME/opt/ghidra_12.1.4_PUBLIC"
  export PATH="\$JAVA_HOME/bin:\$GHIDRA_INSTALL_DIR/support:\$HOME/opt/radare2/bin:\$PATH"
  # <<< re-runtime <<<
export EDITOR=vim
EOF
run_env install_env_block
check "121a rc 0" test "$RC" -eq 0
check_no_out "121a no misleading adoption SKIP" 'unmarked RE exports present' "$OUT"
check_out "121a env ok" 'INSTALL-RE: env ok' "$OUT"
check "121a one canonical start marker" test "$(marker_count '>>>')" -eq 1
check "121a one canonical end marker" test "$(marker_count '<<<')" -eq 1
check_no_out "121a no indented markers left" '  # >>> re-runtime >>>' "$FH/.bashrc"
check "121a user export kept" grep -qxF 'export EDITOR=vim' "$FH/.bashrc"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "121a second run rc 0" test "$RC" -eq 0
check "121a fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

note "#121b: CRLF markers are recognized"
new_home 121b
{
  printf '# user bashrc\r\n'
  printf '# >>> re-runtime >>>\r\n'
  printf '# profile: pre-existing\r\n'
  printf 'export JAVA_HOME="$HOME/opt/jdk-%s"\r\n' "$TEMURIN_VERSION"
  printf '# <<< re-runtime <<<\r\n'
  printf 'export EDITOR=vim\r\n'
} >"$FH/.bashrc"
run_env install_env_block
check "121b rc 0" test "$RC" -eq 0
check_no_out "121b no misleading adoption SKIP" 'unmarked RE exports present' "$OUT"
check_out "121b env ok" 'INSTALL-RE: env ok' "$OUT"
check "121b one canonical start marker" test "$(marker_count '>>>')" -eq 1
check "121b one canonical end marker" test "$(marker_count '<<<')" -eq 1
check_no_out "121b no CR on the canonical marker" $'# >>> re-runtime >>>\r' "$FH/.bashrc"
check "121b kept content parses" bash -n "$FH/.bashrc"

note "#121c: trailing-space markers are recognized"
new_home 121c
cat >"$FH/.bashrc" <<'EOF'
# user bashrc
# >>> re-runtime >>>   
# profile: pre-existing
export JAVA_HOME=/hand/installed
# <<< re-runtime <<<	
export EDITOR=vim
EOF
run_env install_env_block
check "121c rc 0" test "$RC" -eq 0
check_no_out "121c no misleading adoption SKIP" 'unmarked RE exports present' "$OUT"
check "121c one canonical start marker" test "$(marker_count '>>>')" -eq 1
check "121c one canonical end marker" test "$(marker_count '<<<')" -eq 1

note "#121d: a marker string inside other text stays data"
new_home 121d
cat >"$FH/.bashrc" <<'EOF'
# user bashrc
echo '# >>> re-runtime >>>'
printf '%s\n' '# <<< re-runtime <<<'
export EDITOR=vim
EOF
run_env install_env_block
check "121d rc 0" test "$RC" -eq 0
check "121d composing marker present" test "$(marker_count '>>>')" -eq 1
check "121d marker-like text kept" grep -qxF "echo '# >>> re-runtime >>>'" "$FH/.bashrc"
check "121d second marker-like text kept" grep -qxF "printf '%s\n' '# <<< re-runtime <<<'" "$FH/.bashrc"

# ================= #122: unterminated heredoc is damage =================

note "#122: an unterminated heredoc fails loudly instead of stranding the block"
new_home 122
cat >"$FH/.bashrc" <<'EOF'
cat >/dev/null <<EOF
case $- in
  *) return;;
esac
export AFTER=1
EOF
cp "$FH/.bashrc" "$SB/case-122/orig"
check "122 bash -n alone does not detect it" bash -n "$FH/.bashrc"
run_env install_env_block
check "122 rc non-zero" test "$RC" -ne 0
check_out "122 env FAIL line" 'INSTALL-RE: env FAIL:' "$OUT"
check_out "122 names the bashrc" "$FH/.bashrc" "$OUT"
check_out "122 names the opener line" 'line 1' "$OUT"
check_out "122 names the as-found backup" "$FH/.bashrc.install-re-runtime.bak" "$OUT"
check_no_out "122 no env ok" 'INSTALL-RE: env ok' "$OUT"
check "122 file left untouched" cmp -s "$SB/case-122/orig" "$FH/.bashrc"
check "122 backup holds as-found bytes" cmp -s "$SB/case-122/orig" "$FH/.bashrc.install-re-runtime.bak"
check "122 no block composed" bash -c 'shopt -s nullglob; f=("$1"/.bashrc.install-re-runtime.*); for x in "${f[@]}"; do [ "$x" = "$1/.bashrc.install-re-runtime.bak" ] || exit 1; done' _ "$FH"

# ================= PR #191 R3-T6: multiline arithmetic is not a heredoc =================

note "PR191-R3T6: a multiline arithmetic expansion is not rejected as an unterminated heredoc"
new_home r3t6
cat >"$FH/.bashrc" <<'EOF'
x=$((
  1 << 2
))
export AFTER=1
EOF
check "R3T6 fixture parses" bash -n "$FH/.bashrc"
run_env install_env_block
check "R3T6 rc 0" test "$RC" -eq 0
check_out "R3T6 env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "R3T6 no unterminated-heredoc failure" 'unterminated heredoc' "$OUT"
check "R3T6 arithmetic lines kept" grep -qxF '  1 << 2' "$FH/.bashrc"
check "R3T6 block written" test "$(marker_count '>>>')" -eq 1
JAVA_VAL="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
check "R3T6 block reachable in a noninteractive source" test "$JAVA_VAL" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "R3T6 second run rc 0" test "$RC" -eq 0
check "R3T6 fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

# ================= #123: login profile shadowing =================

note "#123a: a non-sourcing .bash_profile is named instead of failing opaquely"
new_home 123a
printf '# my own login profile\nexport EDITOR=vim\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "123a rc 0" test "$RC" -eq 0
check_out "123a shadowing SKIP line" 'login startup is shadowed by' "$OUT"
check_out "123a names .bash_profile" '.bash_profile' "$OUT"
check_out "123a names the non-sourcing reason" 'does not source ~/.bashrc' "$OUT"
check_no_out "123a no opaque env ok" 'INSTALL-RE: env ok' "$OUT"
check "123a no block composed into an unreachable file" test "$(marker_count '>>>')" -eq 0

note "#123b: a sourcing .bash_profile leaves the normal path intact"
new_home 123b
cat >"$FH/.bash_profile" <<'EOF'
if [ -f "$HOME/.bashrc" ]; then
  . "$HOME/.bashrc"
fi
EOF
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "123b rc 0" test "$RC" -eq 0
check_out "123b env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "123b no shadowing SKIP" 'login startup is shadowed by' "$OUT"
check "123b block written" test "$(marker_count '>>>')" -eq 1

note "#123c: transitive sourcing through another file counts"
new_home 123c
printf '. "$HOME/.bashrc-chain"\n' >"$FH/.bash_profile"
printf '. "$HOME/.bashrc"\n' >"$FH/.bashrc-chain"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "123c rc 0" test "$RC" -eq 0
check_out "123c env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "123c no shadowing SKIP" 'login startup is shadowed by' "$OUT"
check "123c block written" test "$(marker_count '>>>')" -eq 1

note "#123d: .bash_login shadows when .bash_profile is absent"
new_home 123d
printf '# login\nexport EDITOR=vim\n' >"$FH/.bash_login"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "123d rc 0" test "$RC" -eq 0
check_out "123d shadowing SKIP names .bash_login" '.bash_login' "$OUT"
check "123d no block composed" test "$(marker_count '>>>')" -eq 0

note "#123e: .bash_login is ignored when .bash_profile comes first"
new_home 123e
printf '. "$HOME/.bashrc"\n' >"$FH/.bash_profile"
printf '# unused login file\nexport EDITOR=vim\n' >"$FH/.bash_login"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "123e rc 0" test "$RC" -eq 0
check_out "123e env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "123e no shadowing SKIP" 'login startup is shadowed by' "$OUT"

note "#123f: the shadowing SKIP survives a repeat call in the same process"
new_home 123f
printf '# my own login profile\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
(
  HOME="$FH"
  PATH="$SB/bin:$PATH"
  export HOME PATH
  # shellcheck disable=SC1090 # the fixture library is generated above
  source "$LIB"
  set +eu
  install_env_block >"$SB/case-123f/out1" 2>&1
  install_env_block >"$SB/case-123f/out2" 2>&1
)
check_out "123f first call names the shadowing" 'login startup is shadowed by' "$SB/case-123f/out1"
check_out "123f repeat call still names the shadowing" 'login startup is shadowed by' "$SB/case-123f/out2"
check "123f no block composed" test "$(marker_count '>>>')" -eq 0

note "#123g: an &&-conditional sourcing .bash_profile is recognized (PR #191 F2)"
new_home 123g
printf '[ -f ~/.bashrc ] && . ~/.bashrc\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "123g rc 0" test "$RC" -eq 0
check_out "123g env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "123g no shadowing SKIP" 'login startup is shadowed by' "$OUT"
check "123g block written" test "$(marker_count '>>>')" -eq 1

note "#123h: a single-line if sourcing .bash_profile is recognized (PR #191 F2)"
new_home 123h
printf 'if [ -f ~/.bashrc ]; then . ~/.bashrc; fi\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "123h rc 0" test "$RC" -eq 0
check_out "123h env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "123h no shadowing SKIP" 'login startup is shadowed by' "$OUT"
check "123h block written" test "$(marker_count '>>>')" -eq 1

note "#123i: the source-keyword && form is recognized (PR #191 F2)"
new_home 123i
printf '[ -f "$HOME/.bashrc" ] && source "$HOME/.bashrc"\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "123i rc 0" test "$RC" -eq 0
check_out "123i env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "123i no shadowing SKIP" 'login startup is shadowed by' "$OUT"
check "123i block written" test "$(marker_count '>>>')" -eq 1

note "#123j: a commented-out sourcing line still does not count (PR #191 F2)"
new_home 123j
printf '# . ~/.bashrc\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "123j rc 0" test "$RC" -eq 0
check_out "123j shadowing SKIP line" 'login startup is shadowed by' "$OUT"
check "123j no block composed" test "$(marker_count '>>>')" -eq 0

note "#123k: mentioning .bashrc without sourcing it still does not count (PR #191 F2)"
new_home 123k
printf '[ -f ~/.bashrc ] && echo ok\necho ". ~/.bashrc"\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "123k rc 0" test "$RC" -eq 0
check_out "123k shadowing SKIP line" 'login startup is shadowed by' "$OUT"
check "123k no block composed" test "$(marker_count '>>>')" -eq 0

note "#123l: a braced \${HOME} sourcing .bash_profile is recognized (PR #191 R2-F2)"
new_home 123l
printf '. "${HOME}/.bashrc"\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "123l rc 0" test "$RC" -eq 0
check_out "123l env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "123l no shadowing SKIP" 'login startup is shadowed by' "$OUT"
check "123l block written" test "$(marker_count '>>>')" -eq 1

note "#123m: the braced \${HOME} && segment form is recognized (PR #191 R2-F2)"
new_home 123m
printf '[ -f "${HOME}/.bashrc" ] && . "${HOME}/.bashrc"\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "123m rc 0" test "$RC" -eq 0
check_out "123m env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "123m no shadowing SKIP" 'login startup is shadowed by' "$OUT"
check "123m block written" test "$(marker_count '>>>')" -eq 1

note "#123n: the braced \${HOME} single-line if form is recognized (PR #191 R2-F2)"
new_home 123n
printf 'if [ -f "${HOME}/.bashrc" ]; then . "${HOME}/.bashrc"; fi\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "123n rc 0" test "$RC" -eq 0
check_out "123n env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "123n no shadowing SKIP" 'login startup is shadowed by' "$OUT"
check "123n block written" test "$(marker_count '>>>')" -eq 1

note "#123o: a commented-out braced \${HOME} sourcing line still does not count (PR #191 R2-F2)"
new_home 123o
printf '# . "${HOME}/.bashrc"\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "123o rc 0" test "$RC" -eq 0
check_out "123o shadowing SKIP line" 'login startup is shadowed by' "$OUT"
check "123o no block composed" test "$(marker_count '>>>')" -eq 0

note "#123p: a quoted-fragment \${HOME} sourcing .bash_profile is recognized (PR #191 R3-T7)"
new_home 123p
printf '. "$HOME"/.bashrc\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "123p rc 0" test "$RC" -eq 0
check_out "123p env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "123p no shadowing SKIP" 'login startup is shadowed by' "$OUT"
check "123p block written" test "$(marker_count '>>>')" -eq 1

note "PR191-R4F2a: a quoted source path containing a space is followed through the chain"
new_home r4f2a
printf '. "$HOME/login setup"\n' >"$FH/.bash_profile"
printf '. "$HOME/.bashrc"\n' >"$FH/login setup"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "R4F2a rc 0" test "$RC" -eq 0
check_out "R4F2a env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "R4F2a no shadowing SKIP" 'login startup is shadowed by' "$OUT"
check "R4F2a block written" test "$(marker_count '>>>')" -eq 1

note "PR191-R4F2b: a backslash-escaped space in a source path is followed through the chain"
new_home r4f2b
printf '. $HOME/login\\ setup\n' >"$FH/.bash_profile"
printf '. "$HOME/.bashrc"\n' >"$FH/login setup"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "R4F2b rc 0" test "$RC" -eq 0
check_out "R4F2b env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "R4F2b no shadowing SKIP" 'login startup is shadowed by' "$OUT"
check "R4F2b block written" test "$(marker_count '>>>')" -eq 1

note "PR191-R5T1a: a relative source path in a chained file resolves against the working directory (PR #191 R3)"
new_home r5t1a
mkdir -p "$FH/.config/bash"
printf '. "$HOME/.config/bash/login"\n' >"$FH/.bash_profile"
printf '. ./.bashrc\n' >"$FH/.config/bash/login"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "R5T1a rc 0" test "$RC" -eq 0
check_out "R5T1a env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "R5T1a no shadowing SKIP" 'login startup is shadowed by' "$OUT"
check "R5T1a block written" test "$(marker_count '>>>')" -eq 1

note "PR191-R5T1b: a relative source path two chain levels deep still resolves against the working directory"
new_home r5t1b
mkdir -p "$FH/d1/d2" "$FH/d3"
printf '. "$HOME/d1/d2/one"\n' >"$FH/.bash_profile"
printf '. "$HOME/d3/two"\n' >"$FH/d1/d2/one"
printf '. ./.bashrc\n' >"$FH/d3/two"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "R5T1b rc 0" test "$RC" -eq 0
check_out "R5T1b env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "R5T1b no shadowing SKIP" 'login startup is shadowed by' "$OUT"
check "R5T1b block written" test "$(marker_count '>>>')" -eq 1

note "PR191-R5T1c: a chained '../..' source path lands outside HOME under working-directory resolution and does not count"
new_home r5t1c
mkdir -p "$FH/.config/bash"
printf '. "$HOME/.config/bash/login"\n' >"$FH/.bash_profile"
printf '. ../../.bashrc\n' >"$FH/.config/bash/login"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "R5T1c rc 0" test "$RC" -eq 0
check_out "R5T1c shadowing SKIP line" 'login startup is shadowed by' "$OUT"
check "R5T1c no block composed" test "$(marker_count '>>>')" -eq 0

note "PR191-R5N4a: a quoted semicolon inside a source filename is data, not a segment separator (PR #191 R3, census N4)"
new_home r5n4a
printf '. "$HOME/log;in setup"\n' >"$FH/.bash_profile"
printf '. "$HOME/.bashrc"\n' >"$FH/log;in setup"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "R5N4a rc 0" test "$RC" -eq 0
check_out "R5N4a env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "R5N4a no shadowing SKIP" 'login startup is shadowed by' "$OUT"
check "R5N4a block written" test "$(marker_count '>>>')" -eq 1

note "PR191-R5N4b: a quoted && inside a source filename is data, not a segment separator"
new_home r5n4b
printf '. "$HOME/a&&b"\n' >"$FH/.bash_profile"
printf '. "$HOME/.bashrc"\n' >"$FH/a&&b"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "R5N4b rc 0" test "$RC" -eq 0
check_out "R5N4b env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "R5N4b no shadowing SKIP" 'login startup is shadowed by' "$OUT"
check "R5N4b block written" test "$(marker_count '>>>')" -eq 1

note "PR191-R5N4c: a backslash-escaped semicolon in a source filename is data, not a segment separator"
new_home r5n4c
printf '. $HOME/a\\;b\n' >"$FH/.bash_profile"
printf '. "$HOME/.bashrc"\n' >"$FH/a;b"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "R5N4c rc 0" test "$RC" -eq 0
check_out "R5N4c env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "R5N4c no shadowing SKIP" 'login startup is shadowed by' "$OUT"
check "R5N4c block written" test "$(marker_count '>>>')" -eq 1

note "PR191-R5T1d: a slash-less source name in a chained file resolves against the working directory"
new_home r5t1d
mkdir -p "$FH/.config/bash"
printf '. "$HOME/.config/bash/login"\n' >"$FH/.bash_profile"
printf '. setup\n' >"$FH/.config/bash/login"
printf '. "$HOME/.bashrc"\n' >"$FH/setup"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "R5T1d rc 0" test "$RC" -eq 0
check_out "R5T1d env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "R5T1d no shadowing SKIP" 'login startup is shadowed by' "$OUT"
check "R5T1d block written" test "$(marker_count '>>>')" -eq 1

note "PR191-R2F2: unit-level profile_sources_bashrc probes for braced forms"
profile_detected() { # profile_detected <profile-line>
  local pdir="$SB/psb-probe"
  rm -rf "$pdir"
  mkdir -p "$pdir"
  printf '%s\n' "$1" >"$pdir/.bash_profile"
  (
    HOME="$pdir"
    export HOME
    # shellcheck disable=SC1090 # the fixture library is generated above
    source "$LIB"
    set +eu
    profile_sources_bashrc "$pdir/.bash_profile"
  ) >/dev/null 2>&1
}
profile_not_detected() { ! profile_detected "$1"; }
check "R2F2 unquoted braced form detected" profile_detected '. ${HOME}/.bashrc'
check "R2F2 source-keyword braced form detected" profile_detected 'source "${HOME}/.bashrc"'
check "R2F2 braced || chain detected (K7d: || is a segment boundary)" profile_detected '[ -f "${HOME}/.bashrc.missing" ] || . "${HOME}/.bashrc"'
check "R2F2 braced mention without a source command not detected" profile_not_detected 'echo ". \"${HOME}/.bashrc\""'
check "R3T7 quoted HOME fragment detected" profile_detected '. "$HOME"/.bashrc'
check "R3T7 quoted suffix fragment detected" profile_detected '. "$HOME/"'"'"'.bashrc'"'"''
check "R3T7 unquoted HOME plus quoted suffix detected" profile_detected '. $HOME"/.bashrc"'
check "R3T7 braced HOME plus unquoted suffix detected" profile_detected '. "${HOME}/".bashrc'
check "R3T7 tilde plus quoted suffix detected" profile_detected '. ~/".bashrc"'
check "R3T7 single-quoted HOME remains literal and is not detected" profile_not_detected ". '\$HOME'/.bashrc"
check "R5T1 direct ./ source in the profile detected" profile_detected '. ./.bashrc'
check "R5T1 absolute path with a .. component detected" profile_detected '. "$HOME/.config/../.bashrc"'

# ================= PR #191 R6: quoted '#' is not a comment (bridge Finding A) =================

note "PR191-R6A: unit-level opener grammar (a quoted '#' does not cut the line)"
check "R6A mid-line quoted hash, case opens" opener_eq 'echo "step # 1"; case $- in' 'esac'
check "R6A case subject with quoted hash opens" opener_eq 'case "$- # flags" in' 'esac'
check "R6A case subject with single-quoted hash opens" opener_eq "case 'mode # 1' in" 'esac'
check "R6A quoted hash in an if condition, if opens" opener_eq 'if [ "$mode" = "a # b" ]; then' 'fi'
check "R6A real comment after a quoted hash still cuts" opener_eq 'echo "step # 1" # case foo in' ''

note "PR191-R6A1: a quoted '#' before the guard's case opener does not strand the block"
new_home r6a1
cat >"$FH/.bashrc" <<'EOF'
echo "setup # 1" >/dev/null; case $- in
  *i*) ;;
  *) return;;
esac
export AFTER=1
EOF
run_env install_env_block
check "R6A1 rc 0" test "$RC" -eq 0
check_out "R6A1 env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
GUARD_LINE="$(line_of 'case $- in')"
check "R6A1 block before the guard" test "$BLOCK_LINE" -lt "$GUARD_LINE"
JAVA_VAL="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
check "R6A1 block reachable in a noninteractive source" test "$JAVA_VAL" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "R6A1 second run rc 0" test "$RC" -eq 0
check "R6A1 fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

note "PR191-R6A2: a quoted '#' in the guard's case subject does not strand the block"
new_home r6a2
cat >"$FH/.bashrc" <<'EOF'
case "$- # flags" in
  *i*) ;;
  *) return;;
esac
export AFTER=1
EOF
run_env install_env_block
check "R6A2 rc 0" test "$RC" -eq 0
check_out "R6A2 env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
GUARD_LINE="$(line_of 'case "$- # flags" in')"
check "R6A2 block before the guard" test "$BLOCK_LINE" -lt "$GUARD_LINE"
JAVA_VAL="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
check "R6A2 block reachable in a noninteractive source" test "$JAVA_VAL" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "R6A2 second run rc 0" test "$RC" -eq 0
check "R6A2 fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

note "PR191-R6B: unit-level closer grammar (a quoted '#' does not cut the line)"
check "R6B quoted hash before a closer tail pops" closer_pops 'echo "note # 1"; fi' 'fi'
check "R6B single-quoted hash before a closer tail pops" closer_pops "echo 'note # 1'; esac" 'esac'
check "R6B closer inside a real comment after a quoted hash does not pop" closer_stuck 'echo "note # 1" # fi' 'fi'

note "PR191-R6B1: a quoted '#' on the line that closes an if body does not strand the block"
new_home r6b1
cat >"$FH/.bashrc" <<'EOF'
if [ -f "$HOME/.optional" ]; then
  echo "step # 1"; fi
case $- in
  *i*) ;;
  *) return;;
esac
export AFTER=1
EOF
run_env install_env_block
check "R6B1 rc 0" test "$RC" -eq 0
check_out "R6B1 env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
GUARD_LINE="$(line_of 'case $- in')"
check "R6B1 block before the guard" test "$BLOCK_LINE" -lt "$GUARD_LINE"
JAVA_VAL="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
check "R6B1 block reachable in a noninteractive source" test "$JAVA_VAL" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "R6B1 second run rc 0" test "$RC" -eq 0
check "R6B1 fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

# ================= Panel K2: one-line compound inside an outer frame =================
# Adversarial-panel finding K2 (PR #191 follow-up): ctrl_closer_line's
# tail-split popped an OUTER frame for a self-contained one-line
# compound (`if true; then :; fi`) that ctrl_opener_closer never
# opened, desyncing the struct stack so a guard nested inside a false
# conditional read as top-level and the block stranded inside it.

note "PANEL-K2: unit-level closer grammar (a self-contained one-line compound does not pop an outer frame)"
check "K2 one-line if does not pop an outer fi" closer_stuck 'if true; then :; fi' 'fi'
check "K2 one-line case does not pop an outer esac" closer_stuck 'case x in x) :;; esac' 'esac'
check "K2 one-line function does not pop an outer }" closer_stuck 'myhelper() { :; }' '}'
check "K2 one-line function (keyword form) does not pop an outer }" closer_stuck 'function myhelper { :; }' '}'
check "K2 closer after a plain command still pops" closer_pops ':; fi' 'fi'
check "K2 balanced compound plus a further closer still pops" closer_pops 'if true; then :; fi; fi' 'fi'

note "PANEL-K2a: a one-line compound inside a false conditional does not strand the block"
new_home k2a
cat >"$FH/.bashrc" <<'EOF'
if [ -f /etc/some-nonexistent-file ]; then
  if true; then :; fi
  case $- in
    *i*) ;;
    *) return;;
  esac
fi
echo AFTER
EOF
run_env install_env_block
check "K2a rc 0" test "$RC" -eq 0
check_out "K2a env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
OUTER_FI_LINE="$(grep -nxF 'fi' "$FH/.bashrc" | head -1 | cut -d: -f1)"
check "K2a block after the outer conditional" test "$BLOCK_LINE" -gt "$OUTER_FI_LINE"
NI_OUT="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf "JAVA=%s" "${JAVA_HOME:-<unset>}"' 2>/dev/null)"
check "K2a block reachable in a noninteractive source" test "${NI_OUT##*JAVA=}" = "$FH/opt/jdk-$TEMURIN_VERSION"
check "K2a trailing content still executes" test "${NI_OUT#*AFTER}" != "$NI_OUT"
LOGIN_OUT="$(env -i HOME="$FH" /bin/bash -lc 'printf "JAVA=%s" "${JAVA_HOME:-<unset>}"' 2>/dev/null)"
check "K2a block reachable in a login shell" test "${LOGIN_OUT##*JAVA=}" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "K2a second run rc 0" test "$RC" -eq 0
check "K2a fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

# ================= Panel K2 round 2: glued then, quoted separators, quoted openers =================
# Independent review of the K2 fix found three residuals in the new
# head-opens check: bash accepts `;then`/`;fi` with no whitespace (the
# opener shapes required a space before `then`); the re-close segment
# scan split on `;` quote-blindly, so a quoted `;fi;` re-closed the
# same-line if; and the head scan was quote-blind, so an `if ... then`
# inside a quoted string minted an opener and refused a genuine pop.

note "PANEL-K2R2: unit-level closer grammar (glued then, quoted separators, quoted openers)"
check "K2R2-F1 glued one-line if does not pop an outer fi" closer_stuck 'if true;then :;fi' 'fi'
check "K2R2-F1 glued then opens fi" opener_eq 'if [ -f \"$HOME/.optional\" ];then' 'fi'
check "K2R2-F1 bare glued then opens fi" opener_eq 'if true;then' 'fi'
check "K2R2-F2 quoted ;fi; does not re-close the same-line if" closer_stuck 'if true; then echo "a;fi;b"; fi' 'fi'
check "K2R2-F2 single-quoted ;fi; does not re-close the same-line if" closer_stuck "if true; then echo 'a;fi;b'; fi" 'fi'
check "K2R2-F2 balanced compound plus a further closer still pops" closer_pops 'if true; then echo "done"; fi; fi' 'fi'
check "K2R2-F3 quoted if...then mints no opener; the closer pops" closer_pops 'echo "; if x; then y"; fi' 'fi'
check "K2R2-F3 single-quoted if...then mints no opener; the closer pops" closer_pops "echo '; if x; then y'; fi" 'fi'
check "K2R2-F3 escaped quotes are literal; the same-line if still owns its fi" closer_stuck 'echo \"; if x; then y\"; fi' 'fi'

note "PANEL-K2b: a glued one-line compound inside a false conditional does not strand the block"
new_home k2b
cat >"$FH/.bashrc" <<'EOF'
if [ -f /etc/some-nonexistent-file ]; then
  if true;then :;fi
  case $- in
    *i*) ;;
    *) return;;
  esac
fi
echo AFTER
EOF
run_env install_env_block
check "K2b rc 0" test "$RC" -eq 0
check_out "K2b env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
OUTER_FI_LINE="$(grep -nxF 'fi' "$FH/.bashrc" | head -1 | cut -d: -f1)"
check "K2b block after the outer conditional" test "$BLOCK_LINE" -gt "$OUTER_FI_LINE"
NI_OUT="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf "JAVA=%s" "${JAVA_HOME:-<unset>}"' 2>/dev/null)"
check "K2b block reachable in a noninteractive source" test "${NI_OUT##*JAVA=}" = "$FH/opt/jdk-$TEMURIN_VERSION"
check "K2b trailing content still executes" test "${NI_OUT#*AFTER}" != "$NI_OUT"
LOGIN_OUT="$(env -i HOME="$FH" /bin/bash -lc 'printf "JAVA=%s" "${JAVA_HOME:-<unset>}"' 2>/dev/null)"
check "K2b block reachable in a login shell" test "${LOGIN_OUT##*JAVA=}" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "K2b second run rc 0" test "$RC" -eq 0
check "K2b fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

note "PANEL-K2c: a quoted ;fi; inside a one-line compound does not strand the block"
new_home k2c
cat >"$FH/.bashrc" <<'EOF'
if [ -f /etc/some-nonexistent-file ]; then
  if true; then echo "a;fi;b"; fi
  case $- in
    *i*) ;;
    *) return;;
  esac
fi
echo AFTER
EOF
run_env install_env_block
check "K2c rc 0" test "$RC" -eq 0
check_out "K2c env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
OUTER_FI_LINE="$(grep -nxF 'fi' "$FH/.bashrc" | head -1 | cut -d: -f1)"
check "K2c block after the outer conditional" test "$BLOCK_LINE" -gt "$OUTER_FI_LINE"
NI_OUT="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf "JAVA=%s" "${JAVA_HOME:-<unset>}"' 2>/dev/null)"
check "K2c block reachable in a noninteractive source" test "${NI_OUT##*JAVA=}" = "$FH/opt/jdk-$TEMURIN_VERSION"
check "K2c trailing content still executes" test "${NI_OUT#*AFTER}" != "$NI_OUT"
LOGIN_OUT="$(env -i HOME="$FH" /bin/bash -lc 'printf "JAVA=%s" "${JAVA_HOME:-<unset>}"' 2>/dev/null)"
check "K2c block reachable in a login shell" test "${LOGIN_OUT##*JAVA=}" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "K2c second run rc 0" test "$RC" -eq 0
check "K2c fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

note "PANEL-K2d: a quoted if...then on the closing line does not strand the block after the guard"
new_home k2d
cat >"$FH/.bashrc" <<'EOF'
if [ -f /etc/some-nonexistent-file ]; then
  echo starting
  echo "; if x; then y"; fi
case $- in
  *i*) ;;
  *) return;;
esac
export AFTER=1
EOF
run_env install_env_block
check "K2d rc 0" test "$RC" -eq 0
check_out "K2d env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
GUARD_LINE="$(line_of 'case $- in')"
check "K2d block before the guard" test "$BLOCK_LINE" -lt "$GUARD_LINE"
NI_OUT="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf "JAVA=%s" "${JAVA_HOME:-<unset>}"' 2>/dev/null)"
check "K2d block reachable in a noninteractive source" test "${NI_OUT##*JAVA=}" = "$FH/opt/jdk-$TEMURIN_VERSION"
LOGIN_OUT="$(env -i HOME="$FH" /bin/bash -lc 'printf "JAVA=%s" "${JAVA_HOME:-<unset>}"' 2>/dev/null)"
check "K2d block reachable in a login shell" test "${LOGIN_OUT##*JAVA=}" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "K2d second run rc 0" test "$RC" -eq 0
check "K2d fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

note "PANEL-K2e: a glued outer opener still nests the guard"
new_home k2e
cat >"$FH/.bashrc" <<'EOF'
if [ -f /etc/some-nonexistent-file ];then
  case $- in
    *i*) ;;
    *) return;;
  esac
fi
echo AFTER
EOF
run_env install_env_block
check "K2e rc 0" test "$RC" -eq 0
check_out "K2e env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
OUTER_FI_LINE="$(grep -nxF 'fi' "$FH/.bashrc" | head -1 | cut -d: -f1)"
check "K2e block after the outer conditional" test "$BLOCK_LINE" -gt "$OUTER_FI_LINE"
NI_OUT="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf "JAVA=%s" "${JAVA_HOME:-<unset>}"' 2>/dev/null)"
check "K2e block reachable in a noninteractive source" test "${NI_OUT##*JAVA=}" = "$FH/opt/jdk-$TEMURIN_VERSION"
check "K2e trailing content still executes" test "${NI_OUT#*AFTER}" != "$NI_OUT"
LOGIN_OUT="$(env -i HOME="$FH" /bin/bash -lc 'printf "JAVA=%s" "${JAVA_HOME:-<unset>}"' 2>/dev/null)"
check "K2e block reachable in a login shell" test "${LOGIN_OUT##*JAVA=}" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "K2e second run rc 0" test "$RC" -eq 0
check "K2e fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

# ================= PR #201 Sourcery S1-S3: the head-opens walk =================
# Sourcery review of the K2 fix found three more shapes where the
# head-opens check diverged from bash compound structure: (S1) it
# matched one opener and counted a NESTED same-type compound's closer
# as that opener's re-close, so the tail closer popped an outer frame;
# (S2) a compound inside an unquoted command substitution closed with
# `fi)` / `esac)`, which the re-close scan did not recognize, so a
# genuine pop was refused and the phantom frame hid the guard; (S3) a
# compound after `&&` / `||` is at a command position the opener
# shapes did not recognize, so its tail closer popped an outer frame.

note "PR201-S1: unit-level closer grammar (a nested same-type compound owns the tail closer)"
check "S1 if nested after then does not pop an outer fi" closer_stuck 'if true; then if true; then :; fi; fi' 'fi'
check "S1 if nested after ; does not pop an outer fi" closer_stuck 'if true; then :; if true; then :; fi; fi' 'fi'
check "S1 nested function does not pop an outer }" closer_stuck 'f() { g() { :; }; }' '}'
check "S1 nested case does not pop an outer esac" closer_stuck 'case x in x) case y in y) :;; esac; esac' 'esac'
check "S1 nested compound plus a further closer still pops" closer_pops 'if true; then if true; then :; fi; fi; fi' 'fi'

note "PR201-S2: unit-level closer grammar (a compound inside a command substitution closes there)"
check "S2 substitution if closed by fi) lets the tail fi pop" closer_pops 'x=$(echo hi; if true; then :; fi); fi' 'fi'
check "S2 substitution case closed by esac) lets the tail esac pop" closer_pops 'x=$(echo hi; case x in x) :;; esac); esac' 'esac'
check "S2 same-line if around a substitution does not pop an outer fi" closer_stuck 'if true; then x=$(if true; then :; fi); fi' 'fi'

note "PR201-S3: unit-level closer grammar (a compound after && or || owns its closer)"
check "S3 if after && does not pop an outer fi" closer_stuck 'true && if true; then :; fi' 'fi'
check "S3 if after || does not pop an outer fi" closer_stuck 'false || if true; then :; fi' 'fi'
check "S3 case after && does not pop an outer esac" closer_stuck 'true && case x in x) :;; esac' 'esac'
check "S3 function after && does not pop an outer }" closer_stuck 'true && f() { :; }' '}'
check "S3 plain command after && still pops" closer_pops 'true && :; fi' 'fi'

note "PR201-S1a: a nested one-line compound inside a false conditional does not strand the block"
new_home s1a
cat >"$FH/.bashrc" <<'EOF'
if [ -f /etc/some-nonexistent-file ]; then
  if true; then if true; then :; fi; fi
  case $- in
    *i*) ;;
    *) return;;
  esac
fi
echo AFTER
EOF
run_env install_env_block
check "S1a rc 0" test "$RC" -eq 0
check_out "S1a env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
OUTER_FI_LINE="$(grep -nxF 'fi' "$FH/.bashrc" | head -1 | cut -d: -f1)"
check "S1a block after the outer conditional" test "$BLOCK_LINE" -gt "$OUTER_FI_LINE"
NI_OUT="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf "JAVA=%s" "${JAVA_HOME:-<unset>}"' 2>/dev/null)"
check "S1a block reachable in a noninteractive source" test "${NI_OUT##*JAVA=}" = "$FH/opt/jdk-$TEMURIN_VERSION"
check "S1a trailing content still executes" test "${NI_OUT#*AFTER}" != "$NI_OUT"
LOGIN_OUT="$(env -i HOME="$FH" /bin/bash -lc 'printf "JAVA=%s" "${JAVA_HOME:-<unset>}"' 2>/dev/null)"
check "S1a block reachable in a login shell" test "${LOGIN_OUT##*JAVA=}" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "S1a second run rc 0" test "$RC" -eq 0
check "S1a fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

note "PR201-S3a: a compound after && inside a false conditional does not strand the block"
new_home s3a
cat >"$FH/.bashrc" <<'EOF'
if [ -f /etc/some-nonexistent-file ]; then
  true && if true; then :; fi
  case $- in
    *i*) ;;
    *) return;;
  esac
fi
echo AFTER
EOF
run_env install_env_block
check "S3a rc 0" test "$RC" -eq 0
check_out "S3a env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
OUTER_FI_LINE="$(grep -nxF 'fi' "$FH/.bashrc" | head -1 | cut -d: -f1)"
check "S3a block after the outer conditional" test "$BLOCK_LINE" -gt "$OUTER_FI_LINE"
NI_OUT="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf "JAVA=%s" "${JAVA_HOME:-<unset>}"' 2>/dev/null)"
check "S3a block reachable in a noninteractive source" test "${NI_OUT##*JAVA=}" = "$FH/opt/jdk-$TEMURIN_VERSION"
check "S3a trailing content still executes" test "${NI_OUT#*AFTER}" != "$NI_OUT"
LOGIN_OUT="$(env -i HOME="$FH" /bin/bash -lc 'printf "JAVA=%s" "${JAVA_HOME:-<unset>}"' 2>/dev/null)"
check "S3a block reachable in a login shell" test "${LOGIN_OUT##*JAVA=}" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "S3a second run rc 0" test "$RC" -eq 0
check "S3a fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

note "PR201-S2a: a substitution compound on the closing line does not hide the guard"
new_home s2a
cat >"$FH/.bashrc" <<'EOF'
if [ -f "$HOME/.optional" ]; then
  . "$HOME/.optional"
x=$(echo hi; if true; then :; fi); fi
case $- in
  *i*) ;;
  *) return;;
esac
export AFTER=1
EOF
run_env install_env_block
check "S2a rc 0" test "$RC" -eq 0
check_out "S2a env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
GUARD_LINE="$(line_of 'case $- in')"
check "S2a block before the guard" test "$BLOCK_LINE" -lt "$GUARD_LINE"
NI_OUT="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf "JAVA=%s" "${JAVA_HOME:-<unset>}"' 2>/dev/null)"
check "S2a block reachable in a noninteractive source" test "${NI_OUT##*JAVA=}" = "$FH/opt/jdk-$TEMURIN_VERSION"
LOGIN_OUT="$(env -i HOME="$FH" /bin/bash -lc 'printf "JAVA=%s" "${JAVA_HOME:-<unset>}"' 2>/dev/null)"
check "S2a block reachable in a login shell" test "${LOGIN_OUT##*JAVA=}" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "S2a second run rc 0" test "$RC" -eq 0
check "S2a fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

# ================= PR #201 round 3: parenthesized case patterns =================
# Round-3 independent review of the head-opens walk found its pattern
# state counted every `(` as nesting depth, so a parenthesized
# pattern's own terminating `)` was consumed as a depth decrement and
# the state never flipped to the arm body. Compounds in the arm body
# became invisible: a self-contained arm-body `if`'s trailing `fi`
# then popped an OUTER frame (the K2 desync direction). In valid bash
# a pattern's parens are only the optional leading `(`, an extglob
# group whose `)` is the pattern terminator, or substitution parens —
# so only a `$(` opens tracked nesting in pattern state; any other
# `)` ends the pattern.

note "PANEL-K2R3: unit-level closer grammar (a parenthesized pattern ends at its own close paren)"
check "K2R3 leading-paren pattern arm-body if does not pop an outer fi" closer_stuck 'case x in (x) if b; then :; fi' 'fi'
check "K2R3 leading-paren alternation arm-body if does not pop an outer fi" closer_stuck 'case x in (a|b) if b; then :; fi' 'fi'
check "K2R3 star-extglob pattern arm-body if does not pop an outer fi" closer_stuck 'case x in *(a|b) if b; then :; fi' 'fi'
check "K2R3 at-extglob pattern arm-body if does not pop an outer fi" closer_stuck 'case x in @(a|b) if b; then :; fi' 'fi'
check "K2R3 plus-extglob pattern arm-body if does not pop an outer fi" closer_stuck 'case x in +(a|b) if b; then :; fi' 'fi'
check "K2R3 bang-extglob pattern arm-body if does not pop an outer fi" closer_stuck 'case x in !(a|b) if b; then :; fi' 'fi'
check "K2R3 plain alternation arm-body if does not pop an outer fi (control)" closer_stuck 'case x in a|b) if b; then :; fi' 'fi'
check "K2R3 substitution pattern arm-body if does not pop an outer fi (control)" closer_stuck 'case x in $(echo a|b)) if b; then :; fi' 'fi'
check "K2R3 arithmetic pattern arm-body if does not pop an outer fi (control)" closer_stuck 'case x in $((1+2))) if b; then :; fi' 'fi'
check "K2R3 subshell-in-substitution pattern arm-body if does not pop an outer fi (control)" closer_stuck 'case x in $( (echo hi) )) if b; then :; fi' 'fi'
check "K2R3 pattern-only extglob line still lets the tail fi pop (control)" closer_pops 'case x in *(a|b) :;; esac; fi' 'fi'

note "PANEL-K2R3a: a parenthesized-pattern arm-body compound inside a false conditional does not strand the block"
new_home k2r3a
cat >"$FH/.bashrc" <<'EOF'
if [ -f /etc/some-nonexistent-file ]; then
  case x in (y) if true; then :; fi
  esac
  case $- in
    *i*) ;;
    *) return;;
  esac
fi
echo AFTER
EOF
run_env install_env_block
check "K2R3a rc 0" test "$RC" -eq 0
check_out "K2R3a env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
OUTER_FI_LINE="$(grep -nxF 'fi' "$FH/.bashrc" | head -1 | cut -d: -f1)"
check "K2R3a block after the outer conditional" test "$BLOCK_LINE" -gt "$OUTER_FI_LINE"
NI_OUT="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf "JAVA=%s" "${JAVA_HOME:-<unset>}"' 2>/dev/null)"
check "K2R3a block reachable in a noninteractive source" test "${NI_OUT##*JAVA=}" = "$FH/opt/jdk-$TEMURIN_VERSION"
check "K2R3a trailing content still executes" test "${NI_OUT#*AFTER}" != "$NI_OUT"
LOGIN_OUT="$(env -i HOME="$FH" /bin/bash -lc 'printf "JAVA=%s" "${JAVA_HOME:-<unset>}"' 2>/dev/null)"
check "K2R3a block reachable in a login shell" test "${LOGIN_OUT##*JAVA=}" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "K2R3a second run rc 0" test "$RC" -eq 0
check "K2R3a fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

# ================= #207: unpredictable temp path for the .bashrc write =================

stray_temps() { # stray_temps: count install temp leftovers (not the .bak, not a planted symlink)
  find "$FH" -maxdepth 1 -name '.bashrc.install-re-runtime.*' ! -name '*.bak' ! -type l | wc -l | tr -d ' '
}

note "#207a: a planted symlink at the old fixed temp path is never followed or touched"
new_home 207a
printf 'export USER_LINE=1\n' >"$FH/.bashrc"
printf 'canary-original\n' >"$FH/canary"
ln -s "$FH/canary" "$FH/.bashrc.install-re-runtime.tmp"
CANARY_SHA="$(file_sha "$FH/canary")"
run_env install_env_block
check "207a rc 0" test "$RC" -eq 0
check_out "207a env ok" 'INSTALL-RE: env ok' "$OUT"
check "207a canary content untouched" test "$(file_sha "$FH/canary")" = "$CANARY_SHA"
check "207a planted symlink untouched" test -L "$FH/.bashrc.install-re-runtime.tmp"
check "207a symlink still points at the canary" test "$(readlink "$FH/.bashrc.install-re-runtime.tmp")" = "$FH/canary"
check "207a block written to .bashrc" test "$(marker_count '>>>')" -eq 1
check "207a no temp leftovers" test "$(stray_temps)" -eq 0

note "#207b: a failed compose step leaves no temp file behind"
new_home 207b
printf 'export USER_LINE=1\n' >"$FH/.bashrc"
mkdir -p "$SB/failbin"
printf '#!/bin/bash\nexit 1\n' >"$SB/failbin/sync"
chmod +x "$SB/failbin/sync"
BASHRC_SHA="$(file_sha "$FH/.bashrc")"
RUN_PATH_PREFIX="$SB/failbin" run_env install_env_block
check "207b failure rc nonzero" test "$RC" -ne 0
check_out "207b names the fsync failure" 'cannot fsync' "$OUT"
check "207b no temp leftovers after failure" test "$(stray_temps)" -eq 0
check "207b .bashrc unchanged after failure" test "$(file_sha "$FH/.bashrc")" = "$BASHRC_SHA"

note "#207c: new-file mode stays umask-derived (mktemp's 0600 is not inherited)"
new_home 207c
RUN_UMASK=022 run_env install_env_block
check "207c rc 0" test "$RC" -eq 0
check "207c fresh .bashrc is 0644 under umask 022" test "$(/usr/bin/stat -c %a "$FH/.bashrc" 2>/dev/null || /usr/bin/stat -f %Lp "$FH/.bashrc")" = "644"

# ================= #195 (K1): a metacharacter-led comment is a comment =================

note "#195: unit-level strip_trailing_comment (# after ; & | ( ) starts a comment; data # does not)"
strip_eq() { # strip_eq <line> <expected-output>
  local got
  got="$(
    (
      # shellcheck disable=SC1090 # the fixture library is generated above
      source "$LIB"
      set +eu
      strip_trailing_comment "$1"
    ) 2>/dev/null
  )"
  test "$got" = "$2"
}
check "K1 semicolon-led comment is cut" strip_eq 'echo x;# case foo in' 'echo x;'
check "K1 ampersand-led comment is cut" strip_eq 'true&&# if foo; then' 'true&&'
check "K1 single-ampersand-led comment is cut" strip_eq 'sleep 1&# if foo; then' 'sleep 1&'
check "K1 pipe-led comment is cut" strip_eq 'true|# case foo in' 'true|'
check "K1 open-paren-led comment is cut" strip_eq '(# case foo in' '('
check "K1 close-paren-led comment is cut" strip_eq '(echo x)# case foo in' '(echo x)'
check "K1 whitespace-led comment is still cut" strip_eq 'echo x # case foo in' 'echo x'
check "K1 line-start comment is still cut" strip_eq '# case foo in' ''
check "K1 \$# is data" strip_eq 'echo $# case foo in' 'echo $# case foo in'
check "K1 \${#var} is data" strip_eq 'echo ${#var};# case foo in' 'echo ${#var};'
check "K1 glued foo#bar is data" strip_eq 'echo foo#bar case foo in' 'echo foo#bar case foo in'
check "K1 double-quoted ;# is data" strip_eq 'echo "x;# case foo in"' 'echo "x;# case foo in"'
check "K1 single-quoted ;# is data" strip_eq "echo 'x;# case foo in'" "echo 'x;# case foo in'"
check "K1 escaped \;\\# is data" strip_eq 'echo x\;\# case foo in' 'echo x\;\# case foo in'

note "#195: a metacharacter-led comment mints no phantom opener"
check "K1 opener: semicolon-led case comment opens nothing" opener_eq 'echo x;# case foo in' ''
check "K1 opener: ampersand-led if comment opens nothing" opener_eq 'true&&# if foo; then' ''
check "K1 opener: pipe-led case comment opens nothing" opener_eq 'true|# case foo in' ''
check "K1 opener: paren-led case comment opens nothing" opener_eq '(# case foo in' ''
check "K1 opener: real opener before a ;-led comment still opens" opener_eq 'case $x in;# note' 'esac'

note "#195: a phantom opener from a metacharacter-led comment does not strand the block"
new_home k1
cat >"$FH/.bashrc" <<'EOF2'
echo x;# case foo in
case $- in
  *i*) ;;
  *) return;;
esac
export AFTER=1
EOF2
run_env install_env_block
check "K1 rc 0" test "$RC" -eq 0
check_out "K1 env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
GUARD_LINE="$(line_of 'case $- in')"
check "K1 block before the guard" test "$BLOCK_LINE" -lt "$GUARD_LINE"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "K1 second run rc 0" test "$RC" -eq 0
check "K1 fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

# ================= #194 (K4) / #196 (C-P1): closer operators and multiple closers per line =================

note "#194: unit-level closer grammar (a closer followed by an operator or redirection still pops)"
check "K4 fi && pops" closer_pops 'fi && echo ok' 'fi'
check "K4 fi || pops" closer_pops 'fi || :' 'fi'
check "K4 fi>/dev/null pops" closer_pops 'fi >/dev/null' 'fi'
check "K4 fi 2>&1 pops" closer_pops 'fi 2>&1' 'fi'
check "K4 fi | pops" closer_pops 'fi | cat' 'fi'
check "K4 fi & pops" closer_pops 'fi &' 'fi'
check "K4 glued fi&& pops" closer_pops 'fi&&echo ok' 'fi'
check "K4 fi < pops" closer_pops 'fi <in' 'fi'
check "K4 fi >> pops" closer_pops 'fi >>log' 'fi'
check "K4 esac && pops" closer_pops 'esac && echo ok' 'esac'
check "K4 esac 2>&1 pops" closer_pops 'esac 2>&1' 'esac'
check "K4 } && pops" closer_pops '} && :' '}'
check "K4 } >/dev/null pops" closer_pops '} >/dev/null' '}'
check "K4 done && pops" closer_pops 'done && echo ok' 'done'
check "K4 fi) pops" closer_pops 'fi)' 'fi'
check "K4 tail fi && after a plain command pops" closer_pops ':; fi && echo ok' 'fi'
check "K4 identifier file=1 && echo done does not pop fi (control)" closer_stuck 'file=1 && echo done' 'fi'
check "K4 identifier fifo does not pop fi (control)" closer_stuck 'fifo' 'fi'
check "K4 identifier fi_x does not pop fi (control)" closer_stuck 'fi_x && :' 'fi'
check "K4 tail identifier ; file=1 does not pop fi (control)" closer_stuck ':; file=1 && echo done' 'fi'
check "K4 identifier esacx does not pop esac (control)" closer_stuck 'esacx && :' 'esac'
check "K4 identifier done does not pop } (control)" closer_stuck 'echo done' '}'
check "K4 quoted fi after a space is data (control)" closer_stuck 'echo "x; fi y"' 'fi'
check "K4+K2 one-line if followed by && does not pop an outer fi (control)" closer_stuck 'if true; then :; fi && echo ok' 'fi'
check "K4+K2 one-line if followed by a redirect does not pop an outer fi (control)" closer_stuck 'if true; then :; fi >/dev/null' 'fi'
check "K4+K2 one-line case followed by || does not pop an outer esac (control)" closer_stuck 'case x in x) :;; esac || :' 'esac'
check "K4+K2 one-line function followed by && does not pop an outer } (control)" closer_stuck 'f() { :; } && :' '}'

note "#196: unit-level remainder (the slice after the popped closer, for the caller's left-to-right loop)"
closer_rest_eq() { # closer_rest_eq <line> <closer> <expected-remainder>
  local got
  got="$(
    (
      # shellcheck disable=SC1090 # the fixture library is generated above
      source "$LIB"
      set +eu
      ctrl_closer_line "$1" "$2"
    ) 2>/dev/null
  )"
  test "$got" = "$3"
}
check "C-P1 rest after a leading closer" closer_rest_eq 'fi; fi' 'fi' '; fi'
check "C-P1 rest after a tail closer" closer_rest_eq ':; fi; }' 'fi' '; }'
check "C-P1 rest after a closer and an operator" closer_rest_eq 'fi && fi' 'fi' ' && fi'
check "C-P1 second closer pops from the remainder" closer_pops '; fi' 'fi'
check "C-P1 second closer pops after an operator remainder" closer_pops ' && fi' 'fi'
check "C-P1 second closer pops after a redirect remainder" closer_pops ' 2>&1; }' '}'
check "C-P1 compound closed earlier in the remainder still lets the real closer pop" closer_pops 'if true; then :; fi; fi' 'fi'

# multi_fixture <case> <prelude>: a prelude of control structures, then a
# top-level noninteractive-guard. The block belongs BEFORE the guard, so
# the prelude's closers must pop every frame they close.
multi_fixture() {
  local name="$1" prelude="$2" marker guard_line val sha
  new_home "$name"
  {
    printf '%s\n' "$prelude"
    printf 'case $- in\n  *i*) ;;\n  *) return;;\nesac\n'
    printf 'export AFTER=1\n'
  } >"$FH/.bashrc"
  run_env install_env_block
  check "$name rc 0" test "$RC" -eq 0
  check_out "$name env ok" 'INSTALL-RE: env ok' "$OUT"
  marker="$(line_of '# >>> re-runtime >>>')"
  guard_line="$(line_of 'case $- in')"
  check "$name block before the guard" test "$marker" -lt "$guard_line"
  val="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
  check "$name block reachable in a noninteractive source" test "$val" = "$FH/opt/jdk-$TEMURIN_VERSION"
  sha="$(file_sha "$FH/.bashrc")"
  run_env install_env_block
  check "$name second run rc 0" test "$RC" -eq 0
  check "$name fixed point" test "$(file_sha "$FH/.bashrc")" = "$sha"
}

note "#194: a multi-line closer followed by an operator or redirection is recognized (end to end)"
multi_fixture k4-and $'if true; then\n  :\nfi && :'
multi_fixture k4-or $'if true; then\n  :\nfi || :'
multi_fixture k4-devnull $'if true; then\n  :\nfi >/dev/null'
multi_fixture k4-dup $'if true; then\n  :\nfi 2>&1'
multi_fixture k4-pipe $'if true; then\n  :\nfi | cat'
multi_fixture k4-bg $'if true; then\n  :\nfi &'
multi_fixture k4-esac-and $'case x in\n  x) :;;\nesac && :'
multi_fixture k4-brace-and $'f() {\n  :\n} && :'
multi_fixture k4-brace-redir $'f() {\n  :\n} >/dev/null 2>&1'

note "#196: several closers on one physical line each pop a frame (end to end)"
multi_fixture cp1-fi-fi $'if true; then\n  if true; then\n    :\n  fi; fi'
multi_fixture cp1-fi-brace $'f() {\n  if true; then\n    :\n  fi; }'
multi_fixture cp1-esac-fi $'if true; then\n  case x in\n    x) :;;\n  esac; fi'
multi_fixture cp1-esac-fi-brace $'f() {\n  if true; then\n    case x in\n      x) :;;\n    esac; fi; }'
multi_fixture cp1-fi-fi-redir $'if true; then\n  if true; then\n    :\n  fi; fi >/dev/null'
multi_fixture cp1-spaced $'if true; then\n  if true; then\n    :\n  fi ; fi ;'

note "#196: a guard whose return shares a multi-closer line is still recognized (R4F1 preserved)"
new_home cp1-return
cat >"$FH/.bashrc" <<'EOF2'
export BEFORE=1
if [ -z "$PS1" ]; then
  if true; then
    return
  fi; fi
export AFTER=1
EOF2
run_env install_env_block
check "cp1-return rc 0" test "$RC" -eq 0
check_out "cp1-return env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
GUARD_LINE="$(line_of 'if [ -z "$PS1" ]')"
check "cp1-return block before the guard" test "$BLOCK_LINE" -lt "$GUARD_LINE"

# ================= #202: an extglob group mid-pattern =================

note "#202: unit-level closer grammar (an extglob group inside a case pattern does not end the pattern at its own close paren)"
check "202 mid-pattern @() arm-body if does not pop an outer fi" closer_stuck 'case x in @(a|b)c) if b; then :; fi' 'fi'
check "202 mid-pattern *() arm-body if does not pop an outer fi" closer_stuck 'case x in *(a|b)c) if b; then :; fi' 'fi'
check "202 mid-pattern +() arm-body if does not pop an outer fi" closer_stuck 'case x in +(a|b)c) if b; then :; fi' 'fi'
check "202 mid-pattern ?() arm-body if does not pop an outer fi" closer_stuck 'case x in ?(a|b)c) if b; then :; fi' 'fi'
check "202 mid-pattern !() arm-body if does not pop an outer fi" closer_stuck 'case x in !(a|b)c) if b; then :; fi' 'fi'
check "202 prefixed mid-pattern group arm-body if does not pop an outer fi" closer_stuck 'case x in pre@(a|b)post) if b; then :; fi' 'fi'
check "202 nested groups arm-body if does not pop an outer fi" closer_stuck 'case x in @(a|@(b|c))) if b; then :; fi' 'fi'
check "202 nested mid-pattern groups arm-body if does not pop an outer fi" closer_stuck 'case x in @(a|*(b|c)d)e) if b; then :; fi' 'fi'
check "202 two groups in one pattern arm-body if does not pop an outer fi" closer_stuck 'case x in @(a|b)@(c|d)) if b; then :; fi' 'fi'
check "202 leading-paren pattern with a group arm-body if does not pop an outer fi" closer_stuck 'case x in (@(a|b)c) if b; then :; fi' 'fi'
check "202 mid-pattern group arm-body case does not pop an outer esac" closer_stuck 'case x in @(a|b)c) case y in y) :;; esac' 'esac'
check "202 group with a substitution arm-body if does not pop an outer fi" closer_stuck 'case x in @(a|$(echo b))c) if b; then :; fi' 'fi'
check "202 second arm after a group arm keeps tracking" closer_stuck 'case x in @(a|b)c) :;; d) if b; then :; fi' 'fi'
check "202 ;; resets a stale group depth" closer_stuck 'case x in @(a ;; b) if y; then :; fi' 'fi'
check "202 ;& resets a stale group depth" closer_stuck 'case x in @(a ;& b) if y; then :; fi' 'fi'
check "202 valid leading group with its own terminator arm-body if does not pop an outer fi" closer_stuck 'case x in @(a|b)) if b; then :; fi' 'fi'
check "202 group then alternation arm-body if does not pop an outer fi" closer_stuck 'case x in @(a|b) | c) if b; then :; fi' 'fi'
check "202 ;;& resets a stale group depth" closer_stuck 'case x in @(a ;;& b) if y; then :; fi' 'fi'
check "202 quoted group is plain data (control)" closer_stuck 'case x in "@(a|b)") if b; then :; fi' 'fi'
check "202 single-quoted group is plain data (control)" closer_stuck "case x in '@(a|b)') if b; then :; fi" 'fi'
check "202 leading group (K2R3) still ends at its own paren (control)" closer_stuck 'case x in @(a|b) if b; then :; fi' 'fi'
check "202 leading star group (K2R3) still ends at its own paren (control)" closer_stuck 'case x in *(a|b) if b; then :; fi' 'fi'
check "202 plain pattern (K2R3) still ends at its paren (control)" closer_stuck 'case x in a|b) if b; then :; fi' 'fi'
check "202 pattern-only group line still lets the tail fi pop (control)" closer_pops 'case x in @(a|b)c) :;; esac; fi' 'fi'

# No end-to-end fixture: the installer's damage check parses the kept
# content with a plain `bash -n`, which rejects extglob syntax before
# any `shopt -s extglob` could take effect, so such a .bashrc never
# reaches the guard scan. The unit-level closer grammar above is the
# observable surface of this fix.

# ================= #199 (K6): a guard split across physical lines by a continuation =================

note "#199: unit-level continuation grammar (an unescaped trailing backslash outside quotes and comments continues the line)"
line_continues_p() { # line_continues_p <physical-line>
  (
    # shellcheck disable=SC1090 # the fixture library is generated above
    source "$LIB"
    set +eu
    line_continues "$1"
  ) >/dev/null 2>&1
}
line_continues_n() { ! line_continues_p "$1"; }
check "K6 single trailing backslash continues" line_continues_p 'case $- \'
check "K6 backslash after text continues" line_continues_p 'echo a \'
check "K6 three trailing backslashes continue" line_continues_p 'echo a \\\'
check "K6 even trailing backslashes do not continue" line_continues_n 'echo a \\'
check "K6 four trailing backslashes do not continue" line_continues_n 'echo a \\\\'
check "K6 no backslash does not continue" line_continues_n 'echo a'
check "K6 backslash before trailing space does not continue (escaped space)" line_continues_n 'echo a\ '
check "K6 backslash inside single quotes does not continue" line_continues_n "echo 'a \\"
check "K6 backslash inside a comment does not continue" line_continues_n 'echo a # note \'
check "K6 whole-line comment does not continue" line_continues_n '# note \'
check "K6 backslash inside double quotes continues" line_continues_p 'echo "a \'
check "K6 backslash before a carriage return does not continue (bash escapes the CR)" line_continues_n $'echo a \\\r'
check "K6 empty line does not continue" line_continues_n ''

# cont_fixture <case> <guard-text> <first-guard-physical-line>: a
# guard written across continued lines. The block must land before the
# FIRST physical line of the logical guard — never between its pieces.
cont_fixture() {
  local name="$1" guard="$2" first="$3" marker first_line after_line val sha
  new_home "$name"
  {
    printf 'export BEFORE_GUARD=1\n'
    printf '%s\n' "$guard"
    printf 'export AFTER=1\n'
  } >"$FH/.bashrc"
  run_env install_env_block
  check "$name rc 0" test "$RC" -eq 0
  check_out "$name env ok" 'INSTALL-RE: env ok' "$OUT"
  marker="$(line_of '# >>> re-runtime >>>')"
  first_line="$(line_of "$first")"
  after_line="$(line_of 'export AFTER=1')"
  check "$name block before the first physical guard line" test "$marker" -lt "$first_line"
  check "$name block before the trailing content" test "$marker" -lt "$after_line"
  check "$name guard lines stay verbatim and adjacent" grep -qxF "$first" "$FH/.bashrc"
  check "$name kept content still parses" bash -n "$FH/.bashrc"
  val="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
  check "$name block reachable in a noninteractive source" test "$val" = "$FH/opt/jdk-$TEMURIN_VERSION"
  sha="$(file_sha "$FH/.bashrc")"
  run_env install_env_block
  check "$name second run rc 0" test "$RC" -eq 0
  check "$name fixed point" test "$(file_sha "$FH/.bashrc")" = "$sha"
}

note "#199: a guard whose opener is split by a continuation is recognized (end to end)"
cont_fixture k6-case $'case $- \\\nin *i*) ;; *) return;; esac' 'case $- \'
cont_fixture k6-case-multi $'case $- \\\nin\n  *i*) ;;\n  *) return;;\nesac' 'case $- \'
cont_fixture k6-if $'if [[ $- != *i* ]] \\\n; then\n  return\nfi' 'if [[ $- != *i* ]] \'
cont_fixture k6-ps1 $'[ -z "$PS1" ] \\\n&& return' '[ -z "$PS1" ] \'
cont_fixture k6-ps1-or $'[ -n "$PS1" ] || \\\nreturn' '[ -n "$PS1" ] || \'
cont_fixture k6-three-pieces $'[ -z \\\n"$PS1" ] \\\n&& return' '[ -z \'

note "#199: an even trailing backslash count is not a continuation (control)"
new_home k6-even
cat >"$FH/.bashrc" <<'EOF2'
echo a \\
case $- in
  *i*) ;;
  *) return;;
esac
export AFTER=1
EOF2
run_env install_env_block
check "k6-even rc 0" test "$RC" -eq 0
check_out "k6-even env ok" 'INSTALL-RE: env ok' "$OUT"
BLOCK_LINE="$(line_of '# >>> re-runtime >>>')"
GUARD_LINE="$(line_of 'case $- in')"
check "k6-even block before the guard (not joined into the echo line)" test "$BLOCK_LINE" -lt "$GUARD_LINE"
check "k6-even echo line stays before the block" test "$(line_of 'echo a')" -lt "$BLOCK_LINE"

note "#199: a continued line inside a heredoc body is data, not a join (control)"
new_home k6-heredoc
cat >"$FH/.bashrc" <<'EOF2'
cat >/dev/null <<'DOC'
note \
case $- in
DOC
export AFTER=1
EOF2
run_env install_env_block
check "k6-heredoc rc 0" test "$RC" -eq 0
check_out "k6-heredoc env ok" 'INSTALL-RE: env ok' "$OUT"
check "k6-heredoc body kept verbatim" grep -qxF 'note \' "$FH/.bashrc"
check "k6-heredoc block appended after the heredoc terminator" test "$(line_of '# >>> re-runtime >>>')" -gt "$(last_line_of 'DOC')"

# ================= #200 (K7d): ||, | and & are command-segment boundaries in the profile reader =================

note "#200: unit-level profile_sources_bashrc (a source after ||, | or & is detected; quoted/commented/redirect forms are not boundaries)"
check "K7d || source detected when the guard fails" profile_detected '[ -f ~/.bashrc.missing ] || . ~/.bashrc'
# With no .bashrc in the probe HOME the guard outcome is unknown, so the
# fallback source counts: a shadowing SKIP must not prevent the installer
# from creating the very file the profile tests for (PR #224 finding 2).
check "K7d || source counted when ~/.bashrc is absent at scan" profile_detected '[ -f ~/.bashrc ] || . ~/.bashrc'
check "K7d braced || source detected when the guard fails" profile_detected '[ -f "${HOME}/.bashrc.missing" ] || . "${HOME}/.bashrc"'
check "K7d glued || source detected" profile_detected 'false||. ~/.bashrc'
check "K7d | source not counted (pipeline subshell)" profile_not_detected 'echo x | . ~/.bashrc'
check "K7d |& source not counted (pipeline subshell)" profile_not_detected 'echo x |& . ~/.bashrc'
check "K7d source after a pipeline then ; still detected (control)" profile_detected 'echo x | cat; . ~/.bashrc'
check "K7d & source detected" profile_detected 'true & . ~/.bashrc'
check "K7d glued & source detected" profile_detected 'true&. ~/.bashrc'
check "K7d && source still detected (control)" profile_detected '[ -f ~/.bashrc ] && . ~/.bashrc'
check "K7d ; source still detected (control)" profile_detected 'true; . ~/.bashrc'
check "K7d source keyword after || detected" profile_detected '[ -f ~/.bashrc.missing ] || source ~/.bashrc'
check "K7d double-quoted || is data, not a boundary" profile_not_detected 'echo "a || . ~/.bashrc"'
check "K7d single-quoted | is data, not a boundary" profile_not_detected "echo 'a | . ~/.bashrc'"
check "K7d double-quoted & is data, not a boundary" profile_not_detected 'echo "a & . ~/.bashrc"'
check "K7d escaped \\| is data, not a boundary" profile_not_detected 'echo a \| . ~/.bashrc'
check "K7d || inside a trailing comment is not a boundary" profile_not_detected 'echo x # a || . ~/.bashrc'
check "K7d ; inside a trailing comment is not a boundary" profile_not_detected 'echo x # a; . ~/.bashrc'
check "K7d >& redirection is not a boundary" profile_not_detected 'echo >& . ~/.bashrc'
check "K7d <& redirection is not a boundary" profile_not_detected 'cat <& . ~/.bashrc'
check "K7d &> redirection is not a boundary" profile_not_detected 'echo &> . ~/.bashrc'
check "K7d 2>&1 redirection does not split a mention" profile_not_detected 'echo . ~/.bashrc 2>&1'
check "K7d a source of another file after || is not ~/.bashrc" profile_not_detected '[ -f ~/.x ] || . ~/.other'
check "K7d a mention after || without a source command is not detected" profile_not_detected 'true || echo ". ~/.bashrc"'

note "#200: a .bash_profile sourcing .bashrc through || is not shadowing (end to end)"
new_home k7d
printf '[ -f "$HOME/.bashrc.missing" ] || . "$HOME/.bashrc"\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "k7d rc 0" test "$RC" -eq 0
check_out "k7d env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "k7d no shadowing SKIP" 'login startup is shadowed by' "$OUT"
check "k7d block written" test "$(marker_count '>>>')" -eq 1

# ================= #198 (K5): heredoc bodies and provably-dead branches are not sourcing =================

note "#198: unit-level profile_sources_bashrc (a heredoc body or a provably-dead branch never counts as sourcing)"
check "K5 quoted-heredoc body mention not detected" profile_not_detected $'cat <<\'EOF\'\n. ~/.bashrc\nEOF'
check "K5 unquoted-heredoc body mention not detected" profile_not_detected $'cat <<EOF\n. ~/.bashrc\nEOF'
check "K5 dash-heredoc body mention not detected (tab-indented terminator)" profile_not_detected $'cat <<-EOF\n\t. ~/.bashrc\n\tEOF'
check "K5 double-quoted-delimiter heredoc body mention not detected" profile_not_detected $'cat <<"END"\nsource ~/.bashrc\nEND'
check "K5 heredoc mention with a source after the terminator detected (positive control)" profile_detected $'cat <<\'EOF\'\n. ~/.bashrc\nEOF\n. ~/.bashrc'
check "K5 heredoc with an unrelated body then a real source detected (positive control)" profile_detected $'cat <<EOF\nhello\nEOF\n[ -f ~/.bashrc ] && . ~/.bashrc'
check "K5 two heredocs on one line both skipped" profile_not_detected $'cat <<A <<B\n. ~/.bashrc\nA\n. ~/.bashrc\nB'
check "K5 here-string mention is not a heredoc (control)" profile_detected $'cat <<< hi\n. ~/.bashrc'
check "K5 if false then-branch not detected" profile_not_detected 'if false; then . ~/.bashrc; fi'
check "K5 multi-line if false then-branch not detected" profile_not_detected $'if false\nthen\n  . ~/.bashrc\nfi'
check "K5 multi-line if false (then on the cond line) not detected" profile_not_detected $'if false; then\n  . ~/.bashrc\nfi'
check "K5 false && source not detected" profile_not_detected 'false && . ~/.bashrc'
check "K5 [ 0 = 1 ] && source not detected" profile_not_detected '[ 0 = 1 ] && . ~/.bashrc'
check "K5 [ 1 = 0 ] && source not detected" profile_not_detected '[ 1 = 0 ] && . ~/.bashrc'
check "K5 true || source not detected" profile_not_detected 'true || . ~/.bashrc'
check "K5 dead chain through a middle && not detected" profile_not_detected 'false && : && . ~/.bashrc'
check "K5 nested live if inside a dead if not detected" profile_not_detected 'if false; then if true; then . ~/.bashrc; fi; fi'
check "K5 else branch of if true not detected" profile_not_detected 'if true; then :; else . ~/.bashrc; fi'
check "K5 else branch of if false detected" profile_detected 'if false; then :; else . ~/.bashrc; fi'
check "K5 then branch of if true detected" profile_detected 'if true; then . ~/.bashrc; fi'
check "K5 unknown condition detected (control)" profile_detected 'if [ -f ~/.bashrc ]; then . ~/.bashrc; fi'
check "K5 source after a closed dead if detected" profile_detected 'if false; then :; fi; . ~/.bashrc'
check "K5 source after a closed dead multi-line if detected" profile_detected $'if false\nthen\n  :\nfi\n. ~/.bashrc'
check "K5 true && source detected (control)" profile_detected 'true && . ~/.bashrc'
check "K5 false || source detected (control)" profile_detected 'false || . ~/.bashrc'
check "K5 dead && then || fallback detected" profile_detected 'false && : || . ~/.bashrc'
check "K5 false ; source detected (a ; ends the dead chain)" profile_detected 'false; . ~/.bashrc'
check "K5 elif keeps the branch live (conservative control)" profile_detected $'if false; then :\nelif [ -f ~/.x ]; then\n  . ~/.bashrc\nfi'
check "K5 compound if false || cond stays live (J2)" profile_detected 'if false || [ -f ~/.bashrc ]; then . ~/.bashrc; fi'
check "K5 compound if [ 0 = 1 ] || cond stays live (J2)" profile_detected 'if [ 0 = 1 ] || [ -f ~/.bashrc ]; then . ~/.bashrc; fi'
check "K5 compound if false; true stays live (J2)" profile_detected 'if false; true; then . ~/.bashrc; fi'
check "K5 compound if false | true stays live (J2)" profile_detected 'if false | true; then . ~/.bashrc; fi'
check "K5 compound if true && cond else stays live (J2)" profile_detected 'if true && [ -f ~/.x ]; then :; else . ~/.bashrc; fi'
check "K5 dead chain before if true skipped" profile_not_detected 'false && if true; then . ~/.bashrc; fi'
check "K5 dead chain before if true else skipped" profile_not_detected 'false && if true; then :; else . ~/.bashrc; fi'

note "#198: a .bash_profile whose only .bashrc source is a heredoc mention or a dead branch is shadowing (end to end)"
new_home k5a
printf 'cat <<'"'"'EOF'"'"'\n. "$HOME/.bashrc"\nEOF\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "k5a rc 0" test "$RC" -eq 0
check_out "k5a shadowing SKIP line" 'login startup is shadowed by' "$OUT"
check_no_out "k5a no opaque env ok" 'INSTALL-RE: env ok' "$OUT"
check "k5a no block composed into an unreachable file" test "$(marker_count '>>>')" -eq 0

new_home k5b
printf 'if false; then\n  . "$HOME/.bashrc"\nfi\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "k5b rc 0" test "$RC" -eq 0
check_out "k5b shadowing SKIP line" 'login startup is shadowed by' "$OUT"
check "k5b no block composed into an unreachable file" test "$(marker_count '>>>')" -eq 0

new_home k5c
printf 'cat <<'"'"'EOF'"'"'\n. "$HOME/.bashrc"\nEOF\n[ -f "$HOME/.bashrc" ] && . "$HOME/.bashrc"\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "k5c rc 0" test "$RC" -eq 0
check_out "k5c env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "k5c no shadowing SKIP" 'login startup is shadowed by' "$OUT"
check "k5c block written" test "$(marker_count '>>>')" -eq 1

# ================= #197 (K3): a pre-existing .profile must source ~/.bashrc =================

note "#197a: a non-sourcing pre-existing .profile is named, left byte-identical, and no block is written"
new_home k3a
printf '# my own profile\nexport EDITOR=vim\n' >"$FH/.profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
PROFILE_SHA="$(file_sha "$FH/.profile")"
BASHRC_SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "k3a rc 0" test "$RC" -eq 0
check_out "k3a shadowing SKIP line" 'login startup is shadowed by' "$OUT"
check_out "k3a names ~/.profile" "$FH/.profile" "$OUT"
check_out "k3a names the non-sourcing reason" 'does not source ~/.bashrc' "$OUT"
check_no_out "k3a no false env ok" 'INSTALL-RE: env ok' "$OUT"
check "k3a .profile byte-identical" test "$(file_sha "$FH/.profile")" = "$PROFILE_SHA"
check "k3a .bashrc untouched" test "$(file_sha "$FH/.bashrc")" = "$BASHRC_SHA"
check "k3a no block composed into an unreachable file" test "$(marker_count '>>>')" -eq 0
run_env install_env_block
check "k3a repeat run rc 0" test "$RC" -eq 0
check_out "k3a repeat run still names the shadowing" 'login startup is shadowed by' "$OUT"
check "k3a repeat run leaves .profile byte-identical" test "$(file_sha "$FH/.profile")" = "$PROFILE_SHA"

note "#197b: a sourcing pre-existing .profile is reachable by a login shell"
new_home k3b
cat >"$FH/.profile" <<'EOF2'
# user profile
if [ -n "$BASH_VERSION" ]; then
  if [ -f "$HOME/.bashrc" ]; then
    . "$HOME/.bashrc"
  fi
fi
EOF2
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
PROFILE_SHA="$(file_sha "$FH/.profile")"
run_env install_env_block
check "k3b rc 0" test "$RC" -eq 0
check_out "k3b env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "k3b no shadowing SKIP" 'login startup is shadowed by' "$OUT"
check "k3b block written" test "$(marker_count '>>>')" -eq 1
check "k3b .profile byte-identical" test "$(file_sha "$FH/.profile")" = "$PROFILE_SHA"
LOGIN_OUT="$(env -i HOME="$FH" /bin/bash -lc 'printf "JAVA=%s" "${JAVA_HOME:-<unset>}"' 2>/dev/null)"
check "k3b block reachable in a login shell" test "${LOGIN_OUT##*JAVA=}" = "$FH/opt/jdk-$TEMURIN_VERSION"
SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "k3b second run rc 0" test "$RC" -eq 0
check "k3b fixed point" test "$(file_sha "$FH/.bashrc")" = "$SHA"

note "#197c: .bash_profile takes precedence over .profile (only the first existing file is judged)"
new_home k3c
printf '# non-sourcing profile\nexport EDITOR=vim\n' >"$FH/.profile"
cat >"$FH/.bash_profile" <<'EOF2'
if [ -f "$HOME/.bashrc" ]; then
  . "$HOME/.bashrc"
fi
EOF2
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "k3c rc 0" test "$RC" -eq 0
check_out "k3c env ok" 'INSTALL-RE: env ok' "$OUT"
check_no_out "k3c no shadowing SKIP" 'login startup is shadowed by' "$OUT"
LOGIN_OUT="$(env -i HOME="$FH" /bin/bash -lc 'printf "JAVA=%s" "${JAVA_HOME:-<unset>}"' 2>/dev/null)"
check "k3c block reachable in a login shell through .bash_profile" test "${LOGIN_OUT##*JAVA=}" = "$FH/opt/jdk-$TEMURIN_VERSION"

note "#197d: a non-sourcing .bash_profile shadows a sourcing .profile (precedence, the other direction)"
new_home k3d
cat >"$FH/.profile" <<'EOF2'
if [ -f "$HOME/.bashrc" ]; then
  . "$HOME/.bashrc"
fi
EOF2
printf '# non-sourcing bash_profile\nexport EDITOR=vim\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "k3d rc 0" test "$RC" -eq 0
check_out "k3d shadowing SKIP names .bash_profile" "$FH/.bash_profile" "$OUT"

note "#197e: an absent .bashrc with a non-sourcing .profile is still named, and nothing is created"
new_home k3e
printf '# my own profile\nexport EDITOR=vim\n' >"$FH/.profile"
run_env install_env_block
check "k3e rc 0" test "$RC" -eq 0
check_out "k3e shadowing SKIP line" 'login startup is shadowed by' "$OUT"
check "k3e no .bashrc created" test ! -e "$FH/.bashrc"

note "#202 end-to-end: extglob mid-pattern with shopt -s extglob passes damage gate and places block before guard"
new_home extglob_e2e
cat >"$FH/.bashrc" <<'EOF2'
shopt -s extglob
if false; then
  case x in @(a|b)c) if b; then :; fi ;; esac
fi
case $- in
  *i*) ;;
  *) return;;
esac
export AFTER=1
EOF2
run_env install_env_block
check "extglob_e2e rc 0" test "$RC" -eq 0
check_out "extglob_e2e env ok" 'INSTALL-RE: env ok' "$OUT"
E2E_VAL="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bashrc"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
check "extglob_e2e block reachable in noninteractive source" test "$E2E_VAL" = "$FH/opt/jdk-$TEMURIN_VERSION"

# ================= PR #220 review residuals: profile-reader parity with bash =================

note "PR220-R1: a source that only runs as a pipeline component is never wiring"
check "PR220 pipeline source not counted" profile_not_detected 'echo x | . ~/.bashrc'
check "PR220 |& pipeline source not counted" profile_not_detected 'echo x |& . ~/.bashrc'
check "PR220 pipeline source not counted across a newline after |" profile_not_detected $'echo x |\n. ~/.bashrc'
check "PR220 pipeline source not counted across a continuation" profile_not_detected $'echo x | \\\n. ~/.bashrc'
check "PR220 a source in the login shell after the pipeline is counted (control)" profile_detected 'echo x | cat; . ~/.bashrc'

note "PR220-R2: && / || chains continue across a newline and skipped commands never count"
check "PR220 dead && chain continued on the next line" profile_not_detected $'false &&\n. ~/.bashrc'
check "PR220 dead && chain continued across a blank line" profile_not_detected $'false &&\n\n. ~/.bashrc'
check "PR220 live || chain continued on the next line (control)" profile_detected $'false ||\n. ~/.bashrc'
check "PR220 live && chain continued on the next line (control)" profile_detected $'true &&\n. ~/.bashrc'

note "PR220-R3: an if condition list split across physical lines is classified only at its then"
check "PR220 multiline condition false/true runs the branch" profile_detected $'if false\ntrue\nthen\n. ~/.bashrc\nfi'
check "PR220 multiline condition false/true; then form" profile_detected $'if false\ntrue; then\n. ~/.bashrc\nfi'
check "PR220 multiline condition false/then stays dead (control)" profile_not_detected $'if false\nthen\n. ~/.bashrc\nfi'
check "PR220 multiline condition false/then on the condition line (control)" profile_not_detected $'if false; then\n. ~/.bashrc\nfi'

note "PR220-R4: an if compound with no branch taken has a successful status"
check "PR220 if false; then :; fi || source is skipped" profile_not_detected 'if false; then :; fi || . ~/.bashrc'
check "PR220 if false; then :; fi && source runs (control)" profile_detected 'if false; then :; fi && . ~/.bashrc'
check "PR220 if true; then false; fi || source runs (control)" profile_detected 'if true; then false; fi || . ~/.bashrc'
check "PR220 if true; then :; fi || source is skipped (compound succeeds)" profile_not_detected 'if true; then :; fi || . ~/.bashrc'

note "PR220-R5: literal comparisons are evaluated, not enumerated as 0/1"
check "PR220 [ 2 = 3 ] then-branch dead" profile_not_detected 'if [ 2 = 3 ]; then . ~/.bashrc; fi'
check "PR220 [ 2 = 2 ] then-branch live (control)" profile_detected 'if [ 2 = 2 ]; then . ~/.bashrc; fi'
check "PR220 [ 1 -gt 2 ] dead" profile_not_detected '[ 1 -gt 2 ] && . ~/.bashrc'
check "PR220 [ 3 -gt 2 ] live (control)" profile_detected '[ 3 -gt 2 ] && . ~/.bashrc'
check "PR220 [[ foo != foo ]] dead" profile_not_detected 'if [[ foo != foo ]]; then . ~/.bashrc; fi'
check "PR220 [ x = y ] dead (string comparison)" profile_not_detected 'if [ x = y ]; then . ~/.bashrc; fi'
check "PR220 test 1 -eq 2 dead" profile_not_detected 'test 1 -eq 2 && . ~/.bashrc'
check "PR220 [[ foo = f* ]] pattern RHS stays reachable" profile_detected '[[ foo = f* ]] && . ~/.bashrc'
check "PR220 [[ foo = \"f*\" ]] quoted RHS is literal and dead" profile_not_detected '[[ foo = "f*" ]] && . ~/.bashrc'
check "PR220 [ foo = \"f*\" ] literal comparison is dead (control)" profile_not_detected '[ foo = "f*" ] && . ~/.bashrc'

note "PR220-R6: a redefined false/true builtin is not a literal constant"
check "PR220 false() override makes if false reachable" profile_detected $'false() { return 0; }\nif false; then . ~/.bashrc; fi'
check "PR220 function false form makes if false reachable" profile_detected $'function false { return 0; }\nif false; then . ~/.bashrc; fi'

note "PR220-R7: a file-existence guard is evaluated for the login shell after install"
# When the probe has no .bashrc, the fallback branch is reachable at
# login; a shadowing SKIP here would stop the installer from creating
# the file the guard tests (PR #224 finding 2).
check "PR220 [ -f ~/.bashrc ] || source is reachable when file absent" profile_detected '[ -f ~/.bashrc ] || . ~/.bashrc'
check "PR220 [ -f \"\$HOME/.bashrc\" ] || source is reachable when file absent" profile_detected '[ -f "$HOME/.bashrc" ] || . "$HOME/.bashrc"'
check "PR220 [ -f ~/.bashrc ] && source runs (control)" profile_detected '[ -f ~/.bashrc ] && . ~/.bashrc'

note "PR220-R8: backslash-continued physical lines are one logical line"
check "PR220 continued source is detected" profile_detected $'. \\\n~/.bashrc'
check "PR220 continued source keyword is detected" profile_detected $'source \\\n"$HOME/.bashrc"'
check "PR220 continued heredoc opener: a source after the terminator is detected" profile_detected $'cat <<E\\\nOF\nbody\nEOF\n. ~/.bashrc'
check "PR220 continued heredoc opener: a source inside the body is not detected" profile_not_detected $'cat <<E\\\nOF\n. ~/.bashrc\nEOF'

note "PR220-R9: a one-argument [ ] / [[ ]] / test is a string test, not a command name"
check "PR220 [ false ] && source runs (non-empty string)" profile_detected '[ false ] && . ~/.bashrc'
check "PR220 [[ false ]] && source runs (non-empty string)" profile_detected '[[ false ]] && . ~/.bashrc'
check "PR220 test false && source runs (non-empty string)" profile_detected 'test false && . ~/.bashrc'
check "PR220 [ \"false\" ] && source runs (quoted string)" profile_detected '[ "false" ] && . ~/.bashrc'
check "PR220 [ \"\" ] && source is skipped (empty string)" profile_not_detected '[ "" ] && . ~/.bashrc'
check "PR220 standalone false && source is skipped (control)" profile_not_detected 'false && . ~/.bashrc'
check "PR220 standalone true && source runs (control)" profile_detected 'true && . ~/.bashrc'

note "PR220-R10: a short-circuited pipeline is skipped whole and does not reset the AND-OR status"
check "PR220 true || echo unused | false && source runs" profile_detected 'true || echo unused | false && . ~/.bashrc'
check "PR220 true || false | false && source runs" profile_detected 'true || false | false && . ~/.bashrc'
check "PR220 false && true | true && source is skipped (control)" profile_not_detected 'false && true | true && . ~/.bashrc'
check "PR220 true | false && source is skipped (control)" profile_not_detected 'true | false && . ~/.bashrc'
check "PR220 false | true && source runs (control)" profile_detected 'false | true && . ~/.bashrc'
check "PR220 false || false | false && source is skipped (control)" profile_not_detected 'false || false | false && . ~/.bashrc'

note "PR220-R11: file tests other than ~/.bashrc stay unknown (earlier startup commands can change them)"
check "PR220 mkdir then [ -d ~/.cache ] && source is reachable" profile_detected $'mkdir -p "$HOME/.cache"\n[ -d "$HOME/.cache" ] && . ~/.bashrc'
check "PR220 [ -f ~/.bashrc ] || source is reachable (installer does not create it on SKIP)" profile_detected '[ -f ~/.bashrc ] || . ~/.bashrc'
check "PR220 [ -d ~/.bashrc ] || source runs (control)" profile_detected '[ -d ~/.bashrc ] || . ~/.bashrc'
check "PR220 standalone false && source is skipped (control)" profile_not_detected 'false && . ~/.bashrc'

note "PR220-R12: [[ ]] arithmetic operands keep bash arithmetic semantics (non-decimal spellings are unknown)"
check "PR220 [[ 010 -eq 8 ]] stays reachable (octal)" profile_detected '[[ 010 -eq 8 ]] && . ~/.bashrc'
check "PR220 [[ 0x10 -eq 16 ]] stays reachable (hex)" profile_detected '[[ 0x10 -eq 16 ]] && . ~/.bashrc'
check "PR220 [[ 2 -eq 2 ]] canonical decimal control stays reachable" profile_detected '[[ 2 -eq 2 ]] && . ~/.bashrc'
check "PR220 [[ 8 -eq 9 ]] canonical decimal control is dead" profile_not_detected '[[ 8 -eq 9 ]] && . ~/.bashrc'
check "PR220 [ 010 -eq 8 ] non-canonical decimal stays reachable (conservative)" profile_detected '[ 010 -eq 8 ] && . ~/.bashrc'

note "PR220-E2E: a path created earlier in the profile is not treated as absent at login"
new_home pr220-mut
printf 'mkdir -p "$HOME/.cache"\n[ -d "$HOME/.cache" ] && . "$HOME/.bashrc"\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "PR220-mut rc 0" test "$RC" -eq 0
check_out "PR220-mut env ok" 'INSTALL-RE: env ok' "$OUT"
check "PR220-mut block written" test "$(marker_count '>>>')" -eq 1
PR220_MUT_VAL="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bash_profile"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
check "PR220-mut block reachable through the profile" test "$PR220_MUT_VAL" = "$FH/opt/jdk-$TEMURIN_VERSION"

note "PR220-E2E: an octal [[ ]] comparison reaches the block"
new_home pr220-oct
printf '[[ 010 -eq 8 ]] && . "$HOME/.bashrc"\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "PR220-oct rc 0" test "$RC" -eq 0
check_out "PR220-oct env ok" 'INSTALL-RE: env ok' "$OUT"
check "PR220-oct block written" test "$(marker_count '>>>')" -eq 1
PR220_OCT_VAL="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bash_profile"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
check "PR220-oct block reachable through the profile" test "$PR220_OCT_VAL" = "$FH/opt/jdk-$TEMURIN_VERSION"

note "PR220-E2E: pipeline-only wiring is named as shadowing end to end"
new_home pr220-pipe
printf 'echo x | . "$HOME/.bashrc"\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "PR220-pipe rc 0" test "$RC" -eq 0
check_out "PR220-pipe shadowing SKIP line" 'login startup is shadowed by' "$OUT"
check_no_out "PR220-pipe no opaque env ok" 'INSTALL-RE: env ok' "$OUT"
check "PR220-pipe no block composed into an unreachable file" test "$(marker_count '>>>')" -eq 0

note "PR220-E2E: [ -f ~/.bashrc ] || . ~/.bashrc never sources it at login"
new_home pr220-orf
printf '[ -f "$HOME/.bashrc" ] || . "$HOME/.bashrc"\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "PR220-orf rc 0" test "$RC" -eq 0
check_out "PR220-orf shadowing SKIP line" 'login startup is shadowed by' "$OUT"
check "PR220-orf no block composed into an unreachable file" test "$(marker_count '>>>')" -eq 0

note "PR220-E2E: a multiline if condition that runs the source reaches the block"
new_home pr220-ml
printf 'if false\ntrue\nthen\n  . "$HOME/.bashrc"\nfi\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "PR220-ml rc 0" test "$RC" -eq 0
check_out "PR220-ml env ok" 'INSTALL-RE: env ok' "$OUT"
check "PR220-ml block written" test "$(marker_count '>>>')" -eq 1
PR220_ML_VAL="$(env -i HOME="$FH" /bin/bash -c '. "$HOME/.bash_profile"; printf %s "${JAVA_HOME:-}"' 2>/dev/null)"
check "PR220-ml block reachable through the profile" test "$PR220_ML_VAL" = "$FH/opt/jdk-$TEMURIN_VERSION"

note "PR220-E2E: a false() override reaches the block"
new_home pr220-fn
printf 'false() { return 0; }\nif false; then . "$HOME/.bashrc"; fi\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "PR220-fn rc 0" test "$RC" -eq 0
check_out "PR220-fn env ok" 'INSTALL-RE: env ok' "$OUT"
check "PR220-fn block written" test "$(marker_count '>>>')" -eq 1

note "PR220-E2E: a backslash-continued source reaches the block"
new_home pr220-cont
printf '. \\\n"$HOME/.bashrc"\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "PR220-cont rc 0" test "$RC" -eq 0
check_out "PR220-cont env ok" 'INSTALL-RE: env ok' "$OUT"
check "PR220-cont block written" test "$(marker_count '>>>')" -eq 1

note "PR220-E2E: a continued heredoc opener is read as one delimiter word"
new_home pr220-hd
printf 'cat <<E\\\nOF\nbody\nEOF\n. "$HOME/.bashrc"\n' >"$FH/.bash_profile"
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
run_env install_env_block
check "PR220-hd rc 0" test "$RC" -eq 0
check_out "PR220-hd env ok" 'INSTALL-RE: env ok' "$OUT"
check "PR220-hd block written" test "$(marker_count '>>>')" -eq 1

note "PR220-CAS: a concurrent .bashrc edit is never overwritten by the composed file"
new_home pr220-cas
printf '# user bashrc\nexport EDITOR=vim\n' >"$FH/.bashrc"
CAS_SHA="$(file_sha "$FH/.bashrc")"
mkdir -p "$SB/casbin"
cat >"$SB/casbin/sync" <<'EOF'
#!/bin/bash
printf '# concurrent edit\n' >>"${HOME:?}/.bashrc"
exec /bin/sync "$@"
EOF
chmod +x "$SB/casbin/sync"
RUN_PATH_PREFIX="$SB/casbin" run_env install_env_block
check "PR220-CAS failure rc nonzero" test "$RC" -ne 0
check_out "PR220-CAS names the concurrent edit" 'concurrent edit' "$OUT"
check "PR220-CAS concurrent edit preserved" test "$(grep -cxF '# concurrent edit' "$FH/.bashrc")" -eq 1
check "PR220-CAS original content preserved" grep -qxF 'export EDITOR=vim' "$FH/.bashrc"
check "PR220-CAS no block installed" test "$(marker_count '>>>')" -eq 0
check "PR220-CAS no temp leftovers" test "$(stray_temps)" -eq 0
check "PR220-CAS backup is the as-found file" test "$(file_sha "$FH/.bashrc.install-re-runtime.bak")" = "$CAS_SHA"

note "PR220-EG: kept .bashrc content must parse under the login shell's own options"
new_home pr220-eg-bad
printf 'case x in @(a|b)c) :;; esac\nexport AFTER=1\n' >"$FH/.bashrc"
BAD_SHA="$(file_sha "$FH/.bashrc")"
run_env install_env_block
check "PR220-EG-bad rc nonzero" test "$RC" -ne 0
check_out "PR220-EG-bad names the damage" 'fails bash -n under the login shell' "$OUT"
check "PR220-EG-bad .bashrc byte-identical" test "$(file_sha "$FH/.bashrc")" = "$BAD_SHA"
check "PR220-EG-bad no block installed" test "$(marker_count '>>>')" -eq 0

new_home pr220-eg-late
printf 'case x in @(a|b)c) :;; esac\nshopt -s extglob\nexport AFTER=1\n' >"$FH/.bashrc"
run_env install_env_block
check "PR220-EG-late extglob before its enabling line is rejected" test "$RC" -ne 0
check_out "PR220-EG-late names the damage" 'fails bash -n under the login shell' "$OUT"

new_home pr220-eg-ok
printf 'shopt -s extglob\ncase x in @(a|b)c) :;; esac\nexport AFTER=1\n' >"$FH/.bashrc"
run_env install_env_block
check "PR220-EG-ok extglob after its enabling line is accepted" test "$RC" -eq 0
check_out "PR220-EG-ok env ok" 'INSTALL-RE: env ok' "$OUT"
check "PR220-EG-ok user line kept" grep -qxF 'export AFTER=1' "$FH/.bashrc"

echo
# ================= PR #224 review findings: false shadowing SKIPs =================
note "224a: canonical decimal operands outside [ -eq ] range follow bash arithmetic"
const_status_of() { # const_status_of <command-text>
  local pdir="$SB/cs-probe"
  rm -rf "$pdir"
  mkdir -p "$pdir"
  (
    HOME="$pdir"
    export HOME
    # shellcheck disable=SC1090 # the fixture library is generated above
    source "$LIB"
    set +eu
    const_status "$1"
  ) 2>/dev/null
}
check "224a out-of-range -eq matches [[ ]] arithmetic" \
  test "$(const_status_of '[[ 18446744073709551616 -eq 0 ]]')" = t

note "224b: a fallback source is reachable when ~/.bashrc is absent at scan time"
check "224b || fallback source counted when .bashrc missing" \
  profile_detected '[ -f ~/.bashrc ] || . ~/.bashrc'

note "224c: relative file test after cd does not resolve against install-time HOME"
check "224c relative test after cd keeps the fallback reachable" \
  profile_detected 'cd /tmp
[ -f .bashrc ] || . "$HOME/.bashrc"'

note "PR220-R13: every unary op on ~/.bashrc keeps only what the installer guarantees"
check "PR220 [ -x ~/.bashrc ] || source runs (0644 is not executable)" profile_detected '[ -x ~/.bashrc ] || . ~/.bashrc'
check "PR220 [ -d ~/.bashrc ] && source is skipped (regular file)" profile_not_detected '[ -d ~/.bashrc ] && . ~/.bashrc'
check "PR220 [ -f \"\$HOME/.bashrc/\" ] || source runs (trailing slash)" profile_detected '[ -f "$HOME/.bashrc/" ] || . ~/.bashrc'
check "PR220 [ -e \"\$HOME/.bashrc/.\" ] || source runs (dot component)" profile_detected '[ -e "$HOME/.bashrc/." ] || . ~/.bashrc'

note "PR220-R14: a source word the scan cannot expand counts as possibly wired"
check "PR220 . \"\$(echo ~/.bashrc)\" is reachable" profile_detected '. "$(echo ~/.bashrc)"'
check "PR220 . \"\${VAR:-~/.bashrc}\" is reachable" profile_detected '. "${VAR:-$HOME/.bashrc}"'
check "PR220 . \"\$UNSET/rc\" is reachable" profile_detected '. "$UNSET/rc"'

note "PR220-R15: numeric operands follow bash arithmetic and non-canonical spellings stay unknown"
check "PR220 [[ 9 -lt 010 ]] reachable (non-canonical right operand)" profile_detected '[[ 9 -lt 010 ]] && . ~/.bashrc'
check "PR220 [[ 10 -gt 010 ]] reachable (octal right operand)" profile_detected '[[ 10 -gt 010 ]] && . ~/.bashrc'
check "PR220 [[ -1 -eq 1 ]] dead (negative control)" profile_not_detected '[[ -1 -eq 1 ]] && . ~/.bashrc'

note "PR220-R16: scanning profile text never executes it"
profile_detected '[ -f "$(touch "$HOME/canary")" ] && . ~/.bashrc'
check "PR220 file-test substitution not executed" test ! -e "$SB/psb-probe/canary"
profile_detected '. "$(touch "$HOME/canary2"; echo ~/.bashrc)"'
check "PR220 source-word substitution not executed" test ! -e "$SB/psb-probe/canary2"

note "224d: a source behind a structural prefix still counts (bash runs it in the login shell)"
check "224d brace group source counted" profile_detected '{ . ~/.bashrc; }'
check "224d bang source counted" profile_detected '! . ~/.bashrc'
check "224d case arm source counted" profile_detected 'case x in x) . ~/.bashrc ;; esac'
check "224d while body source counted" profile_detected 'while true; do . ~/.bashrc; break; done'
check "224d for body source counted" profile_detected 'for i in 1; do . ~/.bashrc; done'
check "224d function body plus call counted" profile_detected 'f() { . ~/.bashrc; }; f'
check "224d command prefix counted" profile_detected 'command . ~/.bashrc'
check "224d builtin prefix counted" profile_detected 'builtin . ~/.bashrc'
check "224d assignment prefix counted" profile_detected 'X=1 . ~/.bashrc'
check "224d eval source counted" profile_detected "eval '. ~/.bashrc'"
check "224d subshell source is not wiring (control)" profile_not_detected '( . ~/.bashrc )'
check "224d dead brace group is not wiring (control)" profile_not_detected 'false && { . ~/.bashrc; }'
check "224d argument that looks like a source is not wiring (control)" profile_not_detected 'echo . ~/.bashrc'
check "224d [ -w ~/.bashrc ] || source is reachable (mode unknown)" profile_detected '[ -w ~/.bashrc ] || . ~/.bashrc'

if [ "$FAILURES" -eq 0 ]; then
  echo "test_install_env_scan: checks=$CHECKS"
  echo "test_install_env_scan: ALL PASS (sandbox $SB)"
  rm -rf "$SB"
  exit 0
fi
echo "test_install_env_scan: $FAILURES failure(s) (sandbox kept at $SB)"
exit 1
