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
# VM replacement. Rules for addresses that have rotated away are left in
# place, which is harmless.
#
# IPv6 is covered when the host has an IPv6 default route or any domain
# publishes an AAAA record. In that case ip6tables is required, and a missing
# or failing ip6tables is an error, not a skip.
#
# It fails closed. It exits non-zero, prints nothing that looks like success,
# and changes nothing when it is not root, a tool is missing, or a domain
# resolves to no address at all. Every rule is re-checked with `-C` after it
# is applied, and the success line prints only when every check passes.
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

read -r -a DOMAINS <<<"${AEP_BLOCK_DOMAINS:-dolthub.com gastownhall-eventsapi.com}"
[ "${#DOMAINS[@]}" -gt 0 ] || die "no domains to block (AEP_BLOCK_DOMAINS is empty)"

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

V6_ROUTE=no
if command -v ip >/dev/null 2>&1; then
  if [ -n "$(ip -6 route show default 2>/dev/null || true)" ]; then V6_ROUTE=yes; fi
else
  echo "WARNING: ip not found, IPv6 default route not checked (AAAA records still are)" >&2
fi

if [ "$V6_ROUTE" = yes ] || [ "$ANY_AAAA" = yes ]; then
  command -v ip6tables >/dev/null 2>&1 ||
    die "IPv6 is active (default route or AAAA records) but ip6tables is missing (nothing was applied)"
  for domain in $NO_AAAA; do
    echo "WARNING: IPv6 is active but $domain has no AAAA record, so no IPv6 rule was added. Re-run after DNS changes." >&2
  done
fi

# Phase 2: apply. `-C` exits 1 when the rule is absent, anything else is a real
# error and must not be mistaken for "absent".
apply_drop() { # $1 = iptables|ip6tables, $2 = ip
  local rc=0
  "$1" -C OUTPUT -d "$2" -j DROP 2>/dev/null || rc=$?
  case "$rc" in
  0) ;;
  1) "$1" -A OUTPUT -d "$2" -j DROP || die "$1 -A failed for $2" ;;
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

# Phase 3: verify. The success line is a claim, so only a passing re-check of
# every rule may print it.
failed=0
while read -r tool ip domain; do
  [ -n "$tool" ] || continue
  if ! "$tool" -C OUTPUT -d "$ip" -j DROP 2>/dev/null; then
    echo "VERIFY FAIL: $tool rule missing for $ip ($domain)" >&2
    failed=1
  fi
done <<<"$RULES"
[ "$failed" -eq 0 ] || die "verification failed, blocks are NOT fully applied"

echo "Domain blocks applied and verified: ${DOMAINS[*]}"
