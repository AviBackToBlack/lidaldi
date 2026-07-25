#!/usr/bin/env bash
# Installs the pinned, checksum-verified k6 binary for the load tier (T13).
# Used by both .devcontainer/Dockerfile and .github/workflows/ci.yml so the
# exact same k6 build runs locally and in CI.
set -euo pipefail

K6_VERSION=1.1.0

case "$(uname -m)" in
  x86_64)
    ARCH=amd64
    SHA256=7d92e0cbf625b5fde10653a67a0a2eeeab2de75f7f9f562a3b6cafd2a5d847e5
    ;;
  aarch64 | arm64)
    ARCH=arm64
    SHA256=8734b1c4b16d336aac8ffae5ff69caa7bef975ad480e5377e52d6fab7524d4a8
    ;;
  *)
    echo "install-k6.sh: unsupported architecture: $(uname -m)" >&2
    exit 1
    ;;
esac

URL="https://github.com/grafana/k6/releases/download/v${K6_VERSION}/k6-v${K6_VERSION}-linux-${ARCH}.tar.gz"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

curl -fsSL -o "$TMP/k6.tgz" "$URL"
echo "${SHA256}  $TMP/k6.tgz" | sha256sum -c -
tar -xzf "$TMP/k6.tgz" -C "$TMP"
install -m 0755 "$TMP/k6-v${K6_VERSION}-linux-${ARCH}/k6" /usr/local/bin/k6
k6 version
