# -*- coding: utf-8 -*-

from GoogleScraper import scrape_with_config, GoogleSearchError
from GoogleScraper.database import ScraperSearch
from GoogleScraper.utils import get_some_words

keywords = get_some_words(50)
with open('keywords.txt', 'wt') as f:
    for word in keywords:
        f.write(word + '\n')

# See in the config.cfg file for possible values
config = {
    'SCRAPING': {
        'use_own_ip': 'True',
        'keyword_file': 'keywords.txt',
        'search_engines': 'bing,duckduckgo',
        'num_pages_for_keyword': 2,
        'scrapemethod': 'http-async',
    },
    'GLOBAL': {
        'verbosity': 3,
        'do_caching': 'True'
    },
    'OUTPUT': {
        'output_filename': 'out.csv'
    }
}

try:
    sqlalchemy_session = scrape_with_config(config)
except GoogleSearchError as e:
    print(e)

# let's inspect what we got. Get the last search:

search = sqlalchemy_session.query(ScraperSearch).all()[-1]

for serp in search.serps:
    print(serp)
    for link in serp.links:
        print(link)