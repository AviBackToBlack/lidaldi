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
        # Allow up to this fraction of items to produce logger.error entries
        # before we call the whole run failed. A single bad item should not
        # sink the pipeline.
        error_ratio_threshold = 0.1
        # Per-item drop ratio threshold. Spider callbacks that skip a
        # product (bad slug/SKU, JSON decode failure on detail, missing
        # canonical URL, etc.) increment the `lidaldi/dropped_items` stat;
        # above this fraction of the *attempted* catalogue we fail the run
        # so partial scrapes don't render a truncated site.
        dropped_ratio_threshold = 0.1

        error_count = 0
        error_ratio = 0.0
        dropped_items = 0
        dropped_ratio = 0.0

        try:
            error_count = self.crawler.stats.get_value('log_count/ERROR', 0)
            error_ratio = (error_count / self.total_items) if self.total_items else 0.0
            dropped_items = self.crawler.stats.get_value('lidaldi/dropped_items', 0)
            # Denominator = attempted items (successful + dropped). Using
            # attempted instead of total_items keeps the ratio meaningful
            # when a large fraction is dropped.
            attempted = self.total_items + dropped_items
            dropped_ratio = (dropped_items / attempted) if attempted else 0.0

            if self.total_items == 0:
                overall_result = "FAILED"
            elif self.total_items < 100:
                overall_result = "FAILED"
            elif error_ratio > error_ratio_threshold:
                overall_result = "FAILED"
            elif dropped_ratio > dropped_ratio_threshold:
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
            "error_count": error_count,
            "error_ratio": round(error_ratio, 4),
            "dropped_items": dropped_items,
            "dropped_ratio": round(dropped_ratio, 4),
            "exceptions": self.exceptions,
            "overall_result": overall_result,
        }

        with open(spider.report_file, "w") as f:
            json.dump(report, f, indent=4)

        # Emit Prometheus textfile metrics if configured.
        try:
            prom_dir = spider.crawler.settings.get("PROM_TEXTFILE_DIR")
        except Exception:
            prom_dir = None
        if prom_dir:
            try:
                import os, time, importlib.util
                # Load offers_processing/common.py by path instead of
                # mutating sys.path. Keeps the scraper process clean in
                # case common is later run in-process (tests, shell).
                proc_dir = spider.crawler.settings.get("OFFERS_PROCESSING_DIR")
                if not proc_dir:
                    raise RuntimeError("OFFERS_PROCESSING_DIR not configured")
                common_path = os.path.join(proc_dir, "common.py")
                spec = importlib.util.spec_from_file_location(
                    "lidaldi_common_for_scraper", common_path
                )
                if spec is None or spec.loader is None:
                    raise RuntimeError(f"cannot load {common_path}")
                common_mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(common_mod)
                write_prom_textfile = common_mod.write_prom_textfile
                missing_help = "Ratio of items missing a required field."
                metrics = [
                    {"name": "lidaldi_scraper_last_run_timestamp_seconds",
                     "value": int(time.time()),
                     "help": "Unix timestamp of last scraper run.",
                     "type": "gauge",
                     "labels": {"spider": spider.name}},
                    {"name": "lidaldi_scraper_status",
                     "value": 1 if overall_result == "SUCCESS" else 0,
                     "help": "1 if last scraper run succeeded, else 0.",
                     "type": "gauge",
                     "labels": {"spider": spider.name}},
                    {"name": "lidaldi_scraper_items_total",
                     "value": self.total_items,
                     "help": "Items scraped in the last run.",
                     "type": "gauge",
                     "labels": {"spider": spider.name}},
                    {"name": "lidaldi_scraper_error_count",
                     "value": error_count,
                     "help": "log_count/ERROR in the last run.",
                     "type": "gauge",
                     "labels": {"spider": spider.name}},
                    {"name": "lidaldi_scraper_dropped_items",
                     "value": dropped_items,
                     "help": "Products dropped during parsing in the last run.",
                     "type": "gauge",
                     "labels": {"spider": spider.name}},
                    {"name": "lidaldi_scraper_dropped_ratio",
                     "value": round(dropped_ratio, 4),
                     "help": "Dropped products divided by attempted products.",
                     "type": "gauge",
                     "labels": {"spider": spider.name}},
                    {"name": "lidaldi_scraper_missing_ratio",
                     "value": round(self.no_title / self.total_items, 4) if self.total_items else 0,
                     "help": missing_help,
                     "type": "gauge",
                     "labels": {"spider": spider.name, "field": "title"}},
                    {"name": "lidaldi_scraper_missing_ratio",
                     "value": round(self.no_description / self.total_items, 4) if self.total_items else 0,
                     "help": missing_help,
                     "type": "gauge",
                     "labels": {"spider": spider.name, "field": "description"}},
                    {"name": "lidaldi_scraper_missing_ratio",
                     "value": round(self.no_price / self.total_items, 4) if self.total_items else 0,
                     "help": missing_help,
                     "type": "gauge",
                     "labels": {"spider": spider.name, "field": "price"}},
                ]
                write_prom_textfile(
                    os.path.join(prom_dir, f"lidaldi_scraper_{spider.name}.prom"),
                    metrics,
                )
            except Exception as e:
                spider.logger.warning(f"Failed to write scraper metrics: {e}")
