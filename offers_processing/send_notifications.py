#!/usr/bin/env python3
"""
LidAldi Push Notification Sender

Checks alerts in all sync profiles against new_offers.json and sends
Web Push notifications for matches. Deduplicates sends via a per-profile
`notified` ledger so interrupted or repeated cron runs don't resend.

Runs after process_offers.py in the cron chain.

Platform: POSIX only. `sync_store` uses fcntl for cross-process locking;
running on Windows is not supported. See README.md.
"""

import argparse
import json
import os
import sys
import time
from urllib.parse import urlparse

import config
import sync_store
from common import (
    log_event,
    hash_prefix,
    send_telegram_message,
    write_prom_textfile,
)

try:
    from pywebpush import WebPusher, WebPushException
    from py_vapid import Vapid
except ImportError:
    sys.stderr.write("pywebpush/py_vapid not installed. Run: pip install pywebpush\n")
    sys.exit(1)


# ---------------------------------------------------------------------------
# VAPID signing (L12): load the key once, cache signed headers by audience.
# ---------------------------------------------------------------------------
_vapid_instance = None
_vapid_headers_by_aud = {}


def get_vapid():
    global _vapid_instance
    if _vapid_instance is None:
        _vapid_instance = Vapid.from_file(config.VAPID_PRIVATE_KEY_PATH)
    return _vapid_instance


def vapid_headers_for(endpoint):
    """Return signed VAPID headers for the origin of `endpoint`.

    JWTs are cached per audience so we don't re-sign for every push.
    """
    u = urlparse(endpoint)
    aud = f"{u.scheme}://{u.netloc}"
    cached = _vapid_headers_by_aud.get(aud)
    if cached is not None:
        return cached
    v = get_vapid()
    headers = v.sign({"sub": config.VAPID_CLAIMS_EMAIL, "aud": aud})
    _vapid_headers_by_aud[aud] = headers
    return headers


# ---------------------------------------------------------------------------
# Push sender
# ---------------------------------------------------------------------------
def send_push(subscription, payload):
    """Send a single push. Returns 'ok', 'expired', or 'error'."""
    try:
        headers = vapid_headers_for(subscription["endpoint"])
        headers = dict(headers)
        headers.setdefault("TTL", "86400")
        resp = WebPusher(subscription).send(
            data=json.dumps(payload),
            headers=headers,
            ttl=86400,
        )
        status = getattr(resp, "status_code", None)
        if status in (404, 410):
            return "expired"
        if status is not None and status >= 400:
            log_event("push_http_error", status=status)
            return "error"
        return "ok"
    except WebPushException as e:
        status = e.response.status_code if e.response is not None else None
        if status in (404, 410):
            return "expired"
        log_event("push_error", status=status, error=str(e))
        return "error"
    except Exception as e:
        log_event("push_error", error=str(e))
        return "error"


# ---------------------------------------------------------------------------
# Alert matching
# ---------------------------------------------------------------------------
def match_alert(alert, item):
    keyword = (alert.get("keyword") or "").lower()
    match_type = alert.get("matchType")
    text = f"{item.get('title', '')} {item.get('description', '')}".lower()
    if not keyword:
        return False
    if match_type == "exact":
        return keyword in text
    if match_type == "allWords":
        return all(w in text for w in keyword.split())
    if match_type == "anyWord":
        return any(w in text for w in keyword.split())
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run(dry_run=False):
    stats = {
        "profiles_scanned": 0,
        "profiles_with_alerts": 0,
        "push_ok": 0,
        "push_expired": 0,
        "push_error": 0,
        "subs_expired_removed": 0,
    }

    if not os.path.exists(config.NEW_OFFERS_JSON):
        log_event("notifications_skip", reason="no_new_offers_file")
        emit_metrics(stats, "skipped")
        return

    try:
        with open(config.NEW_OFFERS_JSON, "r", encoding="utf-8") as f:
            new_offers = json.load(f)
    except Exception as e:
        log_event("notifications_read_error", error=str(e))
        emit_metrics(stats, "error")
        return

    if not new_offers:
        log_event("notifications_skip", reason="empty_new_offers")
        emit_metrics(stats, "skipped")
        return

    codes = sync_store.list_profiles()
    if not codes:
        log_event("notifications_skip", reason="no_profiles")
        emit_metrics(stats, "skipped")
        return

    for code in codes:
        stats["profiles_scanned"] += 1

        # --- Phase 1: snapshot profile under lock (read-only) ---
        snapshot_holder = {}

        def _snapshot(data):
            if data is None:
                return None
            snapshot_holder["data"] = dict(data)
            return None

        def _on_corrupt(err):
            log_event("sync_read_corrupt",
                      code=hash_prefix(code), error=str(err))

        try:
            sync_store.locked_rmw(code, _snapshot, on_corrupt=_on_corrupt)
        except Exception as e:
            log_event("profile_read_error",
                      code=hash_prefix(code), error=str(e))
            continue

        snapshot = snapshot_holder.get("data")
        if not snapshot:
            continue

        alerts = snapshot.get("alerts") or []
        subs = snapshot.get("pushSubscriptions") or []
        ledger = sync_store.gc_notified(snapshot.get("notified") or [])
        if not alerts or not subs:
            continue
        stats["profiles_with_alerts"] += 1

        # --- Phase 2: compute payloads outside the lock ---
        planned = []  # [{payload, alertId, matched_urls}]
        for alert in alerts:
            aid = alert.get("id")
            matches = [
                item for item in new_offers
                if item.get("url") and match_alert(alert, item)
                and not sync_store.already_notified(ledger, aid, item["url"])
            ]
            if not matches:
                continue
            first = matches[0]
            title = f"LidAldi Alert: {alert.get('keyword', '')}"
            body = (
                f"{first.get('store', '')}: {first.get('title', '')} "
                f"\u2014 \u20ac{first.get('price', 'N/A')}"
            )
            if len(matches) > 1:
                extra = len(matches) - 1
                body += f"\nand {extra} more match{'es' if extra > 1 else ''}"
            payload = {
                "title": title,
                "body": body,
                "url": first.get("url", ""),
                "icon": "/img/lidaldi.png",
            }
            planned.append({
                "payload": payload,
                "alertId": aid,
                "matched_urls": [m["url"] for m in matches],
            })

        if not planned:
            continue

        if dry_run:
            log_event("notifications_dry_run",
                      code=hash_prefix(code),
                      planned=len(planned),
                      alerts=len(alerts),
                      subs=len(subs))
            continue

        # --- Phase 3: send (outside lock) ---
        # Track which alerts were actually delivered to at least one live
        # subscription. Only those get ledger entries in Phase 4 so that
        # transient push failures (5xx, network errors) are retried on the
        # next cron run instead of being silently suppressed for 30 days.
        expired_endpoints = set()
        delivered_alert_ids = set()
        for entry in planned:
            payload = entry["payload"]
            any_ok = False
            for sub in subs:
                endpoint = sub.get("endpoint")
                if not endpoint or endpoint in expired_endpoints:
                    continue
                result = send_push(sub, payload)
                if result == "ok":
                    stats["push_ok"] += 1
                    any_ok = True
                elif result == "expired":
                    expired_endpoints.add(endpoint)
                    stats["push_expired"] += 1
                else:
                    stats["push_error"] += 1
            if any_ok:
                delivered_alert_ids.add(entry["alertId"])

        # Build ledger entries only for delivered alerts.
        now_ts = time.time()
        new_ledger_entries = []
        for entry in planned:
            if entry["alertId"] not in delivered_alert_ids:
                continue
            for url in entry["matched_urls"]:
                new_ledger_entries.append({
                    "alertId": entry["alertId"],
                    "url": url,
                    "at": now_ts,
                })

        # --- Phase 4: RMW to update ledger & drop expired subs ---
        def _finalize(data):
            if data is None:
                return None
            ledger2 = sync_store.gc_notified(data.get("notified") or [])
            seen = {(e.get("alertId"), e.get("url")) for e in ledger2}
            for e in new_ledger_entries:
                key = (e["alertId"], e["url"])
                if key in seen:
                    continue
                ledger2.append(e)
                seen.add(key)
            data["notified"] = ledger2[-sync_store.MAX_NOTIFIED:]
            if expired_endpoints:
                before = len(data.get("pushSubscriptions", []))
                data["pushSubscriptions"] = [
                    s for s in data.get("pushSubscriptions", [])
                    if s.get("endpoint") not in expired_endpoints
                ]
                stats["subs_expired_removed"] += (
                    before - len(data["pushSubscriptions"])
                )
            return data

        try:
            sync_store.locked_rmw(code, _finalize, on_corrupt=_on_corrupt)
        except Exception as e:
            log_event("profile_finalize_error",
                      code=hash_prefix(code), error=str(e))

        log_event(
            "profile_processed",
            code=hash_prefix(code),
            planned=len(planned),
            ok=stats["push_ok"],
            expired=stats["push_expired"],
            errors=stats["push_error"],
        )

    log_event("notifications_summary", **stats)
    emit_metrics(stats, "ok")


def emit_metrics(stats, status):
    path = getattr(config, "PROM_TEXTFILE_DIR", None)
    if not path:
        return
    metrics_file = os.path.join(path, "lidaldi_send_notifications.prom")
    metrics = [
        {"name": "lidaldi_notifications_last_run_timestamp_seconds",
         "value": int(time.time()),
         "help": "Unix timestamp of last send_notifications.py run.",
         "type": "gauge"},
        {"name": "lidaldi_notifications_status",
         "value": 1 if status == "ok" else 0,
         "help": "1 if last run ran to completion, else 0.",
         "type": "gauge"},
        {"name": "lidaldi_notifications_profiles_scanned",
         "value": stats.get("profiles_scanned", 0),
         "help": "Number of sync profiles scanned.",
         "type": "counter"},
        {"name": "lidaldi_notifications_profiles_with_alerts",
         "value": stats.get("profiles_with_alerts", 0),
         "help": "Profiles that had alerts and subscriptions.",
         "type": "counter"},
        {"name": "lidaldi_notifications_push_total",
         "value": stats.get("push_ok", 0),
         "help": "Push notifications sent successfully.",
         "type": "counter",
         "labels": {"status": "ok"}},
        {"name": "lidaldi_notifications_push_total",
         "value": stats.get("push_expired", 0),
         "help": "Push notifications sent successfully.",
         "type": "counter",
         "labels": {"status": "expired"}},
        {"name": "lidaldi_notifications_push_total",
         "value": stats.get("push_error", 0),
         "help": "Push notifications sent successfully.",
         "type": "counter",
         "labels": {"status": "error"}},
        {"name": "lidaldi_notifications_subs_expired_removed",
         "value": stats.get("subs_expired_removed", 0),
         "help": "Expired push subscriptions cleaned up.",
         "type": "counter"},
    ]
    write_prom_textfile(metrics_file, metrics)


def main():
    parser = argparse.ArgumentParser(description="LidAldi push notification sender")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be sent; do not actually deliver or "
             "mutate sync profiles.",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
