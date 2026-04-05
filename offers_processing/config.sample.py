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
# ---------------------------------------------------------------------------
VAPID_PRIVATE_KEY_PATH = os.path.join(OFFERS_PROCESSING_DIR, "vapid_private.pem")
VAPID_PUBLIC_KEY = "your-vapid-public-key-base64url"
VAPID_CLAIMS_EMAIL = "mailto:admin@your-website-url"
