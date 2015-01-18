# -*- coding: utf-8 -*-

from GoogleScraper import scrape_with_config, GoogleSearchError
from GoogleScraper.database import ScraperSearch

keywords = [
    'one ',
    'two',
    'three'
]

# See in the config.cfg file for possible values
config = {
    'SCRAPING': {
        'use_own_ip': 'True',
        'keywords': '\n'.join(keywords),
        'search_engines': 'bing',
        'num_pages_for_keyword': 1,
        'scrapemethod': 'http',
    },
    'GLOBAL': {
        'do_caching': 'True'
    }
}

try:
    sqlalchemy_session = scrape_with_config(config)
except GoogleSearchError as e:
    print(e)

# let's inspect what we got
search = sqlalchemy_session.query(ScraperSearch).all()[-1]

for serp in search.serps:
    print(serp)
    for link in serp.links:
        print(link)