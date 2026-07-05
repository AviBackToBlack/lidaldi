# Scrapy settings for lidaldi project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html
#
# Operator-tunable values (paths, delays, image URLs) come from config.toml
# via offers_processing/config_loader.py (T9). Copy this file to settings.py;
# only Scrapy-internal tuning should need editing here.

import importlib.util
import os


def _get_lidaldi_config():
    """Load the shared LIDALDI config via offers_processing/config_loader.py.

    Looks for the loader relative to this file (repo checkout layout) or in
    $LIDALDI_PROCESSING_DIR (deployed layout where scraper/ and
    offers_processing/ live apart).
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.environ.get("LIDALDI_PROCESSING_DIR"),
        os.path.join(here, "..", "..", "offers_processing"),
    ]
    for directory in candidates:
        if not directory:
            continue
        path = os.path.join(directory, "config_loader.py")
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location("lidaldi_config_loader", path)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"cannot load {path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.get_config()
    raise RuntimeError(
        "config_loader.py not found; set LIDALDI_PROCESSING_DIR to the "
        "directory containing offers_processing/config_loader.py"
    )


_cfg = _get_lidaldi_config()

BOT_NAME = "lidaldi"

SPIDER_MODULES = ["lidaldi.spiders"]
NEWSPIDER_MODULE = "lidaldi.spiders"


# Crawl responsibly by identifying yourself (and your website) on the user-agent
#USER_AGENT = "lidaldi (+http://www.yourdomain.com)"

# Obey robots.txt rules
#
# Deliberately disabled. The ALDI.IE and LIDL.IE robots.txt files disallow
# generic bots from most product listing paths, but this scraper is not a
# generic crawler:
#   - It only fetches the non-food category endpoints used to render the
#     public site, at a strict one-request-per-3-seconds cadence (see
#     DOWNLOAD_DELAY below).
#   - It runs once per day from a single IP.
#   - It hits public, non-authenticated, non-transactional pages only.
# See the "Important Notice for ALDI.IE and LIDL.IE Representatives" section
# in README.md for the full rationale. If you fork this project for a
# different data source, reconsider this setting.
ROBOTSTXT_OBEY = False

# Configure maximum concurrent requests performed by Scrapy (default: 16)
#CONCURRENT_REQUESTS = 32

# Configure a delay for requests for the same website (default: 0)
# See https://docs.scrapy.org/en/latest/topics/settings.html#download-delay
# See also autothrottle settings and docs
DOWNLOAD_DELAY = _cfg.DOWNLOAD_DELAY
# The download delay setting will honor only one of:
#CONCURRENT_REQUESTS_PER_DOMAIN = 16
#CONCURRENT_REQUESTS_PER_IP = 16

# Disable cookies (enabled by default)
#COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
#TELNETCONSOLE_ENABLED = False

# Override the default request headers:
#DEFAULT_REQUEST_HEADERS = {
#    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
#    "Accept-Language": "en",
#}

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
#SPIDER_MIDDLEWARES = {
#    "lidaldi.middlewares.LidaldiSpiderMiddleware": 543,
#}

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#DOWNLOADER_MIDDLEWARES = {
#    'first_bot.middlewares.FirstBotDownloaderMiddleware': 543,
#}

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
#EXTENSIONS = {
#    "scrapy.extensions.telnet.TelnetConsole": None,
#}

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
    "scrapy.pipelines.images.ImagesPipeline": 1,
    'lidaldi.pipelines.ErrorCheckingPipeline': 300,
}

# Enable and configure the AutoThrottle extension (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
AUTOTHROTTLE_ENABLED = True
# The initial download delay
AUTOTHROTTLE_START_DELAY = 5
# The maximum download delay to be set in case of high latencies
AUTOTHROTTLE_MAX_DELAY = 60
# The average number of requests Scrapy should be sending in parallel to
# each remote server
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
# Enable showing throttling stats for every response received:
#AUTOTHROTTLE_DEBUG = False

# Enable and configure HTTP caching (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#httpcache-middleware-settings
#HTTPCACHE_ENABLED = True
#HTTPCACHE_EXPIRATION_SECS = 0
#HTTPCACHE_DIR = "httpcache"
#HTTPCACHE_IGNORE_HTTP_CODES = []
#HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"

# Set settings whose default value is deprecated to a future-proof value
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

# ImagesPipeline configuration
IMAGES_STORE = _cfg.IMAGES_STORE
IMAGES_EXPIRES = _cfg.IMAGES_EXPIRES

# Feeds configuration
FEEDS = {
    os.path.join(_cfg.OFFERS_PROCESSING_DIR, "%(name)s_offers.json"): {
        'format': 'json',
        'encoding': 'utf8',
        'store_empty': False,
        'fields': None,
        'indent': 4,
        'overwrite': True,
    },
}

# Scraping report folder path
SCRAPING_REPORT_DIR = _cfg.SCRAPING_REPORT_DIR

# Directory containing offers_processing/common.py. The pipeline imports it
# dynamically to write Prometheus textfile metrics using the same helper the
# other scripts use, so bumping the metric format only needs to happen in
# one place.
OFFERS_PROCESSING_DIR = _cfg.OFFERS_PROCESSING_DIR

# Prometheus textfile exporter directory. Set to the directory watched by
# node_exporter's textfile collector (typically
# /var/lib/prometheus/node-exporter). Leave as None to disable metric
# emission from the pipeline.
PROM_TEXTFILE_DIR = _cfg.PROM_TEXTFILE_DIR

# ALDI & LIDL default images
ALDI_NO_IMAGE_URL = _cfg.ALDI_NO_IMAGE_URL
LIDL_NO_IMAGE_URL = _cfg.LIDL_NO_IMAGE_URL
