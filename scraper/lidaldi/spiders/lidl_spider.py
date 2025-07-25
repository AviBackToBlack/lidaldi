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
    allowed_domains = ["lidl.ie", "imgproxy-retcat.assets.schwarz"]
    start_urls = ["https://www.lidl.ie/"]
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
        category_links = response.css("a.AHeroStageItems__Item--Wrapper::attr(href)").getall()
        for link in category_links:
            if "/c/" in link:
                self.logger.info(f"Following category: {link}")
                yield response.follow(link, self.parse_category)

    def parse_category(self, response):
        product_links = response.css("div.AProductGridbox__GridTilePlaceholder::attr(canonicalpath)").getall()
        for link in product_links:
            if "/p/" in link:
                cleared_link = self.remove_query(response.urljoin(link))
                self.logger.info(f"Following product: {cleared_link}")
                yield response.follow(cleared_link, self.parse_product)

    def parse_product(self, response):
        description_soup = None
        ld_json_text = response.xpath("//script[@type='application/ld+json']/text()").get()
        if ld_json_text:
            try:
                ld_data = json.loads(ld_json_text)
                if isinstance(ld_data, dict) and "description" in ld_data:
                    description_soup = BeautifulSoup(ld_data["description"], "html.parser")
                else:
                    self.logger.warning("ld+json does not contain description.")
            except Exception as e:
                self.logger.error(f"Error parsing ld+json: {e}")
        else:
            self.logger.error("No ld+json script found on the page.")

        image_url = response.css("img.media-carousel-item__item::attr(src)").get(default="").strip()
        if not image_url:
            image_url = self.no_image_url
        image_urls = [image_url] if image_url else []

        scraped_at_val = self.old_offers_map.get(response.url, int(time.time()))
        yield {
            "store": "LIDL",
            "url": response.url,
            "scraped_at": scraped_at_val,
            "category": response.xpath('//nav[@aria-labelledby="heading-breadcrumbs"]//li[last()]//span[@itemprop="name"]/text()').get(default="No category").strip(),
            "title": response.css("h1[data-qa-label='keyfacts-title']::text").get(default="No title").strip(),
            "description": (
                re.sub(r'\s*\n\s*', '\n', description_soup.get_text(separator="\n")).strip() if (description_soup) else "No description"
            ),
            "store_availability": response.css("h3.availability.availability--blue::text").get(default="Unknown").strip(),
            "price": (
                re.sub(r"[^\d.]", "", price) if (price := response.css("div.ods-price__value::text").get()) else "N/A"
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
