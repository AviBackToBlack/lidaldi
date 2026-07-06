"""T11: Prometheus textfile metric-name parity in the new pipeline.

Freezes the pre-refactor metric inventory (names + types + label keys) and
runs each emitter against fixtures, asserting the emitted .prom content
covers the full set. Fails on any missing or renamed metric, a changed
type, or changed label keys.
"""

import json
import re
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Frozen inventory (contract for T14 docs): name -> (type, label keys)
# ---------------------------------------------------------------------------
PROCESS_OFFERS_METRICS = {
    "lidaldi_process_offers_last_run_timestamp_seconds": ("gauge", frozenset()),
    "lidaldi_process_offers_status": ("gauge", frozenset()),
    "lidaldi_process_offers_total_items": ("gauge", frozenset()),
    "lidaldi_process_offers_new_items": ("gauge", frozenset()),
    "lidaldi_process_offers_aldi_items": ("gauge", frozenset()),
    "lidaldi_process_offers_lidl_items": ("gauge", frozenset()),
    # T11 addition (not pre-refactor): first_seen store size.
    "lidaldi_process_offers_first_seen_size": ("gauge", frozenset()),
}

SEND_NOTIFICATIONS_METRICS = {
    "lidaldi_notifications_last_run_timestamp_seconds": ("gauge", frozenset()),
    "lidaldi_notifications_status": ("gauge", frozenset()),
    "lidaldi_notifications_profiles_scanned": ("counter", frozenset()),
    "lidaldi_notifications_profiles_with_alerts": ("counter", frozenset()),
    "lidaldi_notifications_push_total": ("counter", frozenset({"status"})),
    "lidaldi_notifications_subs_expired_removed": ("counter", frozenset()),
}
# Every label value the pre-refactor emitter produced unconditionally.
PUSH_TOTAL_STATUSES = {"ok", "expired", "error"}

SCRAPER_METRICS = {
    "lidaldi_scraper_last_run_timestamp_seconds": ("gauge", frozenset({"spider"})),
    "lidaldi_scraper_status": ("gauge", frozenset({"spider"})),
    "lidaldi_scraper_items_total": ("gauge", frozenset({"spider"})),
    "lidaldi_scraper_error_count": ("gauge", frozenset({"spider"})),
    "lidaldi_scraper_dropped_items": ("gauge", frozenset({"spider"})),
    "lidaldi_scraper_dropped_ratio": ("gauge", frozenset({"spider"})),
    "lidaldi_scraper_missing_ratio": ("gauge", frozenset({"spider", "field"})),
}
MISSING_RATIO_FIELDS = {"title", "description", "price"}

_SAMPLE_RE = re.compile(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{([^}]*)\})?\s+(\S+)$")
_LABEL_RE = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"')


def parse_prom(path):
    """Parse a textfile-exporter .prom file.

    Returns (types, samples): types maps metric name -> declared TYPE;
    samples is a list of (name, labels dict).
    """
    types_by_name = {}
    samples = []
    text = Path(path).read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("# TYPE "):
            _, _, rest = line.partition("# TYPE ")
            name, _, mtype = rest.partition(" ")
            types_by_name[name] = mtype.strip()
            continue
        if line.startswith("#"):
            continue
        m = _SAMPLE_RE.match(line)
        assert m, f"unparseable sample line: {line!r}"
        name, label_str, _value = m.groups()
        labels = dict(_LABEL_RE.findall(label_str or ""))
        samples.append((name, labels))
    return types_by_name, samples


def assert_inventory(path, inventory):
    types_by_name, samples = parse_prom(path)
    sample_names = {name for name, _ in samples}
    missing = set(inventory) - sample_names
    assert not missing, f"metrics missing from {path}: {sorted(missing)}"
    for name, (mtype, label_keys) in inventory.items():
        assert types_by_name.get(name) == mtype, (
            f"{name}: expected type {mtype}, got {types_by_name.get(name)}"
        )
        for sname, labels in samples:
            if sname == name:
                assert set(labels) == set(label_keys), (
                    f"{name}: expected labels {sorted(label_keys)}, "
                    f"got {sorted(labels)}"
                )
    return samples


# ---------------------------------------------------------------------------
# process_offers.py
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


def _write_process_offers_inputs(po):
    aldi = [
        _make_offer("ALDI", str(700000 + i),
                    f"https://www.aldi.ie/product/item-{i}-{700000 + i}", f"Aldi {i}")
        for i in range(30)
    ]
    lidl = [
        _make_offer("LIDL", f"/p/item-{i}/p{i}",
                    f"https://www.lidl.ie/p/item-{i}/p{i}", f"Lidl {i}")
        for i in range(30)
    ]
    for path, data in (
        (po.config.ALDI_OFFERS_JSON, aldi),
        (po.config.LIDL_OFFERS_JSON, lidl),
        (po.config.ALDI_SCRAPING_REPORT_JSON, {"overall_result": "SUCCESS"}),
        (po.config.LIDL_SCRAPING_REPORT_JSON, {"overall_result": "SUCCESS"}),
    ):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)


def test_process_offers_metric_parity(po, tmp_path, monkeypatch):
    prom_dir = tmp_path / "prom"
    monkeypatch.setattr(po.config, "PROM_TEXTFILE_DIR", str(prom_dir), raising=False)
    _write_process_offers_inputs(po)
    po.main()
    assert_inventory(prom_dir / "lidaldi_process_offers.prom",
                     PROCESS_OFFERS_METRICS)


def test_process_offers_metric_parity_on_failure(po, tmp_path, monkeypatch):
    """The FAILED path emits the same metric set as SUCCESS."""
    prom_dir = tmp_path / "prom"
    monkeypatch.setattr(po.config, "PROM_TEXTFILE_DIR", str(prom_dir), raising=False)
    with pytest.raises(SystemExit):
        po.main()  # required input files absent -> fatal()
    assert_inventory(prom_dir / "lidaldi_process_offers.prom",
                     PROCESS_OFFERS_METRICS)


# ---------------------------------------------------------------------------
# send_notifications.py
# ---------------------------------------------------------------------------
def test_send_notifications_metric_parity(sync_env, tmp_path, monkeypatch):
    import send_notifications as sn
    import sync_store

    prom_dir = tmp_path / "prom"
    monkeypatch.setattr(sn.config, "PROM_TEXTFILE_DIR", str(prom_dir), raising=False)
    monkeypatch.setattr(sn, "send_push", lambda sub, payload: "ok")

    with open(sn.config.NEW_OFFERS_JSON, "w", encoding="utf-8") as f:
        json.dump([{"id": "111", "url": "https://www.aldi.ie/product/drill-111",
                    "store": "ALDI", "title": "Cordless Drill",
                    "description": "", "price": "29.99"}], f)
    profile = {
        "alerts": [{"id": "a1", "keyword": "drill",
                    "matchType": "anyWord", "createdAt": 1}],
        "pushSubscriptions": [{"endpoint": "https://push.example/1",
                               "keys": {"p256dh": "k", "auth": "a"}}],
    }
    sync_store.locked_rmw("METRICSPARITY01", lambda _existing: profile)

    sn.run()
    samples = assert_inventory(prom_dir / "lidaldi_send_notifications.prom",
                               SEND_NOTIFICATIONS_METRICS)
    statuses = {labels["status"] for name, labels in samples
                if name == "lidaldi_notifications_push_total"}
    assert statuses == PUSH_TOTAL_STATUSES


# ---------------------------------------------------------------------------
# scraper ErrorCheckingPipeline
# ---------------------------------------------------------------------------
class _FakeSettings:
    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


class _FakeStats:
    def get_value(self, key, default=None):
        return 0


class _FakeCrawler:
    def __init__(self, settings):
        self.settings = _FakeSettings(settings)
        self.stats = _FakeStats()


class _FakeLogger:
    def warning(self, msg):
        raise AssertionError(f"scraper metrics emission failed: {msg}")


class _FakeSpider:
    def __init__(self, name, report_file, crawler):
        self.name = name
        self.report_file = report_file
        self.crawler = crawler
        self.logger = _FakeLogger()


def test_scraper_pipeline_metric_parity(tmp_path):
    # Stub itemadapter so pipelines.py imports without Scrapy installed.
    sys.modules.setdefault("itemadapter", types.ModuleType("itemadapter"))
    sys.modules["itemadapter"].ItemAdapter = object
    sys.path.insert(0, str(REPO_ROOT / "scraper" / "lidaldi"))
    try:
        import pipelines
    finally:
        sys.path.pop(0)

    prom_dir = tmp_path / "prom"
    crawler = _FakeCrawler({
        "PROM_TEXTFILE_DIR": str(prom_dir),
        "OFFERS_PROCESSING_DIR": str(REPO_ROOT / "offers_processing"),
    })
    pipeline = pipelines.ErrorCheckingPipeline.from_crawler(crawler)
    spider = _FakeSpider("aldi", str(tmp_path / "report.json"), crawler)
    for i in range(150):
        pipeline.process_item({
            "category": "Garden", "title": f"Item {i}",
            "description": "desc", "store_availability": "In store",
            "price": "9.99", "image_urls": ["https://img.example/x.jpg"],
        }, spider)
    pipeline.close_spider(spider)

    samples = assert_inventory(prom_dir / "lidaldi_scraper_aldi.prom",
                               SCRAPER_METRICS)
    assert all(labels["spider"] == "aldi" for _name, labels in samples)
    fields = {labels["field"] for name, labels in samples
              if name == "lidaldi_scraper_missing_ratio"}
    assert fields == MISSING_RATIO_FIELDS
