import config
import json
import re
import os
import sys
import time
from datetime import datetime
import requests

def send_telegram_message(message: str):
    try:
        token = config.TELEGRAM_BOT_TOKEN
        chat_id = config.TELEGRAM_CHAT_ID
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, data=payload)
        response.raise_for_status()
    except Exception as e:
        sys.stderr.write(f"Error sending Telegram message: {e}\n")

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
        parsed = datetime.strptime(date_str, "%d-%m-%Y")
        return date_str if parsed.date() >= datetime.now().date() else "01-01-0000"
    match_dot = re.search(r'(\d{2}\.\d{2})', avail)
    if match_dot:
        dd, mm = match_dot.group(1).split('.')
        now = datetime.now()
        year = now.year
        date_str = f"{dd}-{mm}-{year}"
        parsed = datetime.strptime(date_str, "%d-%m-%Y")
        return parsed.strftime("%d-%m-%Y") if parsed.date() >= datetime.now().date() else "01-01-0000"
    match_wdm = re.search(r'\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})\s+([A-Za-z]{3})', avail)
    if match_wdm:
        day = match_wdm.group(1)
        month_abbr = match_wdm.group(2)
        now = datetime.now()
        year = now.year
        try:
            parsed = datetime.strptime(f"{day} {month_abbr} {year}", "%d %b %Y")
        except ValueError:
            return "01-01-0000"
        return parsed.strftime("%d-%m-%Y") if parsed.date() >= now.date() else "01-01-0000"
    return "01-01-9999"

def file_exists(path: str) -> bool:
    return os.path.exists(path) and os.path.getsize(path) > 0

def load_json_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    try:
        required_files = {
            "ALDI_OFFERS_JSON": config.ALDI_OFFERS_JSON,
            "LIDL_OFFERS_JSON": config.LIDL_OFFERS_JSON,
            "ALDI_SCRAPING_REPORT_JSON": config.ALDI_SCRAPING_REPORT_JSON,
            "LIDL_SCRAPING_REPORT_JSON": config.LIDL_SCRAPING_REPORT_JSON
        }
        for name, path in required_files.items():
            if not file_exists(path):
                msg = f"[ERROR] : Required file {name} not found or empty at {path}"
                sys.stderr.write(msg + "\n")
                send_telegram_message(f"LIDALDI : {msg}")
                sys.exit(1)

        aldi_offers = load_json_file(config.ALDI_OFFERS_JSON)
        lidl_offers = load_json_file(config.LIDL_OFFERS_JSON)
        aldi_report = load_json_file(config.ALDI_SCRAPING_REPORT_JSON)
        lidl_report = load_json_file(config.LIDL_SCRAPING_REPORT_JSON)

        if aldi_report.get("overall_result") != "SUCCESS":
            msg = "[ERROR] : ALDI scraping report indicates failure."
            sys.stderr.write(msg + "\n")
            send_telegram_message(f"LIDALDI : {msg}")
            sys.exit(1)
        if lidl_report.get("overall_result") != "SUCCESS":
            msg = "[ERROR] : LIDL scraping report indicates failure."
            sys.stderr.write(msg + "\n")
            send_telegram_message(f"LIDALDI : {msg}")
            sys.exit(1)

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
                "images": item.get("images", [])
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
                "images": item.get("images", [])
            })

        if os.path.exists(config.INDEX_TEMPLATE):
            with open(config.INDEX_TEMPLATE, "r", encoding="utf-8") as tpl:
                template_content = tpl.read()

            offers_json_str = json.dumps(lidaldi_offers, indent=2, ensure_ascii=False)
            today_str = datetime.now().strftime("%d/%m/%Y")
            meta_data = json.dumps({"lastUpdated": today_str}, indent=2)
            new_content = template_content.replace("%%SPECIAL_OFFERS_DATA%%", offers_json_str)
            new_content = new_content.replace("%%SPECIAL_OFFERS_META_DATA%%", meta_data)

            with open(config.INDEX_NEW_HTML, "w", encoding="utf-8") as f:
                f.write(new_content)

            index_html_path = config.INDEX_HTML
            if os.path.exists(index_html_path):
                os.replace(index_html_path, config.INDEX_OLD_HTML)
            os.replace(config.INDEX_NEW_HTML, index_html_path)
        else:
            msg = f"[ERROR] : {config.INDEX_TEMPLATE} does not exist"
            sys.stderr.write(msg + "\n")
            send_telegram_message(f"LIDALDI : {msg}")
            sys.exit(1)
    except Exception as e:
        err_msg = f"[ERROR] : Processing error: {e}"
        sys.stderr.write(err_msg + "\n")
        send_telegram_message(f"LIDALDI : {err_msg}")
        sys.exit(1)

if __name__ == "__main__":
    main()
