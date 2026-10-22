# Domain Blocks Fix (Issue #20) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `scripts/apply-domain-blocks.sh` so the egress firewall control resolves domains at apply time (never goes stale), covers IPv6, fails loudly instead of reporting false success, and is documented in the runbook.

**Architecture:** Single-file rewrite of the 10-line script. Domains map to IPs via `getent hosts`/`getent ahostsv6` at apply time; each resolved IP gets an idempotent `iptables -C || iptables -A` DROP (v4) and `ip6tables` DROP (v6); every failure exits non-zero with a diagnostic; a final verification pass re-checks each rule with `-C` before printing success. `set -euo pipefail` throughout.

**Tech Stack:** bash, iptables/ip6tables (nf_tables), getent.

**Spec:** https://github.com/pratik-saptarshi/autonomous-engineering-platform/issues/20

## Global Constraints
- Conventional Commits; commit as `Musebot-Astro <6238157+pratik-saptarshi@users.noreply.github.com>`.
- Exact-path `git add` only (no `.gitignore` in repo).
- Script must remain idempotent (safe to re-run on boot / after VM replacement).
- Requires root — document, don't assume; fail closed with a clear message when not root.
- Shellcheck-clean and `shfmt -d -i 2` clean (CI enforces both).

## Review Focus
- **Stale IPs are already live:** `getent hosts` on 2026-10-19 resolves dolthub.com→198.18.92.28 and gastownhall-eventsapi.com→198.18.92.29 — the hardcoded 198.18.111.222/223 are stale NOW, and the OUTPUT chain is currently empty (no DROP rules at all). Task 1's verification must confirm the new IPs, not the old ones.
- **IPv6 nuance:** the VM has an IPv6 default route, but neither domain publishes native AAAA records today (only IPv4-mapped `::ffff:`). The script must still install v6 rules when AAAA records exist AND fail closed with a warning when a v6 default route exists but no v6 addresses resolved — otherwise a future AAAA publication silently bypasses the control.
- **DNS failure mode:** if `getent` fails (DNS down), the script must NOT silently apply zero rules and report success — it must fail loudly. An empty IP list is an error, not a no-op.
- **Idempotency under `set -e`:** the `-C || -A` pattern must not trip `set -e` on the expected `-C` failure path (guard it explicitly).
- **The success message is a claim:** it may only print after the verification pass confirms every rule exists.

---

## File Structure

- Modify: `scripts/apply-domain-blocks.sh` — full rewrite (10 lines → ~60 lines); the only code file.
- Modify: `docs/runbook.md` — add the script to the install steps (root requirement, when to run).
- Test: live firewall verification (`iptables -S`, `ip6tables -S`) — no unit-test framework applies to a firewall script; the "tests" are the verification commands with expected rule output.

---

### Task 1: Rewrite apply-domain-blocks.sh

**Files:**
- Modify: `scripts/apply-domain-blocks.sh` (full rewrite)

**Interfaces:**
- Consumes: nothing (first task)
- Produces: `apply_blocks()` behavior — resolves `dolthub.com` and `gastownhall-eventsapi.com` at apply time, installs idempotent v4/v6 DROP rules, fails loudly on any error, verifies before reporting success. Task 2 consumes the final script for runbook documentation.

- [ ] **Step 1: Write the new script**

Replace the full contents of `scripts/apply-domain-blocks.sh` with:

```bash
#!/usr/bin/env bash
# Re-apply domain blocks for dolthub.com and gastownhall-eventsapi.com.
# These domains are force-bypassed from the egress proxy via NO_PROXY
# (see /etc/environment) and then DROPped at the firewall.
#
# IPs are resolved at apply time via getent — the domains have rotated
# addresses before (198.18.111.x -> 198.18.92.x observed 2026-10-19), so
# hardcoded IPs go stale. Run on boot / after VM replacement. Idempotent.
# REQUIRES ROOT (iptables/ip6tables).
set -euo pipefail

DOMAINS=(dolthub.com gastownhall-eventsapi.com)

[ "$(id -u)" -eq 0 ] || { echo "FATAL: must run as root (iptables requires it)" >&2; exit 1; }
command -v iptables >/dev/null || { echo "FATAL: iptables not found" >&2; exit 1; }
command -v ip6tables >/dev/null || { echo "FATAL: ip6tables not found" >&2; exit 1; }

# resolve_v4 <domain>: print one IPv4 per line, fail if none resolve
resolve_v4() {
  local ips
  ips=$(getent hosts "$1" | awk '$1 ~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ {print $1}' | sort -u)
  [ -n "$ips" ] || { echo "FATAL: no IPv4 addresses resolved for $1" >&2; return 1; }
  printf '%s\n' "$ips"
}

# resolve_v6 <domain>: print native IPv6 addresses (excluding IPv4-mapped ::ffff:) one per line; empty is OK
resolve_v6() {
  getent ahostsv6 "$1" 2>/dev/null | awk '$1 ~ /:/ && $1 !~ /^::ffff:/ {print $1}' | sort -u || true
}

apply_drop() { # $1 = iptables|ip6tables, $2 = ip
  "$1" -C OUTPUT -d "$2" -j DROP 2>/dev/null || "$1" -A OUTPUT -d "$2" -j DROP
}

V6_ROUTE=no
ip -6 route show default >/dev/null 2>&1 && V6_ROUTE=yes

for domain in "${DOMAINS[@]}"; do
  # Resolve BEFORE the loop into a checked variable: a process substitution
  # (< <(resolve_v4 ...)) would swallow resolve_v4's non-zero exit (bash does
  # not propagate it, even under set -e), so a DNS failure would silently
  # process zero IPs and the script would exit 0 claiming success.
  v4ips=$(resolve_v4 "$domain") || exit 1
  while read -r ip; do
    apply_drop iptables "$ip"
    echo "blocked (v4): $domain -> $ip"
  done <<< "$v4ips"

  v6ips=$(resolve_v6 "$domain")
  if [ -n "$v6ips" ]; then
    while read -r ip; do
      apply_drop ip6tables "$ip"
      echo "blocked (v6): $domain -> $ip"
    done <<< "$v6ips"
  elif [ "$V6_ROUTE" = yes ]; then
    echo "WARNING: IPv6 default route exists but $domain has no AAAA records — v6 not covered" >&2
  fi
done

# Verification pass: every applied rule must exist before we claim success.
failed=0
for domain in "${DOMAINS[@]}"; do
  # Same checked-variable pattern as the apply loop: never let a resolver
  # failure hide inside process substitution during verification either.
  v4ips=$(resolve_v4 "$domain") || exit 1
  while read -r ip; do
    iptables -C OUTPUT -d "$ip" -j DROP 2>/dev/null || { echo "VERIFY FAIL: v4 rule missing for $ip ($domain)" >&2; failed=1; }
  done <<< "$v4ips"
  v6ips=$(resolve_v6 "$domain") || exit 1
  if [ -n "$v6ips" ]; then
    while read -r ip; do
      ip6tables -C OUTPUT -d "$ip" -j DROP 2>/dev/null || { echo "VERIFY FAIL: v6 rule missing for $ip ($domain)" >&2; failed=1; }
    done <<< "$v6ips"
  fi
done
[ "$failed" -eq 0 ] || { echo "FATAL: verification failed — blocks NOT fully applied" >&2; exit 1; }

echo "Domain blocks applied and verified: ${DOMAINS[*]}"
```

Design notes for the implementer: the `while read` loops take their input from a checked variable via herestring (`<<< "$v4ips"`), NOT process substitution — bash does not propagate a failing command's exit status through `< <(...)`, so `resolve_v4` must run (and its failure must abort) before the loop starts; the `|| true` on the v6 resolver keeps empty results non-fatal; the v6 WARNING (not fatal) reflects that AAAA absence is currently normal.

- [ ] **Step 2: Syntax check and lint**

Run:
```bash
bash -n scripts/apply-domain-blocks.sh && echo SYNTAX-OK
```
(This environment has no shellcheck binary; CI's shell-lint job is the lint gate. If shellcheck is available via ~/go/bin or apt, run `shellcheck scripts/apply-domain-blocks.sh` too.)

- [ ] **Step 3: Test — dry-run the resolvers (no firewall changes)**

Run:
```bash
bash -c 'source <(sed -n "/^resolve_v4/,/^}/p;/^resolve_v6/,/^}/p" scripts/apply-domain-blocks.sh); resolve_v4 dolthub.com; echo ---; resolve_v6 dolthub.com; echo "(empty v6 is expected)"'
```
Expected: prints one or more IPv4 addresses for dolthub.com; v6 section empty (no native AAAA as of 2026-10-19). **Critical:** the v4 addresses must NOT be the stale 198.18.111.222/223 — if they are, DNS has flipped back; record the actual values.

- [ ] **Step 4: Test — apply as root and verify (this modifies the live firewall)**

Run (as root):
```bash
sudo ./scripts/apply-domain-blocks.sh
```
Expected: prints `blocked (v4): ...` lines, the v6 warning, and ends with `Domain blocks applied and verified: dolthub.com gastownhall-eventsapi.com`, exit 0.

- [ ] **Step 5: Test — verify rules exist and idempotency**

Run:
```bash
iptables -S OUTPUT | grep -c 'DROP' ; ./scripts/apply-domain-blocks.sh >/dev/null 2>&1; iptables -S OUTPUT | grep -c 'DROP'
```
Expected: both counts identical (second run adds no duplicates). Also: `iptables -S OUTPUT` must show DROP rules for the CURRENT resolved IPs (198.18.92.28/29 as of 2026-10-19), not the stale .111.x addresses.

- [ ] **Step 6: Test — failure mode (non-root)**

Run (as non-root, if available; otherwise simulate by temporarily... skip if only root exists — note it):
```bash
# if a non-root user exists:
su nobody -s /bin/bash -c './scripts/apply-domain-blocks.sh'
```
Expected: `FATAL: must run as root`, exit non-zero, NO success message.

- [ ] **Step 7: Commit**

```bash
git add scripts/apply-domain-blocks.sh
git commit -m "fix(scripts): resolve domain-block IPs at apply time, cover IPv6, fail loudly"
```

---

### Task 2: Document in the runbook

**Files:**
- Modify: `docs/runbook.md` (add to install steps)

**Interfaces:**
- Consumes: Task 1's rewritten script (references its path and behavior)
- Produces: runbook documents the control so fresh installs enforce it

- [ ] **Step 1: Add a runbook section**

In `docs/runbook.md`, after the binary-tools section, add:

```markdown
## Egress domain blocks

`scripts/apply-domain-blocks.sh` DROP-blocks dolthub.com and gastownhall-eventsapi.com at the firewall (they bypass the egress proxy via NO_PROXY). It resolves IPs at apply time, covers IPv4 and IPv6, and verifies every rule before reporting success.

```bash
sudo ./scripts/apply-domain-blocks.sh
# expect: "Domain blocks applied and verified: dolthub.com gastownhall-eventsapi.com"
```

Run on every boot / VM replacement — iptables rules do not survive either. Requires root.
```

- [ ] **Step 2: Verify the markdown renders (no lint breakage)**

Run: `python3 -c "print('manual check: section added under a ## heading, code fence closed')"` — plus confirm CI docs-lint will pass (the v1 baseline is lenient; a fenced block with `bash` language tag satisfies MD040 even though it's disabled).

- [ ] **Step 3: Commit and push**

```bash
git add docs/runbook.md
git commit -m "docs: document egress domain-block script in runbook"
git push origin feat/ci-platform-gates
```
Then: `gh pr checks 12 --watch` — docs-lint and shell-lint must pass.

---

## Self-Review

**1. Spec coverage:** Issue #20 lists 4 gaps. Tasks map: stale IPs→Task 1 (resolve at apply time); IPv4-only→Task 1 (ip6tables + v6-route warning); silent success→Task 1 (`set -euo pipefail`, root check, verification pass before the success message); not in runbook→Task 2. All covered.

**2. Step scan:** Each step is one action. Step 3 isolates resolver behavior without touching the firewall; Steps 4-6 are the live-firewall test cycle (apply → verify → idempotency → failure mode). No step asks the implementer to invent behavior.

**3. Type consistency:** Bash — function names (`resolve_v4`, `resolve_v6`, `apply_drop`) used consistently; `DOMAINS` array referenced uniformly.

**4. Review Focus:** The header covers all five: already-stale IPs (with the verified current values), the IPv6 nuance (v6 route exists, no AAAA today → warning not fatal), DNS-failure mode (empty list = fatal), `set -e` idempotency guard, and the success message as a verified claim.

**5. Proportion:** ~60-line script, ~150-line plan. The plan is longer because the test cycle for a firewall script (resolvers → apply → verify → idempotency → failure mode) is the actual deliverable — the steps ARE the verification the issue demands.
