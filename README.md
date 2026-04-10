# LidAldi

[![Website](https://img.shields.io/badge/Live%20Site-Visit-blue)](https://lidaldi.neit.me/)

LidAldi aggregates special offers from ALDI.IE and LIDL.IE. The project includes a Scrapy-based scraper, an offers processing pipeline, a sync server for cross-device state, push notifications for deal alerts, and a static website for browsing the combined deals.

## Features

- **Aggregated Offers:** Non-food special offers from both ALDI.IE and LIDL.IE in one place, updated daily.
- **LidlPlus Pricing:** LIDL offers display the LidlPlus member price when available.
- **Cross-Device Sync:** Generate a short sync code to keep your last-visit timestamp and alerts in sync across all your devices.
- **Deal Alerts:** Create keyword-based alerts (exact phrase, all words, or any word matching). When new offers match your alerts, you receive a Web Push notification linking directly to the product page.
- **"New from Last Visit":** Items added since your last visit are highlighted, with the timestamp synced across devices.

## Important Notice for ALDI.IE and LIDL.IE Representatives

We respectfully request that you consider the following before taking any measures to block our scraper:

- **Respectful Scraping:** The scraper is configured to operate in a highly respectful manner, incorporating significant delays between requests to minimize server impact.
- **Limited Frequency:** It runs only once per day, ensuring that your systems are not overloaded.
- **No Price Comparison:** The website is not designed to compare prices on similar products.
- **Mutual Benefit:** The goal of the website is to stimulate product purchases, which in turn generates revenue. Please consider the benefits before opting to block the scraper.

Thank you for your understanding.

## Requirements

- **BeautifulSoup4:** ≥ 4.13.4
- **Pillow:** ≥ 11.1.0
- **pywebpush:** ≥ 2.0.0
- **Python:** ≥ 3.9
- **Scrapy:** ≥ 2.12.0
- **Operating system:** Linux / BSD / macOS. The sync server and
  `send_notifications.py` use `fcntl.flock` for cross-process locking and
  **will not run on Windows**. The scraper and `process_offers.py` are
  portable, but the full production pipeline (sync + push notifications)
  targets POSIX only.

## Project Structure

```
scraper/                    Scrapy project (ALDI + LIDL spiders)
offers_processing/
  config.sample.py          Configuration template
  common.py                 Shared helpers (logging, Telegram, Prometheus, MarkdownV2)
  sync_store.py             Cross-process locked JSON store for sync profiles (POSIX-only)
  process_offers.py         Merges offers, generates new_offers.json & index.html
  send_notifications.py     Sends Web Push notifications for matched alerts
  sync_server.py            HTTP API for cross-device sync
  generate_vapid_keys.py    VAPID key pair generator for Web Push
website/
  index.html.tpl            HTML template (rendered by process_offers.py)
  js/lidaldi.js             Client-side app (filtering, sync, alerts modal)
  css/lidaldi.css            Styles
  sw.js                     Service Worker for push notifications
nginx/
  lidaldi-sync-proxy.conf   Nginx reverse proxy snippet for the sync API
systemd/
  lidaldi-sync.service      systemd unit for the sync server
```

## Installation

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/AviBackToBlack/lidaldi.git
   ```

2. **Create the System User:**

   ```bash
   sudo useradd -M -s /usr/sbin/nologin lidaldi
   ```

3. **Create Folders:**

   ```bash
   sudo mkdir -p /opt/lidaldi/data
   sudo mkdir -p /opt/lidaldi/offers_processing/sync
   ```

4. **Deploy Code:**

   - Copy the `scraper/`, `offers_processing/` folders to `/opt/lidaldi`.
   - For the offers processing script, copy the sample config:
     ```bash
     cp /opt/lidaldi/offers_processing/config.sample.py /opt/lidaldi/offers_processing/config.py
     ```
     Then edit `config.py` with your values (paths, Telegram token, sync settings, VAPID keys).
   - For the Scrapy project, copy the sample settings:
     ```bash
     cp /opt/lidaldi/scraper/lidaldi/settings.sample.py /opt/lidaldi/scraper/lidaldi/settings.py
     ```
     Then edit `settings.py` accordingly.
   - Populate `/opt/lidaldi/scraper/run_scrapers.sh` with the correct paths.
   - Set permissions:
     ```bash
     sudo chown -R lidaldi:lidaldi /opt/lidaldi
     ```

5. **Install Requirements:**

   ```bash
   pip install -r requirements.txt
   ```

6. **Generate VAPID Keys (for push notifications):**

   ```bash
   python /opt/lidaldi/offers_processing/generate_vapid_keys.py /opt/lidaldi/offers_processing
   ```

   This creates `vapid_private.pem` and prints the public key. Add both to `config.py`.

   **Lock down the private key** — it is a long-lived signing credential;
   anyone who reads it can forge push messages to every subscriber:

   ```bash
   sudo chown lidaldi:lidaldi /opt/lidaldi/offers_processing/vapid_private.pem
   sudo chmod 600 /opt/lidaldi/offers_processing/vapid_private.pem
   ```

7. **Optional: Prometheus textfile metrics.**

   `process_offers.py`, `send_notifications.py`, and the Scrapy pipeline can
   emit `.prom` files for the node_exporter textfile collector. Set
   `PROM_TEXTFILE_DIR` in both `offers_processing/config.py` and
   `scraper/lidaldi/settings.py` to the collector directory (typically
   `/var/lib/prometheus/node-exporter`) and ensure it is writable by the
   `lidaldi` user. Leave it as `None` to disable. The systemd unit's
   `ReadWritePaths=` must include this directory if you enable it.

## Sync Server Setup

The sync server is a zero-dependency Python HTTP server that handles cross-device synchronization.

1. **Configure Nginx** — add the reverse proxy snippet from `nginx/lidaldi-sync-proxy.conf` to your site's Nginx config (inside the HTTPS server block, before any deny-all rules):

   ```nginx
   location /api/sync/ {
       proxy_pass http://127.0.0.1:8099;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
       client_max_body_size 10k;
   }
   ```

2. **Install the systemd service:**

   ```bash
   sudo cp systemd/lidaldi-sync.service /etc/systemd/system/
   ```

   Edit the service file to set the correct paths, then:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now lidaldi-sync
   ```

   The unit ships hardened (`NoNewPrivileges`, `ProtectSystem=strict`,
   `MemoryDenyWriteExecute`, a restrictive `SystemCallFilter`, etc.). The
   only writable path is `ReadWritePaths=/opt/lidaldi/offers_processing/sync`
   — if you point `SYNC_DIR` somewhere else, or enable `PROM_TEXTFILE_DIR`,
   you **must** add the corresponding directory to `ReadWritePaths=` or the
   service will fail to write its state.

## Logging & Scheduling

1. **Set Up Logging:**

   ```bash
   sudo mkdir -p /var/log/lidaldi
   sudo chown -R lidaldi:lidaldi /var/log/lidaldi
   sudo chmod 0755 /var/log/lidaldi
   ```

2. **Configure Logrotate:**

   Copy the provided `logrotate.d/lidaldi` file to `/etc/logrotate.d/lidaldi` and update the log path if necessary.

3. **Set Up Cron Jobs:**

   Copy the provided `cron.d/lidaldi` file to `/etc/cron.d/lidaldi` and populate it as needed. The cron chain runs: spiders → `process_offers.py` → `send_notifications.py`.

## Website Deployment

1. **Set Permissions:**

   ```bash
   sudo mkdir -p /var/www/lidaldi
   sudo chown -R root:www-data /var/www/lidaldi
   sudo chown lidaldi:www-data /var/www/lidaldi
   sudo chown lidaldi:www-data /var/www/lidaldi/index.html
   sudo chown lidaldi:www-data /var/www/lidaldi/img/full
   ```

2. **Deploy static assets** (`css/`, `js/`, `sw.js`, `404.html`) to the website root.

## Push Notifications

Push notifications require HTTPS and a browser that supports the Web Push API (Chrome, Firefox, Edge). Safari on iOS supports Web Push when the site is added to the Home Screen.

The notification flow:
1. User creates alerts in the on-page modal and enables notifications.
2. The daily cron runs both spiders, then `process_offers.py` generates `new_offers.json`.
3. `send_notifications.py` matches new offers against all users' alerts and sends Web Push notifications.
4. Clicking a notification opens the product page on aldi.ie or lidl.ie.

🔗 **Live Website:** [https://lidaldi.neit.me/](https://lidaldi.neit.me/)

---
*Enjoy special offers!*
