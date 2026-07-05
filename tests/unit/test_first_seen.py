"""T2: first_seen store, id-based new-offer classification, offers.json/meta.json."""

import json
import os


DAY = 86400


# ---------------------------------------------------------------------------
# update_first_seen / load / save
# ---------------------------------------------------------------------------
def test_first_run_seeding(po):
    assert po.load_first_seen() is None
    store = {}
    new_ids = po.update_first_seen(store, {"111", "/p/foo"}, now=1000)
    assert new_ids == {"111", "/p/foo"}
    assert store["111"] == {"first_seen": 1000, "last_seen": 1000}
    assert store["/p/foo"] == {"first_seen": 1000, "last_seen": 1000}


def test_first_seen_stable_across_runs(po):
    store = {}
    po.update_first_seen(store, {"a", "b"}, now=1000)
    new_ids = po.update_first_seen(store, {"a", "b"}, now=5000)
    assert new_ids == set()
    assert store["a"]["first_seen"] == 1000
    assert store["b"]["first_seen"] == 1000
    assert store["a"]["last_seen"] == 5000


def test_new_id_detected(po):
    store = {}
    po.update_first_seen(store, {"a"}, now=1000)
    new_ids = po.update_first_seen(store, {"a", "c"}, now=2000)
    assert new_ids == {"c"}
    assert store["c"]["first_seen"] == 2000


def test_slug_change_same_sku_not_new(po):
    """N3: ALDI slug churn changes the URL but not the SKU-based id."""
    store = {}
    po.update_first_seen(store, {"743956"}, now=1000)  # old slug URL, same SKU
    new_ids = po.update_first_seen(store, {"743956"}, now=2000)  # new slug URL
    assert new_ids == set()
    assert store["743956"]["first_seen"] == 1000


def test_gc_removes_stale_entries(po):
    store = {
        "stale": {"first_seen": 0, "last_seen": 0},
        "kept": {"first_seen": 0, "last_seen": 0},
    }
    now = 181 * DAY
    po.update_first_seen(store, {"kept"}, now=now)
    assert "stale" not in store
    assert store["kept"]["first_seen"] == 0
    assert store["kept"]["last_seen"] == now


def test_gc_keeps_recent_absent_entries(po):
    store = {"absent": {"first_seen": 0, "last_seen": 0}}
    po.update_first_seen(store, set(), now=179 * DAY)
    assert "absent" in store


def test_save_and_load_roundtrip(po):
    store = {"a": {"first_seen": 1, "last_seen": 2}}
    po.save_first_seen(store)
    assert po.load_first_seen() == store


def test_load_legacy_flat_mapping(po):
    with open(po.config.FIRST_SEEN_JSON, "w", encoding="utf-8") as f:
        json.dump({"a": 123}, f)
    assert po.load_first_seen() == {"a": {"first_seen": 123, "last_seen": 123}}


def test_load_corrupt_store_returns_none(po):
    with open(po.config.FIRST_SEEN_JSON, "w", encoding="utf-8") as f:
        f.write("{not json")
    assert po.load_first_seen() is None


def test_corrupt_store_quarantined_and_alerted(po, monkeypatch):
    alerts = []
    monkeypatch.setattr(po, "telegram", alerts.append)
    with open(po.config.FIRST_SEEN_JSON, "w", encoding="utf-8") as f:
        f.write("{not json")
    assert po.load_first_seen() is None
    assert not os.path.exists(po.config.FIRST_SEEN_JSON)
    corrupt_path = po.config.FIRST_SEEN_JSON + ".corrupt"
    with open(corrupt_path, encoding="utf-8") as f:
        assert f.read() == "{not json"
    assert len(alerts) == 1
    assert "first_seen" in alerts[0]


def test_non_dict_store_quarantined(po):
    with open(po.config.FIRST_SEEN_JSON, "w", encoding="utf-8") as f:
        json.dump(["not", "a", "dict"], f)
    assert po.load_first_seen() is None
    assert os.path.exists(po.config.FIRST_SEEN_JSON + ".corrupt")


# ---------------------------------------------------------------------------
# Sanity-ratio guard
# ---------------------------------------------------------------------------
def test_sanity_ratio_guard(po):
    assert po.exceeds_sanity_ratio(40, 100) is True
    assert po.exceeds_sanity_ratio(30, 100) is False
    assert po.exceeds_sanity_ratio(0, 100) is False
    assert po.exceeds_sanity_ratio(0, 0) is False


# ---------------------------------------------------------------------------
# write_atomic
# ---------------------------------------------------------------------------
def test_write_atomic(po, tmp_path):
    path = str(tmp_path / "out.json")
    po.write_atomic(path, "first")
    po.write_atomic(path, "second")
    with open(path, encoding="utf-8") as f:
        assert f.read() == "second"
    assert not os.path.exists(path + ".tmp")


# ---------------------------------------------------------------------------
# Simulated two-run pipeline through main()
# ---------------------------------------------------------------------------
def _make_offer(store, pid, url, title):
    return {
        "store": store,
        "id": pid,
        "url": url,
        "scraped_at": 1000,
        "category": "Garden",
        "title": title,
        "description": "desc",
        "store_availability": "Unknown",
        "price": "9.99",
        "image_urls": [],
    }


def _write_inputs(po, aldi_offers, lidl_offers):
    for path, data in (
        (po.config.ALDI_OFFERS_JSON, aldi_offers),
        (po.config.LIDL_OFFERS_JSON, lidl_offers),
        (po.config.ALDI_SCRAPING_REPORT_JSON, {"overall_result": "SUCCESS"}),
        (po.config.LIDL_SCRAPING_REPORT_JSON, {"overall_result": "SUCCESS"}),
    ):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    with open(po.config.INDEX_TEMPLATE, "w", encoding="utf-8") as f:
        f.write(
            "<script>var offers=%%SPECIAL_OFFERS_DATA%%;"
            "var meta=%%SPECIAL_OFFERS_META_DATA%%;</script>"
            '<body data-vapid="%%VAPID_PUBLIC_KEY%%"></body>'
        )


def _catalog(po, extra=None):
    aldi = [
        _make_offer("ALDI", str(700000 + i), f"https://www.aldi.ie/product/item-{i}-{700000 + i}", f"Aldi {i}")
        for i in range(30)
    ]
    lidl = [
        _make_offer("LIDL", f"/p/item-{i}/p{i}", f"https://www.lidl.ie/p/item-{i}/p{i}", f"Lidl {i}")
        for i in range(30)
    ]
    if extra:
        aldi = aldi + extra
    _write_inputs(po, aldi, lidl)


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_two_run_pipeline(po):
    # Run 1: no prior store -> seed everything, classify nothing as new.
    _catalog(po)
    po.main()
    assert _read(po.config.NEW_OFFERS_JSON) == []
    store1 = po.load_first_seen()
    assert len(store1) == 60

    offers = _read(po.config.OFFERS_JSON)
    assert len(offers) == 60
    for it in offers:
        assert it["id"]
        assert it["first_seen"] == store1[it["id"]]["first_seen"]
        assert "scraped_at" in it
    meta = _read(po.config.META_JSON)
    assert set(meta) == {"lastUpdated", "vapidPublicKey"}
    assert meta["vapidPublicKey"] == "test-vapid-public-key"

    index_html = open(po.config.INDEX_HTML, encoding="utf-8").read()
    assert '"first_seen"' in index_html
    assert 'data-vapid="test-vapid-public-key"' in index_html

    # Run 2: unchanged catalog -> zero new offers, timestamps unchanged.
    po.main()
    assert _read(po.config.NEW_OFFERS_JSON) == []
    store2 = po.load_first_seen()
    assert {k: v["first_seen"] for k, v in store2.items()} == {
        k: v["first_seen"] for k, v in store1.items()
    }

    # Run 3: one genuinely new id -> exactly one new offer with first_seen.
    new_item = _make_offer(
        "ALDI", "999999", "https://www.aldi.ie/product/brand-new-999999", "Brand New"
    )
    _catalog(po, extra=[new_item])
    po.main()
    new_offers = _read(po.config.NEW_OFFERS_JSON)
    assert len(new_offers) == 1
    assert new_offers[0]["id"] == "999999"
    store3 = po.load_first_seen()
    assert new_offers[0]["first_seen"] == store3["999999"]["first_seen"]
    assert store3["700000"]["first_seen"] == store1["700000"]["first_seen"]


def test_slug_change_end_to_end(po):
    """N3 end-to-end: same ALDI SKU under a new slug URL is NOT new."""
    _catalog(po)
    po.main()

    aldi = [
        _make_offer("ALDI", str(700000 + i), f"https://www.aldi.ie/product/renamed-{i}-{700000 + i}", f"Aldi {i}")
        for i in range(30)
    ]
    lidl = [
        _make_offer("LIDL", f"/p/item-{i}/p{i}", f"https://www.lidl.ie/p/item-{i}/p{i}", f"Lidl {i}")
        for i in range(30)
    ]
    _write_inputs(po, aldi, lidl)
    po.main()
    assert _read(po.config.NEW_OFFERS_JSON) == []


def test_corrupt_store_end_to_end(po):
    """A corrupted store must not break the run or fire notifications;
    the corrupt file is preserved and the store reseeded."""
    _catalog(po)
    po.main()
    with open(po.config.FIRST_SEEN_JSON, "w", encoding="utf-8") as f:
        f.write("{not json")
    po.main()
    assert _read(po.config.NEW_OFFERS_JSON) == []
    assert os.path.exists(po.config.FIRST_SEEN_JSON + ".corrupt")
    assert len(po.load_first_seen()) == 60


def test_sanity_ratio_suppresses_notifications(po):
    """A suspicious flood of new ids must not fire notifications."""
    _catalog(po)
    po.main()

    aldi = [
        _make_offer("ALDI", str(800000 + i), f"https://www.aldi.ie/product/flood-{i}-{800000 + i}", f"Flood {i}")
        for i in range(30)
    ]
    lidl = [
        _make_offer("LIDL", f"/p/item-{i}/p{i}", f"https://www.lidl.ie/p/item-{i}/p{i}", f"Lidl {i}")
        for i in range(30)
    ]
    _write_inputs(po, aldi, lidl)
    po.main()
    assert _read(po.config.NEW_OFFERS_JSON) == []
