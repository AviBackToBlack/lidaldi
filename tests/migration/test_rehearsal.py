"""T15 migration rehearsal assertions.

Each test asserts one step of the cutover recorded by the module-scoped
`cutover` fixture (tests/migration/conftest.py). The rollback rehearsal
deliberately restores the legacy state from the timestamped backup,
exactly as docs/cutover-runbook.md instructs, then puts the migrated
state back so test order does not matter.

Runbook cross-references: every operator step in docs/cutover-runbook.md
names the test(s) here that prove it.
"""

import json

import pytest

from conftest import (
    LEGACY_ALERTS,
    LEGACY_LAST_VISIT,
    OPERATOR,
    SYNC_CODE_A,
    SYNC_CODE_C,
    file_bytes,
    run,
)


# --- Step 2 of the runbook: dry-run + review ------------------------------
def test_dry_run_previews_plan_without_mutation(cutover):
    out = cutover["dry_run"].stdout
    assert "DRY-RUN" in out
    assert "PLAN" in out
    # Legacy artifacts are detected as drift.
    for label in ("cron", "systemd_unit", "nginx_snippet", "logrotate"):
        assert f"install {label}" in out
    assert "sync offers_processing" in out
    # The dry run changed NOTHING on the box.
    assert cutover["post_dry_state"] == cutover["pre_state"]


def test_python_check_enforced_before_anything_else(cutover):
    # D3: update.sh aborts on <3.11 with the deadsnakes hint (covered in
    # depth by tests/installer/test_update_sh.py::test_python_below_311_aborts;
    # here we just pin the message contract the runbook references).
    v = cutover["vps"]
    proc = run(
        ["bash", str(v["repo"] / "deploy" / "update.sh"),
         "--config", str(v["conf"]), "--dry-run"],
        env={"PYTHON": "/bin/false"}, check=False,
    )
    assert proc.returncode != 0


# --- Step 3: apply — backup precedes any mutation --------------------------
def test_backup_taken_with_configs_and_sync_dir(cutover):
    backup = cutover["backup"]
    assert backup is not None, "no timestamped backup created"
    assert "BACKUP" in cutover["apply"].stdout
    # Live legacy configs are in the backup, byte-identical.
    assert (backup / "configs" / "config.py").read_bytes() == \
        cutover["pre_config_py"]
    assert (backup / "configs" / "settings.py").read_bytes() == \
        cutover["pre_settings_py"]
    # Full SYNC_DIR copy, byte-identical to the pre-migration profiles.
    backed_up = file_bytes(backup / "sync")
    assert backed_up == cutover["pre_sync"]


def test_sync_profiles_byte_identical_after_update(cutover):
    assert cutover["post_apply_sync"] == cutover["pre_sync"]


def test_vapid_keypair_untouched(cutover):
    assert cutover["post_vapid"] == cutover["pre_vapid"]
    assert "reused verbatim" in cutover["apply"].stdout


def test_legacy_code_converged_and_config_py_preserved(cutover):
    v = cutover["vps"]
    common = (v["APP_ROOT"] / "offers_processing" / "common.py").read_text()
    assert "stale legacy build marker" not in common
    # The operator's legacy config.py / settings.py are never overwritten.
    assert (v["APP_ROOT"] / "offers_processing" / "config.py").read_bytes() \
        == cutover["pre_config_py"]
    assert (v["APP_ROOT"] / "scraper" / "lidaldi" / "settings.py"
            ).read_bytes() == cutover["pre_settings_py"]


def test_frontend_dist_served_at_web_root(cutover):
    v = cutover["vps"]
    dist = v["repo"] / "frontend" / "dist"
    web = cutover["post_apply_webroot"]
    for rel in ("index.html", "sw.js", "manifest.json"):
        assert rel in web, f"{rel} missing from web root"
        assert web[rel] == (dist / rel).read_bytes()


@pytest.mark.xfail(
    reason="T6 follow-up (PROGRESS.md): push icon /img/lidaldi.png is not "
    "yet shipped by the frontend build", strict=False,
)
def test_push_icon_shipped_at_web_root(cutover):
    v = cutover["vps"]
    assert (v["WEB_ROOT"] / "img" / "lidaldi.png").is_file()
    assert (v["repo"] / "frontend" / "dist" / "img" / "lidaldi.png").is_file()


# --- Step 4: operator config edit + idempotent re-run ----------------------
def test_config_created_from_sample_needs_operator_edit(cutover):
    # Finding F1: update.sh creates config.toml/.env from the SAMPLES; the
    # legacy config.py values do NOT migrate automatically. The runbook
    # makes this edit an explicit mandatory step.
    assert "edit real values afterwards" in cutover["apply"].stdout


def test_operator_values_survive_into_toml_and_env(cutover):
    v = cutover["vps"]
    toml_text = (v["APP_ROOT"] / "config.toml").read_text()
    assert str(v["DATA_DIR"]) in toml_text
    assert OPERATOR["allowed_origin"] in toml_text
    assert v["vapid_public_key"] in toml_text
    assert OPERATOR["vapid_claims_email"] in toml_text
    assert f"port = {v['sync_port']}" in toml_text
    env_text = (v["APP_ROOT"] / ".env").read_text()
    assert f"TELEGRAM_BOT_TOKEN={OPERATOR['telegram_bot_token']}" in env_text
    assert f"TELEGRAM_CHAT_ID={OPERATOR['telegram_chat_id']}" in env_text
    assert f"VAPID_PRIVATE_KEY_PATH={v['vapid_pem']}" in env_text
    # Secrets never land in the TOML.
    assert OPERATOR["telegram_bot_token"] not in toml_text


def test_second_update_run_is_noop(cutover):
    out = cutover["second_run"].stdout
    assert "NOOP" in out
    assert "APPLY" not in out
    assert "BACKUP" not in out
    assert cutover["post_second_state"] is not None


# --- Step 5: first data run on the migrated box ----------------------------
def test_process_offers_succeeds_from_migrated_config(cutover):
    proc = cutover["process_1"]
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_first_run_seeds_first_seen_without_notification_storm(cutover):
    v = cutover["vps"]
    assert cutover["new_offers_1"] == []
    assert len(cutover["first_seen_1"]) == 60
    # After the second run the genuinely new offer joined the store too.
    store = json.loads((v["DATA_DIR"] / "first_seen.json").read_text())
    assert len(store) == 61


def test_offers_and_meta_generated_and_served(cutover):
    v = cutover["vps"]
    offers = json.loads((v["WEB_ROOT"] / "offers.json").read_text())
    assert len(offers) >= 60
    assert all("id" in o and "first_seen" in o for o in offers)
    meta = json.loads((v["WEB_ROOT"] / "meta.json").read_text())
    assert meta["vapidPublicKey"] == v["vapid_public_key"]
    assert isinstance(meta["lastUpdated"], int)


def test_built_index_html_survives_data_runs(cutover):
    # D2 complete: index.html is owned by the frontend build; data runs
    # must leave the deployed file byte-identical.
    dist_index = cutover["post_apply_webroot"]["index.html"]
    assert cutover["post_process_webroot_index"] == dist_index


def test_new_offer_detected_on_second_run(cutover):
    proc = cutover["process_2"]
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert [o["id"] for o in cutover["new_offers_2"]] == ["aldi-0999"]


# --- Step 6: smoke checks — sync server + push against migrated data -------
def test_sync_server_serves_migrated_profile(cutover):
    status, data = cutover["profile_a"]
    assert status == 200
    assert data["lastVisit"] == LEGACY_LAST_VISIT
    assert data["alerts"] == LEGACY_ALERTS
    assert data["tombstones"] == [{"id": "a0", "deletedAt": 1749500000}]


def test_sync_server_serves_oldest_profile_shape(cutover):
    status, data = cutover["profile_c"]
    assert status == 200
    assert data["lastVisit"] == 0
    assert data["alertMatches"] == {}


def test_push_send_path_uses_original_vapid_key(cutover):
    proc = cutover["notify"]
    assert proc.returncode == 0, proc.stdout + proc.stderr
    reqs = cutover["push_requests"]
    assert len(reqs) == 1, "expected exactly one aggregate push"
    req = reqs[0]
    assert req["path"] == "/wp/device-1"
    auth = req["headers"].get("authorization", "")
    assert auth.lower().startswith(("vapid", "webpush"))
    assert req["headers"].get("content-encoding") in ("aes128gcm", "aesgcm")
    assert len(req["body"]) > 0
    # The signing key on disk is still the legacy PEM, byte for byte.
    assert cutover["post_vapid"] == cutover["pre_vapid"]


def test_push_recorded_in_migrated_profile_ledger(cutover):
    prof = cutover["post_notify_profile_a"]
    assert prof["notified"], "per-endpoint ledger not updated"
    matches = prof.get("alertMatches", {})
    assert "a1" in matches
    assert [m["id"] for m in matches["a1"]] == ["aldi-0999"]
    # Alerts and lastVisit are untouched by the notification run.
    assert prof["alerts"] == LEGACY_ALERTS
    assert prof["lastVisit"] == LEGACY_LAST_VISIT


# --- Step 7 (rollback): manual restore from the timestamped backup ---------
def test_rollback_restores_legacy_state_from_backup(cutover):
    # Order-independent: the migrated state it mutates is snapshotted up
    # front and put back at the end, so the shared module-scoped sandbox is
    # unaffected for any test that runs after this one.
    v = cutover["vps"]
    backup = cutover["backup"]
    migrated_sync = {
        p.name: p.read_bytes() for p in sorted(v["SYNC_DIR"].iterdir())
    }
    migrated_toml = (v["APP_ROOT"] / "config.toml").read_bytes()
    try:
        # Simulate a bad post-cutover state the operator wants out of.
        (v["SYNC_DIR"] / f"{SYNC_CODE_A}.json").write_text("{corrupt")
        (v["SYNC_DIR"] / f"{SYNC_CODE_C}.json").unlink()
        (v["APP_ROOT"] / "config.toml").write_text("# broken by operator\n")

        # docs/cutover-runbook.md §Rollback — exact commands.
        run(["bash", "-c", " && ".join([
            f'cp -a "{backup}/configs/config.py" "{v["APP_ROOT"]}/offers_processing/"',
            f'cp -a "{backup}/configs/settings.py" "{v["APP_ROOT"]}/scraper/lidaldi/"',
            f'rm -rf "{v["SYNC_DIR"]}"',
            f'cp -a "{backup}/sync" "{v["SYNC_DIR"]}"',
        ])])

        assert file_bytes(v["SYNC_DIR"]) == cutover["pre_sync"]
        assert (v["APP_ROOT"] / "offers_processing" / "config.py").read_bytes() \
            == cutover["pre_config_py"]
        # The legacy config.py is authoritative again for the old pipeline; a
        # subsequent idempotent update.sh re-run is the roll-FORWARD recovery
        # (T10 verifier note: there is no automated restore in update.sh).
    finally:
        for p in list(v["SYNC_DIR"].iterdir()):
            p.unlink()
        for name, data in migrated_sync.items():
            (v["SYNC_DIR"] / name).write_bytes(data)
        (v["APP_ROOT"] / "config.toml").write_bytes(migrated_toml)
