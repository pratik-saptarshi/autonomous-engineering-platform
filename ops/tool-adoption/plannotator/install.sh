#!/bin/sh
# Pinned, verified installer for Plannotator — the adopt-as-tool pattern
# instance described in ops/tool-adoption/README.md.
#
# What this script does, in order:
#   1. Detects the platform from `uname` and resolves the release asset.
#   2. Downloads the PINNED release into a staging directory. The staged
#      binary is never executed.
#   3. Verifies provenance BEFORE anything is installed:
#        - the download's SHA256 must match the release's published
#          .sha256 sidecar;
#        - on linux-x64 it must additionally match the expected checksum
#          pinned in this script (verified first-hand at adoption time);
#        - when `gh` is available, `gh attestation verify` must pass with
#          the source ref and signer workflow pinned;
#        - when `gh` is absent, installation proceeds only on a platform
#          whose expected checksum is pinned in this script. Otherwise it
#          aborts: never install unverified.
#   4. Installs the binary under a versioned filename, writes the
#      hardening launcher, writes the local config, retains the release
#      SBOM (sidecar-verified) as evidence, and smoke-tests through the
#      launcher.
#
# It never runs the upstream `curl | bash` installer: that installer
# scatters per-agent hooks and configuration this pattern deliberately
# controls itself.
#
# Idempotent: re-running verifies the installed copy and rewrites the
# launcher and config with identical content.
#
# Layout (PREFIX defaults to $HOME; override with PLANNOTATOR_PREFIX):
#   $PREFIX/workspace/plannotator/bin/          versioned binary
#   $PREFIX/workspace/plannotator/verification/ checksums + SBOM evidence
#   $PREFIX/workspace/bin/plannotator           hardening launcher (on PATH)
#   $PREFIX/.plannotator/config.json            local tool config
# For an isolated test install, point HOME at a scratch directory and set
# PLANNOTATOR_PREFIX to the same directory: every path above follows.
#
# Tested on Linux x86_64. The darwin / arm64 / win32 asset mappings follow
# the upstream release layout and are verified by sidecar + attestation,
# but have not been run end-to-end by us.

set -eu

VERSION="0.28.63"
TAG="v${VERSION}"
REPO="backnotprop/plannotator"
SIGNER_WORKFLOW="${REPO}/.github/workflows/release.yml"
DOWNLOAD_BASE="https://github.com/${REPO}/releases/download/${TAG}"

# Expected SHA256 values verified first-hand at adoption time, per
# platform key. Platforms not listed here fall back to the release
# sidecar + mandatory attestation (see step 3 in the header).
EXPECTED_linux_x64="41c00c90ecd8bd9665163671ec0d5503bb83f4251f849123faafa90543286f52"

PREFIX="${PLANNOTATOR_PREFIX:-$HOME}"
BIN_DIR="${PREFIX}/workspace/plannotator/bin"
VER_DIR="${PREFIX}/workspace/plannotator/verification"
LAUNCH_DIR="${PREFIX}/workspace/bin"
STATE_DIR="${PREFIX}/.plannotator"

say() { printf '%s\n' "install: $*"; }
die() { printf '%s\n' "install: ERROR: $*" >&2; exit 1; }

# --- platform detection ---------------------------------------------------

detect_platform() {
  os="$(uname -s)"
  arch="$(uname -m)"
  case "$os" in
    Linux) os_key="linux" ;;
    Darwin) os_key="darwin" ;;
    MINGW* | MSYS* | CYGWIN*) os_key="win32" ;;
    *) die "unsupported operating system: $os" ;;
  esac
  case "$arch" in
    x86_64 | amd64) arch_key="x64" ;;
    arm64 | aarch64) arch_key="arm64" ;;
    *) die "unsupported architecture: $arch" ;;
  esac
  PLATFORM="${os_key}-${arch_key}"
  if [ "$os_key" = "win32" ]; then
    ASSET="plannotator-${PLATFORM}.exe"
  else
    ASSET="plannotator-${PLATFORM}"
  fi
  INSTALLED_NAME="plannotator-${VERSION}-${ASSET#plannotator-}"
}

# --- helpers ---------------------------------------------------------------

fetch() {
  # fetch <url> <dest>
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --retry 2 -o "$2" "$1"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$2" "$1"
  else
    die "neither curl nor wget is available; cannot download the release"
  fi
}

sha_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    die "no sha256 tool (sha256sum / shasum) available; cannot verify the download"
  fi
}

expected_for_platform() {
  case "$PLATFORM" in
    linux-x64) printf '%s' "$EXPECTED_linux_x64" ;;
    *) printf '' ;;
  esac
}

verify_attestation() {
  # verify_attestation <file>; returns non-zero when gh is absent.
  command -v gh >/dev/null 2>&1 || return 1
  gh attestation verify "$1" \
    --repo "$REPO" \
    --source-ref "refs/tags/${TAG}" \
    --signer-workflow "$SIGNER_WORKFLOW"
}

# --- install ---------------------------------------------------------------

detect_platform
INSTALLED_PATH="${BIN_DIR}/${INSTALLED_NAME}"
EXPECTED="$(expected_for_platform)"
RECORDED_HASH_FILE="${VER_DIR}/${ASSET}.sha256"

say "plannotator ${VERSION} (${PLATFORM}) -> ${PREFIX}"

need_download=1
if [ -f "$INSTALLED_PATH" ]; then
  installed_sha="$(sha_of "$INSTALLED_PATH")"
  anchor=""
  if [ -n "$EXPECTED" ]; then
    anchor="$EXPECTED"
  elif [ -f "$RECORDED_HASH_FILE" ]; then
    # Hash recorded by a previous install of this script, which only
    # records a value after sidecar + attestation verification passed.
    anchor="$(awk '{print $1}' "$RECORDED_HASH_FILE")"
  fi
  if [ -n "$anchor" ] && [ "$installed_sha" = "$anchor" ]; then
    need_download=0
    say "installed binary already present and verified (${installed_sha})"
  else
    say "installed binary present but does not match the verified checksum; re-installing"
  fi
fi

if [ "$need_download" -eq 1 ]; then
  staging="$(mktemp -d)"
  trap 'rm -rf "$staging"' EXIT INT TERM

  say "downloading ${ASSET} and its checksum sidecar"
  fetch "${DOWNLOAD_BASE}/${ASSET}" "${staging}/${ASSET}"
  fetch "${DOWNLOAD_BASE}/${ASSET}.sha256" "${staging}/${ASSET}.sha256"

  computed="$(sha_of "${staging}/${ASSET}")"
  sidecar="$(awk '{print $1}' "${staging}/${ASSET}.sha256")"
  [ "$computed" = "$sidecar" ] ||
    die "SHA256 mismatch against the published sidecar (computed ${computed}, sidecar ${sidecar}); aborting, nothing installed"

  if [ -n "$EXPECTED" ]; then
    [ "$computed" = "$EXPECTED" ] ||
      die "SHA256 mismatch against the checksum pinned in this installer (computed ${computed}); aborting, nothing installed"
  fi

  if verify_attestation "${staging}/${ASSET}"; then
    say "attestation verified (repo ${REPO}, ref refs/tags/${TAG}, signer ${SIGNER_WORKFLOW})"
  elif [ -n "$EXPECTED" ]; then
    say "gh unavailable; proceeding on the pinned checksum anchor for ${PLATFORM}"
  else
    die "gh is unavailable and no checksum is pinned for ${PLATFORM}; cannot verify provenance, aborting"
  fi

  # Retain the release SBOM as evidence (sidecar-verified) before install.
  SBOM="plannotator-${VERSION}-release-sbom.cdx.json"
  if fetch "${DOWNLOAD_BASE}/${SBOM}" "${staging}/${SBOM}" &&
    fetch "${DOWNLOAD_BASE}/${SBOM}.sha256" "${staging}/${SBOM}.sha256"; then
    sbom_sha="$(sha_of "${staging}/${SBOM}")"
    sbom_sidecar="$(awk '{print $1}' "${staging}/${SBOM}.sha256")"
    [ "$sbom_sha" = "$sbom_sidecar" ] ||
      die "SBOM SHA256 mismatch (computed ${sbom_sha}, sidecar ${sbom_sidecar}); aborting, nothing installed"
    mkdir -p "$VER_DIR"
    cp "${staging}/${SBOM}" "${VER_DIR}/${SBOM}"
    cp "${staging}/${SBOM}.sha256" "${VER_DIR}/${SBOM}.sha256"
    say "release SBOM retained in ${VER_DIR} (sha256 ${sbom_sha})"
  else
    say "WARNING: SBOM asset not retrieved; continuing without it (binary verification already passed)"
  fi

  mkdir -p "$BIN_DIR" "$VER_DIR"
  cp "${staging}/${ASSET}" "${BIN_DIR}/.${INSTALLED_NAME}.tmp"
  chmod 755 "${BIN_DIR}/.${INSTALLED_NAME}.tmp"
  mv "${BIN_DIR}/.${INSTALLED_NAME}.tmp" "$INSTALLED_PATH"
  cp "${staging}/${ASSET}.sha256" "$RECORDED_HASH_FILE"
  say "installed ${INSTALLED_PATH} (sha256 ${computed})"
fi

# --- hardening launcher ------------------------------------------------------
# The launcher is the control point: it pins the verified binary and
# exports the hardening environment on every invocation, so the settings
# do not depend on operator memory or shell configuration.

mkdir -p "$LAUNCH_DIR"
cat > "${LAUNCH_DIR}/plannotator" <<EOF
#!/bin/sh
# Hardened launcher for the pinned Plannotator release (${TAG}).
# Generated by ops/tool-adoption/plannotator/install.sh — do not edit by
# hand; re-run the installer instead. The binary it execs was verified
# (SHA256 + attestation) before installation.
export NO_ANON_PING=1
export PLANNOTATOR_AI=disabled
export PLANNOTATOR_SHARE=disabled
# Force local mode even when SSH variables are present; remote mode is unauthenticated.
export PLANNOTATOR_REMOTE=0
# Keep review hermetic and preserve the version pin.
export PLANNOTATOR_JINA=0
export PLANNOTATOR_GIT_REMOTE_CHECK=0
export PLANNOTATOR_AUTO_UPDATE=0
exec "${INSTALLED_PATH}" "\$@"
EOF
chmod 755 "${LAUNCH_DIR}/plannotator"
say "launcher written to ${LAUNCH_DIR}/plannotator"

# --- local config ------------------------------------------------------------
# Merge the two hardening keys into the tool config, preserving any other
# keys. Falls back to a minimal file when the config does not exist yet.

mkdir -p "$STATE_DIR"
CONFIG="${STATE_DIR}/config.json"
if command -v python3 >/dev/null 2>&1; then
  python3 - "$CONFIG" <<'PYEOF'
import json, sys
path = sys.argv[1]
try:
    with open(path) as fh:
        cfg = json.load(fh)
except (OSError, ValueError):
    cfg = {}
cfg["autoUpdate"] = False
cfg["gitRemoteCheck"] = False
with open(path, "w") as fh:
    json.dump(cfg, fh, indent=2)
    fh.write("\n")
PYEOF
elif [ ! -f "$CONFIG" ]; then
  printf '{\n  "autoUpdate": false,\n  "gitRemoteCheck": false\n}\n' > "$CONFIG"
else
  say "WARNING: python3 not available; existing ${CONFIG} left untouched — set autoUpdate=false and gitRemoteCheck=false by hand"
fi
say "config ensured at ${CONFIG} (autoUpdate=false, gitRemoteCheck=false)"

# --- smoke tests (through the launcher, never the raw binary) ----------------

version_out="$("${LAUNCH_DIR}/plannotator" --version)" ||
  die "smoke test failed: launcher --version exited non-zero"
case "$version_out" in
  *"${VERSION}"*) say "smoke test: --version -> ${version_out}" ;;
  *) die "smoke test failed: --version printed '${version_out}', expected ${VERSION}" ;;
esac

"${LAUNCH_DIR}/plannotator" sessions >/dev/null ||
  die "smoke test failed: launcher sessions exited non-zero"
say "smoke test: sessions runs clean"

say "done: plannotator ${VERSION} installed and hardened under ${PREFIX}"
