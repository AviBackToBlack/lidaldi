# LidAldi

[![Website](https://img.shields.io/badge/Live%20Site-Visit-blue)](https://lidaldi.neit.me/)

LidAldi aggregates special offers from ALDI.IE and LIDL.IE. The project includes a Scrapy-based scraper, an offers processing script, and a website for displaying the combined deals.

## Important Notice for ALDI.IE and LIDL.IE Representatives

We respectfully request that you consider the following before taking any measures to block our scraper:

- **Respectful Scraping:** The scraper is configured to operate in a highly respectful manner, incorporating significant delays between requests to minimize server impact.
- **Limited Frequency:** It runs only once per day, ensuring that your systems are not overloaded.
- **No Price Comparison:** The website is not designed to compare prices on similar products.
- **Mutual Benefit:** The goal of the website is to stimulate product purchases, which in turn generates revenue. Please consider the benefits before opting to block the scraper.

Thank you for your understanding.

## Requirements

- **Python:** ≥ 3.9  
- **Pillow:** 11.1.0  
- **Scrapy:** 2.12.0  

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
   ```

4. **Deploy Code:**

   - Copy the `scraper/` and `offers_processing/` folders to `/opt/lidaldi`.
   - For the offers processing script, copy the sample config:
     ```bash
     cp /opt/lidaldi/offers_processing/config.sample.py /opt/lidaldi/offers_processing/config.py
     ```
     Then edit `config.py` with your values.
   - For the Scrapy project, copy the sample settings:
     ```bash
     cp /opt/lidaldi/scraper/lidaldi/settings.sample.py /opt/lidaldi/scraper/lidaldi/settings.py
     ```
     Then edit `settings.py` accordingly.
   - Populate `/opt/lidaldi/scraper/run_scrapers.sh` as needed.
   - Set permissions:
     ```bash
     sudo chown -R lidaldi:lidaldi /opt/lidaldi
     ```
   
5. **Install Scrapy Requirements:**

   ```bash
   cd /opt/lidaldi/scraper
   sudo pip install -r requirements.txt
   ```

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

   Copy the provided `cron.d/lidaldi` file to `/etc/cron.d/lidaldi` and populate it as needed.

## Website Deployment

1. **Set Permissions:**

   ```bash
   sudo mkdir -p /var/www/lidaldi
   sudo chown -R root:www-data /var/www/lidaldi
   sudo chown lidaldi:www-data /var/www/lidaldi
   sudo chown lidaldi:www-data /var/www/lidaldi/index.html
   sudo chown lidaldi:www-data /var/www/lidaldi/img/full
   ```

🔗 **Live Website:** [https://lidaldi.neit.me/](https://lidaldi.neit.me/)  

---
*Enjoy special offers!*
