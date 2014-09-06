#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Example for how to use proxies for your scraping endeavour.

In this case, we'll use TOR.
"""

from GoogleScraper import scrape_with_config, GoogleSearchError, Proxy
from tests.utils import random_words

if __name__ == '__main__':
    # get some keywords from wikipedia

    keywords = random_words()
    # See in the config.cfg file for possible values
    config = {
        'SCRAPING': {
            'scrapemethod': 'sel',
            'keywords': '\n'.join(keywords),
            'use_own_ip': 'False' # don't use the own IP
        },
        'SELENIUM': {
            'sel_browser': 'chrome', # lets be invisible here
            'num_browser_instances': '5',
        },
        'GLOBAL': {
            'do_caching': 'True',
            'debug': 'INFO',
        }
    }

    proxies = [
        Proxy(proto='socks5', host='localhost', port=9050, username='', password=''),
        # ... possibly other proxies that you own :>
    ]

    try:
        db = scrape_with_config(config, proxies=proxies)
        print(db.execute('SELECT * FROM link').fetchall())

        # now you have access to all results in the sqlite3 database

    except GoogleSearchError as e:
        print(e)


