"""T3: aggregate push payload, per-endpoint ledger, alertMatches persistence."""

import json
import time

import pytest


@pytest.fixture
def sn(sync_env, monkeypatch):
    import send_notifications
    import common

    monkeypatch.setattr(common, "send_telegram_message", lambda *a, **k: None)
    return send_notifications


@pytest.fixture
def ss(sync_env):
    import sync_store

    return sync_store


def _write_offers(cfg, offers):
    with open(cfg.NEW_OFFERS_JSON, "w", encoding="utf-8") as f:
        json.dump(offers, f)


def _profile(ss, code, data):
    ss.locked_rmw(code, lambda _existing: data)


def _read_profile(ss, code):
    return ss.locked_rmw(code, lambda d: None)


def _sub(n):
    return {
        "endpoint": f"https://push.example/{n}",
        "keys": {"p256dh": "k", "auth": "a"},
    }


OFFERS = [
    {"id": "111", "url": "https://www.aldi.ie/product/drill-111",
     "store": "ALDI", "title": "Cordless Drill", "description": "", "price": "29.99"},
    {"id": "222", "url": "https://www.aldi.ie/product/drill-bits-222",
     "store": "ALDI", "title": "Drill Bits", "description": "", "price": "9.99"},
    {"id": "333", "url": "https://www.lidl.ie/p/tent/p333",
     "store": "LIDL", "title": "Camping Tent", "description": "", "price": "49.99"},
]

ALERT = {"id": "a1", "keyword": "drill", "matchType": "anyWord", "createdAt": 1}


# ---------------------------------------------------------------------------
# Payload shape (Bug #4)
# ---------------------------------------------------------------------------
def test_payload_shape(sn):
    p = sn.build_payload("a1", "drill", 3)
    assert set(p) == {"title", "body", "url", "icon"}
    assert p["url"] == "/?view=alerts&alert=a1"
    assert "3 new matches for 'drill'" in p["body"]
    assert p["icon"] == "/img/lidaldi.png"


def test_payload_singular(sn):
    assert "1 new match for" in sn.build_payload("a1", "drill", 1)["body"]


def test_sent_payload_has_no_third_party_url(sn, ss, sync_env, monkeypatch):
    _write_offers(sync_env, OFFERS)
    _profile(ss, "CODE01", {
        "lastVisit": 0, "alerts": [ALERT], "tombstones": [],
        "pushSubscriptions": [_sub(1)], "notified": [],
    })
    sent = []

    def fake_send(sub, payload):
        sent.append((sub["endpoint"], payload))
        return "ok"

    monkeypatch.setattr(sn, "send_push", fake_send)
    sn.run()
    assert len(sent) == 1
    payload = sent[0][1]
    assert payload["url"] == "/?view=alerts&alert=a1"
    assert "aldi.ie" not in json.dumps(payload)
    assert "2 new matches for 'drill'" in payload["body"]


# ---------------------------------------------------------------------------
# Per-endpoint retry semantics (N5)
# ---------------------------------------------------------------------------
def test_failed_endpoint_retried_ok_endpoint_not_duplicated(sn, ss, sync_env, monkeypatch):
    _write_offers(sync_env, OFFERS)
    _profile(ss, "CODE01", {
        "lastVisit": 0, "alerts": [ALERT], "tombstones": [],
        "pushSubscriptions": [_sub(1), _sub(2)], "notified": [],
    })

    results = {"https://push.example/1": "ok", "https://push.example/2": "error"}
    sent = []

    def fake_send(sub, payload):
        sent.append(sub["endpoint"])
        return results[sub["endpoint"]]

    monkeypatch.setattr(sn, "send_push", fake_send)

    # Run 1: both endpoints attempted; only endpoint 1 recorded.
    sn.run()
    assert sent == ["https://push.example/1", "https://push.example/2"]
    prof = _read_profile(ss, "CODE01")
    eps = {e["endpoint"] for e in prof["notified"]}
    assert eps == {ss.endpoint_hash("https://push.example/1")}

    # Run 2: endpoint 2 recovers; only it is re-sent.
    sent.clear()
    results["https://push.example/2"] = "ok"
    sn.run()
    assert sent == ["https://push.example/2"]
    prof = _read_profile(ss, "CODE01")
    eps = {e["endpoint"] for e in prof["notified"]}
    assert eps == {
        ss.endpoint_hash("https://push.example/1"),
        ss.endpoint_hash("https://push.example/2"),
    }

    # Run 3: fully delivered; nothing sent.
    sent.clear()
    sn.run()
    assert sent == []


def test_legacy_url_ledger_entries_suppress_all_endpoints(sn, ss, sync_env, monkeypatch):
    """Pre-upgrade ledger entries (url-keyed, no endpoint) stay honored."""
    _write_offers(sync_env, OFFERS)
    now = time.time()
    _profile(ss, "CODE01", {
        "lastVisit": 0, "alerts": [ALERT], "tombstones": [],
        "pushSubscriptions": [_sub(1)],
        "notified": [
            {"alertId": "a1", "url": "https://www.aldi.ie/product/drill-111", "at": now},
            {"alertId": "a1", "url": "https://www.aldi.ie/product/drill-bits-222", "at": now},
        ],
    })
    sent = []
    monkeypatch.setattr(sn, "send_push", lambda sub, payload: sent.append(1) or "ok")
    sn.run()
    assert sent == []


def test_legacy_ledger_matches_url_keyed_offers(ss):
    """Offers without a stable id fall back to url; legacy entries match."""
    ledger = [{"alertId": "a1", "url": "https://x/1", "at": time.time()}]
    assert ss.already_notified(ledger, "a1", "https://x/1", ss.endpoint_hash("e"))
    assert not ss.already_notified(ledger, "a1", "https://x/2", ss.endpoint_hash("e"))
    assert not ss.already_notified(ledger, "a2", "https://x/1", ss.endpoint_hash("e"))


def test_expired_endpoint_removed(sn, ss, sync_env, monkeypatch):
    _write_offers(sync_env, OFFERS)
    _profile(ss, "CODE01", {
        "lastVisit": 0, "alerts": [ALERT], "tombstones": [],
        "pushSubscriptions": [_sub(1), _sub(2)], "notified": [],
    })
    results = {"https://push.example/1": "expired", "https://push.example/2": "ok"}
    monkeypatch.setattr(sn, "send_push", lambda sub, payload: results[sub["endpoint"]])
    sn.run()
    prof = _read_profile(ss, "CODE01")
    assert [s["endpoint"] for s in prof["pushSubscriptions"]] == ["https://push.example/2"]


# ---------------------------------------------------------------------------
# alertMatches persistence + GC
# ---------------------------------------------------------------------------
def test_alert_matches_recorded_on_delivery(sn, ss, sync_env, monkeypatch):
    _write_offers(sync_env, OFFERS)
    _profile(ss, "CODE01", {
        "lastVisit": 0, "alerts": [ALERT], "tombstones": [],
        "pushSubscriptions": [_sub(1)], "notified": [],
    })
    monkeypatch.setattr(sn, "send_push", lambda sub, payload: "ok")
    sn.run()
    prof = _read_profile(ss, "CODE01")
    am = prof["alertMatches"]
    assert set(am) == {"a1"}
    assert [e["id"] for e in am["a1"]] == ["111", "222"]
    assert all(isinstance(e["at"], (int, float)) for e in am["a1"])


def test_alert_matches_not_recorded_when_all_sends_fail(sn, ss, sync_env, monkeypatch):
    _write_offers(sync_env, OFFERS)
    _profile(ss, "CODE01", {
        "lastVisit": 0, "alerts": [ALERT], "tombstones": [],
        "pushSubscriptions": [_sub(1)], "notified": [],
    })
    monkeypatch.setattr(sn, "send_push", lambda sub, payload: "error")
    sn.run()
    prof = _read_profile(ss, "CODE01")
    assert prof.get("alertMatches", {}) == {}


def test_alert_matches_dedup_across_runs(sn, ss, sync_env, monkeypatch):
    _write_offers(sync_env, OFFERS)
    _profile(ss, "CODE01", {
        "lastVisit": 0, "alerts": [ALERT], "tombstones": [],
        "pushSubscriptions": [_sub(1), _sub(2)], "notified": [],
    })
    results = {"https://push.example/1": "ok", "https://push.example/2": "error"}
    monkeypatch.setattr(sn, "send_push", lambda sub, payload: results[sub["endpoint"]])
    sn.run()
    results["https://push.example/2"] = "ok"
    sn.run()
    prof = _read_profile(ss, "CODE01")
    assert [e["id"] for e in prof["alertMatches"]["a1"]] == ["111", "222"]


def test_gc_alert_matches_ttl_and_cap(ss):
    now = time.time()
    old = now - ss.ALERT_MATCHES_TTL_SEC - 1
    matches = {
        "a1": [{"id": "old", "at": old}]
        + [{"id": f"o{i}", "at": now} for i in range(ss.MAX_ALERT_MATCHES_PER_ALERT + 5)],
        "a2": [{"id": "old", "at": old}],
        "bad": "not-a-list",
    }
    out = ss.gc_alert_matches(matches, now=now)
    assert set(out) == {"a1"}
    assert len(out["a1"]) == ss.MAX_ALERT_MATCHES_PER_ALERT
    assert all(e["id"] != "old" for e in out["a1"])


def test_notified_ledger_gc_and_cap_preserved(sn, ss, sync_env, monkeypatch):
    _write_offers(sync_env, OFFERS)
    stale = time.time() - ss.NOTIFIED_TTL_SEC - 1
    _profile(ss, "CODE01", {
        "lastVisit": 0, "alerts": [ALERT], "tombstones": [],
        "pushSubscriptions": [_sub(1)],
        "notified": [{"alertId": "zz", "id": "zz", "endpoint": "zz", "at": stale}],
    })
    monkeypatch.setattr(sn, "send_push", lambda sub, payload: "ok")
    sn.run()
    prof = _read_profile(ss, "CODE01")
    assert all(e["alertId"] == "a1" for e in prof["notified"])
    assert len(prof["notified"]) <= ss.MAX_NOTIFIED
