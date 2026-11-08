#!/usr/bin/env bash
# test_package_oci.sh — behavioral tests for scripts/package-oci.sh.
#
# Pins the N5 contract: when neither docker nor podman is on PATH,
# package-oci.sh falls back to archiving a build context that a
# container-capable host can build from, so the archive must contain
# EVERY build-context input the Containerfile consumes. The input the
# fallback originally missed is scripts/package-vm.sh, which the
# Containerfile's builder stage invokes to generate the VM bundle;
# without it the archived context fails mid-build, after the Go build,
# on the receiving host.
#
# The fallback is forced HERMETICALLY via PATH shadowing: the script
# detects container tools with `command -v`, so running it under a
# shadow PATH holding only the coreutils it needs (tar, mkdir, gzip)
# takes the fallback deterministically even on hosts — and CI runners
# — where docker or podman is installed.
#
# Beyond the pinned input list, a DERIVED guard extracts every
# scripts/<path> the Containerfile references and requires each one
# in the archive, so the next script the Containerfile learns to
# invoke is covered without editing this test. If the derivation
# finds no references at all, the guard FAILS explicitly rather than
# passing vacuously on an empty set.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PACKAGE_OCI="$ROOT/scripts/package-oci.sh"
CONTAINERFILE="$ROOT/Containerfile"
SB="$(mktemp -d /tmp/test-package-oci.XXXXXX)"
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
# shellcheck disable=SC2329 # invoked indirectly via check "$@" below.
listing_has_entry() { # <path> — exact entry in the archive listing
  printf '%s\n' "$LISTING" | grep -qx "$1"
}
# shellcheck disable=SC2329 # invoked indirectly via check "$@" below.
listing_has_dir() { # <dir> — at least one entry under dir/
  printf '%s\n' "$LISTING" | grep -q "^$1/"
}

# --- Force the fallback: shadow PATH with only the needed coreutils. ---
SHADOW_BIN="$SB/bin"
mkdir -p "$SHADOW_BIN" "$SB/out"
for tool in tar mkdir gzip; do
  src="$(command -v "$tool")" || {
    echo "FATAL: cannot locate $tool on the real PATH" >&2
    exit 1
  }
  ln -sf "$src" "$SHADOW_BIN/$tool"
done
BASH_BIN="$(command -v bash)"

note "running the package-oci.sh fallback under a shadow PATH (sandbox $SB)"
RUN_LOG="$SB/fallback.log"
if (cd "$ROOT" && env -i PATH="$SHADOW_BIN" "$BASH_BIN" "$PACKAGE_OCI" "$SB/out" "aep:test-package-oci" >"$RUN_LOG" 2>&1); then
  ok "fallback runs without a container tool"
else
  fail "fallback runs without a container tool"
  sed 's/^/    /' "$RUN_LOG"
  echo "test_package_oci: cannot continue without the fallback archive (sandbox kept at $SB)"
  exit 1
fi
check "fallback engages because the shadow PATH hides docker/podman" \
  grep -q "Neither 'docker' nor 'podman' found" "$RUN_LOG"
ARCHIVE="$SB/out/aep-oci-context.tar.gz"
check "fallback produces the OCI context archive" test -f "$ARCHIVE"
LISTING="$(tar -tzf "$ARCHIVE")"

# --- Pinned inputs: everything the Containerfile build consumes. ---
for entry in Containerfile Dockerfile docker-compose.yml go.mod go.sum scripts/package-vm.sh; do
  check "archive contains $entry" listing_has_entry "$entry"
done
for dir in cmd internal; do
  check "archive contains $dir/" listing_has_dir "$dir"
done

# --- Derived guard: every scripts/ input the Containerfile names. ---
DERIVED="$(grep -oE 'scripts/[A-Za-z0-9._/-]+' "$CONTAINERFILE" | sort -u)"
if [ -z "$DERIVED" ]; then
  fail "Containerfile references at least one scripts/ input (derived guard found none)"
else
  while IFS= read -r ref; do
    check "archive contains Containerfile-referenced $ref" listing_has_entry "$ref"
  done <<<"$DERIVED"
fi

echo
if [ "$FAILURES" -eq 0 ]; then
  echo "test_package_oci: ALL PASS (sandbox $SB)"
  rm -rf "$SB"
  exit 0
fi
echo "test_package_oci: $FAILURES failure(s) (sandbox kept at $SB)"
exit 1
