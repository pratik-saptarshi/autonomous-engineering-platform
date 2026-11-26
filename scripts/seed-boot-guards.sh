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
# It fails loudly (exit 1) when neurostrata-mcp is missing or the daemon is
# not answering. It never starts the daemon: see docs/runbook.md, section
# "Start the daemon". Exit 2 is a usage error.
#
# The canonical wording is also documented in docs/runbook.md, section
# "Seed the guard namespace". Presence is decided by a short key phrase, so a
# rule worded differently on a long-lived host still counts and is not
# seeded a second time.
set -euo pipefail

# Same platform-standard locations as boot-gate.sh. They are appended so a
# caller-injected PATH (a test stub dir) keeps precedence.
export PATH="$PATH:$HOME/go/bin:$HOME/sdk/go/bin:$HOME/workspace/neurostrata/bin"

NSMCP="neurostrata-mcp"
MODE="seed"

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

require_daemon() {
  local out
  command -v "$NSMCP" >/dev/null 2>&1 ||
    fail "neurostrata-mcp not found in PATH (install: docs/runbook.md, section 'NeuroStrata engine')"
  out=$("$NSMCP" status 2>&1) ||
    fail "neurostrata-mcp status exited non-zero: $out"
  case "$out" in
  *"daemon: listening"*"answering"*) ;;
  *) fail "daemon not answering (start it first: docs/runbook.md, section 'Start the daemon')" ;;
  esac
}

list_guards() {
  "$NSMCP" list guard 2>&1 || fail "neurostrata-mcp list guard failed"
}

# Same test as boot-gate.sh check_guards: at least three guard_rule entries
# and the destructive-actions rule. Prints the problem and returns 1 if not.
gate_would_pass() { # $1 = list output
  local n
  n=$(printf '%s\n' "$1" | grep -c "guard_rule" || true)
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

case "${1:-}" in
"") ;;
--dry-run) MODE="dry-run" ;;
--check) MODE="check" ;;
*) usage ;;
esac
[ "$#" -le 1 ] || usage

require_daemon
current=$(list_guards)

i=0
while [ "$i" -lt "${#RULE_KEYS[@]}" ]; do
  key="${RULE_KEYS[$i]}"
  case "$current" in
  *"$key"*) echo "SEED-GUARDS: present: $key" ;;
  *)
    case "$MODE" in
    check) echo "SEED-GUARDS: missing: $key" ;;
    dry-run) echo "SEED-GUARDS: would seed: $key" ;;
    seed)
      if ! out=$("$NSMCP" add guard guard_rule "${RULE_TEXTS[$i]}" 2>&1); then
        fail "neurostrata-mcp add failed for '$key': $out"
      fi
      echo "SEED-GUARDS: seeded: $key"
      ;;
    esac
    ;;
  esac
  i=$((i + 1))
done

[ "$MODE" = "dry-run" ] && exit 0

# Verify against the daemon's own answer, not against what was just sent.
final=$(list_guards)
if gate_would_pass "$final"; then
  echo "SEED-GUARDS: guards ok: boot-gate check 3 would pass"
else
  exit 1
fi
