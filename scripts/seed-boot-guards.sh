#!/usr/bin/env bash
# seed-boot-guards.sh: seed the NeuroStrata `guard` namespace so that
# scripts/boot-gate.sh check 3 (guards) can pass on a fresh host.
#
# boot-gate.sh needs at least three guard_rule memories in the `guard`
# namespace, and one of them must contain "Destructive GitHub actions".
# This script adds any canonical rule that is absent and leaves the rest
# alone, so it is safe to run again and never creates duplicates.
#
# Usage:
#   scripts/seed-boot-guards.sh [--dry-run | --check]
#     (no flag)  seed every canonical rule that is absent
#     --dry-run  report what would be seeded and write nothing
#     --check    run the same test as boot-gate.sh check 3, write nothing,
#                exit 1 when it would fail
#
# NeuroStrata's store has a single-writer lock: `neurostrata-mcp add` is a
# direct mutation and only works while no daemon holds the store. If a daemon
# is answering, this script stops it with `neurostrata-mcp shutdown`, seeds,
# verifies against the store, and restarts it with the runbook's nohup command
# (unless it was already stopped, in which case it is left stopped). An
# EXIT trap restarts it even when a seed fails. It never leaves a running
# daemon stopped. Exit 2 is a usage error.
#
# The canonical wording is also documented in docs/runbook.md, section
# "Seed the guard namespace". Presence is decided by a short key phrase inside
# an actual guard_rule record, so an ordinary memory that merely mentions the
# phrase does not count and the rule is still seeded.
set -euo pipefail

# Same platform-standard locations as boot-gate.sh. They are appended so a
# caller-injected PATH (a test stub dir) keeps precedence.
export PATH="$PATH:$HOME/go/bin:$HOME/sdk/go/bin:$HOME/workspace/neurostrata/bin"

NSMCP="neurostrata-mcp"
MODE="seed"
NS_DIR="${NEUROSTRATA_HOME:-$HOME/workspace/neurostrata}"
LOCK_FILE="$NS_DIR/.seed-guards.lock"
LOCK_DIR=""
STOPPED_DAEMON=0

RULE_KEYS=(
  "Destructive GitHub actions"
  "never push without the user's explicit authorization"
  "Merging a PR: default requires"
)
RULE_TEXTS=(
  "Destructive GitHub actions (branch deletion, force-push, history rewrite, repository deletion) each require the user's explicit per-action authorization naming the exact target. Never bundle this permission into a general proceed or a compound question. Ask separately every time."
  "In the document-accessibility-pipeline repo, never push without the user's explicit authorization. Publishing goes only through scripts/source-publisher.sh publish. Leave repo-rule-gated changes as local commits or open PRs."
  "Merging a PR: default requires the user's explicit per-PR authorization. Independent review approved, CI green on the exact head, every review comment analyzed against current code and addressed. On repos under the user's auto-merge rule (2026-10-17, branch protection with required CI checks and required conversation resolution), the pipeline enables GitHub auto-merge (squash) instead, and GitHub merges only when CI is green and zero review threads are unresolved. Never merge directly on behalf of a reviewer and never bypass branch protection."
)

fail() { # $1 = reason
  echo "SEED-GUARDS: FAIL: $1" >&2
  exit 1
}

usage() {
  echo "usage: $0 [--dry-run | --check]" >&2
  exit 2
}

list_guards() {
  "$NSMCP" list guard 2>&1 || fail "neurostrata-mcp list guard failed"
}

# Print only the records whose Type line is exactly guard_rule. The list
# output separates records with "--- ID: ", and Content may be multi-line, so
# records are accumulated until the next ID line rather than split on blanks.
guard_records() { # $1 = list output
  printf '%s\n' "$1" | awk '
    function flush() {
      if (type == "guard_rule") { printf "%s", buf }
      buf = ""
      type = ""
    }
    /^--- ID: / { flush() }
    /^Type: / { t = $0; sub(/^Type: /, "", t); type = t }
    { buf = buf "\n" $0 }
    END { flush() }
  '
}

# Same test as boot-gate.sh check_guards: at least three guard_rule entries
# and the destructive-actions rule in one of those records. Prints the problem
# and returns 1 if not.
gate_would_pass() { # $1 = guard_rule records only
  local n
  n=$(printf '%s\n' "$1" | grep -c '^--- ID: ' || true)
  if [ "$n" -lt 3 ]; then
    echo "SEED-GUARDS: only $n guard_rule entries found, boot-gate needs >= 3"
    return 1
  fi
  case "$1" in
  *"Destructive GitHub actions"*) ;;
  *)
    echo "SEED-GUARDS: destructive-actions guard rule missing"
    return 1
    ;;
  esac
}

daemon_state() { # up | down | busy
  local rc=0
  "$NSMCP" status >/dev/null 2>&1 || rc=$?
  case "$rc" in
  0 | 3) echo up ;;
  1) echo down ;;
  *) echo busy ;;
  esac
}

acquire_lock() {
  mkdir -p "$NS_DIR" 2>/dev/null || fail "cannot create $NS_DIR"
  if command -v flock >/dev/null 2>&1; then
    exec 7>"$LOCK_FILE" || fail "cannot open $LOCK_FILE"
    flock -w 120 7 || fail "another seed-boot-guards run is still running"
  elif mkdir "$LOCK_FILE.d" 2>/dev/null; then
    LOCK_DIR="$LOCK_FILE.d"
  else
    fail "another seed-boot-guards run is in progress (or remove stale $LOCK_FILE.d)"
  fi
}

stop_daemon_for_write() {
  local st i
  st="$(daemon_state)"
  case "$st" in
  down) return 0 ;;
  busy) fail "daemon is starting or shutting down; retry when status settles" ;;
  esac
  echo "SEED-GUARDS: stopping daemon for the single-writer store lock"
  "$NSMCP" shutdown >/dev/null 2>&1 ||
    fail "neurostrata-mcp shutdown failed; nothing was seeded"
  STOPPED_DAEMON=1
  for i in $(seq 1 60); do
    [ "$(daemon_state)" = down ] && return 0
    sleep 1
  done
  fail "daemon did not stop within 60s; nothing was seeded"
}

restart_daemon() {
  [ "$STOPPED_DAEMON" = 1 ] || return 0
  mkdir -p "$NS_DIR" 2>/dev/null || true
  HF_HUB_OFFLINE=1 nohup "$NSMCP" daemon >>"$NS_DIR/daemon.log" 2>&1 &
  local i
  for i in $(seq 1 120); do
    if [ "$(daemon_state)" = up ]; then
      STOPPED_DAEMON=0
      echo "SEED-GUARDS: daemon restarted"
      return 0
    fi
    sleep 1
  done
  echo "SEED-GUARDS: WARNING: daemon did not answer within 120s; start it with:" >&2
  echo "  HF_HUB_OFFLINE=1 nohup neurostrata-mcp daemon >> $NS_DIR/daemon.log 2>&1 &" >&2
  return 1
}

on_exit() {
  local rc=$?
  trap - EXIT
  if ! restart_daemon; then
    [ "$rc" -eq 0 ] && rc=1
  fi
  if [ -n "$LOCK_DIR" ]; then rmdir "$LOCK_DIR" 2>/dev/null || true; fi
  exit "$rc"
}

case "${1:-}" in
"") ;;
--dry-run) MODE="dry-run" ;;
--check) MODE="check" ;;
*) usage ;;
esac
[ "$#" -le 1 ] || usage

command -v "$NSMCP" >/dev/null 2>&1 ||
  fail "neurostrata-mcp not found in PATH (install: docs/runbook.md, section 'NeuroStrata engine')"

if [ "$MODE" = seed ]; then
  acquire_lock
  trap on_exit EXIT
fi

current=$(list_guards)
records=$(guard_records "$current")

MISSING_KEYS=()
MISSING_TEXTS=()
i=0
while [ "$i" -lt "${#RULE_KEYS[@]}" ]; do
  key="${RULE_KEYS[$i]}"
  case "$records" in
  *"$key"*) echo "SEED-GUARDS: present: $key" ;;
  *)
    case "$MODE" in
    check) echo "SEED-GUARDS: missing: $key" ;;
    dry-run) echo "SEED-GUARDS: would seed: $key" ;;
    seed)
      MISSING_KEYS+=("$key")
      MISSING_TEXTS+=("${RULE_TEXTS[$i]}")
      ;;
    esac
    ;;
  esac
  i=$((i + 1))
done

case "$MODE" in
check)
  if gate_would_pass "$records"; then
    echo "SEED-GUARDS: guards ok: boot-gate check 3 would pass"
    exit 0
  fi
  exit 1
  ;;
dry-run)
  exit 0
  ;;
esac

if [ "${#MISSING_KEYS[@]}" -gt 0 ]; then
  stop_daemon_for_write
  i=0
  while [ "$i" -lt "${#MISSING_KEYS[@]}" ]; do
    if ! out=$("$NSMCP" add guard guard_rule "${MISSING_TEXTS[$i]}" 2>&1); then
      fail "neurostrata-mcp add failed for '${MISSING_KEYS[$i]}': $out"
    fi
    echo "SEED-GUARDS: seeded: ${MISSING_KEYS[$i]}"
    i=$((i + 1))
  done
fi

# Verify against the store's own answer, not against what was just sent.
final=$(list_guards)
if gate_would_pass "$(guard_records "$final")"; then
  echo "SEED-GUARDS: guards ok: boot-gate check 3 would pass"
else
  exit 1
fi
