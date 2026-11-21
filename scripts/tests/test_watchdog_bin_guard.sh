#!/usr/bin/env bash
# Issue #15: the backup script must fail loudly when its daemon binary is
# missing, instead of silently taking the "daemon idle" branch and exiting 0.
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$HERE/watchdog-backup.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# A fixture HOME with no neurostrata-mcp binary anywhere.
export HOME="$TMP/home"
mkdir -p "$HOME/workspace/neurostrata" "$HOME/.config/NeuroStrata/data/db" "$TMP/bin"
printf 'v1' >"$HOME/.config/NeuroStrata/data/db/ladybug.db"
# Stub the concurrency guard (not flock-free on every host) and the poll sleep.
printf '#!/bin/sh\nexit 0\n' >"$TMP/bin/flock"
printf '#!/bin/sh\nexit 0\n' >"$TMP/bin/sleep"
chmod +x "$TMP/bin/flock" "$TMP/bin/sleep"
export PATH="$TMP/bin:$PATH"

set +e
out="$(bash "$SCRIPT" 2>&1)"
rc=$?
set -e

if [ "$rc" -eq 0 ]; then
  echo "FAIL: missing binary produced a silent exit 0 (output: $out)" >&2
  exit 1
fi
if ! printf '%s' "$out" | grep -q 'FATAL'; then
  echo "FAIL: missing binary did not emit a FATAL line (output: $out)" >&2
  exit 1
fi
echo "PASS: missing BIN fails fast with FATAL (rc=$rc)"
