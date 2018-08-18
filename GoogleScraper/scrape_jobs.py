# -*- coding: utf-8 -*-

import logging

logger = logging.getLogger(__name__)

"""
The core logic of GoogleScraper is handled here.

By default, every keyword is scraped on all given search engines for the supplied
number of pages.

Example:

keywords = ('one', 'two')
search_eninges = ('google, 'yandex')
num_pages = 5

Then the following requests are issued:

[('one', 'google', 0),
 ('one', 'google', 1),
 ('one', 'google', 2),
 ('one', 'google', 3),
 ('one', 'google', 4),
 ('one', 'yandex', 0),
 ('one', 'yandex', 1),
 ('one', 'yandex', 2),
 ('one', 'yandex', 3),
 ('one', 'yandex', 4),
 ('two', 'google', 0),
 ('two', 'google', 1),
 ('two', 'google', 2),
 ('two', 'google', 3),
 ('two', 'google', 4),
 ('two', 'yandex', 0),
 ('two', 'yandex', 1),
 ('two', 'yandex', 2),
 ('two', 'yandex', 3),
 ('two', 'yandex', 4)]

But sometimes you want to fine tune this generic behaviour. Some keywords should be scraped on
only some search engines. Some keywords should be only used with specific proxies. Maybe
a specific keyword should be searched Y times, whereas another needs to be scraped X times.

Therefore we need am special format, where you can specify the single settings for each
keyword.

The best format for such a keyword file is just a python module with a dictionary with one
mandatory key: The 'query'. The dictionary must be called 'scrape_jobs'.

You can see such a example file in the examples/ directory.
"""


def default_scrape_jobs_for_keywords(keywords, search_engines, scrape_method, num_pages):
    """Get scrape jobs by keywords.

    If you just submit a keyword file, then it is assumed that every keyword
    should be scraped on
    - all supplied search engines
    - for num_pages
    - in the specified search mode.

    Args:
        keywords: A set of keywords to scrape.

    Returns:
        A dict of scrapejobs.
    """
    for keyword in keywords:
        for search_engine in search_engines:
            for page in range(1, num_pages + 1):
                yield {
                    'query': keyword,
                    'search_engine': search_engine,
                    'scrape_method': scrape_method,
                    'page_number': page
                }