#!/usr/bin/env bash
# ZAP scan target (T13, D4): builds the frontend, starts a real sync_server
# with a throwaway SYNC_DIR, and serves both from one origin on :8100
# (static webroot + /api/sync/* proxy, mirroring the production nginx layout).
# Run via `make test-zap` (compose profile "zap").
set -euo pipefail
cd "$(dirname "$0")/../.."

PYTHON="${PYTHON:-python3}"
SYNC_PORT=8099
TARGET_PORT=8100

(cd frontend && npm ci --no-audit --no-fund && npm run build)

TMP="$(mktemp -d)"
mkdir -p "$TMP/processing" "$TMP/webroot" "$TMP/sync"
cat > "$TMP/config.toml" <<EOF
[paths]
offers_processing_dir = "$TMP/processing"
website_root_dir = "$TMP/webroot"

[sync]
dir = "$TMP/sync"
host = "127.0.0.1"
port = $SYNC_PORT
allowed_origin = "http://localhost:$TARGET_PORT"

[push]
vapid_public_key = "test-vapid-public-key"
vapid_claims_email = "mailto:test@example.test"
EOF
printf 'TELEGRAM_BOT_TOKEN=dummy\nTELEGRAM_CHAT_ID=dummy\n' > "$TMP/.env"

LIDALDI_CONFIG="$TMP/config.toml" LIDALDI_ENV_FILE="$TMP/.env" \
  "$PYTHON" offers_processing/sync_server.py &

exec "$PYTHON" tests/zap/static_proxy.py frontend/dist "http://127.0.0.1:$SYNC_PORT" "$TARGET_PORT"
