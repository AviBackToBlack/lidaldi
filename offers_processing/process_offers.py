#!/usr/bin/env python3
"""
LidAldi Offers Processor

Merges ALDI and LIDL scraped offers into a single dataset, maintains the
first_seen store (stable product id -> first-appearance timestamp), generates
new_offers.json (for push notifications), writes offers.json/meta.json for
the frontend, and renders the final index.html from the template.

Run after both spiders have finished in the cron chain.
"""

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime

from config_loader import get_config
from common import (
    log_event,
    send_telegram_message,
    write_prom_textfile,
)

config = get_config()


# Ratio of new items above which we consider the run suspicious and abort
# notification generation. Typical daily churn is well below this.
NEW_OFFER_SANITY_RATIO = 0.3

# Minimum plausible offer count. Below this we assume a scraper meltdown
# even if individual reports said SUCCESS.
MIN_TOTAL_OFFERS = 50

# first_seen entries not seen for this many days are garbage-collected.
FIRST_SEEN_GC_DAYS = 180


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


def _resolve_yearless_date(day: int, month: int, now: datetime):
    """Resolve a day/month with no year to the calendar date nearest to today.

    Nearest-future-date rule (N7): among the previous, current and next
    year's occurrences, pick the one closest to today. A nearest occurrence
    in the past means the availability window already started; a nearest
    occurrence in the future (even across a year boundary, e.g. "05.03"
    seen in December) is a genuine future start date. Returns None when no
    year in the window yields a valid date (e.g. "29.02" outside leap
    years).
    """
    candidates = []
    for y in (now.year - 1, now.year, now.year + 1):
        try:
            candidates.append(datetime(y, month, day))
        except ValueError:
            continue
    if not candidates:
        return None
    return min(candidates, key=lambda d: abs((d.date() - now.date()).days))


def parse_store_availability(avail: str, now: datetime | None = None) -> str:
    now = now if now is not None else datetime.now()
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
        return date_str if parsed.date() >= now.date() else "01-01-0000"
    match_dot = re.search(r'(\d{2}\.\d{2})', avail)
    if match_dot:
        dd, mm = match_dot.group(1).split('.')
        try:
            day, month = int(dd), int(mm)
        except ValueError:
            return "01-01-9999"
        if not 1 <= month <= 12:
            return "01-01-9999"
        parsed = _resolve_yearless_date(day, month, now)
        if parsed is None:
            return "01-01-9999"
        return parsed.strftime("%d-%m-%Y") if parsed.date() >= now.date() else "01-01-0000"
    match_wdm = re.search(r'\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})\s+([A-Za-z]{3})', avail)
    if match_wdm:
        day = match_wdm.group(1)
        month_abbr = match_wdm.group(2)
        try:
            month = datetime.strptime(month_abbr, "%b").month
        except ValueError:
            return "01-01-9999"
        parsed = _resolve_yearless_date(int(day), month, now)
        if parsed is None:
            return "01-01-9999"
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


def offer_id(item) -> str:
    """Stable product id: ALDI SKU / LIDL canonical URL path (D5).
    Falls back to the URL for items scraped before ids existed."""
    return item.get("id") or item.get("url", "")


def load_first_seen():
    """Load the first_seen store from FIRST_SEEN_JSON.

    Maps product id -> {"first_seen": ts, "last_seen": ts}. If the file
    is missing (first run or corruption), returns None so the caller can
    distinguish "truly no previous state" from "empty store" and avoid
    the notification-storm failure mode (H2).
    """
    path = config.FIRST_SEEN_JSON
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"expected JSON object, got {type(data).__name__}")
        store = {}
        for pid, entry in data.items():
            if not isinstance(pid, str):
                continue
            if isinstance(entry, dict) and "first_seen" in entry:
                store[pid] = {
                    "first_seen": int(entry["first_seen"]),
                    "last_seen": int(entry.get("last_seen", entry["first_seen"])),
                }
            elif isinstance(entry, (int, float)):
                store[pid] = {"first_seen": int(entry), "last_seen": int(entry)}
        return store
    except Exception as e:
        quarantine_corrupt_first_seen(path, e)
        return None


def quarantine_corrupt_first_seen(path, error):
    """Move an unreadable first_seen store aside for forensics and alert
    the operator. Reseeding resets every first_seen to "now", so the
    operator may want to restore the store from the sidecar or a backup
    before the UI starts badging items as "New" off these timestamps."""
    corrupt_path = f"{path}.corrupt.{int(time.time())}"
    try:
        os.replace(path, corrupt_path)
    except OSError as move_err:
        log_event("first_seen_quarantine_error", path=path, error=str(move_err))
        corrupt_path = None
    log_event(
        "first_seen_read_error",
        path=path,
        error=str(error),
        quarantined_to=corrupt_path,
    )
    telegram(
        f"LIDALDI: first_seen store unreadable ({error}); "
        f"preserved as {corrupt_path or 'N/A'} and reseeding. "
        f"first_seen timestamps reset — restore from the sidecar or a "
        f"backup to keep 'New' badges accurate."
    )


def save_first_seen(store):
    path = config.FIRST_SEEN_JSON
    if not path:
        return
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    write_atomic(path, json.dumps(store, ensure_ascii=False, sort_keys=True))


def update_first_seen(store, current_ids, now):
    """Update `store` in place with the ids seen in this run.

    Adds new ids with first_seen=last_seen=now, refreshes last_seen for
    ids present in this run, and garbage-collects entries not seen for
    more than FIRST_SEEN_GC_DAYS. Returns the set of new ids.
    """
    new_ids = {pid for pid in current_ids if pid not in store}
    for pid in current_ids:
        if pid in store:
            store[pid]["last_seen"] = now
        else:
            store[pid] = {"first_seen": now, "last_seen": now}
    cutoff = now - FIRST_SEEN_GC_DAYS * 86400
    for pid in [p for p, e in store.items() if e["last_seen"] < cutoff]:
        del store[pid]
    return new_ids


def exceeds_sanity_ratio(new_count, total_count) -> bool:
    if not total_count:
        return False
    return new_count / total_count > NEW_OFFER_SANITY_RATIO


def compute_offers_hash(items):
    m = hashlib.sha256()
    for it in sorted(items, key=lambda x: offer_id(x)):
        m.update((offer_id(it) + "|" + str(it.get("scraped_at", ""))).encode("utf-8"))
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
                "id": offer_id(item),
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
                "id": offer_id(item),
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
        # Determine new offers via the first_seen store (H2, D5)
        # ------------------------------------------------------------------
        now_ts = int(time.time())
        first_seen_store = load_first_seen()
        current_ids = {offer_id(it) for it in lidaldi_offers if offer_id(it)}

        if first_seen_store is None:
            # First run (or previous state corrupt). Seed the store with
            # every current id but do NOT treat any item as new — that
            # would trigger a notification storm.
            log_event("first_seen_missing", note="seeding store; skipping new_offers generation")
            first_seen_store = {}
            update_first_seen(first_seen_store, current_ids, now_ts)
            new_offers = []
        else:
            new_ids = update_first_seen(first_seen_store, current_ids, now_ts)
            new_offers = [
                it for it in lidaldi_offers
                if offer_id(it) and offer_id(it) in new_ids
            ]
            ratio = (
                len(new_offers) / summary["total_items"]
                if summary["total_items"] else 0.0
            )
            if exceeds_sanity_ratio(len(new_offers), summary["total_items"]):
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

        for it in lidaldi_offers:
            entry = first_seen_store.get(offer_id(it))
            it["first_seen"] = entry["first_seen"] if entry else now_ts

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

        # Persist the first_seen store BEFORE replacing the published
        # site files.
        #
        # These are separate writes; there is a window where one can
        # succeed and the other can fail. If we published first and
        # crashed, the next run would diff today's offers against the
        # stale (or missing) store and reclassify already-published
        # items as "new", firing a notification storm. Writing the store
        # first makes the failure mode benign: worst case the site shows
        # yesterday's data for one cycle, but the next run diffs today's
        # ids against today's store and generates zero false new_offers.
        save_first_seen(first_seen_store)

        # Static data files for the frontend (D2), atomic replace.
        for path in (config.OFFERS_JSON, config.META_JSON):
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
        write_atomic(
            config.OFFERS_JSON,
            json.dumps(lidaldi_offers, indent=2, ensure_ascii=False),
        )
        write_atomic(
            config.META_JSON,
            json.dumps(
                {"lastUpdated": now_ts, "vapidPublicKey": config.VAPID_PUBLIC_KEY},
                indent=2,
                ensure_ascii=False,
            ),
        )

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
