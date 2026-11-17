#!/usr/bin/env bash
# profile-tree.sh — render the AEP opencode harness profile on a development host.
#
# The wrapper is the only supported entry point to the vendored renderer. It
# walks up from its own directory (not the caller's cwd) to the repository root
# that holds reference/harness-profiler/plugin/libexec/hp.js, then runs that
# file with the remaining arguments. Nothing is copied and no subsurface is
# reimplemented: hp.js stays the judge of nesting and spend.
#
# Only bash builtins run before the node check, so a stripped PATH still gets
# the actionable message rather than "command not found".
set -euo pipefail

RENDERER=reference/harness-profiler/plugin/libexec/hp.js
NODE_MESSAGE='node 18+ required for profiling; install Node or skip'

# printf is a bash builtin: --help must work with a stripped PATH, before the
# node check, so no external `cat` is used here.
usage() {
  printf '%s\n' \
    'profile-tree.sh — render the AEP opencode harness profile.' \
    '' \
    'Usage:' \
    '  profile-tree.sh tree [session-id-prefix] [--branch <name>] [--verbose] [--format text|html]' \
    '  profile-tree.sh --help' \
    '' \
    'Root discovery:' \
    "  The wrapper walks up from its own directory (not the caller's cwd), looking" \
    '  for reference/harness-profiler/plugin/libexec/hp.js, then runs that renderer' \
    '  from the repository root. It therefore works from scripts/ or any other' \
    '  directory inside a source checkout, and never copies the vendored tree.' \
    '' \
    'Requirements:' \
    '  node 18+ required for profiling; install Node or skip. With no node on PATH' \
    '  the wrapper prints that line, exits non-zero, and does not run the renderer.' \
    '  --help does not need node.' \
    '' \
    'Traces:' \
    '  Read from <repo>/.harness-profile, the default capture location. An explicit' \
    '  AEP_HARNESS_PROFILE_DIR is rendered only when it names a directory called' \
    '  .harness-profile that sits outside any git work tree: the pinned renderer' \
    '  resolves its project through git, so a destination inside one is re-read' \
    '  from that repository root instead, and the wrapper rejects it rather than' \
    '  silently rendering a different directory.' \
    '' \
    'Scope:' \
    '  Development host only. The shipped image has no Node and no reference/ tree,' \
    '  so this wrapper cannot run there.' \
    '' \
    'Examples:' \
    '  bash scripts/profile-tree.sh tree' \
    '  bash scripts/profile-tree.sh tree --branch docs/harness-profiler-adoption' \
    '  bash scripts/profile-tree.sh tree --format html > /tmp/profile.html'
}

die() {
  printf 'profile-tree: %s\n' "$*" >&2
  exit 1
}

case ${1:-} in
-h | --help | help)
  usage
  exit 0
  ;;
tree) ;;
'')
  usage >&2
  exit 2
  ;;
*)
  usage >&2
  die "unsupported command '$1' (only 'tree' is wrapped)"
  ;;
esac

# Resolve the root from this script's location. ${BASH_SOURCE[0]} may be
# relative when invoked as `bash scripts/profile-tree.sh`; cd makes it absolute.
script=${BASH_SOURCE[0]}
case $script in
*/*) script_dir=${script%/*} ;;
*) script_dir=. ;;
esac
script_dir=$(cd -- "$script_dir" && pwd)

root=$script_dir
while [ ! -f "$root/$RENDERER" ]; do
  [ "$root" = / ] && die "cannot find $RENDERER above $script_dir (run from a source checkout of this repository)"
  root=${root%/*}
  [ -z "$root" ] && root=/
done

node_bin=$(command -v node 2>/dev/null || true)
if [ -z "$node_bin" ]; then
  printf 'profile-tree: %s\n' "$NODE_MESSAGE" >&2
  exit 1
fi
node_version=$("$node_bin" -v 2>/dev/null || true)
node_major=${node_version#v}
node_major=${node_major%%.*}
case $node_major in
'' | *[!0-9]*) die "$NODE_MESSAGE (found: ${node_version:-unknown})" ;;
esac
if [ "$node_major" -lt 18 ]; then
  die "$NODE_MESSAGE (found: $node_version)"
fi

# An explicit destination is renderable only when it is a .harness-profile
# directory OUTSIDE any git work tree: hp.js projectDir() resolves the project
# as gitRoot(CLAUDE_PROJECT_DIR) || start, so a destination inside a work tree
# is silently re-read from that repository's own root .harness-profile (the
# reviewer's repro: "No traces", or the default rendered instead). Reject it
# with the reason and both remedies rather than render a different directory.
if [ -n "${AEP_HARNESS_PROFILE_DIR:-}" ]; then
  trace_dir=$(cd -- "$AEP_HARNESS_PROFILE_DIR" 2>/dev/null && pwd) || {
    die "AEP_HARNESS_PROFILE_DIR does not exist: $AEP_HARNESS_PROFILE_DIR"
  }
  case $trace_dir in
  */.harness-profile) project_dir=${trace_dir%/.harness-profile} ;;
  *) die "AEP_HARNESS_PROFILE_DIR is $trace_dir; the pinned renderer reads only a directory named .harness-profile" ;;
  esac
  probe=$project_dir
  while [ "$probe" != / ]; do
    if [ -e "$probe/.git" ]; then
      die "AEP_HARNESS_PROFILE_DIR is $trace_dir, inside a git work tree rooted at $probe; the pinned renderer would read $probe/.harness-profile instead. Unset it to use a repository's default destination, or choose a .harness-profile outside any git repository"
    fi
    probe=${probe%/*}
    [ -z "$probe" ] && probe=/
  done
  export CLAUDE_PROJECT_DIR=$project_dir
fi

cd -- "$root" || die "cannot enter repository root: $root"
exec "$node_bin" "$root/$RENDERER" "$@"
