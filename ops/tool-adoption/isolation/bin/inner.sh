#!/usr/bin/env bash
# inner.sh — runs INSIDE `unshare --mount --pid --net --fork`, as root.
# Builds the sandbox root (tmpfs + declared binds only) and chroots into
# the payload. Any failure aborts before the payload exists (fail-closed):
# this script runs under `set -euo pipefail` and the payload is the last
# exec, reachable only after every mount succeeded.
set -euo pipefail

RUN_DIR=$1
SKILLS_TREE=$2
PROBES_DIR=$3
GATE_BIN=$4
ROOT=$RUN_DIR/rootfs

mount --make-rprivate /
mkdir -p "$ROOT"
mount -t tmpfs -o mode=755 tmpfs "$ROOT"

mkdir -p "$ROOT"/{usr,dev,proc,tmp,work,skills,probes,out,scratch}
ln -s usr/bin "$ROOT/bin"
ln -s usr/lib "$ROOT/lib"
ln -s usr/lib64 "$ROOT/lib64"

mount --bind /usr "$ROOT/usr"
mount -o remount,ro,bind "$ROOT/usr"

mount -t tmpfs -o mode=755 tmpfs "$ROOT/dev"
for d in null zero full random urandom tty; do
  : > "$ROOT/dev/$d"
  mount --bind "/dev/$d" "$ROOT/dev/$d"
done

mount -t proc proc "$ROOT/proc"
mount -t tmpfs -o mode=1777 tmpfs "$ROOT/tmp"

mount --bind "$RUN_DIR/worktree" "$ROOT/work"

# The skill tree is STAGED as a tmpfs copy, not bound. Reason (found in
# the 2a run, recorded in ADOPTION-ADDENDUM.md): the shared tree's files
# carry a group id that is UNMAPPED in this user namespace — it displays
# as the overflow id "nogroup 65534" — so the payload uid 65534 can
# never satisfy group permissions on it, and chmod'ing the shared tree
# itself is out of bounds. A tmpfs copy with controlled modes, remounted
# read-only and covered by the Landlock ro rule, gives the same
# read-only guarantee without touching the shared tree.
mount -t tmpfs -o mode=755,size=256M tmpfs "$ROOT/skills"
cp -a "$SKILLS_TREE/." "$ROOT/skills/"
chmod -R a+rX "$ROOT/skills"
# Read-only via the pilot's proven bind+remount pattern (a plain
# `remount,ro` on the tmpfs mountpoint failed on this util-linux).
mount --bind "$ROOT/skills" "$ROOT/skills"
mount -o remount,ro,bind "$ROOT/skills"
mount --bind "$PROBES_DIR" "$ROOT/probes"
mount -o remount,ro,bind "$ROOT/probes"
mount --bind "$RUN_DIR/out" "$ROOT/out"

cp "$RUN_DIR/payload.sh" "$ROOT/payload.sh"
# cp lands the script root:root with the runtime's restrictive umask
# modes (660-class); the payload now runs as uid 65534, so make it
# world-readable explicitly (its Landlock filero rule governs the rest).
chmod 644 "$ROOT/payload.sh"

# 2a-layer probe fixture (see ADOPTION-ADDENDUM.md): a directory whose
# DISCRETIONARY permissions fully allow the payload (dir mode 777, file
# mode 644, both root-owned) but which has NO Landlock rule beyond the
# minimal root grant — so only Landlock can deny access to it. That is
# what makes the layer probes discriminating instead of vacuous.
printf 'landlock-escape-canary\n' > "$ROOT/scratch/secret.txt"
chmod 644 "$ROOT/scratch/secret.txt"
chmod 777 "$ROOT/scratch"

# The 2a gate: static binary, copied into the root; it applies the
# Landlock ruleset + seccomp denylist, drops to uid/gid 65534, then
# execs the payload. Any gate failure exits nonzero before exec —
# the payload never runs (fail-closed).
cp "$GATE_BIN" "$ROOT/sandbox-gate"
chmod 755 "$ROOT/sandbox-gate"

cd /
exec chroot "$ROOT" /sandbox-gate \
  --uid=65534 --gid=65534 \
  --rule=/:root \
  --rule=/usr:ro \
  --rule=/proc:ro \
  --rule=/dev:dev \
  --rule=/work:rw \
  --rule=/out:rw \
  --rule=/tmp:rw \
  --rule=/skills:ro \
  --rule=/probes:ro \
  --rule=/payload.sh:filero \
  -- /bin/bash --noprofile --norc /payload.sh
