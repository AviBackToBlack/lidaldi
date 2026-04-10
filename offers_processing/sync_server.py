#!/usr/bin/env python3
"""
LidAldi Sync Server

Minimal HTTP API for cross-device synchronization of lastVisit timestamps,
alerts, and push notification subscriptions.

Endpoints:
    GET  /api/sync/{code}  - Read sync data
    POST /api/sync/{code}  - Update sync data

Runs as a systemd service behind an Nginx reverse proxy.

Platform: POSIX only. `sync_store` uses fcntl for cross-process locking;
running on Windows is not supported. See README.md.
"""

import json
import os
import re
import sys
import time
import uuid
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

import config
import sync_store
from common import log_event, hash_prefix


SYNC_CODE_RE = re.compile(r"^[A-Za-z0-9]{6,8}$")
MAX_BODY = 10 * 1024       # 10 KB
RATE_WINDOW = 60           # seconds
RATE_MAX = 30              # requests per window per IP
RATE_MAX_IPS = 10000       # soft cap on tracked IPs
VALID_MATCH_TYPES = {"exact", "allWords", "anyWord"}
MAX_ALERTS = 50
MAX_PUSH_SUBS = 10
MAX_TOMBSTONES = 200
ALERT_ID_RE = re.compile(r"^[A-Za-z0-9]{1,32}$")

# Trusted proxy networks that are allowed to set X-Real-IP / X-Forwarded-For.
# Anything else sees its TCP peer address and cannot spoof.
_TRUSTED_PROXIES = {"127.0.0.1", "::1"}


# ---------------------------------------------------------------------------
# Rate limiting (in-memory, per real-client IP)
# ---------------------------------------------------------------------------
_rate = {}
_rate_lock = threading.Lock()


def _rate_limited(ip):
    now = time.time()
    with _rate_lock:
        if len(_rate) > RATE_MAX_IPS:
            # LRU-ish drop: keep the half with the most recent activity.
            items = sorted(
                _rate.items(),
                key=lambda kv: (max(kv[1]) if kv[1] else 0),
            )
            keep = dict(items[-(RATE_MAX_IPS // 2):])
            _rate.clear()
            _rate.update(keep)
        hits = _rate.get(ip, [])
        hits = [t for t in hits if now - t < RATE_WINDOW]
        if len(hits) >= RATE_MAX:
            _rate[ip] = hits
            return True
        hits.append(now)
        _rate[ip] = hits
        return False


# ---------------------------------------------------------------------------
# Per-code in-process locks (paired with fcntl in sync_store for cross-proc)
# ---------------------------------------------------------------------------
_locks = {}
_locks_meta = threading.Lock()


def _get_thread_lock(code):
    with _locks_meta:
        lk = _locks.get(code)
        if lk is None:
            lk = threading.Lock()
            _locks[code] = lk
        return lk


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
def _valid_alerts(arr):
    if not isinstance(arr, list) or len(arr) > MAX_ALERTS:
        return False
    seen = set()
    for a in arr:
        if not isinstance(a, dict):
            return False
        allowed_keys = {"id", "keyword", "matchType", "createdAt"}
        if not set(a.keys()).issubset(allowed_keys):
            return False
        if not isinstance(a.get("id"), str) or not ALERT_ID_RE.match(a["id"]):
            return False
        if a["id"] in seen:
            return False
        seen.add(a["id"])
        if not isinstance(a.get("keyword"), str) or not a["keyword"].strip() or len(a["keyword"]) > 200:
            return False
        if a.get("matchType") not in VALID_MATCH_TYPES:
            return False
        ca = a.get("createdAt")
        if ca is not None and not isinstance(ca, (int, float)):
            return False
    return True


def _valid_tombstones(arr):
    if arr is None:
        return True
    if not isinstance(arr, list) or len(arr) > MAX_TOMBSTONES:
        return False
    for t in arr:
        if not isinstance(t, dict):
            return False
        if not isinstance(t.get("id"), str) or not ALERT_ID_RE.match(t["id"]):
            return False
        at = t.get("at")
        if at is not None and not isinstance(at, (int, float)):
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

    def setup(self):
        super().setup()
        self.req_id = uuid.uuid4().hex[:12]

    def log_message(self, fmt, *args):  # noqa: ARG002
        # Structured events emitted explicitly; suppress BaseHTTPServer access log.
        return

    def _client_ip(self):
        peer = self.client_address[0]
        if peer in _TRUSTED_PROXIES:
            real = self.headers.get("X-Real-IP")
            if real:
                return real.strip()
            xff = self.headers.get("X-Forwarded-For")
            if xff:
                return xff.split(",")[0].strip()
        return peer

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
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _err(self, status, msg):
        self._json(status, {"error": msg})

    def _code(self):
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
        ip = self._client_ip()
        if _rate_limited(ip):
            log_event("rate_limited", req=self.req_id, ip=ip, method="GET")
            return self._err(429, "Rate limit exceeded")
        code = self._code()
        if not code:
            return self._err(400, "Invalid request")

        def _read_only(_data):
            return None

        def _on_corrupt(err):
            log_event("sync_read_corrupt", req=self.req_id,
                      code=hash_prefix(code), error=str(err))

        try:
            data = sync_store.locked_rmw(
                code, _read_only,
                thread_lock=_get_thread_lock(code),
                on_corrupt=_on_corrupt,
            )
        except Exception as e:
            log_event("sync_read_error", req=self.req_id,
                      code=hash_prefix(code), error=str(e))
            return self._err(500, "Internal error")

        if data is None:
            log_event("sync_get", req=self.req_id, code=hash_prefix(code),
                      status="empty")
            return self._json(200, {"lastVisit": 0, "alerts": [], "tombstones": []})

        # Defence in depth: drop any alerts whose id is in the current
        # tombstone list before returning. merge_alerts normally prevents
        # this, but any write that left a tombstoned alert on disk (legacy
        # profile, concurrent-write race in an older version) would
        # otherwise resurrect the deletion to every reader.
        stored_alerts = data.get("alerts", []) or []
        stored_tombs = data.get("tombstones", []) or []
        tomb_ids = {
            t.get("id") for t in stored_tombs
            if isinstance(t, dict) and isinstance(t.get("id"), str)
        }
        visible_alerts = [
            a for a in stored_alerts
            if isinstance(a, dict) and a.get("id") not in tomb_ids
        ]

        log_event("sync_get", req=self.req_id, code=hash_prefix(code),
                  alerts=len(visible_alerts),
                  tombstones=len(stored_tombs))
        safe = {
            "lastVisit": data.get("lastVisit", 0),
            "alerts": visible_alerts,
            "tombstones": stored_tombs,
        }
        self._json(200, safe)

    def do_POST(self):
        ip = self._client_ip()
        if _rate_limited(ip):
            log_event("rate_limited", req=self.req_id, ip=ip, method="POST")
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

        lv = body.get("lastVisit", 0)
        if not isinstance(lv, (int, float)) or lv < 0:
            return self._err(400, "Invalid lastVisit")
        lv = int(lv)

        alerts = body.get("alerts")
        if alerts is not None and not _valid_alerts(alerts):
            return self._err(400, "Invalid alerts")

        tombs_in = body.get("deletedAlertIds")
        if not _valid_tombstones(tombs_in):
            return self._err(400, "Invalid tombstones")

        push_sub = body.get("pushSubscription")
        if push_sub is not None and not _valid_push_sub(push_sub):
            return self._err(400, "Invalid push subscription")

        def modifier(existing):
            if existing is None:
                existing = {
                    "lastVisit": 0,
                    "alerts": [],
                    "tombstones": [],
                    "pushSubscriptions": [],
                    "notified": [],
                }

            merged_lv = max(int(existing.get("lastVisit", 0) or 0), lv)

            merged_alerts, merged_tombs = sync_store.merge_alerts(
                existing.get("alerts", []),
                existing.get("tombstones", []),
                alerts,
                tombs_in,
            )

            subs = list(existing.get("pushSubscriptions", []))
            if push_sub:
                subs = [s for s in subs if s.get("endpoint") != push_sub["endpoint"]]
                subs.append(push_sub)
                if len(subs) > MAX_PUSH_SUBS:
                    subs = subs[-MAX_PUSH_SUBS:]

            return {
                "lastVisit": merged_lv,
                "alerts": merged_alerts,
                "tombstones": merged_tombs,
                "pushSubscriptions": subs,
                "notified": existing.get("notified", []),
            }

        def _on_corrupt(err):
            log_event("sync_read_corrupt", req=self.req_id,
                      code=hash_prefix(code), error=str(err))

        try:
            result = sync_store.locked_rmw(
                code, modifier,
                thread_lock=_get_thread_lock(code),
                on_corrupt=_on_corrupt,
            )
        except Exception as e:
            log_event("sync_write_error", req=self.req_id,
                      code=hash_prefix(code), error=str(e))
            return self._err(500, "Internal error")

        log_event("sync_post", req=self.req_id, code=hash_prefix(code),
                  alerts=len(result.get("alerts", [])),
                  tombstones=len(result.get("tombstones", [])),
                  subs=len(result.get("pushSubscriptions", [])))

        safe = {
            "lastVisit": result["lastVisit"],
            "alerts": result["alerts"],
            "tombstones": result.get("tombstones", []),
        }
        self._json(200, safe)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    os.makedirs(config.SYNC_DIR, exist_ok=True)
    addr = (config.SYNC_SERVER_HOST, config.SYNC_SERVER_PORT)
    srv = ThreadingHTTPServer(addr, SyncHandler)
    log_event("sync_server_start", host=addr[0], port=addr[1])
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log_event("sync_server_stop", reason="keyboard_interrupt")
        srv.shutdown()


if __name__ == "__main__":
    main()
