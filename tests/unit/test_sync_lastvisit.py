"""T4: lastVisit semantics (Bug #2/N1 server half) — docs/sync-contract.md.

Integration tests against a real sync_server in a thread + temp SYNC_DIR
(`server` fixture in conftest).
"""

import json
import time
import urllib.error
import urllib.request


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
# Read vs advance split
# ---------------------------------------------------------------------------
def test_get_never_advances_lastvisit(server):
    _post(server, "CODE01", {"lastVisit": 1000})
    for _ in range(3):
        _, body = _get(server, "CODE01")
        assert body["lastVisit"] == 1000


def test_post_advances_via_max(server):
    _post(server, "CODE01", {"lastVisit": 1000})
    _, body = _post(server, "CODE01", {"lastVisit": 2000})
    assert body["lastVisit"] == 2000
    _, body = _post(server, "CODE01", {"lastVisit": 1500})
    assert body["lastVisit"] == 2000


def test_post_lastvisit_zero_does_not_regress(server):
    _post(server, "CODE01", {"lastVisit": 1000})
    _, body = _post(server, "CODE01", {"lastVisit": 0})
    assert body["lastVisit"] == 1000


def test_post_lastvisit_omitted_does_not_regress(server):
    """A read-only client (e.g. registering a push sub) must be able to
    POST without advancing anyone's lastVisit."""
    _post(server, "CODE01", {"lastVisit": 1000})
    sub = {"endpoint": "https://push.example/1",
           "keys": {"p256dh": "k", "auth": "a"}}
    _, body = _post(server, "CODE01", {"pushSubscription": sub})
    assert body["lastVisit"] == 1000
    _, body = _get(server, "CODE01")
    assert body["lastVisit"] == 1000


def _post_expect_400(server, body):
    req = urllib.request.Request(
        f"{server}/api/sync/CODE01",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req)
        assert False, "expected 400"
    except urllib.error.HTTPError as e:
        assert e.code == 400


def test_post_negative_lastvisit_rejected(server):
    _post_expect_400(server, {"lastVisit": -1})


def test_post_bool_lastvisit_rejected(server):
    """JSON true must not be coerced to lastVisit=1."""
    _post_expect_400(server, {"lastVisit": True})
    _post_expect_400(server, {"lastVisit": False})


def test_post_nonfinite_lastvisit_rejected(server):
    """json.loads accepts NaN/Infinity; they must be a 400, not a 500."""
    for raw in (b'{"lastVisit": NaN}', b'{"lastVisit": Infinity}'):
        req = urllib.request.Request(
            f"{server}/api/sync/CODE01",
            data=raw,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req)
            assert False, "expected 400"
        except urllib.error.HTTPError as e:
            assert e.code == 400


# ---------------------------------------------------------------------------
# The legacy self-race (N1): documented contract keeps the "new" window
# ---------------------------------------------------------------------------
def test_legacy_self_race_sequence_contract(server):
    """Simulate the legacy sequence POST(now) -> GET and assert that a
    client following docs/sync-contract.md keeps a correct "new" window.

    first_seen timeline: offer X first_seen=1500. Previous visit L0=1000.
    """
    L0 = 1000
    now = 2000
    _post(server, "CODE01", {"lastVisit": L0})

    # Correct client: GET first, remember bootLastVisit.
    _, body = _get(server, "CODE01")
    boot_last_visit = body["lastVisit"]
    assert boot_last_visit == L0

    # Advance once per session (after render).
    _, body = _post(server, "CODE01", {"lastVisit": now})
    assert body["lastVisit"] == now

    # Legacy bug: a subsequent GET returns the just-advanced value...
    _, body = _get(server, "CODE01")
    assert body["lastVisit"] == now
    # ...but per contract rule 2 the client keeps bootLastVisit for this
    # session, so offer X (first_seen=1500) stays "new".
    first_seen_x = 1500
    assert first_seen_x > boot_last_visit          # correct client: X is new
    assert not first_seen_x > body["lastVisit"]    # legacy client: X vanished

    # A later session (device B) boots against the advanced value.
    _, body = _get(server, "CODE01")
    assert body["lastVisit"] == now


# ---------------------------------------------------------------------------
# Merge / tombstone regressions (unchanged by T4)
# ---------------------------------------------------------------------------
def test_alert_merge_keeps_existing_when_omitted(server):
    _post(server, "CODE01", {"lastVisit": 1, "alerts": [ALERT]})
    _, body = _post(server, "CODE01", {"lastVisit": 2})
    assert [a["id"] for a in body["alerts"]] == ["a1"]


def test_alert_merge_newer_created_at_wins(server):
    _post(server, "CODE01", {"alerts": [ALERT]})
    newer = dict(ALERT, keyword="hammer", createdAt=2)
    _, body = _post(server, "CODE01", {"alerts": [newer]})
    assert body["alerts"][0]["keyword"] == "hammer"


def test_tombstone_prevents_resurrection(server):
    _post(server, "CODE01", {"alerts": [ALERT]})
    _post(server, "CODE01", {"deletedAlertIds": [{"id": "a1", "at": time.time()}]})
    # A stale device re-posts the deleted alert: it must stay dead.
    _, body = _post(server, "CODE01", {"alerts": [ALERT]})
    assert body["alerts"] == []
    assert any(t["id"] == "a1" for t in body["tombstones"])
    _, body = _get(server, "CODE01")
    assert body["alerts"] == []


def test_tombstoned_alert_filtered_from_get(server):
    _post(server, "CODE01", {"alerts": [ALERT]})
    _post(server, "CODE01", {"deletedAlertIds": [{"id": "a1", "at": time.time()}]})
    _, body = _get(server, "CODE01")
    assert body["alerts"] == []
    assert body["lastVisit"] == 0
