# -*- coding: utf-8 -*-

import threading
import json
import logging
import datetime
import time
import math
import re
import sys

try:
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait  # available since 2.4.0
    from selenium.webdriver.support import expected_conditions as EC  # available since 2.26.0
except ImportError as ie:
    print(ie)
    sys.exit('You can install missing modules with `pip3 install [modulename]`')

from GoogleScraper.scraping import SearchEngineScrape, SeleniumSearchError, SeleniumMisconfigurationError, get_base_search_url_by_search_engine, GoogleSearchError, MaliciousRequestDetected
from GoogleScraper.config import Config
from GoogleScraper.log import out

logger = logging.getLogger('GoogleScraper')


def get_selenium_scraper_by_search_engine_name(search_engine_name, *args, **kwargs):
    """Get the appropriate selenium scraper for the given search engine name.

    Args:
        search_engine_name: The search engine name.
        args: The arguments for the target search engine instance creation.
        kwargs: The keyword arguments for the target search engine instance creation.
    Returns;
        Either a concrete SelScrape instance specific for the given search engine or the abstract SelScrape object.
    """
    class_name = search_engine_name[0].upper() + search_engine_name[1:].lower() + 'SelScrape'
    ns = globals()
    if class_name in ns:
        return ns[class_name](*args, **kwargs)

    return SelScrape(*args, **kwargs)

class SelScrape(SearchEngineScrape, threading.Thread):
    """Instances of this class make use of selenium browser objects to query the search engines on a high level.
    """

    next_page_selectors = {
        'google': '#pnnext',
        'yandex': '.pager__button_kind_next',
        'bing': '.sb_pagN',
        'yahoo': '#pg-next',
        'baidu': '.n',
        'ask': '#paging div a.txt3.l_nu'
    }

    input_field_selectors = {
        'google': (By.NAME, 'q'),
        'yandex': (By.NAME, 'text'),
        'bing': (By.NAME, 'q'),
        'yahoo': (By.NAME, 'p'),
        'baidu': (By.NAME, 'wd'),
        'duckduckgo': (By.NAME, 'q'),
        'ask': (By.NAME, 'q'),
        'blekko': (By.NAME, 'q'),
    }

    normal_search_locations = {
        'google': 'https://www.google.com/',
        'yandex': 'http://www.yandex.ru/',
        'bing': 'http://www.bing.com/',
        'yahoo': 'https://yahoo.com/',
        'baidu': 'http://baidu.com/',
        'duckduckgo': 'https://duckduckgo.com/',
        'ask': 'http://ask.com/',
        'blekko': 'http://blekko.com/'
    }

    image_search_locations = {
        'google': 'https://www.google.com/imghp',
        'yandex': 'http://yandex.ru/images/',
        'bing': 'https://www.bing.com/?scope=images',
        'yahoo': 'http://images.yahoo.com/',
        'baidu': 'http://image.baidu.com/',
        'duckduckgo': None, # duckduckgo doesnt't support direct image search
        'ask': 'http://www.ask.com/pictures/',
        'blekko': None,
    }

    def __init__(self, *args, captcha_lock=None, browser_num=1, **kwargs):
        """Create a new SelScraper thread Instance.

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
        self.scrapemethod = 'selenium'

        # get the base search url based on the search engine.
        self.base_search_url = get_base_search_url_by_search_engine(self.search_engine, self.scrapemethod)
        super().instance_creation_info(self.__class__.__name__)

    def set_proxy(self):
        """Install a proxy on the communication channel."""

    def switch_proxy(self, proxy):
        """Switch the proxy on the communication channel."""

    def proxy_check(self):
        assert self.proxy and self.webdriver, 'Scraper instance needs valid webdriver and proxy instance to make the proxy check'

        online = False
        status = 'Proxy check failed: {host}:{port} is not used while requesting'.format(**self.proxy.__dict__)
        ipinfo = {}

        try:
            self.webdriver.get(Config['GLOBAL'].get('proxy_info_url'))
            try:
                text = re.search(r'(\{.*?\})', self.webdriver.page_source, flags=re.DOTALL).group(0)
                ipinfo = json.loads(text)
            except ValueError as v:
                logger.critical(text)

        except Exception as e:
            status = str(e)

        if 'ip' in ipinfo and ipinfo['ip']:
            online = True
            status = 'Proxy is working.'
        else:
            logger.warning(status)

        super().update_proxy_status(status, ipinfo, online)

        return online

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
            # we don't have a chrome executable or a chrome webdriver installed
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
            return True
        except WebDriverException as e:
            logger.error(e)
        return False

    def handle_request_denied(self):
        """Checks whether Google detected a potentially harmful request.

        Whenever such potential abuse is detected, Google shows an captcha.
        This method just blocks as long as someone entered the captcha in the browser window.
        When the window is not visible (For example when using PhantomJS), this method
        makes a png from the html code and shows it to the user, which should enter it in a command
        line.

        Returns:
            The search input field.

        Raises:
            MaliciousRequestDetected when there was not way to stp Google From denying our requests.
        """
        # selenium webdriver objects have no status code :/
        super().handle_request_denied('400')

        needles = self.malicious_request_needles[self.search_engine]

        if needles and needles['inurl'] in self.webdriver.current_url and needles['inhtml'] in self.webdriver.page_source:

            if Config['SELENIUM'].getboolean('manual_captcha_solving', False):
                with self.captcha_lock:
                    import tempfile
                    tf = tempfile.NamedTemporaryFile('wb')
                    tf.write(self.webdriver.get_screenshot_as_png())
                    import webbrowser
                    webbrowser.open('file://{}'.format(tf.name))
                    solution = input('enter the captcha please...')
                    self.webdriver.find_element_by_name('submit').send_keys(solution + Keys.ENTER)
                    try:
                        self.search_input = WebDriverWait(self.webdriver, 5).until(
                                EC.visibility_of_element_located(self._get_search_input_field()))
                    except TimeoutException as e:
                        raise MaliciousRequestDetected('Requesting with this ip is not possible at the moment.')
                    tf.close()

            else:
                # Just wait until the user solves the captcha in the browser window
                # 10 hours if needed :D
                out('Waiting for user to solve captcha', lvl=1)
                return self._wait_until_search_input_field_appears(10*60*60)


    def build_search(self):
        """Build the search for SelScrapers"""
        assert self.webdriver, 'Webdriver needs to be ready to build the search'

        self.starting_point = None

        if Config['SCRAPING'].get('search_type', 'normal') == 'image':
            self.starting_point = self.image_search_locations[self.search_engine]
        else:
            self.starting_point = self.base_search_url

        self.webdriver.get(self.starting_point)


    def _get_search_input_field(self):
        """Get the search input field for the current search_engine.

        Returns:
            A tuple to locate the search field as used by seleniums function presence_of_element_located()
        """
        return self.input_field_selectors[self.search_engine]

    def _wait_until_search_input_field_appears(self, max_wait=5):
        """Waits until the search input field can be located for the current search engine

        Args:
            max_wait: How long to wait maximally before returning False.

        Returns: False if the search input field could not be located within the time
                or the handle to the search input field.
        """
        try:
            search_input = WebDriverWait(self.webdriver, max_wait).until(
                EC.visibility_of_element_located(self._get_search_input_field()))
            return search_input
        except TimeoutException as e:
            return False

    def _goto_next_page(self):
        """Finds the url that locates the next page for any search_engine.

        Returns:
            The href attribute of the next_url for further results.
        """
        if self.search_type == 'normal':
            selector = self.next_page_selectors[self.search_engine]
            try:
                # wait until the next page link emerges
                WebDriverWait(self.webdriver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                element = self.webdriver.find_element_by_css_selector(selector)
                next_url = element.get_attribute('href')
                element.click()
                return next_url
            except TimeoutException as te:
                logger.warning('Cannot locate next page element: {}'.format(te))
                return False
            except WebDriverException as e:
                logger.warning('Cannot locate next page element: {}'.format(e))
                return False

        elif self.search_type == 'image':
            self.page_down()
            return True

    def wait_until_serp_loaded(self):
        # Waiting until the keyword appears in the title may
        # not be enough. The content may still be from the old page.
        try:
            WebDriverWait(self.webdriver, 5).until(EC.title_contains(self.current_keyword))
        except TimeoutException as e:
            logger.error(SeleniumSearchError('Keyword "{}" not found in title: {}'.format(self.current_keyword, self.webdriver.title)))

    def search(self):
        """Search with webdriver.

        Fills out the search form of the search engine for each keyword.
        Clicks the next link while num_pages_per_keyword is not reached.
        """
        for self.current_keyword in self.keywords:

            self.search_input = self._wait_until_search_input_field_appears()

            if self.search_input is False:
                self.search_input = self.handle_request_denied()

            if self.search_input:
                self.search_input.clear()
                time.sleep(.25)
                self.search_input.send_keys(self.current_keyword + Keys.ENTER)
                self.current_request_time = datetime.datetime.utcnow()
            else:
                logger.warning('Cannot get handle to the input form for keyword {}.'.format(self.current_keyword))
                continue

            super().detection_prevention_sleep()
            super().keyword_info()

            for self.current_page in range(1, self.num_pages_per_keyword + 1):

                self.wait_until_serp_loaded()

                try:
                    self.html = self.webdriver.execute_script('return document.body.innerHTML;')
                except WebDriverException as e:
                    self.html = self.webdriver.page_source

                super().after_search()

                # Click the next page link not when leaving the loop
                # in the next iteration.
                if self.current_page < self.num_pages_per_keyword:
                    self.next_url = self._goto_next_page()
                    self.current_request_time = datetime.datetime.utcnow()
                    
                    if not self.next_url:
                        break

    def page_down(self):
        """Scrolls down a page with javascript.

        Used for next page in image search mode or when the 
        next results are obtained by scrolling down a page.
        """
        js = '''
        var w = window,
            d = document,
            e = d.documentElement,
            g = d.getElementsByTagName('body')[0],
            y = w.innerHeight|| e.clientHeight|| g.clientHeight;

        window.scrollBy(0,y);
        return y;
        '''

        self.webdriver.execute_script(js)

    def run(self):
        """Run the SelScraper."""

        if not self._get_webdriver():
            raise SeleniumMisconfigurationError('Aborting due to no available selenium webdriver.')

        try:
            self.webdriver.set_window_size(400, 400)
            self.webdriver.set_window_position(400*(self.browser_num % 4), 400*(math.floor(self.browser_num//4)))
        except WebDriverException as e:
            logger.error(e)

        super().before_search()

        if self.startable:
            self.build_search()
            self.search()

        if self.webdriver:
            self.webdriver.close()
            
            
"""
For most search engines, the normal SelScrape works perfectly, but sometimes
the scraping logic is different for other search engines.

Duckduckgo loads new results on the fly (via ajax) and doesn't support any "next page"
link. Other search engines like gekko.com have a completely different SERP page format.

That's why we need to inherit from SelScrape for specific logic that only applies for the given
search engine.

The following functionality may differ in particular:

    - _goto_next_page()
    - _get_search_input()
    - _wait_until_search_input_field_appears()
    - _handle_request_denied()
    - wait_until_serp_loaded()
"""

class DuckduckgoSelScrape(SelScrape):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.largest_id = 0

    def _goto_next_page(self):
        super().page_down()
        return 'No more results' not in self.html
    
    def wait_until_serp_loaded(self):
        def new_results(driver):
            try:
                elements = driver.find_elements_by_css_selector('[id*="r1-"]')
                if elements:
                    i = sorted([int(e.get_attribute('id')[3:]) for e in elements])[-1]
                    return i > self.largest_id
                else:
                    return False
            except WebDriverException:
                pass

        try:
            WebDriverWait(self.webdriver, 5).until(new_results)
        except TimeoutException as e:
            pass

        elements = self.webdriver.find_elements_by_css_selector('[id*="r1-"]')
        try:
            self.largest_id = sorted([int(e.get_attribute('id')[3:]) for e in elements])[-1]
        except:
            self.largest_id = 0
        

class BlekkoSelScrape(SelScrape):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def _goto_next_page(self):
        pass

class AskSelScrape(SelScrape):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def wait_until_serp_loaded(self):
        
        def wait_until_keyword_in_url(driver):
            try:
                return self.current_keyword in driver.current_url
            except WebDriverException as e:
                pass
            
        WebDriverWait(self.webdriver, 5).until(wait_until_keyword_in_url)

