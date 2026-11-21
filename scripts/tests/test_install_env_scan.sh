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
run_env() { # run_env <function-name>
  (
    HOME="$FH"
    PATH="$SB/bin:$PATH"
    export HOME PATH
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
check "122 no block composed" test ! -f "$FH/.bashrc.install-re-runtime.tmp"

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
check "R2F2 braced || chain not detected (unchanged)" profile_not_detected '[ -f "${HOME}/.bashrc" ] || . "${HOME}/.bashrc"'
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

echo
if [ "$FAILURES" -eq 0 ]; then
  echo "test_install_env_scan: ALL PASS (sandbox $SB)"
  rm -rf "$SB"
  exit 0
fi
echo "test_install_env_scan: $FAILURES failure(s) (sandbox kept at $SB)"
exit 1
