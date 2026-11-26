#!/usr/bin/env bash
# apply-domain-blocks.sh: DROP egress to a set of domains at the firewall.
#
# The domains (default dolthub.com and gastownhall-eventsapi.com, override
# with AEP_BLOCK_DOMAINS as a space-separated list) are bypassed from the
# egress proxy via NO_PROXY (see /etc/environment) and then dropped here.
#
# Addresses are resolved at apply time with `getent ahostsv4` and
# `getent ahostsv6`, never read from a hardcoded list, because the provider
# addresses rotate. A DROP rule is only as good as the DNS answer it was
# built from, so re-run this script after a DNS rotation and on every boot or
# VM replacement. Rules this script added for addresses that have rotated away
# are removed on the next run (the managed set is kept in
# $AEP_BLOCK_STATE_DIR, default /run/aep-domain-blocks), so an address that is
# later reused by an unrelated service is not left blocked.
#
# Drops are inserted at the head of OUTPUT (`-I OUTPUT 1`), not appended, so an
# earlier ACCEPT rule cannot match a blocked destination first. Verification
# checks both that the DROP exists and that it sits before the first ACCEPT
# rule in OUTPUT.
#
# IPv6 is covered when the host has an IPv6 default route or any domain
# publishes an AAAA record. In that case ip6tables is required, and a missing
# or failing ip6tables is an error, not a skip. `ip` is required so the IPv6
# default route is always checked; without it the script fails closed rather
# than assuming the host is IPv4-only.
#
# It fails closed. It exits non-zero, prints nothing that looks like success,
# and changes nothing when it is not root, a tool is missing, or a domain
# resolves to no address at all. Rule application is transactional: if any
# insert or verification fails, every rule added by this run is removed before
# exiting. Concurrent runs are serialized with flock. Every rule is re-checked
# with `-C` and ordered against OUTPUT's ACCEPT rules after it is applied, and
# the success line prints only when every check passes.
#
# REQUIRES ROOT (iptables and ip6tables). Idempotent: safe to run again.
set -euo pipefail

die() { # $1 = reason
  echo "FATAL: $1" >&2
  exit 1
}

[ "$(id -u)" -eq 0 ] || die "must run as root (iptables and ip6tables require it)"
command -v getent >/dev/null 2>&1 || die "getent not found, cannot resolve domains"
command -v iptables >/dev/null 2>&1 || die "iptables not found"
command -v ip >/dev/null 2>&1 ||
  die "ip not found, cannot check for an IPv6 default route (refusing to assume IPv4-only)"
command -v flock >/dev/null 2>&1 || die "flock not found, cannot serialize firewall changes"

read -r -a DOMAINS <<<"${AEP_BLOCK_DOMAINS:-dolthub.com gastownhall-eventsapi.com}"
[ "${#DOMAINS[@]}" -gt 0 ] || die "no domains to block (AEP_BLOCK_DOMAINS is empty)"

STATE_DIR="${AEP_BLOCK_STATE_DIR:-/run/aep-domain-blocks}"
STATE_FILE="$STATE_DIR/managed-rules"
mkdir -p "$STATE_DIR" || die "cannot create state directory $STATE_DIR"

# Serialize the whole check/insert/remove/verify sequence: two overlapping
# runs would otherwise both see a missing rule with -C and both insert it.
exec 9>"$STATE_DIR/lock" || die "cannot open lock file $STATE_DIR/lock"
flock -w 60 9 || die "another apply-domain-blocks run is still holding the lock"

ADDED=""
CURRENT_PAIRS=""
PREV_PAIRS=""
TMP_STATE=""
COMMITTED=0

cleanup() {
  local rc=$?
  trap - EXIT
  # Failed before the block set was verified: undo only the rules this run
  # inserted. Reordered pre-existing rules are left alone (they still block).
  if [ "$rc" -ne 0 ] && [ "$COMMITTED" -ne 1 ] && [ -n "$ADDED" ] && [ -s "$ADDED" ]; then
    while read -r tool ip; do
      [ -n "$tool" ] || continue
      "$tool" -D OUTPUT -d "$ip" -j DROP 2>/dev/null || true
    done <"$ADDED"
    echo "ROLLBACK: removed rules added by this failed run" >&2
  fi
  if [ -n "$ADDED" ]; then rm -f "$ADDED"; fi
  if [ -n "$CURRENT_PAIRS" ]; then rm -f "$CURRENT_PAIRS"; fi
  if [ -n "$PREV_PAIRS" ]; then rm -f "$PREV_PAIRS"; fi
  if [ -n "$TMP_STATE" ]; then rm -f "$TMP_STATE"; fi
  exit "$rc"
}
trap cleanup EXIT

# One IPv4 address per line. Empty output means no A record.
resolve_v4() {
  { getent ahostsv4 "$1" 2>/dev/null || true; } |
    awk '$1 ~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ {print $1}' | sort -u
}

# One native IPv6 address per line. IPv4-mapped (::ffff:) answers are the
# resolver's rendering of an A record, not an AAAA record, so they are dropped.
resolve_v6() {
  { getent ahostsv6 "$1" 2>/dev/null || true; } |
    awk '$1 ~ /:/ && tolower($1) !~ /^::ffff:/ {print $1}' | sort -u
}

# Phase 1: resolve every domain before touching the firewall, so a DNS failure
# leaves the host exactly as it was.
RULES=""
NO_AAAA=""
ANY_AAAA=no
for domain in "${DOMAINS[@]}"; do
  v4=$(resolve_v4 "$domain")
  v6=$(resolve_v6 "$domain")
  if [ -z "$v4" ] && [ -z "$v6" ]; then
    die "$domain resolved to no addresses, refusing to continue (nothing was applied)"
  fi
  while read -r ip; do
    if [ -n "$ip" ]; then RULES="$RULES"$'\n'"iptables $ip $domain"; fi
  done <<<"$v4"
  if [ -n "$v6" ]; then
    ANY_AAAA=yes
    while read -r ip; do
      if [ -n "$ip" ]; then RULES="$RULES"$'\n'"ip6tables $ip $domain"; fi
    done <<<"$v6"
  else
    NO_AAAA="$NO_AAAA $domain"
  fi
done

# The managed set is the (tool, address) pair, not the domain, because one
# address can answer for several domains.
CURRENT_PAIRS="$(mktemp "$STATE_DIR/.current.XXXXXX")"
while read -r tool ip _domain; do
  [ -n "$tool" ] && printf '%s %s\n' "$tool" "$ip"
done <<<"$RULES" | sort -u >"$CURRENT_PAIRS"

PREV_PAIRS="$(mktemp "$STATE_DIR/.previous.XXXXXX")"
if [ -f "$STATE_FILE" ]; then
  cp "$STATE_FILE" "$PREV_PAIRS"
else
  : >"$PREV_PAIRS"
fi

V6_ROUTE=no
if [ -n "$(ip -6 route show default 2>/dev/null || true)" ]; then V6_ROUTE=yes; fi

if [ "$V6_ROUTE" = yes ] || [ "$ANY_AAAA" = yes ]; then
  command -v ip6tables >/dev/null 2>&1 ||
    die "IPv6 is active (default route or AAAA records) but ip6tables is missing (nothing was applied)"
  for domain in $NO_AAAA; do
    echo "WARNING: IPv6 is active but $domain has no AAAA record, so no IPv6 rule was added. Re-run after DNS changes." >&2
  done
fi

# Line number of the DROP for $2 in OUTPUT, or empty when absent. `-S` renders
# IPv4 as a /32 and IPv6 as a /128, so the optional prefix is part of the match.
rule_position() { # $1 = iptables|ip6tables, $2 = ip
  "$1" -S OUTPUT 2>/dev/null | awk -v ip="$2" '
    $0 ~ "-d " ip "(/[0-9]+)? -j DROP$" { print NR; exit }
  '
}

first_accept_position() { # $1 = iptables|ip6tables
  "$1" -S OUTPUT 2>/dev/null | awk '/-j ACCEPT$/ { print NR; exit }'
}

ordered_before_accept() { # $1 = tool, $2 = ip; true when the DROP precedes every ACCEPT
  local pos accept
  pos="$(rule_position "$1" "$2")"
  [ -n "$pos" ] || return 1
  accept="$(first_accept_position "$1")"
  [ -z "$accept" ] || [ "$pos" -lt "$accept" ]
}

# Phase 2: apply. `-C` exits 1 when the rule is absent, anything else is a real
# error and must not be mistaken for "absent". Insert at the head so no earlier
# ACCEPT can swallow the traffic; an existing rule that sits after an ACCEPT is
# moved to the head.
apply_drop() { # $1 = iptables|ip6tables, $2 = ip
  local rc=0
  "$1" -C OUTPUT -d "$2" -j DROP 2>/dev/null || rc=$?
  case "$rc" in
  0)
    ordered_before_accept "$1" "$2" && return 0
    "$1" -D OUTPUT -d "$2" -j DROP 2>/dev/null ||
      die "$1 -D failed while reordering $2"
    "$1" -I OUTPUT 1 -d "$2" -j DROP ||
      die "$1 -I failed while reordering $2"
    echo "reordered drop ahead of OUTPUT accept rules: $2" >&2
    ;;
  1)
    ADDED="${ADDED:-$(mktemp "$STATE_DIR/.added.XXXXXX")}"
    "$1" -I OUTPUT 1 -d "$2" -j DROP || die "$1 -I failed for $2"
    printf '%s %s\n' "$1" "$2" >>"$ADDED"
    ;;
  *) die "$1 -C failed for $2 (exit $rc)" ;;
  esac
}

while read -r tool ip domain; do
  [ -n "$tool" ] || continue
  apply_drop "$tool" "$ip"
  family=v6
  if [ "$tool" = iptables ]; then family=v4; fi
  echo "blocked ($family): $domain -> $ip"
done <<<"$RULES"

# Phase 3: verify presence and effective ordering. The success line is a claim,
# so only a passing re-check of every rule may print it.
failed=0
while read -r tool ip _domain; do
  [ -n "$tool" ] || continue
  if ! "$tool" -C OUTPUT -d "$ip" -j DROP 2>/dev/null; then
    echo "VERIFY FAIL: $tool rule missing for $ip" >&2
    failed=1
  elif ! ordered_before_accept "$tool" "$ip"; then
    echo "VERIFY FAIL: $tool rule for $ip is not ahead of OUTPUT's ACCEPT rules" >&2
    failed=1
  fi
done <<<"$RULES"
[ "$failed" -eq 0 ] || die "verification failed, blocks are NOT fully applied"

# The verified set is committed; a later reconciliation failure must not roll
# the working drops back out.
COMMITTED=1

# Phase 4: reconcile. Remove a managed DROP only when this script installed it
# (it is in the previous managed set) and the address is no longer a current
# DNS answer. Rules we never managed are left alone.
while read -r tool ip; do
  [ -n "$tool" ] || continue
  grep -qxF -- "$tool $ip" "$CURRENT_PAIRS" && continue
  command -v "$tool" >/dev/null 2>&1 || continue
  if "$tool" -C OUTPUT -d "$ip" -j DROP 2>/dev/null; then
    if "$tool" -D OUTPUT -d "$ip" -j DROP 2>/dev/null; then
      echo "unblocked (rotated away): $ip"
    else
      die "could not remove the stale $tool drop for $ip (current blocks are in place)"
    fi
  fi
done <"$PREV_PAIRS"

TMP_STATE="$(mktemp "$STATE_DIR/.state.XXXXXX")"
sort -u "$CURRENT_PAIRS" >"$TMP_STATE"
mv -f "$TMP_STATE" "$STATE_FILE"

echo "Domain blocks applied and verified: ${DOMAINS[*]}"
