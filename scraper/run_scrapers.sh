#!/bin/bash
#
# LidAldi scraper + post-processing cron driver.
#
# Any single stage failure aborts the chain so we don't render the site
# from partial data. Per-step timeouts bound the worst-case runtime.
#
set -euo pipefail

SCRAPY_DIR="/path/to/scrapy"
PROCESSING_DIR="/path/to/processing"
IMAGES_DIR="/path/to/images/folder"
VENV_ACTIVATE=""   # e.g. "/path/to/venv/bin/activate"

# Timeouts (seconds). Tune to your crawl budget.
SCRAPE_TIMEOUT=1800
PROCESS_TIMEOUT=300
NOTIFY_TIMEOUT=600

cd "$SCRAPY_DIR"

if [ -n "$VENV_ACTIVATE" ]; then
    # shellcheck disable=SC1090
    source "$VENV_ACTIVATE"
fi

# Run ALDI and LIDL spiders sequentially. If either fails, `set -e` stops
# the chain before process_offers runs.
timeout "$SCRAPE_TIMEOUT" scrapy crawl aldi
timeout "$SCRAPE_TIMEOUT" scrapy crawl lidl

# Post-process merged offers and render the site.
timeout "$PROCESS_TIMEOUT" python "$PROCESSING_DIR/process_offers.py"

# Send push notifications for new offers matching user alerts. Runs after
# process_offers.py so it sees the freshly written new_offers.json.
timeout "$NOTIFY_TIMEOUT" python "$PROCESSING_DIR/send_notifications.py"

# Delete images older than 90 calendar days. `-daystart` anchors -mtime
# to midnight so the cutoff is stable regardless of the cron start time.
# `-type f` avoids clobbering the directory itself; no shell glob so an
# empty dir is safe.
find "$IMAGES_DIR" -daystart -type f -mtime +90 -delete
