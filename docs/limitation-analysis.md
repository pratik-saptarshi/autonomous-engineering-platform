# Limitation analysis

Root-cause analysis of the five documented platform limitations, performed 2026-10-16 using evidence-based investigation: every claim below was verified against the live environment before being recorded. Each item carries its resolution status.

## 1. Daemon supervision — mitigated

**Root cause.** No user D-Bus exists in this environment (`DBUS_SESSION_BUS_ADDRESS` and `XDG_RUNTIME_DIR` are empty; `systemctl --user` fails), so the shipped systemd user units can never activate. The daemon runs under `nohup`.

**Worse finding.** The dead backup timer meant the database had never been backed up: a corrupt `ladybug.db` would have been unrecoverable.

**Resolution.** A watchdog cron (`neurostrata-watchdog`, every 2 h) revives a dead daemon via direct `nohup` restart (an MCP-spawn revive was tried and found unreliable — the stdio server hangs without starting the daemon) and takes change-detected backups: the DB is checksummed, and only on change is the daemon SIGTERMed for a checkpoint-consistent copy (sha256-verified), restarted, and the copy uploaded to Google Drive (`Musebot-Astro/database`). The shipped `backup.sh` requires systemd and could not be used; `scripts/watchdog-backup.sh` in this repo is the nohup-aware equivalent.

## 2. TLS-intercepting proxy vs model downloads — mitigated

**Root cause.** Dependency chain: fastembed 7.0.1 → hf-hub 0.5.0 → ureq 3.4.2 with rustls + `webpki-roots` only. No `rustls-native-certs` is linked into the download path, so `SSL_CERT_FILE` is never consulted; requests reach the proxy, then verification of huggingface.co fails against the embedded Mozilla roots. The server works today purely because the model cache is warm.

**Resolution.** The pre-seeded cache is kept as a compressed backup in the workspace (`model-cache-backup.tar.gz`, sha256-recorded), and `HF_HUB_OFFLINE=1` is set on the daemon and the MCP client spawn environment, so a cache miss fails fast with a clear error instead of an opaque TLS failure. Patching the TLS stack was rejected as disproportionate (week-scale effort, supply-chain burden).

## 3. Gateway persistence — mitigated

**Root cause.** The open-connector gateway was entirely manually managed: PID file and logs in ephemeral `/tmp`, no unit file, no restart policy, and `oc.py` did not auto-start. It was found stopped, with all 19,526 actions unavailable.

**Resolution.** `oc.py` now probes the gateway on every invocation and auto-starts it via `start.sh` on connection failure (verified by stopping the gateway and watching it recover). A systemd unit remains the long-term option once linger can be verified from a privileged session.

## 4. Egress guard — mitigated

**Root cause.** Corrected mental model: the guard is a DNS-classification SSRF policy, not a hostname firewall. `OOMOL_CONNECT_EGRESS_TRUSTED_HOSTS` is only the split-DNS escape hatch, read once at gateway bootstrap; it was unset in the environment and absent from all shell rc files.

**Resolution.** The allowlist lives in `egress-allowlist.conf` (one host per line), which `start.sh` reads on every start unless the variable is already set. Deterministic across restarts; documented per host.

## 5. `bd doctor` in embedded mode — accepted

**Root cause.** Deliberate upstream policy, not a bug: `doctor.go` routes DB-layer checks through a stub in embedded mode because they need `RawDBAccessor`, which only the server-mode store implements. The three working checks use the portable `Storage` interface.

**Resolution.** Accepted as a limitation. The realistic failure modes for this deployment (single agent, per-repo partitions) are covered by the working checks plus the open-time schema guard.

## Prioritization used

Ordered by impact per unit effort: (1) watchdog + backups — the unrecoverable-DB risk was the single scariest finding; (2) gateway auto-start — the gateway was down at analysis time; (3) cache backup + offline mode — cheap insurance against total memory outage; (4) allowlist config — removes recurring friction; (5) doctor runbook — lowest urgency.
