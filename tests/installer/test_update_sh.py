"""Installer/updater acceptance tests (T10).

Covers the T10 success criteria: idempotency (second run = no-op), sample->
real merge adds-never-clobbers, dry-run makes zero changes, Python < 3.11
abort, and backups before any mutation.
"""

import os
import stat

from conftest import run_update, tree_state


def test_first_run_installs_everything(sandbox):
    proc = run_update(sandbox)
    assert "APPLY" in proc.stdout
    assert (sandbox["CRON_DIR"] / "lidaldi").is_file()
    assert (sandbox["LOGROTATE_DIR"] / "lidaldi").is_file()
    assert (sandbox["SYSTEMD_DIR"] / "lidaldi-sync.service").is_file()
    assert (sandbox["NGINX_SNIPPET_DIR"] / "lidaldi-sync-proxy.conf").is_file()
    assert (sandbox["WEB_ROOT"] / "index.html").is_file()
    assert (sandbox["APP_ROOT"] / "offers_processing" / "process_offers.py").is_file()
    assert (sandbox["APP_ROOT"] / ".venv" / "bin" / "python").exists()
    assert (sandbox["APP_ROOT"] / "config.toml").is_file()
    env_file = sandbox["APP_ROOT"] / ".env"
    assert env_file.is_file()
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600
    # Rendered templates carry sandbox paths, not repo placeholders.
    cron = (sandbox["CRON_DIR"] / "lidaldi").read_text()
    assert "/path/to/" not in cron
    assert str(sandbox["APP_ROOT"] / "scraper" / "run_scrapers.sh") in cron
    unit = (sandbox["SYSTEMD_DIR"] / "lidaldi-sync.service").read_text()
    assert str(sandbox["SYNC_DIR"]) in unit
    assert "your-website-url" not in unit


def test_second_run_is_noop(sandbox):
    run_update(sandbox)
    before = tree_state(sandbox["root"])
    proc = run_update(sandbox)
    assert "NOOP" in proc.stdout
    assert "APPLY" not in proc.stdout
    assert "BACKUP" not in proc.stdout
    assert tree_state(sandbox["root"]) == before


def test_dry_run_makes_zero_changes(sandbox):
    proc = run_update(sandbox, "--dry-run")
    assert "DRY-RUN" in proc.stdout
    assert "PLAN" in proc.stdout
    # Nothing was created: the sandbox system root does not even exist yet.
    assert not sandbox["root"].exists()
    # And a dry run after install reports no-op.
    run_update(sandbox)
    before = tree_state(sandbox["root"])
    proc = run_update(sandbox, "--dry-run")
    assert "NOOP" in proc.stdout
    assert tree_state(sandbox["root"]) == before


def test_dry_run_reports_config_diff(sandbox):
    run_update(sandbox)
    sample = sandbox["repo"] / "config.toml.sample"
    sample.write_text(sample.read_text() + '\n[newsection]\nnew_key = "x"\n')
    proc = run_update(sandbox, "--dry-run")
    assert "ADD [newsection] new_key" in proc.stdout
    assert "DRY-RUN" in proc.stdout
    live = (sandbox["APP_ROOT"] / "config.toml").read_text()
    assert "new_key" not in live


def test_merge_adds_never_clobbers(sandbox):
    run_update(sandbox)
    live_toml = sandbox["APP_ROOT"] / "config.toml"
    text = live_toml.read_text().replace(
        'host = "127.0.0.1"', 'host = "10.0.0.7"'
    )
    live_toml.write_text(text)
    live_env = sandbox["APP_ROOT"] / ".env"
    live_env.write_text(
        live_env.read_text().replace(
            "TELEGRAM_CHAT_ID=your-chat-id", "TELEGRAM_CHAT_ID=LIVE-VALUE"
        )
    )
    # New keys appear in the samples.
    sample = sandbox["repo"] / "config.toml.sample"
    sample.write_text(sample.read_text() + '\n[newsection]\nnew_key = "default"\n')
    env_sample = sandbox["repo"] / ".env.sample"
    env_sample.write_text(env_sample.read_text() + "NEW_SECRET=changeme\n")

    proc = run_update(sandbox)
    assert "APPLY merge new sample keys" in proc.stdout
    toml_text = live_toml.read_text()
    assert 'host = "10.0.0.7"' in toml_text        # live value kept
    assert 'new_key = "default"' in toml_text      # sample key added
    env_text = live_env.read_text()
    assert "TELEGRAM_CHAT_ID=LIVE-VALUE" in env_text
    assert "NEW_SECRET=changeme" in env_text
    # And the merge converges: next run is a no-op.
    proc = run_update(sandbox)
    assert "NOOP" in proc.stdout


def test_python_below_311_aborts(sandbox, tmp_path):
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    shim = shim_dir / "fakepython"
    shim.write_text(
        "#!/bin/bash\n"
        'if [ "$1" = "--version" ]; then echo "Python 3.8.10"; exit 0; fi\n'
        "exit 1\n"
    )
    shim.chmod(0o755)
    proc = run_update(sandbox, env={"PYTHON": str(shim)}, check=False)
    assert proc.returncode != 0
    assert "Python >= 3.11 required" in proc.stderr
    assert "deadsnakes" in proc.stderr
    assert not sandbox["root"].exists()


def test_backup_before_mutation(sandbox):
    run_update(sandbox)
    # Simulate live state: edited config + a sync profile.
    live_toml = sandbox["APP_ROOT"] / "config.toml"
    live_toml.write_text(live_toml.read_text() + "\n# operator edit\n")
    sandbox["SYNC_DIR"].mkdir(parents=True, exist_ok=True)
    (sandbox["SYNC_DIR"] / "ABC123.json").write_text('{"alerts": []}')
    # Trigger drift so the run mutates (and therefore backs up).
    sample = sandbox["repo"] / ".env.sample"
    sample.write_text(sample.read_text() + "ANOTHER_KEY=x\n")

    proc = run_update(sandbox)
    assert "BACKUP" in proc.stdout
    backups = sorted(sandbox["BACKUP_DIR"].glob("lidaldi-backup-*"))
    assert backups, "no timestamped backup created"
    backup = backups[-1]
    saved_toml = backup / "configs" / "config.toml"
    assert saved_toml.is_file()
    assert "# operator edit" in saved_toml.read_text()
    assert (backup / "configs" / ".env").is_file()
    assert (backup / "sync" / "ABC123.json").read_text() == '{"alerts": []}'


def test_webroot_preserves_data_files(sandbox):
    run_update(sandbox)
    offers = sandbox["WEB_ROOT"] / "offers.json"
    offers.write_text('{"offers": ["live-data"]}')
    (sandbox["repo"] / "frontend" / "dist" / "app.js").write_text("new build\n")
    run_update(sandbox)
    assert offers.read_text() == '{"offers": ["live-data"]}'
    assert (sandbox["WEB_ROOT"] / "app.js").read_text() == "new build\n"


def test_vapid_key_never_touched(sandbox):
    run_update(sandbox)
    pem = sandbox["APP_ROOT"] / "offers_processing" / "vapid_private.pem"
    pem.write_text("FAKE PEM CONTENT\n")
    mtime = pem.stat().st_mtime_ns
    # Force drift elsewhere.
    (sandbox["repo"] / "frontend" / "dist" / "app.js").write_text("v2\n")
    proc = run_update(sandbox)
    assert "reused verbatim" in proc.stdout
    assert pem.read_text() == "FAKE PEM CONTENT\n"
    assert pem.stat().st_mtime_ns == mtime


def test_missing_local_conf_aborts(sandbox):
    conf = sandbox["conf"]
    missing = conf.parent / "nope.conf"
    proc = run_update({**sandbox, "conf": missing}, check=False)
    assert proc.returncode != 0
    assert "install.local.conf" in proc.stderr


def test_removed_key_reported_for_review(sandbox):
    run_update(sandbox)
    live_toml = sandbox["APP_ROOT"] / "config.toml"
    live_toml.write_text(live_toml.read_text() + '\n[legacy]\nold_key = "v"\n')
    proc = run_update(sandbox, "--dry-run")
    assert "REVIEW live key absent from sample" in proc.stdout
    assert "legacy.old_key" in proc.stdout
    # Live-only keys are reported, never deleted.
    assert 'old_key = "v"' in live_toml.read_text()


def test_synctree_never_overwrites_live_config_or_keys(sandbox):
    run_update(sandbox)
    app_op = sandbox["APP_ROOT"] / "offers_processing"
    (app_op / "config.py").write_text("LIVE VALUES\n")
    (app_op / "vapid_private.pem").write_text("LIVE PEM\n")
    (app_op / "first_seen.json").write_text('{"live": true}')
    repo_op = sandbox["repo"] / "offers_processing"
    (repo_op / "config.py").write_text("REPO VERSION\n")
    (repo_op / "vapid_private.pem").write_text("REPO PEM\n")
    (repo_op / "first_seen.json").write_text('{"repo": true}')
    # Force drift in the tree so synctree actually runs.
    (repo_op / "common.py").write_text(
        (repo_op / "common.py").read_text() + "\n# drift\n"
    )
    proc = run_update(sandbox)
    assert "APPLY sync offers_processing" in proc.stdout
    assert (app_op / "config.py").read_text() == "LIVE VALUES\n"
    assert (app_op / "vapid_private.pem").read_text() == "LIVE PEM\n"
    assert (app_op / "first_seen.json").read_text() == '{"live": true}'
    assert "# drift" in (app_op / "common.py").read_text()


def test_synctree_prunes_stale_files_and_converges(sandbox):
    run_update(sandbox)
    repo_op = sandbox["repo"] / "offers_processing"
    app_op = sandbox["APP_ROOT"] / "offers_processing"
    # Live-only protected files must survive the prune.
    (app_op / "vapid_private.pem").write_text("LIVE PEM\n")
    (app_op / "first_seen.json").write_text('{"live": true}')
    # A file removed from the repo must be pruned from APP_ROOT.
    (repo_op / "common.py").unlink()
    proc = run_update(sandbox)
    assert "APPLY sync offers_processing" in proc.stdout
    assert not (app_op / "common.py").exists()
    assert (app_op / "vapid_private.pem").read_text() == "LIVE PEM\n"
    assert (app_op / "first_seen.json").read_text() == '{"live": true}'
    # The sync converges: next run is a no-op, not a perpetual re-sync.
    proc = run_update(sandbox)
    assert "NOOP" in proc.stdout


def test_synctree_preserves_executable_bits(sandbox):
    run_update(sandbox)
    script = sandbox["APP_ROOT"] / "scraper" / "run_scrapers.sh"
    assert script.is_file()
    assert os.access(script, os.X_OK)


def test_second_run_noop_survives_operator_edits(sandbox):
    """Operator-edited live values alone must not cause churn."""
    run_update(sandbox)
    live_toml = sandbox["APP_ROOT"] / "config.toml"
    live_toml.write_text(
        live_toml.read_text().replace('port = 8099', 'port = 9000')
    )
    proc = run_update(sandbox)
    assert "NOOP" in proc.stdout
    assert 'port = 9000' in live_toml.read_text()
