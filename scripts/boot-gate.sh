#!/usr/bin/env bash
# boot-gate.sh — fail-closed preflight for autonomous runs.
#
# Asserts the environment is in a known-good state before an autonomous
# session (cron job, agent run) does any real work:
#   1. binaries  — required CLIs are on PATH
#   2. daemon    — the NeuroStrata daemon is answering
#   3. guards    — the guard namespace holds the standing guard rules
#   4. gh-auth   — the GitHub CLI is authenticated
#   5. policy    — the policy data matches the committed version (read-only:
#                  it creates, copies, and freezes nothing; the committed
#                  git blob is the policy)
#
# Contract: prints "BOOT-GATE: <name> ok" per passing check; on the first
# failure prints "BOOT-GATE: <name> FAIL: <reason>" and exits 1 immediately.
# It never warns-and-continues. The policy check additionally prints
# "BOOT-GATE: policy SKIP: <reason>" and proceeds when no policy data is
# present: a SKIP means the mechanism is not installed here, not that it
# passed, so it never prints "ok" for a check that did not run. The policy
# check's ok line names the resolved path and short digest, and the check
# ends with a machine-readable token line — "BOOT-GATE-RESULT: POLICY-OK"
# on a pass, "BOOT-GATE-RESULT: POLICY-INACTIVE" on a SKIP — so exit-code
# consumers can distinguish a passed policy check from an inactive one
# (both exit 0; the exit contract itself is unchanged).
# Scope: this wires the policy check into boot-gate.sh only. Whether and
# when anything invokes boot-gate.sh is issue #17's unexecuted scope.
# Run with --self-test to execute the stub-based negative tests
# (each prints "SELF-TEST: <case> ok").
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

check_policy() {
  local gate_dir policy ref_sha work_sha
  gate_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  policy="${AEP_POLICY_DATA:-$gate_dir/policy.data}"
  if [ ! -f "$policy" ]; then
    echo "BOOT-GATE: policy SKIP: no policy data at $policy (launch-policy integrity inactive)"
    echo "BOOT-GATE-RESULT: POLICY-INACTIVE"
    return 0
  fi
  # The blob streams straight into sha256sum (no intermediate variable, so
  # no trailing-newline stripping — the hash is byte-exact). The `|| fail`
  # guard is load-bearing: under `set -euo pipefail` a bare assignment whose
  # pipeline fails would terminate the script silently before any FAIL line.
  ref_sha=$(git -C "$gate_dir" show HEAD:scripts/policy.data 2>/dev/null | sha256sum | cut -d' ' -f1) ||
    fail policy "cannot read committed scripts/policy.data via git"
  work_sha=$(sha256sum "$policy" | cut -d' ' -f1)
  [ "$work_sha" = "$ref_sha" ] ||
    fail policy "policy.data differs from the committed version (unreviewed edit?) — policy changes land via git/PR"
  echo "BOOT-GATE: policy ok: $policy (sha256 ${work_sha:0:12})"
  echo "BOOT-GATE-RESULT: POLICY-OK"
}

self_test() {
  local gate real_nsmcp fails gate_dir policy_out policy_rc same_sha
  gate="$0"
  fails=0
  gate_dir="$(cd "$(dirname "$gate")" && pwd)"
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
  # policy cases run the gate WITHOUT the stubdir on PATH, so the real
  # binaries serve the first four checks and the run reaches policy; both
  # assert on captured output, not exit code alone.
  cp "$gate_dir/policy.data" "$stubdir/policy-extra.data"
  printf '%s\n' '*/extra-pattern' >>"$stubdir/policy-extra.data"
  policy_out=$(AEP_POLICY_DATA="$stubdir/policy-extra.data" bash "$gate" 2>&1) && policy_rc=0 || policy_rc=$?
  if [ "$policy_rc" -ne 0 ] && printf '%s\n' "$policy_out" | grep -q "BOOT-GATE: policy FAIL:"; then
    echo "SELF-TEST: policy-mismatch ok"
  else
    echo "SELF-TEST: policy-mismatch FAIL: expected non-zero exit with 'BOOT-GATE: policy FAIL:' (rc=$policy_rc)"
    printf '%s\n' "$policy_out"
    fails=$((fails + 1))
  fi
  policy_out=$(AEP_POLICY_DATA="$stubdir/no-such-policy.data" bash "$gate" 2>&1) && policy_rc=0 || policy_rc=$?
  if [ "$policy_rc" -eq 0 ] && printf '%s\n' "$policy_out" | grep -q "BOOT-GATE: policy SKIP:" &&
    printf '%s\n' "$policy_out" | grep -q "^BOOT-GATE-RESULT: POLICY-INACTIVE$"; then
    echo "SELF-TEST: policy-skip ok"
  else
    echo "SELF-TEST: policy-skip FAIL: expected exit 0 with 'BOOT-GATE: policy SKIP:' and the POLICY-INACTIVE token (rc=$policy_rc)"
    printf '%s\n' "$policy_out"
    fails=$((fails + 1))
  fi
  # policy-token-ok: a byte-identical copy of the committed policy,
  # passed via the override, passes the check; the ok line names the
  # resolved path + short digest and the run ends with the POLICY-OK
  # token, so exit-code consumers can distinguish pass from SKIP.
  cp "$gate_dir/policy.data" "$stubdir/policy-same.data"
  policy_out=$(AEP_POLICY_DATA="$stubdir/policy-same.data" bash "$gate" 2>&1) && policy_rc=0 || policy_rc=$?
  same_sha=$(sha256sum "$stubdir/policy-same.data" | cut -d' ' -f1)
  if [ "$policy_rc" -eq 0 ] &&
    printf '%s\n' "$policy_out" | grep -qF "BOOT-GATE: policy ok: $stubdir/policy-same.data (sha256 ${same_sha:0:12})" &&
    printf '%s\n' "$policy_out" | grep -q "^BOOT-GATE-RESULT: POLICY-OK$"; then
    echo "SELF-TEST: policy-token-ok ok"
  else
    echo "SELF-TEST: policy-token-ok FAIL: expected exit 0 with the path+digest ok line and the POLICY-OK token (rc=$policy_rc)"
    printf '%s\n' "$policy_out"
    fails=$((fails + 1))
  fi
  # policy-unreadable: a fixture copy of the gate outside any git repo, so
  # `git show HEAD:scripts/policy.data` fails deterministically; the gate
  # must fail closed WITH the contracted FAIL line, not silently.
  mkdir -p "$stubdir/fixture"
  cp "$gate" "$stubdir/fixture/boot-gate.sh"
  cp "$gate_dir/policy.data" "$stubdir/fixture/policy.data"
  policy_out=$(bash "$stubdir/fixture/boot-gate.sh" 2>&1) && policy_rc=0 || policy_rc=$?
  if [ "$policy_rc" -ne 0 ] && printf '%s\n' "$policy_out" | grep -q "BOOT-GATE: policy FAIL: cannot read committed scripts/policy.data via git"; then
    echo "SELF-TEST: policy-unreadable ok"
  else
    echo "SELF-TEST: policy-unreadable FAIL: expected non-zero exit with 'BOOT-GATE: policy FAIL: cannot read committed scripts/policy.data via git' (rc=$policy_rc)"
    printf '%s\n' "$policy_out"
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
  check_policy
  ;;
*)
  echo "usage: $0 [--self-test]" >&2
  exit 2
  ;;
esac
