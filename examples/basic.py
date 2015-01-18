# -*- coding: utf-8 -*-

from GoogleScraper import scrape_with_config, GoogleSearchError
from GoogleScraper.database import ScraperSearch

# See in the config.cfg file for possible values
config = {
    'SCRAPING': {
        'use_own_ip': 'True',
        'keyword': 'Let\'s go bubbles!',
        'search_engines': 'yandex, bing',
        'num_pages_for_keyword': 1,
        'scrapemethod': 'selenium',
    },
    'SELENIUM': {
        'sel_browser': 'chrome',
    },
    'GLOBAL': {
        'do_caching': 'False'
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
    print(serp.search_engine_name)
    print(serp.scrapemethod)
    print(serp.page_number)
    print(serp.requested_at)
    print(serp.num_results)
    # ... more attributes ...
    for link in serp.links:
        print(link)
