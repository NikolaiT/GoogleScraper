#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from GoogleScraper import scrape_with_config, GoogleSearchError

keywords = [
    'apple ',
    'peach',
    'incolumitas.com'
]

# See in the config.cfg file for possible values
config = {
        'use_own_ip': True,
        'keywords': keywords,
        'search_engines': ['google', 'duckduckgo'],
        'num_pages_for_keyword': 2,
        'scrape_method': 'selenium',
        # this makes scraping with browsers headless
        # and quite fast.
        'sel_browser': 'phantomjs',
}

try:
    search = scrape_with_config(config)
except GoogleSearchError as e:
    print(e)

# let's inspect what we got. Get the last search:

for serp in search.serps:
    print(serp)
    for link in serp.links:
        print(link)