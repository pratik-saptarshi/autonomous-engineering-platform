#!/usr/bin/env bash
# Issue #22: scripts/seed-boot-guards.sh gives boot-gate.sh check 3 a setup path.
#
# A stub neurostrata-mcp backs a temp JSON store, so the real daemon and the
# real guard namespace are never touched. The flow under test:
#   empty store -> boot-gate fails naming the seed script -> seed -> boot-gate
#   prints "guards ok" -> a second run is idempotent (zero duplicates).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SEED="$ROOT/scripts/seed-boot-guards.sh"
GATE="$ROOT/scripts/boot-gate.sh"
SB="$(mktemp -d)"
trap 'rm -rf "$SB"' EXIT
FAILURES=0

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

export HOME="$SB/home"
mkdir -p "$HOME" "$SB/bin"
export STUB_STORE="$SB/store.json"

# Stub neurostrata-mcp: `status`, `list <ns>`, `add <ns> <type> <content>`.
# The store is a JSON list of {id, namespace, type, content}. STUB_DOWN=1
# makes the daemon report down.
cat >"$SB/bin/neurostrata-mcp" <<'STUB'
#!/usr/bin/env python3
import json, os, sys

store = os.environ["STUB_STORE"]
args = sys.argv[1:]


def load():
    if not os.path.exists(store):
        return []
    with open(store) as handle:
        return json.load(handle)


def save(items):
    with open(store, "w") as handle:
        json.dump(items, handle)


if not args:
    sys.exit(2)
if args[0] == "status":
    if os.environ.get("STUB_DOWN") == "1":
        print("daemon: not running")
    else:
        print("daemon: listening on 127.0.0.1:34343, answering")
    sys.exit(0)
if os.environ.get("STUB_DOWN") == "1":
    print("error: daemon unreachable")
    sys.exit(1)
if args[0] == "list":
    items = [i for i in load() if i["namespace"] == args[1]]
    print(f"Found {len(items)} memories in namespace '{args[1]}':")
    for item in items:
        print()
        print(f"--- ID: {item['id']} ---")
        print(f"Type: {item['type']}")
        print(f"Content: {item['content']}")
    sys.exit(0)
if args[0] == "add" and len(args) >= 4:
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

echo "# case 1: empty namespace fails boot-gate and names the seed script"
run with_stub bash "$GATE"
t "boot-gate fails on an empty guard namespace" "$RC" -ne 0
case "$OUT" in *"BOOT-GATE: guards FAIL"*) ok "failure names the guards check" ;; *) fail "failure names the guards check: $OUT" ;; esac
case "$OUT" in *"scripts/seed-boot-guards.sh"*) ok "failure points to scripts/seed-boot-guards.sh" ;; *) fail "failure points to scripts/seed-boot-guards.sh: $OUT" ;; esac
case "$OUT" in *"docs/runbook.md"*) ok "failure points to docs/runbook.md" ;; *) fail "failure points to docs/runbook.md: $OUT" ;; esac

echo "# case 2: --check fails and --dry-run writes nothing"
run with_stub bash "$SEED" --check
t "--check exits non-zero on an empty namespace" "$RC" -ne 0
run with_stub bash "$SEED" --dry-run
t "--dry-run exits 0" "$RC" -eq 0
case "$OUT" in *"would seed: Destructive GitHub actions"*) ok "--dry-run reports the destructive rule" ;; *) fail "--dry-run reports the destructive rule: $OUT" ;; esac
t "--dry-run left the store empty" "$(count_guards)" -eq 0

echo "# case 3: seeding makes boot-gate print guards ok"
run with_stub bash "$SEED"
t "seed exits 0" "$RC" -eq 0
t "three guard_rule memories seeded" "$(count_guards)" -eq 3
case "$(store_text)" in *"Destructive GitHub actions"*) ok "destructive rule is in the store" ;; *) fail "destructive rule is in the store" ;; esac
run with_stub bash "$GATE"
case "$OUT" in *"BOOT-GATE: guards ok"*) ok "boot-gate prints guards ok after seeding" ;; *) fail "boot-gate prints guards ok after seeding: $OUT" ;; esac
run with_stub bash "$SEED" --check
t "--check exits 0 after seeding" "$RC" -eq 0

echo "# case 4: a second run is idempotent"
before="$(store_text)"
run with_stub bash "$SEED"
t "second seed exits 0" "$RC" -eq 0
t "still exactly three guard_rule memories" "$(count_guards)" -eq 3
t "store is byte-identical after the second run" "$(store_text)" = "$before"
case "$OUT" in *"seeded:"*) fail "second run seeded something: $OUT" ;; *) ok "second run seeds nothing" ;; esac

echo "# case 5: a rule already present (live wording) is not duplicated"
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

echo "# case 6: missing neurostrata-mcp fails loudly"
rm -f "$STUB_STORE"
OUT="$(PATH="/usr/bin:/bin" bash "$SEED" 2>&1)"
RC=$?
t "missing binary exits non-zero" "$RC" -ne 0
case "$OUT" in *"FAIL"*"neurostrata-mcp"*) ok "missing binary says so" ;; *) fail "missing binary says so: $OUT" ;; esac
case "$OUT" in *"guards ok"*) fail "missing binary printed success: $OUT" ;; *) ok "missing binary never prints success" ;; esac

echo "# case 7: a down daemon fails loudly and writes nothing"
run env STUB_DOWN=1 PATH="$SB/bin:$PATH" bash "$SEED"
t "down daemon exits non-zero" "$RC" -ne 0
case "$OUT" in *"not answering"*) ok "down daemon says so" ;; *) fail "down daemon says so: $OUT" ;; esac
t "down daemon left the store empty" "$(count_guards)" -eq 0

echo "# case 8: unknown flag is a usage error"
run with_stub bash "$SEED" --bogus
t "unknown flag exits 2" "$RC" -eq 2

if [ "$FAILURES" -ne 0 ]; then
  echo "test_seed_boot_guards: $FAILURES failure(s)"
  exit 1
fi
echo "test_seed_boot_guards: ALL PASS"
