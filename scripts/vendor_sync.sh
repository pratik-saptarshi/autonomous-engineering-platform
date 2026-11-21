#!/usr/bin/env bash
# Helpers for the AEP vendor fork migration. Every command is local and
# auditable; external gh pushes are performed by the controller, never here.
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
usage: vendor_sync.sh <command> [args]
  verify-sha EXPECTED ACTUAL
  merge-forward REPO_DIR MIRROR_REF WORKING_BRANCH MSG
  assert-ancestors REPO_DIR WORKING_BRANCH SHA...
  assert-content REPO_DIR WORKING_BRANCH FILE PATTERN
  mirror-ff REPO_DIR MIRROR_BRANCH MIRROR_REF
  backup REPO_DIR TREE MIRROR_SHA WORKING_SHA BUNDLE_PATH
  rollback-plan TREE MIRROR_BRANCH WORKING_BRANCH
EOF
  exit 2
}

[ $# -ge 1 ] || usage
cmd=$1
shift

case "$cmd" in
verify-sha)
  [ $# -eq 2 ] || usage
  expected=$1 actual=$2
  if [ "$expected" != "$actual" ]; then
    echo "verify-sha: expected $expected, got $actual" >&2
    exit 1
  fi
  echo "verify-sha: OK $actual"
  ;;
merge-forward)
  [ $# -eq 4 ] || usage
  repo=$1 mirror_ref=$2 working=$3 msg=$4
  git -C "$repo" checkout -q "$working"
  git -C "$repo" merge --no-ff -q -m "$msg" "$mirror_ref"
  echo "merge-forward: merged $mirror_ref into $working"
  ;;
assert-ancestors)
  [ $# -ge 3 ] || usage
  repo=$1 working=$2
  shift 2
  for sha in "$@"; do
    if ! git -C "$repo" merge-base --is-ancestor "$sha" "$working"; then
      echo "assert-ancestors: $sha is not an ancestor of $working" >&2
      exit 1
    fi
  done
  echo "assert-ancestors: OK ($# commits)"
  ;;
assert-content)
  [ $# -eq 4 ] || usage
  repo=$1 working=$2 file=$3 pattern=$4
  content=$(git -C "$repo" show "$working:$file")
  if [[ "$content" != *"$pattern"* ]]; then
    echo "assert-content: '$pattern' missing from $file on $working" >&2
    exit 1
  fi
  echo "assert-content: OK ($file contains $pattern)"
  ;;
mirror-ff)
  [ $# -eq 3 ] || usage
  repo=$1 mirror=$2 ref=$3
  git -C "$repo" checkout -q "$mirror"
  git -C "$repo" merge --ff-only -q "$ref"
  echo "mirror-ff: $mirror now at $(git -C "$repo" rev-parse "$mirror")"
  ;;
backup)
  [ $# -eq 5 ] || usage
  repo=$1 tree=$2 mirror_sha=$3 working_sha=$4 bundle=$5
  case "$bundle" in /*) ;; *) bundle="$PWD/$bundle" ;; esac
  # Tags BEFORE the bundle: a bundle captures the refs that exist when it is
  # created, and the rollback restore clones from the bundle and resolves
  # these tags -- a bundle made first can never contain them.
  for spec in "backup/pre-sync-$tree-mirror $mirror_sha" "backup/pre-sync-$tree-working $working_sha"; do
    tag=${spec% *}
    sha=${spec#* }
    if existing=$(git -C "$repo" rev-parse -q --verify "refs/tags/$tag" 2>/dev/null); then
      if [ "$existing" != "$sha" ]; then
        echo "backup: tag $tag already exists at $existing, not $sha; delete it manually to re-backup a different state" >&2
        exit 1
      fi
    else
      git -C "$repo" tag "$tag" "$sha"
    fi
  done
  git -C "$repo" bundle create "$bundle" --all >/dev/null
  heads=$(git bundle list-heads "$bundle")
  for ref in "refs/tags/backup/pre-sync-$tree-mirror" "refs/tags/backup/pre-sync-$tree-working"; do
    if ! grep -q "$ref" <<<"$heads"; then
      echo "backup: $ref missing from bundle $bundle" >&2
      exit 1
    fi
  done
  echo "backup: tags created before bundle; both tag refs verified in $bundle"
  ;;
rollback-plan)
  [ $# -eq 3 ] || usage
  tree=$1 mirror=$2 working=$3
  cat <<EOF
# Rollback plan for $tree (run only on explicit owner authorization)
revert working branch:
  git revert --no-edit -m 1 <merge-commit-sha> && git push origin $working
restore mirror from bundle (destructive; separate authorization):
  git clone --mirror /Users/neo/Git-SCM/.vendor-backups/2026-11-19/vendor-backup-$tree-2026-11-19.git/pre-sync-$tree-2026-11-19.bundle restore-$tree.git
  git -C restore-$tree.git push --force https://github.com/pratik-saptarshi/$tree.git backup/pre-sync-$tree-mirror:refs/heads/$mirror
verify: gh api repos/pratik-saptarshi/$tree/compare/<pre-sync-sha>...$mirror
EOF
  ;;
*)
  usage
  ;;
esac
