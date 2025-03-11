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

# index.html paths
INDEX_TEMPLATE = os.path.join(WEBSITE_ROOT_DIR, "index.html.tpl")
INDEX_HTML = os.path.join(WEBSITE_ROOT_DIR, "index.html")
INDEX_NEW_HTML = os.path.join(WEBSITE_ROOT_DIR, "index.new.html")
INDEX_OLD_HTML = os.path.join(WEBSITE_ROOT_DIR, "index.old.html")

# Telegram
TELEGRAM_BOT_TOKEN = "your-telegram-bot-token"
TELEGRAM_CHAT_ID = "your-chat-id"
