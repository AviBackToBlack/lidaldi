import json
import os
import re
import scrapy
import time
from bs4 import BeautifulSoup
from scrapy import signals
from urllib.parse import urlparse, urlunparse

class AldiSpider(scrapy.Spider):
    name = "aldi"
    allowed_domains = ["aldi.ie", "api.aldi.ie", "dm.emea.cms.aldi.cx", "lidaldi.neit.me"]
    start_urls = ["https://www.aldi.ie/products/specialbuys"]
    product_detail_api = "https://api.aldi.ie/v2/products/{sku}?serviceType=walk-in"
    no_image_url = ""

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(AldiSpider, cls).from_crawler(crawler, *args, **kwargs)
        report_folder = crawler.settings.get('SCRAPING_REPORT_DIR')
        spider.no_image_url = crawler.settings.get('ALDI_NO_IMAGE_URL')
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
        link = None
        ld_json_text = response.xpath("//script[@type='application/ld+json']/text()").get()
        if ld_json_text:
            try:
                ld_data = json.loads(ld_json_text)
                if isinstance(ld_data, dict) and "itemListElement" in ld_data:
                    for element in ld_data["itemListElement"]:
                        if element.get("name") == "SpecialBuys":
                            link = element.get("item")
                            break
                else:
                    self.logger.error("ld+json does not contain a valid breadcrumb list.")
            except Exception as e:
                self.logger.error(f"Error parsing ld+json: {e}")
        else:
            self.logger.error("No ld+json script found on the page.")

        if link:
            self.logger.info(f"Found 'Browse All' URL: {link}")
            yield response.follow(link, self.parse_products)
        else:
            self.logger.error("No 'Browse All' URL found.")

    def parse_products(self, response):
        specialbuys_category_key = urlparse(response.url).path.rstrip("/").split("/")[-1]
        limit, offset = 30, 0
        api_url = f"https://api.aldi.ie/v3/product-search?currency=EUR&categoryKey={specialbuys_category_key}&limit={limit}&offset={offset}&getNotForSaleProducts=1&serviceType=walk-in"
        yield response.follow(api_url, self.parse_products_api, meta={"specialbuys_category_key": specialbuys_category_key, "limit": limit, "offset": offset}, dont_filter=True)

    def parse_products_api(self, response):
        specialbuys_category_key = response.meta["specialbuys_category_key"]
        limit = response.meta["limit"]
        offset = response.meta["offset"]

        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode failed on product-search: {e}")
            return

        products = payload.get("data") or []
        meta = payload.get("meta") or {}
        pagination = meta.get("pagination") or {}
        total = pagination.get("totalCount") or 0

        if total == 0:
            self.logger.error(f"Can not identify totalCount")
            return

        for item in products:
            slug_text = (item.get("urlSlugText") or "").strip()
            sku       = (item.get("sku") or "").strip()
            if not (slug_text and sku):
                self.logger.error(f"Missing slug/SKU in record: {item.get('name')}")
                continue
            product_url = f"https://www.aldi.ie/product/{slug_text}-{sku}"
            detail_api_url = self.product_detail_api.format(sku=sku)
            yield response.follow(
                detail_api_url, self.parse_product_api,
                meta={"product_url": product_url, "slug_text": slug_text},
                dont_filter=True,
            )

        next_offset = offset + limit
        if next_offset < total:
            api_url = f"https://api.aldi.ie/v3/product-search?currency=EUR&categoryKey={specialbuys_category_key}&limit={limit}&offset={next_offset}&getNotForSaleProducts=1&serviceType=walk-in"
            yield response.follow(api_url, self.parse_products_api, meta={"specialbuys_category_key": specialbuys_category_key, "limit": limit, "offset": offset + limit}, dont_filter=True)

    def parse_product_api(self, response):
        product_url = response.meta["product_url"]
        slug_text = response.meta["slug_text"]

        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode failed on product detail: {e}")
            return

        data = payload.get("data") or {}
        if not data:
            self.logger.error(f"No data in product detail response for {product_url}")
            return

        categories = data.get("categories") or []
        category = (categories[-1].get("name") or "No category") if categories else "No category"
        brand = (data.get("brandName") or "").strip()
        name = (data.get("name") or "No title").strip()
        title = f"{brand} {name}".strip() if brand else name
        raw_description = data.get("description") or ""
        description = ""
        if raw_description:
            description_soup = BeautifulSoup(raw_description, "html.parser")
            description = re.sub(
                r'\s*\n\s*', '\n',
                description_soup.get_text(separator="\n"),
            ).strip()
        if not description:
            description = "No description"
        price_data = data.get("price") or {}
        price_display = price_data.get("amountRelevantDisplay") or ""
        price = re.sub(r"[^\d.]", "", price_display) if price_display else "N/A"
        store_availability = (data.get("onSaleDateDisplay") or "Unknown").strip()
        scraped_at_val = self.old_offers_map.get(product_url, int(time.time()))

        image_url = ""
        assets = data.get("assets") or []
        if assets:
            raw_url = assets[0].get("url") or ""
            if raw_url:
                image_url = raw_url.replace("{width}", "306").replace("{slug}", slug_text)
        if not image_url:
            image_url = self.no_image_url
        image_urls = [image_url] if image_url else []

        yield {
            "store": "ALDI",
            "url": product_url,
            "scraped_at": scraped_at_val,
            "category": category,
            "title": title,
            "description": description,
            "store_availability": store_availability,
            "price": price,
            "image_urls": image_urls,
        }

    def remove_query(self, url: str) -> str:
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))

    def handle_spider_error(self, failure, response, spider):
        self.logger.error(f"Error processing {response.url}: {failure}")

    def closed(self, reason):
        self.logger.info(f"Spider closed: {reason}")
