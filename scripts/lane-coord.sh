#!/usr/bin/env bash
# lane-coord.sh — lane coordinator: claim, release, status for worktree lanes.
#
# Contract:
#   * A claim is held by a launcher process for the lane's whole lifetime:
#     `claim ... --exec <command...>` is required because the fence is an
#     flock held on an open fd BY this lane-coord process itself. A claim
#     that returned immediately would hold nothing.
#   * The worker runs as a child of the launcher with the fence and
#     capacity fds CLOSED, so no descendant can keep the fence alive after
#     the launcher dies — that is what makes a later takeover provable.
#   * The claim transaction (auto-settle, fence acquisition, fence
#     verification, takeover bookkeeping, capacity check, manifest write)
#     runs in that order under one exclusive capacity lock. Worktree setup
#     happens only after the capacity lock is released.
#   * Operational code signals no process, ever. launcher_pid in the
#     manifest is operator information only. The only signalling in this
#     file lives inside the --self-test harness, which signals only
#     processes the test itself spawned.
#   * Manifests are JSON written with printf from charset-validated
#     fields (temp file + mv, inside the lock) and read back only via
#     python3 JSON parsing — never grep.
#   * Launch-point controls: every claim loads and validates the
#     launch policy data (scripts/policy.data, sibling of this script;
#     AEP_POLICY_DATA overrides it for tests) before any state changes.
#     The declared working set (the worktree path plus every --path
#     extra) is checked against the sensitive-path patterns after the
#     claim transaction, before worktree setup; the worker child — and
#     only the child — runs with credential-named environment variables
#     scrubbed, unless AEP_LANE_FULL_ENV=1 disables the scrub loudly.
set -euo pipefail

# Platform-standard tool locations (see TOOLS.md): non-interactive runs
# (cron, agents) may not source ~/.bashrc, so ensure them here. They are
# APPENDED (not prepended) so a caller-injected PATH — e.g. the --self-test
# stub dir — keeps precedence. The command -v checks below stay strict.
export PATH="$PATH:$HOME/go/bin:$HOME/sdk/go/bin:$HOME/workspace/bin:$HOME/workspace/neurostrata/bin:$HOME/workspace/toolchains/bin"

LANES_DIR="${AEP_LANES_DIR:-$HOME/workspace/worktrees/.lanes}"
WT_ROOT="${AEP_WORKTREES_ROOT:-$HOME/workspace/worktrees}"

now_iso() {
  date -u +%Y-%m-%dT%H:%M:%SZ
}

usage() {
  echo "usage: lane-coord.sh claim --repo <abs path> --project <slug> --lane <slug> --branch <name> [--base <ref>] --worker <id> [--capacity <n>] [--path <extra> ...] --exec <command...>" >&2
  echo "usage: lane-coord.sh release --name <name>" >&2
  echo "usage: lane-coord.sh status [--name <name>]" >&2
  echo "usage: lane-coord.sh --self-test" >&2
}

# manifest_get <file> <field> — print the field value; non-zero if the
# file does not parse or the field is absent.
manifest_get() {
  python3 -c '
import json, sys
try:
    with open(sys.argv[1]) as fh:
        data = json.load(fh)
except Exception:
    sys.exit(1)
value = data.get(sys.argv[2])
if value is None:
    sys.exit(1)
print(value)
' "$1" "$2"
}

# manifest_epoch_state <file> — print "<epoch> <state>" from a SINGLE
# parse, so the two values can never be observed across a concurrent
# rewrite of the manifest.
manifest_epoch_state() {
  python3 -c '
import json, sys
try:
    with open(sys.argv[1]) as fh:
        data = json.load(fh)
except Exception:
    sys.exit(1)
if data.get("epoch") is None or data.get("state") is None:
    sys.exit(1)
print(data["epoch"], data["state"])
' "$1"
}

# write_manifest <name> <repo> <path> <branch> <base> <worker> <pid> <epoch> <state> <claimed_at>
write_manifest() {
  local name="$1" repo="$2" path="$3" branch="$4" base="$5" worker="$6"
  local pid="$7" epoch="$8" state="$9" claimed_at="${10}"
  local tmp="$LANES_DIR/$name.json.tmp.$$"
  printf '{"version": 1, "name": "%s", "repo": "%s", "path": "%s", "branch": "%s", "base": "%s", "worker": "%s", "launcher_pid": %s, "epoch": %s, "state": "%s", "claimed_at": "%s", "updated_at": "%s"}\n' \
    "$name" "$repo" "$path" "$branch" "$base" "$worker" "$pid" "$epoch" \
    "$state" "$claimed_at" "$(now_iso)" >"$tmp"
  mv "$tmp" "$LANES_DIR/$name.json"
}

# update_manifest_state <name> <new-state> — rewrite the manifest with a
# new state and a fresh updated_at, preserving every other field.
update_manifest_state() {
  local name="$1" new_state="$2" file="$LANES_DIR/$1.json"
  local repo path branch base worker pid epoch claimed_at
  repo=$(manifest_get "$file" repo) || return 1
  path=$(manifest_get "$file" path) || return 1
  branch=$(manifest_get "$file" branch) || return 1
  base=$(manifest_get "$file" base) || return 1
  worker=$(manifest_get "$file" worker) || return 1
  pid=$(manifest_get "$file" launcher_pid) || return 1
  epoch=$(manifest_get "$file" epoch) || return 1
  claimed_at=$(manifest_get "$file" claimed_at) || return 1
  write_manifest "$name" "$repo" "$path" "$branch" "$base" "$worker" \
    "$pid" "$epoch" "$new_state" "$claimed_at"
}

history_append() { # $1 = name, $2 = event, $3 = epoch, $4 = worker
  printf '%s %s epoch=%s worker=%s\n' "$(now_iso)" "$2" "$3" "$4" >>"$LANES_DIR/$1.log"
}

fence_is_held() { # $1 = name — live probe, never inferred from a pid
  local fence="$LANES_DIR/$1.fence"
  [ -e "$fence" ] || return 1
  if flock -n "$fence" true 2>/dev/null; then
    return 1
  fi
  return 0
}

count_claimed() {
  local n=0 f state
  for f in "$LANES_DIR"/*.json; do
    [ -e "$f" ] || continue
    state=$(manifest_get "$f" state 2>/dev/null || true)
    if [ "$state" = "claimed" ]; then
      n=$((n + 1))
    fi
  done
  printf '%s\n' "$n"
}

resolve_capacity() { # $1 = flag value (may be empty)
  local cap="${1:-}"
  if [ -z "$cap" ]; then
    cap="${AEP_LANE_CAPACITY:-2}"
  fi
  case "$cap" in
  *[!0-9]* | "")
    echo "lane-coord.sh: capacity must be a positive integer" >&2
    exit 2
    ;;
  esac
  if [ "$cap" -lt 1 ]; then
    echo "lane-coord.sh: capacity must be a positive integer" >&2
    exit 2
  fi
  printf '%s\n' "$cap"
}

# --- Launch policy data (scripts/policy.data) ---
# Grammar (validated on every claim by the embedded python3 loader):
# [section] headers ([sensitive-paths], [env-scrub]), one
# whitespace-free pattern/fragment per line, '#' comments and blank
# lines ignored; anything else — an unknown section, a pattern before
# any section, a token containing whitespace, an empty section — is a
# validation error and refuses the claim before anything is created.
POLICY_SENSITIVE_PATTERNS=()
POLICY_ENV_SCRUB=()

load_policy() {
  local policy_file="${AEP_POLICY_DATA:-$(dirname "${BASH_SOURCE[0]}")/policy.data}"
  local parsed line section=""
  if ! parsed=$(python3 -c '
import sys

path = sys.argv[1]
try:
    with open(path) as fh:
        lines = fh.read().splitlines()
except OSError:
    print("LANE: refuse policy data invalid: cannot read " + path)
    sys.exit(1)

section = None
data = {"sensitive-paths": [], "env-scrub": []}
for num, raw in enumerate(lines, 1):
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    if line.startswith("["):
        if line in ("[sensitive-paths]", "[env-scrub]"):
            section = line[1:-1]
            continue
        print("LANE: refuse policy data invalid: line %d: %s" % (num, raw))
        sys.exit(1)
    if section is None:
        print("LANE: refuse policy data invalid: line %d: %s" % (num, raw))
        sys.exit(1)
    if any(ch.isspace() for ch in line):
        print("LANE: refuse policy data invalid: line %d: %s" % (num, raw))
        sys.exit(1)
    data[section].append(line)

for name in ("sensitive-paths", "env-scrub"):
    if not data[name]:
        last = lines[-1] if lines else ""
        print("LANE: refuse policy data invalid: line %d: %s" % (len(lines), last))
        sys.exit(1)

for name in ("sensitive-paths", "env-scrub"):
    print("[" + name + "]")
    for entry in data[name]:
        print(entry)
' "$policy_file"); then
    printf '%s\n' "$parsed"
    exit 1
  fi
  POLICY_SENSITIVE_PATTERNS=()
  POLICY_ENV_SCRUB=()
  while IFS= read -r line; do
    case "$line" in
    "[sensitive-paths]") section="sensitive" ;;
    "[env-scrub]") section="scrub" ;;
    *)
      case "$section" in
      sensitive) POLICY_SENSITIVE_PATTERNS+=("$line") ;;
      scrub) POLICY_ENV_SCRUB+=("$line") ;;
      esac
      ;;
    esac
  done <<<"$parsed"
}

canonical_path() { # $1 = path — realpath, symlinks resolved
  python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$1"
}

# sensitive_match <canonical path> — print the first [sensitive-paths]
# pattern matching the path (fnmatchcase semantics: '*' spans '/'),
# or nothing.
sensitive_match() {
  python3 -c '
import fnmatch, sys
for pat in sys.argv[2:]:
    if fnmatch.fnmatchcase(sys.argv[1], pat):
        print(pat)
        break
' "$1" "${POLICY_SENSITIVE_PATTERNS[@]}"
}

# auth_occurrence_is_sensitive <UPPERCASED name> — true if the name has
# an AUTH occurrence that is NOT boundary-exempt: an occurrence is
# exempt when immediately preceded by SSH_ (spares SSH_AUTH_SOCK) or
# immediately followed by OR + ('_' or end-of-name) (spares
# GIT_AUTHOR_NAME, GIT_AUTHOR_EMAIL, ...AUTHOR / ...AUTHOR_ names).
# AUTHORITY is not exempt: its AUTH is followed by ORI..., not OR_/end.
auth_occurrence_is_sensitive() {
  local s="$1" i after
  local len=${#s}
  for ((i = 0; i + 4 <= len; i++)); do
    if [ "${s:i:4}" = "AUTH" ]; then
      if [ "$i" -ge 4 ] && [ "${s:$((i - 4)):4}" = "SSH_" ]; then
        continue
      fi
      after="${s:$((i + 4))}"
      if [ "$after" = "OR" ] || [[ "$after" == OR_* ]]; then
        continue
      fi
      return 0
    fi
  done
  return 1
}

# name_is_sensitive <name> — true if the variable name contains any
# [env-scrub] fragment as a case-insensitive substring (the AUTH
# fragment applies its boundary exemptions above; other fragments have
# none).
name_is_sensitive() {
  local upper="${1^^}" frag frag_upper
  for frag in "${POLICY_ENV_SCRUB[@]}"; do
    frag_upper="${frag^^}"
    if [ "$frag_upper" = "AUTH" ]; then
      if auth_occurrence_is_sensitive "$upper"; then return 0; fi
    elif [[ "$upper" == *"$frag_upper"* ]]; then
      return 0
    fi
  done
  return 1
}

# registered_worktree_branch <repo> <path> — print the branch registered
# for that exact worktree path in the repo, or nothing.
registered_worktree_branch() {
  local repo="$1" want_path="$2" line cur="" found=""
  git -C "$repo" worktree list --porcelain >/dev/null 2>&1 || return 1
  while IFS= read -r line; do
    case "$line" in
    "worktree "*)
      cur="${line#worktree }"
      ;;
    "branch refs/heads/"*)
      if [ "$cur" = "$want_path" ]; then
        found="${line#branch refs/heads/}"
      fi
      ;;
    esac
  done <<EOF
$(git -C "$repo" worktree list --porcelain)
EOF
  if [ -n "$found" ]; then
    printf '%s\n' "$found"
  fi
}

# Globals set by cmd_claim for the setup-failure path.
CLAIM_EPOCH=0
CLAIM_WORKER=""

claim_setup_failed() { # $1 = name — manifest was written; settle it, then exit 1
  update_manifest_state "$1" "released" || true
  history_append "$1" "setup-failed" "$CLAIM_EPOCH" "$CLAIM_WORKER"
  exit 1
}

claim_refused() { # $1 = name — manifest was written; settle it as a refusal, then exit 1
  update_manifest_state "$1" "released" || true
  history_append "$1" "claim-refused" "$CLAIM_EPOCH" "$CLAIM_WORKER"
  exit 1
}

cmd_claim() {
  local repo="" project="" lane="" branch="" base="origin/main" worker=""
  local capacity_flag="" seen_exec=0
  local -a declared_paths=() worker_cmd=()
  while [ $# -gt 0 ]; do
    case "$1" in
    --repo)
      [ $# -ge 2 ] || { usage; exit 2; }
      repo="$2"; shift 2 ;;
    --project)
      [ $# -ge 2 ] || { usage; exit 2; }
      project="$2"; shift 2 ;;
    --lane)
      [ $# -ge 2 ] || { usage; exit 2; }
      lane="$2"; shift 2 ;;
    --branch)
      [ $# -ge 2 ] || { usage; exit 2; }
      branch="$2"; shift 2 ;;
    --base)
      [ $# -ge 2 ] || { usage; exit 2; }
      base="$2"; shift 2 ;;
    --worker)
      [ $# -ge 2 ] || { usage; exit 2; }
      worker="$2"; shift 2 ;;
    --capacity)
      [ $# -ge 2 ] || { usage; exit 2; }
      capacity_flag="$2"; shift 2 ;;
    --path)
      [ $# -ge 2 ] || { usage; exit 2; }
      declared_paths+=("$2"); shift 2 ;;
    --exec)
      shift
      worker_cmd=("$@")
      seen_exec=1
      break ;;
    *)
      usage; exit 2 ;;
    esac
  done

  if [ "$seen_exec" -ne 1 ] || [ ${#worker_cmd[@]} -eq 0 ]; then
    echo "usage: lane-coord.sh claim ... --exec <command...> (the launcher must stay alive for the lane's lifetime — it holds the fence)" >&2
    exit 2
  fi
  if [ -z "$repo" ] || [ -z "$project" ] || [ -z "$lane" ] || [ -z "$branch" ] || [ -z "$worker" ]; then
    usage
    exit 2
  fi
  case "$repo" in
  /*) ;;
  *) usage; exit 2 ;;
  esac
  if ! [[ "$project" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then usage; exit 2; fi
  if ! [[ "$lane" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then usage; exit 2; fi
  if ! [[ "$worker" =~ ^[A-Za-z0-9_.-]+$ ]]; then usage; exit 2; fi
  if ! git check-ref-format --branch "$branch" >/dev/null 2>&1; then usage; exit 2; fi

  local capacity
  capacity=$(resolve_capacity "$capacity_flag")

  # Launch policy: load and validate first thing, before any state
  # changes — a malformed policy file refuses the claim with nothing
  # created (no lanes dir, no manifest, no worktree).
  load_policy

  local name="$project-$lane"
  local wt_path="$WT_ROOT/$name"
  local fence_file="$LANES_DIR/$name.fence"
  local manifest_file="$LANES_DIR/$name.json"
  CLAIM_WORKER="$worker"

  mkdir -p "$LANES_DIR" "$WT_ROOT"

  local prev_exists=0 prev_epoch=0 prev_state=""

  # --- Claim transaction, under the capacity lock ---
  exec 9>"$LANES_DIR/.capacity.lock"
  if ! flock -w 60 9; then
    echo "LANE: lock timeout after 60s waiting for the capacity lock"
    exit 5
  fi

  # Previous-claim snapshot: taken only AFTER the capacity lock is held,
  # in a single parse, and before the step-1 settle pass rewrites this
  # lane's manifest — so epoch and state are always one consistent
  # observation of the previous claim, never a torn pair straddling
  # another lane's settle or a standalone release.
  if [ -f "$manifest_file" ]; then
    local prev_snap
    if prev_snap=$(manifest_epoch_state "$manifest_file" 2>/dev/null); then
      prev_epoch="${prev_snap%% *}"
      prev_state="${prev_snap##* }"
      prev_exists=1
    fi
  fi

  # 1. Auto-settle stale claims: a claimed manifest whose fence probes
  #    free has a dead launcher — settle it and free its capacity.
  local f other other_state other_epoch other_worker
  for f in "$LANES_DIR"/*.json; do
    [ -e "$f" ] || continue
    other_state=$(manifest_get "$f" state 2>/dev/null || true)
    [ "$other_state" = "claimed" ] || continue
    other="${f##*/}"
    other="${other%.json}"
    if ! fence_is_held "$other"; then
      other_epoch=$(manifest_get "$f" epoch 2>/dev/null || echo 0)
      other_worker=$(manifest_get "$f" worker 2>/dev/null || echo unknown)
      update_manifest_state "$other" "reaped" || true
      history_append "$other" "settled-interrupted" "$other_epoch" "$other_worker"
    fi
  done

  # 2. Acquire this lane's fence on the launcher's own fd 8.
  exec 8>"$fence_file"
  if ! flock -n 8; then
    local busy_worker busy_epoch
    busy_worker=$(manifest_get "$manifest_file" worker 2>/dev/null || true)
    busy_epoch=$(manifest_get "$manifest_file" epoch 2>/dev/null || true)
    if [ -n "$busy_worker" ] && [ -n "$busy_epoch" ]; then
      echo "LANE: busy $name held by worker $busy_worker epoch $busy_epoch"
    else
      echo "LANE: busy $name (fence held)"
    fi
    exit 3
  fi

  # 3. Post-acquisition fence verification: a fresh probe MUST fail.
  if flock -n "$fence_file" true 2>/dev/null; then
    echo "LANE: fence verification failed for $name"
    exit 1
  fi

  # 4. Takeover bookkeeping: epoch is monotonic per lane.
  local epoch=1
  if [ "$prev_exists" -eq 1 ]; then
    epoch=$((prev_epoch + 1))
    if [ "$prev_state" = "claimed" ]; then
      echo "LANE: note previous claim on $name settled interrupted at epoch $prev_epoch"
    fi
  fi
  CLAIM_EPOCH="$epoch"

  # 5. Capacity check, against the post-settle claimed count.
  local claimed_count
  claimed_count=$(count_claimed)
  if [ "$claimed_count" -ge "$capacity" ]; then
    echo "LANE: capacity reached ($capacity active lanes)"
    exit 4
  fi

  # Resolve the base to a full SHA for the manifest (worktree creation
  # itself happens after the lock is released).
  local base_sha
  if ! base_sha=$(git -C "$repo" rev-parse --verify "$base^{commit}" 2>/dev/null); then
    echo "LANE: refuse $name: cannot resolve base $base"
    exit 1
  fi

  # 6. Write the manifest (temp + mv, inside the lock) and history.
  write_manifest "$name" "$repo" "$wt_path" "$branch" "$base_sha" "$worker" \
    "$$" "$epoch" "claimed" "$(now_iso)"
  history_append "$name" "claimed" "$epoch" "$worker"

  # Release the capacity lock — the transaction is over.
  flock -u 9 || true
  exec 9>&-

  # --- Declared-path check (after the transaction, before worktree setup) ---
  # The declared working set is the deterministic worktree path plus
  # every --path extra. Each path is canonicalized (symlinks resolved:
  # a declared symlink into a sensitive directory IS the sensitive
  # directory) and matched against [sensitive-paths]. Declared extras
  # must exist at claim time — canonicalizing a nonexistent path's
  # parent chain is guesswork.
  local -a all_declared=("$wt_path")
  if [ ${#declared_paths[@]} -gt 0 ]; then
    all_declared+=("${declared_paths[@]}")
  fi
  local check_idx=0 check_path canon matched
  for check_path in "${all_declared[@]}"; do
    if [ "$check_idx" -gt 0 ] && [ ! -e "$check_path" ]; then
      echo "LANE: refuse $name: declared path $check_path does not exist"
      claim_refused "$name"
    fi
    check_idx=$((check_idx + 1))
    canon=$(canonical_path "$check_path")
    matched=$(sensitive_match "$canon")
    if [ -n "$matched" ]; then
      echo "LANE: refuse $name: declared path $canon matches sensitive pattern $matched"
      claim_refused "$name"
    fi
  done

  # --- Worktree setup (after the capacity lock is released) ---
  if [ ! -e "$wt_path" ]; then
    if git -C "$repo" show-ref --verify --quiet "refs/heads/$branch"; then
      echo "LANE: refuse $name: branch $branch already exists without a registered worktree"
      claim_setup_failed "$name"
    fi
    if ! git -C "$repo" worktree add -b "$branch" "$wt_path" "$base_sha" >/dev/null 2>&1; then
      echo "LANE: refuse $name: worktree setup failed"
      claim_setup_failed "$name"
    fi
  else
    local reg_branch cur_branch
    reg_branch=$(registered_worktree_branch "$repo" "$wt_path" || true)
    cur_branch=$(git -C "$wt_path" branch --show-current 2>/dev/null || true)
    if [ "$reg_branch" != "$branch" ] || [ "$cur_branch" != "$branch" ]; then
      echo "LANE: refuse $name: path exists but is not this lane's registered worktree"
      claim_setup_failed "$name"
    fi
  fi

  # --- Worker spawn: child process, fence/capacity fds closed ---
  echo "LANE: claimed $name path=$wt_path branch=$branch epoch=$epoch"
  cd "$wt_path" || claim_setup_failed "$name"
  local worker_status=0
  if [ "${AEP_LANE_FULL_ENV:-}" = "1" ]; then
    # Opt-out is loud, never silent: the warning goes to stderr on
    # every launch and the worker receives the full environment.
    echo "LANE: warning AEP_LANE_FULL_ENV=1: worker receives the full environment (credential scrub disabled)" >&2
    "${worker_cmd[@]}" 8>&- 9>&- || worker_status=$?
  else
    # Env sanitization applies to the worker child only: the scrub
    # runs in the subshell wrapping the spawn, so the launcher keeps
    # its own environment for its bookkeeping. The subshell closes the
    # fence/capacity fds itself first — otherwise it would hold the
    # fence open as an orphan after the launcher dies, defeating the
    # fence-lifetime contract above.
    (
      exec 8>&- 9>&-
      while IFS= read -r scrub_var; do
        if name_is_sensitive "$scrub_var"; then
          unset "$scrub_var"
        fi
      done < <(compgen -e)
      "${worker_cmd[@]}" 8>&- 9>&-
    ) || worker_status=$?
  fi

  update_manifest_state "$name" "released" || true
  history_append "$name" "released" "$epoch" "$worker"
  echo "LANE: released $name (worker exit $worker_status)"
  exit "$worker_status"
}

cmd_release() {
  local name=""
  while [ $# -gt 0 ]; do
    case "$1" in
    --name)
      [ $# -ge 2 ] || { usage; exit 2; }
      name="$2"; shift 2 ;;
    *)
      usage; exit 2 ;;
    esac
  done
  if [ -z "$name" ]; then usage; exit 2; fi
  if ! [[ "$name" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then usage; exit 2; fi

  # Serialize against claim transactions: the fence probe, the state
  # check, and the manifest update below all run under the capacity
  # lock, so a claim can never interleave between probe and write and
  # have its fresh "claimed" manifest clobbered to "released".
  mkdir -p "$LANES_DIR"
  exec 9>"$LANES_DIR/.capacity.lock"
  if ! flock -w 60 9; then
    echo "LANE: lock timeout after 60s waiting for the capacity lock"
    exit 5
  fi

  local manifest_file="$LANES_DIR/$name.json"
  if [ ! -f "$manifest_file" ]; then
    echo "LANE: refuse release $name: no manifest"
    exit 1
  fi
  if fence_is_held "$name"; then
    echo "LANE: refuse release $name: fence held (launcher alive)"
    exit 1
  fi
  local state epoch worker
  state=$(manifest_get "$manifest_file" state 2>/dev/null || true)
  if [ "$state" != "claimed" ]; then
    echo "LANE: refuse release $name: state is $state"
    exit 1
  fi
  epoch=$(manifest_get "$manifest_file" epoch 2>/dev/null || echo 0)
  worker=$(manifest_get "$manifest_file" worker 2>/dev/null || echo unknown)
  update_manifest_state "$name" "released"
  history_append "$name" "released" "$epoch" "$worker"
  echo "LANE: released $name"
}

cmd_status() {
  local name="" capacity_flag=""
  while [ $# -gt 0 ]; do
    case "$1" in
    --name)
      [ $# -ge 2 ] || { usage; exit 2; }
      name="$2"; shift 2 ;;
    --capacity)
      [ $# -ge 2 ] || { usage; exit 2; }
      capacity_flag="$2"; shift 2 ;;
    *)
      usage; exit 2 ;;
    esac
  done
  local capacity
  capacity=$(resolve_capacity "$capacity_flag")

  print_status_line() { # $1 = manifest file
    local f="$1" n state epoch worker path fence_state
    n=$(manifest_get "$f" name 2>/dev/null || true)
    state=$(manifest_get "$f" state 2>/dev/null || true)
    epoch=$(manifest_get "$f" epoch 2>/dev/null || true)
    worker=$(manifest_get "$f" worker 2>/dev/null || true)
    path=$(manifest_get "$f" path 2>/dev/null || true)
    if fence_is_held "$n"; then fence_state="held"; else fence_state="free"; fi
    echo "$n state=$state epoch=$epoch worker=$worker fence=$fence_state path=$path"
  }

  if [ -n "$name" ]; then
    if [ ! -f "$LANES_DIR/$name.json" ]; then
      echo "LANE: no manifest for $name"
      exit 1
    fi
    print_status_line "$LANES_DIR/$name.json"
    return 0
  fi
  local f
  for f in "$LANES_DIR"/*.json; do
    [ -e "$f" ] || continue
    print_status_line "$f"
  done
  echo "LANE: pool: $(count_claimed) claimed of $capacity"
}

self_test() {
  local fails=0 case_fails=0
  local self_path
  self_path="$(cd "$(dirname -- "$0")" && pwd -P)/$(basename -- "$0")"
  # NB: fixture globals (not local) so the EXIT trap can still see them
  # under `set -u` after this function returns — boot-gate idiom.
  selftest_root=$(mktemp -d)
  export AEP_LANES_DIR="$selftest_root/lanes"
  export AEP_WORKTREES_ROOT="$selftest_root/worktrees"
  LANES_DIR="$AEP_LANES_DIR"
  WT_ROOT="$AEP_WORKTREES_ROOT"
  BG_PIDS=()
  trap 'for p in "${BG_PIDS[@]:-}"; do if [ -n "$p" ]; then kill "$p" 2>/dev/null || true; fi; done; rm -rf "$selftest_root"' EXIT

  local repo="$selftest_root/repo"
  mkdir -p "$repo" "$LANES_DIR" "$WT_ROOT"
  git init -q "$repo"
  printf 'fixture\n' >"$repo/file.txt"
  git -C "$repo" add file.txt
  git -C "$repo" -c user.name=LaneTest -c user.email=lane@test.invalid commit -q -m "fixture commit"
  local head_sha
  head_sha=$(git -C "$repo" rev-parse HEAD)

  wait_for_manifest() { # $1 = lane name
    local i=0
    while [ $i -lt 50 ]; do
      if [ -f "$LANES_DIR/$1.json" ]; then return 0; fi
      sleep 0.1
      i=$((i + 1))
    done
    return 1
  }

  wait_for_file() { # $1 = file path
    local i=0
    while [ $i -lt 50 ]; do
      if [ -f "$1" ]; then return 0; fi
      sleep 0.1
      i=$((i + 1))
    done
    return 1
  }

  mget() { # $1 = lane name, $2 = field
    python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' \
      "$LANES_DIR/$1.json" "$2" 2>/dev/null || true
  }

  wait_for_claimed() { # $1 = lane name, $2 = epoch — poll until that claim is live
    local i=0
    while [ $i -lt 50 ]; do
      if [ "$(mget "$1" epoch)" = "$2" ] && [ "$(mget "$1" state)" = "claimed" ]; then return 0; fi
      sleep 0.1
      i=$((i + 1))
    done
    return 1
  }

  report_case() { # $1 = case label
    if [ "$case_fails" -eq 0 ]; then
      echo "SELF-TEST: $1 ok"
    else
      echo "SELF-TEST: $1 FAIL"
      fails=$((fails + 1))
    fi
    case_fails=0
  }

  # --- Case 1: claim-runs-worker-in-worktree ---
  local out1="$selftest_root/out1.txt" rc1=0
  bash "$self_path" claim --repo "$repo" --project alpha --lane one \
    --branch br-one --base HEAD --worker w1 \
    --exec sh -c "pwd > $selftest_root/pwd.out" >"$out1" 2>&1 || rc1=$?
  local wt1="$WT_ROOT/alpha-one"
  [ "$rc1" -eq 0 ] || case_fails=1
  [ -d "$wt1" ] || case_fails=1
  [ "$(git -C "$wt1" branch --show-current 2>/dev/null || true)" = "br-one" ] || case_fails=1
  [ "$(cat "$selftest_root/pwd.out" 2>/dev/null || true)" = "$wt1" ] || case_fails=1
  [ "$(mget alpha-one epoch)" = "1" ] || case_fails=1
  [ "$(mget alpha-one base)" = "$head_sha" ] || case_fails=1
  [ "$(mget alpha-one state)" = "released" ] || case_fails=1
  grep -q "LANE: claimed alpha-one path=$wt1 branch=br-one epoch=1" "$out1" || case_fails=1
  grep -q "LANE: released alpha-one (worker exit 0)" "$out1" || case_fails=1
  grep -q " claimed epoch=1 worker=w1" "$LANES_DIR/alpha-one.log" || case_fails=1
  grep -q " released epoch=1 worker=w1" "$LANES_DIR/alpha-one.log" || case_fails=1
  report_case "claim-runs-worker-in-worktree"

  # --- Case 2: second-claim-same-name-busy ---
  local out2="$selftest_root/out2.txt" out2b="$selftest_root/out2b.txt" rc2b=0
  bash "$self_path" claim --repo "$repo" --project beta --lane two \
    --branch br-two --base HEAD --worker w-first \
    --exec sleep 10 >"$out2" 2>&1 &
  local launcher2=$!
  BG_PIDS+=("$launcher2")
  wait_for_manifest "beta-two" || case_fails=1
  bash "$self_path" claim --repo "$repo" --project beta --lane two \
    --branch br-two --base HEAD --worker w-second \
    --exec true >"$out2b" 2>&1 || rc2b=$?
  [ "$rc2b" -eq 3 ] || case_fails=1
  grep -q "LANE: busy beta-two held by worker w-first epoch 1" "$out2b" || case_fails=1
  kill "$launcher2" 2>/dev/null || true
  wait "$launcher2" 2>/dev/null || true
  report_case "second-claim-same-name-busy"

  # --- Case 3: release-frees-fence ---
  local out3="$selftest_root/out3.txt" out3b="$selftest_root/out3b.txt" rc3=0 rc3b=0
  bash "$self_path" claim --repo "$repo" --project gamma --lane three \
    --branch br-three --base HEAD --worker w3 \
    --exec true >"$out3" 2>&1 || rc3=$?
  bash "$self_path" claim --repo "$repo" --project gamma --lane three \
    --branch br-three --base HEAD --worker w3 \
    --exec true >"$out3b" 2>&1 || rc3b=$?
  [ "$rc3" -eq 0 ] || case_fails=1
  [ "$rc3b" -eq 0 ] || case_fails=1
  [ "$(mget gamma-three epoch)" = "2" ] || case_fails=1
  # Extension: standalone release serializes under the capacity lock.
  # Leave a claimed manifest with a free fence (signal the launcher, as
  # in case 4), then hold the capacity lock in the test itself: a
  # release launched with the test's lock fd closed must stay blocked
  # and change nothing until the lock is dropped, then succeed.
  local out3c="$selftest_root/out3c.txt" out3r="$selftest_root/out3r.txt" rc3r=0
  bash "$self_path" claim --repo "$repo" --project gamma --lane three \
    --branch br-three --base HEAD --worker w3 \
    --exec sleep 10 >"$out3c" 2>&1 &
  local launcher3c=$!
  BG_PIDS+=("$launcher3c")
  wait_for_claimed "gamma-three" 3 || case_fails=1
  kill "$launcher3c" 2>/dev/null || true
  wait "$launcher3c" 2>/dev/null || true
  sleep 0.2
  [ "$(mget gamma-three state)" = "claimed" ] || case_fails=1
  exec 7>"$LANES_DIR/.capacity.lock"
  flock 7 || case_fails=1
  bash "$self_path" release --name gamma-three >"$out3r" 2>&1 7>&- &
  local release3_pid=$!
  BG_PIDS+=("$release3_pid")
  sleep 1
  kill -0 "$release3_pid" 2>/dev/null || case_fails=1
  [ "$(mget gamma-three state)" = "claimed" ] || case_fails=1
  flock -u 7 || true
  exec 7>&-
  wait "$release3_pid" || rc3r=$?
  [ "$rc3r" -eq 0 ] || case_fails=1
  grep -q "LANE: released gamma-three" "$out3r" || case_fails=1
  [ "$(mget gamma-three state)" = "released" ] || case_fails=1
  report_case "release-frees-fence"

  # --- Case 4: stale-claim-auto-settles ---
  local out4a="$selftest_root/out4a.txt" out4b="$selftest_root/out4b.txt" rc4b=0
  bash "$self_path" claim --repo "$repo" --project delta --lane a \
    --branch br-four-a --base HEAD --worker wa \
    --exec sh -c "echo \$\$ > $selftest_root/worker-a.pid; exec sleep 30" >"$out4a" 2>&1 &
  local launcher4=$!
  BG_PIDS+=("$launcher4")
  wait_for_manifest "delta-a" || case_fails=1
  wait_for_file "$selftest_root/worker-a.pid" || case_fails=1
  local worker_a_pid=""
  worker_a_pid=$(cat "$selftest_root/worker-a.pid" 2>/dev/null || true)
  [ -n "$worker_a_pid" ] || case_fails=1
  kill "$launcher4" 2>/dev/null || true
  wait "$launcher4" 2>/dev/null || true
  sleep 0.2
  [ "$(mget delta-a state)" = "claimed" ] || case_fails=1
  bash "$self_path" claim --repo "$repo" --project delta --lane b \
    --branch br-four-b --base HEAD --worker wb --capacity 1 \
    --exec true >"$out4b" 2>&1 || rc4b=$?
  [ "$rc4b" -eq 0 ] || case_fails=1
  [ "$(mget delta-a state)" = "reaped" ] || case_fails=1
  grep -q " settled-interrupted epoch=1 worker=wa" "$LANES_DIR/delta-a.log" || case_fails=1
  if [ -n "$worker_a_pid" ]; then
    kill -0 "$worker_a_pid" 2>/dev/null || case_fails=1
    kill "$worker_a_pid" 2>/dev/null || true
  fi
  # Extension: the previous-claim snapshot is taken under the capacity
  # lock. Leave lane delta-c claimed with a free fence, hold the lock
  # in the test, and launch the takeover claim with the test's lock fd
  # closed so it blocks on the lock. While it is blocked, flip
  # delta-c's manifest claimed -> released (what a concurrent settle or
  # standalone release would do). After the lock drops, the claim's
  # snapshot must observe "released": no settled-interrupted note, and
  # the epoch still advances to 2. A pre-lock snapshot would have seen
  # "claimed" and printed the note spuriously.
  local out4c="$selftest_root/out4c.txt" out4d="$selftest_root/out4d.txt" rc4d=0
  bash "$self_path" claim --repo "$repo" --project delta --lane c \
    --branch br-four-c --base HEAD --worker wc \
    --exec sleep 10 >"$out4c" 2>&1 &
  local launcher4c=$!
  BG_PIDS+=("$launcher4c")
  wait_for_claimed "delta-c" 1 || case_fails=1
  kill "$launcher4c" 2>/dev/null || true
  wait "$launcher4c" 2>/dev/null || true
  sleep 0.2
  [ "$(mget delta-c state)" = "claimed" ] || case_fails=1
  exec 7>"$LANES_DIR/.capacity.lock"
  flock 7 || case_fails=1
  bash "$self_path" claim --repo "$repo" --project delta --lane c \
    --branch br-four-c --base HEAD --worker wc2 \
    --exec true >"$out4d" 2>&1 7>&- &
  local takeover4_pid=$!
  BG_PIDS+=("$takeover4_pid")
  sleep 1
  kill -0 "$takeover4_pid" 2>/dev/null || case_fails=1
  python3 -c 'import json, sys; p = sys.argv[1]; d = json.load(open(p)); d["state"] = "released"; json.dump(d, open(p, "w"))' \
    "$LANES_DIR/delta-c.json" || case_fails=1
  flock -u 7 || true
  exec 7>&-
  wait "$takeover4_pid" || rc4d=$?
  [ "$rc4d" -eq 0 ] || case_fails=1
  if grep -q "LANE: note previous claim on delta-c" "$out4d"; then case_fails=1; fi
  [ "$(mget delta-c epoch)" = "2" ] || case_fails=1
  report_case "stale-claim-auto-settles"

  # --- Case 5: capacity-blocks-second-lane ---
  local out5="$selftest_root/out5.txt" out5b="$selftest_root/out5b.txt" rc5b=0
  bash "$self_path" claim --repo "$repo" --project epsilon --lane a \
    --branch br-five-a --base HEAD --worker w5a \
    --exec sleep 10 >"$out5" 2>&1 &
  local launcher5=$!
  BG_PIDS+=("$launcher5")
  wait_for_manifest "epsilon-a" || case_fails=1
  bash "$self_path" claim --repo "$repo" --project epsilon --lane b \
    --branch br-five-b --base HEAD --worker w5b --capacity 1 \
    --exec true >"$out5b" 2>&1 || rc5b=$?
  [ "$rc5b" -eq 4 ] || case_fails=1
  grep -q "LANE: capacity reached (1 active lanes)" "$out5b" || case_fails=1
  kill "$launcher5" 2>/dev/null || true
  wait "$launcher5" 2>/dev/null || true
  report_case "capacity-blocks-second-lane"

  # --- Case 6: parallel-claim-race ---
  local out6a="$selftest_root/out6a.txt" out6b="$selftest_root/out6b.txt"
  bash "$self_path" claim --repo "$repo" --project zeta --lane race \
    --branch br-race --base HEAD --worker w6a \
    --exec sleep 5 >"$out6a" 2>&1 &
  local pid6a=$!
  BG_PIDS+=("$pid6a")
  bash "$self_path" claim --repo "$repo" --project zeta --lane race \
    --branch br-race --base HEAD --worker w6b \
    --exec sleep 5 >"$out6b" 2>&1 &
  local pid6b=$!
  BG_PIDS+=("$pid6b")
  local rc6a=0 rc6b=0
  wait "$pid6a" || rc6a=$?
  wait "$pid6b" || rc6b=$?
  local zeros=0 threes=0
  [ "$rc6a" -eq 0 ] && zeros=$((zeros + 1))
  [ "$rc6b" -eq 0 ] && zeros=$((zeros + 1))
  [ "$rc6a" -eq 3 ] && threes=$((threes + 1))
  [ "$rc6b" -eq 3 ] && threes=$((threes + 1))
  [ "$zeros" -eq 1 ] || case_fails=1
  [ "$threes" -eq 1 ] || case_fails=1
  report_case "parallel-claim-race"

  # --- Case 7: working-set-refuses-sensitive-dir ---
  local out7="$selftest_root/out7.txt" rc7=0
  local canon7
  canon7=$(python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$HOME/.ssh")
  bash "$self_path" claim --repo "$repo" --project eta --lane seven \
    --branch br-seven --base HEAD --worker w7 \
    --path "$HOME/.ssh" \
    --exec true >"$out7" 2>&1 || rc7=$?
  [ "$rc7" -eq 1 ] || case_fails=1
  grep -qF "LANE: refuse eta-seven: declared path $canon7 matches sensitive pattern */.ssh" "$out7" || case_fails=1
  [ ! -e "$WT_ROOT/eta-seven" ] || case_fails=1
  [ "$(mget eta-seven state)" = "released" ] || case_fails=1
  grep -q " claim-refused epoch=1 worker=w7" "$LANES_DIR/eta-seven.log" || case_fails=1
  report_case "working-set-refuses-sensitive-dir"

  # --- Case 8: working-set-refuses-symlink-into-sensitive ---
  mkdir -p "$selftest_root/home/.aws"
  ln -s "$selftest_root/home/.aws" "$selftest_root/link-aws"
  local out8="$selftest_root/out8.txt" rc8=0
  local canon8
  canon8=$(python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$selftest_root/link-aws")
  bash "$self_path" claim --repo "$repo" --project eta --lane eight \
    --branch br-eight --base HEAD --worker w8 \
    --path "$selftest_root/link-aws" \
    --exec true >"$out8" 2>&1 || rc8=$?
  [ "$rc8" -eq 1 ] || case_fails=1
  [ "$canon8" != "$selftest_root/link-aws" ] || case_fails=1
  grep -qF "LANE: refuse eta-eight: declared path $canon8 matches sensitive pattern */.aws" "$out8" || case_fails=1
  [ ! -e "$WT_ROOT/eta-eight" ] || case_fails=1
  report_case "working-set-refuses-symlink-into-sensitive"

  # --- Case 9: working-set-refuses-secrets-file ---
  printf 'fixture\n' >"$selftest_root/secrets.json"
  local out9="$selftest_root/out9.txt" rc9=0
  local canon9
  canon9=$(python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$selftest_root/secrets.json")
  bash "$self_path" claim --repo "$repo" --project eta --lane nine \
    --branch br-nine --base HEAD --worker w9 \
    --path "$selftest_root/secrets.json" \
    --exec true >"$out9" 2>&1 || rc9=$?
  [ "$rc9" -eq 1 ] || case_fails=1
  grep -qF "LANE: refuse eta-nine: declared path $canon9 matches sensitive pattern */secrets.json" "$out9" || case_fails=1
  [ ! -e "$WT_ROOT/eta-nine" ] || case_fails=1
  report_case "working-set-refuses-secrets-file"

  # --- Case 10: exec-scrubs-credential-env ---
  export AEP_TEST_API_KEY=not-a-real-secret
  export AEP_TEST_AUTHORITY=not-a-real-secret
  export SSH_AUTH_SOCK=/tmp/fake.sock
  export GIT_AUTHOR_NAME="Lane Test"
  local out10="$selftest_root/out10.txt" rc10=0
  bash "$self_path" claim --repo "$repo" --project theta --lane ten \
    --branch br-ten --base HEAD --worker w10 \
    --exec sh -c 'printf "%s|%s|%s|%s" "${AEP_TEST_API_KEY:-unset}" "${SSH_AUTH_SOCK:-unset}" "${GIT_AUTHOR_NAME:-unset}" "${AEP_TEST_AUTHORITY:-unset}"' >"$out10" 2>&1 || rc10=$?
  [ "$rc10" -eq 0 ] || case_fails=1
  grep -qF "unset|/tmp/fake.sock|Lane Test|unset" "$out10" || case_fails=1
  report_case "exec-scrubs-credential-env"

  # --- Case 11: full-env-opt-out-warns ---
  local out11="$selftest_root/out11.txt" err11="$selftest_root/err11.txt" rc11=0
  AEP_LANE_FULL_ENV=1 bash "$self_path" claim --repo "$repo" --project theta --lane eleven \
    --branch br-eleven --base HEAD --worker w11 \
    --exec sh -c 'printf "%s|%s|%s|%s" "${AEP_TEST_API_KEY:-unset}" "${SSH_AUTH_SOCK:-unset}" "${GIT_AUTHOR_NAME:-unset}" "${AEP_TEST_AUTHORITY:-unset}"' >"$out11" 2>"$err11" || rc11=$?
  [ "$rc11" -eq 0 ] || case_fails=1
  grep -qF "not-a-real-secret|/tmp/fake.sock|Lane Test|not-a-real-secret" "$out11" || case_fails=1
  grep -qF "LANE: warning AEP_LANE_FULL_ENV=1: worker receives the full environment (credential scrub disabled)" "$err11" || case_fails=1
  report_case "full-env-opt-out-warns"

  # --- Case 12: policy-data-malformed-refuses ---
  local bad_policy="$selftest_root/policy-bad.data"
  printf '# fixture comment\n[sensitive-paths]\nbogus line here\n' >"$bad_policy"
  local out12="$selftest_root/out12.txt" rc12=0
  AEP_POLICY_DATA="$bad_policy" bash "$self_path" claim --repo "$repo" \
    --project kappa --lane twelve \
    --branch br-twelve --base HEAD --worker w12 \
    --exec true >"$out12" 2>&1 || rc12=$?
  [ "$rc12" -eq 1 ] || case_fails=1
  grep -qF "LANE: refuse policy data invalid: line 3: bogus line here" "$out12" || case_fails=1
  [ ! -e "$WT_ROOT/kappa-twelve" ] || case_fails=1
  [ ! -f "$LANES_DIR/kappa-twelve.json" ] || case_fails=1
  report_case "policy-data-malformed-refuses"

  return "$fails"
}

case "${1:-}" in
--self-test)
  rc=0
  self_test || rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "SELF-TEST: $rc assertion(s) failed"
    exit 1
  fi
  echo "SELF-TEST: all ok"
  ;;
claim)
  shift
  cmd_claim "$@"
  ;;
release)
  shift
  cmd_release "$@"
  ;;
status)
  shift
  cmd_status "$@"
  ;;
*)
  usage
  exit 2
  ;;
esac
