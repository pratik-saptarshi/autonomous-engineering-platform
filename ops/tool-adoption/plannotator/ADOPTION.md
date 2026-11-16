# Plannotator adoption record

The adoption record for the Plannotator instance of the tool-adoption
pattern (playbook: `ops/tool-adoption/README.md`). Adopted shape:
**pinned binary operated as a local tool**. This is not a vendoring: no
Plannotator source or binary is committed to this or any repository, and
the upstream `curl | bash` installer is not used. The installer that
reproduces this adoption is `install.sh` in this directory; it performs
the verification below before installing anything.

- Adoption date: 2026-11-13
- Release: `v0.28.63`
- Release published: 2026-11-13T11:11:22Z
- Platform: Linux x86_64
- Installed binary: `~/workspace/plannotator/bin/plannotator-0.28.63-linux-x64`
- Launcher: `~/workspace/bin/plannotator`
- Local state: `~/.plannotator/`
- Pilot workspace: `~/workspace/plannotator-pilot/` (per-machine local state, not repository content)

## Provenance verification

All verification was completed before the binary was executed.

### Checksum

GitHub release asset: `plannotator-linux-x64` (214,730,928 bytes)

```text
41c00c90ecd8bd9665163671ec0d5503bb83f4251f849123faafa90543286f52
```

The downloaded file's SHA256 matched all three records checked:

1. the release's `plannotator-linux-x64.sha256` sidecar (`sha256sum -c`: OK);
2. the GitHub release asset digest returned by the API;
3. the installed copy after placement in `~/workspace/plannotator/bin/`.

### GitHub artifact attestation

Command run against the downloaded artifact:

```bash
gh attestation verify ~/workspace/plannotator/verification/plannotator-linux-x64 \
  --repo backnotprop/plannotator \
  --source-ref refs/tags/v0.28.63 \
  --signer-workflow backnotprop/plannotator/.github/workflows/release.yml
```

Result: **exit 0**. This `gh` build emitted no human-readable output on success. The source ref and signer workflow were pinned, rather than accepting provenance from any workflow in the repository.

## SBOM and Grype evidence

Each installing machine retains in `~/workspace/plannotator/verification/`:

- `plannotator-0.28.63-release-sbom.cdx.json`
- its published `.sha256` sidecar
- on the origin machine, `release-workflow-jobs.json` (release CI snapshot)

SBOM SHA256:

```text
ef1872903105dc58125701147d48ddd65d51e092e1759745f7a8b35edae1d58a
```

The sidecar check returned OK, and the digest also matched the GitHub release asset digest.

SBOM summary:

- Format: CycloneDX 1.6
- Generator: Syft 1.51.0
- Release source commit recorded in the SBOM: `f1cc5f0083804c171b451712fe5716bd197d7d9e`
- Components: 799
- Vulnerability entries embedded in the public SBOM: 0

Important limitation stated by the SBOM itself: it is a release-wide, Syft-detected monorepo locked build-input and dependency inventory, **not an exact per-binary runtime inventory**. Bun standalone executables hide JavaScript package metadata from Syft, and host-provided peers or dependencies Syft cannot parse may be absent.

No standalone Grype report is published as a release asset. The release workflow evidence is nevertheless specific: in release run `43413212378`, the `release-security` job — whose workflow step is “Generate SBOM and enforce Grype policy” — completed with conclusion **success**. The `attest` and `release` jobs also succeeded. The workflow run's overall conclusion was failure because the separate `npm-publish` job failed; the binary build, security, attestation, and release jobs did not.

- Release-security job: https://github.com/backnotprop/plannotator/actions/runs/43413212378/job/131848695979

## Hardened local configuration

The launcher at `~/workspace/bin/plannotator` execs only the pinned binary and exports:

```text
NO_ANON_PING=1
PLANNOTATOR_AI=disabled
PLANNOTATOR_SHARE=disabled
PLANNOTATOR_REMOTE=0
PLANNOTATOR_JINA=0
PLANNOTATOR_GIT_REMOTE_CHECK=0
PLANNOTATOR_AUTO_UPDATE=0
```

`~/.plannotator/config.json` also sets:

```json
{
  "autoUpdate": false,
  "gitRemoteCheck": false
}
```

Policy consequences:

- The release build's default daily anonymous ping is off. In the v0.28.63 source, `NO_ANON_PING` makes the daily-ping check return off before an endpoint request is made.
- Plannotator AI features are disabled, so this setup does not spawn agent CLIs with the operator's credentials.
- Sharing is disabled; no fragment-link or paste-service sharing should be used.
- Remote mode is forced off. This matters because SSH variables can otherwise trigger remote detection, and remote mode binds 0.0.0.0 without authentication.
- Automatic update is off in both the launcher environment and config, preserving the verified pin.
- Git-remote checks are off in both the launcher environment and config.

Accepted residual: Plannotator still performs its documented GitHub release check when a surface loads, and the evaluation found no supported opt-out for that surface-level check. It sends no plan content. This adoption does not attempt to block or patch around it.

## Smoke tests

All tests used the wrapper, not the raw binary.

| Test | Result |
|---|---|
| `plannotator --version` | Exit 0; output `plannotator 0.28.63` |
| `plannotator --help` | Exit 0; command surface printed normally |
| `plannotator sessions` | Exit 0; `No active Plannotator sessions.` |
| `plannotator data-dir` | Exit 0; reported `~/.plannotator` |
| `plannotator --browser none archive` from the pilot scratch directory | Started the empty archive surface on loopback at `http://localhost:45185`; as designed it remained in the foreground and was stopped by the test timeout after 8 seconds; `sessions` was empty afterward |

### Network behaviour observed

The archive smoke test created `~/.plannotator/update-state.json`. It recorded a release check sourced from the page and the then-latest tag `0.28.64`. The installed binary remained version 0.28.63 with the verified hash, so no automatic update occurred.

No `ping.json` was created during the CLI/archive smoke tests. Archive is not one of the modes counted by the daily-ping client; the operative proof for the hardened setup is the wrapper setting plus the source behaviour above, not the archive test alone.

No review, annotate, code-review, inbox, or plan-gate session was opened against AEP or any real repository during the adoption setup.

## Wrapper skills

The two thin wrapper skills for this instance live in this repository:

- `skills/plannotator-gate/` — SkillSpector: **score 3, LOW, SAFE, GATE PASSED**
- `skills/plannotator-inbox/` — SkillSpector: **score 7, LOW, SAFE, GATE PASSED**

## Current state

The pinned tool, hardened launcher, local configuration, wrapper skills, verification evidence, and pilot workspace are prepared on the origin machine; other machines reproduce the install with `install.sh`. No harness hook or MCP registration was installed during this adoption setup, and no human pilot session has been started. The pilot is ready for the owner's participation as approver.
