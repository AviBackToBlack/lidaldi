#!/usr/bin/env python3
"""
LidAldi Sync Server

Minimal HTTP API for cross-device synchronization of lastVisit timestamps,
alerts, and push notification subscriptions.

Endpoints:
    GET  /api/sync/{code}  - Read sync data
    POST /api/sync/{code}  - Update sync data

Runs as a systemd service behind Nginx reverse proxy.
"""

import json
import os
import re
import sys
import time
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

import config

SYNC_CODE_RE = re.compile(r"^[A-Za-z0-9]{6,8}$")
MAX_BODY = 10 * 1024      # 10 KB
RATE_WINDOW = 60           # seconds
RATE_MAX = 30              # requests per window per IP
RATE_MAX_IPS = 10000       # evict rate table when it exceeds this many IPs
VALID_MATCH_TYPES = {"exact", "allWords", "anyWord"}
MAX_ALERTS = 50
MAX_PUSH_SUBS = 10
MAX_LOCKS = 10000          # evict lock table when it exceeds this many entries

# ---------------------------------------------------------------------------
# Rate limiting (in-memory, per IP)
# ---------------------------------------------------------------------------
_rate = {}
_rate_lock = threading.Lock()


def _rate_limited(ip):
    now = time.time()
    with _rate_lock:
        # Evict stale IPs to prevent unbounded memory growth
        if len(_rate) > RATE_MAX_IPS:
            _rate.clear()
        hits = _rate.get(ip, [])
        hits = [t for t in hits if now - t < RATE_WINDOW]
        if len(hits) >= RATE_MAX:
            _rate[ip] = hits
            return True
        hits.append(now)
        _rate[ip] = hits
        return False


# ---------------------------------------------------------------------------
# Per-code file locks (prevents concurrent writes to the same sync file)
# ---------------------------------------------------------------------------
_locks = {}
_locks_meta = threading.Lock()


def _get_lock(code):
    with _locks_meta:
        # Evict all locks to prevent unbounded memory growth
        if len(_locks) > MAX_LOCKS:
            _locks.clear()
        if code not in _locks:
            _locks[code] = threading.Lock()
        return _locks[code]


# ---------------------------------------------------------------------------
# File I/O with atomic writes
# ---------------------------------------------------------------------------
def _path(code):
    return os.path.join(config.SYNC_DIR, f"{code}.json")


def _read(code):
    p = _path(code)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(code, data):
    p = _path(code)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, p)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
def _valid_alerts(arr):
    if not isinstance(arr, list) or len(arr) > MAX_ALERTS:
        return False
    for a in arr:
        if not isinstance(a, dict):
            return False
        allowed_keys = {"id", "keyword", "matchType", "createdAt"}
        if not set(a.keys()).issubset(allowed_keys):
            return False
        if not isinstance(a.get("id"), str) or len(a["id"]) > 32:
            return False
        if not isinstance(a.get("keyword"), str) or not a["keyword"].strip() or len(a["keyword"]) > 200:
            return False
        if a.get("matchType") not in VALID_MATCH_TYPES:
            return False
    return True


def _valid_push_sub(s):
    if not isinstance(s, dict):
        return False
    ep = s.get("endpoint")
    keys = s.get("keys")
    if not isinstance(ep, str) or len(ep) > 500 or not ep.startswith("https://"):
        return False
    if not isinstance(keys, dict):
        return False
    if not isinstance(keys.get("p256dh"), str) or not isinstance(keys.get("auth"), str):
        return False
    return True


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------
class SyncHandler(BaseHTTPRequestHandler):

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", config.SYNC_ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Vary", "Origin")

    def _json(self, status, obj):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _err(self, status, msg):
        self._json(status, {"error": msg})

    def _code(self):
        """Extract and validate sync code from URL path."""
        parts = self.path.rstrip("/").split("/")
        if len(parts) == 4 and parts[1] == "api" and parts[2] == "sync":
            c = parts[3]
            if SYNC_CODE_RE.match(c):
                return c
        return None

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if _rate_limited(self.client_address[0]):
            return self._err(429, "Rate limit exceeded")
        code = self._code()
        if not code:
            return self._err(400, "Invalid request")
        lock = _get_lock(code)
        with lock:
            data = _read(code)
        if data is None:
            return self._json(200, {"lastVisit": 0, "alerts": []})
        # Never leak push subscriptions to the client
        safe = {
            "lastVisit": data.get("lastVisit", 0),
            "alerts": data.get("alerts", []),
        }
        self._json(200, safe)

    def do_POST(self):
        if _rate_limited(self.client_address[0]):
            return self._err(429, "Rate limit exceeded")
        code = self._code()
        if not code:
            return self._err(400, "Invalid request")

        try:
            cl = int(self.headers.get("Content-Length", 0))
        except (ValueError, TypeError):
            return self._err(400, "Invalid Content-Length")
        if cl < 0 or cl > MAX_BODY:
            return self._err(413, "Body too large")

        try:
            raw = self.rfile.read(cl)
            body = json.loads(raw)
        except Exception:
            return self._err(400, "Invalid JSON")

        if not isinstance(body, dict):
            return self._err(400, "Expected object")

        # -- lastVisit --
        lv = body.get("lastVisit", 0)
        if not isinstance(lv, (int, float)) or lv < 0:
            return self._err(400, "Invalid lastVisit")
        lv = int(lv)

        # -- alerts (optional: if omitted, keep existing) --
        alerts = body.get("alerts")
        if alerts is not None and not _valid_alerts(alerts):
            return self._err(400, "Invalid alerts")

        # -- pushSubscription (single, this device; optional) --
        push_sub = body.get("pushSubscription")
        if push_sub is not None and not _valid_push_sub(push_sub):
            return self._err(400, "Invalid push subscription")

        lock = _get_lock(code)
        with lock:
            existing = _read(code) or {
                "lastVisit": 0,
                "alerts": [],
                "pushSubscriptions": [],
            }

            merged_lv = max(existing.get("lastVisit", 0), lv)
            merged_alerts = alerts if alerts is not None else existing.get("alerts", [])

            subs = list(existing.get("pushSubscriptions", []))
            if push_sub:
                subs = [s for s in subs if s.get("endpoint") != push_sub["endpoint"]]
                subs.append(push_sub)
                if len(subs) > MAX_PUSH_SUBS:
                    subs = subs[-MAX_PUSH_SUBS:]

            result = {
                "lastVisit": merged_lv,
                "alerts": merged_alerts,
                "pushSubscriptions": subs,
            }
            _write(code, result)

        safe = {"lastVisit": result["lastVisit"], "alerts": result["alerts"]}
        self._json(200, safe)

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[{self.log_date_time_string()}] {fmt % args}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    os.makedirs(config.SYNC_DIR, exist_ok=True)
    addr = (config.SYNC_SERVER_HOST, config.SYNC_SERVER_PORT)
    srv = ThreadingHTTPServer(addr, SyncHandler)
    print(f"LidAldi Sync Server listening on {addr[0]}:{addr[1]}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        srv.shutdown()


if __name__ == "__main__":
    main()
