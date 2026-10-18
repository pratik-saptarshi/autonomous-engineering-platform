#!/usr/bin/env bash
# boot-gate.sh — fail-closed preflight for autonomous runs.
#
# Asserts the environment is in a known-good state before an autonomous
# session (cron job, agent run) does any real work:
#   1. binaries  — required CLIs are on PATH
#   2. daemon    — the NeuroStrata daemon is answering
#   3. guards    — the guard namespace holds the standing guard rules
#   4. gh-auth   — the GitHub CLI is authenticated
#
# Contract: prints "BOOT-GATE: <name> ok" per passing check; on the first
# failure prints "BOOT-GATE: <name> FAIL: <reason>" and exits 1 immediately.
# It never warns-and-continues. Run with --self-test to execute the
# stub-based negative tests (each prints "SELF-TEST: <case> ok").
set -euo pipefail

# Platform-standard tool locations (see TOOLS.md): non-interactive runs
# (cron, agents) may not source ~/.bashrc, so ensure them here. They are
# APPENDED (not prepended) so a caller-injected PATH — e.g. the --self-test
# stub dir — keeps precedence. The command -v checks below stay strict.
export PATH="$PATH:$HOME/go/bin:$HOME/sdk/go/bin:$HOME/workspace/bin:$HOME/workspace/neurostrata/bin:$HOME/workspace/toolchains/bin"

fail() { # $1 = check name, $2 = reason
  echo "BOOT-GATE: $1 FAIL: $2"
  exit 1
}

ok() { # $1 = check name
  echo "BOOT-GATE: $1 ok"
}

check_binaries() {
  local b
  for b in neurostrata-mcp bd ocr gh; do
    command -v "$b" >/dev/null 2>&1 || fail binaries "required binary '$b' not found in PATH"
  done
  ok binaries
}

check_daemon() {
  local out
  if ! out=$(neurostrata-mcp status 2>&1); then
    fail daemon "neurostrata-mcp status exited non-zero: $out"
  fi
  case "$out" in
  *"daemon: listening"*"answering"*) ok daemon ;;
  *) fail daemon "daemon not answering (neurostrata-mcp status)" ;;
  esac
}

check_guards() {
  local out n
  if ! out=$(neurostrata-mcp list guard 2>&1); then
    fail guards "neurostrata-mcp list guard failed: $out"
  fi
  # Count actual guard_rule entries, not total memories in the namespace
  n=$(printf '%s\n' "$out" | grep -c "guard_rule" || true)
  [ "$n" -ge 3 ] || fail guards "only $n guard_rule entries found, need >= 3"
  printf '%s\n' "$out" | grep -q "Destructive GitHub actions" ||
    fail guards "destructive-actions guard rule missing"
  ok guards
}

check_gh_auth() {
  gh auth status >/dev/null 2>&1 || fail gh-auth "gh auth status failed"
  ok gh-auth
}

self_test() {
  local gate real_nsmcp fails
  gate="$0"
  fails=0
  real_nsmcp=$(command -v neurostrata-mcp)
  # NB: stubdir is intentionally global (not local) so the EXIT trap can
  # still see it under `set -u` after this function returns.
  stubdir=$(mktemp -d)
  trap 'rm -rf "$stubdir"' EXIT

  # Fake neurostrata-mcp: STUB_CASE selects the failure mode; anything else
  # delegates to the real binary (so the gh-auth-fail case runs real checks).
  cat >"$stubdir/neurostrata-mcp" <<EOF
#!/usr/bin/env bash
case "\${STUB_CASE:-}" in
  daemon-down) echo "daemon: not running" ;;
  zero-guards)
    if [ "\$1" = "status" ]; then echo "daemon: listening on 127.0.0.1:34343, answering"
    else echo "Found 0 memories in namespace 'guard':"; fi ;;
  missing-rule)
    if [ "\$1" = "status" ]; then echo "daemon: listening on 127.0.0.1:34343, answering"
    else printf "Found 3 memories in namespace 'guard':\n\n--- ID: x ---\nType: guard_rule\nContent: some other rule\n"; fi ;;
  *) exec "$real_nsmcp" "\$@" ;;
esac
EOF
  cat >"$stubdir/gh" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
  chmod +x "$stubdir/neurostrata-mcp" "$stubdir/gh"

  expect_fail() { # $1 = STUB_CASE value (empty = unset), $2 = case label
    if [ -n "$1" ]; then
      if STUB_CASE="$1" PATH="$stubdir:$PATH" bash "$gate" >/dev/null 2>&1; then
        echo "SELF-TEST: $2 FAIL: gate exited 0, expected non-zero"
        fails=$((fails + 1))
      else
        echo "SELF-TEST: $2 ok"
      fi
    else
      if PATH="$stubdir:$PATH" bash "$gate" >/dev/null 2>&1; then
        echo "SELF-TEST: $2 FAIL: gate exited 0, expected non-zero"
        fails=$((fails + 1))
      else
        echo "SELF-TEST: $2 ok"
      fi
    fi
  }

  expect_fail daemon-down "daemon-down"
  expect_fail zero-guards "zero-guards"
  expect_fail missing-rule "missing-destructive-rule"
  expect_fail "" "gh-auth-fail"
  if bash "$gate" >/dev/null 2>&1; then
    echo "SELF-TEST: real-environment ok"
  else
    echo "SELF-TEST: real-environment FAIL: gate failed against the real environment"
    fails=$((fails + 1))
  fi
  return "$fails"
}

case "${1:-}" in
--self-test)
  rc=0
  self_test || rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "SELF-TEST: $rc assertion(s) failed"
    exit 1
  fi
  echo "SELF-TEST: all ok"
  ;;
"")
  check_binaries
  check_daemon
  check_guards
  check_gh_auth
  ;;
*)
  echo "usage: $0 [--self-test]" >&2
  exit 2
  ;;
esac
