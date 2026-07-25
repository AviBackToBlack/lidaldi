# Observability — Prometheus Metric Inventory

LidAldi emits metrics as Prometheus **textfiles** (`.prom`) for the
node_exporter textfile collector. Emission is optional and gated on
configuration:

- `offers_processing/` emitters: `[paths] prom_textfile_dir` in
  `config.toml` (omit to disable);
- scraper: the Scrapy setting `PROM_TEXTFILE_DIR` (pulled from the same
  config by `settings.sample.py`).

Point both at the collector directory (typically
`/var/lib/prometheus/node-exporter`) and make it writable by the service
user; the systemd unit's `ReadWritePaths=` must include it (the installer
handles this via `PROM_DIR` in `install.local.conf`).

## Frozen metric inventory

This inventory is a **frozen contract** (T11, PR #11): the unit test
`tests/unit/test_metrics_parity.py` runs each emitter and fails if any
metric below is missing or renamed. 19 legacy series survived the refactor
byte-identically, plus one addition (`first_seen_size`) — 20 metric names
in total.

### `lidaldi_process_offers.prom` (`offers_processing/process_offers.py`, emitted on SUCCESS and FAILED)

| name | type | labels |
|---|---|---|
| `lidaldi_process_offers_last_run_timestamp_seconds` | gauge | — |
| `lidaldi_process_offers_status` | gauge | — |
| `lidaldi_process_offers_total_items` | gauge | — |
| `lidaldi_process_offers_new_items` | gauge | — |
| `lidaldi_process_offers_aldi_items` | gauge | — |
| `lidaldi_process_offers_lidl_items` | gauge | — |
| `lidaldi_process_offers_first_seen_size` | gauge | — *(new in T11: entries in the first_seen store after the run; watch for GC anomalies / store reseeding)* |

### `lidaldi_send_notifications.prom` (`offers_processing/send_notifications.py`, emitted on ok/skipped/error)

| name | type | labels |
|---|---|---|
| `lidaldi_notifications_last_run_timestamp_seconds` | gauge | — |
| `lidaldi_notifications_status` | gauge | — |
| `lidaldi_notifications_profiles_scanned` | counter | — |
| `lidaldi_notifications_profiles_with_alerts` | counter | — |
| `lidaldi_notifications_push_total` | counter | `status` ∈ {ok, expired, error} |
| `lidaldi_notifications_subs_expired_removed` | counter | — |

### `lidaldi_scraper_{spider}.prom` (`scraper/lidaldi/pipelines.py` `ErrorCheckingPipeline`, spider ∈ {aldi, lidl})

| name | type | labels |
|---|---|---|
| `lidaldi_scraper_last_run_timestamp_seconds` | gauge | `spider` |
| `lidaldi_scraper_status` | gauge | `spider` |
| `lidaldi_scraper_items_total` | gauge | `spider` |
| `lidaldi_scraper_error_count` | gauge | `spider` |
| `lidaldi_scraper_dropped_items` | gauge | `spider` |
| `lidaldi_scraper_dropped_ratio` | gauge | `spider` |
| `lidaldi_scraper_missing_ratio` | gauge | `spider`, `field` ∈ {title, description, price} |

Notes:

- `sync_server.py` emits no metrics (it never did pre-refactor either).
- Beyond Prometheus, the pipeline sends operator alerts via **Telegram**
  (`.env` `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`), including the
  notification-storm suppression alert when the new-offers sanity ratio is
  exceeded; run state (counts + offer-set SHA) is kept in
  `last_run.json` for churn detection.
