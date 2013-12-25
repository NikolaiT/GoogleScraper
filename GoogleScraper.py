#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Complete rewrite.
# Many thanks go to v3nz3n

# This is a little module that uses Google to automate search
# queries. It gives (pragmatical) access to all data of a search results:
# - The links of the result page
# - The title of the links
# - The caption/description below each link
# - The number of results for this keyword

# GoogleScraper's architecture outlined:
# - Proxy support (Socks5, Socks4, HTTP Proxy)
# - Threading support

# The module implements some countermeasures to circumvent spamming detection
# from the Google Servers:
# {List them here}

# Note: Scraping compromises the google terms of service (TOS).

__VERSION__ = '0.3'
__UPDATED__ = '24.12.2013' # day.month.year
__AUTHOR__ = 'Nikolai'
__WEBSITE__ = 'incolumitas.com'

import sys
import os
import socket
import argparse
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
    print('You can install missing modules with `pip install modulename`')
    sys.exit(1)

# module wide global variables

# Whether caching shall be enabled
DO_CACHING = True
# The directory path for cached google results
CACHEDIR = 'scrapecache/'

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
    '''
    loads a cached search results page from scrapecache/fname.cache
    It help in testing and avoid requesting
    the same resources again and again (such that google would
    recognize us as what we are: Sneaky seo crawlers!)
    '''
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
    '''
    Stores a html resource as a file in scrapecache/fname.cache
    This will always write(overwrite) the file.
    '''
    fname = cached_file_name(search_params)

    with open(os.path.join(CACHEDIR, fname), 'w') as fd:
        fd.write(html)


class GoogleScraper:
    '''
    Offers a fast way to query the google search engine. It returns a list
    of all found URLs found on x pages with n search results per page.
    You can define x and n, sir!
    '''

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

    # http://www.blueglass.com/blog/google-search-url-parameters-query-string-anatomy/
    _GOOGLE_SEARCH = 'http://www.google.com/search'

    _GOOGLE_SEARCH_PARAMS = {
        'q': '', # the search term
        'num': '', # the number of results per page
        'start': '0', # the offset to the search results. page number = (start / num) + 1
        'pws': '0'      # personalization turned off
    }

    Result = namedtuple('LinkResult', 'link_title link_snippet link_url')
    _GOOGLE_SEARCH_RESULTS = {
        'search_keyword': '', # The query keyword
        'num_results_for_kw': '', # The number of results for the keyword
        'results': [] # List of Result named tuples
    }

    _HEADERS = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'close',
        'DNT': '1'
    }

    # Keep the User-Agents updated. 
    # I guess 9 different UA's is engough, since many users
    # have the same UA (and only a different IP).
    # Get them here: http://techblog.willshouse.com/2012/01/03/most-common-user-agents/
    _UAS = [
        'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/31.0.1650.57 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9) AppleWebKit/537.71 (KHTML, like Gecko) Version/7.0 Safari/537.71',
        'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:25.0) Gecko/20100101 Firefox/25.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/31.0.1650.57 Safari/537.36',
        'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.101 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.101 Safari/537.36',
        'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/31.0.1650.57 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:25.0) Gecko/20100101 Firefox/25.0',
        'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/31.0.1650.57 Safari/537.36'
    ]

    def __init__(self, search_term, number_results_page=50, offset=0):
        self.search_term = search_term
        if number_results_page not in [10, 25, 50, 100]:
            raise InvalidNumberResultsException(number_results_page)

        self.number_results_page = number_results_page
        self.offset = offset
        self._GOOGLE_SEARCH_RESULTS['search_keyword'] = self.search_term

    # Front end
    # This function returns a list of 5-tuples: 
    # (addressing scheme, network location, path, query, fragment identifier).
    def search(self, number_pages=1):
        for i in range(number_pages):
            self.offset = int(self.number_results_page * 100 * i)
            self._search()

            # Now try to create ParseResult objects from the URL
            for i, e in enumerate(self._GOOGLE_SEARCH_RESULTS['results']):
                try:
                    url = self._REGEX_VALID_URL.search(e.link_url).group()
                    self._GOOGLE_SEARCH_RESULTS['results'][i].link_url = urllib.parse.urlparse(url)
                except Exception as e:
                    pass

        return self._GOOGLE_SEARCH_RESULTS

    # private internal functions who implement the actual stuff 

    # When random == True, several headers (like the UA) are chosen
    # randomly.
    def _build_query(self, random=False):
        self._GOOGLE_SEARCH_PARAMS['q'] = self.search_term
        self._GOOGLE_SEARCH_PARAMS['num'] = self.number_results_page
        self._GOOGLE_SEARCH_PARAMS['start'] = str(self.offset)

        if random:
            self._HEADERS['User-Agent'] = choice(self._UAS)

    # Search via google and parse with lxml
    # private function
    def _search(self):
        self._build_query()

        if DO_CACHING:
            html = get_cached(self._GOOGLE_SEARCH_PARAMS)
        else:
            html = False

        if not html:
            try:
                r = requests.get(self._GOOGLE_SEARCH, headers=self._HEADERS,
                                 params=self._GOOGLE_SEARCH_PARAMS, timeout=3.0)
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
                cache_results(self._GOOGLE_SEARCH_PARAMS, html)

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
            print(e.msg)
            # Try iterlinks() [Its probably better anyways]
            # may become deprecated
            # return [link for element, attribute, link, position in dom.iterlinks() if attribute == 'href']

        self._GOOGLE_SEARCH_RESULTS['results'].extend(links)

        # try to get the number of results for our search query
        try:
            self._GOOGLE_SEARCH_RESULTS['num_results_for_kw'] = dom.xpath(HTMLTranslator().css_to_xpath('div#resultStats'))[0].text_content()
        except Exception as e:
            print(e.msg)


def scrape(query, results_per_page=100, number_pages=1, offset=0):
    '''Search for terms and return a list of all URLs.'''
    scraper = GoogleScraper(query, number_results_page=results_per_page)
    results = scraper.search(number_pages=number_pages)
    return results


# For unit tests and direct use of the module
if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='GoogleScraper', description='Scrape the Google search engine',
                                     epilog='This program might infringe Google TOS, so use at your own risk')
    parser.add_argument('-q', '--query', metavar='search_string', type=str, action='store', dest='query', required=True,
                        help='The search query.')
    parser.add_argument('-n', '--num_search_results', metavar='number_of_search_results', type=int,
                        dest='num_search_results', action='store', default=100,
                        help='The number of results per page. Most be one of [10, 25, 50, 100]')
    parser.add_argument('-p', '--num_pages', metavar='num_of_pages', type=int, dest='num_pages', action='store',
                        default=1,
                        help='The number of pages to search in. Each page is requested by a unique connection and if possible by a unique IP.')
    parser.add_argument('--proxy', metavar='proxycredentials', type=str, dest='proxy', action='store',
                        default=('127.0.0.1', 9050), required=False,
                        help='A string such as "127.0.0.1:9050" specifying a single proxy server')
    parser.add_argument('--proxy_file', metavar='proxyfile', type=str, dest='proxy_file', action='store',
                        required=False, #default='.proxies'
                        help='A filename for a list of proxies with the following format: "(proxy_ip|proxy_host):Port\\n"')
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
        socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, proxy_host, int(proxy_port), rdns=True) # rdns is by default on true. Never use rnds=False with TOR, otherwise you are screwed!
        socks.wrap_module(socket)
        socket.create_connection = create_connection

    import textwrap
    results = scrape(args.query, args.num_search_results, args.num_pages)
    print('[+] The search with the keyword "{}" yielded `{}`'.format(results['search_keyword'], results['num_results_for_kw']))
    for link_title, link_snippet, link_url in results['results']:
        print('[+] Link: {}'.format(link_url))
        print('[+] Title: \n{}'.format('\n'.join(textwrap.wrap(link_title, 50))))
        print('[+] Description: \n{}\n'.format('\n'.join(textwrap.wrap(link_snippet, 70))))
