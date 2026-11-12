#!/usr/bin/env bash
# test_makefile.sh — freshness tests for the Makefile's output targets.
#
# Pins the N6 contract (the F5 staleness class): an output target must
# declare prerequisites covering its REAL inputs, or once its output
# exists it never rebuilds and silently ships stale artifacts. F5
# fixed the four dist/bin targets; the dist/vm bundle targets and
# dist/oci shipped without that audit — dist/oci declared no
# prerequisites at all, and the dist/vm targets omitted
# scripts/package-vm.sh even though every bundle file except the
# binary is a heredoc inside that script.
#
# Method: build a skeleton tree around the REAL Makefile with stub
# inputs and outputs at controlled mtimes, then probe with `make -n`
# dry runs. Every probe resets all mtimes first, so a pass is
# attributable to the single probed input: control probes require NO
# recipe when every input is older than the output, and trigger probes
# touch exactly one input newest and require the target's recipe line.
# Dockerfile is a plain stub file here (in the repo it is a symlink to
# Containerfile) so its mtime can be probed independently. Dry runs
# only: no Go build, no container tool. A probe whose dry run cannot
# execute FAILS — it never skips silently.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SB="$(mktemp -d /tmp/test-makefile.XXXXXX)"
FAILURES=0

note() { echo "# $*"; }
ok() { echo "ok - $*"; }
fail() {
  echo "FAIL - $*"
  FAILURES=$((FAILURES + 1))
}

# --- Skeleton: real Makefile + stub inputs/outputs. ---
mkdir -p "$SB/cmd/aep" "$SB/internal/probe" "$SB/scripts" \
  "$SB/dist/bin" "$SB/dist/vm/linux-amd64" "$SB/dist/vm/linux-arm64" \
  "$SB/dist/oci"
cp "$ROOT/Makefile" "$SB/Makefile"
cp "$ROOT/scripts/package-vm.sh" "$ROOT/scripts/package-oci.sh" "$SB/scripts/"
touch "$SB/cmd/aep/main.go" "$SB/internal/probe/probe.go" \
  "$SB/go.mod" "$SB/go.sum" "$SB/Containerfile" "$SB/Dockerfile" \
  "$SB/docker-compose.yml"
touch "$SB/dist/bin/aep-linux-amd64" "$SB/dist/bin/aep-linux-arm64" \
  "$SB/dist/bin/aep-darwin-arm64" "$SB/dist/bin/aep-darwin-amd64"

# Controlled mtimes: inputs oldest, binary stubs mid (newer than the
# Go inputs, older than the outputs), outputs newer still, and the one
# probed input newest of all.
T_INPUT='2020-01-01 00:00:00'
T_BINARY='2020-01-01 12:00:00'
T_OUTPUT='2020-01-02 00:00:00'
T_NEWEST='2020-01-03 00:00:00'
INPUTS=(cmd/aep/main.go internal/probe/probe.go go.mod go.sum
  Containerfile Dockerfile docker-compose.yml
  scripts/package-vm.sh scripts/package-oci.sh)
BINARIES=(dist/bin/aep-linux-amd64 dist/bin/aep-linux-arm64
  dist/bin/aep-darwin-arm64 dist/bin/aep-darwin-amd64)
OUTPUT_DIRS=(dist/vm/linux-amd64 dist/vm/linux-arm64 dist/oci)

reset_skeleton() {
  local f
  for f in "${INPUTS[@]}"; do touch -d "$T_INPUT" "$SB/$f"; done
  for f in "${BINARIES[@]}"; do touch -d "$T_BINARY" "$SB/$f"; done
  for f in "${OUTPUT_DIRS[@]}"; do touch -d "$T_OUTPUT" "$SB/$f"; done
}

dry_run() { # dry_run <make-target> — `make -n` output for the skeleton
  (cd "$SB" && make -n "$1" 2>/dev/null)
}

probe_quiet() { # probe_quiet <label> <target> <marker>
  local label="$1" target="$2" marker="$3"
  reset_skeleton
  local out
  if ! out="$(dry_run "$target")"; then
    fail "$label (make -n $target could not run)"
    return
  fi
  if printf '%s\n' "$out" | grep -q -- "$marker"; then
    fail "$label"
  else
    ok "$label"
  fi
}

probe_triggers() { # probe_triggers <label> <file> <target> <marker>
  local label="$1" file="$2" target="$3" marker="$4"
  reset_skeleton
  touch -d "$T_NEWEST" "$SB/$file"
  local out
  if ! out="$(dry_run "$target")"; then
    fail "$label (make -n $target could not run)"
    return
  fi
  if printf '%s\n' "$out" | grep -q -- "$marker"; then
    ok "$label"
  else
    fail "$label"
  fi
}

note "dist/oci freshness (sandbox $SB)"
probe_quiet "oci: up to date when every input is older than dist/oci" \
  oci 'package-oci.sh'
probe_triggers "oci: rebuilds when a Go source under cmd/ changes" \
  cmd/aep/main.go oci 'package-oci.sh'
probe_triggers "oci: rebuilds when a Go source under internal/ changes" \
  internal/probe/probe.go oci 'package-oci.sh'
probe_triggers "oci: rebuilds when go.mod changes" \
  go.mod oci 'package-oci.sh'
probe_triggers "oci: rebuilds when go.sum changes" \
  go.sum oci 'package-oci.sh'
probe_triggers "oci: rebuilds when Containerfile changes" \
  Containerfile oci 'package-oci.sh'
probe_triggers "oci: rebuilds when Dockerfile changes" \
  Dockerfile oci 'package-oci.sh'
probe_triggers "oci: rebuilds when docker-compose.yml changes" \
  docker-compose.yml oci 'package-oci.sh'
probe_triggers "oci: rebuilds when scripts/package-oci.sh changes" \
  scripts/package-oci.sh oci 'package-oci.sh'
probe_triggers "oci: rebuilds when scripts/package-vm.sh changes" \
  scripts/package-vm.sh oci 'package-oci.sh'

note "dist/vm freshness"
probe_quiet "vm: up to date when binary and script are older than the bundle dirs" \
  vm 'package-vm.sh linux'
probe_triggers "vm/linux-amd64: rebuilds when scripts/package-vm.sh changes" \
  scripts/package-vm.sh dist/vm/linux-amd64 'package-vm.sh linux amd64'
probe_triggers "vm/linux-arm64: rebuilds when scripts/package-vm.sh changes" \
  scripts/package-vm.sh dist/vm/linux-arm64 'package-vm.sh linux arm64'
probe_triggers "vm/linux-amd64: rebuilds when its binary changes" \
  dist/bin/aep-linux-amd64 dist/vm/linux-amd64 'package-vm.sh linux amd64'
probe_triggers "vm/linux-arm64: rebuilds when its binary changes" \
  dist/bin/aep-linux-arm64 dist/vm/linux-arm64 'package-vm.sh linux arm64'

echo
if [ "$FAILURES" -eq 0 ]; then
  echo "test_makefile: ALL PASS (sandbox $SB)"
  rm -rf "$SB"
  exit 0
fi
echo "test_makefile: $FAILURES failure(s) (sandbox kept at $SB)"
exit 1
