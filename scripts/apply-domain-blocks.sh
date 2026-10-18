#!/bin/bash
# Re-apply domain blocks for dolthub.com and gastownhall-eventsapi.com
# These domains are force-bypassed from the egress proxy via NO_PROXY
# (see /etc/environment) and then DROPped at the firewall.
# Run on boot / after VM replacement. Idempotent.

for ip in 198.18.111.222 198.18.111.223; do
  iptables -C OUTPUT -d "$ip" -j DROP 2>/dev/null || iptables -A OUTPUT -d "$ip" -j DROP
done
echo "Domain blocks applied: dolthub.com, gastownhall-eventsapi.com"
