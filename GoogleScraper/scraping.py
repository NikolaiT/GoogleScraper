# -*- coding: utf-8 -*-

import threading
import types
import random
import math
import logging
import pprint
import sys
import lxml.html
import time
import socket
import os
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
from GoogleScraper.config import Config
from GoogleScraper.parsing import GoogleParser, YahooParser, YandexParser, BaiduParser, BingParser, DuckduckgoParser

logger = logging.getLogger('GoogleScraper')


class GoogleSearchError(Exception):
    pass

class InvalidNumberResultsException(GoogleSearchError):
    pass

class MaliciousRequestDetected(GoogleSearchError):
    pass

class SeleniumMisconfigurationError(Exception):
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

    def __init__(self, keywords=None, num_page=1, search_engine=None, search_type=None, proxy=None):
        if not search_engine:
            self.search_engine = Config['SCRAPING'].get('search_engine', 'Google')
        else:
            self.search_engine = search_engine

        self.search_engine = self.search_engine.lower()

        if not search_type:
            self.search_type = Config['SCRAPING'].get('search_type', 'normal')
        else:
            self.search_type = search_type
            
        # On which page to begin scraping
        self.search_offset = Config['SCRAPING'].getint('search_offset', 1)
        
        # The number of pages to scrape for each keyword
        self.num_pages_per_keyword = Config['SCRAPING'].getint('num_of_pages', 1)
        
        # The proxy to use
        self.proxy = proxy
        
        # The keywords that need to be scraped
        # If a SearchEngineScrape receives explicitly keywords,
        # scrape them. otherwise scrape the ones specified in the Config.
        if keywords:
            self.keywords = keywords
        else:
            self.keywords = Config['SCRAPING'].get('keywords', [])

        if not isinstance(keywords, list):
            self.keywords = list(self.keywords)
        
        # The actual keyword that is to be scraped next
        self.current_keyword = ''
        
        # The parser that should be used to parse the search engine results
        self.parser = None
        
        # The number of results per page
        self.num_results_per_page = Config['SCRAPING'].getint('num_results_per_page', 10)

        # The page where to start scraping. By default the starting page is 1.
        self.num_page = 1 if num_page < 1 else num_page
        
        # Install the proxy if one was provided
        self.proxy = proxy
        if proxy:
            self.set_proxy()

        # get the base search url based on the search engine.
        self.base_search_url = Config['SCRAPING'].get('{search_engine}_search_url'.format(search_engine=self.search_engine))
        
    
    @abc.abstractmethod
    def search(self):
        """Send the search request(s) over the transport."""
        
    @abc.abstractmethod
    def set_proxy(self):
        """Install a proxy on the communication channel."""
        
    @abc.abstractmethod
    def switch_proxy(self, proxy):
        """Switch the proxy on the communication channel."""
        
    @abc.abstractmethod
    def handle_request_denied(self):
        """Behaviour when search engines detect our scraping."""

    def next_page(self):
        """Increment the page. The next search request will request the next page."""
        self.num_page += 1
        
    def next_keyword(self):
        """Spits out search queries as long as there are some remaining.
        
        Returns:
            False if no more search keywords are present. Otherwise the next keyword.
        """
        try:
            keyword = self.keywords.pop()

        except IndexError as e:
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
        super(threading.Timer, self).__init__(time_offset, self.search)
        super(SearchEngineScrape, self).__init__(*args, **kwargs)
        
        # Bind the requests module to this instance such that each 
        # instance may have an own proxy
        self.requests == __import__('requests')
        
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
        
        keyword = self.next_keyword()
        
        start_search_position = None if self.search_offset == 1 else str(int(self.num_results_per_page) * int(self.num_page))
        
        if self.search_engine == 'google':
            self.parser = GoogleParser(searchtype=self.search_type)
            self.search_params['q'] = keyword
            self.search_params['num'] = str(self.num_results_per_page)
            self.search_params['start'] = start_search_position

            if self.search_type == 'image':
                self.search_params.update({
                    'oq': keyword,
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
            self.search_params['text'] = keyword
            self.search_params['p'] = start_search_position
        
        elif self.search_engine == 'bing':
            self.parser = BingParser(searchtype=self.search_type)
            self.search_params['q'] = keyword
            self.search_params['first'] = start_search_position
            
        elif self.search_engine == 'yahoo':
            self.parser = YahooParser(searchtype=self.search_type)
            self.search_params['p'] = keyword
            self.search_params['b'] = start_search_position
            self.search_params['ei'] = 'UTF-8'
            
        elif self.search_engine == 'baidu':
            self.parser = BaiduParser(searchtype=self.search_type)
            self.search_params['wd'] = keyword
            self.search_params['pn'] = start_search_position
            self.search_params['ie'] = 'utf-8'
        elif self.search_engine == 'duckduckgo':
            self.parser = DuckduckgoParser(searchtype=self.search_type)
            self.search_params['q'] = keyword
            
    def search(self, rand=False):
        """The actual search and parsing of the results."""
        self.build_search()
        
        if rand:
            self.headers['User-Agent'] = random.choice(self.USER_AGENTS)

        html = get_cached(self.keyword, Config['GLOBAL'].get('base_search_url'), params=self.search_params)

        if not html:
            try:
                base_url = Config['GLOBAL'].get('base_search_url')

                if Config['GLOBAL'].getint('verbosity', 0) > 1:
                    logger.info('[HTTP] Base_url: {base_url}, headers={headers}, params={params}'.format(
                        base_url=base_url,
                        headers=self.headers,
                        params=self.search_params)
                    )

                r = self.requests.get(Config['GLOBAL'].get('base_search_url'), headers=self.headers,
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
            cache_results(html, self.keyword, url=Config['GLOBAL'].get('base_search_url'), params=self.search_params)

        self.parser.parse(html)
        
        # TODO: remove it and save it to a data storage
        print(self.parser)
        
class AsyncHttpScrape(SearchEngineScrape):
    pass

class SelScrape(threading.Thread):
    """Instances of this class make use of selenium browser objects to query Google.
    """

    def __init__(self, keywords, rlock=None, queue=None, captcha_lock=None, proxy=None, browser_num=0):
        """Create a new SelScraper Thread.

        Args:
            rlock: To synchronize multiple SelScraper objects. If no threading.Rlock is given
                     it is assumed that no synchronization is needed. Mainly used for caching and fs interaction.
            queue: A queue to push scraped results to be consumed by a worker thread.
            captcha_lock: To sync captcha solving (stdin)
            proxy: Optional, if set, use the proxy to route all scrapign through it.
            browser_num: A unique, semantic number for each thread.
        """
        super().__init__()
        self.num_pages = Config['SCRAPING'].getint('num_of_pages')
        self.browser_type = Config['SELENIUM'].get('sel_browser', 'chrome').lower()
        logger.info('[+] SelScraper[{}] created. Number of keywords to scrape={}, using proxy={}, number of pages={}, browser_num={}'.format(self.browser_type, len(keywords), proxy, self.num_pages, browser_num))
        self.url = Config['SELENIUM'].get('sel_scraper_base_url',
                                    Config['GLOBAL'].get('base_search_url'))
        self.proxy = proxy
        self.browser_num = browser_num
        self.queue = queue
        self.rlock = rlock
        self.captcha_lock = captcha_lock
        self.keywords = set(keywords)
        self.ip = '127.0.0.1'
        self._parse_config()
        self._results = []

    def _parse_config(self):
        """Parse the config parameter given in the constructor.

        First apply some default values. The config parameter overwrites them, if given.
        """
        # How long to sleep (ins seconds) after every n-th request
        self.sleeping_ranges = dict()
        for line in Config['SELENIUM'].get('sleeping_ranges').split('\n'):
            assert line.count(';') == 1
            key, value = line.split(';')
            self.sleeping_ranges[int(key)] = tuple([int(offset.strip()) for offset in value.split(',')])

    def _largest_sleep_range(self, i):
        assert i >= 0
        if i != 0:
            s = sorted(self.sleeping_ranges.keys(), reverse=True)
            for n in s:
                if i % n == 0:
                    return self.sleeping_ranges[n]
        # sleep one second
        return (1, 2)

    def _maybe_crop(self, html):
        """Crop Google the HTML of  SERP pages.

        If we find the needle that indicates the beginning of the main content, use lxml to crop the selections.

        Args:
            html: The html to crop.

        Returns:
            The cropped html.
        """
        parsed = lxml.html.fromstring(html)
        for bad in parsed.xpath('//script|//style'):
            bad.getparent().remove(bad)

        return lxml.html.tostring(parsed)

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
                            self.element = WebDriverWait(self.webdriver, 5).until(EC.presence_of_element_located((By.NAME, "q")))
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

    def run(self):
        """The core logic of an GoogleScrape"""

        # Create the browser and align it according to its position and in maximally two rows
        if len(self.keywords) <= 0:
            return True

        if not self._get_webdriver():
            raise SeleniumMisconfigurationError('Aborting due to no available selenium webdriver.')

        if self.browser_type != 'browser_type':
            self.webdriver.set_window_size(400, 400)
            self.webdriver.set_window_position(400*(self.browser_num % 4), 400*(math.floor(self.browser_num//4)))

        for i, kw in enumerate(self.keywords):
            if not kw:
                continue
            write_kw = True
            next_url = ''
            for page_num in range(0, self.num_pages):
                if not next_url:
                    next_url = self.url
                self.webdriver.get(next_url)
                # match the largest sleep range
                j = random.randrange(*self._largest_sleep_range(i))
                if self.proxy:
                    logger.info('[i] Page number={}, ScraperThread({url}) ({ip}:{port} {} is sleeping for {} seconds...Next keyword: ["{kw}"]'.format(page_num, self._ident, j, url= next_url, ip=self.proxy.host, port=self.proxy.port, kw=kw))
                else:
                    logger.info('[i] Page number={}, ScraperThread({url}) ({} is sleeping for {} seconds...Next keyword: ["{}"]'.format(page_num, self._ident, j, kw, url=next_url))
                time.sleep(j)
                try:
                    self.element = WebDriverWait(self.webdriver, 10).until(EC.presence_of_element_located((By.NAME, "q")))
                except TimeoutException as e:
                    if not self.handle_request_denied():
                        open('/tmp/out.png', 'wb').write(self.webdriver.get_screenshot_as_png())
                        raise GoogleSearchError('`q` search input cannot be found.')

                if write_kw:
                    self.element.clear()
                    time.sleep(.25)
                    self.element.send_keys(kw + Keys.ENTER)
                    write_kw = False
                # Waiting until the keyword appears in the title may
                # not be enough. The content may still be off the old page.
                try:
                    WebDriverWait(self.webdriver, 10).until(EC.title_contains(kw))
                except TimeoutException as e:
                    logger.debug('Keyword not found in title: {}'.format(e))
                    continue

                try:
                    # wait until the next page link emerges
                    WebDriverWait(self.webdriver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#pnnext')))
                    next_url = self.webdriver.find_element_by_css_selector('#pnnext').get_attribute('href')
                except TimeoutException as te:
                    logger.debug('Cannot locate next page html id #pnnext')
                except WebDriverException as e:
                    # leave if no next results page is available
                    break

                # That's because we sleep explicitly one second, so the site and
                # whatever js loads all shit dynamically has time to update the
                # DOM accordingly.
                time.sleep(1.5)

                html = self._maybe_crop(self.webdriver.page_source)

                if self.rlock or self.queue:
                    # Lock for the sake that two threads write to same file (not probable)
                    self.rlock.acquire()
                    cache_results(html, kw, self.url)
                    self.rlock.release()
                    # commit in intervals specified in the config
                    self.queue.put(self._get_parse_links(html, kw, page_num=page_num+1, ip=self.ip))

                self._results.append(self._get_parse_links(html, kw, only_results=True).all_results)

        self.webdriver.close()

    def _get_parse_links(self, data, kw, only_results=False, page_num = 1, ip='127.0.0.1'):
        """Act the same as _parse_links, but just return the db data instead of inserting data into a connection or
        or building actual queries.

        [[lastrowid]] needs to be replaced with the last rowid from the database when inserting.

        Args:
            data: The html to parse.
            kw: The keywords that was used in the scrape.
            only_results: Whether only the parsed results should be returned.
            page_num: The Google page number of the parsed reqeust.
            ip: The ip address the request was issued.

        Returns:
            The data to insert in the database (serp_page and links table entries respectively)
        """

        parser = Parser(data)
        if only_results:
            return parser

        results = parser.links
        first = (page_num,
                 time.asctime(),
                 len(results),
                 parser.num_results() or '',
                 kw,
                 ip)

        second = []
        for result in results:
            second.append([
                result.link_title,
                result.link_url.geturl(),
                result.link_snippet,
                result.link_position,
                result.link_url.hostname
            ])

        return (first, second)

    @property
    def results(self):
        return self._results
