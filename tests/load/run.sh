#!/usr/bin/env bash
# T13 load tier runner: boots a real sync_server with a throwaway SYNC_DIR
# and runs the k6 scenario against it. FAILS (never skips) when k6 is not
# installed or the server does not come up.
set -euo pipefail
cd "$(dirname "$0")/../.."

PYTHON="${PYTHON:-python3}"
PORT="${SYNC_API_PORT:-8099}"
BASE="http://127.0.0.1:${PORT}"

if ! command -v k6 >/dev/null 2>&1; then
  echo "test-load: k6 is not installed — run tests/load/install-k6.sh (pinned version)" >&2
  exit 1
fi

TMP="$(mktemp -d)"
SERVER_PID=""
cleanup() {
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  rm -rf "$TMP"
}
trap cleanup EXIT

mkdir -p "$TMP/processing" "$TMP/webroot" "$TMP/sync"
cat > "$TMP/config.toml" <<EOF
[paths]
offers_processing_dir = "$TMP/processing"
website_root_dir = "$TMP/webroot"

[sync]
dir = "$TMP/sync"
host = "127.0.0.1"
port = $PORT
allowed_origin = "https://example.test"

[push]
vapid_public_key = "test-vapid-public-key"
vapid_claims_email = "mailto:test@example.test"
EOF
printf 'TELEGRAM_BOT_TOKEN=dummy\nTELEGRAM_CHAT_ID=dummy\n' > "$TMP/.env"

LIDALDI_CONFIG="$TMP/config.toml" LIDALDI_ENV_FILE="$TMP/.env" \
  "$PYTHON" offers_processing/sync_server.py > "$TMP/server.log" 2>&1 &
SERVER_PID=$!

# Readiness: GET on a valid (empty) code returns 200. Each probe carries a
# distinct X-Forwarded-For (trusted from loopback) so the probes themselves
# can never trip the 30 req/min per-IP rate limit.
ready=""
for i in $(seq 1 50); do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    break
  fi
  if curl -sf -o /dev/null -H "X-Forwarded-For: 10.255.255.$i" "$BASE/api/sync/READY01"; then
    ready=1
    break
  fi
  sleep 0.2
done
if [ -z "$ready" ]; then
  echo "test-load: sync_server failed to start on $BASE" >&2
  cat "$TMP/server.log" >&2 || true
  exit 1
fi

k6 run -e "SYNC_API_URL=$BASE" tests/load/sync_api.js
