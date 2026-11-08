# Autonomous Engineering Platform (AEP) Makefile

GO ?= go
VERSION ?= 1.0.0
GIT_COMMIT ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
LDFLAGS := -s -w -X main.version=$(VERSION) -X main.commit=$(GIT_COMMIT)

DIST_BIN := dist/bin
DIST_VM := dist/vm
DIST_OCI := dist/oci

GO_SOURCES := $(shell find cmd internal -type f -name '*.go')

.PHONY: all binaries vm oci clean test

all: binaries vm oci

test:
	$(GO) test -v ./...

binaries: dist/bin/aep-linux-amd64 dist/bin/aep-linux-arm64 dist/bin/aep-darwin-arm64 dist/bin/aep-darwin-amd64

dist/bin/aep-linux-amd64: $(GO_SOURCES) go.mod go.sum
	@mkdir -p $(DIST_BIN)
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 $(GO) build -ldflags "$(LDFLAGS)" -o $@ ./cmd/aep

dist/bin/aep-linux-arm64: $(GO_SOURCES) go.mod go.sum
	@mkdir -p $(DIST_BIN)
	CGO_ENABLED=0 GOOS=linux GOARCH=arm64 $(GO) build -ldflags "$(LDFLAGS)" -o $@ ./cmd/aep

dist/bin/aep-darwin-arm64: $(GO_SOURCES) go.mod go.sum
	@mkdir -p $(DIST_BIN)
	CGO_ENABLED=0 GOOS=darwin GOARCH=arm64 $(GO) build -ldflags "$(LDFLAGS)" -o $@ ./cmd/aep

dist/bin/aep-darwin-amd64: $(GO_SOURCES) go.mod go.sum
	@mkdir -p $(DIST_BIN)
	CGO_ENABLED=0 GOOS=darwin GOARCH=amd64 $(GO) build -ldflags "$(LDFLAGS)" -o $@ ./cmd/aep

vm: dist/vm/linux-amd64 dist/vm/linux-arm64

dist/vm/linux-amd64: dist/bin/aep-linux-amd64
	@bash scripts/package-vm.sh linux amd64 dist/bin/aep-linux-amd64 $@

dist/vm/linux-arm64: dist/bin/aep-linux-arm64
	@bash scripts/package-vm.sh linux arm64 dist/bin/aep-linux-arm64 $@

oci: dist/oci

dist/oci:
	@bash scripts/package-oci.sh $(DIST_OCI)

clean:
	rm -rf dist/
