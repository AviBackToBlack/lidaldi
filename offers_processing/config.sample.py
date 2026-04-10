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

# Snapshot of the URLs in the previously-rendered offer set. process_offers.py
# reads this on the next run to diff "what's new" instead of re-parsing
# index.html — the HTML is a presentation artefact, not a data source.
OFFERS_URLS_JSON = os.path.join(OFFERS_PROCESSING_DIR, "offers_urls.json")

# Last-run state file (counts + SHA of the offer set). Used by monitoring /
# Telegram alerts to detect suspicious churn between runs.
LAST_RUN_STATE_JSON = os.path.join(OFFERS_PROCESSING_DIR, "last_run.json")

# Prometheus textfile exporter directory. Set to the directory watched by
# node_exporter's textfile collector (typically /var/lib/prometheus/node-exporter).
# Leave as None to disable metric emission.
PROM_TEXTFILE_DIR = None

# index.html paths
INDEX_TEMPLATE = os.path.join(WEBSITE_ROOT_DIR, "index.html.tpl")
INDEX_HTML = os.path.join(WEBSITE_ROOT_DIR, "index.html")
INDEX_NEW_HTML = os.path.join(WEBSITE_ROOT_DIR, "index.new.html")
INDEX_OLD_HTML = os.path.join(WEBSITE_ROOT_DIR, "index.old.html")

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
