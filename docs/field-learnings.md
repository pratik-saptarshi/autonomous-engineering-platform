# Field Learnings

Operational lessons earned the hard way, distilled for the next person (or the next
you) who sets up or runs this platform. Each one cost at least an hour. None of them
should have.

## Validate fixes like an adversary, not a cheerleader

"Tests pass" is not validation. When reviewing someone else's fix:

1. **Map every finding to its diff hunk.** Confirm each review finding has a
   corresponding code change — not just a nearby one.
2. **Prove non-vacuity with mutation.** Deliberately break what the test guards
   (typo the fixture value, remove the guard clause) and confirm the test FAILS.
   A test that cannot fail is theater.
3. **Check for follow-up findings.** Re-list review threads after fetching latest;
   new ones may have landed after the fix.
4. **Verify thread state, not just code state.** Fixes on outdated diffs leave
   threads unresolved; branch protection blocks merge until they're resolved.
5. **Leave the working tree clean.** Revert every checkout and mutation used during
   validation. Verify with `git status`.

## Block suspicious domains at the network layer

When `/etc/hosts` is read-only and all traffic goes through an egress proxy (which
bypasses IP firewall rules), block like this:

```bash
# 1. Force direct connections so the firewall sees them:
#    add to /etc/environment and ~/.bashrc
export NO_PROXY="$NO_PROXY,dolthub.com,gastownhall-eventsapi.com"

# 2. Drop at the firewall (get IPs via getent hosts):
iptables -A OUTPUT -d 198.18.111.222 -j DROP
iptables -A OUTPUT -d 198.18.111.223 -j DROP
```

Limitations, stated plainly: no wildcard subdomain blocking (`/etc/hosts` is
read-only, the iptables string-match module is unavailable), and iptables rules
don't survive VM replacement — re-apply via `scripts/apply-domain-blocks.sh`.
If a blocked domain changes IPs, the block won't follow.

## Turn off beads telemetry

`bd` ships with anonymous usage metrics enabled. Disable it during setup:

```bash
bd metrics off
```

It only reports command names, version, and OS — but there's no reason to phone
home from an autonomous engineering environment.

## Know that Dolt phones home (a little)

`bd` is built on Dolt, and the binary contains `doltremoteapi.dolthub.com` —
Dolt's remote API endpoint. If you block `*.dolthub.com` at the network layer,
`bd` commands that touch remotes will trip the block and surface access prompts.
This is Dolt's legitimate infrastructure, not malware. Either allowlist
`doltremoteapi.dolthub.com` specifically or accept the noise.

## Route scheduled reports to topic chats

When side chats exist per topic, point each cron's delivery at the relevant one
instead of main. The main chat stays a command deck; each topic's history stays
coherent. For loops that stall on the same blockers, add a quiet-while-blocked
rule: log the run, stay silent in chat, and only report when something changed
(iterations completed, blockers cleared, new decision needed).

## Reply to review threads in-thread

When addressing Codex (or any bot) review comments on a PR, reply using the
review-thread reply mutation — never the REST issue-comment endpoint. REST
comments spawn *new* unresolved threads instead of replying in place, and branch
protection will block the merge until someone notices and resolves them. This
one bit us on PR #117; don't let it bite you.
