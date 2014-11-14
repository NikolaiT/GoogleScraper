# -*- coding: utf-8 -*-

import threading
import datetime
import random
import math
import logging
import sys
import time
import socket
import abc

try:
    from cssselect import HTMLTranslator, SelectorError
    from bs4 import UnicodeDammit
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait  # available since 2.4.0
    from selenium.webdriver.support import expected_conditions as EC  # available since 2.26.0
except ImportError as ie:
    if hasattr(ie, 'name') and ie.name == 'bs4' or hasattr(ie, 'args') and 'bs4' in str(ie):
        sys.exit('Install bs4 with the command "sudo pip3 install beautifulsoup4"')
    if ie.name == 'socks':
        sys.exit('socks is not installed. Try this one: https://github.com/Anorov/PySocks')

    print(ie)
    sys.exit('You can install missing modules with `pip3 install [modulename]`')

import GoogleScraper.socks as socks
from GoogleScraper.caching import get_cached, cache_results, cached_file_name, cached
from GoogleScraper.database import SearchEngineResultsPage, Link
from GoogleScraper.config import Config
from GoogleScraper.parsing import GoogleParser, YahooParser, YandexParser, BaiduParser, BingParser, DuckduckgoParser, get_parser_by_search_engine

logger = logging.getLogger('GoogleScraper')


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

    def __init__(self, keywords=None, session=None, scaper_search=None, start_page_pos=1, search_engine=None, search_type=None, proxy=None):
        if not search_engine:
            self.search_engine = Config['SCRAPING'].get('search_engine', 'Google')
        else:
            self.search_engine = search_engine

        self.search_engine = self.search_engine.lower()

        if not search_type:
            self.search_type = Config['SCRAPING'].get('search_type', 'normal')
        else:
            self.search_type = search_type
            
        # The number of pages to scrape for each keyword
        self.num_pages_per_keyword = Config['SCRAPING'].getint('num_pages_for_keyword', 1)
        
        # The proxy to use
        self.proxy = proxy
        
        # The keywords that need to be scraped
        # If a SearchEngineScrape receives explicitly keywords,
        # scrape them. otherwise scrape the ones specified in the Config.
        if keywords:
            self.keywords = set(keywords)
        else:
            self.keywords = set(Config['SCRAPING'].get('keywords', []))

        if not isinstance(keywords, list):
            self.keywords = set([self.keywords])
        
        # The actual keyword that is to be scraped next
        self.current_keyword = self.next_keyword()

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
        if proxy:
            self.set_proxy()

        # set the database scoped session
        self.session = session

        # the scraper_search database object
        self.scraper_search = scaper_search

        # get the base search url based on the search engine.
        self.base_search_url = Config['SCRAPING'].get('{search_engine}_search_url'.format(search_engine=self.search_engine))
        
    
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
        """
        while self.current_keyword:

            self.current_page = self.start_page_pos

            for self.current_page in range(1, self.num_pages_per_keyword + 1):

                # set the actual search code in the derived class
                callback(*args, **kwargs)

            self.current_keyword = self.next_keyword()

        
    @abc.abstractmethod
    def set_proxy(self):
        """Install a proxy on the communication channel."""
        
    @abc.abstractmethod
    def switch_proxy(self, proxy):
        """Switch the proxy on the communication channel."""
        
    @abc.abstractmethod
    def handle_request_denied(self):
        """Behaviour when search engines detect our scraping."""

    def store(self):
        """Store the parsed data in the sqlalchemy scoped session."""
        assert self.session, 'You need to pass a sqlalchemy scoped session to SearchEngineScrape instances'

        serp = SearchEngineResultsPage(
            search_engine_name=self.search_engine,
            page_number=self.current_page,
            requested_at=datetime.datetime.utcnow(),
            requested_by='127.0.0.1',
            query=self.current_keyword,
            num_results_for_keyword=self.parser.search_results['num_results'],
            search=self.scraper_search
        )
        self.session.add(serp)

        for key, value in self.parser.search_results.items():
            if isinstance(value, list):
                for link in value:
                    l = Link(
                        url=link['link'],
                        snippet=link['snippet'],
                        title=link['title'],
                        visible_link=link['visible_link'],
                        serp=serp
                    )
                    self.session.add(l)

        self.session.commit()

    def next_page(self):
        """Increment the page. The next search request will request the next page."""
        self.start_page_pos += 1
        
    def next_keyword(self):
        """Spits out search queries as long as there are some remaining.
        
        Returns:
            False if no more search keywords are present. Otherwise the next keyword.
        """
        try:
            keyword = self.keywords.pop()
            return keyword
        except KeyError as e:
            return False


class HttpScrape(SearchEngineScrape, threading.Timer):
    """Offers a fast way to query any search engine using raw HTTP requests.

    Overrides the run() method of the superclass threading.Timer.
    Each thread represents a crawl for one Search Engine SERP page. Inheriting
    from threading.Timer allows the deriving class to delay execution of the run()
    method.

    This is a base class, Any supported search engine needs to subclass HttpScrape to
    implement this specific scrape type.

    Attributes:
        results: Returns the found results.
    """

    # Several different User-Agents to diversify the requests.
    # Keep the User-Agents updated. Last update: 13th November 2014
    # Get them here: http://techblog.willshouse.com/2012/01/03/most-common-user-agents/
    USER_AGENTS = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10) AppleWebKit/600.1.25 (KHTML, like Gecko) Version/8.0 Safari/600.1.25',
        'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.111 Safari/537.36',
        'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.104 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_5) AppleWebKit/600.1.17 (KHTML, like Gecko) Version/7.1 Safari/537.85.10',
        'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:32.0) Gecko/20100101 Firefox/32.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.111 Safari/537.36',
        'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:33.0) Gecko/20100101 Firefox/33.0',
        'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.104 Safari/537.36',
        'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.111 Safari/537.36',
        'Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.104 Safari/537.36',
        'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.104 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.111 Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 8_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12B411 Safari/600.1.4',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:33.0) Gecko/20100101 Firefox/33.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:32.0) Gecko/20100101 Firefox/32.0',
        'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.111 Safari/537.36'
    ]

    def __init__(self, *args, time_offset=0.0, **kwargs):
        """Initialize an HttScrape object to scrape over blocking http.

        HttpScrape inherits from SearchEngineScrape
        and from threading.Timer.
        """
        threading.Timer.__init__(self, time_offset, self.search)
        SearchEngineScrape.__init__(self, *args, **kwargs)
        
        # Bind the requests module to this instance such that each 
        # instance may have an own proxy
        self.requests = __import__('requests')
        
        # initialize the GET parameters for the search request
        self.search_params = {}

        # initialize the HTTP headers of the search request
        # to some base values that mozilla uses with requests.
        # the Host and User-Agent field need to be set additionally.
        self.headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }

    def set_proxy(self):
        """Setup a socks connection for the socks module bound to this instance.

        Args:
            proxy: Namedtuple, Proxy to use for this thread.
        """
        def create_connection(address, timeout=None, source_address=None):
            sock = socks.socksocket()
            sock.connect(address)
            return sock

        pmapping = {
            'socks4': 1,
            'socks5': 2,
            'http': 3
        }
        # Patch the socket module
        # rdns is by default on true. Never use rnds=False with TOR, otherwise you are screwed!
        socks.setdefaultproxy(pmapping.get(self.proxy.proto), self.proxy.host, int(self.proxy.port), rdns=True)
        socks.wrap_module(socket)
        socket.create_connection = create_connection

    def switch_proxy(self, proxy):
        super().switch_proxy()

    def handle_request_denied(self, status_code):
        raise Exception('Request not allowed')

    def build_search(self):
        """Build the headers and params for the search request for the search engine."""
        
        self.search_params = {}

        # Don't set the offset parameter explicitly if the default search (no offset) is correct.
        start_search_position = None if self.current_page == 1 else str(int(self.num_results_per_page) * int(self.current_page))
        
        if self.search_engine == 'google':
            self.parser = GoogleParser(searchtype=self.search_type)
            self.search_params['q'] = self.current_keyword
            self.search_params['num'] = str(self.num_results_per_page)
            self.search_params['start'] = start_search_position

            if self.search_type == 'image':
                self.search_params.update({
                    'oq': self.current_keyword,
                    'site': 'imghp',
                    'tbm': 'isch',
                    'source': 'hp',
                    #'sa': 'X',
                    'biw': 1920,
                    'bih': 881
                }) 
            elif self.search_type == 'video':
                self.search_params.update({
                    'tbm': 'vid',
                    'source': 'lnms',
                    'sa': 'X',
                    'biw': 1920,
                    'bih': 881
                })
            elif self.search_type == 'news':
                self.search_params.update({
                    'tbm': 'nws',
                    'source': 'lnms',
                    'sa': 'X'
                })
        elif self.search_engine == 'yandex':
            self.parser = YandexParser(searchtype=self.search_type)
            self.search_params['text'] = self.current_keyword
            self.search_params['p'] = start_search_position
        
        elif self.search_engine == 'bing':
            self.parser = BingParser(searchtype=self.search_type)
            self.search_params['q'] = self.current_keyword
            self.search_params['first'] = start_search_position
            
        elif self.search_engine == 'yahoo':
            self.parser = YahooParser(searchtype=self.search_type)
            self.search_params['p'] = self.current_keyword
            self.search_params['b'] = start_search_position
            self.search_params['ei'] = 'UTF-8'
            
        elif self.search_engine == 'baidu':
            self.parser = BaiduParser(searchtype=self.search_type)
            self.search_params['wd'] = self.current_keyword
            self.search_params['pn'] = start_search_position
            self.search_params['ie'] = 'utf-8'
        elif self.search_engine == 'duckduckgo':
            self.parser = DuckduckgoParser(searchtype=self.search_type)
            self.search_params['q'] = self.current_keyword
            
    def search(self, *args, rand=False, **kwargs):
        """The actual search for the search engine."""

        self.build_search()

        if rand:
            self.headers['User-Agent'] = random.choice(self.USER_AGENTS)

        html = get_cached(self.current_keyword, self.base_search_url, params=self.search_params)

        if not html:
            try:
                if Config['GLOBAL'].getint('verbosity', 0) > 1:
                    logger.info('[HTTP] Base_url: {base_url}, headers={headers}, params={params}'.format(
                        base_url=self.base_search_url,
                        headers=self.headers,
                        params=self.search_params)
                    )

                r = self.requests.get(self.base_search_url, headers=self.headers,
                                 params=self.search_params, timeout=3.0)

            except self.requests.ConnectionError as ce:
                logger.error('Network problem occurred {}'.format(ce))
                raise ce
            except self.requests.Timeout as te:
                logger.error('Connection timeout {}'.format(te))
                raise te

            if not r.ok:
                logger.error('HTTP Error: {}'.format(r.status_code))
                self.handle_request_denied(r.status_code)
                return False

            html = r.text

            # cache fresh results
            cache_results(html, self.current_keyword, url=self.base_search_url, params=self.search_params)

        self.parser.parse(html)
        self.store()
        print(self.parser)

    def run(self):
        args = []
        kwargs = {}
        kwargs['rand'] = False
        SearchEngineScrape.blocking_search(self, self.search, *args, **kwargs)
        
class AsyncHttpScrape(SearchEngineScrape):
    pass

class SelScrape(SearchEngineScrape, threading.Thread):
    """Instances of this class make use of selenium browser objects to query Google.

    This is a quite cool approach if you ask me :D
    """

    def __init__(self, *args, rlock=None, captcha_lock=None, browser_num=1, **kwargs):
        """Create a new SelScraper Thread.

        Args:
            captcha_lock: To sync captcha solving (stdin)
            proxy: Optional, if set, use the proxy to route all scrapign through it.
            browser_num: A unique, semantic number for each thread.
        """
        self.search_input = None

        threading.Thread.__init__(self)
        SearchEngineScrape.__init__(self, *args, **kwargs)

        self.browser_type = Config['SELENIUM'].get('sel_browser', 'chrome').lower()
        self.browser_num = browser_num
        self.captcha_lock = captcha_lock
        self.rlock = rlock
        self.ip = '127.0.0.1'
        self.search_number = 0

        # How long to sleep (ins seconds) after every n-th request
        self.sleeping_ranges = dict()
        for line in Config['SELENIUM'].get('sleeping_ranges').split('\n'):
            assert line.count(';') == 1
            key, value = line.split(';')
            self.sleeping_ranges[int(key)] = tuple([int(offset.strip()) for offset in value.split(',')])

        if Config['GLOBAL'].getint('verbosity', 0) > 1:
            logger.info('[+] SelScraper[{}] created using the search engine {}. Number of keywords to scrape={}, using proxy={}, number of pages={}, browser_num={}'.format(self.search_engine, self.browser_type, len(self.keywords), self.proxy, self.num_pages_per_keyword, self.name))

    def _largest_sleep_range(self, search_number):
        assert search_number >= 0
        if search_number != 0:
            s = sorted(self.sleeping_ranges.keys(), reverse=True)
            for n in s:
                if search_number % n == 0:
                    return self.sleeping_ranges[n]
        # sleep one second
        return (1, 2)

    def set_proxy(self):
        """Install a proxy on the communication channel."""

    def switch_proxy(self, proxy):
        """Switch the proxy on the communication channel."""

    def _get_webdriver(self):
        """Return a webdriver instance and set it up with the according profile/ proxies.

        Chrome is quite fast, but not as stealthy as PhantomJS.

        Returns:
            The appropriate webdriver mode according to self.browser_type. If no webdriver mode
            could be found, return False.
        """
        if self.browser_type == 'chrome':
            return self._get_Chrome()
        elif self.browser_type == 'firefox':
            return self._get_Firefox()
        elif self.browser_type == 'phantomjs':
            return self._get_PhantomJS()

        # if the config remains silent, try to get Chrome, else Firefox
        if not self._get_Chrome():
            self._get_Firefox()

        return False

    def _get_Chrome(self):
        try:
            if self.proxy:
                chrome_ops = webdriver.ChromeOptions()
                chrome_ops.add_argument('--proxy-server={}://{}:{}'.format(self.proxy.proto, self.proxy.host, self.proxy.port))
                self.webdriver = webdriver.Chrome(chrome_options=chrome_ops)
            else:
                self.webdriver = webdriver.Chrome()
            return True
        except WebDriverException as e:
            # we dont have a chrome executable or a chrome webdriver installed
            logger.error(e)
        return False

    def _get_Firefox(self):
        try:
            if self.proxy:
                profile = webdriver.FirefoxProfile()
                profile.set_preference("network.proxy.type", 1) # this means that the proxy is user set, regardless of the type
                if self.proxy.proto.lower().startswith('socks'):
                    profile.set_preference("network.proxy.socks", self.proxy.host)
                    profile.set_preference("network.proxy.socks_port", self.proxy.port)
                    profile.set_preference("network.proxy.socks_version", 5 if self.proxy.proto[-1] == '5' else 4)
                    profile.update_preferences()
                elif self.proxy.proto == 'http':
                    profile.set_preference("network.proxy.http", self.proxy.host)
                    profile.set_preference("network.proxy.http_port", self.proxy.port)
                else:
                    raise ValueError('Invalid protocol given in proxyfile.')
                profile.update_preferences()
                self.webdriver = webdriver.Firefox(firefox_profile=profile)
            else:
                self.webdriver = webdriver.Firefox()
            return True
        except WebDriverException as e:
            # reaching here is bad, since we have no available webdriver instance.
            logger.error(e)
        return False

    def _get_PhantomJS(self):
        try:
            service_args = []

            if self.proxy:
                service_args.extend([
                    '--proxy={}:{}'.format(self.proxy.host, self.proxy.port),
                    '--proxy-type={}'.format(self.proxy.proto),
                ])

                if self.proxy.username and self.proxy.password:
                    service_args.append(
                        '--proxy-auth={}:{}'.format(self.proxy.username, self.proxy.password)
                    )

            self.webdriver = webdriver.PhantomJS(service_args=service_args)
        except WebDriverException as e:
            logger.error(e)

    def handle_request_denied(self):
        """Checks whether Google detected a potentially harmful request.

        Whenever such potential abuse is detected, Google shows an captcha.

        Returns:
            True If the issue could be resolved.

        Raises:
            MaliciousRequestDetected when there was not way to stp Google From denying our requests.
        """
        if Config['SELENIUM'].getboolean('manual_captcha_solving'):
            if '/sorry/' in self.webdriver.current_url \
                    and 'detected unusual traffic' in self.webdriver.page_source:
                if Config['SELENIUM'].get('manual_captcha_solving', False):
                    with self.captcha_lock:
                        import tempfile
                        tf = tempfile.NamedTemporaryFile('wb')
                        tf.write(self.webdriver.get_screenshot_as_png())
                        import webbrowser
                        webbrowser.open('file://{}'.format(tf.name))
                        solution = input('enter the captcha please...')
                        self.webdriver.find_element_by_name('submit').send_keys(solution + Keys.ENTER)
                        try:
                            self.search_input = WebDriverWait(self.webdriver, 5).until(EC.presence_of_element_located((By.NAME, "q")))
                        except TimeoutException as e:
                            raise MaliciousRequestDetected('Requesting with this ip is not possible at the moment.')
                        tf.close()
                        return True
            elif 'is not an HTTP Proxy' in self.webdriver.page_source:
                raise GoogleSearchError('Inavlid TOR usage. Specify the proxy protocol as socks5')
            else:
                return False
        else:
            raise MaliciousRequestDetected('Requesting with this ip is not possible at the moment.')


    def build_search(self):
        """Build the search for SelScrapers"""
        assert self.webdriver, 'Webdriver needs to be ready to build the search'

        url_params= {
            'google': 'q={query}',
            'yandex': 'text={query}',
            'bing': 'q={query}',
            'yahoo': 'p={query}',
            'baidu': 'wd={query}',
            'duckduckgo': 'q={query}'
        }[self.search_engine]

        url_params = url_params.format(query=self.current_keyword)

        self.starting_point = self.base_search_url +  url_params

        logger.info(self.starting_point)

        self.webdriver.get(self.starting_point)

    def _get_search_input_field(self):
        """Get the search input field for the current search_engine.

        Returns:
            A tuple to locate the search field as used by seleniums function presence_of_element_located()
        """

        input_field_selectors = {
            'google': (By.NAME, 'q'),
            'yandex': (By.NAME, 'text'),
            'bing': (By.NAME, 'q'),
            'yahoo': (By.NAME, 'p'),
            'baidu': (By.NAME, 'wd'),
            'duckduckgo': (By.NAME, 'q')
        }

        return input_field_selectors[self.search_engine]


    def _get_next_page_url(self):
        """Finds the url that locates the next page for any search_engine.

        Returns:
            The href attribute of the next_url for further results.
        """

        next_page_selectors = {
            'google': '#pnnext',
            'yandex': '.pager__button_kind_next',
            'bing': '.sb_pagN',
            'yahoo': '#pg-next',
            'baidu': '.n',
            'duckduckgo': '' # loads results dynamically with ajax
        }

        selector = next_page_selectors[self.search_engine]

        next_url = ''

        try:
            # wait until the next page link emerges
            WebDriverWait(self.webdriver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            next_url = self.webdriver.find_element_by_css_selector(selector).get_attribute('href')
        except TimeoutException as te:
            logger.debug('Cannot locate next page element.')
            raise te
        except WebDriverException as e:
            # leave if no next results page is available
            return False

        return next_url

    def next_keyword(self):
        keyword = SearchEngineScrape.next_keyword(self)

        if self.search_input:
            self.search_input.clear()
            time.sleep(.25)
            self.search_input.send_keys(self.current_keyword + Keys.ENTER)

        return keyword

    def search(self):
        """Search with webdriver."""

        next_url = None

        # match the largest sleep range
        sleep_time = random.randrange(*self._largest_sleep_range(self.search_number))

        # log stuff if verbosity is set accordingly
        if Config['GLOBAL'].getint('verbosity', 1 ) > 1:
            if self.proxy:
                logger.info('[i] Page number={}, ScraperThread({url}) ({ip}:{port} {} is sleeping for {} seconds...Next keyword: ["{kw}"]'.format(self.current_page, self._ident, sleep_time, url=next_url, ip=self.proxy.host, port=self.proxy.port, kw=self.current_keyword))
            else:
                logger.info('[i] Page number={}, ScraperThread({url}) ({} is sleeping for {} seconds...Next keyword: ["{}"]'.format(self.current_page, self._ident, sleep_time, self.current_keyword, url=next_url))

        time.sleep(sleep_time)

        try:
            self.search_input = WebDriverWait(self.webdriver, 5).until(EC.presence_of_element_located(self._get_search_input_field()))
        except TimeoutException as e:
            logger.error(e)
            if not self.handle_request_denied():
                open('/tmp/out.png', 'wb').write(self.webdriver.get_screenshot_as_png())
                raise GoogleSearchError('search input field cannot be found.')

        # Waiting until the keyword appears in the title may
        # not be enough. The content may still be off the old page.
        try:
            WebDriverWait(self.webdriver, 5).until(EC.title_contains(self.current_keyword))
        except TimeoutException as e:
            raise SeleniumSearchError('Keyword not found in title: {}'.format(e))

        next_url = self._get_next_page_url()

        # That's because we sleep explicitly one second, so the site and
        # whatever js loads all shit dynamically has time to update the
        # DOM accordingly.
        time.sleep(1.5)

        html = self.webdriver.page_source

        self.parser.parse(html)
        self.store()
        print(self.parser)

        if self.rlock:
            # Lock for the sake that two threads write to same file (not probable)
            self.rlock.acquire()
            cache_results(html, self.current_keyword, next_url if next_url else self.starting_point)
            self.rlock.release()

        self.search_number += 1

    def run(self):
        if not self._get_webdriver():
            raise SeleniumMisconfigurationError('Aborting due to no available selenium webdriver.')

        if self.browser_type != 'browser_type':
            self.webdriver.set_window_size(400, 400)
            self.webdriver.set_window_position(400*(self.browser_num % 4), 400*(math.floor(self.browser_num//4)))

        self.build_search()

        SearchEngineScrape.blocking_search(self, self.search)