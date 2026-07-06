"""Fixtures for backend unit tests.

Installs a stub `config` module before importing process_offers, so the
module under test can be exercised against per-test temporary paths.
"""

import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "offers_processing"))

_stub_config = types.ModuleType("config")
sys.modules.setdefault("config", _stub_config)

# Stub the webpush libs so send_notifications imports without the real
# pywebpush installed; tests monkeypatch send_push and never hit the network.
_stub_pywebpush = types.ModuleType("pywebpush")


class _StubWebPusher:  # pragma: no cover - replaced in tests
    def __init__(self, *a, **kw):
        raise RuntimeError("network push not available in tests")


class _StubWebPushException(Exception):
    def __init__(self, *a, response=None, **kw):
        super().__init__(*a)
        self.response = response


_stub_pywebpush.WebPusher = _StubWebPusher
_stub_pywebpush.WebPushException = _StubWebPushException
sys.modules.setdefault("pywebpush", _stub_pywebpush)

_stub_py_vapid = types.ModuleType("py_vapid")


class _StubVapid:  # pragma: no cover - replaced in tests
    @classmethod
    def from_file(cls, path):
        raise RuntimeError("VAPID keys not available in tests")


_stub_py_vapid.Vapid = _StubVapid
sys.modules.setdefault("py_vapid", _stub_py_vapid)


@pytest.fixture
def sync_env(tmp_path, monkeypatch):
    """Point the shared config stub at a per-test SYNC_DIR and offers file."""
    import config as cfg

    sync_dir = tmp_path / "sync"
    sync_dir.mkdir()
    monkeypatch.setattr(cfg, "SYNC_DIR", str(sync_dir), raising=False)
    monkeypatch.setattr(cfg, "NEW_OFFERS_JSON", str(tmp_path / "new_offers.json"), raising=False)
    monkeypatch.setattr(cfg, "PROM_TEXTFILE_DIR", None, raising=False)
    monkeypatch.setattr(cfg, "SYNC_ALLOWED_ORIGIN", "https://example.test", raising=False)
    monkeypatch.setattr(cfg, "VAPID_PRIVATE_KEY_PATH", str(tmp_path / "vapid.pem"), raising=False)
    monkeypatch.setattr(cfg, "VAPID_CLAIMS_EMAIL", "mailto:test@example.test", raising=False)
    return cfg


@pytest.fixture
def po(tmp_path, monkeypatch):
    """Import process_offers with a stub config pointed at tmp_path."""
    import process_offers

    cfg = process_offers.config
    processing = tmp_path / "processing"
    webroot = tmp_path / "webroot"
    processing.mkdir()
    webroot.mkdir()

    monkeypatch.setattr(cfg, "ALDI_OFFERS_JSON", str(processing / "aldi_offers.json"), raising=False)
    monkeypatch.setattr(cfg, "LIDL_OFFERS_JSON", str(processing / "lidl_offers.json"), raising=False)
    monkeypatch.setattr(cfg, "ALDI_SCRAPING_REPORT_JSON", str(processing / "aldi_scraping_report.json"), raising=False)
    monkeypatch.setattr(cfg, "LIDL_SCRAPING_REPORT_JSON", str(processing / "lidl_scraping_report.json"), raising=False)
    monkeypatch.setattr(cfg, "NEW_OFFERS_JSON", str(processing / "new_offers.json"), raising=False)
    monkeypatch.setattr(cfg, "FIRST_SEEN_JSON", str(processing / "first_seen.json"), raising=False)
    monkeypatch.setattr(cfg, "LAST_RUN_STATE_JSON", str(processing / "last_run.json"), raising=False)
    monkeypatch.setattr(cfg, "PROM_TEXTFILE_DIR", None, raising=False)
    monkeypatch.setattr(cfg, "OFFERS_JSON", str(webroot / "offers.json"), raising=False)
    monkeypatch.setattr(cfg, "META_JSON", str(webroot / "meta.json"), raising=False)
    monkeypatch.setattr(cfg, "INDEX_TEMPLATE", str(webroot / "index.html.tpl"), raising=False)
    monkeypatch.setattr(cfg, "INDEX_HTML", str(webroot / "index.html"), raising=False)
    monkeypatch.setattr(cfg, "VAPID_PUBLIC_KEY", "test-vapid-public-key", raising=False)
    monkeypatch.setattr(cfg, "TELEGRAM_BOT_TOKEN", "dummy", raising=False)
    monkeypatch.setattr(cfg, "TELEGRAM_CHAT_ID", "dummy", raising=False)

    # Never hit the network from tests.
    monkeypatch.setattr(process_offers, "telegram", lambda msg: None)

    return process_offers
