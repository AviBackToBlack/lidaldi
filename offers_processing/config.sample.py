import os

# Offers processing folder path
OFFERS_PROCESSING_DIR = "/path/to/processing/folder"

# Website root folder path
WEBSITE_ROOT_DIR = "/path/to/website/root/folder"

# Paths to individual JSON files
ALDI_OFFERS_JSON = os.path.join(OFFERS_PROCESSING_DIR, "aldi_offers.json")
LIDL_OFFERS_JSON = os.path.join(OFFERS_PROCESSING_DIR, "lidl_offers.json")
ALDI_SCRAPING_REPORT_JSON = os.path.join(OFFERS_PROCESSING_DIR, "aldi_scraping_report.json")
LIDL_SCRAPING_REPORT_JSON = os.path.join(OFFERS_PROCESSING_DIR, "lidl_scraping_report.json")

# New offers JSON (items added in this cron run, used by send_notifications.py)
NEW_OFFERS_JSON = os.path.join(OFFERS_PROCESSING_DIR, "new_offers.json")

# first_seen store: maps stable product id (ALDI SKU / LIDL canonical URL
# path) to {"first_seen": ts, "last_seen": ts}. Maintained by
# process_offers.py; "new" = id not present in this store. Entries not seen
# for >180 days are garbage-collected.
FIRST_SEEN_JSON = os.path.join(OFFERS_PROCESSING_DIR, "first_seen.json")

# Last-run state file (counts + SHA of the offer set). Used by monitoring /
# Telegram alerts to detect suspicious churn between runs.
LAST_RUN_STATE_JSON = os.path.join(OFFERS_PROCESSING_DIR, "last_run.json")

# Prometheus textfile exporter directory. Set to the directory watched by
# node_exporter's textfile collector (typically /var/lib/prometheus/node-exporter).
# Leave as None to disable metric emission.
PROM_TEXTFILE_DIR = None

# Static data files served from the web root (D2). offers.json is the merged
# offer list (each item carries id + first_seen); meta.json holds
# {"lastUpdated": unix_ts, "vapidPublicKey": ...} for the frontend.
OFFERS_JSON = os.path.join(WEBSITE_ROOT_DIR, "offers.json")
META_JSON = os.path.join(WEBSITE_ROOT_DIR, "meta.json")

# Telegram
TELEGRAM_BOT_TOKEN = "your-telegram-bot-token"
TELEGRAM_CHAT_ID = "your-chat-id"

# ---------------------------------------------------------------------------
# Sync server settings
# ---------------------------------------------------------------------------
SYNC_DIR = os.path.join(OFFERS_PROCESSING_DIR, "sync")
SYNC_SERVER_HOST = "127.0.0.1"
SYNC_SERVER_PORT = 8099
SYNC_ALLOWED_ORIGIN = "https://your-website-url"

# ---------------------------------------------------------------------------
# VAPID keys for Web Push notifications
# Generate with:  python generate_vapid_keys.py /path/to/processing/folder
#
# SECURITY: the private key is a long-lived signing credential. After
# generation, lock it down:
#
#     chown lidaldi:lidaldi vapid_private.pem
#     chmod 600 vapid_private.pem
#
# The systemd unit runs as the `lidaldi` user; no other account needs read
# access. Leaking this key lets an attacker forge push messages to every
# subscriber.
# ---------------------------------------------------------------------------
VAPID_PRIVATE_KEY_PATH = os.path.join(OFFERS_PROCESSING_DIR, "vapid_private.pem")
VAPID_PUBLIC_KEY = "your-vapid-public-key-base64url"
VAPID_CLAIMS_EMAIL = "mailto:admin@your-website-url"
