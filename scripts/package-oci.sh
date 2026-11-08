#!/usr/bin/env bash
# package-oci.sh — builds and packages OCI images for Docker / Podman
# across linux/amd64 and linux/arm64 targets.
set -euo pipefail

TOOL=""
if command -v podman >/dev/null 2>&1; then
  TOOL="podman"
elif command -v docker >/dev/null 2>&1; then
  TOOL="docker"
fi

OUT_DIR="${1:-dist/oci}"
mkdir -p "${OUT_DIR}"

IMAGE_TAG="${2:-aep:latest}"

if [ -z "${TOOL}" ]; then
  echo "NOTICE: Neither 'docker' nor 'podman' found on local host."
  echo "Generating OCI specification and build context artifact in ${OUT_DIR}..."
  tar -czf "${OUT_DIR}/aep-oci-context.tar.gz" Containerfile Dockerfile docker-compose.yml cmd/ internal/ go.mod go.sum
  echo "OCI build context archived to ${OUT_DIR}/aep-oci-context.tar.gz"
  echo "To build on a system with Docker/Podman:"
  echo "  tar -xzf aep-oci-context.tar.gz && docker build -t ${IMAGE_TAG} ."
  exit 0
fi

echo "Building multi-arch OCI images using ${TOOL}..."
${TOOL} build --platform linux/amd64,linux/arm64 -f Containerfile -t "${IMAGE_TAG}" .

echo "Saving image tarballs..."
${TOOL} save "${IMAGE_TAG}" -o "${OUT_DIR}/aep-oci.tar"
echo "OCI image saved to ${OUT_DIR}/aep-oci.tar"
