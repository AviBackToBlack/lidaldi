"""Sandboxed fixtures for the installer tests (T10).

Every test runs deploy/update.sh against a throwaway sandbox: all system
directories (cron.d, logrotate.d, systemd, nginx snippets) are redirected
into a tmp tree via install.local.conf overrides, SERVICE_USER is the
current user with MANAGE_USER=0, and REPO_DIR points at a pruned copy of
the real checkout with a fake frontend/dist. Nothing outside tmp_path is
ever touched, so the suite is safe in any Ubuntu container.
"""

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
UPDATE_SH = REPO_ROOT / "deploy" / "update.sh"
MERGE_PY = REPO_ROOT / "deploy" / "merge_config.py"


@pytest.fixture()
def sandbox(tmp_path):
    repo = tmp_path / "checkout"
    for d in ("deploy", "cron.d", "logrotate.d", "systemd", "nginx",
              "offers_processing", "scraper"):
        shutil.copytree(REPO_ROOT / d, repo / d,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for f in ("config.toml.sample", ".env.sample", "requirements.txt"):
        shutil.copy2(REPO_ROOT / f, repo / f)
    # Minimal fake requirements so the venv step doesn't hit the network.
    (repo / "requirements.txt").write_text("")
    dist = repo / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html>fake build</html>\n")
    (dist / "app.js").write_text("console.log('fake');\n")

    root = tmp_path / "sys"
    paths = {
        "APP_ROOT": root / "opt" / "lidaldi",
        "WEB_ROOT": root / "var" / "www" / "lidaldi",
        "SYNC_DIR": root / "opt" / "lidaldi" / "data" / "sync",
        "LOG_DIR": root / "var" / "log" / "lidaldi",
        "BACKUP_DIR": root / "var" / "backups" / "lidaldi",
        "CRON_DIR": root / "etc" / "cron.d",
        "LOGROTATE_DIR": root / "etc" / "logrotate.d",
        "SYSTEMD_DIR": root / "etc" / "systemd" / "system",
        "NGINX_SNIPPET_DIR": root / "etc" / "nginx" / "snippets",
    }
    conf = tmp_path / "install.local.conf"
    lines = [f'{k}="{v}"' for k, v in paths.items()]
    lines += [f'SERVICE_USER="{os.environ.get("USER", "root")}"',
              "MANAGE_USER=0",
              f'REPO_DIR="{repo}"']
    conf.write_text("\n".join(lines) + "\n")
    return {"repo": repo, "conf": conf, "root": root, **paths}


def run_update(sandbox, *args, env=None, check=True):
    cmd = ["bash", str(sandbox["repo"] / "deploy" / "update.sh"),
           "--config", str(sandbox["conf"]), *args]
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    proc = subprocess.run(cmd, capture_output=True, text=True, env=full_env)
    if check and proc.returncode != 0:
        raise AssertionError(
            f"update.sh failed ({proc.returncode}):\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def tree_state(root: Path):
    """Map of every file under root -> (mtime_ns, sha256)."""
    state = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            state[str(path.relative_to(root))] = (path.stat().st_mtime_ns,
                                                  digest)
    return state
