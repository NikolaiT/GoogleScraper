#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from GoogleScraper import scrape_with_config, GoogleSearchError
from GoogleScraper.utils import get_some_words

keywords = get_some_words(10)
with open('keywords.txt', 'wt') as f:
    for word in keywords:
        f.write(word + '\n')

# See in the config.cfg file for possible values
config = {
    'use_own_ip': True,
    'keyword_file': 'keywords.txt',
    'search_engines': ['bing', 'duckduckgo'],
    'num_pages_for_keyword': 2,
    'scrape_method': 'http-async',
    'do_caching': True,
    'output_filename': 'out.csv',
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
