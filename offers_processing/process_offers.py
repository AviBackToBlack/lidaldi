#!/usr/bin/env python3
"""
LidAldi Offers Processor

Merges ALDI and LIDL scraped offers into a single dataset, generates
new_offers.json (for push notifications), writes offers_urls.json (used
by the next run to determine what is "new"), and renders the final
index.html from the template.

Run after both spiders have finished in the cron chain.
"""

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime

import config
from common import (
    log_event,
    send_telegram_message,
    write_prom_textfile,
)


# Ratio of new items above which we consider the run suspicious and abort
# notification generation. Typical daily churn is well below this.
NEW_OFFER_SANITY_RATIO = 0.3

# Minimum plausible offer count. Below this we assume a scraper meltdown
# even if individual reports said SUCCESS.
MIN_TOTAL_OFFERS = 50


# ---------------------------------------------------------------------------
# Telegram wrapper using structured logging
# ---------------------------------------------------------------------------
def telegram(message):
    send_telegram_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, message)


# ---------------------------------------------------------------------------
# JSON-in-HTML escaping (C1)
# ---------------------------------------------------------------------------
def safe_json_for_script(obj, indent=2):
    """Serialize `obj` to JSON that is safe to embed inside an HTML
    <script> block. Prevents `</script>` termination and U+2028/U+2029
    script-parser surprises."""
    s = json.dumps(obj, indent=indent, ensure_ascii=False)
    return (
        s.replace("</", "<\\/")
         .replace("\u2028", "\\u2028")
         .replace("\u2029", "\\u2029")
    )


# ---------------------------------------------------------------------------
# Offer field cleanup & availability parsing
# ---------------------------------------------------------------------------
def clean_description(desc: str) -> str:
    desc = desc.replace('\t', '')
    desc = re.sub(r'\n\s*\n+', '\n', desc)
    return desc.strip()


def parse_store_availability(avail: str) -> str:
    low = avail.lower()
    if "while stock" in low:
        return "01-01-0000"
    if "unknown" in low or not avail.strip():
        return "01-01-9999"
    match_dash = re.search(r'(\d{2}-\d{2}-\d{4})', avail)
    if match_dash:
        date_str = match_dash.group(1)
        try:
            parsed = datetime.strptime(date_str, "%d-%m-%Y")
        except ValueError:
            return "01-01-9999"
        return date_str if parsed.date() >= datetime.now().date() else "01-01-0000"
    match_dot = re.search(r'(\d{2}\.\d{2})', avail)
    if match_dot:
        dd, mm = match_dot.group(1).split('.')
        now = datetime.now()
        year = now.year
        date_str = f"{dd}-{mm}-{year}"
        try:
            parsed = datetime.strptime(date_str, "%d-%m-%Y")
        except ValueError:
            return "01-01-9999"
        if parsed.date() < now.date():
            if now.month >= 11 and parsed.month <= 2:
                parsed = parsed.replace(year=year + 1)
            else:
                return "01-01-0000"
        return parsed.strftime("%d-%m-%Y") if parsed.date() >= now.date() else "01-01-0000"
    match_wdm = re.search(r'\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})\s+([A-Za-z]{3})', avail)
    if match_wdm:
        day = match_wdm.group(1)
        month_abbr = match_wdm.group(2)
        now = datetime.now()
        year = now.year
        try:
            parsed = datetime.strptime(f"{day} {month_abbr} {year}", "%d %b %Y")
        except ValueError:
            return "01-01-9999"
        if parsed.date() < now.date():
            if now.month >= 11 and parsed.month <= 2:
                try:
                    parsed = parsed.replace(year=year + 1)
                except ValueError:
                    return "01-01-9999"
            else:
                return "01-01-0000"
        return parsed.strftime("%d-%m-%Y") if parsed.date() >= now.date() else "01-01-0000"
    if "in store" in low:
        return "01-01-0000"
    return "01-01-9999"


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------
def file_exists(path: str) -> bool:
    return os.path.exists(path) and os.path.getsize(path) > 0


def load_json_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_atomic(path: str, content: str):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)


def load_previous_urls() -> set:
    """Load the previous offer URL set from offers_urls.json.

    If the file is missing (first run or corruption), returns None so
    the caller can distinguish "truly no previous state" from "empty
    set" and avoid the notification-storm failure mode (H2).
    """
    path = getattr(config, "OFFERS_URLS_JSON", None)
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {u for u in data if isinstance(u, str)}
        if isinstance(data, dict) and "urls" in data:
            return {u for u in data["urls"] if isinstance(u, str)}
        return None
    except Exception as e:
        log_event("previous_urls_read_error", path=path, error=str(e))
        return None


def save_previous_urls(urls):
    path = getattr(config, "OFFERS_URLS_JSON", None)
    if not path:
        return
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    write_atomic(path, json.dumps(sorted(urls), ensure_ascii=False))


def compute_offers_hash(items):
    m = hashlib.sha256()
    for it in sorted(items, key=lambda x: x.get("url", "")):
        m.update((it.get("url", "") + "|" + str(it.get("scraped_at", ""))).encode("utf-8"))
    return m.hexdigest()


# ---------------------------------------------------------------------------
# Metrics emission
# ---------------------------------------------------------------------------
def emit_metrics(summary, status):
    path = getattr(config, "PROM_TEXTFILE_DIR", None)
    if not path:
        return
    metrics_file = os.path.join(path, "lidaldi_process_offers.prom")
    metrics = [
        {"name": "lidaldi_process_offers_last_run_timestamp_seconds",
         "value": int(time.time()),
         "help": "Unix timestamp of last process_offers.py run.",
         "type": "gauge"},
        {"name": "lidaldi_process_offers_status",
         "value": 1 if status == "SUCCESS" else 0,
         "help": "1 if last run succeeded, else 0.",
         "type": "gauge"},
        {"name": "lidaldi_process_offers_total_items",
         "value": summary.get("total_items", 0),
         "help": "Total merged offer items written to the site.",
         "type": "gauge"},
        {"name": "lidaldi_process_offers_new_items",
         "value": summary.get("new_items", 0),
         "help": "Offers classified as new-since-last-run.",
         "type": "gauge"},
        {"name": "lidaldi_process_offers_aldi_items",
         "value": summary.get("aldi_items", 0),
         "help": "ALDI offer count.",
         "type": "gauge"},
        {"name": "lidaldi_process_offers_lidl_items",
         "value": summary.get("lidl_items", 0),
         "help": "LIDL offer count.",
         "type": "gauge"},
    ]
    write_prom_textfile(metrics_file, metrics)


def write_last_run_state(summary, status):
    path = getattr(config, "LAST_RUN_STATE_JSON", None)
    if not path:
        return
    try:
        state = {
            "ts": time.time(),
            "status": status,
            **summary,
        }
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        write_atomic(path, json.dumps(state, ensure_ascii=False, indent=2))
    except Exception as e:
        log_event("last_run_state_write_error", error=str(e))


def fatal(msg, summary):
    log_event("process_offers_failed", reason=msg, **summary)
    telegram(f"LIDALDI: {msg}")
    write_last_run_state(summary, "FAILED")
    emit_metrics(summary, "FAILED")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    summary = {
        "total_items": 0,
        "new_items": 0,
        "aldi_items": 0,
        "lidl_items": 0,
        "offers_hash": None,
    }

    try:
        required_files = {
            "ALDI_OFFERS_JSON": config.ALDI_OFFERS_JSON,
            "LIDL_OFFERS_JSON": config.LIDL_OFFERS_JSON,
            "ALDI_SCRAPING_REPORT_JSON": config.ALDI_SCRAPING_REPORT_JSON,
            "LIDL_SCRAPING_REPORT_JSON": config.LIDL_SCRAPING_REPORT_JSON,
        }
        for name, path in required_files.items():
            if not file_exists(path):
                fatal(f"Required file {name} not found or empty at {path}", summary)

        aldi_offers = load_json_file(config.ALDI_OFFERS_JSON)
        lidl_offers = load_json_file(config.LIDL_OFFERS_JSON)
        aldi_report = load_json_file(config.ALDI_SCRAPING_REPORT_JSON)
        lidl_report = load_json_file(config.LIDL_SCRAPING_REPORT_JSON)

        if aldi_report.get("overall_result") != "SUCCESS":
            fatal("ALDI scraping report indicates failure.", summary)
        if lidl_report.get("overall_result") != "SUCCESS":
            fatal("LIDL scraping report indicates failure.", summary)

        lidaldi_offers = []
        for item in aldi_offers:
            description = clean_description(item.get("description", "No description"))
            store_availability = parse_store_availability(item.get("store_availability", "Unknown"))
            lidaldi_offers.append({
                "store": item.get("store", ""),
                "url": item.get("url", ""),
                "category": item.get("category", ""),
                "title": item.get("title", ""),
                "scraped_at": item.get("scraped_at", 0),
                "description": description,
                "store_availability_date": store_availability,
                "price": item.get("price", "N/A"),
                "image_urls": item.get("image_urls", []),
                "images": item.get("images", []),
            })
        for item in lidl_offers:
            description = clean_description(item.get("description", "No description"))
            store_availability = parse_store_availability(item.get("store_availability", "Unknown"))
            lidaldi_offers.append({
                "store": item.get("store", ""),
                "url": item.get("url", ""),
                "category": item.get("category", ""),
                "title": item.get("title", ""),
                "scraped_at": item.get("scraped_at", 0),
                "description": description,
                "store_availability_date": store_availability,
                "price": item.get("price", "N/A"),
                "image_urls": item.get("image_urls", []),
                "images": item.get("images", []),
            })

        summary["aldi_items"] = len(aldi_offers)
        summary["lidl_items"] = len(lidl_offers)
        summary["total_items"] = len(lidaldi_offers)
        summary["offers_hash"] = compute_offers_hash(lidaldi_offers)

        if summary["total_items"] < MIN_TOTAL_OFFERS:
            fatal(
                f"Merged offer count {summary['total_items']} below "
                f"sanity minimum {MIN_TOTAL_OFFERS}.",
                summary,
            )

        # ------------------------------------------------------------------
        # Determine new offers via persisted URL list (H2)
        # ------------------------------------------------------------------
        previous_urls = load_previous_urls()
        current_urls = {it["url"] for it in lidaldi_offers if it.get("url")}

        if previous_urls is None:
            # First run (or previous state corrupt). Do NOT treat every
            # item as new — that would trigger a notification storm.
            log_event("previous_urls_missing", note="skipping new_offers generation")
            new_offers = []
        else:
            new_offers = [
                it for it in lidaldi_offers
                if it.get("url") and it["url"] not in previous_urls
            ]
            ratio = (
                len(new_offers) / summary["total_items"]
                if summary["total_items"] else 0.0
            )
            if ratio > NEW_OFFER_SANITY_RATIO:
                log_event(
                    "new_offers_ratio_exceeded",
                    ratio=round(ratio, 3),
                    new_items=len(new_offers),
                    total_items=summary["total_items"],
                )
                telegram(
                    f"LIDALDI: new_offers ratio {ratio:.2f} "
                    f"exceeds sanity threshold {NEW_OFFER_SANITY_RATIO}; "
                    f"suppressing notifications for this run."
                )
                new_offers = []

        summary["new_items"] = len(new_offers)

        # Atomic write of new_offers.json
        new_offers_content = json.dumps(new_offers, indent=2, ensure_ascii=False)
        parent = os.path.dirname(config.NEW_OFFERS_JSON)
        if parent:
            os.makedirs(parent, exist_ok=True)
        write_atomic(config.NEW_OFFERS_JSON, new_offers_content)

        # ------------------------------------------------------------------
        # Render index.html
        # ------------------------------------------------------------------
        if not os.path.exists(config.INDEX_TEMPLATE):
            fatal(f"{config.INDEX_TEMPLATE} does not exist", summary)

        with open(config.INDEX_TEMPLATE, "r", encoding="utf-8") as tpl:
            template_content = tpl.read()

        offers_json_str = safe_json_for_script(lidaldi_offers, indent=2)
        today_str = datetime.now().strftime("%d/%m/%Y")
        meta_data = safe_json_for_script({"lastUpdated": today_str}, indent=2)

        new_content = template_content.replace("%%SPECIAL_OFFERS_DATA%%", offers_json_str)
        new_content = new_content.replace("%%SPECIAL_OFFERS_META_DATA%%", meta_data)
        # VAPID key lands in a quoted HTML attribute; escape defensively.
        # A well-formed base64url key has no special characters, but
        # operator misconfiguration (e.g. pasting a PEM) must not break
        # the markup or inject attributes.
        vapid_attr = (
            (config.VAPID_PUBLIC_KEY or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )
        new_content = new_content.replace("%%VAPID_PUBLIC_KEY%%", vapid_attr)

        # Persist URL list BEFORE replacing index.html.
        #
        # index.html and offers_urls.json are two separate writes; there
        # is a window where one can succeed and the other can fail. If
        # we wrote index.html first and crashed, the next run would diff
        # today's offers against the stale (or missing) URL snapshot and
        # reclassify already-published items as "new", firing a
        # notification storm. Writing offers_urls.json first makes the
        # failure mode benign: worst case the site shows yesterday's
        # data for one cycle, but the next run diffs today's URLs
        # against today's snapshot and generates zero false new_offers.
        save_previous_urls(current_urls)

        # Single atomic rename: write to .tmp, then os.replace into place.
        # This avoids the previous two-step rename that could leave index.html
        # absent if the process was interrupted (H3).
        tmp_path = config.INDEX_HTML + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        os.replace(tmp_path, config.INDEX_HTML)

        log_event(
            "process_offers_success",
            total_items=summary["total_items"],
            new_items=summary["new_items"],
            aldi_items=summary["aldi_items"],
            lidl_items=summary["lidl_items"],
            offers_hash=summary["offers_hash"][:12] if summary["offers_hash"] else None,
        )
        write_last_run_state(summary, "SUCCESS")
        emit_metrics(summary, "SUCCESS")

    except SystemExit:
        raise
    except Exception as e:
        fatal(f"Processing error: {e}", summary)


if __name__ == "__main__":
    main()
