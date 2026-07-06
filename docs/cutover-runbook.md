# LIDALDI VPS Cutover Runbook (T15)

Exact operator steps to migrate the production VPS from the legacy system
(static `website/` rendering, legacy `config.py`/`settings.py`, Python 3.8)
to the refactored stack. **Do NOT execute against the real VPS before Hard
Stop #2 sign-off** (PROGRESS.md).

Every step is proven by an automated rehearsal assertion in
`tests/migration/test_rehearsal.py` (run with `make test-migration`),
executed against a sandboxed simulation of the production box:
legacy operator configs, populated SYNC_DIR profiles (alerts, lastVisit,
push subscriptions, tombstones), the live VAPID PEM, legacy web root and
cron/systemd/nginx artifacts.

## Preconditions

| Check | Rehearsal proof |
|---|---|
| Full box snapshot/backup independent of this procedure (recommended) | — (operator responsibility) |
| Repo checkout of branch `refactor` on the VPS | fixture `build_legacy_vps` (deploys from a checkout) |
| Frontend built: `cd frontend && npm ci && npm run build` | `test_frontend_dist_served_at_web_root` (update.sh warns and skips web root if `frontend/dist` is missing) |

## Step 1 — Install Python 3.11 (deadsnakes, decision D3)

```sh
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv
```

The installer refuses to run on anything older and prints the deadsnakes
hint — you cannot skip this step by accident.
**Proof:** `test_python_check_enforced_before_anything_else`,
`tests/installer/test_update_sh.py::test_python_below_311_aborts`.

## Step 2 — Configure and dry-run

```sh
cp deploy/install.local.conf.sample deploy/install.local.conf
$EDITOR deploy/install.local.conf   # APP_ROOT, WEB_ROOT, SYNC_DIR (the
                                    # EXISTING live sync dir!), LOG_DIR,
                                    # VAPID_PRIVATE_KEY_PATH (the EXISTING pem)
sudo PYTHON=python3.11 deploy/update.sh --dry-run
```

Review the printed plan: expect drift on cron/logrotate/systemd/nginx,
code sync, web root, venv, and config creation. A dry run changes
**nothing** on disk and takes no backup.
**Proof:** `test_dry_run_previews_plan_without_mutation`.

## Step 3 — Apply

```sh
sudo PYTHON=python3.11 deploy/update.sh
```

Before mutating anything, the installer writes a timestamped backup to
`$BACKUP_DIR/lidaldi-backup-<stamp>/` containing the live configs
(`config.py`, `settings.py`, `config.toml`, `.env` if present) and a full
copy of `SYNC_DIR`. Note the backup path printed at the end.

What the apply guarantees:

| Guarantee | Rehearsal proof |
|---|---|
| Backup precedes any mutation; SYNC_DIR copy is byte-identical | `test_backup_taken_with_configs_and_sync_dir` |
| SYNC_DIR profiles untouched by the installer (no data loss) | `test_sync_profiles_byte_identical_after_update` |
| VAPID keypair reused verbatim — never generated/moved/rewritten | `test_vapid_keypair_untouched`, `test_push_send_path_uses_original_vapid_key` |
| Legacy `config.py`/`settings.py` never overwritten by the code sync | `test_legacy_code_converged_and_config_py_preserved` |
| Frontend dist (index.html, sw.js, manifest.json) served at web root | `test_frontend_dist_served_at_web_root` |

## Step 4 — Edit the new config files (MANDATORY)

`update.sh` creates `$APP_ROOT/config.toml` and `$APP_ROOT/.env` **from the
samples** — it does NOT migrate values out of the legacy `config.py`
automatically (finding F1, see the T15 PR). Carry your live values over by
hand, using the key map in the T9 PR (#7):

- `config.toml`: `offers_processing_dir`, `website_root_dir`, `[sync]`
  host/port/`allowed_origin`, `[push] vapid_public_key` /
  `vapid_claims_email`, `[scraper]` settings.
- `.env` (mode 0600): `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
  `VAPID_PRIVATE_KEY_PATH` (point at the **existing** PEM).

Then re-run the installer; it must report `NOOP` (converged state):

```sh
sudo PYTHON=python3.11 deploy/update.sh   # expect: NOOP
```

**Proof:** `test_config_created_from_sample_needs_operator_edit`,
`test_operator_values_survive_into_toml_and_env`,
`test_second_update_run_is_noop`.

## Step 5 — First data run

Trigger one pipeline run (or wait for cron):

```sh
sudo -u <service-user> $APP_ROOT/.venv/bin/python \
    $APP_ROOT/offers_processing/process_offers.py
```

Expected on the very first migrated run: the `first_seen` store does not
exist yet, so it is **seeded** from the current offers and
`new_offers.json` is empty — **no notification storm**. `offers.json` and
`meta.json` (carrying your VAPID public key) appear in the web root.
**Proof:** `test_process_offers_succeeds_from_migrated_config`,
`test_first_run_seeds_first_seen_without_notification_storm`,
`test_offers_and_meta_generated_and_served`,
`test_new_offer_detected_on_second_run`.

## Step 6 — Smoke checks

```sh
systemctl status lidaldi-sync
curl -s https://<site>/api/sync/<a-real-code> | jq .   # alerts + lastVisit intact
curl -sI https://<site>/offers.json                    # 200
curl -sI https://<site>/sw.js                          # 200
```

Existing profiles must be served unchanged by the new sync server (alerts,
lastVisit, tombstones — including the oldest on-disk profile shape), and
the next notification run must deliver pushes signed with the original
VAPID key to existing subscriptions.
**Proof:** `test_sync_server_serves_migrated_profile`,
`test_sync_server_serves_oldest_profile_shape`,
`test_push_send_path_uses_original_vapid_key`,
`test_push_recorded_in_migrated_profile_ledger`.

## Rollback — manual restore from the timestamped backup

There is no automated restore in `update.sh` (T10 verifier note); recovery
is manual and rehearsed. From the backup path printed in Step 3:

```sh
B=/var/backups/lidaldi/lidaldi-backup-<stamp>
sudo cp -a "$B/configs/config.py"   $APP_ROOT/offers_processing/
sudo cp -a "$B/configs/settings.py" $APP_ROOT/scraper/lidaldi/
# restore config.toml/.env from $B/configs/ too if they existed pre-run
sudo rm -rf "$SYNC_DIR" && sudo cp -a "$B/sync" "$SYNC_DIR"
sudo chown -R <service-user>:<service-user> "$SYNC_DIR"
```

This returns the profile data and legacy configs byte-identical to their
pre-cutover state. Roll-*forward* recovery is simply re-running the
idempotent `update.sh`.
**Proof:** `test_rollback_restores_legacy_state_from_backup`.

## Known gaps found by the rehearsal (tracked, not fixed here)

- **F1** — no automated legacy `config.py` → TOML/.env value migration;
  Step 4 is mandatory manual work.
- **F2** — RESOLVED (D2 complete): `process_offers.py` no longer renders
  `index.html`; the deployed frontend build survives data runs
  (`test_built_index_html_survives_data_runs` now passes).
- **T6 follow-up** — push icon `/img/lidaldi.png` is not yet shipped by the
  frontend build (xfail `test_push_icon_shipped_at_web_root`).
- `update.sh` code sync never *removes* files deleted from the repo
  (legacy modules and a stale `index.html.tpl` may linger in
  APP_ROOT/WEB_ROOT — harmless now that nothing reads the template).
