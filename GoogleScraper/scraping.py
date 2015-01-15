# -*- coding: utf-8 -*-

import datetime
import random
import logging
import time
import os
import abc

from GoogleScraper.proxies import Proxy
from GoogleScraper.caching import cache_results
from GoogleScraper.database import SearchEngineResultsPage, db_Proxy
from GoogleScraper.config import Config
from GoogleScraper.log import out
from GoogleScraper.output_converter import store_serp_result
from GoogleScraper.parsing import get_parser_by_search_engine, parse_serp

logger = logging.getLogger('GoogleScraper')


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

- If the proxy is detected by the search engine we try to get another proxy from the pool and we call switch_proxy() => continue.

- If the proxy is detected by the search engine and there is no other proxy in the pool, we wait {search_engine}_proxy_detected_timeout seconds => continue.
    + If the proxy is detected again after the waiting time, we discard the proxy for the whole scrape.
"""


def get_base_search_url_by_search_engine(search_engine_name, search_mode):
    """Retrieves the search engine base url for a specific search_engine.

    This function cascades. So base urls in the SCRAPING section will
    be overwritten by search_engine urls in the specific mode sections.
    On the other side, if a search engine has no special url in it' corresponding
    mode, the default one from the SCRAPING config section will be loaded.

    Args:
        search_engine_name The name of the search engine
        search_mode: The search mode that is used

    Returns:
        The base search url.
    """
    assert search_mode in SEARCH_MODES, 'search mode "{}" is not available'.format(search_mode)

    specific_base_url = Config[search_mode.upper()].get('{}_search_url'.format(search_engine_name), None)

    if not specific_base_url:
        specific_base_url = Config['SCRAPING'].get('{}_search_url'.format(search_engine_name), None)

    ipfile = Config['SCRAPING'].get('{}_ip_file'.format(search_engine_name), '')

    if os.path.exists(ipfile):
        ips = open(ipfile, 'rt').read().split('\n')
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
    different communication channels like Raw HTTP, doing it with the 
    selenium framework or using the an asynchronous HTTP client.
    
    The next layer is the concrete implementation of the search functionality
    of the specific search engines. This is not done in a extra derivation
    hierarchy (otherwise there would be a lot of base classes for each
    search engine and thus quite some boilerplate overhead), 
    instead we determine our search engine over the internal state
    (An attribute name self.search_engine) and handle the different search
    engines in the search function.
    
    Each must behave similarly: It can only scape at one search engine at the same time,
    but it may search for multiple search keywords. The initial start number may be
    set by the configuration. The number of pages that should be scraped for each
    keyword may be also set.
    
    It may be possible to apply all the above rules dynamically for each
    search query. This means that the search page offset, the number of
    consecutive search pages may be provided for all keywords uniquely instead
    that they are the same for all keywords. But this requires also a
    sophisticated input format and some more tricky engineering.
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
        'blekko': {}
    }

    def __init__(self, keywords=None, scraper_search=None, session=None, db_lock=None, cache_lock=None,
                 start_page_pos=1, search_engine=None, search_type=None, proxy=None, progress_queue=None):
        """Instantiate an SearchEngineScrape object.

        Args:
            TODO
        """
        self.search_engine = search_engine
        assert self.search_engine, 'You need to specify an search_engine'

        self.search_engine = self.search_engine.lower()

        if not search_type:
            self.search_type = Config['SCRAPING'].get('search_type', 'normal')
        else:
            self.search_type = search_type
            
        # The number of pages to scrape for each keyword
        self.num_pages_per_keyword = Config['SCRAPING'].getint('num_pages_for_keyword', 1)
        
        # The keywords that need to be scraped
        # If a SearchEngineScrape receives explicitly keywords,
        # scrape them. otherwise scrape the ones specified in the Config.
        if keywords:
            self.keywords = keywords
        else:
            self.keywords = Config['SCRAPING'].get('keywords', [])

        self.keywords = list(set(self.keywords))

        # the keywords that couldn't be scraped by this worker
        self.missed_keywords = set()

        # the number of keywords
        self.num_keywords = len(self.keywords)
        
        # The actual keyword that is to be scraped next
        self.current_keyword = self.keywords[0]

        # The number that shows how many searches have been done by the worker
        self.search_number = 1

        # The parser that should be used to parse the search engine results
        self.parser = get_parser_by_search_engine(self.search_engine)()
        
        # The number of results per page
        self.num_results_per_page = Config['SCRAPING'].getint('num_results_per_page', 10)

        # The page where to start scraping. By default the starting page is 1.
        if start_page_pos:
            self.start_page_pos = 1 if start_page_pos < 1 else start_page_pos
        else:
            self.start_page_pos = Config['SCRAPING'].getint('search_offset', 1)

        # The page where we are right now
        self.current_page = self.start_page_pos
        
        # Install the proxy if one was provided
        self.proxy = proxy
        if isinstance(proxy, Proxy):
            self.set_proxy()
            self.ip = self.proxy.host + ':' + self.proxy.port
        else:
            self.ip = 'localhost'

        # the scraper_search object
        self.scraper_search = scraper_search
        
        # the scrape mode
        # to be set by subclasses
        self.scrapemethod = ''
        
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
        self.current_request_time = None

        # How long to sleep (in seconds) after every n-th request
        self.sleeping_ranges = dict()
        sleep_ranges_option = Config['GLOBAL'].get('{search_engine}_sleeping_ranges'.format(search_engine=self.search_engine),
                                      Config['GLOBAL'].get('sleeping_ranges'))

        for line in sleep_ranges_option.split('\n'):
            assert line.count(':') == 1, 'Invalid sleep range format.'
            key, value = line.split(':')
            self.sleeping_ranges[int(key)] = tuple([int(offset.strip()) for offset in value.split(',')])


        # the default timeout
        self.timeout = 5



    @abc.abstractmethod
    def search(self, *args, **kwargs):
        """Send the search request(s) over the transport."""


    def blocking_search(self, callback, *args, **kwargs):
        """Similar transports have the same search loop layout.

        The SelScrape and HttpScrape classes have the same search loops. Just
        the transport mechanism is quite different (In HttpScrape class we replace
        the browsers functionality with our own for example).

        Args:
            callback: A callable with the search functionality.
            args: Arguments for the callback
            kwargs: Keyword arguments for the callback.
        """
        for i, self.current_keyword in enumerate(self.keywords):

            self.current_page = self.start_page_pos

            for self.current_page in range(1, self.num_pages_per_keyword + 1):

                # set the actual search code in the derived class
                try:

                    if not callback(*args, **kwargs):
                        self.missed_keywords.add(self.current_keyword)

                except StopScrapingException as e:
                    # Leave search when search engines detected us
                    # add the rest of the keywords as missed one
                    logger.critical(e)
                    self.missed_keywords.add(self.keywords[i:])
                    continue

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
        logger.warning('Malicious request detected: {}'.format(status_code))

        # cascade
        timeout = Config['PROXY_POLICY'].getint('{search_engine}_proxy_detected_timeout'.format(
            search_engine=self.search_engine), Config['PROXY_POLICY'].getint('proxy_detected_timeout'))
        time.sleep(timeout)

    def store(self):
        """Store the parsed data in the sqlalchemy scoped session."""
        assert self.session, 'No database session.'

        with self.db_lock:
            serp = SearchEngineResultsPage(
                search_engine_name=self.search_engine,
                scrapemethod=self.scrapemethod,
                page_number=self.current_page,
                requested_at=self.current_request_time,
                requested_by=self.ip,
                query=self.current_keyword,
                effective_query=self.parser.effective_query,
                num_results_for_keyword=self.parser.num_results,
            )
            self.scraper_search.serps.append(serp)

            serp = parse_serp(serp=serp, parser=self.parser)

            if serp.num_results > 0:
                self.session.add(serp)
                self.session.commit()
            else:
                return False

            store_serp_result(serp)

            return True

    def next_page(self):
        """Increment the page. The next search request will request the next page."""
        self.start_page_pos += 1

    def keyword_info(self):
        """Print a short summary where we are in the scrape and what's the next keyword."""
        out('[{thread_name}][{ip}][{search_engine}]Keyword: "{keyword}" with {num_pages} pages, slept {delay} seconds before scraping. {done}/{all} already scraped.'.format(
            thread_name=self.name,
            search_engine=self.search_engine,
            ip=self.ip,
            keyword=self.current_keyword,
            num_pages=self.num_pages_per_keyword,
            delay=self.current_delay,
            done=self.search_number,
            all=self.num_keywords
        ), lvl=2)

    def instance_creation_info(self, scraper_name):
        """Debug message whenever a scraping worker is created"""
        out('[+] {}[{}][search-type:{}][{}] using search engine "{}". Num keywords={}, num pages for keyword={}'.format(
            scraper_name, self.ip, self.search_type, self.base_search_url, self.search_engine, len(self.keywords), self.num_pages_per_keyword), lvl=1)


    def cache_results(self):
        """Caches the html for the current request."""
        if Config['GLOBAL'].getboolean('do_caching', False):
            with self.cache_lock:
                cache_results(self.parser.cleaned_html, self.current_keyword, self.search_engine, self.scrapemethod)


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
        return (1, 2)

    def detection_prevention_sleep(self):
        # match the largest sleep range
        self.current_delay = random.randrange(*self._largest_sleep_range(self.search_number))
        time.sleep(self.current_delay)

    def after_search(self):
        """Store the results and parse em.

        Notify the progress queue if necessary.
        """
        self.parser.parse(self.html)
        self.search_number += 1

        if not self.store():
            logger.error('No results to store, skip current keyword: "{0}"'.format(self.current_keyword))
            return

        if self.progress_queue:
            self.progress_queue.put(1)
        self.cache_results()

    def before_search(self):
        """Things that need to happen before entering the search loop."""

        # check proxies first before anything
        if Config['SCRAPING'].getboolean('check_proxies', True) and self.proxy:
            if not self.proxy_check():
                self.startable = False


    def update_proxy_status(self, status, ipinfo={}, online=True):
        """Sets the proxy status with the results of ipinfo.io

        Args:
            status: A string the describes the status of the proxy.
            ipinfo: The json results from ipinfo.io
            online: Whether the proxy is usable or not.
        """

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

