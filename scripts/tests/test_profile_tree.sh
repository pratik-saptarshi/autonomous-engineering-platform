#!/usr/bin/env bash
# test_profile_tree.sh — E14/E14b/E14c evals for scripts/profile-tree.sh.
#
# The wrapper is the operator entry point for the vendored renderer. These
# evals pin the three things an operator needs:
#
#   E14   run from scripts/, the wrapper walks up to the repository root that
#         holds reference/harness-profiler/plugin/libexec/hp.js and renders the
#         trace with it (a throwaway root proves it is not the caller's cwd);
#   E14b  with no node on PATH it stops with the actionable one-line message
#         "node 18+ required for profiling; install Node or skip" and a non-zero
#         exit — never a raw "command not found". A second, distinct assertion
#         covers a node that exists but cannot report a usable version, so the
#         presence check and the version probe each fail their own mutation;
#   E14c  --help documents both the root walk and the node requirement, and
#         works without node (help must not require the runtime it describes).
#
# The child tree carries a real (empty) .git directory so the pin's own
# projectDir() resolves the trace to the throwaway root, exactly as it does in
# the repository.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT/scripts/profile-tree.sh"
RENDERER="reference/harness-profiler/plugin/libexec/hp.js"
BASH_BIN="$(command -v bash)"
SB="$(mktemp -d "${TMPDIR:-/tmp}/test-profile-tree.XXXXXX")"
FAILURES=0
# Every assertion must run: the count is compared with EXPECTED_ASSERTIONS at
# the end, so deleting an eval block fails the run instead of printing a
# constant total over whatever is left.
CHECKED=0
EXPECTED_ASSERTIONS=7

trap 'rm -rf "$SB"' EXIT

note() { echo "# $*"; }
ok() {
  CHECKED=$((CHECKED + 1))
  echo "ok - $*"
}
fail() {
  CHECKED=$((CHECKED + 1))
  echo "FAIL - $*"
  FAILURES=$((FAILURES + 1))
}

# --- Child repository: wrapper + renderer + one inert trace. ---
CHILD="$SB/root"
mkdir -p "$CHILD/scripts" "$CHILD/reference/harness-profiler/plugin/libexec" \
  "$CHILD/.git" "$CHILD/.harness-profile"
cp "$SCRIPT" "$CHILD/scripts/profile-tree.sh"
cp "$ROOT/$RENDERER" "$CHILD/$RENDERER"
printf '%s\n' \
  '{"v":2,"at":"2026-01-01T00:00:00.000Z","session":"ses_eval_tree","agent":"main","tool":"Bash","name":"eval-call"}' \
  >"$CHILD/.harness-profile/ses_eval_tree.jsonl"

# --- E14: root discovery and renderer invocation from scripts/. ---
note "E14: from scripts/, walk up to $RENDERER and render the root trace"
out="$(cd "$CHILD/scripts" && env -u AEP_HARNESS_PROFILE_DIR "$BASH_BIN" ./profile-tree.sh tree --verbose 2>&1)"
status=$?
if [ "$status" -ne 0 ]; then
  fail "E14: wrapper exited $status from scripts/: $out"
elif ! grep -q 'eval-call' <<<"$out"; then
  fail "E14: renderer output has no trace content: $out"
elif grep -qi 'cannot find\|no such file\|not found' <<<"$out"; then
  fail "E14: wrapper did not resolve the renderer: $out"
else
  ok "E14: wrapper resolved the root renderer and rendered the trace"
fi

# A nested caller (scripts/ is where the eval runs; this is the "anywhere"
# claim in --help) resolves the same root rather than its own cwd.
out="$(cd "$CHILD/scripts" && env -u AEP_HARNESS_PROFILE_DIR "$BASH_BIN" "$CHILD/scripts/profile-tree.sh" tree --verbose 2>&1)"
status=$?
if [ "$status" -eq 0 ] && grep -q 'eval-call' <<<"$out"; then
  ok "E14: absolute invocation from scripts/ renders the same root trace"
else
  fail "E14: absolute invocation failed ($status): $out"
fi

# --- E14b: the node floor, once per guard. ---
# A node that exists but cannot report a version (`-v` exits 1) exercises the
# version probe; an empty PATH exercises the presence check. Expecting
# "found: unknown" in the first case and no "found:" in the second keeps the
# two guards distinguishable by mutation: deleting either one fails only its
# own assertion.
FAKE_BIN="$SB/fakebin"
mkdir -p "$FAKE_BIN"
printf '%s\n' '#!/bin/sh' 'exit 1' >"$FAKE_BIN/node"
chmod +x "$FAKE_BIN/node"

note "E14b: a node whose -v fails is rejected with the actionable message"
out="$(cd "$CHILD/scripts" && PATH="$FAKE_BIN" AEP_HARNESS_PROFILE_DIR='' "$BASH_BIN" ./profile-tree.sh tree 2>&1)"
status=$?
if [ "$status" -eq 0 ]; then
  fail "E14b: wrapper succeeded with a node that cannot report a version"
elif ! grep -q 'node 18+ required for profiling; install Node or skip' <<<"$out"; then
  fail "E14b: version probe message is not actionable: $out"
elif ! grep -q 'found: unknown' <<<"$out"; then
  fail "E14b: version probe did not name the unusable version: $out"
elif grep -qi 'command not found\|^sh: node\|^bash: node' <<<"$out"; then
  fail "E14b: raw shell traceback leaked: $out"
else
  ok "E14b: unusable node version named, exit $status, no traceback"
fi

note "E14b: PATH without node prints the actionable message and exits non-zero"
out="$(cd "$CHILD/scripts" && PATH=/nonexistent AEP_HARNESS_PROFILE_DIR='' "$BASH_BIN" ./profile-tree.sh tree 2>&1)"
status=$?
if [ "$status" -eq 0 ]; then
  fail "E14b: wrapper succeeded without node"
elif ! grep -q 'node 18+ required for profiling; install Node or skip' <<<"$out"; then
  fail "E14b: message is not actionable: $out"
elif grep -q 'found:' <<<"$out"; then
  # The presence check reports the missing binary, not an unknown version; a
  # "found:" suffix here means the version probe answered for a node that
  # is not on PATH.
  fail "E14b: no-node path went through the version probe: $out"
elif grep -qi 'command not found\|^sh: node\|^bash: node' <<<"$out"; then
  fail "E14b: raw shell traceback leaked: $out"
else
  ok "E14b: actionable message, exit $status, no traceback"
fi

# --- E14c: --help documents root discovery and the node floor. ---
note "E14c: --help documents the root walk and node 18+ without needing node"
out="$(cd "$CHILD/scripts" && PATH=/nonexistent "$BASH_BIN" ./profile-tree.sh --help 2>&1)"
status=$?
if [ "$status" -ne 0 ]; then
  fail "E14c: --help exited $status without node: $out"
elif ! grep -q "$RENDERER" <<<"$out"; then
  fail "E14c: --help does not name the renderer path it walks up for: $out"
elif ! grep -q 'node 18+ required' <<<"$out"; then
  fail "E14c: --help does not document the node requirement: $out"
elif ! grep -qi 'walk' <<<"$out"; then
  fail "E14c: --help does not document the root walk: $out"
else
  ok "E14c: --help documents root discovery and the node floor"
fi

# --- E14e: explicit destinations are honored exactly, or rejected by name. ---
# hp.js projectDir() resolves the project as gitRoot(CLAUDE_PROJECT_DIR) || dir,
# so a destination inside a git work tree is silently re-read from that
# repository's root .harness-profile. The wrapper must reject it with the
# reason rather than render a different directory, and must honor an override
# outside any work tree down to the exact directory.
note "E14e: an in-repo explicit destination is rejected, not silently mis-rendered"
mkdir -p "$CHILD/nested/.harness-profile"
printf '%s\n' \
  '{"v":2,"at":"2026-01-01T00:00:00.000Z","session":"ses_eval_nested","agent":"main","tool":"Bash","name":"nested-call"}' \
  >"$CHILD/nested/.harness-profile/ses_eval_nested.jsonl"
out="$(cd "$CHILD/scripts" && AEP_HARNESS_PROFILE_DIR="$CHILD/nested/.harness-profile" "$BASH_BIN" ./profile-tree.sh tree --verbose 2>&1)"
status=$?
if [ "$status" -eq 0 ]; then
  fail "E14e: an in-repo destination was accepted: $out"
elif ! grep -q 'inside a git work tree' <<<"$out"; then
  fail "E14e: the rejection does not name the reason: $out"
elif ! grep -q 'Unset it to use' <<<"$out"; then
  fail "E14e: the rejection does not name both remedies: $out"
elif grep -q 'eval-call\|nested-call' <<<"$out"; then
  fail "E14e: the wrapper rendered a different directory instead of refusing: $out"
else
  ok "E14e: in-repo destination rejected with reason and remedies, exit $status"
fi

note "E14e: an override outside any work tree is rendered exactly"
mkdir -p "$SB/external/project/.harness-profile"
printf '%s\n' \
  '{"v":2,"at":"2026-01-01T00:00:00.000Z","session":"ses_eval_external","agent":"main","tool":"Bash","name":"external-call"}' \
  >"$SB/external/project/.harness-profile/ses_eval_external.jsonl"
out="$(cd "$CHILD/scripts" && AEP_HARNESS_PROFILE_DIR="$SB/external/project/.harness-profile" "$BASH_BIN" ./profile-tree.sh tree --verbose 2>&1)"
status=$?
if [ "$status" -ne 0 ]; then
  fail "E14e: the external override was rejected: $out"
elif ! grep -q 'external-call' <<<"$out"; then
  fail "E14e: the external override was not rendered exactly: $out"
elif grep -q 'eval-call' <<<"$out"; then
  fail "E14e: the wrapper rendered the repository default instead of the override: $out"
else
  ok "E14e: external override honored down to the exact directory"
fi

if [ "$CHECKED" -ne "$EXPECTED_ASSERTIONS" ]; then
  FAILURES=$((FAILURES + 1))
  echo "FAIL - expected $EXPECTED_ASSERTIONS assertions, ran $CHECKED (an eval block is missing)"
fi

echo "# $CHECKED/$EXPECTED_ASSERTIONS assertions checked, $FAILURES failure(s)"
[ "$FAILURES" -eq 0 ]
