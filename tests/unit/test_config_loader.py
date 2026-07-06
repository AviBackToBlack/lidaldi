"""Tests for the TOML/.env config loader (T9, D3)."""

import sys
import types

import pytest

import config_loader
from config_loader import ConfigError


VALID_TOML = """\
[paths]
offers_processing_dir = "{processing}"
website_root_dir = "{webroot}"

[sync]
allowed_origin = "https://example.test"

[push]
vapid_public_key = "pub-key"
vapid_claims_email = "mailto:test@example.test"

[scraper]
images_store = "/tmp/images"
"""

VALID_ENV = "TELEGRAM_BOT_TOKEN=tok\nTELEGRAM_CHAT_ID=chat\n"


def write_config(tmp_path, toml_text=None, env_text=VALID_ENV):
    processing = tmp_path / "processing"
    webroot = tmp_path / "webroot"
    processing.mkdir(exist_ok=True)
    webroot.mkdir(exist_ok=True)
    if toml_text is None:
        toml_text = VALID_TOML.format(processing=processing, webroot=webroot)
    toml_path = tmp_path / "config.toml"
    toml_path.write_text(toml_text, encoding="utf-8")
    env_path = tmp_path / ".env"
    if env_text is not None:
        env_path.write_text(env_text, encoding="utf-8")
    return toml_path, env_path


def test_load_valid_toml(tmp_path):
    toml_path, env_path = write_config(tmp_path)
    cfg = config_loader.load(config_path=str(toml_path), env_path=str(env_path))
    processing = str(tmp_path / "processing")
    assert cfg.OFFERS_PROCESSING_DIR == processing
    assert cfg.ALDI_OFFERS_JSON == processing + "/aldi_offers.json"
    assert cfg.FIRST_SEEN_JSON == processing + "/first_seen.json"
    assert cfg.SYNC_DIR == processing + "/sync"
    assert cfg.SYNC_SERVER_HOST == "127.0.0.1"
    assert cfg.SYNC_SERVER_PORT == 8099
    assert cfg.SYNC_ALLOWED_ORIGIN == "https://example.test"
    assert cfg.OFFERS_JSON == str(tmp_path / "webroot") + "/offers.json"
    assert cfg.PROM_TEXTFILE_DIR is None
    assert cfg.VAPID_PUBLIC_KEY == "pub-key"
    assert cfg.VAPID_PRIVATE_KEY_PATH == processing + "/vapid_private.pem"
    assert cfg.IMAGES_STORE == "/tmp/images"
    assert cfg.IMAGES_EXPIRES == 90
    assert cfg.DOWNLOAD_DELAY == 3
    assert cfg.SCRAPING_REPORT_DIR == processing


def test_env_secret_injection(tmp_path):
    toml_path, env_path = write_config(
        tmp_path,
        env_text=(
            "# comment line\n"
            "\n"
            "export TELEGRAM_BOT_TOKEN='quoted-tok'\n"
            'TELEGRAM_CHAT_ID="chat-42"\n'
            "VAPID_PRIVATE_KEY_PATH=/custom/vapid.pem\n"
        ),
    )
    cfg = config_loader.load(config_path=str(toml_path), env_path=str(env_path))
    assert cfg.TELEGRAM_BOT_TOKEN == "quoted-tok"
    assert cfg.TELEGRAM_CHAT_ID == "chat-42"
    assert cfg.VAPID_PRIVATE_KEY_PATH == "/custom/vapid.pem"


def test_process_environment_overrides_env_file(tmp_path, monkeypatch):
    toml_path, env_path = write_config(tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "from-environ")
    cfg = config_loader.load(config_path=str(toml_path), env_path=str(env_path))
    assert cfg.TELEGRAM_BOT_TOKEN == "from-environ"


def test_missing_secret_error(tmp_path, monkeypatch):
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    toml_path, _ = write_config(tmp_path, env_text="TELEGRAM_BOT_TOKEN=tok\n")
    with pytest.raises(ConfigError, match="TELEGRAM_CHAT_ID"):
        config_loader.load(config_path=str(toml_path), env_path=str(tmp_path / ".env"))


def test_missing_required_key_error(tmp_path):
    toml_path, env_path = write_config(
        tmp_path, toml_text='[paths]\nwebsite_root_dir = "/tmp/webroot"\n'
    )
    with pytest.raises(ConfigError, match=r"\[paths\] offers_processing_dir"):
        config_loader.load(config_path=str(toml_path), env_path=str(env_path))


def test_invalid_toml_error(tmp_path):
    toml_path, env_path = write_config(tmp_path, toml_text="[paths\n")
    with pytest.raises(ConfigError, match="invalid TOML"):
        config_loader.load(config_path=str(toml_path), env_path=str(env_path))


def test_non_integer_port_rejected(tmp_path):
    processing = tmp_path / "processing"
    webroot = tmp_path / "webroot"
    toml_text = VALID_TOML.format(processing=processing, webroot=webroot)
    toml_text = toml_text.replace(
        'allowed_origin = "https://example.test"',
        'port = "8099"\nallowed_origin = "https://example.test"',
    )
    toml_path, env_path = write_config(tmp_path, toml_text=toml_text)
    with pytest.raises(ConfigError, match="port must be an integer"):
        config_loader.load(config_path=str(toml_path), env_path=str(env_path))


def test_secret_in_toml_rejected(tmp_path):
    processing = tmp_path / "processing"
    webroot = tmp_path / "webroot"
    toml_text = VALID_TOML.format(processing=processing, webroot=webroot)
    toml_text += '\n[telegram]\ntelegram_bot_token = "tok"\n'
    toml_path, env_path = write_config(tmp_path, toml_text=toml_text)
    with pytest.raises(ConfigError, match="must live in .env"):
        config_loader.load(config_path=str(toml_path), env_path=str(env_path))


def test_toml_preferred_over_legacy(tmp_path, monkeypatch):
    toml_path, env_path = write_config(tmp_path)
    legacy = types.ModuleType("config")
    legacy.OFFERS_PROCESSING_DIR = "/legacy/path"
    monkeypatch.setitem(sys.modules, "config", legacy)
    monkeypatch.setenv("LIDALDI_CONFIG", str(toml_path))
    monkeypatch.setenv("LIDALDI_ENV_FILE", str(env_path))
    cfg = config_loader.load()
    assert cfg.OFFERS_PROCESSING_DIR == str(tmp_path / "processing")


def test_legacy_fallback_warns(tmp_path, monkeypatch):
    legacy = types.ModuleType("config")
    legacy.OFFERS_PROCESSING_DIR = "/legacy/path"
    monkeypatch.setitem(sys.modules, "config", legacy)
    monkeypatch.delenv("LIDALDI_CONFIG", raising=False)
    monkeypatch.setattr(config_loader, "_HERE", str(tmp_path / "nowhere" / "sub"))
    with pytest.warns(DeprecationWarning, match="legacy config.py"):
        cfg = config_loader.load()
    assert cfg is legacy


def test_no_config_at_all_errors(tmp_path, monkeypatch):
    monkeypatch.delenv("LIDALDI_CONFIG", raising=False)
    monkeypatch.setattr(config_loader, "_HERE", str(tmp_path / "nowhere" / "sub"))
    monkeypatch.setitem(sys.modules, "config", None)
    with pytest.raises(ConfigError, match="no configuration found"):
        config_loader.load()


def test_python_version_guard_message():
    err = config_loader._python_version_error((3, 10, 20))
    assert err is not None
    assert "Python >= 3.12" in err
    assert "3.10.20" in err
    assert config_loader._python_version_error((3, 12, 0)) is None
    assert config_loader._python_version_error(sys.version_info) is None
