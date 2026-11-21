#!/usr/bin/env bash
# Fixture tests for scripts/vendor_sync.sh — local git repos, no network.
set -euo pipefail

SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/vendor_sync.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git config --global user.email 2>/dev/null || true
export GIT_AUTHOR_NAME=Test GIT_AUTHOR_EMAIL=test@example.invalid
export GIT_COMMITTER_NAME=Test GIT_COMMITTER_EMAIL=test@example.invalid

fail() {
  echo "FAIL: $*" >&2
  exit 1
}
pass() { echo "PASS: $*"; }

# ---------- fixture: upstream with mirror branch, fork with working branch ----------
mkdir -p "$TMP/upstream"
(cd "$TMP/upstream" && git init -q -b master)
UP="$TMP/upstream"
echo base >"$UP/README"
(cd "$UP" && git add . && git commit -qm base)
BASE_SHA=$(git -C "$UP" rev-parse HEAD)

git clone -q "$UP" "$TMP/fork"
FK="$TMP/fork"
(cd "$FK" && git checkout -qb develop)
echo 'filelock>=4.2.9' >"$FK/fork-remediation.txt"
(cd "$FK" && git add . && git commit -qm 'fork remediation')
FORK_ONLY=$(git -C "$FK" rev-parse HEAD)

# upstream advances
echo 'certifi>=2026.10.23' >"$UP/upstream-update.txt"
(cd "$UP" && git add . && git commit -qm 'upstream update')
UP_SHA=$(git -C "$UP" rev-parse HEAD)
(cd "$FK" && git remote add upstream "$UP" && git fetch -q upstream)

# ---------- test: forward merge preserves fork-only commit ----------
bash "$SCRIPT" merge-forward "$FK" upstream/master develop "merge upstream" >/dev/null
bash "$SCRIPT" assert-ancestors "$FK" develop "$FORK_ONLY" "$UP_SHA" >/dev/null &&
  pass "forward merge preserves fork-only and upstream commits" ||
  fail "forward merge lost a commit"
bash "$SCRIPT" assert-content "$FK" develop fork-remediation.txt 'filelock>=4.2.9' >/dev/null &&
  pass "remediation content survived" || fail "remediation content lost"
bash "$SCRIPT" assert-content "$FK" develop upstream-update.txt 'certifi>=2026.10.23' >/dev/null &&
  pass "upstream content present" || fail "upstream content missing"

# ---------- test: assert-content fails on downgrade ----------
if bash "$SCRIPT" assert-content "$FK" develop fork-remediation.txt 'filelock>=3.32.7' >/dev/null 2>&1; then
  fail "assert-content accepted a downgraded remediation"
else
  pass "assert-content rejects a missing/downgraded remediation"
fi

# ---------- test: assert-ancestors fails for a missing commit ----------
if bash "$SCRIPT" assert-ancestors "$FK" develop 0000000000000000000000000000000000000000 >/dev/null 2>&1; then
  fail "assert-ancestors accepted a non-ancestor"
else
  pass "assert-ancestors rejects a non-ancestor"
fi

# ---------- test: verify-sha ----------
bash "$SCRIPT" verify-sha "$UP_SHA" "$(git -C "$UP" rev-parse HEAD)" >/dev/null &&
  pass "verify-sha accepts matching SHA" || fail "verify-sha rejected a match"
if bash "$SCRIPT" verify-sha "$BASE_SHA" "$UP_SHA" >/dev/null 2>&1; then
  fail "verify-sha accepted a mismatch"
else
  pass "verify-sha rejects a mismatch"
fi

# ---------- test: mirror fast-forward ----------
bash "$SCRIPT" mirror-ff "$FK" master upstream/master >/dev/null
[ "$(git -C "$FK" rev-parse master)" = "$UP_SHA" ] &&
  pass "mirror fast-forward reaches upstream head" || fail "mirror FF failed"

# ---------- test: rollback-plan prints bundle + revert commands ----------
bash "$SCRIPT" rollback-plan esf master develop | grep -q 'pre-sync-esf-2026-11-19.bundle' &&
  pass "rollback-plan references the backup bundle" || fail "rollback-plan missing bundle"

# ---------- test: rollback-plan revert carries -m 1 (forward merges are --no-ff) ----------
bash "$SCRIPT" rollback-plan esf master develop | grep -q 'git revert --no-edit -m 1' &&
  pass "rollback-plan revert specifies -m 1 for the merge commit" ||
  fail "rollback-plan revert lacks -m 1 (git revert refuses a merge commit without it)"

# ---------- test: the printed revert actually undoes a forward merge ----------
MERGE_SHA=$(git -C "$FK" rev-parse develop)
git -C "$FK" checkout -q develop
git -C "$FK" revert --no-edit -m 1 "$MERGE_SHA" >/dev/null
if git -C "$FK" cat-file -e develop:upstream-update.txt 2>/dev/null; then
  fail "revert with -m 1 left the merged upstream file in place"
else
  pass "revert with -m 1 undoes the forward merge"
fi

# ---------- test: backup tags first, bundle second, so the bundle carries the tags ----------
BUNDLE="$TMP/pre-sync-esf-2026-11-19.bundle"
bash "$SCRIPT" backup "$FK" esf "$UP_SHA" "$FORK_ONLY" "$BUNDLE" >/dev/null ||
  fail "backup helper failed"
git clone -q --mirror "$BUNDLE" "$TMP/restore.git"
[ "$(git -C "$TMP/restore.git" rev-parse backup/pre-sync-esf-mirror)" = "$UP_SHA" ] &&
  pass "bundle clone resolves the mirror backup tag" || fail "mirror backup tag missing from bundle"
[ "$(git -C "$TMP/restore.git" rev-parse backup/pre-sync-esf-working)" = "$FORK_ONLY" ] &&
  pass "bundle clone resolves the working backup tag" || fail "working backup tag missing from bundle"

# ---------- test: backup with a relative bundle path from a foreign cwd ----------
mkdir -p "$TMP/foreign"
(cd "$TMP/foreign" && bash "$SCRIPT" backup "$FK" reltest "$UP_SHA" "$FORK_ONLY" "relative-backup.bundle" >/dev/null) ||
  fail "backup with a relative bundle path from a foreign cwd failed"
[ -f "$TMP/foreign/relative-backup.bundle" ] &&
  pass "relative bundle path resolves against the caller's cwd" ||
  fail "relative bundle not found at the caller-relative location"
git clone -q --mirror "$TMP/foreign/relative-backup.bundle" "$TMP/restore-relative.git"
[ "$(git -C "$TMP/restore-relative.git" rev-parse backup/pre-sync-reltest-mirror)" = "$UP_SHA" ] &&
  pass "relative-path bundle clone resolves the mirror backup tag" || fail "mirror backup tag missing from relative-path bundle"
[ "$(git -C "$TMP/restore-relative.git" rev-parse backup/pre-sync-reltest-working)" = "$FORK_ONLY" ] &&
  pass "relative-path bundle clone resolves the working backup tag" || fail "working backup tag missing from relative-path bundle"

# ---------- test: backup retry with the same arguments succeeds ----------
RETRY_BUNDLE="$TMP/retry.bundle"
bash "$SCRIPT" backup "$FK" retry "$UP_SHA" "$FORK_ONLY" "$RETRY_BUNDLE" >/dev/null ||
  fail "first backup run for the retry test failed"
bash "$SCRIPT" backup "$FK" retry "$UP_SHA" "$FORK_ONLY" "$RETRY_BUNDLE" >/dev/null &&
  pass "backup retry with the same arguments succeeds" || fail "backup retry failed on existing backup tags"
git clone -q --mirror "$RETRY_BUNDLE" "$TMP/restore-retry.git"
[ "$(git -C "$TMP/restore-retry.git" rev-parse backup/pre-sync-retry-mirror)" = "$UP_SHA" ] &&
  pass "retry bundle clone resolves the mirror backup tag" || fail "mirror backup tag missing from retry bundle"
[ "$(git -C "$TMP/restore-retry.git" rev-parse backup/pre-sync-retry-working)" = "$FORK_ONLY" ] &&
  pass "retry bundle clone resolves the working backup tag" || fail "working backup tag missing from retry bundle"

# ---------- test: backup fails when a backup tag points at a different commit ----------
git -C "$FK" tag "backup/pre-sync-conflict-mirror" "$BASE_SHA"
if conflict_out=$(bash "$SCRIPT" backup "$FK" conflict "$UP_SHA" "$FORK_ONLY" "$TMP/conflict.bundle" 2>&1); then
  fail "backup accepted a backup tag pointing at a different commit"
else
  pass "backup rejects a backup tag pointing at a different commit"
fi
grep -q "backup/pre-sync-conflict-mirror" <<<"$conflict_out" &&
  grep -qi "delete" <<<"$conflict_out" &&
  pass "backup tag conflict message names the tag and says to delete it manually" ||
  fail "backup tag conflict message does not name the tag or say to delete it manually: $conflict_out"
[ "$(git -C "$FK" rev-parse backup/pre-sync-conflict-mirror)" = "$BASE_SHA" ] &&
  pass "conflicting backup tag was not moved" || fail "conflicting backup tag was moved"

echo "ALL VENDOR SYNC TESTS PASSED"
