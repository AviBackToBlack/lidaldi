"""LIDALDI configuration loader (T9, deviation D3).

Non-secret configuration lives in config.toml (parsed with stdlib
``tomllib``); secrets live in a .env file and/or the process environment.
When no config.toml is found the loader falls back to the legacy
``config.py`` module with a deprecation warning, so existing installs keep
working during the migration.

Resolution order for the TOML file:
    1. explicit ``config_path`` argument
    2. $LIDALDI_CONFIG
    3. config.toml next to this file (offers_processing/)
    4. config.toml in the parent directory (repo root)

Resolution order for the secrets file:
    1. explicit ``env_path`` argument
    2. $LIDALDI_ENV_FILE
    3. .env next to the chosen config.toml

Process environment variables override values from the .env file.
"""

import os
import sys
import types
import warnings


def _python_version_error(version_info):
    """Return an error message if the interpreter is too old, else None."""
    if version_info < (3, 12):
        found = ".".join(str(p) for p in version_info[:3])
        return (
            "lidaldi requires Python >= 3.12 (decision D3); "
            f"found {found}. Use the pyenv-managed lidaldi runtime "
            "(PYENV_VERSION=lidaldi python) or another Python >= 3.12."
        )
    return None


_err = _python_version_error(sys.version_info)
if _err:
    sys.exit(_err)

import tomllib  # noqa: E402  (guarded import: requires Python >= 3.12)


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


# Secrets that must come from .env / the environment, never from TOML.
_SECRET_KEYS = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")

_HERE = os.path.dirname(os.path.abspath(__file__))


def parse_env_file(path):
    """Parse a minimal .env file into a dict.

    Supports ``KEY=value`` lines, blank lines and ``#`` comments, an
    optional ``export `` prefix, and single/double quotes around values.
    """
    result = {}
    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].lstrip()
            if "=" not in line:
                raise ConfigError(f"{path}:{lineno}: expected KEY=value, got {raw.strip()!r}")
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            if not key:
                raise ConfigError(f"{path}:{lineno}: empty key")
            result[key] = value
    return result


def _find_config_path(config_path):
    if config_path:
        if not os.path.exists(config_path):
            raise ConfigError(f"config file not found: {config_path}")
        return config_path
    env_path = os.environ.get("LIDALDI_CONFIG")
    if env_path:
        if not os.path.exists(env_path):
            raise ConfigError(f"$LIDALDI_CONFIG points to a missing file: {env_path}")
        return env_path
    for candidate in (
        os.path.join(_HERE, "config.toml"),
        os.path.join(os.path.dirname(_HERE), "config.toml"),
    ):
        if os.path.exists(candidate):
            return candidate
    return None


def _load_secrets(env_path, toml_path):
    if not env_path:
        env_path = os.environ.get("LIDALDI_ENV_FILE")
    if not env_path:
        candidate = os.path.join(os.path.dirname(os.path.abspath(toml_path)), ".env")
        env_path = candidate if os.path.exists(candidate) else None
    elif not os.path.exists(env_path):
        raise ConfigError(f".env file not found: {env_path}")
    secrets = parse_env_file(env_path) if env_path else {}
    # Process environment overrides file values.
    for key in _SECRET_KEYS + ("VAPID_PRIVATE_KEY_PATH",):
        if key in os.environ:
            secrets[key] = os.environ[key]
    return secrets


def _require(table, section, key, expected_type=str):
    try:
        value = table[section][key]
    except KeyError:
        raise ConfigError(f"config.toml: missing required key [{section}] {key}") from None
    if not isinstance(value, expected_type) or (expected_type is str and not value):
        raise ConfigError(
            f"config.toml: [{section}] {key} must be a non-empty {expected_type.__name__}"
        )
    return value


def _optional(table, section, key, default=None):
    return table.get(section, {}).get(key, default)


def _load_toml(toml_path, env_path):
    with open(toml_path, "rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f"invalid TOML in {toml_path}: {e}") from None

    for section in data.values():
        if isinstance(section, dict):
            for key in section:
                if key.upper() in _SECRET_KEYS:
                    raise ConfigError(
                        f"config.toml: {key} is a secret and must live in .env, not TOML"
                    )

    secrets = _load_secrets(env_path, toml_path)

    cfg = types.SimpleNamespace()

    processing = _require(data, "paths", "offers_processing_dir")
    webroot = _require(data, "paths", "website_root_dir")
    cfg.OFFERS_PROCESSING_DIR = processing
    cfg.WEBSITE_ROOT_DIR = webroot

    def _path(key, default):
        return _optional(data, "paths", key, default)

    cfg.ALDI_OFFERS_JSON = _path("aldi_offers_json", os.path.join(processing, "aldi_offers.json"))
    cfg.LIDL_OFFERS_JSON = _path("lidl_offers_json", os.path.join(processing, "lidl_offers.json"))
    cfg.ALDI_SCRAPING_REPORT_JSON = _path(
        "aldi_scraping_report_json", os.path.join(processing, "aldi_scraping_report.json")
    )
    cfg.LIDL_SCRAPING_REPORT_JSON = _path(
        "lidl_scraping_report_json", os.path.join(processing, "lidl_scraping_report.json")
    )
    cfg.NEW_OFFERS_JSON = _path("new_offers_json", os.path.join(processing, "new_offers.json"))
    cfg.FIRST_SEEN_JSON = _path("first_seen_json", os.path.join(processing, "first_seen.json"))
    cfg.LAST_RUN_STATE_JSON = _path("last_run_state_json", os.path.join(processing, "last_run.json"))
    cfg.PROM_TEXTFILE_DIR = _path("prom_textfile_dir", None)

    cfg.OFFERS_JSON = _path("offers_json", os.path.join(webroot, "offers.json"))
    cfg.META_JSON = _path("meta_json", os.path.join(webroot, "meta.json"))

    cfg.SYNC_DIR = _optional(data, "sync", "dir", os.path.join(processing, "sync"))
    cfg.SYNC_SERVER_HOST = _optional(data, "sync", "host", "127.0.0.1")
    cfg.SYNC_SERVER_PORT = _optional(data, "sync", "port", 8099)
    if not isinstance(cfg.SYNC_SERVER_PORT, int):
        raise ConfigError("config.toml: [sync] port must be an integer")
    cfg.SYNC_ALLOWED_ORIGIN = _require(data, "sync", "allowed_origin")

    cfg.VAPID_PUBLIC_KEY = _require(data, "push", "vapid_public_key")
    cfg.VAPID_CLAIMS_EMAIL = _require(data, "push", "vapid_claims_email")

    cfg.IMAGES_STORE = _optional(data, "scraper", "images_store")
    cfg.IMAGES_EXPIRES = _optional(data, "scraper", "images_expires", 90)
    cfg.DOWNLOAD_DELAY = _optional(data, "scraper", "download_delay", 3)
    cfg.SCRAPING_REPORT_DIR = _optional(data, "scraper", "scraping_report_dir", processing)
    cfg.ALDI_NO_IMAGE_URL = _optional(data, "scraper", "aldi_no_image_url")
    cfg.LIDL_NO_IMAGE_URL = _optional(data, "scraper", "lidl_no_image_url")

    for key in _SECRET_KEYS:
        value = secrets.get(key)
        if not value:
            raise ConfigError(
                f"secret {key} not set: add it to .env (next to config.toml, or "
                "$LIDALDI_ENV_FILE) or export it in the environment"
            )
        setattr(cfg, key, value)
    cfg.VAPID_PRIVATE_KEY_PATH = secrets.get(
        "VAPID_PRIVATE_KEY_PATH", os.path.join(processing, "vapid_private.pem")
    )

    return cfg


def _load_legacy():
    try:
        import config  # noqa: F401  (legacy operator-provided module)
    except ImportError:
        return None
    warnings.warn(
        "no config.toml found; falling back to legacy config.py — migrate to "
        "config.toml + .env (see config.toml.sample / .env.sample)",
        DeprecationWarning,
        stacklevel=3,
    )
    return config


def load(config_path=None, env_path=None):
    """Load configuration, preferring config.toml over legacy config.py."""
    toml_path = _find_config_path(config_path)
    if toml_path:
        return _load_toml(toml_path, env_path)
    legacy = _load_legacy()
    if legacy is not None:
        return legacy
    raise ConfigError(
        "no configuration found: create config.toml (+ .env for secrets) from "
        "config.toml.sample / .env.sample, or set $LIDALDI_CONFIG"
    )


_config = None


def get_config():
    """Return the shared configuration object, loading it on first use."""
    global _config
    if _config is None:
        _config = load()
    return _config
