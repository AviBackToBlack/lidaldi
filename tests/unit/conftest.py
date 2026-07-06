"""Fixtures for backend unit tests.

Points the config loader (T9) at a temporary config.toml + .env fixture
before importing the modules under test, so they can be exercised against
per-test temporary paths without a real installation.
"""

import os
import sys
import tempfile
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "offers_processing"))

_cfg_dir = Path(tempfile.mkdtemp(prefix="lidaldi-test-config-"))
(_cfg_dir / "processing").mkdir()
(_cfg_dir / "webroot").mkdir()
(_cfg_dir / "config.toml").write_text(
    f"""\
[paths]
offers_processing_dir = "{_cfg_dir / 'processing'}"
website_root_dir = "{_cfg_dir / 'webroot'}"

[sync]
allowed_origin = "https://example.test"

[push]
vapid_public_key = "test-vapid-public-key"
vapid_claims_email = "mailto:test@example.test"
""",
    encoding="utf-8",
)
(_cfg_dir / ".env").write_text(
    "TELEGRAM_BOT_TOKEN=dummy\nTELEGRAM_CHAT_ID=dummy\n", encoding="utf-8"
)
os.environ["LIDALDI_CONFIG"] = str(_cfg_dir / "config.toml")
os.environ["LIDALDI_ENV_FILE"] = str(_cfg_dir / ".env")

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
    """Point the shared config at a per-test SYNC_DIR and offers file."""
    from config_loader import get_config

    cfg = get_config()

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
def server(sync_env, monkeypatch):
    """Real sync_server (ThreadingHTTPServer) in a thread + temp SYNC_DIR."""
    import threading
    from http.server import ThreadingHTTPServer

    import sync_server

    # Tests fire many requests from one IP; don't trip the rate limiter.
    monkeypatch.setattr(sync_server, "RATE_MAX", 10000)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), sync_server.SyncHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    t.join(timeout=5)


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
    monkeypatch.setattr(cfg, "VAPID_PUBLIC_KEY", "test-vapid-public-key", raising=False)
    monkeypatch.setattr(cfg, "TELEGRAM_BOT_TOKEN", "dummy", raising=False)
    monkeypatch.setattr(cfg, "TELEGRAM_CHAT_ID", "dummy", raising=False)

    # Never hit the network from tests.
    monkeypatch.setattr(process_offers, "telegram", lambda msg: None)

    return process_offers
