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
    tzdata

# Create unprivileged aep user and workspace hierarchy
RUN addgroup -g 1000 aep && \
    adduser -u 1000 -G aep -s /bin/bash -D aep && \
    mkdir -p /workspace /etc/aep && \
    chown -R aep:aep /workspace /etc/aep

COPY --from=builder /out/aep /usr/local/bin/aep

USER aep
WORKDIR /workspace

ENV PATH="/usr/local/bin:${PATH}"

ENTRYPOINT ["/usr/local/bin/aep"]
CMD ["info"]
