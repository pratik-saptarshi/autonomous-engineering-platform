# Multi-stage OCI Containerfile for Autonomous Engineering Platform (AEP)
# Supports both linux/amd64 and linux/arm64 (Muse Embedded VM container target)

ARG BASE_IMAGE=alpine:3.20

FROM --platform=$BUILDPLATFORM golang:1.27.3-alpine AS builder

WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download

COPY . .

ARG TARGETOS TARGETARCH
RUN CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} \
    go build -ldflags "-s -w" -o /out/aep ./cmd/aep

# Generate the VM bundle with the repo's own packaging script, from the
# binary built above, so the runtime stage installs the bundle's hardware
# profile and verification payload from the same source the VM route ships.
RUN apk add --no-cache bash && \
    bash scripts/package-vm.sh linux "${TARGETARCH:-amd64}" /out/aep /bundle

FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="Autonomous Engineering Platform" \
      org.opencontainers.image.description="Platform-agnostic autonomous software engineering execution engine" \
      org.opencontainers.image.source="https://github.com/pratik-saptarshi/autonomous-engineering-platform"

RUN apk add --no-cache \
    bash \
    ca-certificates \
    git \
    curl \
    jq \
    tzdata \
    make

# Create unprivileged aep user and workspace hierarchy
RUN addgroup -g 1000 aep && \
    adduser -u 1000 -G aep -s /bin/bash -D aep && \
    mkdir -p /workspace /etc/aep && \
    chown -R aep:aep /workspace /etc/aep

COPY --from=builder /out/aep /usr/local/bin/aep

# Install the bundle's hardware profile and verification payload: the
# payload is the self-check tree the supervisor verifies by default (the
# Compose service pins it as its --root; see docker-compose.yml) — the
# same root the bundle's systemd unit configures on the VM route.
COPY --from=builder /bundle/config/hardware-profile.conf /etc/aep/hardware-profile.conf
COPY --from=builder /bundle/verify /usr/local/lib/aep/verify

USER aep
WORKDIR /workspace

ENV PATH="/usr/local/bin:${PATH}"

ENTRYPOINT ["/usr/local/bin/aep"]
CMD ["info"]
