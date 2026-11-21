# Boot-gate policy runbook

`scripts/boot-gate.sh` fails closed on policy: when no policy file exists at
the configured path (`AEP_POLICY_DATA`, else the `policy.data` beside the
script), the gate prints `BOOT-GATE: policy FAIL: no policy data at ...` and
exits 1. A host without policy is refused, never waved through. Out-of-repo
cron/VM callers that previously proceeded on the old SKIP path now hard-fail;
that is the intended contract — treat the failure as the gate doing its job.

## Break-glass: bring a policy-less host back

1. Confirm the failure is really a missing policy file: the FAIL line names
   the exact path the gate looked at.
2. Preferred fix — restore the policy file from git: `git status` in the
   checkout, then restore `scripts/policy.data` from `HEAD` so the working
   tree matches the committed blob (an uncommitted policy edit fails the gate
   by design).
3. If the host has no checkout (installed copy, bare cron host): a copied
   policy file cannot restore service on its own — the gate hashes the
   policy against the committed blob it reads with git from the script's
   own directory, so a checkout-less copy fails closed with `cannot read
   committed scripts/policy.data via git` even when the copy is
   byte-identical, and pointing `AEP_POLICY_DATA` at the copy does not
   change that. Provision a trusted checkout on the host instead (clone or
   fetch the repo at the trusted commit), restore `scripts/policy.data`
   there as in step 2, and invoke the gate from that checkout.
4. Re-run `bash scripts/boot-gate.sh` and confirm the fifth check line is
   `BOOT-GATE: policy ok: ...` with the `BOOT-GATE-RESULT: POLICY-OK` token.

## Emergency override

`AEP_POLICY_DATA` pointing at a reviewed policy file lets the gate run while
the checkout is repaired. Do not leave the override as the steady state:
commit the policy file into the host's checkout so the working tree again
matches the committed blob the gate hashes against.
