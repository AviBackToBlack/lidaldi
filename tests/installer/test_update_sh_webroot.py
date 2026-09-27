"""update.sh web root: permissions policy, IMAGES_DIR, frontend auto-build.

Permission tests check real access as the real accounts (runuser), since
that is what broke production: www-data (nginx) must read everything, the
cron user must write exactly its data paths, and nothing else. They need
root plus the base image's `daemon` user and `www-data` group.
"""

import grp
import os
import pwd
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from conftest import run_update

CRON_USER = "daemon"
WEB_GROUP = "www-data"


def _have_accounts():
    try:
        pwd.getpwnam(CRON_USER)
        grp.getgrnam(WEB_GROUP)
        pwd.getpwnam(WEB_GROUP)
    except KeyError:
        return False
    return os.geteuid() == 0 and shutil.which("runuser") is not None


# Skippable on a dev box, never in CI: there they must run (CI's container
# is root with the base image's accounts), so a missing prerequisite fails
# loudly instead of silently dropping the real-access coverage.
needs_root = pytest.mark.skipif(
    not _have_accounts() and not os.environ.get("CI"),
    reason="needs root, runuser, a 'daemon' user and a 'www-data' user/group",
)


def append_conf(sandbox, **values):
    with open(sandbox["conf"], "a") as f:
        for key, value in values.items():
            f.write(f'{key}="{value}"\n')


def owner(path: Path):
    st = path.lstat()
    return (pwd.getpwuid(st.st_uid).pw_name, grp.getgrgid(st.st_gid).gr_name,
            stat.S_IMODE(st.st_mode))


def as_user(user, *cmd, member_of_web_group=True):
    # The cron user runs with WEB_GROUP as a supplementary group, as
    # lidaldi does in production (update.sh adds it when MANAGE_USER=1);
    # runuser -G simulates that without touching /etc/group.
    extra = ["-G", WEB_GROUP] if user == CRON_USER and member_of_web_group else []
    return subprocess.run(["runuser", "-u", user, *extra, "--", *map(str, cmd)],
                          capture_output=True).returncode == 0


def sh_as(user, script, **kw):
    return as_user(user, "sh", "-c", script, **kw)


@pytest.fixture()
def perms_sandbox(sandbox, tmp_path):
    append_conf(sandbox, SERVICE_USER=CRON_USER, WEB_GROUP=WEB_GROUP)
    # pytest's temp dirs are 0700; let the other accounts reach the sandbox.
    for p in [tmp_path, *tmp_path.parents]:
        if str(p) in ("/", "/tmp"):
            break
        p.chmod(p.stat().st_mode | 0o755)
    sandbox["IMAGES_DIR"] = sandbox["WEB_ROOT"] / "img" / "full"
    return sandbox


# --- Permissions ---------------------------------------------------------

@needs_root
def test_webroot_permissions_policy(perms_sandbox):
    run_update(perms_sandbox)
    web, img = perms_sandbox["WEB_ROOT"], perms_sandbox["IMAGES_DIR"]

    assert owner(web) == (CRON_USER, WEB_GROUP, 0o750)
    assert owner(web / "index.html") == ("root", WEB_GROUP, 0o640)
    assert owner(web / "app.js") == ("root", WEB_GROUP, 0o640)
    assert owner(web / "img") == ("root", WEB_GROUP, 0o750)
    assert owner(img) == (CRON_USER, WEB_GROUP, 0o750)

    # nginx reads, never writes; the cron user can't touch the app.
    assert as_user(WEB_GROUP, "test", "-r", web / "index.html")
    assert as_user(WEB_GROUP, "ls", img)
    assert not as_user(WEB_GROUP, "touch", web / "x")
    assert not sh_as(CRON_USER, f"echo x >> {web}/index.html")


@needs_root
def test_cron_job_output_is_writable_then_normalised(perms_sandbox):
    run_update(perms_sandbox)
    web, img = perms_sandbox["WEB_ROOT"], perms_sandbox["IMAGES_DIR"]

    # What the daily job does, with the production umask: process_offers'
    # write_atomic (.tmp + rename) and the scraper's new full/v2 images.
    assert sh_as(CRON_USER, f"umask 0002; echo '[]' > {web}/offers.json.tmp"
                            f" && mv {web}/offers.json.tmp {web}/offers.json")
    assert sh_as(CRON_USER, f"umask 0002; mkdir -p {img}/v2 && echo a > {img}/v2/a.jpg")

    proc = run_update(perms_sandbox)
    assert "set web root permissions to fix" in proc.stdout
    assert owner(web / "offers.json") == (CRON_USER, WEB_GROUP, 0o640)
    assert owner(img / "v2") == (CRON_USER, WEB_GROUP, 0o750)
    assert owner(img / "v2" / "a.jpg") == (CRON_USER, WEB_GROUP, 0o640)
    assert as_user(WEB_GROUP, "test", "-r", web / "offers.json")
    assert as_user(WEB_GROUP, "test", "-r", img / "v2" / "a.jpg")
    # ...and the next day's job still works: overwrite an expired image,
    # replace offers.json again.
    assert sh_as(CRON_USER, f"echo b > {img}/v2/a.jpg")
    assert sh_as(CRON_USER, f"echo '[1]' > {web}/offers.json.tmp"
                            f" && mv {web}/offers.json.tmp {web}/offers.json")

    run_update(perms_sandbox)  # normalise the replaced offers.json
    assert "NOOP" in run_update(perms_sandbox).stdout


@needs_root
def test_root_owned_images_are_handed_back_to_the_cron_user(perms_sandbox):
    # The old fix_perms script left images root-owned, so the scraper could
    # not overwrite them once they expired.
    run_update(perms_sandbox)
    old = perms_sandbox["IMAGES_DIR"] / "old.jpg"
    old.write_text("img")
    os.chown(old, 0, grp.getgrnam(WEB_GROUP).gr_gid)
    old.chmod(0o640)

    run_update(perms_sandbox)
    assert owner(old) == (CRON_USER, WEB_GROUP, 0o640)
    assert sh_as(CRON_USER, f"echo new > {old}")


@needs_root
def test_symlinks_in_writable_dirs_are_never_followed(perms_sandbox, tmp_path):
    run_update(perms_sandbox)
    web, img = perms_sandbox["WEB_ROOT"], perms_sandbox["IMAGES_DIR"]
    secret = tmp_path / "secret"
    secret.write_text("root only")
    secret.chmod(0o600)
    before = secret.stat()
    # The cron user owns these dirs, so it could plant links there.
    assert as_user(CRON_USER, "ln", "-s", secret, img / "evil.jpg")
    assert as_user(CRON_USER, "ln", "-s", secret, web / "offers.json")
    assert as_user(CRON_USER, "ln", "-s", "/etc", img / "evil-dir")

    run_update(perms_sandbox)
    after = secret.stat()
    assert (after.st_uid, after.st_gid, after.st_mode) == \
        (before.st_uid, before.st_gid, before.st_mode)
    assert (web / "offers.json").is_symlink()
    assert "NOOP" in run_update(perms_sandbox).stdout


@needs_root
def test_dry_run_reports_permission_drift_without_fixing_it(perms_sandbox):
    run_update(perms_sandbox)
    index = perms_sandbox["WEB_ROOT"] / "index.html"
    index.chmod(0o644)

    proc = run_update(perms_sandbox, "--dry-run")
    assert "web root permissions: 1 path(s) differ" in proc.stdout
    assert "root:www-data 644  index.html" in proc.stdout
    assert stat.S_IMODE(index.stat().st_mode) == 0o644


@needs_root
def test_cron_user_outside_web_group_is_flagged(perms_sandbox):
    # Without the group the cron user cannot even reach IMAGES_DIR: its
    # parent is root:www-data 0750.
    proc = run_update(perms_sandbox)
    assert f"WARN  user {CRON_USER} is not in group {WEB_GROUP}" in proc.stdout
    assert f"usermod -aG {WEB_GROUP} {CRON_USER}" in proc.stdout
    img = perms_sandbox["IMAGES_DIR"]
    assert not sh_as(CRON_USER, f"echo a > {img}/a.jpg", member_of_web_group=False)
    assert sh_as(CRON_USER, f"echo a > {img}/a.jpg")


@needs_root
def test_group_membership_is_planned_when_managing_users(perms_sandbox):
    append_conf(perms_sandbox, MANAGE_USER=1)
    proc = run_update(perms_sandbox, "--dry-run")
    assert f"PLAN  add user {CRON_USER} to group {WEB_GROUP}" in proc.stdout
    assert not perms_sandbox["root"].exists()


@needs_root
def test_unknown_web_group_is_rejected(sandbox):
    append_conf(sandbox, WEB_GROUP="no-such-group-xyz")
    proc = run_update(sandbox, check=False)
    assert proc.returncode != 0
    assert "WEB_GROUP 'no-such-group-xyz' does not exist" in proc.stderr
    assert not sandbox["root"].exists()


# --- IMAGES_DIR ------------------------------------------------------------

def test_image_cleanup_targets_the_images_dir(sandbox):
    # Regression: the 90-day cleanup was rendered to APP_ROOT/data/images,
    # a directory that never existed, so old images were never deleted.
    run_update(sandbox)
    text = (sandbox["APP_ROOT"] / "scraper" / "run_scrapers.sh").read_text()
    assert f'IMAGES_DIR="{sandbox["WEB_ROOT"]}/img/full"' in text
    assert "data/images" not in text


def test_images_dir_outside_web_root_is_rejected(sandbox, tmp_path):
    append_conf(sandbox, IMAGES_DIR=tmp_path / "elsewhere")
    proc = run_update(sandbox, check=False)
    assert proc.returncode != 0
    assert "must be inside WEB_ROOT" in proc.stderr


# --- Frontend auto-build ---------------------------------------------------

FAKE_NPM = """#!/bin/bash
set -eu
echo "$*" >> "$(dirname "$0")/npm.log"
case "$1" in
  ci) ;;
  run)
    [ "${FAKE_NPM_FAIL:-}" = "1" ] && { echo "boom: build exploded" >&2; exit 1; }
    rm -rf dist && mkdir -p dist/assets
    printf '<html>%s</html>\\n' "$(cat src/version.txt)" > dist/index.html
    echo app > dist/assets/app.js
    echo '{"fixture": true}' > dist/offers.json   # vite copies public/
    ;;
  *) exit 2 ;;
esac
"""


@pytest.fixture()
def build_sandbox(sandbox, tmp_path):
    frontend = sandbox["repo"] / "frontend"
    shutil.rmtree(frontend / "dist")
    (frontend / "src").mkdir()
    (frontend / "package.json").write_text('{"name": "fake"}\n')
    (frontend / "src" / "version.txt").write_text("v1")
    npm = tmp_path / "bin" / "npm"
    npm.parent.mkdir()
    npm.write_text(FAKE_NPM)
    npm.chmod(0o755)
    append_conf(sandbox, NPM_BIN=npm)
    sandbox["frontend"] = frontend
    sandbox["npm_log"] = npm.parent / "npm.log"
    return sandbox


def builds(sandbox):
    log = sandbox["npm_log"]
    return log.read_text().count("run build") if log.exists() else 0


def test_stale_frontend_is_built_then_deployed(build_sandbox):
    proc = run_update(build_sandbox)
    web = build_sandbox["WEB_ROOT"]
    assert "PLAN  build frontend" in proc.stdout
    assert (web / "index.html").read_text() == "<html>v1</html>\n"
    assert (web / "assets" / "app.js").is_file()
    assert (build_sandbox["frontend"] / "dist" / ".build-fingerprint").is_file()
    assert not (web / ".build-fingerprint").exists()
    assert not (web / "offers.json").exists()  # public/ fixture never deployed
    assert "ci --no-audit --no-fund" in build_sandbox["npm_log"].read_text()

    proc = run_update(build_sandbox)
    assert "NOOP" in proc.stdout
    assert builds(build_sandbox) == 1


def test_source_change_triggers_rebuild(build_sandbox):
    run_update(build_sandbox)
    (build_sandbox["frontend"] / "src" / "version.txt").write_text("v2")
    proc = run_update(build_sandbox)
    assert "sources changed since the last build" in proc.stdout
    assert (build_sandbox["WEB_ROOT"] / "index.html").read_text() == "<html>v2</html>\n"
    assert builds(build_sandbox) == 2


def test_hand_built_dist_is_rebuilt_once(build_sandbox):
    dist = build_sandbox["frontend"] / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>stale hand build</html>\n")
    proc = run_update(build_sandbox)
    assert "no build fingerprint" in proc.stdout
    assert (build_sandbox["WEB_ROOT"] / "index.html").read_text() == "<html>v1</html>\n"
    assert "NOOP" in run_update(build_sandbox).stdout


def test_stale_frontend_without_npm_aborts_before_any_change(build_sandbox):
    append_conf(build_sandbox, NPM_BIN="/nonexistent/npm")
    proc = run_update(build_sandbox, check=False)
    assert proc.returncode != 0
    assert "refusing to deploy a stale frontend" in proc.stderr
    assert not build_sandbox["root"].exists()


def test_fancy_build_failure_shows_the_build_output(build_sandbox):
    # Fancy mode hides build output behind a spinner; on failure the tail
    # of it must still reach the operator.
    proc = run_update(build_sandbox, env={"LIDALDI_FANCY": "1", "FAKE_NPM_FAIL": "1"},
                      check=False)
    assert proc.returncode != 0
    assert "failed (exit 1)" in proc.stdout
    assert "boom: build exploded" in proc.stdout


def test_failed_build_keeps_the_live_site_and_retries(build_sandbox):
    run_update(build_sandbox)
    (build_sandbox["frontend"] / "src" / "version.txt").write_text("v2")
    proc = run_update(build_sandbox, env={"FAKE_NPM_FAIL": "1"}, check=False)
    assert proc.returncode != 0
    assert (build_sandbox["WEB_ROOT"] / "index.html").read_text() == "<html>v1</html>\n"

    proc = run_update(build_sandbox)
    assert "sources changed since the last build" in proc.stdout
    assert (build_sandbox["WEB_ROOT"] / "index.html").read_text() == "<html>v2</html>\n"
