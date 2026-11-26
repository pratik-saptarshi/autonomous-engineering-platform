#!/usr/bin/env bash
# Issue #20: scripts/apply-domain-blocks.sh resolves domains at apply time,
# covers IPv6, and never reports success it did not verify.
#
# Every external command the script uses (id, getent, ip, iptables, ip6tables)
# is a stub on a private PATH, so the test never touches the real firewall,
# needs no root, and behaves the same on a runner that has real iptables.
# Stub state lives in a temp dir: the iptables stubs record rules in a file,
# the getent stub reads fixture files, and env switches select failure modes.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT/scripts/apply-domain-blocks.sh"
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
has() { # has <description> <needle>: ok when $OUT contains the needle
  case "$OUT" in *"$2"*) ok "$1" ;; *) fail "$1: output was: $OUT" ;; esac
}
lacks() { # lacks <description> <needle>: ok when $OUT does not contain it
  case "$OUT" in *"$2"*) fail "$1: output was: $OUT" ;; *) ok "$1" ;; esac
}

# --- Private tool dir: only what the script legitimately needs. ---
BASE="$SB/base"
mkdir -p "$BASE"
for tool in awk sort cat grep sed tr head env cut wc dirname touch uniq; do
  src="$(command -v "$tool")" && ln -s "$src" "$BASE/$tool"
done
ln -s "$BASH" "$BASE/bash"

# --- Stubs ---
STUBS="$SB/stubs"
STATE="$SB/state"
DNS="$SB/dns"
mkdir -p "$STUBS" "$STATE" "$DNS"
export STUB_STATE="$STATE" STUB_DNS="$DNS"

cat >"$STUBS/id" <<'EOF'
#!/usr/bin/env bash
[ "${1:-}" = "-u" ] && { echo "${STUB_UID:-0}"; exit 0; }
exit 1
EOF
cat >"$STUBS/ip" <<'EOF'
#!/usr/bin/env bash
if [ "$*" = "-6 route show default" ] && [ "${STUB_V6_ROUTE:-0}" = "1" ]; then
  echo "default via fe80::1 dev eth0 proto ra metric 100"
fi
exit 0
EOF
# getent ahostsv4 <domain> / ahostsv6 <domain>: fixtures $DNS/<domain>.v4|.v6
# hold one address per line. A v4-only host answers ahostsv6 with IPv4-mapped
# ::ffff: addresses, as glibc does.
cat >"$STUBS/getent" <<'EOF'
#!/usr/bin/env bash
db="$1"
domain="$2"
case "$db" in
ahostsv4)
  [ -s "$STUB_DNS/$domain.v4" ] || exit 2
  while read -r ip; do echo "$ip STREAM $domain"; done <"$STUB_DNS/$domain.v4"
  ;;
ahostsv6)
  if [ -s "$STUB_DNS/$domain.v6" ]; then
    while read -r ip; do echo "$ip STREAM $domain"; done <"$STUB_DNS/$domain.v6"
  elif [ -s "$STUB_DNS/$domain.v4" ]; then
    while read -r ip; do echo "::ffff:$ip STREAM $domain"; done <"$STUB_DNS/$domain.v4"
  else
    exit 2
  fi
  ;;
*) exit 2 ;;
esac
EOF
# iptables / ip6tables: `-C OUTPUT -d IP -j DROP` exits 1 unless recorded,
# `-A` records. STUB_IPT_FAIL=1 makes every call fail (exit 4).
# STUB_IPT_DROP_ADD=1 makes -A succeed without recording (verify must catch).
for fam in iptables ip6tables; do
  cat >"$STUBS/$fam" <<EOF
#!/usr/bin/env bash
file="\$STUB_STATE/$fam.rules"
touch "\$file"
[ "\${STUB_IPT_FAIL:-0}" = "1" ] && { echo "$fam: Permission denied" >&2; exit 4; }
op="\$1"
shift
rule="\$*"
case "\$op" in
-C) grep -qxF -- "\$rule" "\$file" && exit 0 || exit 1 ;;
-A)
  [ "\${STUB_IPT_DROP_ADD:-0}" = "1" ] && exit 0
  printf '%s\n' "\$rule" >>"\$file"
  ;;
*) exit 2 ;;
esac
EOF
done
chmod +x "$STUBS/"*

reset_case() {
  rm -f "$STATE"/* "$DNS"/*
  unset STUB_UID STUB_V6_ROUTE STUB_IPT_FAIL STUB_IPT_DROP_ADD AEP_BLOCK_DOMAINS
  export AEP_BLOCK_DOMAINS="alpha.example beta.example"
  printf '192.0.2.10\n' >"$DNS/alpha.example.v4"
  printf '192.0.2.20\n' >"$DNS/beta.example.v4"
}
run() { # run [PATH dir override]: run the script on the stub PATH
  OUT="$(PATH="${RUN_PATH:-$STUBS:$BASE}" "$BASH" "$SCRIPT" 2>&1)"
  RC=$?
}
rules() { cat "$STATE/$1.rules" 2>/dev/null; }
nrules() { rules "$1" | wc -l | tr -d ' '; }
SUCCESS="Domain blocks applied and verified:"

echo "# case 1: non-root fails loudly and changes nothing"
reset_case
export STUB_UID=1000
run
t "non-root exits non-zero" "$RC" -ne 0
has "non-root says it must run as root" "must run as root"
lacks "non-root never prints success" "$SUCCESS"
t "non-root added no rules" "$(nrules iptables)" -eq 0

echo "# case 2: a failing iptables fails loudly"
reset_case
export STUB_IPT_FAIL=1
run
t "failing iptables exits non-zero" "$RC" -ne 0
lacks "failing iptables never prints success" "$SUCCESS"

echo "# case 3: addresses come from DNS at apply time, never from a hardcoded list"
reset_case
run
t "dynamic v4 exits 0" "$RC" -eq 0
has "dynamic v4 prints the verified success line" "$SUCCESS alpha.example beta.example"
t "alpha resolved address is blocked" "$(rules iptables | grep -cx -- 'OUTPUT -d 192.0.2.10 -j DROP' || true)" -eq 1
t "beta resolved address is blocked" "$(rules iptables | grep -cx -- 'OUTPUT -d 192.0.2.20 -j DROP' || true)" -eq 1
t "the old hardcoded addresses are gone" "$(rules iptables | grep -c '198\.18\.111' || true)" -eq 0
t "script source holds no hardcoded 198.18 address" "$(grep -c '198\.18\.' "$SCRIPT" || true)" -eq 0

echo "# case 4: IPv6 active with AAAA records gets ip6tables rules"
reset_case
export STUB_V6_ROUTE=1
printf '2001:db8::10\n' >"$DNS/alpha.example.v6"
run
t "v6 active exits 0" "$RC" -eq 0
t "AAAA address is blocked with ip6tables" "$(rules ip6tables | grep -cx -- 'OUTPUT -d 2001:db8::10 -j DROP' || true)" -eq 1
t "IPv4-mapped answers are not blocked as v6" "$(rules ip6tables | grep -c 'ffff' || true)" -eq 0
t "v4 rules still applied" "$(nrules iptables)" -eq 2
has "v6 run prints the verified success line" "$SUCCESS"

echo "# case 5: IPv6 default route but no ip6tables fails closed"
reset_case
export STUB_V6_ROUTE=1
mkdir -p "$SB/no6"
for tool in id ip getent iptables; do ln -sf "$STUBS/$tool" "$SB/no6/$tool"; done
RUN_PATH="$SB/no6:$BASE" run
unset RUN_PATH
t "missing ip6tables exits non-zero" "$RC" -ne 0
has "missing ip6tables is named" "ip6tables"
lacks "missing ip6tables never prints success" "$SUCCESS"

echo "# case 6: a domain that resolves to nothing fails closed before any change"
reset_case
rm -f "$DNS/beta.example.v4"
run
t "empty DNS exits non-zero" "$RC" -ne 0
has "empty DNS names the domain" "beta.example"
lacks "empty DNS never prints success" "$SUCCESS"
t "empty DNS applied no rules at all" "$(nrules iptables)" -eq 0

echo "# case 7: idempotent re-run adds no duplicates"
reset_case
run
first="$(rules iptables)"
run
t "second run exits 0" "$RC" -eq 0
has "second run prints the verified success line" "$SUCCESS"
t "second run left the rule set byte-identical" "$(rules iptables)" = "$first"
t "no duplicate rules" "$(rules iptables | sort | uniq -d | wc -l | tr -d ' ')" -eq 0

echo "# case 8: AAAA records with no v6 route and no ip6tables still fail closed"
reset_case
printf '2001:db8::10\n' >"$DNS/alpha.example.v6"
RUN_PATH="$SB/no6:$BASE" run
unset RUN_PATH
t "AAAA without ip6tables exits non-zero" "$RC" -ne 0
lacks "AAAA without ip6tables never prints success" "$SUCCESS"

echo "# case 9: v6 route but no AAAA records is a warning, not a failure"
reset_case
export STUB_V6_ROUTE=1
run
t "v6 route without AAAA exits 0" "$RC" -eq 0
has "it warns that v6 is not covered" "WARNING"
t "no v6 rules were invented" "$(nrules ip6tables)" -eq 0

echo "# case 10: a rule that did not stick is caught by verification"
reset_case
export STUB_IPT_DROP_ADD=1
run
t "unverifiable rules exit non-zero" "$RC" -ne 0
lacks "unverifiable rules never print success" "$SUCCESS"
has "verification failure is reported" "VERIFY FAIL"

if [ "$FAILURES" -ne 0 ]; then
  echo "test_apply_domain_blocks: $FAILURES failure(s)"
  exit 1
fi
echo "test_apply_domain_blocks: ALL PASS"
