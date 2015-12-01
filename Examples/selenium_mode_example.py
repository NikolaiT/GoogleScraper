#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from GoogleScraper import scrape_with_config, GoogleSearchError

keywords = [
    'alpha ',
    'beta',
    'yankee'
]

# See in the config.cfg file for possible values
config = {
    'use_own_ip': True,
    'keywords': keywords,
    'search_engines': ['baidu', 'duckduckgo'],
    'num_pages_for_keyword': 2,
    'scrape_method': 'selenium',
    'sel_browser': 'chrome',
}

try:
    search = scrape_with_config(config)
except GoogleSearchError as e:
    print(e)

for serp in search.serps:
    print(serp)
    for link in serp.links:
        print(link)