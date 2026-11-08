#!/usr/bin/env bash
# package-vm.sh — packages autonomous engineering platform runtime, bundle,
# and provisioning units for Linux VM targets (amd64 and arm64).
set -euo pipefail

OS="${1:-linux}"
ARCH="${2:-amd64}"
BINARY="${3:-dist/bin/aep-linux-${ARCH}}"
OUT_DIR="${4:-dist/vm/${OS}-${ARCH}}"

mkdir -p "${OUT_DIR}/bin" "${OUT_DIR}/systemd" "${OUT_DIR}/config"

# 1. Copy the targeted AEP binary
cp "${BINARY}" "${OUT_DIR}/bin/aep"
chmod 755 "${OUT_DIR}/bin/aep"

# 2. Hardware profile configuration
if [ "${ARCH}" = "arm64" ]; then
  cat <<'EOF' >"${OUT_DIR}/config/hardware-profile.conf"
# Hardware Profile: Muse Embedded Server VM (ARM64, <= 8GB RAM)
AEP_HARDWARE_TIER=muse-embedded-8gb
AEP_MAX_LANES=2
AEP_MEM_PREFLIGHT_MB=384
AEP_ONNX_THREADS=2
AEP_SUBAGENT_WORKER_CAP=2
EOF
else
  cat <<'EOF' >"${OUT_DIR}/config/hardware-profile.conf"
# Hardware Profile: Linux Server VM (x86_64, Standard/High Memory)
AEP_HARDWARE_TIER=server-vm-x86_64
AEP_MAX_LANES=6
AEP_MEM_PREFLIGHT_MB=512
AEP_ONNX_THREADS=4
AEP_SUBAGENT_WORKER_CAP=6
EOF
fi

# 3. Systemd Service Unit
cat <<'EOF' >"${OUT_DIR}/systemd/aep-ralph.service"
[Unit]
Description=Autonomous Engineering Platform (Ralph Execution Loop)
After=network.target

[Service]
Type=simple
EnvironmentFile=-/etc/aep/hardware-profile.conf
ExecStartPre=/usr/local/bin/aep boot
ExecStart=/usr/local/bin/aep supervisor --loop
Restart=on-failure
RestartSec=10s
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

# 4. Systemd Timer Unit (Scheduled 2-hour interval)
cat <<'EOF' >"${OUT_DIR}/systemd/aep-ralph.timer"
[Unit]
Description=Run Autonomous Engineering Platform Loop Every 2 Hours

[Timer]
OnBootSec=5min
OnUnitActiveSec=2h
Persistent=true

[Install]
WantedBy=timers.target
EOF

# 5. Cloud-init user data configuration for VM provisioning
cat <<EOF >"${OUT_DIR}/user-data.yaml"
#cloud-config
package_update: true
packages:
  - curl
  - git
  - tar
  - jq

write_files:
  - path: /etc/aep/hardware-profile.conf
    permissions: '0644'
    content: |
$(sed 's/^/      /' "${OUT_DIR}/config/hardware-profile.conf")

runcmd:
  - install -m 755 /tmp/aep /usr/local/bin/aep
  - cp /tmp/aep-ralph.service /etc/systemd/system/
  - cp /tmp/aep-ralph.timer /etc/systemd/system/
  - systemctl daemon-reload
  - systemctl enable --now aep-ralph.timer
EOF

# 6. Single-command installer script for existing VMs
cat <<'EOF' >"${OUT_DIR}/install.sh"
#!/usr/bin/env bash
set -euo pipefail

echo "=== Installing Autonomous Engineering Platform ==="
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

sudo install -m 755 "${DIR}/bin/aep" /usr/local/bin/aep
sudo mkdir -p /etc/aep
sudo cp "${DIR}/config/hardware-profile.conf" /etc/aep/

if command -v systemctl >/dev/null 2>&1; then
  sudo cp "${DIR}/systemd/aep-ralph.service" /etc/systemd/system/
  sudo cp "${DIR}/systemd/aep-ralph.timer" /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now aep-ralph.timer
  echo "AEP installed and systemd service/timer activated."
else
  echo "AEP installed to /usr/local/bin/aep (systemd not found)."
fi

/usr/local/bin/aep info
/usr/local/bin/aep boot
EOF
chmod 755 "${OUT_DIR}/install.sh"

# 7. Create a compressed distribution bundle tarball
tar -czf "${OUT_DIR}.tar.gz" -C "$(dirname "${OUT_DIR}")" "$(basename "${OUT_DIR}")"

echo "Packaged VM bundle: ${OUT_DIR} and ${OUT_DIR}.tar.gz"
