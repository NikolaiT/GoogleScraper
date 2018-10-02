# -*- coding: utf-8 -*-

import tempfile
import threading
from urllib.parse import quote
import json
import datetime
import time
import math
import random
import re
import sys
import os

try:
    from fake_useragent import UserAgent
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.common.exceptions import ElementNotVisibleException
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait  # available since 2.4.0
    from selenium.webdriver.support import expected_conditions as EC  # available since 2.26.0
    from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
except ImportError as ie:
    print(ie)
    sys.exit('You can install missing modules with `pip3 install [modulename]`')

from GoogleScraper.scraping import SearchEngineScrape, SeleniumSearchError, get_base_search_url_by_search_engine, MaliciousRequestDetected
from GoogleScraper.user_agents import random_user_agent
import logging


logger = logging.getLogger(__name__)


class NotSupportedException(Exception):
    pass


def check_detection(config, search_engine_name):
    """
    Checks whether the search engine specified by search_engine_name 
    blocked us.
    """
    status = ''
    chromedriver = config.get('chromedriver_path', '/usr/bin/chromedriver')

    options = webdriver.ChromeOptions()
    options.add_argument('headless')
    options.add_argument('window-size=1200x600')

    browser = webdriver.Chrome(chrome_options=options, executable_path=chromedriver)

    if search_engine_name == 'google': 
        url = get_base_search_url_by_search_engine(config, 'google', 'selenium')
        browser.get(url)

        def check(browser, status):
            needles = SearchEngineScrape.malicious_request_needles['google']

            if needles['inurl'] in browser.current_url and needles['inhtml'] in browser.page_source:
                status += 'Google is asking for a captcha! '
                code = 'DETECTED'
            else:
                status += 'No captcha prompt detected. '
                code = 'UNDETECTED'

            return (code, status)

        search_input = None
        try:
            search_input = WebDriverWait(browser, 5).until(
                EC.visibility_of_element_located((By.NAME, 'q')))
            status += 'Got a search input field. '
        except TimeoutException:
            status += 'No search input field located after 5 seconds. '
            return check(browser, status)

        try:
            # random query
            search_input.send_keys('President of Finland'+ Keys.ENTER)
            status += 'Google Search successful! '
        except WebDriverException:
            status += 'Cannot make a google search! '
            return check(browser, status)

        return check(browser, status)

    else:
        raise NotImplementedError('Detection check only implemented for Google Right now.')

    browser.quit()

    return status


def get_selenium_scraper_by_search_engine_name(config, search_engine_name, *args, **kwargs):
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
        return ns[class_name](config, *args, **kwargs)

    return SelScrape(config, *args, **kwargs)


class SelScrape(SearchEngineScrape, threading.Thread):
    """Instances of this class make use of selenium browser
       objects to query the search engines on a high level.
    """

    next_page_selectors = {
        'google': '#pnnext',
        'yandex': '.pager__item_kind_next',
        'bing': '.sb_pagN',
        'yahoo': '#pg-next',
        'baidu': '.n',
        'ask': '#paging div a.txt3.l_nu',
        'blekko': '',
        'duckduckgo': '',
        'googleimg': '#pnnext',
        'baiduimg': '.n',
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
        'google': (By.NAME, 'q'),
        'googleimg': (By.NAME, 'as_q'),
        'baiduimg': (By.NAME, 'word'),
    }

    param_field_selectors = {
        'googleimg': {
            'image_type': (By.ID, 'imgtype_input'),
            'image_size': (By.ID, 'imgsz_input'),
        },
    }

    search_params = {
        'googleimg': {
            'image_type': None,
            'image_size': None,
        },
    }

    normal_search_locations = {
        'google': 'https://www.google.com/',
        'yandex': 'http://www.yandex.ru/',
        'bing': 'http://www.bing.com/',
        'yahoo': 'https://yahoo.com/',
        'baidu': 'http://baidu.com/',
        'duckduckgo': 'https://duckduckgo.com/',
        'ask': 'http://ask.com/',
        'blekko': 'http://blekko.com/',
    }

    image_search_locations = {
        'google': 'https://www.google.com/imghp',
        'yandex': 'http://yandex.ru/images/',
        'bing': 'https://www.bing.com/?scope=images',
        'yahoo': 'http://images.yahoo.com/',
        'baidu': 'http://image.baidu.com/',
        'duckduckgo': None,  # duckduckgo doesnt't support direct image search
        'ask': 'http://www.ask.com/pictures/',
        'blekko': None,
        'googleimg':'https://www.google.com/advanced_image_search',
        'baiduimg': 'http://image.baidu.com/',
    }

    def __init__(self, config, *args, captcha_lock=None, browser_num=1, **kwargs):
        """Create a new SelScraper thread Instance.

        Args:
            captcha_lock: To sync captcha solving (stdin)
            proxy: Optional, if set, use the proxy to route all scrapign through it.
            browser_num: A unique, semantic number for each thread.
        """
        self.search_input = None

        threading.Thread.__init__(self)
        SearchEngineScrape.__init__(self, config, *args, **kwargs)

        self.browser_type = self.config.get('sel_browser', 'chrome').lower()
        self.browser_mode = self.config.get('browser_mode', 'headless').lower()
        self.browser_num = browser_num
        self.captcha_lock = captcha_lock
        self.scrape_method = 'selenium'

        # number of tabs per instance
        self.number_of_tabs = self.config.get('num_tabs', 1)

        self.xvfb_display = self.config.get('xvfb_display', None)

        self.search_param_values = self._get_search_param_values()

        self.user_agent = UserAgent()

        # get the base search url based on the search engine.
        self.base_search_url = get_base_search_url_by_search_engine(self.config, self.search_engine_name, self.scrape_method)
        super().instance_creation_info(self.__class__.__name__)


    def switch_to_tab(self, tab_number):
        """Switch to tab identified by tab_number

        https://stackoverflow.com/questions/46425797/opening-link-in-the-new-tab-and-switching-between-tabs-selenium-webdriver-pyt
        https://gist.github.com/lrhache/7686903
        """
        assert tab_number < self.number_of_tabs

        first_link = first_result.find_element_by_tag_name('a')

        # Save the window opener (current window, do not mistaken with tab... not the same)
        main_window = browser.current_window_handle

        # Open the link in a new tab by sending key strokes on the element
        # Use: Keys.CONTROL + Keys.SHIFT + Keys.RETURN to open tab on top of the stack 
        first_link.send_keys(Keys.CONTROL + Keys.RETURN)

        # Switch tab to the new tab, which we will assume is the next one on the right
        browser.find_element_by_tag_name('body').send_keys(Keys.CONTROL + Keys.TAB)
            
        # Put focus on current window which will, in fact, put focus on the current visible tab
        browser.switch_to_window(main_window)

        # do whatever you have to do on this page, we will just got to sleep for now
        sleep(2)

        # Close current tab
        browser.find_element_by_tag_name('body').send_keys(Keys.CONTROL + 'w')

        # Put focus on current window which will be the window opener
        browser.switch_to_window(main_window)


    def set_proxy(self):
        """Install a proxy on the communication channel."""

    def switch_proxy(self, proxy):
        """Switch the proxy on the communication channel."""

    def proxy_check(self, proxy):
        assert self.proxy and self.webdriver, 'Scraper instance needs valid webdriver and proxy instance to make the proxy check'

        online = False
        status = 'Proxy check failed: {host}:{port} is not used while requesting'.format(**self.proxy.__dict__)
        ipinfo = {}

        try:
            self.webdriver.get(self.config.get('proxy_info_url'))
            try:
                text = re.search(r'(\{.*?\})', self.webdriver.page_source, flags=re.DOTALL).group(0)
                ipinfo = json.loads(text)
            except ValueError as v:
                logger.critical(v)

        except Exception as e:
            status = str(e)

        if 'ip' in ipinfo and ipinfo['ip']:
            online = True
            status = 'Proxy is working.'
        else:
            logger.warning(status)

        super().update_proxy_status(status, ipinfo, online)

        return online


    def _save_debug_screenshot(self):
        """
        Saves a debug screenshot of the browser window to figure
        out what went wrong.
        """
        tempdir = tempfile.gettempdir()
        location = os.path.join(tempdir, '{}_{}_debug_screenshot.png'.format(self.search_engine_name, self.browser_type))
        self.webdriver.get_screenshot_as_file(location)

    def _set_xvfb_display(self):
        # TODO: should we check the format of the config?
        if self.xvfb_display:
            os.environ['DISPLAY'] = self.xvfb_display

    def _get_webdriver(self):
        """Return a webdriver instance and set it up with the according profile/ proxies.

        https://stackoverflow.com/questions/49162667/unknown-error-call-function-result-missing-value-for-selenium-send-keys-even
        Get Chrome Drivers here: https://chromedriver.storage.googleapis.com/index.html?path=2.41/

        Returns:
            The appropriate webdriver mode according to self.browser_type. If no webdriver mode
            could be found, return False.
        """
        if self.browser_type == 'chrome':
            return self._get_Chrome()
        elif self.browser_type == 'firefox':
            return self._get_Firefox()

        return False

    def _get_Chrome(self):
        try:
            chrome_options = webdriver.ChromeOptions()
            chrome_options.binary_location = ""

            # save resouces, options are experimental
            # See here:
            # https://news.ycombinator.com/item?id=14103503
            # https://stackoverflow.com/questions/49008008/chrome-headless-puppeteer-too-much-cpu
            # https://engineering.21buttons.com/crawling-thousands-of-products-using-aws-lambda-80332e259de1
            chrome_options.add_argument("test-type")
            chrome_options.add_argument('--js-flags="--expose-gc --max-old-space-size=500"')
            chrome_options.add_argument(
                'user-agent={}'.format(self.user_agent.random))
            chrome_options.add_argument('--enable-precise-memory-info')
            chrome_options.add_argument('--disable-default-apps')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--incognito')
            chrome_options.add_argument('--disable-application-cache')


            if self.browser_mode == 'headless':
                chrome_options.add_argument('headless')
                #chrome_options.add_argument('window-size=1200x600') # optional

            if self.proxy:
                chrome_options.add_argument(
                    '--proxy-server={}://{}:{}'.format(self.proxy.proto, self.proxy.host, self.proxy.port))

            chromedriver_path = self.config.get('chromedriver_path')
            self.webdriver = webdriver.Chrome(executable_path=chromedriver_path,
                                                        chrome_options=chrome_options)
            return True

        except WebDriverException as e:
            # we don't have a chrome executable or a chrome webdriver installed
            raise
        return False


    def _get_Firefox(self):

        try:
            bin_path = self.config.get('firefox_binary_path')
            binary = FirefoxBinary(bin_path)
            geckodriver_path = self.config.get('geckodriver_path')
            options = FirefoxOptions()
            profile = webdriver.FirefoxProfile()

            options.add_argument(
                'user-agent={}'.format(self.user_agent.random))

            if self.browser_mode == 'headless':
                options.set_headless(headless=True)
                #options.add_argument('window-size=1200x600') # optional

            if self.proxy:
                # this means that the proxy is user set, regardless of the type
                profile.set_preference("network.proxy.type", 1)
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

            self.webdriver = webdriver.Firefox(firefox_binary=binary, firefox_options=options,
                     executable_path=geckodriver_path, firefox_profile=profile)
            return True

        except WebDriverException as e:
            # reaching here is bad, since we have no available webdriver instance.
            logger.error(e)

        return False


    def malicious_request_detected(self):
        """Checks whether a malicious request was detected.
        """
        needles = self.malicious_request_needles[self.search_engine_name]

        return needles and needles['inurl'] in self.webdriver.current_url \
                and needles['inhtml'] in self.webdriver.page_source

    def handle_request_denied(self):
        """Checks whether Google detected a potentially harmful request.

        Whenever such potential abuse is detected, Google shows an captcha.
        This method just blocks as long as someone entered the captcha in the browser window.
        When the window is not visible (For example when using chrome headless), this method
        makes a png from the html code and shows it to the user, which should enter it in a command
        line.

        Returns:
            The search input field.

        Raises:
            MaliciousRequestDetected when there was not way to stp Google From denying our requests.
        """
        # selenium webdriver objects have no status code :/
        if self.malicious_request_detected():

            super().handle_request_denied('400')

            # only solve when in non headless mode
            if self.config.get('manual_captcha_solving', False) and self.config.get('browser_mode') != 'headless':
                with self.captcha_lock:
                    solution = input('Please solve the captcha in the browser! Enter any key when done...')
                    try:
                        self.search_input = WebDriverWait(self.webdriver, 7).until(
                            EC.visibility_of_element_located(self._get_search_input_field()))
                    except TimeoutException:
                        raise MaliciousRequestDetected('Requesting with this IP address or cookies is not possible at the moment.')

            elif self.config.get('captcha_solving_service', False):
                # implement request to manual captcha solving service such 
                # as https://2captcha.com/
                pass
            else:
                # Just wait until the user solves the captcha in the browser window
                # 10 hours if needed :D
                logger.info('Waiting for user to solve captcha')
                return self._wait_until_search_input_field_appears(10 * 60 * 60)


    def _get_search_param_values(self):
        search_param_values = {}
        if self.search_engine_name in self.search_params:
            for param_key in self.search_params[self.search_engine_name]:
                cfg = self.config.get(param_key, None)
                if cfg:
                    search_param_values[param_key] = cfg
        return search_param_values

    def _get_search_input_field(self):
        """Get the search input field for the current search_engine.

        Returns:
            A tuple to locate the search field as used by seleniums function presence_of_element_located()
        """
        return self.input_field_selectors[self.search_engine_name]

    def _get_search_param_fields(self):
        if self.search_engine_name in self.param_field_selectors:
            return self.param_field_selectors[self.search_engine_name]
        else:
            return {}

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


    def _wait_until_search_param_fields_appears(self, max_wait=5):
        """Waits until the search input field contains the query.

        Args:
            max_wait: How long to wait maximally before returning False.
        """
        def find_visible_search_param(driver):
            for param, field in self._get_search_param_fields().items():
                input_field = driver.find_element(*field)
                if not input_field:
                    return False
            return True

        try:
            fields = WebDriverWait(self.webdriver, max_wait).until(find_visible_search_param)
            return fields
        except TimeoutException as e:
            logger.error('{}: TimeoutException waiting for search param field: {}'.format(self.name, e))
            return False

    def _goto_next_page(self):
        """
        Click the next page element,

        Returns:
            The url of the next page or False if there is no such url
                (end of available pages for instance).
        """
        next_url = ''
        element = self._find_next_page_element()

        if element and hasattr(element, 'click'):
            next_url = element.get_attribute('href')
            try:
                element.click()
            except WebDriverException:
                # See http://stackoverflow.com/questions/11908249/debugging-element-is-not-clickable-at-point-error
                # first move mouse to the next element, some times the element is not visibility, like blekko.com
                selector = self.next_page_selectors[self.search_engine_name]
                if selector:
                    try:
                        next_element = WebDriverWait(self.webdriver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                        webdriver.ActionChains(self.webdriver).move_to_element(next_element).perform()
                        # wait until the next page link emerges
                        WebDriverWait(self.webdriver, 8).until(
                            EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))
                        element = self.webdriver.find_element_by_css_selector(selector)
                        next_url = element.get_attribute('href')
                        element.click()
                    except WebDriverException:
                        pass

        # wait until the next page was loaded
        if not next_url:
            return False
        else:
            return next_url


    def _find_next_page_element(self):
        """Finds the element that locates the next page for any search engine.

        Returns:
            The element that needs to be clicked to get to the next page or a boolean value to
            indicate an error condition.
        """
        if self.search_type == 'normal':
            selector = self.next_page_selectors[self.search_engine_name]
            try:
                # wait until the next page link is clickable
                WebDriverWait(self.webdriver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
            except (WebDriverException, TimeoutException) as e:
                # If we can't detect the next page element because there is no
                # next page (for example because the search query is to unique)
                # we need to return false
                self._save_debug_screenshot()
                logger.warning('{}: Cannot locate next page element: {}'.format(self.name, str(e)))
                return False

            return self.webdriver.find_element_by_css_selector(selector)

        elif self.search_type == 'image':
            self.page_down()
            return True


    def wait_until_serp_loaded(self):
        """
        This method tries to wait until the page requested is loaded.

        We know that the correct page is loaded when self.page_number appears
        in the navigation of the page.
        """

        if self.search_type == 'normal':

            if self.search_engine_name == 'google':
                selector = '#navcnt td.cur'
            elif self.search_engine_name == 'yandex':
                selector = '.pager__item_current_yes'
            elif self.search_engine_name == 'bing':
                selector = 'nav li a.sb_pagS'
            elif self.search_engine_name == 'yahoo':
                selector = '.compPagination strong'
            elif self.search_engine_name == 'baidu':
                selector = '#page .fk_cur + .pc'
            elif self.search_engine_name == 'duckduckgo':
                # no pagination in duckduckgo
                pass
            elif self.search_engine_name == 'ask':
                selector = '#paging .pgcsel .pg'

            if self.search_engine_name == 'duckduckgo':
                time.sleep(1.5)
            else:

                try:
                    WebDriverWait(self.webdriver, 5).\
            until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, selector), str(self.page_number)))
                except TimeoutException as e:
                    self._save_debug_screenshot()
                    logger.warning('Pagenumber={} did not appear in serp. Maybe there is only one result for this query?'.format(self.page_number))

        elif self.search_type == 'image':
            self.wait_until_title_contains_keyword()

        else:
            self.wait_until_title_contains_keyword()

    def wait_until_title_contains_keyword(self):
        try:
            WebDriverWait(self.webdriver, 5).until(EC.title_contains(self.query))
        except TimeoutException:
            logger.debug(SeleniumSearchError(
                '{}: Keyword "{}" not found in title: {}'.format(self.name, self.query, self.webdriver.title)))


    def build_search(self):
        """Build the search for SelScrapers"""
        assert self.webdriver, 'Webdriver needs to be ready to build the search'

        if self.config.get('search_type', 'normal') == 'image':
            starting_url = self.image_search_locations[self.search_engine_name]
        else:
            starting_url = self.base_search_url

        num_results = self.config.get('num_results_per_page', 10)

        if self.search_engine_name == 'google':
            if num_results not in (10, 20, 30, 50, 100):
                raise Exception('num_results_per_page for selenium mode and search engine Google must be in (10, 20, 30, 50, 100)')
            starting_url += 'num={}'.format(num_results)

        elif self.search_engine_name == 'bing':
            if num_results not in range(1, 100):
                raise Exception('num_results_per_page for selenium mode and search engine Bing must be in range(1, 100)')
            starting_url += 'count={}'.format(num_results)

        elif self.search_engine_name == 'yahoo':
            if num_results not in range(1, 100):
                raise Exception('num_results_per_page for selenium mode and search engine Yahoo must be in range(1, 100)')
            starting_url += 'n={}'.format(num_results)

        self.webdriver.get(starting_url)


    def search(self):
        """Search with webdriver.

        Fills out the search form of the search engine for each keyword.
        Clicks the next link while pages_per_keyword is not reached.
        """
        for self.query, self.pages_per_keyword in self.jobs.items():

            self.search_input = self._wait_until_search_input_field_appears()

            if self.search_input is False and self.config.get('stop_on_detection'):
                self.status = 'Malicious request detected'
                return

            # check if request denied
            self.handle_request_denied()

            if self.search_input:
                self.search_input.clear()
                time.sleep(.25)

                self.search_param_fields = self._get_search_param_fields()

                if self.search_param_fields:
                    wait_res = self._wait_until_search_param_fields_appears()
                    if wait_res is False:
                        raise Exception('Waiting search param input fields time exceeds')
                    for param, field in self.search_param_fields.items():
                        if field[0] == By.ID:
                            js_tpl = '''
                            var field = document.getElementById("%s");
                            field.setAttribute("value", "%s");
                            '''
                        elif field[0] == By.NAME:
                            js_tpl = '''
                            var fields = document.getElementsByName("%s");
                            for (var f in fields) {
                                f.setAttribute("value", "%s");
                            }
                            '''
                        js_str = js_tpl % (field[1], self.search_param_values[param])
                        self.webdriver.execute_script(js_str)

                try:
                    self.search_input.send_keys(self.query + Keys.ENTER)
                except ElementNotVisibleException:
                    time.sleep(2)
                    self.search_input.send_keys(self.query + Keys.ENTER)

                self.requested_at = datetime.datetime.utcnow()
            else:
                logger.debug('{}: Cannot get handle to the input form for keyword {}.'.format(self.name, self.query))
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
                    next_url = self._goto_next_page()
                    self.requested_at = datetime.datetime.utcnow()

                    if not next_url:
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

        self._set_xvfb_display()

        if not self._get_webdriver():
            raise Exception('{}: Aborting: No available selenium webdriver.'.format(self.name))

        try:
            self.webdriver.set_window_size(400, 400)
            self.webdriver.set_window_position(400 * (self.browser_num % 4), 400 * (math.floor(self.browser_num // 4)))
        except WebDriverException as e:
            logger.debug('Cannot set window size: {}'.format(e))

        super().before_search()

        if self.startable:
            self.build_search()
            self.search()

        if self.webdriver:
            self.webdriver.quit()


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


class GoogleSelScrape(SelScrape):
    """
    Add Google Settings via this subclass.
    """

    def __init__(self, *args, **kwargs):
        SelScrape.__init__(self, *args, **kwargs)
        self.largest_id = 0

    def build_search(self):
        """
        Specify google page settings according to config.

        Doing this automatically often provocates a captcha question.
        This is highly sensitive.
        """
        super().build_search()

        if self.config.get('google_selenium_search_settings', False):
            # assume we are on the normal google search page right now
            self.webdriver.get('https://www.google.com/preferences?hl=en')

            time.sleep(random.randint(1,4))

            if self.config.get('google_selenium_manual_settings', False):
                return input('Press any Key after search settings completed...')


            oldsize = self.webdriver.get_window_size()
            self.webdriver.maximize_window()

            # wait until we see the settings
            element = WebDriverWait(self.webdriver, 7).until(EC.presence_of_element_located((By.NAME, 'safeui')))

            try:
                if self.config.get('google_selenium_safe_search', False):
                    if self.webdriver.find_element_by_name('safeui').get_attribute('value') != 'on':
                        self.webdriver.find_element_by_name('safeui').click()

                try:
                    if self.config.get('google_selenium_personalization', False):
                        self.webdriver.find_element_by_css_selector('#pson-radio > div:first-child').click()
                    else:
                        self.webdriver.find_element_by_css_selector('#pson-radio > div:nth-child(2)').click()
                except WebDriverException as e:
                    logger.warning('Cannot set personalization settings.')

                time.sleep(random.randint(1,4))

                # set the region
                try:
                    self.webdriver.find_element_by_id('regionanchormore').click()
                except WebDriverException as e:
                    logger.warning('Regions probably already expanded.')

                try:
                    region = self.config.get('google_selenium_region', 'US')
                    self.webdriver.find_element_by_css_selector('div[data-value="{}"]'.format(region)).click()
                except WebDriverException as e:
                    logger.warning('Cannot set region settings.')

                # set the number of results
                try:
                    num_results = self.config.get('google_selenium_num_results', 10)
                    self.webdriver.find_element_by_id('result_slider').click()
                    # reset
                    for i in range(5):
                        self.webdriver.find_element_by_id('result_slider').send_keys(Keys.LEFT)
                    # move to desicred result
                    for i in range((num_results//10)-1):
                        time.sleep(.25)
                        self.webdriver.find_element_by_id('result_slider').send_keys(Keys.RIGHT)
                except WebDriverException as e:
                    logger.warning('Cannot set number of results settings.')

                time.sleep(random.randint(1,4))

                # save settings
                self.webdriver.find_element_by_css_selector('#form-buttons div:first-child').click()
                time.sleep(1)
                # accept alert
                self.webdriver.switch_to.alert.accept()

                time.sleep(random.randint(1,4))

                self.handle_request_denied()

            except WebDriverException as e:
                logger.error('Unable to set google page settings')
                wait = input('waiting...')
                raise e

            driver.set_window_size(oldsize['width'], oldsize['height'])


class DuckduckgoSelScrape(SelScrape):
    """
    Duckduckgo is a little special since new results are obtained by ajax.
    next page thus is then to scroll down.

    It cannot be the User-Agent, because I already tried this.
    """

    def __init__(self, *args, **kwargs):
        SelScrape.__init__(self, *args, **kwargs)
        self.largest_id = 0

    def _goto_next_page(self):
        super().page_down()
        return 'No more results' not in self.html

    def wait_until_serp_loaded(self):
        super()._wait_until_search_input_field_appears()


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
                return quote(self.query) in driver.current_url or \
                    self.query.replace(' ', '+') in driver.current_url
            except WebDriverException:
                pass

        WebDriverWait(self.webdriver, 5).until(wait_until_keyword_in_url)
