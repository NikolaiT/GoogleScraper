#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Example for how to scrape with http mode. This mode isn't quite as sophisticated as selenium mode.
"""

from GoogleScraper import scrape_with_config, GoogleSearchError

if __name__ == '__main__':
    # See in the config.cfg file for possible values
    config = {
        'SCRAPING': {
            'keyword': 'python sucks',
            'scrapemethod': 'http'
        },
        'SELENIUM': {
            'sel_browser': 'chrome',
            'manual_captcha_solving': 'True'
        },
        'GLOBAL': {
            'do_caching': 'True',
            'debug': '10',
        }
    }

    try:
        # scrape() and scrape_with_config() will return a handle to a sqlite database with the results
        db = scrape_with_config(config)
        print(db.execute('SELECT * FROM link').fetchall())

    except GoogleSearchError as e:
        print(e)


