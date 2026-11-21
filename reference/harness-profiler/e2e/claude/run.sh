#!/bin/sh
# Runs the fixture harness in Claude Code headless, with harness-profiler's
# committed hook, and copies the trace to output/trace.jsonl. Three turns of
# one session: the features, a manual /compact, and a call after it.
# With a directory (e2e/toy), runs that fixture instead: its PROMPT-1 only
# when it has no PROMPT-2. Output goes to <dir>/output.
# Needs `claude` signed in; costs one short session. Then run ../render.js --png.
set -eu
bin=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$bin/../.." && pwd)
here=$(cd "${1:-$bin}" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

cp -R "$here/fixture/." "$work/"
cd "$work"
git init -q -b main && git add -A && git -c user.name=e2e -c user.email=e2e@example.com commit -qm fixture
node "$root/plugin/libexec/hp.js" init claude >/dev/null

allowed='Skill Agent Read Edit Write Bash(wc:*) Bash(grep:*) Bash(cat:*) Bash(false)'
claude=${CLAUDE:-claude}
session=$($claude -p "$(cat PROMPT-1.txt)" --allowedTools $allowed --max-turns 40 --output-format json </dev/null \
  | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>console.log(JSON.parse(s).session_id))')
if [ -f PROMPT-2.txt ]; then
  $claude -p "/compact" --resume "$session" </dev/null >/dev/null
  $claude -p "$(cat PROMPT-2.txt)" --resume "$session" --allowedTools $allowed --max-turns 20 </dev/null >/dev/null
fi

sleep 3 # async hooks may still be writing
mkdir -p "$here/output"
node "$bin/collect.js" ".harness-profile/$session.jsonl" "$work" "$here/output"
echo "$here/output/trace.jsonl: $(wc -l < "$here/output/trace.jsonl") records"
