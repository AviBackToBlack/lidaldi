# LidAldi

[![Website](https://img.shields.io/badge/Live%20Site-Visit-blue)](https://lidaldi.neit.me/)

LidAldi aggregates non-food special offers from ALDI.IE and LIDL.IE. A daily
Scrapy run feeds a processing pipeline that publishes static JSON data files,
a zero-dependency sync server keeps alerts and last-visit state in sync across
devices, and Web Push notifications fire when new offers match user-defined
keyword alerts. The frontend is a static Vite + Svelte 5 PWA.

## Features

- **Aggregated offers:** non-food special offers from both ALDI.IE and LIDL.IE in one place, updated daily.
- **LidlPlus pricing:** LIDL offers display the LidlPlus member price when available.
- **Cross-device sync:** a short sync code keeps your last-visit timestamp and alerts in sync across devices.
- **Deal alerts:** keyword alerts (exact phrase, all words, or any word). Matching new offers trigger a Web Push notification linking to the product page.
- **"New from last visit":** items added since your last visit are highlighted; "new" is determined by a stable product id (ALDI SKU / LIDL canonical URL path) in the `first_seen` store, not by page diffing.
- **Installable PWA:** web app manifest + service worker (offline shell, cached `offers.json`/`meta.json` data).

## Important Notice for ALDI.IE and LIDL.IE Representatives

We respectfully request that you consider the following before taking any measures to block our scraper:

- **Respectful scraping:** significant delays between requests to minimize server impact.
- **Limited frequency:** one run per day.
- **No price comparison:** the website is not designed to compare prices on similar products.
- **Mutual benefit:** the website stimulates product purchases. Please consider the benefits before opting to block the scraper.

Thank you for your understanding.

## Architecture

```
cron (daily)
  └─ run_scrapers.sh
       ├─ Scrapy spiders (aldi, lidl)  →  {aldi,lidl}_offers.json + scraping reports
       ├─ process_offers.py
       │    ├─ merges offers, maintains first_seen store (stable ids, 180-day GC)
       │    ├─ writes offers.json + meta.json to the web root (static data, D2)
       │    ├─ writes new_offers.json (items new this run)
       │    └─ renders legacy index.html (transition only — see website/)
       └─ send_notifications.py
            ├─ matches new_offers.json against every profile's alerts
            └─ sends one aggregate Web Push per subscription endpoint,
               records matches in the profile's alertMatches ledger

sync_server.py (systemd, 127.0.0.1:8099)
  └─ /api/sync/{code} behind nginx — cross-device profiles
     (lastVisit, alerts, tombstones, alertMatches); contract frozen in
     docs/sync-contract.md

frontend/ (Vite + Svelte 5 SPA, static build output)
  └─ fetches offers.json + meta.json, talks to /api/sync/, registers
     the service worker + push subscription
```

Key data files (paths derived from config, see `config.toml.sample`):

| File | Written by | Consumed by |
|---|---|---|
| `<web root>/offers.json` | `process_offers.py` | frontend (each item carries `id` + `first_seen`) |
| `<web root>/meta.json` | `process_offers.py` | frontend (`{"lastUpdated": unix_ts, "vapidPublicKey": ...}`) |
| `<processing>/new_offers.json` | `process_offers.py` | `send_notifications.py` |
| `<processing>/first_seen.json` | `process_offers.py` | stable-id store; "new" = id not present |
| `<sync dir>/*` | `sync_server.py` / `send_notifications.py` | per-profile sync state (locked RMW) |

## Repository Layout

```
scraper/                    Scrapy project (ALDI + LIDL spiders, pipelines)
offers_processing/
  config_loader.py          TOML/.env config loader (Python >= 3.11, stdlib tomllib)
  common.py                 Shared helpers (logging, Telegram, Prometheus textfiles)
  sync_store.py             Cross-process locked JSON store for sync profiles (POSIX-only)
  process_offers.py         Merge + first_seen + offers.json/meta.json + new_offers.json
  send_notifications.py     Aggregate Web Push per endpoint for matched alerts
  sync_server.py            HTTP API for cross-device sync
  generate_vapid_keys.py    VAPID key pair generator for Web Push
frontend/                   Vite + Svelte 5 PWA (static build → frontend/dist)
website/                    LEGACY frontend — frozen for cutover (see website/README.md)
deploy/
  update.sh                 Idempotent installer/updater (plan-then-apply)
  merge_config.py           Sample→real config merge (adds keys, never clobbers)
  install.local.conf.sample Per-environment paths for update.sh (git-ignored real file)
docs/                       Operations, observability, testing, sync API contract
tests/                      Unit / installer / e2e / load / security tiers (see tests/README.md)
nginx/                      Reverse proxy snippet for the sync API
systemd/                    Hardened unit for the sync server
cron.d/, logrotate.d/       Daily pipeline schedule + log rotation
config.toml.sample          Non-secret configuration template
.env.sample                 Secrets template (Telegram, VAPID private key path)
```

## Requirements

- **Python ≥ 3.11** (decision D3 — the config loader uses stdlib `tomllib` and
  aborts on older interpreters). On Ubuntu install it via the deadsnakes PPA:
  `add-apt-repository ppa:deadsnakes/ppa && apt install python3.11`.
- Python packages: see `requirements.txt` (Scrapy, BeautifulSoup4, Pillow, pywebpush).
- **Node LTS** — only to build the frontend (`frontend/`) and run e2e tests; not needed at runtime on the server.
- **Operating system:** Linux / BSD / macOS. `sync_server.py`, `sync_store.py`
  and `send_notifications.py` use `fcntl.flock` and **will not run on
  Windows**. The scraper and `process_offers.py` are portable, but the full
  production pipeline targets POSIX only.

## Quickstart (development)

```bash
git clone https://github.com/AviBackToBlack/lidaldi.git
cd lidaldi

# Backend/pipeline: configure
cp config.toml.sample config.toml    # edit paths etc. (non-secret)
cp .env.sample .env                  # edit secrets (never commit)

# Frontend dev server
cd frontend && npm ci && npm run dev

# Frontend production build (static output in frontend/dist)
npm run build
```

Run the tests (containerized — identical to CI):

```bash
docker compose run --rm test make test
# or, on a host with python3 >= 3.11, Node LTS and Playwright browsers:
make test
```

`make test` = unit + installer + e2e + load + security tiers. See
[docs/testing.md](docs/testing.md) and [tests/README.md](tests/README.md).

## Configuration

Non-secret configuration lives in **`config.toml`** (template:
`config.toml.sample`); secrets live in **`.env`** (template: `.env.sample`).
The loader (`offers_processing/config_loader.py`) resolves the TOML as:
explicit path → `$LIDALDI_CONFIG` → `offers_processing/config.toml` →
repo-root `config.toml`; the `.env` is looked up next to the chosen TOML
(override with `$LIDALDI_ENV_FILE`), and process environment variables
override `.env` file values. A legacy `offers_processing/config.py` still
works during migration (with a `DeprecationWarning`); `config.toml` always
wins when present. Secrets placed in the TOML are rejected.

### Config key map (legacy `config.py` → TOML/.env)

| Legacy `config.py` | New location |
|---|---|
| `OFFERS_PROCESSING_DIR` | TOML `[paths] offers_processing_dir` (required) |
| `WEBSITE_ROOT_DIR` | TOML `[paths] website_root_dir` (required) |
| `ALDI_OFFERS_JSON` / `LIDL_OFFERS_JSON` | derived; override `[paths] aldi_offers_json` / `lidl_offers_json` |
| `ALDI_SCRAPING_REPORT_JSON` / `LIDL_SCRAPING_REPORT_JSON` | derived; override `[paths] aldi_scraping_report_json` / `lidl_scraping_report_json` |
| `NEW_OFFERS_JSON` / `FIRST_SEEN_JSON` / `LAST_RUN_STATE_JSON` | derived; override `[paths] new_offers_json` / `first_seen_json` / `last_run_state_json` |
| `PROM_TEXTFILE_DIR` | `[paths] prom_textfile_dir` (optional, default None) |
| `OFFERS_JSON` / `META_JSON` | derived; override `[paths] offers_json` / `meta_json` |
| `INDEX_TEMPLATE` / `INDEX_HTML` / `INDEX_NEW_HTML` / `INDEX_OLD_HTML` | derived; override `[paths] index_template` / `index_html` / `index_new_html` / `index_old_html` |
| `SYNC_DIR` | `[sync] dir` (default `<processing>/sync`) |
| `SYNC_SERVER_HOST` / `SYNC_SERVER_PORT` | `[sync] host` / `port` (defaults `127.0.0.1` / `8099`) |
| `SYNC_ALLOWED_ORIGIN` | `[sync] allowed_origin` (required) |
| `VAPID_PUBLIC_KEY` / `VAPID_CLAIMS_EMAIL` | `[push] vapid_public_key` / `vapid_claims_email` (required) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | **.env** `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` (required) |
| `VAPID_PRIVATE_KEY_PATH` | **.env** `VAPID_PRIVATE_KEY_PATH` (default `<processing>/vapid_private.pem`) |
| scraper `IMAGES_STORE` / `IMAGES_EXPIRES` / `DOWNLOAD_DELAY` | `[scraper] images_store` / `images_expires` (90) / `download_delay` (3) |
| scraper `SCRAPING_REPORT_DIR` | `[scraper] scraping_report_dir` (default `<processing>`) |
| scraper `ALDI_NO_IMAGE_URL` / `LIDL_NO_IMAGE_URL` | `[scraper] aldi_no_image_url` / `lidl_no_image_url` |
| scraper `FEEDS` | derived from `offers_processing_dir` (`%(name)s_offers.json`) |

The Scrapy `settings.sample.py` pulls its operator-tunable values from the
same loader (repo-relative, or `$LIDALDI_PROCESSING_DIR` in the deployed
layout); Scrapy-internal tuning stays in the settings file.

## Deploy / Update

Installation and updates are handled by the idempotent installer
**`deploy/update.sh`** (plan-then-apply: it only mutates on drift, and a
second run on an installed system is a strict no-op). Always dry-run first:

```bash
cp deploy/install.local.conf.sample deploy/install.local.conf   # edit paths
sudo ./deploy/update.sh --dry-run    # prints per-file diffs + action plan, mutates nothing
sudo ./deploy/update.sh              # backs up live configs + SYNC_DIR, then applies
```

The installer verifies Python ≥ 3.11 and aborts with the deadsnakes message
otherwise; it never generates, moves or rewrites the VAPID keypair, and never
touches `offers.json`/`meta.json` in the web root. Full operator procedures
(backups, VAPID handling, service-worker cache-name bumps, ZAP scans) are in
[docs/operations.md](docs/operations.md).

## Push Notifications & PWA

Push notifications require HTTPS and a browser that supports the Web Push API
(Chrome, Firefox, Edge; Safari on iOS when the site is added to the Home
Screen). The frontend is an installable PWA: `frontend/public/manifest.json`
plus a service worker built from `frontend/src/sw.ts` (offline app shell in a
versioned static cache, cached data files, push + notification-click
handlers).

The notification flow:
1. The user creates alerts in the frontend and enables notifications; the push subscription is stored in the sync profile.
2. The daily cron runs both spiders, then `process_offers.py` generates `new_offers.json`.
3. `send_notifications.py` matches new offers against all profiles' alerts and sends **one aggregate push per subscription endpoint** covering all matched alerts; matches are recorded in the profile's read-only `alertMatches` ledger (see [docs/sync-contract.md](docs/sync-contract.md)).
4. Clicking the notification opens the app (or the product page on aldi.ie / lidl.ie).

VAPID keys are generated once with
`offers_processing/generate_vapid_keys.py`; see
[docs/operations.md](docs/operations.md#vapid-keys) for handling rules — the
private key is a long-lived credential and losing or regenerating it silently
kills push for every subscriber.

## Frontend UI

> **Placeholder (T6 in flight):** the full feature UI (filtering, paging,
> alerts modal, deep-linked alert views) is being ported to Svelte and is not
> yet merged. This section will document the finished UI. Until then, the
> scaffold in `frontend/` covers data loading, sync, push wiring and the PWA
> shell; the legacy UI in `website/` remains what production serves.

## Documentation

- [docs/operations.md](docs/operations.md) — operations guide: installer, backups, VAPID, deploy discipline, ZAP scans
- [docs/observability.md](docs/observability.md) — Prometheus metric inventory (frozen contract)
- [docs/testing.md](docs/testing.md) — testing guide (pointer to tests/README.md)
- [docs/sync-contract.md](docs/sync-contract.md) — frozen sync API contract
- `REFACTOR_RESEARCH_AND_ARCHITECTURE.md`, `LOOP1_DELIVERABLES.md`, `PROGRESS.md`, `REFACTOR_OPERATOR_RUNBOOK.md` — refactor planning/state documents (not operator docs)

🔗 **Live Website:** [https://lidaldi.neit.me/](https://lidaldi.neit.me/)

---
*Enjoy special offers!*
