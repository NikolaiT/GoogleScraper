# -*- coding: utf-8 -*-

import threading
import json
import datetime
import socket
from urllib.parse import urlencode

import GoogleScraper.socks as socks
from GoogleScraper.scraping import SearchEngineScrape, get_base_search_url_by_search_engine
from GoogleScraper.parsing import get_parser_by_search_engine
from GoogleScraper.user_agents import random_user_agent
import logging

logger = logging.getLogger(__name__)

headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, sdch',
    'Connection': 'keep-alive',
}


def get_GET_params_for_search_engine(query, search_engine, page_number=1, num_results_per_page=10,
                                     search_type='normal'):
    """Returns the params of the url for the search engine and the search mode.

    Args:
        search_engine: The search engine. Example: 'google'
        search_mode: The search mode. Example: 'image' or 'normal'
        query: The search query
        page_number: Which SERP page.
        num_results_per_page: How many entries per page.

    Returns:
        The params for the GET url.
    """

    search_params = {}

    if search_engine == 'google':
        # always use the english interface, such that we can detect
        # state by some hard coded needles.
        search_params['hl'] = 'en'
        search_params['q'] = query
        # only set when other num results than 10.
        if num_results_per_page != 10:
            search_params['num'] = str(num_results_per_page)

        if page_number > 1:
            search_params['start'] = str((page_number - 1) * int(num_results_per_page))

        if search_type == 'image':
            search_params.update({
                'oq': query,
                'site': 'imghp',
                'tbm': 'isch',
                'source': 'hp',
                # 'sa': 'X',
                'biw': 1920,
                'bih': 881
            })
        elif search_type == 'video':
            search_params.update({
                'tbm': 'vid',
                'source': 'lnms',
                'sa': 'X',
                'biw': 1920,
                'bih': 881
            })
        elif search_type == 'news':
            search_params.update({
                'tbm': 'nws',
                'source': 'lnms',
                'sa': 'X'
            })

    elif search_engine == 'yandex':
        search_params['text'] = query
        if page_number > 1:
            search_params['p'] = str(page_number - 1)

        # @todo: what was this for?
        # if search_type == 'image':
        #     base_search_url = 'http://yandex.ru/images/search?'

    elif search_engine == 'bing':
        search_params['q'] = query
        # bing doesn't support variable number of results (As far as I know).
        if page_number > 1:
            search_params['first'] = str(1 + ((page_number - 1) * 10))

    elif search_engine == 'yahoo':
        search_params['p'] = query
        if page_number > 1:
            search_params['b'] = str(1 + ((page_number - 1) * 10))
        search_params['ei'] = 'UTF-8'

    elif search_engine == 'baidu':
        search_params['wd'] = query
        if page_number > 1:
            search_params['pn'] = str((page_number - 1) * 10)
        search_params['ie'] = 'utf-8'
    elif search_engine == 'duckduckgo':
        search_params['q'] = query
    elif search_engine == 'ask':
        search_params['q'] = query
        search_params['qsrc'] = '0'
        search_params['l'] = 'dir'
        search_params['qo'] = 'homepageSearchBox'
        if page_number > 1:
            search_params['page'] = str(page_number)
    elif search_engine == 'blekko':
        search_params['q'] = query

    return search_params


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

    def __init__(self, config, *args, time_offset=0.0, **kwargs):
        """Initialize an HttScrape object to scrape over blocking http.

        HttpScrape inherits from SearchEngineScrape
        and from threading.Timer.
        """
        threading.Timer.__init__(self, time_offset, self.search)
        SearchEngineScrape.__init__(self, config, *args, **kwargs)

        # Bind the requests module to this instance such that each
        # instance may have an own proxy
        self.requests = __import__('requests')

        # initialize the GET parameters for the search request
        self.search_params = {}

        # initialize the HTTP headers of the search request
        # to some base values that mozilla uses with requests.
        # the Host and User-Agent field need to be set additionally.
        self.headers = headers

        # the mode
        self.scrape_method = 'http'

        # get the base search url based on the search engine.
        self.base_search_url = get_base_search_url_by_search_engine(self.config, self.search_engine_name, self.scrape_method)

        super().instance_creation_info(self.__class__.__name__)

        if self.search_engine_name == 'blekko':
            logger.critical('blekko does not support http mode.')
            self.startable = False

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

    def proxy_check(self, proxy):
        assert self.proxy and self.requests, 'ScraperWorker needs valid proxy instance and requests library to make ' \
                                             'the proxy check.'

        online = False
        status = 'Proxy check failed: {host}:{port} is not used while requesting'.format(**self.proxy.__dict__)
        ipinfo = {}

        try:
            text = self.requests.get(self.config.get('proxy_info_url')).text
            try:
                ipinfo = json.loads(text)
            except ValueError:
                pass
        except self.requests.ConnectionError as e:
            status = 'No connection to proxy server possible, aborting: {}'.format(e)
        except self.requests.Timeout as e:
            status = 'Timeout while connecting to proxy server: {}'.format(e)
        except self.requests.exceptions.RequestException as e:
            status = 'Unknown exception: {}'.format(e)

        if 'ip' in ipinfo and ipinfo['ip']:
            online = True
            status = 'Proxy is working.'
        else:
            logger.warning(status)

        super().update_proxy_status(status, ipinfo, online)

        return online

    def handle_request_denied(self, status_code=''):
        """Handle request denied by the search engine.

        This is the perfect place to distinguish the different responses
        if search engine detect exhaustive searching.

        Args:
            status_code: The status code of the HTTP response.

        Returns:
        """
        super().handle_request_denied(status_code)

    def build_search(self):
        """Build the headers and params for the search request for the search engine."""

        self.search_params = get_GET_params_for_search_engine(self.query, self.search_engine_name,
                                                              self.page_number, self.num_results_per_page,
                                                              self.search_type)

        self.parser = get_parser_by_search_engine(self.search_engine_name)
        self.parser = self.parser(config=self.config)

    def search(self, rand=True, timeout=15):
        """The actual search for the search engine.

        When raising StopScrapingException, the scraper will stop.

        When return False, the scraper tries to continue with next keyword.
        """

        success = True

        self.build_search()

        if rand:
            self.headers['User-Agent'] = random_user_agent(only_desktop=True)

        try:
            super().detection_prevention_sleep()
            super().keyword_info()

            request = self.requests.get(self.base_search_url + urlencode(self.search_params),
                                        headers=self.headers, timeout=timeout)

            self.requested_at = datetime.datetime.utcnow()
            self.html = request.text

            logger.debug('[HTTP - {url}, headers={headers}, params={params}'.format(
                url=request.url,
                headers=self.headers,
                params=self.search_params))

        except self.requests.ConnectionError as ce:
            self.status = 'Network problem occurred {}'.format(ce)
            success = False
        except self.requests.Timeout as te:
            self.status = 'Connection timeout {}'.format(te)
            success = False
        except self.requests.exceptions.RequestException as e:
            # In case of any http networking exception that wasn't caught
            # in the actual request, just end the worker.
            self.status = 'Stopping scraping because {}'.format(e)
        else:
            if not request.ok:
                self.handle_request_denied(request.status_code)
                success = False

        super().after_search()

        return success

    def run(self):
        super().before_search()

        if self.startable:
            for self.query, self.pages_per_keyword in self.jobs.items():

                for self.page_number in self.pages_per_keyword:

                    if not self.search(rand=True):
                        self.missed_keywords.add(self.query)
