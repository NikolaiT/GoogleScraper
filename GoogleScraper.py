#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Complete rewrite.
Many thanks go to v3nz3n

This is a little module that uses Google to automate search
queries. It gives straightforward access to all relevant data of Google such as
- The links of the result page
- The title of the links
- The caption/description below each link
- The number of results for this keyword

GoogleScraper's architecture outlined:
- Proxy support (Socks5, Socks4, HTTP Proxy)
- Threading support

The module implements some countermeasures to circumvent spamming detection
from the Google Servers:
{List them here}

Note: Scraping compromises the google terms of service (TOS).
"""

__VERSION__ = '0.4'
__UPDATED__ = '16.02.2014' # day.month.year
__AUTHOR__ = 'Nikolai Tschacher'
__WEBSITE__ = 'incolumitas.com'

import sys
import os
import socket
import logging
import argparse
import threading
from collections import namedtuple
import hashlib
import re
import time
import lxml.html
import urllib.parse
from random import choice

try:
    import requests
    from cssselect import HTMLTranslator, SelectorError
    from bs4 import UnicodeDammit
    import socks # should be in the same directory
except ImportError as e:
    print(e.msg)
    print('You can install missing modules with `pip install [modulename]`')
    sys.exit(1)

# module wide global variables and configuration

# First obtain a logger
logger = logging.getLogger('GoogleScraper')
logger.setLevel(logging.INFO)

ch = logging.StreamHandler(stream=sys.stderr)
ch.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

# Whether caching shall be enabled
DO_CACHING = True
# The directory path for cached google results
CACHEDIR = '.scrapecache/'

if DO_CACHING:
    if not os.path.exists(CACHEDIR):
        os.mkdir(CACHEDIR, 0o744)


class GoogleSearchError(Exception):
    def __init__(self):
        pass

    def __str__(self):
        return 'Exception in GoogleSearch class'


class InvalidNumberResultsException(GoogleSearchError):
    def __init__(self, number_of_results):
        self.nres = number_of_results

    def __str__(self):
        return '%d is not a valid number of results per page' % self.nres


def cached_file_name(search_params):
    sha = hashlib.sha256()
    # Make a unique file name based on the values of the google search parameters.
    sha.update(b''.join(str(search_params.get(s)).encode() for s in sorted(search_params.keys())))
    return '{}.{}'.format(sha.hexdigest(), 'cache')


def get_cached(search_params):
    """Loads a cached search results page from scrapecache/fname.cache

    It helps in testing and avoid requesting
    the same resources again and again (such that google may
    recognize us as what we are: Sneaky SEO crawlers!)
    """
    fname = cached_file_name(search_params)

    try:
        if fname in os.listdir(CACHEDIR):
            # If the cached file is older than 12 hours, return False and thus
            # make a new fresh request.
            modtime = os.path.getmtime(os.path.join(CACHEDIR, fname))
            if (time.time() - modtime) / 60 / 60 > 12:
                return False
            with open(os.path.join(CACHEDIR, fname), 'r') as fd:
                return fd.read()
    except FileNotFoundError as err:
        raise Exception('Unexpected file not found: {}'.format(err.msg))

    return False


def cache_results(search_params, html):
    """Stores a html resource as a file in scrapecache/fname.cache

    This will always write(overwrite) the cache file.
    """
    fname = cached_file_name(search_params)

    with open(os.path.join(CACHEDIR, fname), 'w') as fd:
        fd.write(html)


class GoogleScrape(threading.Thread):
    """Offers a fast way to query the google search engine.

    Overrides the run() method of the superclass threading.Thread.
    Each thread represents a crawl for one Google Results Page.

    http://www.blueglass.com/blog/google-search-url-parameters-query-string-anatomy/
    """

    # Valid URL (taken from django)
    _REGEX_VALID_URL = re.compile(
        r'^(?:http|ftp)s?://' # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' # domain...
        r'localhost|' # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
        r'(?::\d+)?' # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    _REGEX_VALID_URL_SIMPLE = re.compile(
        'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')

    # Named tuple type for the search results
    Result = namedtuple('LinkResult', 'link_title link_snippet link_url')

    # Several different User-Agents to diversify the requests.
    # Keep the User-Agents updated. Last update: 17th february 14
    # Get them here: http://techblog.willshouse.com/2012/01/03/most-common-user-agents/
    _UAS = [
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

    _HEADERS = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'close',
        'DNT': '1'
    }

    def __init__(self, search_term, num_results_per_page=10, num_page=0):
        super().__init__()
        logger.debug("Created new GoogleScrape objectt with params: query={}, num_results_per_page={}, num_page={}".format(
            search_term, num_results_per_page, num_page))
        self.search_term = search_term
        if num_results_per_page not in [10, 25, 50, 100]:
            raise InvalidNumberResultsException(num_results_per_page)

        self.num_results_per_page = num_results_per_page
        self.num_page = num_page

        self._SEARCH_URL = 'http://www.google.com/search'

        self._SEARCH_PARAMS = {
            'q': '', # the search term
            'num': '', # the number of results per page
            'start': '0', # the offset to the search results. page number = (start / num) + 1
            'pws': '0'      # personalization turned off
        }

        self.SEARCH_RESULTS = {
            'search_keyword': self.search_term, # The query keyword
            'num_results_for_kw': '', # The number of results for the keyword
            'results': [] # List of Result named tuples
        }

    def run(self):
        """Make the the scrape and clean the URL's."""
        self._search()

        # Now try to create ParseResult objects from the URL
        for i, e in enumerate(self.SEARCH_RESULTS['results']):
            try:
                url = re.search(r'/url\?q=(?P<url>.*?)&sa=U&ei=', e.link_url).group(1)
                assert self._REGEX_VALID_URL.match(url).group()
                self.SEARCH_RESULTS['results'][i] = \
                    self.Result(link_title=e.link_title, link_url=urllib.parse.urlparse(url),
                                link_snippet=e.link_snippet)
            except Exception as err:
                pass # Skip if the url wasn't valid

    def _build_query(self, random=False):
        """Build the headeres and params for the GET request to the Google server.

        When random == True, several headers (like the UA) are chosen
        randomly.
        """
        self._SEARCH_PARAMS.update(
            {'q': self.search_term,
             'num': str(self.num_results_per_page),
             'start': str(int(self.num_results_per_page) * int(self.num_page))
            })

        if random:
            self._HEADERS['User-Agent'] = choice(self._UAS)

    def _search(self):
        """The actual search and parsing of the results.

        Private, internal method.
        Parsing is done with lxml and cssselect. The html structure of the Google Search
        results may change over time. Effective: February 2014
        """
        self._build_query()

        if DO_CACHING:
            html = get_cached(self._SEARCH_PARAMS)
        else:
            html = False

        if not html:
            try:
                logger.debug("Initiating search with params={}".format(self._SEARCH_PARAMS))
                r = requests.get(self._SEARCH_URL, headers=self._HEADERS,
                                 params=self._SEARCH_PARAMS, timeout=3.0)

            except requests.ConnectionError as cerr:
                print('Network problem occured {}'.format(cerr.msg))
                return False
            except requests.Timeout as terr:
                print('Connection timeout {}'.format(terr.msg))
                return False

            if not r.ok:
                print('HTTP Error:', r.status_code)
                if str(r.status_code)[0] == '5':
                    print('Maybe google recognizes you as sneaky spammer after'
                          ' you requested their services too inexhaustibly :D')
                return False

            html = r.text
            # cache fresh results
            if DO_CACHING:
                cache_results(self._SEARCH_PARAMS, html)

        # Try to parse the google HTML result using lxml
        try:
            doc = UnicodeDammit(html, is_html=True)
            parser = lxml.html.HTMLParser(encoding=doc.declared_html_encoding)
            dom = lxml.html.document_fromstring(html, parser=parser)
            dom.resolve_base_href()
        except Exception as e:
            print('Some error occured while lxml tried to parse: {}'.format(e.msg))
            return False

        # Try to extract all links, including their snippets(descriptions) and titles.
        try:
            li_g_results = dom.xpath(HTMLTranslator().css_to_xpath('li.g'))
            links = []
            for e in li_g_results:
                link_element = e.xpath(HTMLTranslator().css_to_xpath('h3.r > a:first-child'))
                link = link_element[0].get('href')
                title = link_element[0].text_content()
                snippet_element = e.xpath(HTMLTranslator().css_to_xpath('span.st'))
                snippet = snippet_element[0].text_content()
                links.append(self.Result(link_title=title, link_url=link, link_snippet=snippet))
        except Exception as e:
            print(e.__cause__)

        self.SEARCH_RESULTS['results'].extend(links)

        # try to get the number of results for our search query
        try:
            self.SEARCH_RESULTS['num_results_for_kw'] = \
                dom.xpath(HTMLTranslator().css_to_xpath('div#resultStats'))[0].text_content()
        except Exception as e:
            logger.critical(e.msg)


def scrape(query, num_results_per_page=100, num_pages=1, offset=0):
    """Public API function to search for terms and return a list of results.

    arguments:
    query -- the search query. Can be whatever you want to crawl google for.

    Keyword arguments:
    num_results_per_page -- the number of results per page. Either 10, 25, 50 or 100.
    num_pages -- The number of pages to search for.
    offset -- specifies the offset to the page to begin searching.

    """
    threads = [GoogleScrape(query, num_results_per_page, i) for i in range(offset, num_pages + offset, 1)]

    for t in threads:
        t.start()

    for t in threads:
        t.join(3.0)

    return [t.SEARCH_RESULTS for t in threads]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='GoogleScraper', description='Scrape the Google search engine',
                                     epilog='This program might infringe Google TOS, so use at your own risk')
    parser.add_argument('-q', '--query', metavar='search_string', type=str, action='store', dest='query', required=True,
                        help='The search query.')
    parser.add_argument('-n', '--num_results_per_page', metavar='number_of_results_per_page', type=int,
                        dest='num_results_per_page', action='store', default=100,
                        help='The number of results per page. Most be one of [10, 25, 50, 100]')
    parser.add_argument('-p', '--num_pages', metavar='num_of_pages', type=int, dest='num_pages', action='store',
                        default=1,
                        help='The number of pages to search in. Each page is requested by a unique connection and if possible by a unique IP.')
    parser.add_argument('--proxy', metavar='proxycredentials', type=str, dest='proxy', action='store',
                        required=False, #default=('127.0.0.1', 9050)
                        help='A string such as "127.0.0.1:9050" specifying a single proxy server')
    parser.add_argument('--proxy_file', metavar='proxyfile', type=str, dest='proxy_file', action='store',
                        required=False, #default='.proxies'
                        help='A filename for a list of proxies with the following format: "(proxy_ip|proxy_host):Port\\n"')
    parser.add_argument('-v', '--verbosity', type=int, default=1,
                        help="The verbosity of the output reporting for the found search results.")
    args = parser.parse_args()

    if args.proxy_file:
        raise NotImplementedError('Coming soon.')

    if args.proxy:
        def create_connection(address, timeout=None, source_address=None):
            sock = socks.socksocket()
            sock.connect(address)
            return sock

        proxy_host, proxy_port = args.proxy.split(':')

        # Patch the socket module
        socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, proxy_host, int(proxy_port),
                              rdns=True) # rdns is by default on true. Never use rnds=False with TOR, otherwise you are screwed!
        socks.wrap_module(socket)
        socket.create_connection = create_connection

    import textwrap

    results = scrape(args.query, args.num_results_per_page, args.num_pages)

    if args.verbosity <= 1:
        for result in results:
            logger.info('{} links found! The search with the keyword "{}" yielded the result:{}'.format(
                len(result['results']), result['search_keyword'], result['num_results_for_kw']))
            for link_title, link_snippet, link_url in result['results']:
                print('Link: {}'.format(urllib.parse.unquote(link_url.geturl())))
    else:
        for result in results:
            logger.info('{} links found! The search with the keyword "{}" yielded the result:{}'.format(
                len(result['results']), result['search_keyword'], result['num_results_for_kw']))
            for link_title, link_snippet, link_url in result['results']:
                print('Link: {}'.format(urllib.parse.unquote(link_url.geturl())))
                print('Title: \n{}'.format(textwrap.indent('\n'.join(textwrap.wrap(link_title, 50)), '\t')))
                print(
                    'Description: \n{}\n'.format(textwrap.indent('\n'.join(textwrap.wrap(link_snippet, 70)), '\t')))
                print('*' * 70)
