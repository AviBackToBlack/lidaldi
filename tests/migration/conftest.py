"""Migration rehearsal fixtures (T15).

Builds a faithful *legacy VPS* fixture in a throwaway sandbox — legacy
config.py/settings.py with operator-customized values, a populated
SYNC_DIR (alerts, lastVisit, push subscriptions, tombstones), the live
VAPID PEM, legacy web root (index.html.tpl + rendered index.html + assets)
and fake cron/systemd/nginx artifacts — then rehearses the full cutover
with the real `deploy/update.sh` (dry-run, apply, operator config edit,
re-run) and the real pipeline (process_offers, sync_server,
send_notifications against a local mock push service).

Everything happens under tmp_path; nothing outside is ever touched. The
sandboxing pattern mirrors tests/installer/conftest.py, but with the REAL
requirements.txt (the pyenv virtualenv step pip-installs for real — network needed)
and the REAL built frontend/dist, so the rehearsal exercises the exact
artifacts the operator will deploy. Runs via `make test-migration`
(separate CI job); NOT part of `make test`.
"""

import base64
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYENV_PYTHON_VERSION = "3.12.13"

SYNC_CODE_A = "k7PmQ2xZ"   # alerts + push subscription (mock push endpoint)
SYNC_CODE_B = "Wf4nR9tC"   # alerts, no subscriptions
SYNC_CODE_C = "zH6dT3vM"   # legacy minimal shape (no alertMatches key)

LEGACY_LAST_VISIT = 1750000000
LEGACY_ALERTS = [
    {"id": "a1", "keyword": "drill", "matchType": "anyWord", "createdAt": 1749000000},
]
LEGACY_TOMBSTONES = [{"id": "a0", "deletedAt": 1749500000}]

OPERATOR = {
    # Operator-customized legacy config.py values that MUST survive cutover.
    "allowed_origin": "https://lidaldi.example.ie",
    "vapid_claims_email": "mailto:admin@lidaldi.example.ie",
    "telegram_bot_token": "8123456789:AAlegacy-operator-token",
    "telegram_chat_id": "-1001234567890",
    "download_delay": 5,
}


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run(cmd, env=None, cwd=None, check=True, timeout=600):
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    proc = subprocess.run(
        cmd, capture_output=True, text=True, env=full_env, cwd=cwd,
        timeout=timeout,
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            f"command failed ({proc.returncode}): {cmd}\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def tree_state(root: Path):
    """Map of every file under root -> sha256 (for no-mutation assertions)."""
    state = {}
    if not root.exists():
        return state
    for path in sorted(root.rglob("*")):
        if path.is_file():
            state[str(path.relative_to(root))] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return state


def file_bytes(root: Path):
    """Map of every file under root -> raw bytes (byte-identity checks)."""
    out = {}
    if not root.exists():
        return out
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[str(path.relative_to(root))] = path.read_bytes()
    return out


def create_fake_pyenv(root: Path):
    """Create a minimal pyenv/pyenv-virtualenv shim for migration rehearsal."""
    pyenv_root = root / "pyenv"
    bin_dir = pyenv_root / "bin"
    versions = pyenv_root / "versions"
    base = versions / PYENV_PYTHON_VERSION
    bin_dir.mkdir(parents=True)
    (base / "bin").mkdir(parents=True)
    os.symlink(sys.executable, base / "bin" / "python")
    shim = bin_dir / "pyenv"
    shim.write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        'root="${PYENV_ROOT:?}"\n'
        'cmd="${1:-}"\n'
        "case \"$cmd\" in\n"
        "  root)\n"
        "    printf '%s\\n' \"$root\"\n"
        "    ;;\n"
        "  versions)\n"
        "    find \"$root/versions\" -mindepth 1 -maxdepth 1 -type d -printf '%f\\n' | sort\n"
        "    ;;\n"
        "  virtualenv)\n"
        "    if [ \"${2:-}\" = \"--help\" ]; then echo 'usage: pyenv virtualenv VERSION NAME'; exit 0; fi\n"
        "    base=\"$2\"; name=\"$3\"\n"
        "    \"$root/versions/$base/bin/python\" -m venv \"$root/versions/$name\"\n"
        "    ;;\n"
        "  exec)\n"
        "    shift\n"
        "    exe=\"$1\"; shift\n"
        "    exec \"$root/versions/${PYENV_VERSION:?}/bin/$exe\" \"$@\"\n"
        "    ;;\n"
        "  *) echo \"fake pyenv: unsupported $cmd\" >&2; exit 2 ;;\n"
        "esac\n"
    )
    shim.chmod(0o755)
    return pyenv_root


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def gen_ec_keypair(tmp: Path, name: str):
    """Generate a P-256 keypair with openssl. Returns (pkcs8_pem_path,
    uncompressed_public_point_bytes)."""
    raw = tmp / f"{name}.ec.pem"
    pem = tmp / f"{name}.pem"
    run(["openssl", "ecparam", "-genkey", "-name", "prime256v1", "-noout",
         "-out", str(raw)])
    run(["openssl", "pkcs8", "-topk8", "-nocrypt", "-in", str(raw),
         "-out", str(pem)])
    der = subprocess.run(
        ["openssl", "ec", "-in", str(raw), "-pubout", "-outform", "DER"],
        capture_output=True, check=True,
    ).stdout
    point = der[-65:]
    assert point[0] == 0x04 and len(point) == 65
    return pem, point


def make_offer(store, n, title):
    sku = f"{store.lower()}-{n:04d}"
    if store == "ALDI":
        url = f"https://www.aldi.ie/product/{title.lower().replace(' ', '-')}-{n}"
    else:
        url = f"https://www.lidl.ie/p/{title.lower().replace(' ', '-')}/p{n}"
    return {
        "store": store,
        "id": sku,
        "url": url,
        "category": "DIY",
        "title": title,
        "scraped_at": 1751000000,
        "description": f"{title} — legacy-scraped offer {n}",
        "store_availability": "Unknown",
        "price": "29.99",
        "image_urls": [],
        "images": [],
    }


class MockPushService:
    """Local stand-in for a browser push service: accepts encrypted Web
    Push POSTs, records them, answers 201."""

    def __init__(self):
        self.port = free_port()
        self.requests = []
        service = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                service.requests.append(
                    {"path": self.path,
                     "headers": {k.lower(): v for k, v in self.headers.items()},
                     "body": body}
                )
                self.send_response(201)
                self.end_headers()

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture(scope="session")
def frontend_dist():
    """Real built frontend (the exact artifact update.sh deploys)."""
    dist = REPO_ROOT / "frontend" / "dist"
    if not (dist / "index.html").is_file() or not (dist / "sw.js").is_file():
        run(["npm", "ci"], cwd=REPO_ROOT / "frontend", timeout=900)
        run(["npm", "run", "build"], cwd=REPO_ROOT / "frontend", timeout=900)
    assert (dist / "index.html").is_file()
    return dist


def build_legacy_vps(tmp_path: Path, frontend_dist: Path):
    """Assemble the sandboxed legacy VPS + a repo checkout to deploy from."""
    v = {}
    root = tmp_path / "sys"
    v["root"] = root
    v["APP_ROOT"] = root / "opt" / "lidaldi"
    v["WEB_ROOT"] = root / "var" / "www" / "lidaldi"
    v["DATA_DIR"] = v["APP_ROOT"] / "data" / "processing"
    v["SYNC_DIR"] = v["DATA_DIR"] / "sync"
    v["LOG_DIR"] = root / "var" / "log" / "lidaldi"
    v["BACKUP_DIR"] = root / "var" / "backups" / "lidaldi"
    v["CRON_DIR"] = root / "etc" / "cron.d"
    v["LOGROTATE_DIR"] = root / "etc" / "logrotate.d"
    v["SYSTEMD_DIR"] = root / "etc" / "systemd" / "system"
    v["NGINX_SNIPPET_DIR"] = root / "etc" / "nginx" / "snippets"
    v["sync_port"] = free_port()
    v["PYENV_ROOT"] = create_fake_pyenv(tmp_path)

    # --- Repo checkout the operator deploys from (real code, real
    # requirements.txt, real built frontend/dist). ---
    repo = tmp_path / "checkout"
    v["repo"] = repo
    for d in ("deploy", "cron.d", "logrotate.d", "systemd", "nginx",
              "offers_processing", "scraper"):
        shutil.copytree(REPO_ROOT / d, repo / d,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for f in ("config.toml.sample", ".env.sample", "requirements.txt"):
        shutil.copy2(REPO_ROOT / f, repo / f)
    shutil.copytree(frontend_dist, repo / "frontend" / "dist")

    # --- Legacy application code in APP_ROOT: current-shaped tree with a
    # stale marker so the code sync has real drift to converge. ---
    for d in ("offers_processing", "scraper"):
        shutil.copytree(REPO_ROOT / d, v["APP_ROOT"] / d,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    legacy_common = v["APP_ROOT"] / "offers_processing" / "common.py"
    legacy_common.write_text(
        legacy_common.read_text() + "\n# stale legacy build marker\n"
    )

    # --- VAPID keypair (the real long-lived credential to preserve). ---
    v["DATA_DIR"].mkdir(parents=True)
    keys_tmp = tmp_path / "keys"
    keys_tmp.mkdir()
    vapid_pem, vapid_point = gen_ec_keypair(keys_tmp, "vapid")
    v["vapid_pem"] = v["DATA_DIR"] / "vapid_private.pem"
    shutil.copy2(vapid_pem, v["vapid_pem"])
    os.chmod(v["vapid_pem"], 0o600)
    v["vapid_public_key"] = b64url(vapid_point)

    # --- Legacy operator config.py (customized values) + settings.py. ---
    sample = (REPO_ROOT / "offers_processing" / "config.sample.py").read_text()
    legacy_cfg = (
        sample
        .replace('"/path/to/processing/folder"', f'"{v["DATA_DIR"]}"')
        .replace('"/path/to/website/root/folder"', f'"{v["WEB_ROOT"]}"')
        .replace('"your-telegram-bot-token"', f'"{OPERATOR["telegram_bot_token"]}"')
        .replace('"your-chat-id"', f'"{OPERATOR["telegram_chat_id"]}"')
        .replace("SYNC_SERVER_PORT = 8099", f"SYNC_SERVER_PORT = {v['sync_port']}")
        .replace('"https://your-website-url"', f'"{OPERATOR["allowed_origin"]}"')
        .replace('"your-vapid-public-key-base64url"', f'"{v["vapid_public_key"]}"')
        .replace('"mailto:admin@your-website-url"',
                 f'"{OPERATOR["vapid_claims_email"]}"')
    )
    (v["APP_ROOT"] / "offers_processing" / "config.py").write_text(legacy_cfg)
    settings_sample = (REPO_ROOT / "scraper" / "lidaldi" /
                       "settings.sample.py").read_text()
    (v["APP_ROOT"] / "scraper" / "lidaldi" / "settings.py").write_text(
        settings_sample + f'\nDOWNLOAD_DELAY = {OPERATOR["download_delay"]}\n'
    )

    # --- Scraper feeds with real-shaped data (>= 50 offers, D5 ids). ---
    aldi = [make_offer("ALDI", n, f"Cordless Screwdriver {n}") for n in range(30)]
    lidl = [make_offer("LIDL", n, f"Camping Lantern {n}") for n in range(30)]
    (v["DATA_DIR"] / "aldi_offers.json").write_text(json.dumps(aldi, indent=1))
    (v["DATA_DIR"] / "lidl_offers.json").write_text(json.dumps(lidl, indent=1))
    for r in ("aldi_scraping_report.json", "lidl_scraping_report.json"):
        (v["DATA_DIR"] / r).write_text(json.dumps({"overall_result": "SUCCESS"}))

    # --- SYNC_DIR profiles: alerts, lastVisit, tombstones, push sub. ---
    v["push"] = MockPushService()
    _, sub_point = gen_ec_keypair(keys_tmp, "subscription")
    v["subscription"] = {
        "endpoint": f"http://127.0.0.1:{v['push'].port}/wp/device-1",
        "keys": {"p256dh": b64url(sub_point), "auth": b64url(os.urandom(16))},
    }
    v["SYNC_DIR"].mkdir(parents=True)
    profiles = {
        SYNC_CODE_A: {
            "lastVisit": LEGACY_LAST_VISIT,
            "alerts": LEGACY_ALERTS,
            "tombstones": LEGACY_TOMBSTONES,
            "pushSubscriptions": [v["subscription"]],
            "notified": [],
            "alertMatches": {},
        },
        SYNC_CODE_B: {
            "lastVisit": LEGACY_LAST_VISIT - 86400,
            "alerts": [{"id": "b1", "keyword": "lantern",
                        "matchType": "anyWord", "createdAt": 1749100000}],
            "tombstones": [],
            "pushSubscriptions": [],
            "notified": [],
            "alertMatches": {},
        },
        # Oldest on-disk shape (pre-alertMatches) must survive unchanged.
        SYNC_CODE_C: {"lastVisit": 0, "alerts": [], "tombstones": []},
    }
    for code, data in profiles.items():
        (v["SYNC_DIR"] / f"{code}.json").write_text(json.dumps(data, indent=1))

    # --- Legacy web root: template-rendered static site. ---
    shutil.copytree(REPO_ROOT / "website", v["WEB_ROOT"])
    (v["WEB_ROOT"] / "index.html").write_text(
        "<html><body>legacy rendered index</body></html>\n"
    )

    # --- Fake legacy cron/systemd/nginx/logrotate artifacts (unrendered
    # placeholders = guaranteed drift for update.sh to converge). ---
    for d in ("CRON_DIR", "LOGROTATE_DIR", "SYSTEMD_DIR", "NGINX_SNIPPET_DIR"):
        v[d].mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "cron.d" / "lidaldi", v["CRON_DIR"] / "lidaldi")
    shutil.copy2(REPO_ROOT / "logrotate.d" / "lidaldi",
                 v["LOGROTATE_DIR"] / "lidaldi")
    shutil.copy2(REPO_ROOT / "systemd" / "lidaldi-sync.service",
                 v["SYSTEMD_DIR"] / "lidaldi-sync.service")
    shutil.copy2(REPO_ROOT / "nginx" / "lidaldi-sync-proxy.conf",
                 v["NGINX_SNIPPET_DIR"] / "lidaldi-sync-proxy.conf")
    for d, name in (("CRON_DIR", "lidaldi"), ("LOGROTATE_DIR", "lidaldi"),
                    ("SYSTEMD_DIR", "lidaldi-sync.service"),
                    ("NGINX_SNIPPET_DIR", "lidaldi-sync-proxy.conf")):
        p = v[d] / name
        p.write_text(p.read_text() + "\n# stale legacy artifact\n")

    v["LOG_DIR"].mkdir(parents=True)

    conf = tmp_path / "install.local.conf"
    lines = [
        f'APP_ROOT="{v["APP_ROOT"]}"',
        f'WEB_ROOT="{v["WEB_ROOT"]}"',
        f'SYNC_DIR="{v["SYNC_DIR"]}"',
        f'LOG_DIR="{v["LOG_DIR"]}"',
        f'BACKUP_DIR="{v["BACKUP_DIR"]}"',
        f'CRON_DIR="{v["CRON_DIR"]}"',
        f'LOGROTATE_DIR="{v["LOGROTATE_DIR"]}"',
        f'SYSTEMD_DIR="{v["SYSTEMD_DIR"]}"',
        f'NGINX_SNIPPET_DIR="{v["NGINX_SNIPPET_DIR"]}"',
        f'SERVICE_USER="{os.environ.get("USER", "root")}"',
        "MANAGE_USER=0",
        f'REPO_DIR="{v["repo"]}"',
        f'VAPID_PRIVATE_KEY_PATH="{v["vapid_pem"]}"',
        f'PYENV_ROOT="{v["PYENV_ROOT"]}"',
        f'PYENV_PYTHON_VERSION="{PYENV_PYTHON_VERSION}"',
    ]
    conf.write_text("\n".join(lines) + "\n")
    v["conf"] = conf
    return v


def run_update(v, *args, check=True):
    return run(
        ["bash", str(v["repo"] / "deploy" / "update.sh"),
         "--config", str(v["conf"]), "--no-restart", *args],
        env={"PYENV_VERSION": "ignored-by-update-sh",
             "PYENV_VIRTUALENV": "also-ignored"},
        check=check,
    )


def operator_edit_configs(v):
    """The runbook's mandatory 'edit real values' step: carry the legacy
    config.py values into the freshly created config.toml/.env."""
    toml_path = v["APP_ROOT"] / "config.toml"
    text = toml_path.read_text()
    text = (
        text
        .replace('offers_processing_dir = "/path/to/processing/folder"',
                 f'offers_processing_dir = "{v["DATA_DIR"]}"')
        .replace('website_root_dir = "/path/to/website/root/folder"',
                 f'website_root_dir = "{v["WEB_ROOT"]}"')
        .replace("port = 8099", f"port = {v['sync_port']}")
        .replace('allowed_origin = "https://your-website-url"',
                 f'allowed_origin = "{OPERATOR["allowed_origin"]}"')
        .replace('vapid_public_key = "your-vapid-public-key-base64url"',
                 f'vapid_public_key = "{v["vapid_public_key"]}"')
        .replace('vapid_claims_email = "mailto:admin@your-website-url"',
                 f'vapid_claims_email = "{OPERATOR["vapid_claims_email"]}"')
        .replace('images_store = "/path/to/images/folder"',
                 f'images_store = "{v["DATA_DIR"] / "images"}"')
    )
    toml_path.write_text(text)

    env_path = v["APP_ROOT"] / ".env"
    text = env_path.read_text()
    text = (
        text
        .replace("TELEGRAM_BOT_TOKEN=your-telegram-bot-token",
                 f"TELEGRAM_BOT_TOKEN={OPERATOR['telegram_bot_token']}")
        .replace("TELEGRAM_CHAT_ID=your-chat-id",
                 f"TELEGRAM_CHAT_ID={OPERATOR['telegram_chat_id']}")
    )
    text += f"VAPID_PRIVATE_KEY_PATH={v['vapid_pem']}\n"
    env_path.write_text(text)


def pipeline_env(v):
    return {
        "LIDALDI_CONFIG": str(v["APP_ROOT"] / "config.toml"),
        "LIDALDI_ENV_FILE": str(v["APP_ROOT"] / ".env"),
    }


def venv_python(v):
    return str(v["PYENV_ROOT"] / "versions" / "lidaldi" / "bin" / "python")


def run_pipeline(v, script, check=True):
    return run(
        [venv_python(v), str(v["APP_ROOT"] / "offers_processing" / script)],
        env=pipeline_env(v), check=check,
    )


def sync_get(v, code, probe_ip):
    req = urllib.request.Request(
        f"http://127.0.0.1:{v['sync_port']}/api/sync/{code}",
        # Distinct trusted-from-loopback client IPs so rehearsal probes
        # can never trip the 30 req/min per-IP rate limit.
        headers={"X-Forwarded-For": probe_ip},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read())


@pytest.fixture(scope="module")
def cutover(tmp_path_factory, frontend_dist):
    """Run the entire rehearsal once; tests assert on the recorded steps."""
    tmp_path = tmp_path_factory.mktemp("rehearsal")
    v = build_legacy_vps(tmp_path, frontend_dist)
    R = {"vps": v}

    # Phase 0: preflight — the operator has installed pinned pyenv Python 3.12.x (D3).
    assert sys.version_info >= (3, 12), "rehearsal must run under >=3.12"
    R["pre_state"] = tree_state(v["root"])
    R["pre_sync"] = file_bytes(v["SYNC_DIR"])
    R["pre_vapid"] = v["vapid_pem"].read_bytes()
    R["pre_config_py"] = (v["APP_ROOT"] / "offers_processing" /
                          "config.py").read_bytes()
    R["pre_settings_py"] = (v["APP_ROOT"] / "scraper" / "lidaldi" /
                            "settings.py").read_bytes()

    # Phase 1: dry-run + review.
    R["dry_run"] = run_update(v, "--dry-run")
    R["post_dry_state"] = tree_state(v["root"])

    # Phase 2: apply.
    R["apply"] = run_update(v)
    R["post_apply_sync"] = file_bytes(v["SYNC_DIR"])
    R["post_apply_webroot"] = file_bytes(v["WEB_ROOT"])
    backups = sorted(v["BACKUP_DIR"].glob("lidaldi-backup-*"))
    R["backup"] = backups[-1] if backups else None

    # Phase 3: operator edits the freshly created config.toml/.env with the
    # legacy values (see finding F1 in the PR: this step is manual).
    operator_edit_configs(v)

    # Phase 4: idempotency — a second run after the config edit is a no-op.
    R["second_run"] = run_update(v)
    R["post_second_state"] = tree_state(v["root"])

    # Phase 5: first data run on the migrated box (seeds first_seen).
    R["process_1"] = run_pipeline(v, "process_offers.py", check=False)
    R["new_offers_1"] = json.loads(
        (v["DATA_DIR"] / "new_offers.json").read_text()
    )
    R["first_seen_1"] = json.loads(
        (v["DATA_DIR"] / "first_seen.json").read_text()
    )
    R["post_process_webroot_index"] = (v["WEB_ROOT"] / "index.html").read_bytes()

    # Phase 6: second data run with one genuinely new offer.
    aldi_path = v["DATA_DIR"] / "aldi_offers.json"
    aldi = json.loads(aldi_path.read_text())
    aldi.append(make_offer("ALDI", 999, "Cordless Drill Deluxe"))
    aldi_path.write_text(json.dumps(aldi, indent=1))
    R["process_2"] = run_pipeline(v, "process_offers.py", check=False)
    R["new_offers_2"] = json.loads(
        (v["DATA_DIR"] / "new_offers.json").read_text()
    )

    # Phase 7: boot the new sync_server against the migrated SYNC_DIR.
    server = subprocess.Popen(
        [venv_python(v),
         str(v["APP_ROOT"] / "offers_processing" / "sync_server.py")],
        env={**os.environ, **pipeline_env(v)},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        status = None
        for i in range(1, 51):
            if server.poll() is not None:
                break
            try:
                status, _ = sync_get(v, "READY001", f"10.255.255.{i}")
                break
            except OSError:
                time.sleep(0.2)
        assert status == 200, "sync_server failed to start"
        R["profile_a"] = sync_get(v, SYNC_CODE_A, "10.255.254.1")
        R["profile_c"] = sync_get(v, SYNC_CODE_C, "10.255.254.2")
    finally:
        server.terminate()
        server.wait(timeout=10)

    # Phase 8: push send path against the migrated profile (mock service).
    R["notify"] = run_pipeline(v, "send_notifications.py", check=False)
    R["push_requests"] = list(v["push"].requests)
    R["post_notify_profile_a"] = json.loads(
        (v["SYNC_DIR"] / f"{SYNC_CODE_A}.json").read_text()
    )
    R["post_vapid"] = v["vapid_pem"].read_bytes()

    yield R
    v["push"].stop()
