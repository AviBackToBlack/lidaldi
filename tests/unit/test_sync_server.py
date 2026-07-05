"""T3/T4: sync_server HTTP contract tests against a real server in a thread."""

import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest


@pytest.fixture
def server(sync_env, monkeypatch):
    import sync_server

    # Tests fire many requests from one IP; don't trip the rate limiter.
    monkeypatch.setattr(sync_server, "RATE_MAX", 10000)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), sync_server.SyncHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    yield base
    srv.shutdown()
    t.join(timeout=5)


def _get(base, code):
    with urllib.request.urlopen(f"{base}/api/sync/{code}") as r:
        return r.status, json.loads(r.read())


def _post(base, code, body):
    req = urllib.request.Request(
        f"{base}/api/sync/{code}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return r.status, json.loads(r.read())


ALERT = {"id": "a1", "keyword": "drill", "matchType": "anyWord", "createdAt": 1}


# ---------------------------------------------------------------------------
# T3: alertMatches — exposed on GET, server-owned on POST
# ---------------------------------------------------------------------------
def test_get_empty_profile_includes_alert_matches(server):
    status, body = _get(server, "CODE01")
    assert status == 200
    assert body == {"lastVisit": 0, "alerts": [], "tombstones": [],
                    "alertMatches": {}}


def test_get_returns_alert_matches_written_by_notifier(server, sync_env):
    import sync_store

    now = time.time()
    _post(server, "CODE01", {"lastVisit": 100, "alerts": [ALERT]})

    def _add(data):
        data["alertMatches"] = {"a1": [{"id": "111", "at": now}]}
        return data

    sync_store.locked_rmw("CODE01", _add)
    status, body = _get(server, "CODE01")
    assert status == 200
    assert body["alertMatches"] == {"a1": [{"id": "111", "at": now}]}


def test_get_gcs_expired_alert_matches(server, sync_env):
    import sync_store

    old = time.time() - sync_store.ALERT_MATCHES_TTL_SEC - 1
    _post(server, "CODE01", {"lastVisit": 100})

    def _add(data):
        data["alertMatches"] = {"a1": [{"id": "111", "at": old}]}
        return data

    sync_store.locked_rmw("CODE01", _add)
    _, body = _get(server, "CODE01")
    assert body["alertMatches"] == {}


def test_post_cannot_inject_alert_matches_or_notified(server, sync_env):
    import sync_store

    status, body = _post(server, "CODE01", {
        "lastVisit": 100,
        "alerts": [ALERT],
        "alertMatches": {"a1": [{"id": "evil", "at": time.time()}]},
        "notified": [{"alertId": "a1", "id": "evil", "endpoint": "x", "at": 1}],
    })
    assert status == 200
    assert "alertMatches" not in body and "notified" not in body

    stored = sync_store.locked_rmw("CODE01", lambda d: None)
    assert stored["alertMatches"] == {}
    assert stored["notified"] == []


def test_post_cannot_overwrite_existing_server_owned_fields(server, sync_env):
    import sync_store

    now = time.time()
    _post(server, "CODE01", {"lastVisit": 100, "alerts": [ALERT]})

    def _add(data):
        data["alertMatches"] = {"a1": [{"id": "111", "at": now}]}
        data["notified"] = [{"alertId": "a1", "id": "111", "endpoint": "e", "at": now}]
        return data

    sync_store.locked_rmw("CODE01", _add)
    _post(server, "CODE01", {
        "lastVisit": 200,
        "alertMatches": {},
        "notified": [],
    })
    stored = sync_store.locked_rmw("CODE01", lambda d: None)
    assert stored["alertMatches"] == {"a1": [{"id": "111", "at": now}]}
    assert stored["notified"] == [
        {"alertId": "a1", "id": "111", "endpoint": "e", "at": now}
    ]


def test_post_response_shape_unchanged(server):
    status, body = _post(server, "CODE01", {"lastVisit": 100, "alerts": [ALERT]})
    assert status == 200
    assert set(body) == {"lastVisit", "alerts", "tombstones"}


# ---------------------------------------------------------------------------
# Security validation preserved
# ---------------------------------------------------------------------------
def test_invalid_code_rejected(server):
    req = urllib.request.Request(f"{server}/api/sync/bad!code")
    try:
        urllib.request.urlopen(req)
        assert False, "expected 400"
    except urllib.error.HTTPError as e:
        assert e.code == 400


def test_invalid_alerts_rejected(server):
    req = urllib.request.Request(
        f"{server}/api/sync/CODE01",
        data=json.dumps({"alerts": [{"id": "x", "keyword": "", "matchType": "exact"}]}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req)
        assert False, "expected 400"
    except urllib.error.HTTPError as e:
        assert e.code == 400
