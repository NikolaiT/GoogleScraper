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
from GoogleScraper.caching import get_cached, cache_results, cached_file_name
from GoogleScraper.config import Config
from GoogleScraper.parsing import Parser
import GoogleScraper.google_search_params
import webbrowser
import tempfile

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
    selenium framework or using the Twisted HTTP client.
    
    The next layer is the concrete implementation of the search functionality
    of the specific search engines. This is not done in a next derivation
    hierarchy (otherwise there would be a lot of base classes for each
    search engine and thus quite some boilerplate overhead).
    Instead we determine our search engine over the internal state
    (An attribute name self.search_engine) and handle the different search
    engine in the search function.    
    """

    def __init__(self, search_engine=None, search_type=None,):
        if not search_engine:
            self.search_engine = Config['SCRAPING'].get('search_engine', 'Google')
        else:
            self.search_engine = search_engine

        self.search_engine = self.search_engine.lower()

        if not search_type:
            self.search_type = Config['SCRAPING'].get('search_type', 'normal')
        else:
            self.search_type = search_type

    
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
        """Behaviour when search engines dedect our scraping."""
        

def timer_support(Class):
    """Adds support for timeable threads.

    In python versions prior to 3.3, threading.Timer
    seems to be a function that returns an instance
    of _Timer which is the class we want.
    """
    if isinstance(threading.Timer, (types.FunctionType, types.BuiltinFunctionType)) \
            and hasattr(threading, '_Timer'):
        timer_class = threading._Timer
    else:
        timer_class = threading.Timer

    class Cls(timer_class):
        def __init__(self, *args, **kwargs):
            # Signature of Timer or _Timer
            # def __init__(self, interval, function, args=None, kwargs=None):
            super(Cls, self).__init__(kwargs.get('interval'), self._search)
            self._init(*args, **kwargs)

    # add all attributes excluding __init__() and __dict__
    for name, attribute in Class.__dict__.items():
        if name not in ('__init__', '__dict__'):
            try:
                setattr(Cls, name, attribute)
            except AttributeError as ae:
                logger.error(ae)
    return Cls


@timer_support
class HttpScrape(SearchEngineScrape):
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
    # Keep the User-Agents updated. Last update: 17th february 14
    # Get them here: http://techblog.willshouse.com/2012/01/03/most-common-user-agents/
    USER_AGENTS = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_1) AppleWebKit/537.73.11 (KHTML, like Gecko) Version/7.0.1 Safari/537.73.11',
        'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/32.0.1700.76 Safari/537.36',
        'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:26.0) Gecko/20100101 Firefox/26.0',
        'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/32.0.1700.107 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/32.0.1700.77 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/32.0.1700.107 Safari/537.36',
        'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/32.0.1700.102 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/32.0.1700.102 Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 7_0_4 like Mac OS X) AppleWebKit/537.51.1 (KHTML, like Gecko) Version/7.0 Mobile/11B554a Safari/9537.53',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:26.0) Gecko/20100101 Firefox/26.0',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:26.0) Gecko/20100101 Firefox/26.0',
        'Mozilla/5.0 (iPad; CPU OS 7_0_4 like Mac OS X) AppleWebKit/537.51.1 (KHTML, like Gecko) Version/7.0 Mobile/11B554a Safari/9537.53',
        'Mozilla/5.0 (Windows NT 6.1; rv:26.0) Gecko/20100101 Firefox/26.0',
        'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/32.0.1700.76 Safari/537.36'
    ]

    HEADERS = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'close',
        'DNT': '1'
    }

    def __init__(self, *args, **kwargs):
        """Dummy constructor to be modified by the timer_support class decorator."""
        pass

    def _init(self, keyword, num_page=0, interval=0.0, search_params={}):
        """Initialises an object responsible for scraping one SERP page.

        Args:
            keyword: Which keyword to scrape for.
            num_page: The page number.
            interval: The amount of seconds to wait until executing run()
            search_params: A dictionary with additional search params. The default search params are updated with this parameter.
        """

        self.parser = None
        self.keyword = keyword
        self.search_params = GoogleScraper.google_search_params.search_params
        self.num_results_per_page = Config['SCRAPING'].getint('num_results_per_page')
        self.num_page = num_page

        if proxy:
            self._set_proxy(proxy)

        self.requests = __import__('requests')

        # Maybe update the default search params when the user has supplied a dictionary
        if search_params is not None and isinstance(search_params, dict):
            self.search_params.update(search_params)

        self.search_results = {
            'cache_file': None,  # A path to a file that caches the results.
            'search_keyword': self.keyword,  # The query keyword
        }

    def _set_proxy(self, proxy):
        """Setup a socks connection for the socks module bound to the instance.

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
        socks.setdefaultproxy(pmapping.get(proxy.proto), proxy.host, int(proxy.port), rdns=True)
        socks.wrap_module(socket)
        socket.create_connection = create_connection

    def reset_search_params(self):
        """Reset all search params to None.

        Such that they won't be used in the query
        """
        for k, v in self.search_params.items():
            self.search_params[k] = None

    def _build_query(self, rand=False):
        """Build the headers and params for the GET request for the Google server.

        If random is True, several headers (like the UA) are chosen
        randomly.

        There are currently four different Google searches supported:
        - The normal web search: 'normal'
        - image search: 'image'
        - video search: 'video'
        - news search: 'news'

        Args:
            rand: Whether to use an random user-agent. By default set to False.
        """

        # params used by all search-types
        self.search_params.update(
            {
                'q': self.keyword,
            })

        if self.search_type == 'normal':
            # The normal web search. That's what you probably want
            self.search_params.update(
                {
                    'num': str(self.num_results_per_page),
                    'start': str(int(self.num_results_per_page) * int(self.num_page))
                })
        elif self.search_type == 'image':
            # Image raw search url for keyword 'cat' in mozilla 27.0.1
            # 'q' and tbs='isch' are sufficient for a search
            # https://www.google.com/search?q=cat&client=firefox-a&rls=org.mozilla:en-US:official&channel=sb&noj=1&source=lnms&tbm=isch&sa=X&ei=XX8dU93kMMbroAS5_IGwBw&ved=0CAkQ_AUoAQ&biw=1920&bih=881
            # Link that Chromium generates: https://www.google.com/search?site=imghp&tbm=isch&source=hp&biw=1536&bih=769&q=good+view&oq=good+view&gs_l=img.3..0l10.18.3212.0.3351.17.16.1.0.0.0.355.2509.3j9j0j3.15.0....0...1ac.1.37.img..6.11.1342.tSOKFxzvFbE
            self.reset_search_params()
            self.search_params.update(
                {
                    'q': self.keyword,
                    'oq': self.keyword,
                    'site': 'imghp',
                    'tbm': 'isch',
                    'source': 'hp',
                    #'sa': 'X',
                    'biw': 1920,
                    'bih': 881
                })
        elif self.search_type == 'video':
            # Video search raw url with keyword 'cat' in mozilla 27.0.1
            # 'q' and tbs='vid' are sufficient for a search
            # https://www.google.com/search?q=cat&client=firefox-a&rls=org.mozilla:en-US:official&channel=sb&noj=1&tbm=vid&source=lnms&sa=X&ei=DoAdU9uxHdGBogTp8YLACQ&ved=0CAoQ_AUoAg&biw=1920&bih=881&dpr=1
            self.search_params.update(
                {
                    'num': str(self.num_results_per_page),
                    'start': str(int(self.num_results_per_page) * int(self.num_page)),
                    'tbm': 'vid',
                    'source': 'lnms',
                    'sa': 'X',
                    'biw': 1920,
                    'bih': 881
                })
        elif self.search_type == 'news':
            # pretty much as above;
            # 'q' and tbs='nws' are perfectly fine for a news search
            # But there is a more elaborate Google news search with a different URL on: https://news.google.com/nwshp?
            # this code only handles the standard search news
            self.search_params.update(
                {
                    'num': str(self.num_results_per_page),
                    'start': str(int(self.num_results_per_page) * int(self.num_page)),
                    'tbm': 'nws',
                    'source': 'lnms',
                    'sa': 'X'
                })

        if rand:
            self.HEADERS['User-Agent'] = random.choice(self.USER_AGENTS)

    def browserview(self, html):
        """View html in browser.

        Args:
            html: The html to inspect in the default browser.
        """
        tf = tempfile.NamedTemporaryFile(delete=False)
        tf.write(html.encode())
        webbrowser.open(tf.name)

    def _search(self):
        """The actual search and parsing of the results.

        Private, internal method.
        Parsing is done with lxml and cssselect. The html structure of the Google Search
        results may change over time. Effective: February 2014

        There are several parts of a SERP results page the average user is most likely interested:

        (Probably in this order)
        - Non-advertisement links, as well as their little snippet and title
        - The message that indicates how many results were found. For example: "About 834,000,000 results (0.39 seconds)"
        - Advertisement search results (links, titles, snippets like above)
        """
        self._build_query()

        # After building the query, all parameters are set, so we know what we're requesting.
        logger.debug("Created new GoogleScrape object with searchparams={}".format(pprint.pformat(self.search_params)))

        html = get_cached(self.keyword, Config['GLOBAL'].get('base_search_url'), params=self.search_params)
        self.search_results['cache_file'] = os.path.join(Config['GLOBAL'].get('cachedir'), cached_file_name(self.keyword, Config['GLOBAL'].get('base_search_url'), self.search_params))

        if not html:
            try:
                base_url=Config['GLOBAL'].get('base_search_url')

                if Config['GLOBAL'].getint('verbosity', 0) > 1:
                    logger.info('[HTTP] Base_url: {base_url}, headers={headers}, params={params}'.format(
                        base_url=base_url,
                        headers=self.HEADERS,
                        params=self.search_params
                    ))

                r = self.requests.get(Config['GLOBAL'].get('base_search_url'), headers=self.HEADERS,
                                 params=self.search_params, timeout=3.0)

                logger.debug("Scraped with url: {} and User-Agent: {}".format(r.url, self.HEADERS['User-Agent']))

            except self.requests.ConnectionError as ce:
                logger.error('Network problem occurred {}'.format(ce))
                raise ce
            except self.requests.Timeout as te:
                logger.error('Connection timeout {}'.format(te))
                raise te

            if not r.ok:
                logger.error('HTTP Error: {}'.format(r.status_code))
                return False

            html = r.text

            if Config['HTTP'].getboolean('view', False):
                self.browserview(html)

            # cache fresh results
            cache_results(html, self.keyword, url=Config['GLOBAL'].get('base_search_url'), params=self.search_params)
            self.search_results['cache_file'] = os.path.join(Config['GLOBAL'].get('cachedir'), cached_file_name(self.keyword, Config['GLOBAL'].get('base_search_url'), self.search_params))

        self.parser = Parser(html, searchtype=self.search_type)
        self.search_results.update(self.parser.all_results)

    @property
    def results(self):
        return self.search_results


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
