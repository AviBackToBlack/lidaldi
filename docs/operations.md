# Operations Guide

Operator procedures for installing, updating and running LidAldi in
production. Companion docs: [observability.md](observability.md)
(metrics), [testing.md](testing.md) (test suites),
[sync-contract.md](sync-contract.md) (sync API).

## Installer / updater (`deploy/update.sh`)

One script handles both fresh installs and updates. It is **idempotent and
plan-then-apply**: every step (service user, directories, code sync,
`frontend/dist` → web root, rendered cron/logrotate/systemd/nginx files,
venv + deps, config merge) checks the current state and only registers an
action on drift. A second run on an already-installed system is a strict
no-op (`NOOP`, no backup, no mutation).

```bash
cp deploy/install.local.conf.sample deploy/install.local.conf
$EDITOR deploy/install.local.conf     # APP_ROOT, WEB_ROOT, SERVICE_USER, SYNC_DIR, LOG_DIR, ...

sudo ./deploy/update.sh --dry-run     # ALWAYS dry-run first
sudo ./deploy/update.sh               # apply
```

- `--dry-run` prints the per-file diffs and full action list and mutates
  nothing.
- `--no-restart` skips the systemd `daemon-reload`/`restart` of
  `lidaldi-sync` (which otherwise happens only when the rendered unit
  changed, running as root, with systemd present).
- `--config /path/to/install.local.conf` uses an alternate local config.
- Preflight: aborts unless `python3` is ≥ 3.11 (decision D3). On Ubuntu:
  `add-apt-repository ppa:deadsnakes/ppa`, install `python3.11`, re-run with
  `PYTHON=python3.11`.
- The real `install.local.conf` is git-ignored — paths differ per
  environment and never belong in the repo.
- The venv is re-pipped only when the `requirements.txt` hash changes.
- The web-root sync deploys `frontend/dist` verbatim but **never touches
  `offers.json` / `meta.json`** — those are data written by
  `process_offers.py` (D2: app deploy ≠ data write). `frontend/dist` is a
  build artifact: build it in CI or locally (`cd frontend && npm ci && npm
  run build`) before running the installer; if it is missing the installer
  warns and skips the web-root sync rather than running npm on the server.

### Config merge (`deploy/merge_config.py`)

Run by the installer; the sample files are the schema:

- **ADD** — keys present in `config.toml.sample`/`.env.sample` but missing in
  the live file are appended (into the right `[section]`); live values are
  **never overwritten**.
- **REVIEW** — live keys absent from the sample (removed/renamed upstream)
  are reported, never deleted.
- **WARN** — secret-looking keys in the TOML (`token|secret|password|api_key|private_key`)
  are flagged: secrets belong in `.env`.
- Exit codes: `0` in-sync, `3` changes made/needed, `2` error.

## Backups

Before its **first mutating action** (and only then — no-op runs take no
backup), `update.sh` writes a timestamped backup to
`$BACKUP_DIR/lidaldi-backup-<stamp>/` containing:

- live configs: `config.toml`, `.env`, and legacy `config.py` /
  `settings.py` if present;
- the entire `SYNC_DIR` (sync profiles: alerts, lastVisit, push
  subscriptions, tombstones, alertMatches).

`BACKUP_DIR` is set in `install.local.conf`. Keep independent periodic
backups of `SYNC_DIR` and the VAPID private key as well — the sync profiles
and the keypair are the only state that cannot be regenerated from the repo.

## VAPID keys

The VAPID keypair authenticates the server to browser push services. It is
**a long-lived credential: if the private key is lost or regenerated, every
existing push subscription silently dies** and all users must re-enable
notifications.

- Generate **once**, at first install only:

  ```bash
  python offers_processing/generate_vapid_keys.py /path/to/processing/folder
  ```

  This writes `vapid_private.pem` and prints the public key. Put the public
  key in `config.toml` (`[push] vapid_public_key`) and the private key path
  in `.env` (`VAPID_PRIVATE_KEY_PATH`, defaults to
  `<offers_processing_dir>/vapid_private.pem`).

- Lock the private key down — anyone who reads it can forge push messages to
  every subscriber:

  ```bash
  sudo chown lidaldi:lidaldi vapid_private.pem
  sudo chmod 600 vapid_private.pem
  ```

- `deploy/update.sh` **never generates, moves or rewrites** the keypair; it
  only checks and reports its existence. Include `vapid_private.pem` in your
  off-machine backups.

## Deploy discipline: service-worker cache-name bump

The service worker (`frontend/src/sw.ts`) caches the app shell in a
versioned static cache (`STATIC_CACHE = "lidaldi-static-v1"`) with a
cache-first strategy, and prunes caches not in `KNOWN_CACHES` on activate.
Consequence for deploys:

> **Whenever statically-cached assets change** (icons, `manifest.json`,
> anything served cache-first) **bump the `STATIC_CACHE` version** (e.g.
> `lidaldi-static-v1` → `-v2`) in `frontend/src/sw.ts` as part of the same
> change, then rebuild. The new SW installs, activates
> (`skipWaiting`/`clients.claim`) and deletes the old cache; without the
> bump, returning clients keep serving stale assets from the old cache.

Hashed Vite build assets are immune (new URLs), so this mainly concerns the
fixed-URL files in `frontend/public/`. Data files (`offers.json`,
`meta.json`) use a network-first data cache and never need a bump.

## Services, cron, logs

Managed by the installer (rendered from the repo templates with your
`install.local.conf` paths):

- **systemd**: `lidaldi-sync.service` — the sync server on
  `127.0.0.1:8099`. The unit ships hardened (`NoNewPrivileges`,
  `ProtectSystem=strict`, `MemoryDenyWriteExecute`, restrictive
  `SystemCallFilter`); its `ReadWritePaths=` must cover `SYNC_DIR` and (if
  enabled) the Prometheus textfile directory — the installer renders this
  from your paths.
- **nginx**: `nginx/lidaldi-sync-proxy.conf` — reverse proxy for
  `/api/sync/` (10 KB body cap, `X-Real-IP`/`X-Forwarded-For` headers; the
  server rate-limits 30 req/min per client IP).
- **cron**: `cron.d/lidaldi` — daily chain `run_scrapers.sh` → spiders →
  `process_offers.py` → `send_notifications.py`.
- **logrotate**: `logrotate.d/lidaldi` for `LOG_DIR`.
- **Prometheus** (optional): set `[paths] prom_textfile_dir` in
  `config.toml` and `PROM_DIR` in `install.local.conf`; see
  [observability.md](observability.md).

## Security scans

`pip-audit`, `bandit` and `npm audit` run in every `make test` (default CI).
The OWASP ZAP baseline scan is **opt-in only** (decision D4), from a host
with docker compose:

```bash
make test-zap
```

This boots a `zap-target` compose service (built frontend + real sync
server on one origin, port 8100, mirroring the production nginx layout) and
runs `zap-baseline.py` against it. Set `ZAP_TARGET` to scan a running
instance instead. Teardown is scoped to the zap-profile services, so a
running `test` container is untouched.
