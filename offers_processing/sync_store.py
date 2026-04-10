"""Shared persistence layer for LidAldi sync profiles.

Used by both `sync_server.py` (long-running HTTP service) and
`send_notifications.py` (cron job). Provides cross-process locking via
`fcntl.flock` on a dedicated lock file, plus alert-merge helpers with
tombstone support for cross-device consistency.

NOTE: This module uses `fcntl` and therefore works only on POSIX systems.
Running the sync pipeline on Windows is not supported — see README.md.
"""

import json
import os
import time

try:
    import fcntl  # POSIX-only. See module docstring.
except ImportError as _e:
    raise RuntimeError(
        "sync_store requires fcntl (POSIX). LidAldi sync stack is not "
        "supported on Windows; run inside Linux/WSL."
    ) from _e

import config


TOMBSTONE_TTL_SEC = 30 * 24 * 3600
NOTIFIED_TTL_SEC = 30 * 24 * 3600
MAX_TOMBSTONES = 200
MAX_NOTIFIED = 2000


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------
def data_path(code):
    return os.path.join(config.SYNC_DIR, f"{code}.json")


def lock_path(code):
    return os.path.join(config.SYNC_DIR, f"{code}.lock")


def _quarantine_path(code):
    return os.path.join(config.SYNC_DIR, f"{code}.corrupt.{int(time.time())}")


def _read_raw(code, on_corrupt=None):
    """Read a sync file, quarantining the file if corrupt. Returns dict or None."""
    p = data_path(code)
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("not an object")
        return data
    except (json.JSONDecodeError, OSError, ValueError) as e:
        try:
            os.replace(p, _quarantine_path(code))
        except OSError:
            pass
        if on_corrupt:
            on_corrupt(e)
        return None


def _write_atomic(code, data):
    p = data_path(code)
    parent = os.path.dirname(p)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, p)


# ---------------------------------------------------------------------------
# Locked read-modify-write
# ---------------------------------------------------------------------------
def locked_rmw(code, modifier, thread_lock=None, on_corrupt=None):
    """Atomic cross-process read-modify-write for a sync profile.

    Acquires (optionally) an in-process thread lock, then a cross-process
    fcntl.flock on a dedicated lock file. The `modifier` callback receives
    the current dict (or None) and must return either:
      - a dict (same or new object) to persist, or
      - None to skip writing (read-only path).
    In-place mutation of the passed-in dict is supported: returning the
    same object still triggers a write. Returns the final dict (the
    written one if any, otherwise the freshly-read one).
    """
    os.makedirs(config.SYNC_DIR, exist_ok=True)
    lockpath = lock_path(code)
    if thread_lock is not None:
        thread_lock.acquire()
    try:
        lockfd = open(lockpath, "a+")
        try:
            fcntl.flock(lockfd.fileno(), fcntl.LOCK_EX)
            data = _read_raw(code, on_corrupt=on_corrupt)
            new_data = modifier(data)
            if new_data is not None:
                _write_atomic(code, new_data)
                return new_data
            return data
        finally:
            try:
                fcntl.flock(lockfd.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            lockfd.close()
    finally:
        if thread_lock is not None:
            thread_lock.release()


def list_profiles():
    """Return sync codes for profiles on disk (excludes lock/tmp/corrupt files)."""
    try:
        entries = os.listdir(config.SYNC_DIR)
    except FileNotFoundError:
        return []
    codes = []
    for name in entries:
        if not name.endswith(".json"):
            continue
        if ".corrupt." in name or name.endswith(".tmp"):
            continue
        codes.append(name[: -len(".json")])
    return codes


# ---------------------------------------------------------------------------
# Alert merge with tombstones
# ---------------------------------------------------------------------------
def gc_tombstones(tombstones, now=None):
    now = now if now is not None else time.time()
    return [
        t for t in (tombstones or [])
        if isinstance(t, dict) and (now - float(t.get("at", 0))) < TOMBSTONE_TTL_SEC
    ][-MAX_TOMBSTONES:]


def merge_alerts(existing_alerts, existing_tombstones,
                 client_alerts, client_tombstones, now=None):
    """Merge alert lists with tombstones. Returns (alerts, tombstones).

    If `client_alerts` is None, client is sending no alerts update (server
    keeps existing); tombstones are still merged if provided.
    """
    now = now if now is not None else time.time()
    tombs = gc_tombstones(existing_tombstones, now=now)
    tomb_ids = {t["id"] for t in tombs}

    for t in (client_tombstones or []):
        if not isinstance(t, dict):
            continue
        tid = t.get("id")
        if not isinstance(tid, str):
            continue
        if tid in tomb_ids:
            continue
        at = t.get("at")
        try:
            at_val = float(at) if at is not None else now
        except (TypeError, ValueError):
            at_val = now
        tombs.append({"id": tid, "at": at_val})
        tomb_ids.add(tid)
    tombs = tombs[-MAX_TOMBSTONES:]

    merged = {}
    for a in (existing_alerts or []):
        aid = a.get("id")
        if not aid or aid in tomb_ids:
            continue
        merged[aid] = a
    if client_alerts is not None:
        for a in client_alerts:
            aid = a.get("id")
            if not aid or aid in tomb_ids:
                continue
            prev = merged.get(aid)
            if prev is None or (a.get("createdAt") or 0) >= (prev.get("createdAt") or 0):
                merged[aid] = a
    return list(merged.values()), tombs


# ---------------------------------------------------------------------------
# Notification ledger (dedup across cron runs)
# ---------------------------------------------------------------------------
def gc_notified(ledger, now=None):
    now = now if now is not None else time.time()
    kept = [
        e for e in (ledger or [])
        if isinstance(e, dict)
        and (now - float(e.get("at", 0))) < NOTIFIED_TTL_SEC
    ]
    return kept[-MAX_NOTIFIED:]


def already_notified(ledger, alert_id, url):
    for e in (ledger or []):
        if e.get("alertId") == alert_id and e.get("url") == url:
            return True
    return False
