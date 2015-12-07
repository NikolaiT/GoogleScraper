# -*- coding: utf-8 -*-

import datetime
import random
import time
import os
import abc

from GoogleScraper.proxies import Proxy
from GoogleScraper.database import db_Proxy
from GoogleScraper.output_converter import store_serp_result
from GoogleScraper.parsing import get_parser_by_search_engine, parse_serp
import logging

logger = logging.getLogger(__name__)

SEARCH_MODES = ('http', 'selenium', 'http-async')


class GoogleSearchError(Exception):
    pass


class InvalidNumberResultsException(GoogleSearchError):
    pass


class MaliciousRequestDetected(GoogleSearchError):
    pass


class SeleniumMisconfigurationError(Exception):
    pass


class SeleniumSearchError(Exception):
    pass


class StopScrapingException(Exception):
    pass


"""
GoogleScraper should be as robust as possible.

There are several conditions that may stop the scraping process. In such a case,
a StopScrapingException is raised with the reason.

Important events:

- All proxies are detected and we cannot request further keywords => Stop.
- No internet connection => Stop.

- If the proxy is detected by the search engine we try to get another proxy from the pool and we
  call switch_proxy() => continue.

- If the proxy is detected by the search engine and there is no other proxy in the pool, we wait
  {search_engine}_proxy_detected_timeout seconds => continue.
    + If the proxy is detected again after the waiting time, we discard the proxy for the whole scrape.
"""


def get_base_search_url_by_search_engine(config, search_engine_name, search_mode):
    """Retrieves the search engine base url for a specific search_engine.

    This function cascades. So base urls will
    be overwritten by search_engine urls in the specific mode sections.
    On the other side, if a search engine has no special url in it' corresponding
    mode, the default one from the SCRAPING config section will be loaded.

    Args:
        search_engine_name The name of the search engine
        search_mode: The search mode that is used. selenium or http or http-async

    Returns:
        The base search url.
    """
    assert search_mode in SEARCH_MODES, 'search mode "{}" is not available'.format(search_mode)

    specific_base_url = config.get('{}_{}_search_url'.format(search_mode, search_engine_name), None)

    if not specific_base_url:
        specific_base_url = config.get('{}_search_url'.format(search_engine_name), None)

    ipfile = config.get('{}_ip_file'.format(search_engine_name), '')

    if os.path.exists(ipfile):
        with open(ipfile, 'rt') as file:
            ips = file.read().split('\n')
            random_ip = random.choice(ips)
            return random_ip

    return specific_base_url


class SearchEngineScrape(metaclass=abc.ABCMeta):
    """Abstract base class that represents a search engine scrape.
    
    Each subclass that derives from SearchEngineScrape needs to 
    implement some common functionality like setting a proxy, 
    returning the found results, caching results and pushing scraped
    data to a storage like a database or an output file.
    
    The derivation is divided in two hierarchies: First we divide child
    classes in different Transport mechanisms. Scraping can happen over 
    different communication channels like Raw HTTP, scraping with the
    selenium framework or using the an asynchronous HTTP client.
    
    The next layer is the concrete implementation of the search functionality
    of the specific search engines. This is not done in a extra derivation
    hierarchy (otherwise there would be a lot of base classes for each
    search engine and thus quite some boilerplate overhead), 
    instead we determine our search engine over the internal state
    (An attribute name self.search_engine) and handle the different search
    engines in the search function.
    
    Each mode must behave similarly: It can only scape one search engine at the same time,
    but it may search for multiple search keywords. The initial start number may be
    set by the configuration. The number of pages that should be scraped for each
    keyword is also configurable.
    
    It may be possible to apply all the above rules dynamically for each
    search query. This means that the search page offset, the number of
    consecutive search pages may be provided for all keywords uniquely instead
    that they are the same for all keywords. But this requires also a
    sophisticated input format and more tricky engineering.
    """

    malicious_request_needles = {
        'google': {
            'inurl': '/sorry/',
            'inhtml': 'detected unusual traffic'
        },
        'bing': {},
        'yahoo': {},
        'baidu': {},
        'yandex': {},
        'ask': {},
        'blekko': {},
        'duckduckgo': {}
    }

    def __init__(self, config, cache_manager=None, jobs=None, scraper_search=None, session=None, db_lock=None, cache_lock=None,
                 start_page_pos=1, search_engine=None, search_type=None, proxy=None, progress_queue=None):
        """Instantiate an SearchEngineScrape object.

        Args:
            TODO
        """
        # Set the config dictionary
        self.config = config

        # Set the cache manager
        self.cache_manager = cache_manager

        jobs = jobs or {}
        self.search_engine_name = search_engine
        assert self.search_engine_name, 'You need to specify an search_engine'

        self.search_engine_name = self.search_engine_name.lower()

        if not search_type:
            self.search_type = self.config.get('search_type', 'normal')
        else:
            self.search_type = search_type

        self.jobs = jobs

        # the keywords that couldn't be scraped by this worker
        self.missed_keywords = set()

        # the number of keywords
        self.num_keywords = len(self.jobs)

        # The actual keyword that is to be scraped next
        self.query = ''

        # The default pages per keywords
        self.pages_per_keyword = [1, ]

        # The number that shows how many searches have been done by the worker
        self.search_number = 1

        # The parser that should be used to parse the search engine results
        self.parser = get_parser_by_search_engine(self.search_engine_name)(config=self.config)

        # The number of results per page
        self.num_results_per_page = int(self.config.get('num_results_per_page', 10))

        # The page where to start scraping. By default the starting page is 1.
        if start_page_pos:
            self.start_page_pos = 1 if start_page_pos < 1 else start_page_pos
        else:
            self.start_page_pos = int(self.config.get('search_offset', 1))

        # The page where we are right now
        self.page_number = self.start_page_pos

        # Install the proxy if one was provided
        self.proxy = proxy
        if isinstance(proxy, Proxy):
            self.set_proxy()
            self.requested_by = self.proxy.host + ':' + self.proxy.port
        else:
            self.requested_by = 'localhost'

        # the scraper_search object
        self.scraper_search = scraper_search

        # the scrape mode
        # to be set by subclasses
        self.scrape_method = ''

        # Whether the instance is ready to run
        self.startable = True

        # set the database lock
        self.db_lock = db_lock

        # init the cache lock
        self.cache_lock = cache_lock

        # a queue to put an element in whenever a new keyword is scraped.
        # to visualize the progress
        self.progress_queue = progress_queue

        # set the session
        self.session = session

        # the current request time
        self.requested_at = None

        # The name of the scraper
        self.name = '[{}]'.format(self.search_engine_name) + self.__class__.__name__

        # How long to sleep (in seconds) after every n-th request
        self.sleeping_ranges = dict()
        self.sleeping_ranges = self.config.get(
            '{search_engine}_sleeping_ranges'.format(search_engine=self.search_engine_name),
            self.config.get('sleeping_ranges'))

        # the default timeout
        self.timeout = 5

        # the status of the thread after finishing or failing
        self.status = 'successful'

        self.html = ''

    @abc.abstractmethod
    def search(self, *args, **kwargs):
        """Send the search request(s) over the transport."""

    @abc.abstractmethod
    def set_proxy(self):
        """Install a proxy on the communication channel."""

    @abc.abstractmethod
    def switch_proxy(self, proxy):
        """Switch the proxy on the communication channel."""

    @abc.abstractmethod
    def proxy_check(self, proxy):
        """Check whether the assigned proxy works correctly and react"""

    @abc.abstractmethod
    def handle_request_denied(self, status_code):
        """Generic behaviour when search engines detect our scraping.

        Args:
            status_code: The status code of the http response.
        """
        self.status = 'Malicious request detected: {}'.format(status_code)

    def store(self):
        """Store the parsed data in the sqlalchemy scoped session."""
        assert self.session, 'No database session.'

        if self.html:
            self.parser.parse(self.html)
        else:
            self.parser = None

        with self.db_lock:

            serp = parse_serp(self.config, parser=self.parser, scraper=self, query=self.query)

            self.scraper_search.serps.append(serp)
            self.session.add(serp)
            self.session.commit()

            store_serp_result(serp, self.config)

            if serp.num_results:
                return True
            else:
                return False

    def next_page(self):
        """Increment the page. The next search request will request the next page."""
        self.start_page_pos += 1

    def keyword_info(self):
        """Print a short summary where we are in the scrape and what's the next keyword."""
        logger.info(
            '[{thread_name}][{ip}]]Keyword: "{keyword}" with {num_pages} pages, slept {delay} seconds before '
            'scraping. {done}/{all} already scraped.'.format(
                thread_name=self.name,
                ip=self.requested_by,
                keyword=self.query,
                num_pages=self.pages_per_keyword,
                delay=self.current_delay,
                done=self.search_number,
                all=self.num_keywords
            ))

    def instance_creation_info(self, scraper_name):
        """Debug message whenever a scraping worker is created"""
        logger.info('[+] {}[{}][search-type:{}][{}] using search engine "{}". Num keywords={}, num pages for keyword={}'.format(
            scraper_name, self.requested_by, self.search_type, self.base_search_url, self.search_engine_name,
            len(self.jobs),
            self.pages_per_keyword))

    def cache_results(self):
        """Caches the html for the current request."""
        self.cache_manager.cache_results(self.parser, self.query, self.search_engine_name, self.scrape_method, self.page_number,
                      db_lock=self.db_lock)

    def _largest_sleep_range(self, search_number):
        """Sleep a given amount of time dependent on the number of searches done.

        Args:
            search_number: How many searches the worker has done yet.

        Returns:
            A range tuple which defines in which range the worker should sleep.
        """

        assert search_number >= 0
        if search_number != 0:
            s = sorted(self.sleeping_ranges.keys(), reverse=True)
            for n in s:
                if search_number % n == 0:
                    return self.sleeping_ranges[n]
        # sleep one second
        return 1, 2

    def detection_prevention_sleep(self):
        # match the largest sleep range
        self.current_delay = random.randrange(*self._largest_sleep_range(self.search_number))
        time.sleep(self.current_delay)

    def after_search(self):
        """Store the results and parse em.

        Notify the progress queue if necessary.
        """
        self.search_number += 1

        if not self.store():
            logger.debug('No results to store for keyword: "{}" in search engine: {}'.format(self.query,
                                                                                    self.search_engine_name))

        if self.progress_queue:
            self.progress_queue.put(1)
        self.cache_results()

    def before_search(self):
        """Things that need to happen before entering the search loop."""
        # check proxies first before anything
        if self.config.get('check_proxies', True) and self.proxy:
            if not self.proxy_check():
                self.startable = False

    def update_proxy_status(self, status, ipinfo=None, online=True):
        """Sets the proxy status with the results of ipinfo.io

        Args:
            status: A string the describes the status of the proxy.
            ipinfo: The json results from ipinfo.io
            online: Whether the proxy is usable or not.
        """
        ipinfo = ipinfo or {}

        with self.db_lock:

            proxy = self.session.query(db_Proxy).filter(self.proxy.host == db_Proxy.ip).first()
            if proxy:
                for key in ipinfo.keys():
                    setattr(proxy, key, ipinfo[key])

                proxy.checked_at = datetime.datetime.utcnow()
                proxy.status = status
                proxy.online = online

                self.session.add(proxy)
                self.session.commit()


from GoogleScraper.http_mode import HttpScrape
from GoogleScraper.selenium_mode import get_selenium_scraper_by_search_engine_name


class ScrapeWorkerFactory():
    def __init__(self, config, cache_manager=None, mode=None, proxy=None, search_engine=None, session=None, db_lock=None,
                 cache_lock=None, scraper_search=None, captcha_lock=None, progress_queue=None, browser_num=1):

        self.config = config
        self.cache_manager = cache_manager
        self.mode = mode
        self.proxy = proxy
        self.search_engine = search_engine
        self.session = session
        self.db_lock = db_lock
        self.cache_lock = cache_lock
        self.scraper_search = scraper_search
        self.captcha_lock = captcha_lock
        self.progress_queue = progress_queue
        self.browser_num = browser_num

        self.jobs = dict()

    def is_suitabe(self, job):

        return job['scrape_method'] == self.mode and job['search_engine'] == self.search_engine

    def add_job(self, job):

        query = job['query']
        page_number = job['page_number']

        if query not in self.jobs:
            self.jobs[query] = []

        self.jobs[query].append(page_number)

    def get_worker(self):

        if self.jobs:

            if self.mode == 'selenium':

                return get_selenium_scraper_by_search_engine_name(
                    self.config,
                    self.search_engine,
                    cache_manager=self.cache_manager,
                    search_engine=self.search_engine,
                    jobs=self.jobs,
                    session=self.session,
                    scraper_search=self.scraper_search,
                    cache_lock=self.cache_lock,
                    db_lock=self.db_lock,
                    proxy=self.proxy,
                    progress_queue=self.progress_queue,
                    captcha_lock=self.captcha_lock,
                    browser_num=self.browser_num,
                )

            elif self.mode == 'http':

                return HttpScrape(
                    self.config,
                    cache_manager=self.cache_manager,
                    search_engine=self.search_engine,
                    jobs=self.jobs,
                    session=self.session,
                    scraper_search=self.scraper_search,
                    cache_lock=self.cache_lock,
                    db_lock=self.db_lock,
                    proxy=self.proxy,
                    progress_queue=self.progress_queue,
                )

        return None
