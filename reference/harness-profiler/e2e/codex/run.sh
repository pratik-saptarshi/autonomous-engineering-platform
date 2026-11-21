#!/bin/sh
# Runs the Claude fixture harness in Codex and records the raw hook payloads
# to output/raw.jsonl. hp has no `capture codex` yet, so this uses the raw
# recorder; once it does, the hook command changes and render.js takes over.
#
# What differs from Claude Code: skills come from .agents/skills/ (copied
# from the Claude fixture), `context: fork` is ignored so validator runs inline,
# and subagents are spawn_agent calls the prompt asks for in words.
#
# Codex runs a hook only after you trust it once in /hooks, and in 0.166
# project hooks did not fire, so put e2e/codex/hooks.json in
# ~/.codex/hooks.json, open `codex`, trust it in /hooks, then run this.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export HP_RECORD_DIR="$here" HP_RECORD_OUT="$work/.raw"

cp -R "$here/../claude/fixture/." "$work/"
mkdir -p "$work/.agents" && mv "$work/.claude/skills" "$work/.agents/skills" && rm -rf "$work/.claude"
cp "$here"/PROMPT-*.txt "$work/"
cd "$work"
git init -q -b main && git add -A && git -c user.name=e2e -c user.email=e2e@example.com commit -qm fixture

codex --version
codex exec --full-auto "$(cat PROMPT-1.txt)"
codex exec --full-auto resume --last "$(cat PROMPT-2.txt)"

if [ ! -s "$HP_RECORD_OUT/codex.jsonl" ]; then
  echo "No hook payloads recorded: trust the hooks in codex /hooks first." >&2
  exit 1
fi
mkdir -p "$here/output"
sed "s#$work#/work/fixture#g; s#$HOME#/home/dev#g" "$HP_RECORD_OUT/codex.jsonl" > "$here/output/raw.jsonl"
echo "$here/output/raw.jsonl: $(wc -l < "$here/output/raw.jsonl") payloads"
