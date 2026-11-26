#!/usr/bin/env bash
# deploy-watchdog.sh: deploy the canonical watchdog to the live path, with
# drift detection, a rollback backup, and a receipt.
#
# The canonical source is always ops/bin/watchdog-backup.sh in the repo this
# script lives in. There is no flag to deploy anything else. The deployed copy
# is DEPLOY_TARGET (default ~/workspace/neurostrata/bin/watchdog-backup.sh).
#
# Usage:
#   ops/bin/deploy-watchdog.sh --check
#       Compare SHA-256 of source and target. Exit 0 when they match, exit 1
#       on drift or when the target is missing. Writes nothing.
#   ops/bin/deploy-watchdog.sh --dry-run
#       Show what --apply would do. Writes nothing. Exit 0.
#   ops/bin/deploy-watchdog.sh --apply [--skip-tests]
#       Run `bash -n` on the source and the behavioral suite
#       (ops/tests/test_watchdog_ops.sh), then deploy. A drifted target is
#       first saved as <target>.bak.<UTC timestamp>. The new file is written
#       to a temp file beside the target, set to mode 755, hash-verified, and
#       moved into place with mv, so a watchdog run in progress keeps its old
#       inode and never reads a half-written script. Finally it writes
#       .watchdog-deploy-receipt.json beside the target (override with
#       DEPLOY_RECEIPT) holding the UTC time, the git commit of the source,
#       and the SHA-256. An in-sync target is a no-op, except that a missing
#       or stale receipt is repaired. Deploys are serialized with flock and
#       the target is rechecked immediately before the move. A DEPLOY_RECEIPT
#       that resolves to the target or the canonical source is refused.
#
# Rollback: copy the .bak.<UTC timestamp> file back over the target.
# Exit 2 is a usage error.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
SRC="$REPO/ops/bin/watchdog-backup.sh"
SUITE="$REPO/ops/tests/test_watchdog_ops.sh"
TARGET="${DEPLOY_TARGET:-$HOME/workspace/neurostrata/bin/watchdog-backup.sh}"
RECEIPT="${DEPLOY_RECEIPT:-$(dirname "$TARGET")/.watchdog-deploy-receipt.json}"

say() { echo "DEPLOY-WATCHDOG: $*"; }
die() {
  echo "DEPLOY-WATCHDOG: FAIL: $*" >&2
  exit 1
}
usage() {
  echo "usage: $0 --check | --dry-run | --apply [--skip-tests]" >&2
  exit 2
}

sha_of() { # portable SHA-256 of a file
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

json_escape() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }

check_clean_path() {
  # JSON cannot carry raw C0 control characters. Newline, carriage return and
  # tab are not the only ones; a vertical tab or escape byte would also make
  # the receipt invalid.
  case "$2" in
  *[[:cntrl:]]*) die "$1 contains control characters" ;;
  esac
}

# Absolute path with a resolved parent when the parent exists. Lexical
# fallback keeps the check working for a target directory not created yet.
normalize_path() {
  local p="$1" dir base
  case "$p" in
  /*) ;;
  *) p="$PWD/$p" ;;
  esac
  dir="${p%/*}"
  base="${p##*/}"
  [ -n "$dir" ] || dir=/
  if [ -d "$dir" ]; then
    dir="$(cd "$dir" && pwd -P)" || return 1
  fi
  printf '%s/%s\n' "$dir" "$base"
}

MODE=""
SKIP_TESTS=0
for arg in "$@"; do
  case "$arg" in
  --check | --dry-run | --apply)
    [ -z "$MODE" ] || usage
    MODE="${arg#--}"
    ;;
  --skip-tests) SKIP_TESTS=1 ;;
  *) usage ;;
  esac
done
[ -n "$MODE" ] || usage
if [ "$SKIP_TESTS" -eq 1 ] && [ "$MODE" != apply ]; then usage; fi

check_clean_path "DEPLOY_TARGET" "$TARGET"
check_clean_path "DEPLOY_RECEIPT" "$RECEIPT"
[ -f "$SRC" ] || die "canonical source not found: $SRC"
SRC_SHA="$(sha_of "$SRC")"

# The receipt is moved into place last. If it names the deployed script or the
# canonical source, that move would replace the watchdog (or corrupt the
# checkout) and the deploy could still report success.
SRC_KEY="$(normalize_path "$SRC")"
TARGET_KEY="$(normalize_path "$TARGET")"
RECEIPT_KEY="$(normalize_path "$RECEIPT")"
[ "$RECEIPT_KEY" != "$TARGET_KEY" ] ||
  die "DEPLOY_RECEIPT resolves to the deployment target: $RECEIPT"
[ "$RECEIPT_KEY" != "$SRC_KEY" ] ||
  die "DEPLOY_RECEIPT resolves to the canonical source: $RECEIPT"

compute_state() {
  # state: missing | in-sync | drift
  if [ -L "$TARGET" ]; then
    die "refusing to deploy over symlink: $TARGET"
  fi
  if [ ! -f "$TARGET" ]; then
    STATE=missing
    TARGET_SHA=""
  else
    TARGET_SHA="$(sha_of "$TARGET")"
    if [ "$TARGET_SHA" = "$SRC_SHA" ]; then STATE=in-sync; else STATE=drift; fi
  fi
}
compute_state

report_state() {
  case "$STATE" in
  missing) say "MISSING: no deployed watchdog at $TARGET (source sha256 $SRC_SHA)" ;;
  in-sync) say "IN SYNC: $TARGET matches ops/bin/watchdog-backup.sh (sha256 $SRC_SHA)" ;;
  drift)
    say "DRIFT: $TARGET differs from ops/bin/watchdog-backup.sh"
    say "  source   sha256 $SRC_SHA"
    say "  deployed sha256 $TARGET_SHA"
    ;;
  esac
}

backup_path() { # first free <target>.bak.<UTC timestamp>, never overwriting
  local base n candidate
  base="$TARGET.bak.$(date -u +%Y%m%dT%H%M%SZ)"
  candidate="$base"
  n=1
  while [ -e "$candidate" ]; do
    candidate="$base.$n"
    n=$((n + 1))
  done
  echo "$candidate"
}

compute_commit() {
  COMMIT="unknown"
  DIRTY=false
  if git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1; then
    COMMIT="$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)"
    if [ -n "$(git -C "$REPO" status --porcelain -- ops/bin/watchdog-backup.sh 2>/dev/null)" ]; then
      DIRTY=true
      say "WARNING: ops/bin/watchdog-backup.sh has uncommitted changes, the receipt records source_dirty=true"
    fi
  else
    say "WARNING: $REPO is not a git checkout, the receipt records git_commit=unknown"
  fi
}

receipt_is_current() {
  [ -s "$RECEIPT" ] || return 1
  grep -qF "\"sha256\": \"$SRC_SHA\"" "$RECEIPT" || return 1
  grep -qF "\"target\": \"$(json_escape "$TARGET")\"" "$RECEIPT" || return 1
}

write_receipt() {
  local rtmp
  rtmp="$(mktemp "$RECEIPT.tmp.XXXXXX")"
  trap 'rm -f "${TMP:-}" "$rtmp"' EXIT
  {
    echo "{"
    echo "  \"deployed_at_utc\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
    echo "  \"source\": \"ops/bin/watchdog-backup.sh\","
    echo "  \"git_commit\": \"$(json_escape "$COMMIT")\","
    echo "  \"source_dirty\": $DIRTY,"
    echo "  \"sha256\": \"$SRC_SHA\","
    echo "  \"target\": \"$(json_escape "$TARGET")\","
    echo "  \"backup\": \"$(json_escape "$BACKUP")\""
    echo "}"
  } >"$rtmp"
  chmod 644 "$rtmp"
  mv -f "$rtmp" "$RECEIPT"
  trap 'rm -f "${TMP:-}"' EXIT
}

case "$MODE" in
check)
  report_state
  [ "$STATE" = in-sync ]
  ;;

dry-run)
  report_state
  case "$STATE" in
  in-sync) say "would do nothing: target is already deployed" ;;
  missing) say "would deploy $SRC to $TARGET (first deploy, no backup)" ;;
  drift) say "would back up $TARGET to $TARGET.bak.<UTC timestamp> and deploy $SRC" ;;
  esac
  if [ "$STATE" != in-sync ]; then
    if [ "$SKIP_TESTS" -eq 1 ]; then
      say "would skip the behavioral suite"
    else
      say "would run bash -n and $SUITE first"
    fi
    say "would write receipt $RECEIPT"
  fi
  ;;

apply)
  report_state
  mkdir -p "$(dirname "$TARGET")" "$(dirname "$RECEIPT")"
  # Serialize concurrent deploys. flock is present on the Linux host this
  # targets; when it is absent (a macOS dev box) the deploy still works but
  # cannot be serialized, so say so rather than pretending.
  if command -v flock >/dev/null 2>&1; then
    exec 8>"$TARGET.lock"
    flock -n 8 || die "another deploy is in progress for $TARGET"
  else
    say "WARNING: flock not found, concurrent deploys are not serialized"
  fi
  compute_state

  compute_commit
  if [ "$STATE" = in-sync ]; then
    if receipt_is_current; then
      say "already deployed, nothing to do"
    else
      BACKUP=""
      write_receipt
      say "target is in sync but the receipt was missing or stale — repaired $RECEIPT"
    fi
    exit 0
  fi

  bash -n "$SRC" || die "bash -n failed on $SRC, nothing was deployed"
  if [ "$SKIP_TESTS" -eq 1 ]; then
    say "WARNING: --skip-tests, the behavioral suite was not run"
  else
    [ -x "$SUITE" ] || die "behavioral suite not found or not executable: $SUITE"
    say "running $SUITE"
    "$SUITE" || die "behavioral suite failed (check unshare privileges or stop a live daemon); nothing was deployed — do not use --skip-tests blindly"
  fi

  # Recompute target state after the behavioral suite finishes so a file
  # created or modified in the meantime is never overwritten without a backup.
  compute_state
  if [ "$STATE" = in-sync ]; then
    say "target is now in sync, nothing to do"
    exit 0
  fi

  BACKUP=""
  if [ "$STATE" = drift ]; then
    BACKUP="$(backup_path)"
    cp -p "$TARGET" "$BACKUP" || die "could not write rollback backup $BACKUP"
    say "rollback backup: $BACKUP"
  fi

  TMP="$(mktemp "$TARGET.tmp.XXXXXX")"
  trap 'rm -f "${TMP:-}"' EXIT
  cp "$SRC" "$TMP"
  chmod 755 "$TMP"
  [ "$(sha_of "$TMP")" = "$SRC_SHA" ] || die "staged copy does not match the source, nothing was deployed"
  # Recheck immediately before the move: if another writer changed the target
  # while this run staged the copy, overwriting it would lose that state.
  CURRENT_SHA=""
  if [ -f "$TARGET" ]; then CURRENT_SHA="$(sha_of "$TARGET")"; fi
  [ "$CURRENT_SHA" = "$TARGET_SHA" ] ||
    die "target changed during the deploy ($TARGET); refusing to overwrite (rollback backup: ${BACKUP:-none})"
  mv -f "$TMP" "$TARGET"
  [ "$(sha_of "$TARGET")" = "$SRC_SHA" ] || die "deployed file does not match the source after the move"

  write_receipt

  say "deployed $TARGET (sha256 $SRC_SHA, commit $COMMIT)"
  say "receipt: $RECEIPT"
  ;;
esac
