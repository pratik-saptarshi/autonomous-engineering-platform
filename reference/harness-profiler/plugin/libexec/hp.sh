#!/bin/sh
# Finds node and runs hp.js beside this script. Hooks may run with a bare
# PATH, so it also looks where Volta, nvm and Homebrew put node; HP_NODE
# overrides the search. Without node, `capture` exits 0 silently: a missing
# profiler must never block a tool call. Only shell builtins run before node.
case $0 in */*) here=${0%/*} ;; *) here=. ;; esac

find_node() {
  if [ -n "${HP_NODE+set}" ]; then [ -x "$HP_NODE" ] && echo "$HP_NODE"; return; fi
  if command -v node >/dev/null 2>&1; then command -v node; return; fi
  if [ -x "$HOME/.volta/bin/node" ]; then echo "$HOME/.volta/bin/node"; return; fi
  newest=
  for candidate in "$HOME"/.nvm/versions/node/*/bin/node; do
    [ -x "$candidate" ] && newest=$candidate
  done
  if [ -n "$newest" ]; then echo "$newest"; return; fi
  for candidate in /opt/homebrew/bin/node /usr/local/bin/node; do
    if [ -x "$candidate" ]; then echo "$candidate"; return; fi
  done
}

node=$(find_node)
if [ -z "$node" ]; then
  case $1 in
    capture) cat >/dev/null 2>&1; exit 0 ;;
    *) echo "hp: node not found on PATH, in ~/.volta, ~/.nvm or Homebrew. Install Node 18+ or set HP_NODE." >&2; exit 1 ;;
  esac
fi
exec "$node" "$here/hp.js" "$@"
