#!/usr/bin/env python3
"""
LidAldi Push Notification Sender

Checks alerts in all sync profiles against new_offers.json and sends
Web Push notifications for matches.

Run after process_offers.py in the cron chain.
"""

import fcntl
import json
import os
import sys
import glob

import config

try:
    from pywebpush import webpush, WebPushException
except ImportError:
    sys.stderr.write("pywebpush not installed. Run: pip install pywebpush\n")
    sys.exit(1)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def match_alert(alert, item):
    """Check if an alert matches an item's title or description."""
    keyword = alert["keyword"].lower()
    match_type = alert["matchType"]
    text = f"{item.get('title', '')} {item.get('description', '')}".lower()

    if match_type == "exact":
        return keyword in text
    elif match_type == "allWords":
        return all(w in text for w in keyword.split())
    elif match_type == "anyWord":
        return any(w in text for w in keyword.split())
    return False


def send_push(subscription, payload, vapid_key_path, vapid_claims):
    """Send a single push notification. Returns 'ok', 'expired', or 'error'."""
    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps(payload),
            vapid_private_key=vapid_key_path,
            vapid_claims=vapid_claims,
        )
        return "ok"
    except WebPushException as e:
        if e.response and e.response.status_code in (404, 410):
            return "expired"
        sys.stderr.write(f"Push error: {e}\n")
        return "error"
    except Exception as e:
        sys.stderr.write(f"Push error: {e}\n")
        return "error"


def main():
    # Load new offers
    if not os.path.exists(config.NEW_OFFERS_JSON):
        print("No new_offers.json found, skipping notifications.")
        return

    new_offers = load_json(config.NEW_OFFERS_JSON)
    if not new_offers:
        print("No new offers, skipping notifications.")
        return

    # Load all sync profiles
    sync_pattern = os.path.join(config.SYNC_DIR, "*.json")
    sync_files = glob.glob(sync_pattern)
    if not sync_files:
        print("No sync profiles found, skipping notifications.")
        return

    vapid_claims = {"sub": config.VAPID_CLAIMS_EMAIL}
    profiles_checked = 0

    for sync_path in sync_files:
        try:
            sync_data = load_json(sync_path)
        except Exception as e:
            sys.stderr.write(f"Error reading {sync_path}: {e}\n")
            continue

        alerts = sync_data.get("alerts", [])
        subs = sync_data.get("pushSubscriptions", [])
        if not alerts or not subs:
            continue

        profiles_checked += 1

        # Collect notifications: one per alert that has matches
        notifications = []
        for alert in alerts:
            matches = [item for item in new_offers if match_alert(alert, item)]
            if not matches:
                continue

            first = matches[0]
            title = f"LidAldi Alert: {alert['keyword']}"
            body = f"{first.get('store', '')}: {first.get('title', '')} \u2014 \u20ac{first.get('price', 'N/A')}"
            if len(matches) > 1:
                extra = len(matches) - 1
                body += f"\nand {extra} more match{'es' if extra > 1 else ''}"

            notifications.append({
                "title": title,
                "body": body,
                "url": first.get("url", ""),
                "icon": "/img/lidaldi.png",
            })

        if not notifications:
            continue

        # Send all notifications and track expired subscriptions
        expired_endpoints = set()
        for payload in notifications:
            for sub in subs:
                if sub["endpoint"] in expired_endpoints:
                    continue
                result = send_push(sub, payload, config.VAPID_PRIVATE_KEY_PATH, vapid_claims)
                if result == "expired":
                    expired_endpoints.add(sub["endpoint"])

        # Clean up expired subscriptions (with file lock to avoid races with sync_server)
        if expired_endpoints:
            try:
                with open(sync_path, "r+", encoding="utf-8") as f:
                    fcntl.flock(f, fcntl.LOCK_EX)
                    try:
                        current_data = json.load(f)
                        current_data["pushSubscriptions"] = [
                            s for s in current_data.get("pushSubscriptions", [])
                            if s["endpoint"] not in expired_endpoints
                        ]
                        tmp = sync_path + ".tmp"
                        with open(tmp, "w", encoding="utf-8") as tf:
                            json.dump(current_data, tf, ensure_ascii=False)
                        os.replace(tmp, sync_path)
                    finally:
                        fcntl.flock(f, fcntl.LOCK_UN)
            except Exception as e:
                sys.stderr.write(f"Error updating {sync_path}: {e}\n")

    print(f"Notification check complete. {len(sync_files)} profiles scanned, {profiles_checked} had active alerts.")


if __name__ == "__main__":
    main()
