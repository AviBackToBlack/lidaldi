# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
import json


class LidaldiPipeline:
    def process_item(self, item, spider):
        return item


class ErrorCheckingPipeline:
    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls()
        pipeline.crawler = crawler
        pipeline.total_items = 0
        pipeline.no_category = 0
        pipeline.no_title = 0
        pipeline.no_description = 0
        pipeline.no_store_availability = 0
        pipeline.no_price = 0
        pipeline.empty_image_urls = 0
        pipeline.invalid_image_urls = 0
        pipeline.exceptions = []
        return pipeline

    def process_item(self, item, spider):
        self.total_items += 1
        try:
            if item.get("category", "").strip() == "No category":
                self.no_category += 1
            if item.get("title", "").strip() == "No title":
                self.no_title += 1
            if item.get("description", "").strip() == "No description":
                self.no_description += 1
            if item.get("store_availability", "").strip() == "Unknown":
                self.no_store_availability += 1
            if item.get("price", "").strip() == "N/A":
                self.no_price += 1
            image_urls = item.get("image_urls") or []
            if not image_urls or all(not url.strip() for url in image_urls):
                self.empty_image_urls += 1
            else:
                for url in image_urls:
                    if not url.startswith("http"):
                        self.invalid_image_urls += 1
        except Exception as e:
            self.exceptions.append(str(e))

        return item

    def close_spider(self, spider):
        overall_result = "SUCCESS"
        hard_threshold = 0.1
        soft_threshold = 0.5

        try:
            error_count = self.crawler.stats.get_value('log_count/ERROR', 0)

            if self.total_items < 100:
                overall_result = "FAILED"
            elif error_count > 0:
                overall_result = "FAILED"
            elif ((self.no_category / self.total_items) > hard_threshold or 
                  (self.no_title / self.total_items) > hard_threshold or 
                  (self.no_description / self.total_items) > soft_threshold or 
                  (self.no_store_availability / self.total_items) > hard_threshold or 
                  (self.no_price / self.total_items) > hard_threshold or 
                  (self.empty_image_urls / self.total_items) > hard_threshold or 
                  self.exceptions):
                overall_result = "FAILED"
        except Exception as e:
            overall_result = "FAILED"
            self.exceptions.append(str(e))

        report = {
            "total_items": self.total_items,
            "no_category": self.no_category,
            "no_title": self.no_title,
            "no_description": self.no_description,
            "no_store_availability": self.no_store_availability,
            "no_price": self.no_price,
            "empty_image_urls": self.empty_image_urls,
            "exceptions": self.exceptions,
            "overall_result": overall_result
        }

        with open(spider.report_file, "w") as f:
            json.dump(report, f, indent=4)
