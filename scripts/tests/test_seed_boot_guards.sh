#!/usr/bin/env bash
# Issue #22: scripts/seed-boot-guards.sh gives boot-gate.sh check 3 a setup path.
#
# A stub neurostrata-mcp backs a temp JSON store, so the real daemon and the
# real guard namespace are never touched. The stub enforces the real
# single-writer constraint: `add` refuses while a daemon process holds the
# store, exactly as the CLI does. The flow under test:
#   empty store -> boot-gate fails naming the seed script -> seed -> boot-gate
#   prints "guards ok" -> a second run is idempotent (zero duplicates).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SEED="$ROOT/scripts/seed-boot-guards.sh"
GATE="$ROOT/scripts/boot-gate.sh"
SB="$(mktemp -d)"
FAILURES=0

export HOME="$SB/home"
mkdir -p "$HOME/workspace/neurostrata" "$SB/bin"
export STUB_STORE="$SB/store.json"
export STUB_PIDFILE="$HOME/workspace/neurostrata/.stub-daemon.pid"

cleanup() {
  if [ -f "$STUB_PIDFILE" ]; then
    kill -TERM "$(cat "$STUB_PIDFILE")" 2>/dev/null || true
  fi
  rm -rf "$SB"
}
trap cleanup EXIT

ok() { echo "ok - $*"; }
fail() {
  echo "FAIL - $*"
  FAILURES=$((FAILURES + 1))
}
t() { # t <description> <test args...>: ok when `[ <test args> ]` holds
  local desc="$1"
  shift
  if [ "$@" ]; then ok "$desc"; else fail "$desc (rc=${RC:-})"; fi
}

# Stub neurostrata-mcp: `status`, `list <ns>`, `add <ns> <type> <content>`,
# `shutdown`, `daemon`. The store is a JSON list of
# {id, namespace, type, content}. The daemon is a real background process so
# `add` can enforce the single-writer lock the real CLI enforces.
cat >"$SB/bin/neurostrata-mcp" <<'STUB'
#!/usr/bin/env python3
import json, os, signal, sys, time

store = os.environ["STUB_STORE"]
pidfile = os.environ["STUB_PIDFILE"]
args = sys.argv[1:]


def load():
    if not os.path.exists(store):
        return []
    with open(store) as handle:
        return json.load(handle)


def save(items):
    with open(store, "w") as handle:
        json.dump(items, handle)


def daemon_pid():
    try:
        with open(pidfile) as handle:
            return int(handle.read().strip())
    except (OSError, ValueError):
        return None


def alive(pid):
    if not pid:
        return False
    try:
        with open(f"/proc/{pid}/stat") as handle:
            return handle.read().split()[2] != "Z"
    except OSError:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def daemon_up():
    return alive(daemon_pid())


if not args:
    sys.exit(2)
if args[0] == "status":
    if daemon_up():
        print("daemon: listening on 127.0.0.1:34343, answering")
        print("status: healthy")
        sys.exit(0)
    print("daemon: not running")
    sys.exit(1)
if args[0] == "shutdown":
    pid = daemon_pid()
    if alive(pid):
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            if not alive(pid):
                break
            time.sleep(0.1)
    try:
        os.remove(pidfile)
    except OSError:
        pass
    sys.exit(0)
if args[0] == "daemon":
    with open(pidfile, "w") as handle:
        handle.write(str(os.getpid()))

    def stop(_signum, _frame):
        try:
            os.remove(pidfile)
        except OSError:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    while True:
        time.sleep(0.2)
if args[0] == "list":
    items = [i for i in load() if i["namespace"] == args[1]]
    print(f"Found {len(items)} memories in namespace '{args[1]}':")
    for item in items:
        print()
        print(f"--- ID: {item['id']} ---")
        print(f"Type: {item['type']}")
        print(f"Location: N/A")
        print(f"Content: {item['content']}")
        print()
    sys.exit(0)
if args[0] == "add" and len(args) >= 4:
    if daemon_up():
        print("CRITICAL ERROR: The NeuroStrata daemon is currently running and holds the database lock.")
        print("You cannot run database-modifying CLI commands while the daemon is active.")
        sys.exit(1)
    items = load()
    items.append(
        {"id": f"m{len(items) + 1}", "namespace": args[1], "type": args[2], "content": args[3]}
    )
    save(items)
    print(f"Added memory m{len(items)}")
    sys.exit(0)
sys.exit(2)
STUB
for tool in bd ocr gh; do
  printf '#!/usr/bin/env bash\nexit 0\n' >"$SB/bin/$tool"
done
chmod +x "$SB/bin/"*
export PATH="$SB/bin:$PATH"

count_guards() { # number of guard_rule memories in the guard namespace
  python3 - "$STUB_STORE" <<'PY'
import json, os, sys
path = sys.argv[1]
items = json.load(open(path)) if os.path.exists(path) else []
print(sum(1 for i in items if i["namespace"] == "guard" and i["type"] == "guard_rule"))
PY
}
store_text() { cat "$STUB_STORE" 2>/dev/null || echo "[]"; }
run() { # run <command...> : capture combined output and rc, stub on PATH
  OUT="$("$@" 2>&1)"
  RC=$?
}
with_stub() { PATH="$SB/bin:$PATH" "$@"; }
daemon_running() { [ -f "$STUB_PIDFILE" ] && kill -0 "$(cat "$STUB_PIDFILE")" 2>/dev/null; }
start_daemon() {
  "$SB/bin/neurostrata-mcp" daemon >/dev/null 2>&1 &
  local i
  for _ in $(seq 1 50); do
    "$SB/bin/neurostrata-mcp" status >/dev/null 2>&1 && return 0
    sleep 0.1
  done
  echo "stub daemon did not start" >&2
  return 1
}
stop_daemon() {
  "$SB/bin/neurostrata-mcp" shutdown >/dev/null 2>&1 || true
  rm -f "$STUB_PIDFILE"
}

echo "# case 1: empty namespace fails boot-gate and names the seed script"
start_daemon
run with_stub bash "$GATE"
t "boot-gate fails on an empty guard namespace" "$RC" -ne 0
case "$OUT" in *"BOOT-GATE: guards FAIL"*) ok "failure names the guards check" ;; *) fail "failure names the guards check: $OUT" ;; esac
case "$OUT" in *"scripts/seed-boot-guards.sh"*) ok "failure points to scripts/seed-boot-guards.sh" ;; *) fail "failure points to scripts/seed-boot-guards.sh: $OUT" ;; esac
case "$OUT" in *"docs/runbook.md"*) ok "failure points to docs/runbook.md" ;; *) fail "failure points to docs/runbook.md: $OUT" ;; esac
stop_daemon

echo "# case 2: --check fails and --dry-run writes nothing"
run with_stub bash "$SEED" --check
t "--check exits non-zero on an empty namespace" "$RC" -ne 0
run with_stub bash "$SEED" --dry-run
t "--dry-run exits 0" "$RC" -eq 0
case "$OUT" in *"would seed: Destructive GitHub actions"*) ok "--dry-run reports the destructive rule" ;; *) fail "--dry-run reports the destructive rule: $OUT" ;; esac
t "--dry-run left the store empty" "$(count_guards)" -eq 0
t "--dry-run started no daemon" "$(daemon_running && echo yes || echo no)" = no

echo "# case 3: a stopped daemon seeds directly and stays stopped"
run with_stub bash "$SEED"
t "seed exits 0 with the daemon stopped" "$RC" -eq 0
t "three guard_rule memories seeded" "$(count_guards)" -eq 3
case "$(store_text)" in *"Destructive GitHub actions"*) ok "destructive rule is in the store" ;; *) fail "destructive rule is in the store" ;; esac
t "seeding did not start the daemon" "$(daemon_running && echo yes || echo no)" = no
start_daemon
run with_stub bash "$GATE"
case "$OUT" in *"BOOT-GATE: guards ok"*) ok "boot-gate prints guards ok after seeding" ;; *) fail "boot-gate prints guards ok after seeding: $OUT" ;; esac
stop_daemon
run with_stub bash "$SEED" --check
t "--check exits 0 after seeding" "$RC" -eq 0

echo "# case 4: a second run is idempotent"
before="$(store_text)"
run with_stub bash "$SEED"
t "second seed exits 0" "$RC" -eq 0
t "still exactly three guard_rule memories" "$(count_guards)" -eq 3
t "store is byte-identical after the second run" "$(store_text)" = "$before"
case "$OUT" in *"seeded:"*) fail "second run seeded something: $OUT" ;; *) ok "second run seeds nothing" ;; esac

echo "# case 5: a running daemon is stopped, seeded, and restarted"
rm -f "$STUB_STORE"
start_daemon
t "the stub daemon is up before seeding" "$(daemon_running && echo yes || echo no)" = yes
run with_stub bash "$SEED"
t "seed over a running daemon exits 0" "$RC" -eq 0
t "three guard_rule memories seeded" "$(count_guards)" -eq 3
t "the daemon is running again after seeding" "$(daemon_running && echo yes || echo no)" = yes
case "$OUT" in *"stopping daemon"*) ok "the stop is reported" ;; *) fail "the stop is reported: $OUT" ;; esac
case "$OUT" in *"daemon restarted"*) ok "the restart is reported" ;; *) fail "the restart is reported: $OUT" ;; esac
if command -v flock >/dev/null 2>&1; then
  if flock -n "$HOME/workspace/neurostrata/.seed-guards.lock" -c true 2>/dev/null; then
    ok "the restarted daemon does not hold the seed lock"
  else
    fail "the restarted daemon retains the seed lock"
  fi
else
  ok "flock unavailable; seed-lock inheritance not checked"
fi
stop_daemon

echo "# case 6: a rule already present (live wording) is not duplicated"
rm -f "$STUB_STORE"
python3 - "$STUB_STORE" <<'PY'
import json, sys
json.dump(
    [
        {
            "id": "m1",
            "namespace": "guard",
            "type": "guard_rule",
            "content": "Destructive GitHub actions — each require explicit authorization.",
        }
    ],
    open(sys.argv[1], "w"),
)
PY
run with_stub bash "$SEED"
t "seed over a partial namespace exits 0" "$RC" -eq 0
t "partial namespace topped up to three" "$(count_guards)" -eq 3
n_destructive="$(store_text | grep -o 'Destructive GitHub actions' | wc -l | tr -d ' ')"
t "destructive rule not duplicated" "$n_destructive" -eq 1

echo "# case 7: missing neurostrata-mcp fails loudly"
rm -f "$STUB_STORE"
OUT="$(PATH="/usr/bin:/bin" bash "$SEED" 2>&1)"
RC=$?
t "missing binary exits non-zero" "$RC" -ne 0
case "$OUT" in *"FAIL"*"neurostrata-mcp"*) ok "missing binary says so" ;; *) fail "missing binary says so: $OUT" ;; esac
case "$OUT" in *"guards ok"*) fail "missing binary printed success: $OUT" ;; *) ok "missing binary never prints success" ;; esac

echo "# case 8: unknown flag is a usage error"
run with_stub bash "$SEED" --bogus
t "unknown flag exits 2" "$RC" -eq 2

echo "# case 9: an ordinary memory that mentions the guard phrases does not satisfy the gate"
rm -f "$STUB_STORE"
python3 - "$STUB_STORE" <<'PY'
import json, sys
json.dump(
    [
        {
            "id": f"d{n}",
            "namespace": "guard",
            "type": "fact",
            "content": "guard_rule: Destructive GitHub actions are handled by another tool",
        }
        for n in range(1, 4)
    ],
    open(sys.argv[1], "w"),
)
PY
start_daemon
run with_stub bash "$GATE"
t "three non-guard memories do not pass boot-gate" "$RC" -ne 0
case "$OUT" in *"BOOT-GATE: guards FAIL"*) ok "boot-gate still fails on the decoy memories" ;; *) fail "boot-gate still fails on the decoy memories: $OUT" ;; esac
stop_daemon
run with_stub bash "$SEED" --check
t "--check fails on the decoy memories" "$RC" -ne 0
run with_stub bash "$SEED"
t "seeding over the decoy memories exits 0" "$RC" -eq 0
t "three real guard_rule memories exist" "$(count_guards)" -eq 3
start_daemon
run with_stub bash "$GATE"
case "$OUT" in *"BOOT-GATE: guards ok"*) ok "boot-gate passes after real rules are seeded" ;; *) fail "boot-gate passes after real rules are seeded: $OUT" ;; esac
stop_daemon

if [ "$FAILURES" -ne 0 ]; then
  echo "test_seed_boot_guards: $FAILURES failure(s)"
  exit 1
fi
echo "test_seed_boot_guards: ALL PASS"
