# -*- coding: utf-8 -*-

import threading
from urllib.parse import quote
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
    from selenium.common.exceptions import ElementNotVisibleException
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait  # available since 2.4.0
    from selenium.webdriver.support import expected_conditions as EC  # available since 2.26.0
    from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
except ImportError as ie:
    print(ie)
    sys.exit('You can install missing modules with `pip3 install [modulename]`')

from GoogleScraper.config import Config
from GoogleScraper.log import out, raise_or_log
from GoogleScraper.scraping import SearchEngineScrape, SeleniumSearchError, SeleniumMisconfigurationError, get_base_search_url_by_search_engine, MaliciousRequestDetected
from GoogleScraper.user_agents import random_user_agent

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
        'ask': '#paging div a.txt3.l_nu',
        'blekko': '',
        'duckduckgo': ''
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
        self.scrape_method = 'selenium'

        # get the base search url based on the search engine.
        self.base_search_url = get_base_search_url_by_search_engine(self.search_engine_name, self.scrape_method)
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

            dcap = dict(DesiredCapabilities.PHANTOMJS)
            # dcap["phantomjs.page.settings.userAgent"] = random_user_agent()

            self.webdriver = webdriver.PhantomJS(service_args=service_args, desired_capabilities=dcap)
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

        needles = self.malicious_request_needles[self.search_engine_name]

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
            self.starting_point = self.image_search_locations[self.search_engine_name]
        else:
            self.starting_point = self.base_search_url

        self.webdriver.get(self.starting_point)

    def _get_search_input_field(self):
        """Get the search input field for the current search_engine.

        Returns:
            A tuple to locate the search field as used by seleniums function presence_of_element_located()
        """
        return self.input_field_selectors[self.search_engine_name]

    def _wait_until_search_input_field_appears(self, max_wait=5):
        """Waits until the search input field can be located for the current search engine

        Args:
            max_wait: How long to wait maximally before returning False.

        Returns: False if the search input field could not be located within the time
                or the handle to the search input field.
        """

        def find_visible_search_input(driver):
            input_field = driver.find_element(*self._get_search_input_field())
            return input_field

        try:
            search_input = WebDriverWait(self.webdriver, max_wait).until(find_visible_search_input)
            return search_input
        except TimeoutException as e:
            logger.error('{}: TimeoutException waiting for search input field: {}'.format(self.name, e))
            return False


    def _wait_until_search_input_field_contains_query(self, max_wait=5):
        """Waits until the search input field contains the query.

        Args:
            max_wait: How long to wait maximally before returning False.
        """

        def find_query_in_input(driver):
            input_field = driver.find_element(*self._get_search_input_field())
            return input_field.get_attribute('value') == self.query

        try:
            WebDriverWait(self.webdriver, max_wait).until(find_query_in_input)
        except TimeoutException as e:
            logger.error('{}: TimeoutException waiting for query in input field: {}'.format(self.name, e))

    def _goto_next_page(self):
        """Click the next page element.
        """
        element = self._find_next_page_element()

        if hasattr(element, 'click'):
            next_url = element.get_attribute('href')
            try:
                element.click()
            except WebDriverException:
                # See http://stackoverflow.com/questions/11908249/debugging-element-is-not-clickable-at-point-error
                # first move mouse to the next element, some times the element is not visibility, like blekko.com
                selector = self.next_page_selectors[self.search_engine_name]
                if selector:
                    try:
                        next_element = WebDriverWait(self.webdriver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                        webdriver.ActionChains(self.webdriver).move_to_element(next_element).perform()
                        # wait until the next page link emerges
                        WebDriverWait(self.webdriver, 8).until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))
                        element = self.webdriver.find_element_by_css_selector(selector)
                        next_url = element.get_attribute('href')
                        element.click()
                    except WebDriverException:
                        pass

            return next_url

        return element

    def _find_next_page_element(self):
        """Finds the element that locates the next page for any search engine.

        Returns:
            The element that needs to be clicked to get to the next page.
        """
        if self.search_type == 'normal':
            selector = self.next_page_selectors[self.search_engine_name]
            try:
                # wait until the next page link emerges
                WebDriverWait(self.webdriver, 5).until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))
                return self.webdriver.find_element_by_css_selector(selector)
            except TimeoutException as te:
                out('{}: Cannot locate next page element: {}'.format(self.name, te), lvl=4)
                return False
            except WebDriverException as e:
                out('{} Cannot locate next page element: {}'.format(self.name, e), lvl=4)
                return False

        elif self.search_type == 'image':
            self.page_down()
            return True

    def wait_until_serp_loaded(self):
        """
        First tries to wait until next page selector is located. If this fails, waits
        until the title contains the query.

        """
        if self.search_type == 'normal':
            selector = self.next_page_selectors[self.search_engine_name]
            try:
                WebDriverWait(self.webdriver, 5).until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))
            except (TimeoutException, WebDriverException) as e:
                self.wait_until_title_contains_keyword()

        elif self.search_type == 'image':
            self.wait_until_title_contains_keyword()

        else:
            self.wait_until_title_contains_keyword()


    def wait_until_title_contains_keyword(self):
        try:
            WebDriverWait(self.webdriver, 5).until(EC.title_contains(self.query))
        except TimeoutException as e:
            out(SeleniumSearchError('{}: Keyword "{}" not found in title: {}'.format(self.name, self.query, self.webdriver.title)), lvl=4)


    def search(self):
        """Search with webdriver.

        Fills out the search form of the search engine for each keyword.
        Clicks the next link while pages_per_keyword is not reached.
        """
        for self.query, self.pages_per_keyword in self.jobs.items():

            self.search_input = self._wait_until_search_input_field_appears()

            if self.search_input is False and Config['PROXY_POLICY'].getboolean('stop_on_detection'):
                self.status = 'Malicious request detected'
                super().after_search()
                return

            if self.search_input is False:
                self.search_input = self.handle_request_denied()

            if self.search_input:
                self.search_input.clear()
                time.sleep(.25)

                try:
                    self.search_input.send_keys(self.query + Keys.ENTER)
                except ElementNotVisibleException as e:
                    time.sleep(2)
                    self.search_input.send_keys(self.query + Keys.ENTER)

                self.requested_at = datetime.datetime.utcnow()
            else:
                out('{}: Cannot get handle to the input form for keyword {}.'.format(self.name, self.query), lvl=4)
                continue

            super().detection_prevention_sleep()
            super().keyword_info()

            for self.page_number in self.pages_per_keyword:

                self.wait_until_serp_loaded()

                try:
                    self.html = self.webdriver.execute_script('return document.body.innerHTML;')
                except WebDriverException as e:
                    self.html = self.webdriver.page_source

                super().after_search()

                # Click the next page link not when leaving the loop
                # in the next iteration.
                if self.page_number in self.pages_per_keyword:
                    self.next_url = self._goto_next_page()
                    self.requested_at = datetime.datetime.utcnow()
                    
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
            raise_or_log('{}: Aborting due to no available selenium webdriver.'.format(self.name), exception_obj=SeleniumMisconfigurationError)

        try:
            self.webdriver.set_window_size(400, 400)
            self.webdriver.set_window_position(400*(self.browser_num % 4), 400*(math.floor(self.browser_num//4)))
        except WebDriverException as e:
            out('Cannot set window size: {}'.format(e), lvl=4)

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
    """
    Duckduckgo is a little special since new results are obtained by ajax.
    next page thus is then to scroll down.

    Furthermore duckduckgo.com doesn't seem to work with Phantomjs. Maybe they block it, but I
    don't know how ??!

    It cannot be the User-Agent, because I already tried this.
    """

    def __init__(self, *args, **kwargs):
        SelScrape.__init__(self, *args, **kwargs)
        self.largest_id = 0

    def _goto_next_page(self):
        super().page_down()
        return 'No more results' not in self.html
    
    def wait_until_serp_loaded(self):
        super()._wait_until_search_input_field_contains_query()

class BlekkoSelScrape(SelScrape):
    def __init__(self, *args, **kwargs):
        SelScrape.__init__(self, *args, **kwargs)
        
    def _goto_next_page(self):
        pass

class AskSelScrape(SelScrape):
    def __init__(self, *args, **kwargs):
        SelScrape.__init__(self, *args, **kwargs)

    def wait_until_serp_loaded(self):
        
        def wait_until_keyword_in_url(driver):
            try:
                return quote(self.query) in driver.current_url or\
                       self.query.replace(' ', '+') in driver.current_url
            except WebDriverException as e:
                pass
            
        WebDriverWait(self.webdriver, 5).until(wait_until_keyword_in_url)

