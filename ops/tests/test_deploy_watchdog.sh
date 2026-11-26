#!/usr/bin/env bash
# Issue #18: ops/bin/deploy-watchdog.sh gives the canonical watchdog a
# deployment process with drift detection, a rollback backup, and a receipt.
#
# The deploy script locates its source relative to itself, so every case runs
# a COPY of it inside a throwaway git repo (fixture) that also holds a copy of
# the canonical watchdog and a stub ops/tests/test_watchdog_ops.sh. Nothing
# here touches a real deployment: DEPLOY_TARGET always points into the temp
# dir, and HOME is redirected.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SB="$(mktemp -d)"
trap 'rm -rf "$SB"' EXIT
FAILURES=0

ok() { echo "ok - $*"; }
fail() {
  echo "FAIL - $*"
  FAILURES=$((FAILURES + 1))
}
t() { # t <description> <test args...>: ok when `[ <test args> ]` holds
  local desc="$1"
  shift
  if [ "$@" ]; then ok "$desc"; else fail "$desc (rc=${RC:-})"; fi
}
has() { # has <description> <needle>: ok when $OUT contains the needle
  case "$OUT" in *"$2"*) ok "$1" ;; *) fail "$1: output was: $OUT" ;; esac
}
sha() { # portable sha256 of a file
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

export HOME="$SB/home"
mkdir -p "$HOME"

# --- Fixture repo: copy of the deploy script + canonical watchdog + stub test. ---
FIX="$SB/repo"
mkdir -p "$FIX/ops/bin" "$FIX/ops/tests"
cp "$ROOT/ops/bin/deploy-watchdog.sh" "$FIX/ops/bin/deploy-watchdog.sh" 2>/dev/null || true
cp "$ROOT/ops/bin/watchdog-backup.sh" "$FIX/ops/bin/watchdog-backup.sh"
cat >"$FIX/ops/tests/test_watchdog_ops.sh" <<'EOF'
#!/usr/bin/env bash
# Stub of the behavioral suite: records that it ran, passes unless told not to.
echo ran >>"${STUB_TEST_MARKER:?}"
[ "${STUB_TEST_FAIL:-0}" = "1" ] && { echo "stub suite: FAIL" >&2; exit 1; }
exit 0
EOF
chmod +x "$FIX/ops/tests/test_watchdog_ops.sh"
(
  cd "$FIX" &&
    git init -q &&
    git add -A &&
    git -c user.name=test -c user.email=test@example.invalid commit -q -m fixture
)
FIX_COMMIT="$(git -C "$FIX" rev-parse HEAD)"
SRC="$FIX/ops/bin/watchdog-backup.sh"
DEPLOY="$FIX/ops/bin/deploy-watchdog.sh"
export STUB_TEST_MARKER="$SB/test-marker"

TARGET_DIR="$SB/live/bin"
export DEPLOY_TARGET="$TARGET_DIR/watchdog-backup.sh"
RECEIPT="$TARGET_DIR/.watchdog-deploy-receipt.json"

reset_target() {
  rm -rf "$SB/live"
  rm -f "$STUB_TEST_MARKER"
  unset STUB_TEST_FAIL
}
run() { # run <args...>
  OUT="$(bash "$DEPLOY" "$@" 2>&1)"
  RC=$?
}
baks() { find "$TARGET_DIR" -maxdepth 1 -name 'watchdog-backup.sh.bak.*' 2>/dev/null | wc -l | tr -d ' '; }
seed_drifted() {
  mkdir -p "$TARGET_DIR"
  printf '#!/usr/bin/env bash\n# an older deployed watchdog\nexit 0\n' >"$DEPLOY_TARGET"
  chmod 755 "$DEPLOY_TARGET"
}

echo "# case 1: --check on a missing target reports MISSING and fails"
reset_target
run --check
t "missing target exits non-zero" "$RC" -ne 0
has "missing target is named" "MISSING"

echo "# case 2: --check on a drifted target reports both hashes and fails"
reset_target
seed_drifted
run --check
t "drifted target exits non-zero" "$RC" -ne 0
has "drift is named" "DRIFT"
has "output carries the source sha256" "$(sha "$SRC")"
has "output carries the deployed sha256" "$(sha "$DEPLOY_TARGET")"

echo "# case 3: --dry-run changes nothing"
reset_target
seed_drifted
before="$(sha "$DEPLOY_TARGET")"
run --dry-run
t "--dry-run exits 0" "$RC" -eq 0
has "--dry-run says what it would do" "would"
t "--dry-run left the target untouched" "$(sha "$DEPLOY_TARGET")" = "$before"
t "--dry-run made no backup" "$(baks)" -eq 0
t "--dry-run wrote no receipt" "$(test -e "$RECEIPT" && echo yes || echo no)" = "no"
t "--dry-run ran no tests" "$(test -e "$STUB_TEST_MARKER" && echo yes || echo no)" = "no"

echo "# case 4: --apply deploys, backs up the drifted target, and writes a receipt"
reset_target
seed_drifted
old_sha="$(sha "$DEPLOY_TARGET")"
run --apply
t "--apply exits 0" "$RC" -eq 0
t "--apply ran the behavioral suite" "$(test -e "$STUB_TEST_MARKER" && echo yes || echo no)" = "yes"
t "target now equals the canonical source" "$(sha "$DEPLOY_TARGET")" = "$(sha "$SRC")"
t "target is mode 755" "$(stat -c '%a' "$DEPLOY_TARGET" 2>/dev/null || stat -f '%Lp' "$DEPLOY_TARGET")" = "755"
t "exactly one rollback backup exists" "$(baks)" -eq 1
bak="$(find "$TARGET_DIR" -maxdepth 1 -name 'watchdog-backup.sh.bak.*' | head -n 1)"
t "backup holds the previous deployed bytes" "$(sha "$bak")" = "$old_sha"
case "$bak" in *.bak.[0-9]*T[0-9]*Z*) ok "backup name carries a UTC timestamp" ;; *) fail "backup name carries a UTC timestamp: $bak" ;; esac
t "receipt exists" "$(test -s "$RECEIPT" && echo yes || echo no)" = "yes"
field() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$RECEIPT" "$1" 2>/dev/null; }
t "receipt sha256 matches the deployed file" "$(field sha256)" = "$(sha "$DEPLOY_TARGET")"
t "receipt git_commit is the fixture HEAD" "$(field git_commit)" = "$FIX_COMMIT"
case "$(field deployed_at_utc)" in [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z) ok "receipt carries a UTC timestamp" ;; *) fail "receipt carries a UTC timestamp: $(field deployed_at_utc)" ;; esac
t "receipt names the backup" "$(field backup)" = "$bak"
run --check
t "--check exits 0 after --apply" "$RC" -eq 0
has "--check reports in sync" "IN SYNC"

echo "# case 5: --apply on an in-sync target is a no-op"
receipt_before="$(cat "$RECEIPT")"
run --apply
t "in-sync --apply exits 0" "$RC" -eq 0
has "in-sync --apply says so" "already"
t "in-sync --apply made no new backup" "$(baks)" -eq 1
t "in-sync --apply left the receipt alone" "$(cat "$RECEIPT")" = "$receipt_before"

echo "# case 6: --apply creates a missing target without a backup"
reset_target
run --apply
t "--apply on a missing target exits 0" "$RC" -eq 0
t "missing target was created" "$(sha "$DEPLOY_TARGET")" = "$(sha "$SRC")"
t "no backup for a first deploy" "$(baks)" -eq 0
run --check
t "--check exits 0 after a first deploy" "$RC" -eq 0

echo "# case 7: a failing behavioral suite aborts the deploy"
reset_target
seed_drifted
before="$(sha "$DEPLOY_TARGET")"
STUB_TEST_FAIL=1 run --apply
t "failing suite exits non-zero" "$RC" -ne 0
t "failing suite left the target untouched" "$(sha "$DEPLOY_TARGET")" = "$before"
t "failing suite wrote no receipt" "$(test -e "$RECEIPT" && echo yes || echo no)" = "no"
rm -f "$STUB_TEST_MARKER"
STUB_TEST_FAIL=1 run --apply --skip-tests
t "--skip-tests deploys despite the failing suite" "$RC" -eq 0
t "--skip-tests did not run the suite" "$(test -e "$STUB_TEST_MARKER" && echo yes || echo no)" = "no"

echo "# case 8: a source that fails bash -n is never deployed"
reset_target
seed_drifted
before="$(sha "$DEPLOY_TARGET")"
cp "$SRC" "$SB/src.good"
printf 'if then fi (\n' >>"$SRC"
run --apply --skip-tests
t "syntax error exits non-zero" "$RC" -ne 0
has "syntax error is named" "bash -n"
t "syntax error left the target untouched" "$(sha "$DEPLOY_TARGET")" = "$before"
cp "$SB/src.good" "$SRC"

echo "# case 9: usage errors"
run
t "no mode exits 2" "$RC" -eq 2
run --bogus
t "unknown mode exits 2" "$RC" -eq 2
run --check --skip-tests
t "--skip-tests without --apply exits 2" "$RC" -eq 2

echo "# case 10: the real canonical source passes the real script's checks"
RC=0
OUT="$(DEPLOY_TARGET="$SB/real-target/watchdog-backup.sh" bash "$ROOT/ops/bin/deploy-watchdog.sh" --dry-run 2>&1)" || RC=$?
t "dry-run from the real repo exits 0" "$RC" -eq 0

echo "# case 11: symlink target refused and missing custom receipt dir created"
reset_target
mkdir -p "$(dirname "$DEPLOY_TARGET")"
ln -s "$SB/elsewhere" "$DEPLOY_TARGET"
run --apply --skip-tests
t "symlink target refused with non-zero" "$RC" -ne 0
has "symlink refusal named" "symlink"
rm -f "$DEPLOY_TARGET"
DEPLOY_RECEIPT="$SB/nested/receipt-dir/custom.json" run --apply --skip-tests
t "missing custom receipt dir created and exits 0" "$RC" -eq 0
t "custom receipt written" "$(test -s "$SB/nested/receipt-dir/custom.json" && echo yes || echo no)" = "yes"

if [ "$FAILURES" -ne 0 ]; then
  echo "test_deploy_watchdog: $FAILURES failure(s)"
  exit 1
fi
echo "test_deploy_watchdog: ALL PASS"
