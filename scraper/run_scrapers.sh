#!/bin/bash

cd /path/to/scrapy || exit 1

# Activate your virtual environment if necessary
# source /path/to/venv/bin/activate

# Run ALDI and LIDL spiders sequentially (adjust the commands if needed)
scrapy crawl aldi
scrapy crawl lidl

# Run the post-processing script after both spiders finish
python /path/to/process_offers.py

# Delete images older than 90 days
find /path/to/images/folder/* -daystart -mtime +90 -delete
