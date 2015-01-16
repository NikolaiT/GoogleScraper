# -*- coding: utf-8 -*-

import logging

from GoogleScraper.utils import chunk_it
from GoogleScraper.config import Config

logger = logging.getLogger('GoogleScraper')

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
mandatory key: The 'keyword'.
"""

def get_scrape_jobs(keywords, search_engines, scrapemethod, num_pages, all_pages=True):
    """Yield the elements that define a scrape job."""
    for query in keywords:
        for search_engine in search_engines:
            if all_pages:
                for page_number in range(1, num_pages+1):
                    yield (query, search_engine, scrapemethod, page_number)
            else:
                yield (query, search_engine, scrapemethod, num_pages)


def assign_elements_to_scrapers(elements, proxies):
    """Scrapers are threads or asynchronous objects.

    Splitting the elements to scrape equally on the workers is crucial
    for maximal performance.

    A SearchEngineScrape worker consumes:
        - One or more keywords.
        - A single proxy/ip address.
        - One or more pages.
        - A single search engine name.

    It is important to see that the one connection can scrape all the
    search engines simultaneously. Therefore we need to spread the load
    evenly on such a data structure:

    {
        'connection1': {
            'search_engine1': [
                # the first worker
                {
                    keywords: ...
                    num_pages: ...
                },
                # the second worker
                {
                    keywords: ...
                    num_pages: ...
                },
            ],
            'search_engine2': [
                # the first worker
                {
                    keywords: ...
                    num_pages: ...
                },
                # the second worker
                {
                    keywords: ...
                    num_pages: ...
                },
            ],
            ...
        },
        'connection2': {
            'search_engine1': [
                # the first worker
                {
                    keywords: ...
                    num_pages: ...
                },
                # the second worker
                {
                    keywords: ...
                    num_pages: ...
                },
            ],
        }
    }

    But if num_workers is bigger than 1 (This means that an connection may
    scrape more than one request at the same time on a search engine), the value
    of the search_engine keys is a list of
    {
        keywords: ...
        num_pages: ...
    }
    elements.


    Args:
        elements: All elements to scrape
        proxies: All available connection.s

    Returns:
        The above depicted data structure.
    """
    num_workers = Config['SCRAPING'].getint('num_workers', 1)

    # if len(elements) > num_workers:
    #     groups = chunk_it(elements, num_workers)
    # else:
    #     groups = [[e, ] for e in elements]
    #
    # return groups
    import pprint

    d = {proxy: {} for proxy in proxies}

    last_worker = 0

    for query, search_engine, scrapemethod, page_number in elements:

        for proxy, data in d.items():

            if not search_engine in d[proxy]:
                 d[proxy][search_engine] = []

            if not d[proxy][search_engine]:
                for worker in range(num_workers):
                    d[proxy][search_engine].append({
                        'keywords': set(),
                        'num_pages': page_number
                    })

            try:
                d[proxy][search_engine][last_worker]['keywords'].add(query)
                d[proxy][search_engine][last_worker]['num_pages'] = page_number
            except (KeyError, IndexError) as e:
                pass

            last_worker = (last_worker + 1) % num_workers


    return d