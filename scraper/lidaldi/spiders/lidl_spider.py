import json
import os
import re
import scrapy
import time
from bs4 import BeautifulSoup
from scrapy import signals
from urllib.parse import urlparse, urlunparse

class LidlSpider(scrapy.Spider):
    name = "lidl"
    allowed_domains = ["lidl.ie", "imgproxy-retcat.assets.schwarz", "lidaldi.neit.me"]
    search_api_url = "https://www.lidl.ie/q/api/search?assortment=IE&locale=en_IE&version=2.1.0"
    search_api_fetchsize = 108
    start_urls = [search_api_url]
    no_image_url = ""

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(LidlSpider, cls).from_crawler(crawler, *args, **kwargs)
        report_folder = crawler.settings.get('SCRAPING_REPORT_DIR')
        spider.no_image_url = crawler.settings.get('LIDL_NO_IMAGE_URL')
        spider.report_file = os.path.join(report_folder, f"{spider.name}_scraping_report.json")
        spider.offers_file = os.path.join(report_folder, f"{spider.name}_offers.json")
        spider.load_old_offers()
        crawler.signals.connect(spider.handle_spider_error, signal=signals.spider_error)
        return spider

    def load_old_offers(self):
        self.old_offers_map = {}
        if os.path.exists(self.offers_file):
            try:
                with open(self.offers_file, "r") as f:
                    old_data = json.load(f)
                for offer in old_data:
                    url = offer.get("url")
                    scraped_at = offer.get("scraped_at")
                    if url and scraped_at:
                        self.old_offers_map[url] = scraped_at
            except Exception as e:
                self.logger.error(f"Error reading old offers file: {e}")
            try:
                os.remove(self.offers_file)
            except Exception as e:
                self.logger.error(f"Error removing old offers file: {e}")

    def parse(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode failed on search API: {e}")
            return

        for facet in (payload.get("facets") or []):
            if facet.get("code") != "category":
                continue
            all_values = (facet.get("topvalues") or []) + (facet.get("values") or [])
            for value in all_values:
                label = value.get("label") or ""
                cat_id = value.get("value") or ""
                if not label or not cat_id or label == "Food & Drink":
                    continue
                self.logger.info(f"Found non-food category: {label} (id={cat_id})")
                api_url = (
                    f"{self.search_api_url}"
                    f"&fetchsize={self.search_api_fetchsize}&offset=0"
                    f"&category.id={cat_id}"
                )
                yield response.follow(
                    api_url, self.parse_category_api,
                    meta={"category_label": label, "category_id": cat_id},
                    dont_filter=True,
                )
            break

    def parse_category_api(self, response):
        category_label = response.meta["category_label"]
        category_id = response.meta["category_id"]

        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode failed on category API: {e}")
            return

        items = payload.get("items") or []
        num_found = payload.get("numFound") or 0
        offset = payload.get("offset") or 0
        fetchsize = payload.get("fetchsize") or self.search_api_fetchsize

        self.logger.info(
            f"Category '{category_label}': got {len(items)} items "
            f"(offset={offset}, total={num_found})"
        )

        for item in items:
            gridbox_data = (item.get("gridbox") or {}).get("data") or {}
            if gridbox_data.get("category") == "Food":
                continue

            canonical_url = gridbox_data.get("canonicalUrl") or ""
            if not canonical_url:
                self.logger.warning(
                    f"No canonicalUrl for item: {gridbox_data.get('fullTitle')}"
                )
                continue

            product_url = f"https://www.lidl.ie{canonical_url}"
            title = gridbox_data.get("fullTitle") or "No title"
            price_data = gridbox_data.get("price") or {}
            raw_price = price_data.get("price")
            price = str(raw_price) if raw_price is not None else "N/A"
            image_url = gridbox_data.get("image") or self.no_image_url
            stock_avail = gridbox_data.get("stockAvailability") or {}
            badge_info = stock_avail.get("badgeInfo") or {}
            badges = badge_info.get("badges") or []
            store_availability = (
                (badges[0].get("text") or "Unknown") if badges else "Unknown"
            )

            yield response.follow(
                product_url, self.parse_product,
                meta={
                    "product_url": product_url,
                    "category": category_label,
                    "title": title,
                    "price": price,
                    "image_url": image_url,
                    "store_availability": store_availability,
                },
            )

        next_offset = offset + fetchsize
        if next_offset < num_found:
            api_url = (
                f"{self.search_api_url}"
                f"&fetchsize={self.search_api_fetchsize}&offset={next_offset}"
                f"&category.id={category_id}"
            )
            yield response.follow(
                api_url, self.parse_category_api,
                meta={"category_label": category_label, "category_id": category_id},
                dont_filter=True,
            )

    def parse_product(self, response):
        product_url = response.meta["product_url"]
        description = "No description"
        ld_json_text = response.xpath("//script[@type='application/ld+json']/text()").get()
        if ld_json_text:
            try:
                ld_data = json.loads(ld_json_text)
                if isinstance(ld_data, dict) and "description" in ld_data:
                    description_soup = BeautifulSoup(
                        ld_data["description"], "html.parser"
                    )
                    description = re.sub(
                        r'\s*\n\s*', '\n',
                        description_soup.get_text(separator="\n"),
                    ).strip()
                else:
                    self.logger.warning("ld+json does not contain description.")
            except Exception as e:
                self.logger.error(f"Error parsing ld+json: {e}")
        else:
            self.logger.error("No ld+json script found on the page.")

        if not description:
            description = "No description"

        image_url = response.meta.get("image_url", "")
        image_urls = [image_url] if image_url else []
        scraped_at_val = self.old_offers_map.get(product_url, int(time.time()))

        yield {
            "store": "LIDL",
            "url": product_url,
            "scraped_at": scraped_at_val,
            "category": response.meta.get("category", "No category"),
            "title": response.meta.get("title", "No title"),
            "description": description,
            "store_availability": response.meta.get("store_availability", "Unknown"),
            "price": response.meta.get("price", "N/A"),
            "image_urls": image_urls,
        }

    def remove_query(self, url: str) -> str:
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))

    def handle_spider_error(self, failure, response, spider):
        self.logger.error(f"Error processing {response.url}: {failure}")

    def closed(self, reason):
        self.logger.info(f"Spider closed: {reason}")
