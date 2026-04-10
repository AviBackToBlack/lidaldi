"""Shared helpers used by LidAldi offers_processing scripts.

Provides:
    - Structured JSON-line logging.
    - Telegram alerting with MarkdownV2 escaping.
    - Prometheus textfile-exporter output.
    - Small hashing helper for log correlation.
"""

import hashlib
import json
import os
import sys
import time


_MD_V2_SPECIAL = set(r"_*[]()~`>#+-=|{}.!\\")


def escape_md_v2(text):
    """Escape text so it is safe inside Telegram MarkdownV2 content."""
    if not isinstance(text, str):
        text = str(text)
    out = []
    for ch in text:
        if ch in _MD_V2_SPECIAL:
            out.append("\\")
        out.append(ch)
    return "".join(out)


def log_event(event, stream=None, **kv):
    """Emit a single JSON line to stderr (or the provided stream)."""
    entry = {"ts": round(time.time(), 3), "event": event}
    entry.update(kv)
    target = stream if stream is not None else sys.stderr
    try:
        target.write(json.dumps(entry, default=str) + "\n")
        target.flush()
    except Exception:
        pass


def hash_prefix(value, n=8):
    """Return first `n` hex chars of SHA-256(value). Used to tag sync codes in logs."""
    if value is None:
        return "-"
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:n]


def _prom_escape(s):
    return str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def write_prom_textfile(path, metrics):
    """Write Prometheus textfile-exporter format metrics atomically.

    metrics: iterable of dicts with keys:
        name (str), value (int/float), help (str), type (str),
        labels (dict, optional)
    """
    if not path:
        return
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        tmp = path + ".tmp"
        lines = []
        seen_headers = set()
        for m in metrics:
            name = m["name"]
            if name not in seen_headers:
                lines.append(f"# HELP {name} {m.get('help', '')}")
                lines.append(f"# TYPE {name} {m.get('type', 'gauge')}")
                seen_headers.add(name)
            labels = m.get("labels") or {}
            if labels:
                label_str = ",".join(
                    f'{k}="{_prom_escape(v)}"' for k, v in labels.items()
                )
                lines.append(f"{name}{{{label_str}}} {m['value']}")
            else:
                lines.append(f"{name} {m['value']}")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(tmp, path)
    except Exception as e:
        log_event("prom_write_error", path=path, error=str(e))


def send_telegram_message(token, chat_id, message):
    """Send a Telegram message using MarkdownV2. Silent-fails on any error."""
    try:
        import requests
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": escape_md_v2(message),
            "parse_mode": "MarkdownV2",
        }
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        log_event("telegram_error", error=str(e))
