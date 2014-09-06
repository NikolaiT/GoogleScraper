#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Shows how to control GoogleScraper programmatically. Uses selenium mode.
"""

from GoogleScraper import scrape_with_config, GoogleSearchError

if __name__ == '__main__':
    # See in the config.cfg file for possible values
    config = {
        'SCRAPING': {
            'use_own_ip': 'True',
            'keyword': 'Hello World'
        },
        'SELENIUM': {
            'sel_browser': 'chrome',
            'manual_captcha_solving': 'True'
        },
        'GLOBAL': {
            'do_caching': 'True'
        }
    }

    try:
        # scrape() and scrape_with_config() will reuturn a handle to a sqlite database with the results
        db = scrape_with_config(config)

        print(db.execute('SELECT * FROM link').fetchall())

    except GoogleSearchError as e:
        print(e)


