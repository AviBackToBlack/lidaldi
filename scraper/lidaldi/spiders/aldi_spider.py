import json
import os
import re
import scrapy
import time
from scrapy import signals
from urllib.parse import urlparse, urlunparse


class AldiSpider(scrapy.Spider):
    name = "aldi"
    allowed_domains = ["aldi.ie", "dm.emea.cms.aldi.cx"]
    start_urls = ["https://www.aldi.ie/products/specialbuys"]
    no_image_url = "";

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
        product_links = response.css("a.product-tile__link::attr(href)").getall()
        for link in product_links:
            cleared_link = self.remove_query(link)
            self.logger.info(f"Following product: {cleared_link}")
            yield response.follow(cleared_link, self.parse_product)

        next_page = response.css("a.base-pagination__arrow[data-test='next-page']::attr(href)").get()
        if next_page:
            yield response.follow(next_page, self.parse_products)

    def parse_product(self, response):
        image_url = response.css("img.base-image[fetchpriority='high']::attr(src)").get(default="").strip()
        if not image_url:
            image_url = self.no_image_url
        image_urls = [image_url] if image_url else []

        scraped_at_val = self.old_offers_map.get(response.url, int(time.time()))
        yield {
            "store": "ALDI",
            "url": response.url,
            "scraped_at": scraped_at_val,
            "category" : response.xpath('//nav[@aria-label="Breadcrumb"]/a[last()]/text()').get(default="No category").strip(),
            "title": response.css("h1.product-details__title::text").get(default="No title").strip(),
            "description": "\n".join(response.css("div.product-details__information div.base-rich-text.p360-richtext *::text").getall()).strip() or "No description",
            "store_availability": response.css("div.injection-product-details-on-sale-date-display::text").get(default="Unknown").strip(),
            "price": (
                re.sub(r"[^\d.]", "", price) if (price := response.css("span.base-price__regular span::text").get()) else "N/A"
            ),
            "image_urls": image_urls,
        }

    def remove_query(self, url: str) -> str:
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))

    def handle_spider_error(self, failure, response, spider):
        self.logger.error(f"Error processing {response.url}: {failure}")

    def closed(self, reason):
        self.logger.info(f"Spider closed: {reason}")
