#!/bin/bash
# Pre-ingestion gate for agent skills.
# Usage: scan-gate.sh <skill-dir-or-file>
# Exits 0 (allow) when score <= 50 AND no HIGH/CRITICAL findings.
# Exits 1 (block) otherwise, or on scan error (fail closed).
set -u
BIN="$HOME/workspace/skillspector/venv/bin/skillspector"
TARGET="${1:?usage: scan-gate.sh <skill-dir-or-file>}"

REPORT="$("$BIN" scan "$TARGET" --no-llm --format json 2>/dev/null)"
if [ -z "$REPORT" ]; then
  echo "GATE BLOCKED: skillspector scan failed or produced no output (fail closed)" >&2
  exit 1
fi

EVAL="$(echo "$REPORT" | python3 -c "
import json,sys
r = json.load(sys.stdin)
score = r['risk_assessment']['score']
sev = r['risk_assessment']['severity']
rec = r['risk_assessment']['recommendation']
bad = [i for i in r['issues'] if i['severity'] in ('HIGH','CRITICAL')]
print(f'score={score} severity={sev} recommendation={rec} high_critical={len(bad)}')
for i in bad:
    loc = i['location']; print(f\"  BLOCKER: {i['severity']} {i['id']} {loc['file']}:{loc['start_line']}\")
sys.exit(1 if (score > 50 or bad) else 0)
")"
RC=$?
echo "$EVAL"
if [ $RC -ne 0 ]; then
  echo "GATE BLOCKED: see findings above" >&2
  exit 1
fi
echo "GATE PASSED"
