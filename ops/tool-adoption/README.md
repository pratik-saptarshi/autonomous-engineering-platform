# Tool adoption pattern — pinned binary, verified, hardened, piloted

How this platform adopts a third-party tool **as a tool**: operated on the
machine, never vendored into a repository. The repository carries the
*pattern* — this playbook, one installer and adoption record per tool,
and thin wrapper skills. The binary itself is never committed; each
machine installs its own verified copy.

Use this pattern when a tool is valuable but its source does not belong
in our tree: too large to vendor sanely, released too fast for a snapshot
to stay current, or supported only at its latest version. Vendoring and
forking remain the right answers for code we must modify or carry;
adoption is for instruments we merely operate.

## The pattern, in order

1. **Pin an exact version.** Never adopt "latest": a moving target
   cannot be verified, reproduced, or rolled back.
   *Why: every later step anchors to the pin.*
2. **Verify provenance before first execution.** Check the download's
   SHA256 against the publisher's checksums, run
   `gh attestation verify` with the source ref and signer workflow
   pinned, and retain the release SBOM as evidence.
   *Why: an unverified binary is untrusted code running next to the
   operator's credentials and repositories.*
3. **Harden through a launcher, not by configuration alone.** Install
   the binary under a versioned filename and put a small launcher on
   PATH that exports the safety environment on every invocation
   (telemetry off, network features off, remote modes off, auto-update
   off).
   *Why: settings held in operator memory or shell rc files drift,
   differ per machine, and vanish on a fresh VM; the launcher cannot be
   forgotten.*
4. **Write the adoption record.** One `ADOPTION.md` per tool instance:
   the pin, the checksums, the attestation result, the hardening and
   its policy consequences, the accepted residuals, and the smoke-test
   results.
   *Why: the next operator must be able to re-derive trust from the
   record instead of redoing the evaluation — or worse, trusting the
   install because it exists.*
5. **Wrap with thin skills.** Small skills encode the local policy
   around the tool — where it may be used, what it must never do, its
   failure rules — so every lane on every machine uses it the same way.
   *Why: the tool ships mechanics; the skills carry our judgement about
   them.*
6. **Pilot before real use.** A bounded trial in a scratch project,
   with named measures, beside an ungated lane for comparison. Broader
   use is a separate decision taken on the pilot's evidence.
   *Why: installation is not adoption; adoption is a decision.*

## Failure rules

- **Never execute an unverified binary.** Verification precedes the
  first run, always — including smoke tests.
- **Never run a vendor installer that scatters configuration** (hooks,
  per-agent config, shell edits). If a tool can only be installed that
  way, stop and escalate; control the integration yourself or do not
  adopt the tool.
- **Fail closed.** If verification tooling is absent and no checksum is
  pinned for the platform, the installer aborts. A warning that can be
  clicked past is not verification.
- **Loopback by default.** Never enable a tool's remote or unattended
  modes as part of adoption; a surface that binds beyond loopback is a
  stop-and-report event.
- **A version bump is a new adoption.** New pin, new verification, new
  record entries. Auto-update stays off so the pin never moves by
  itself.
- **Hardening lives in the launcher.** If a safety setting matters, it
  is exported by the launcher or it does not exist.

## Layout

```text
ops/tool-adoption/
  README.md                  this playbook
  <tool>/
    install.sh               pinned, verifying, idempotent installer
    ADOPTION.md              the adoption record for this instance
skills/<tool>-<role>/        the thin wrapper skills (step 5)
```

## Instances

- **Plannotator 0.28.63** — human decision gate for plan approvals and
  batched rulings. Installer: `plannotator/install.sh`; record:
  `plannotator/ADOPTION.md`; wrapper skills: `skills/plannotator-gate`,
  `skills/plannotator-inbox`. Status: adopted on the origin VM, pilot
  posture (see the record).

## Fresh-VM checklist

1. Clone this repository; read this playbook and the instance's
   `ADOPTION.md`, including its accepted residuals.
2. Run `ops/tool-adoption/<tool>/install.sh`. It needs `curl` or
   `wget`, a SHA256 tool, and — on platforms without a pinned checksum
   — an authenticated `gh` for attestation verification.
3. Confirm the installer's smoke tests pass and the launcher resolves
   on PATH (`plannotator --version` for the current instance).
4. Read the instance's wrapper skills before first real use; respect
   their adoption boundaries (pilot scope, if any) until a ruling
   widens them.
