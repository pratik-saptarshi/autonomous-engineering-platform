#!/bin/sh
# Recorder hook: appends each payload verbatim as one line of <dir>/<harness>.jsonl,
# wrapped with the receive time. Always exits 0.
out="${HP_RECORD_OUT:-$HOME/hp-record}"
mkdir -p "$out" 2>/dev/null
ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
{ printf '{"harness":"%s","received":"%s","payload":' "$1" "$ts"; tr -d '\n\r'; printf '}\n'; } >> "$out/$1.jsonl" 2>/dev/null
exit 0
