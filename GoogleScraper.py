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
- The rank for the specific results

GoogleScraper's architecture outlined:
- Proxy support (Socks5, Socks4, HTTP Proxy)
- Threading support

The module implements some countermeasures to circumvent spamming detection
from the Google Servers:
- Small time interval between parallel requests

Note: Scraping compromises the google terms of service (TOS).

Debug:
Get a jQuery selector in a console: (function() {var e = document.createElement('script'); e.src = '//ajax.googleapis.com/ajax/libs/jquery/1.11.0/jquery.min.js'; document.getElementsByTagName('head')[0].appendChild(e); jQuery.noConflict(); })();
"""

__VERSION__ = '0.8'
__UPDATED__ = '23.05.2014'  # day.month.year
__AUTHOR__ = 'Nikolai Tschacher'
__WEBSITE__ = 'incolumitas.com'

import sys
import os
import math
import types
import logging
import pprint
import argparse
import threading
from collections import namedtuple
import hashlib
import re
import queue
import time
import signal
import lxml.html
import urllib.parse
import sqlite3
import itertools
import random
import zlib

try:
    import requests
    from cssselect import HTMLTranslator, SelectorError
    from bs4 import UnicodeDammit
    #import socks  # should be in the same directory
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait  # available since 2.4.0
    from selenium.webdriver.support import expected_conditions as EC  # available since 2.26.0
    from cssselect import HTMLTranslator, SelectorError
except ImportError as ie:
    if hasattr(ie, 'name') and ie.name == 'bs4' or hasattr(ie, 'args') and 'bs4' in str(ie):
        print('Install bs4 with the command "sudo pip3 install beautifulsoup4"')
        sys.exit(1)
    print(ie)
    print('You can install missing modules with `pip3 install [modulename]`')
    sys.exit(1)

# module wide global variables and configuration

def setup_logger(level=logging.INFO):
    if not hasattr(sys.modules[__name__], 'logger'):
        # First obtain a logger
        logger = logging.getLogger('GoogleScraper')
        logger.setLevel(level)

        ch = logging.StreamHandler(stream=sys.stderr)
        ch.setLevel(level)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        # add logger to the modules namespace
        setattr(sys.modules[__name__], 'logger', logger)

Config = {
    # The database name, with a timestamp as fmt
    'db': 'results_{asctime}.db',
    # The directory path for cached google results
    'do_caching': True,
    # If set, then compress/decompress files with this algorithm
    'compress_cached_files': True,
    # Whether caching shall be enabled
    'cachedir': '.scrapecache/',
    # After how many hours should the cache be cleaned
    'clean_cache_after': 24,
    # The maximal amount of selenium browser windows running in parallel
    'max_sel_browsers': 12,
    # Commit changes to db every N requests per GET/POST request
    'commit_interval': 10,
    # Whether to scrape with own ip address or just with proxies
    'use_own_ip': True,
    # The base Google URL for SelScraper objects
    'sel_scraper_base_url': 'http://www.google.com/ncr',
    # unique identifier that is sent to signal that a queue has
    # processed all inputs
    'all_processed_sig': 'kLQ#vG*jatBv$32JKlAvcK90DsvGskAkVfBr',
    # which browser to use with selenium. Valid values: ('Chrome', 'Firefox')
    'sel_browser': 'Chrome'
}

class GoogleSearchError(Exception): pass

class InvalidNumberResultsException(GoogleSearchError): pass


if Config['do_caching']:
    if not os.path.exists(Config['cachedir']):
        os.mkdir(Config['cachedir'], 0o744)


def maybe_clean_cache():
    """Delete all .cache files in the cache directory that are older than 12 hours."""
    for fname in os.listdir(Config['cachedir']):
        path = os.path.join(Config['cachedir'], fname)
        if time.time() > os.path.getmtime(path) + (60 * 60 * Config['clean_cache_after']):
            if os.path.isdir(path):
                import shutil
                shutil.rmtree(path)
            else:
                os.remove(os.path.join(Config['cachedir'], fname))

if Config['do_caching']:
    # Clean the Config['cachedir'] once in a while
    maybe_clean_cache()


def cached_file_name(kw, url=Config['sel_scraper_base_url'], params={}):
    """Make a unique file name based on the values of the google search parameters.

        kw -- The search keyword
        url -- The url for the search (without params)
        params -- GET params in the URL string

        If search_params is a dict, include both keys/values in the calculation of the
        file name. If a sequence is provided, just use the elements of the sequence to
        build the hash.

        Important! The order of the sequence is darn important! If search queries have same
        words but in a different order, they are individua searches.
    """
    assert isinstance(kw, str), kw
    assert isinstance(url, str), url
    if params:
        assert isinstance(params, dict)

    if params:
        unique = list(itertools.chain([kw], url, params.keys(), params.values()))
    else:
        unique = list(itertools.chain([kw], url))

    sha = hashlib.sha256()
    sha.update(b''.join(str(s).encode() for s in unique))
    return '{}.{}'.format(sha.hexdigest(), 'cache')


def get_cached(kw, url=Config['sel_scraper_base_url'], params={}, cache_dir=''):
    """Loads a cached search results page from CACHEDIR/fname.cache

    It helps in testing and avoid requesting
    the same resources again and again (such that google may
    recognize us as what we are: Sneaky SEO crawlers!)

    --search_params The parameters that identify the resource
    --decompress What algorithm to use for decompression
    """

    if Config['do_caching']:
        fname = cached_file_name(kw, url, params)

        if os.path.exists(cache_dir) and cache_dir:
            cdir = cache_dir
        else:
            cdir = Config['cachedir']

        try:
            if fname in os.listdir(cdir):
                # If the cached file is older than 12 hours, return False and thus
                # make a new fresh request.
                modtime = os.path.getmtime(os.path.join(cdir, fname))
                if (time.time() - modtime) / 60 / 60 > Config['clean_cache_after']:
                    return False
                path = os.path.join(cdir, fname)
                return read_cached_file(path)
        except FileNotFoundError as err:
            raise Exception('Unexpected file not found: {}'.format(err.msg))

    return False


def read_cached_file(path, n=2):
    """Read a zipped or unzipped cache file."""
    assert n != 0

    if Config['compress_cached_files']:
        with open(path, 'rb') as fd:
            try:
                data = zlib.decompress(fd.read()).decode()
                return data
            except zlib.error:
                Config['compress_cached_files'] = False
                return read_cached_file(path, n-1)
    else:
        with open(path, 'r') as fd:
            try:
                data = fd.read()
                return data
            except UnicodeDecodeError as e:
                # If we get this error, the cache files are probably
                # compressed but the 'compress_cached_files' flag was
                # set to false. Try to decompress them, but this may
                # lead to a infinite recursion. This isn't proper coding,
                # but convenient for the end user.
                Config['compress_cached_files'] = True
                return read_cached_file(path, n-1)

def cache_results(html, kw, url=Config['sel_scraper_base_url'], params={}):
    """Stores a html resource as a file in Config['cachedir']/fname.cache

    This will always write(overwrite) the cache file. If compress_cached_files is
    True, the page is written in bytes (obviously).
    """
    if Config['do_caching']:
        fname = cached_file_name(kw, url=url, params=params)
        path = os.path.join(Config['cachedir'], fname)

        if Config['compress_cached_files']:
            with open(path, 'wb') as fd:
                if isinstance(html, bytes):
                    fd.write(zlib.compress(html, 5))
                else:
                    fd.write(zlib.compress(html.encode('utf-8'), 5))
        else:
            with open(os.path.join(Config['cachedir'], fname), 'w') as fd:
                if isinstance(html, bytes):
                    fd.write(html.decode())
                else:
                    fd.write(html)

def _get_all_cache_files():
    """Return all files found in Config['cachedir']."""
    files = set()
    for dirpath, dirname, filenames in os.walk(Config['cachedir']):
        for name in filenames:
            files.add(os.path.join(dirpath, name))
    return files

def _caching_is_one_to_one(keywords, url=Config['sel_scraper_base_url']):
    mappings = {}
    for kw in keywords:
        hash = cached_file_name(kw, url)
        if hash not in mappings:
            mappings.update({hash: [kw, ]})
        else:
            mappings[hash].append(kw)

    duplicates = [v for k, v in mappings.items() if len(v) > 1]
    if duplicates:
        print('Not one-to-one. Hash function sucks. {}'.format(duplicates))
    else:
        print('one-to-one')
    sys.exit(0)

def parse_all_cached_files(keywords, conn, url=Config['sel_scraper_base_url'], try_harder=True, simulate=False):
    """Walk recursively through the cachedir (as given by the Config) and parse cache files.

    Arguments:
    keywords -- A sequence of keywords which were used as search query strings.

    Keyword arguments:
    dtokens -- A list of strings to add to each cached_file_name() call.
    with the contents of the <title></title> elements if necessary.
    conn -- A sqlite3 database connection.
    try_harder -- If there is a cache file that cannot be mapped to a keyword, read it and try it again with the query.

    Return:
    A list of keywords that couldn't be parsed and which need to be scraped freshly.
    """
    r = re.compile(r'<title>(?P<kw>.*?) - Google Search</title>')
    files = _get_all_cache_files()
    mapping = {cached_file_name(kw, url): kw for kw in keywords}
    diff = set(mapping.keys()).difference({os.path.split(path)[1] for path in files})
    logger.info('{} cache files found in {}'.format(len(files), Config['cachedir']))
    logger.info('{}/{} keywords have been cached and are ready to get parsed. {} remain to get scraped.'.format(len(keywords)-len(diff), len(keywords), len(diff)))
    if simulate:
        sys.exit(0)
    for path in files:
        fname = os.path.split(path)[1]
        query = mapping.get(fname)
        data = read_cached_file(path)
        if not query and try_harder:
            m = r.search(data)
            if m:
                query = m.group('kw').strip()
                if query in mapping.values():
                    logger.debug('The request with the keywords {} was wrongly cached.'.format(query))
                else:
                    continue
            else:
                continue
        _parse_links(data, conn.cursor(), query)
        mapping.pop(fname)
    conn.commit()

    # return the remaining keywords to scrape
    return mapping.values()

def fix_broken_cache_names(url=Config['sel_scraper_base_url']):
    """Fix the fucking broken cache fuck shit.

    @param url: A list of strings to add to each cached_file_name() call.
    @return: void you cocksucker
    """
    files = _get_all_cache_files()
    logger.debug('{} cache files found in {}'.format(len(files), Config['cachedir']))
    r = re.compile(r'<title>(?P<kw>.*?) - Google Search</title>')

    for i, path in enumerate(files):
        fname = os.path.split(path)[1].strip()
        data = read_cached_file(path)
        infilekws = r.search(data).group('kw')
        realname = cached_file_name(infilekws, url)
        if fname != realname:
            logger.debug('The search query in the title element in file {} differ from that hash of its name. Fixing...'.format(path))
            src = os.path.abspath(path)
            dst = os.path.abspath(os.path.join(os.path.split(path)[0], realname))
            logger.debug('Renamed from {} => {}'.format(src, dst))
            os.rename(src, dst)
    logger.debug('Renamed {} files.'.format(i))

def _parse_links(data, conn, kw, ip='127.0.0.1'):
    """Insert parsed data into the database. High level parsing function.

    Args:
    conn -- Either a sqlite3 cursor or connection object. If called in threads, make sure
    to wrap this function in some kind of synchronization functionality.
    """
    parser = Google_SERP_Parser(data)
    results = parser.links
    conn.execute(
        'INSERT INTO serp_page (requested_at, num_results, num_results_for_kw_google, search_query, requested_by) VALUES(?, ?, ?, ?, ?)',
        (time.asctime(), len(results), parser.num_results() or '',  kw, ip))
    lastrowid = conn.lastrowid
    #logger.debug('Inserting in link: search_query={}, title={}, url={}'.format(kw, ))
    conn.executemany('''INSERT INTO link
    (search_query,
     title,
     url,
     snippet,
     rank,
     domain,
     serp_id) VALUES(?, ?, ?, ?, ?, ?, ?)''',
    [(kw,
      result.link_title,
      result.link_url.geturl(),
      result.link_snippet,
      result.link_position,
      result.link_url.hostname) +
     (lastrowid, ) for result in results])

def _get_parse_links(data, kw, ip='127.0.0.1'):
    """Act the same as _parse_links, but just return the db data instead of inserting data into a connection or
    or building actual queries.

    [[lastrowid]] needs to be replaced with the last rowid from the database when inserting.

    Not secure against sql injections from google ~_~
    """
    parser = Google_SERP_Parser(data)
    results = parser.links
    first = (time.asctime(),
        len(results),
        parser.num_results() or '',
        kw,
        ip)

    second = []
    for result in results:
        second.append([kw,
          result.link_title,
          result.link_url.geturl(),
          result.link_snippet,
          result.link_position,
          result.link_url.hostname
        ])

    return (first, second)

def timer_support(Class):
    """In python versions prior to 3.3, threading.Timer
    seems to be a function that returns an instance
    of _Timer which is the class we want.
    """
    if isinstance(threading.Timer, (types.FunctionType, types.BuiltinFunctionType)) \
            and hasattr(threading, '_Timer'):
        timer_class = threading._Timer
    else:
        timer_class = threading.Timer

    class GoogleScrape(timer_class):
        def __init__(self, *args, **kwargs):
            # Signature of Timer or _Timer
            # def __init__(self, interval, function, args=None, kwargs=None):
            super().__init__(kwargs.get('interval'), self._search)
            self._init(*args, **kwargs)

    # add all attributes excluding __init__() and __dict__
    for name, attribute in Class.__dict__.items():
        if name not in ('__init__', '__dict__'):
            try:
                setattr(GoogleScrape, name, attribute)
            except AttributeError as ae:
                pass
    return GoogleScrape


@timer_support
class GoogleScrape():
    """Offers a fast way to query the google search engine.

    Overrides the run() method of the superclass threading.Timer.
    Each thread represents a crawl for one Google Results Page. Inheriting
    from threading.Timer allows the deriving class to delay execution of the run()
    method.

    http://www.blueglass.com/blog/google-search-url-parameters-query-string-anatomy/
    """

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

    def __init__(self, *args, **kwargs):
        """To be modified by the timer_support class decorator"""
        pass

    def _init(self, search_query, num_results_per_page=10, num_page=0, searchtype='normal', interval=0.0,
              search_params={}):
        """Initialises an object responsible for scraping one SERP page.

        @param search_query: The query to scrape for.
        @param num_results_per_page: The number of results per page. Must be smaller than 1000.
        (My tests though have shown that at most 100 results were returned per page)
        @param num_page: The number/index of the page.
        @param searchtype: The kind of search issued.
        @param interval: The amount of seconds to wait until executing run()
        @param search_params: A dictionary with additional search params. The default search params is updated with this parameter.
        """

        self.parser = None
        self.search_query = search_query
        self.searchtype = searchtype
        assert self.searchtype in ('normal', 'image', 'news', 'video')

        if num_results_per_page not in range(0,  1001):  # The maximum value of this parameter is 1000. See search appliance docs
            logger.error('The parameter -n must be smaller or equal to 1000')
            raise InvalidNumberResultsException(num_results_per_page)

        if num_page * num_results_per_page + num_results_per_page > 1000:
            logger.error('The maximal number of results for a query is 1000')
            raise InvalidNumberResultsException(num_page * num_results_per_page + num_results_per_page)

        self.num_results_per_page = num_results_per_page
        self.num_page = num_page

        self._SEARCH_URL = 'http://www.google.com/search'

        # http://www.rankpanel.com/blog/google-search-parameters/
        # typical chrome requests (on linux x64): https://www.google.de/search?q=hotel&oq=hotel&aqs=chrome.0.69i59j69i60l3j69i57j69i61.860j0j9&sourceid=chrome&espv=2&es_sm=106&ie=UTF-8
        # All values set to None, are NOT INCLUDED in the GET request! Everything else (also the empty string), is included in the request

        # http://lifehacker.com/5933248/avoid-getting-redirected-to-country-specific-versions-of-google

        # All search requests must include the parameters site, client, q, and output. All parameter values
        # must be URL-encoded (see “Appendix B: URL Encoding” on page 94), except where otherwise noted.
        self._SEARCH_PARAMS = {
            'q': '',  # the search query string
            'oq': None,  # Shows the original query.
            'num': '',  # the number of results per page
            'numgm': None,
            # Number of KeyMatch results to return with the results. A value between 0 to 50 can be specified for this option.
            'start': '0',
            # Specifies the index number of the first entry in the result set that is to be returned. page number = (start / num) + 1
            # The maximum number of results available for a query is 1,000, i.e., the value of the start parameter added to the value of the num parameter cannot exceed 1,000.
            'rc': None,  # Request an accurate result count for up to 1M documents.
            'site': None,
            # Limits search results to the contents of the specified collection. If a user submits a search query without the site parameter, the entire search index is queried.
            'sort': None,  # Specifies a sorting method. Results can be sorted by date.
            'client': 'firefox-a',
            # Required parameter. If this parameter does not have a valid value, other parameters in the query string
            #do not work as expected. Set to 'firefox-a' in mozilla firefox
            #A string that indicates a valid front end and the policies defined for it, including KeyMatches, related
            #queries, filters, remove URLs, and OneBox Modules. Notice that the rendering of the front end is
            #determined by the proxystylesheet parameter. Example: client=myfrontend
            'output': None,
            # required parameter. Selects the format of the search results. 'xml_no_dtd XML' : XML results or custom HTML, 'xml': XML results with Google DTD reference. When you use this value, omit proxystylesheet.
            'partialfields': None,
            # Restricts the search results to documents with meta tags whose values contain the specified words or phrases. Meta tag names or values must be double URL-encoded
            'requiredfields': None,
            #Restricts the search results to documents that contain the exact meta tag names or name-value pairs.
            #See “Meta Tags” on page 32 for more information.
            'pws': '0',  # personalization turned off
            'proxycustom': None,
            #Specifies custom XML tags to be included in the XML results. The default XSLT stylesheet uses these
            #values for this parameter: <HOME/>, <ADVANCED/>. The proxycustom parameter can be used in custom
            #XSLT applications. See “Custom HTML” on page 44 for more information.
            #This parameter is disabled if the search request does not contain the proxystylesheet tag. If custom
            #XML is specified, search results are not returned with the search request.
            'proxyreload': None,
            # Instructs the Google Search Appliance when to refresh the XSL stylesheet cache. A value of 1 indicates
            # that the Google Search Appliance should update the XSL stylesheet cache to refresh the stylesheet
            # currently being requested. This parameter is optional. By default, the XSL stylesheet cache is updated
            # approximately every 15 minutes.
            'proxystylesheet': None,
            #If the value of the output parameter is xml_no_dtd, the output format is modified by the
            # proxystylesheet value as follows:
            # 'Omitted': Results are in XML format.
            # 'Front End Name': Results are in Custom HTML format. The XSL stylesheet associated
            # with the specified Front End is used to transform the output.

            'cd': None,  # Passes down the keyword rank clicked.
            'filter': 0,  # Include omitted results if set to 0
            'complete': None,  #Turn auto-suggest and Google Instant on (=1) or off (=0)
            'nfpr': None,  #Turn off auto-correction of spelling on=1, off=0
            'ncr': None,
            #No country redirect: Allows you to set the Google country engine you would like to use despite your current geographic location.
            'safe': 'off',  # Turns the adult content filter on or off
            'rls': None,
            #Source of query with version of the client and language set. With firefox set to 'org.mozilla:en-US:official'
            'sa': None,
            # User search behavior parameter sa=N: User searched, sa=X: User clicked on related searches in the SERP
            'source': None,  #Google navigational parameter specifying where you came from, univ: universal search
            'sourceid': None,  # When searching with chrome, is set to 'chrome'
            'tlen': None,
            #Specifies the number of bytes that would be used to return the search results title. If titles contain
            # characters that need more bytes per character, for example in utf-8, this parameter can be used to
            # specify a higher number of bytes to get more characters for titles in the search results.
            'ud': None,
            #Specifies whether results include ud tags. A ud tag contains internationalized domain name (IDN)
            # encoding for a result URL. IDN encoding is a mechanism for including non-ASCII characters. When a ud
            # tag is present, the search appliance uses its value to display the result URL, including non-ASCII
            # characters.The value of the ud parameter can be zero (0) or one (1):
            # • A value of 0 excludes ud tags from the results.
            # • A value of 1 includes ud tags in the results.
            # As an example, if the result URLs contain files whose names are in Chinese characters and the ud
            # parameter is set to 1, the Chinese characters appear. If the ud parameter is set to 0, the Chinese
            # characters are escaped.
            'tbm': None,  # Used when you select any of the “special” searches, like image search or video search
            'tbs': None,
            # Also undocumented as `tbm`, allows you to specialize the time frame of the results you want to obtain.
            # Examples: Any time: tbs=qdr:a, Last second: tbs=qdr:s, Last minute: tbs=qdr:n, Last day: tbs=qdr:d, Time range: tbs=cdr:1,cd_min:3/2/1984,cd_max:6/5/1987
            # But the tbs parameter is also used to specify content:
            # Examples: Sites with images: tbs=img:1, Results by reading level, Basic level: tbs=rl:1,rls:0, Results that are translated from another language: tbs=clir:1,
            # For full documentation, see http://stenevang.wordpress.com/2013/02/22/google-search-url-request-parameters/
            'lr': None,
            # Restricts searches to pages in the specified language. If there are no results in the specified language, the search appliance displays results in all languages .
            # lang_xx where xx is the country code such as en, de, fr, ca, ...
            'hl': None,  # Language settings passed down by your browser
            'cr': None,  # The region the results should come from
            'gr': None,
            # Just as gl shows you how results look in a specified country, gr limits the results to a certain region
            'gcs': None,  # Limits results to a certain city, you can also use latitude and longitude
            'gpc': None,  #Limits results to a certain zip code
            'gm': None,  # Limits results to a certain metropolitan region
            'gl': None,  # as if the search was conducted in a specified location. Can be unreliable. for example: gl=countryUS
            'ie': 'UTF-8',  # Sets the character encoding that is used to interpret the query string.
            'oe': 'UTF-8',  # Sets the character encoding that is used to encode the results.
            'ip': None,
            # When queries are made using the HTTP protocol, the ip parameter contains the IP address of the user
            #who submitted the search query. You do not supply this parameter with the search request. The ip
            #parameter is returned in the XML search results. For example:
            'sitesearch': None,
            # Limits search results to documents in the specified domain, host, or web directory. Has no effect if the q
            # parameter is empty. This parameter has the same effect as the site special query term.
            # Unlike the as_sitesearch parameter, the sitesearch parameter is not affected by the as_dt
            # parameter. The sitesearch and as_sitesearch parameters are handled differently in the XML results.
            # The sitesearch parameter’s value is not appended to the search query in the results. The original
            # query term is not modified when you use the sitesearch parameter. The specified value for this
            # parameter must contain fewer than 125 characters.

            'access': 'a',  # Specifies whether to search public content (p), secure content (s), or both (a).
            'biw': None,  #Browser inner width in pixel
            'bih': None,  # Browser inner height in pixel

            'as_dt': None,  # If 'i' is supplied: Include only results in the web directory specified by as_sitesearch
            # if 'e' is given: Exclude all results in the web directory specified by as_sitesearch
            'as_epq': None,
            # Adds the specified phrase to the search query in parameter q. This parameter has the same effect as
            # using the phrase special query term (see “Phrase Search” on page 24).
            'as_eq': None,
            # Excludes the specified terms from the search results. This parameter has the same effect as using the exclusion (-) special query term (see “Exclusion” on page 22).
            'as_filetype': None,
            # Specifies a file format to include or exclude in the search results. Modified by the as_ft parameter.
            'as_ft': None,
            # Modifies the as_filetype parameter to specify filetype inclusion and exclusion options. The values for as_ft are: 'i': filetype and 'e': -filetype
            'as_lq': None,
            # Specifies a URL, and causes search results to show pages that link to the that URL. This parameter has
            #the same effect as the link special query term (see “Back Links” on page 20). No other query terms can
            #be used when using this parameter.
            'as_occt': None,
            # Specifies where the search engine is to look for the query terms on the page: anywhere on the page, in
            #the title, or in the URL.
            'as_oq': None,
            # Combines the specified terms to the search query in parameter q, with an OR operation. This parameter
            # has the same effect as the OR special query term (see “Boolean OR Search” on page 20).
            'as_q': None,  # Adds the specified query terms to the query terms in parameter q.
            'as_sitesearch': None,
            # Limits search results to documents in the specified domain, host or web directory, or excludes results
            #from the specified location, depending on the value of as_dt. This parameter has the same effect as the
            #site or -site special query terms. It has no effect if the q parameter is empty.
            'entqr': None,  # This parameter sets the query expansion policy according to the following valid values:
            # 0: None
            # 1: Standard Uses only the search appliance’s synonym file.
            # 2: Local Uses all displayed and activated synonym files.
            # 3: Full Uses both standard and local synonym files.
        }

        # Maybe update the default search params when the user has supplied a dictionary
        if search_params is not None and isinstance(search_params, dict):
            self._SEARCH_PARAMS.update(search_params)

        self.SEARCH_RESULTS = {
            'cache_file': None,  # A path to a file that caches the results.
            'search_keyword': self.search_query,  # The query keyword
        }

    def _set_proxy(self):
        pass
        # if args.proxy:
        #     def create_connection(address, timeout=None, source_address=None):
        #         sock = socks.socksocket()
        #         sock.connect(address)
        #         return sock
        #
        #     proxy_host, proxy_port = args.proxy.split(':')
        #
        #     # Patch the socket module
        #     socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, proxy_host, int(proxy_port),
        #                           rdns=True)  # rdns is by default on true. Never use rnds=False with TOR, otherwise you are screwed!
        #     socks.wrap_module(socket)
        #     socket.create_connection = create_connection


    def reset_search_params(self):
        """Reset all search params to None.
            Such that they won't be used in the query
        """
        for k, v in self._SEARCH_PARAMS.items():
            self._SEARCH_PARAMS[k] = None

    def _build_query(self, rand=False):
        """Build the headers and params for the GET request for the Google server.

        When random is True, several headers (like the UA) are chosen
        randomly.

        There are currently four different Google searches supported:
        - The normal web search: 'normal'
        - image search: 'image'
        - video search: 'video'
        - news search: 'news'
        """

        # params used by all search-types
        self._SEARCH_PARAMS.update(
            {
                'q': self.search_query,
            })

        if self.searchtype == 'normal':
            # The normal web search. That's what you probably want
            self._SEARCH_PARAMS.update(
                {
                    'num': str(self.num_results_per_page),
                    'start': str(int(self.num_results_per_page) * int(self.num_page))
                })
        elif self.searchtype == 'image':
            # Image raw search url for keyword 'cat' in mozilla 27.0.1
            # 'q' and tbs='isch' are sufficient for a search
            # https://www.google.com/search?q=cat&client=firefox-a&rls=org.mozilla:en-US:official&channel=sb&noj=1&source=lnms&tbm=isch&sa=X&ei=XX8dU93kMMbroAS5_IGwBw&ved=0CAkQ_AUoAQ&biw=1920&bih=881
            # Link that Chromium generates: https://www.google.com/search?site=imghp&tbm=isch&source=hp&biw=1536&bih=769&q=good+view&oq=good+view&gs_l=img.3..0l10.18.3212.0.3351.17.16.1.0.0.0.355.2509.3j9j0j3.15.0....0...1ac.1.37.img..6.11.1342.tSOKFxzvFbE
            self.reset_search_params()
            self._SEARCH_PARAMS.update(
                {
                    'q': self.search_query,
                    'oq': self.search_query,
                    'site': 'imghp',
                    'tbm': 'isch',
                    'source': 'hp',
                    #'sa': 'X',
                    'biw': 1920,
                    'bih': 881
                })
        elif self.searchtype == 'video':
            # Video search raw url with keyword 'cat' in mozilla 27.0.1
            # 'q' and tbs='vid' are sufficient for a search
            # https://www.google.com/search?q=cat&client=firefox-a&rls=org.mozilla:en-US:official&channel=sb&noj=1&tbm=vid&source=lnms&sa=X&ei=DoAdU9uxHdGBogTp8YLACQ&ved=0CAoQ_AUoAg&biw=1920&bih=881&dpr=1
            self._SEARCH_PARAMS.update(
                {
                    'num': str(self.num_results_per_page),
                    'start': str(int(self.num_results_per_page) * int(self.num_page)),
                    'tbm': 'vid',
                    'source': 'lnms',
                    'sa': 'X',
                    'biw': 1920,
                    'bih': 881
                })
        elif self.searchtype == 'news':
            # pretty much as above;
            # 'q' and tbs='nws' are perfectly fine for a news search
            # But there is a more elaborate Google news search with a different URL on: https://news.google.com/nwshp?
            # this code only handles the standard search news
            self._SEARCH_PARAMS.update(
                {
                    'num': str(self.num_results_per_page),
                    'start': str(int(self.num_results_per_page) * int(self.num_page)),
                    'tbm': 'nws',
                    'source': 'lnms',
                    'sa': 'X'
                })

        if rand:
            self._HEADERS['User-Agent'] = random.choice(self._UAS)

    def _search(self, searchtype='normal'):
        """The actual search and parsing of the results.

        Private, internal method.
        Parsing is done with lxml and cssselect. The html structure of the Google Search
        results may change over time. Effective: February 2014

        There are several parts of a SERP results page the average user is most likely interested:

        (Probably in this order)
        - Non-advertisement links, as well as their little snippet and title
        - The message that indicates how many results were found. For example: "About 834,000,000 results (0.39 seconds)"
        - Advertisement search results (links, titles, snippets like above)

        Problem: This data comes in a wide range of different formats, depending on the parameters set in the search.
        Investigations over the different formats are done in the directory tests/serp_formats.

        """
        self._build_query(searchtype)

        # After building the query, all parameters are set, so we know what we're requesting.
        logger.debug("Created new GoogleScrape object with searchparams={}".format(pprint.pformat(self._SEARCH_PARAMS)))

        html = get_cached(self.search_query, self._SEARCH_URL, params=self._SEARCH_PARAMS)
        self.SEARCH_RESULTS['cache_file'] = os.path.join(Config['cachedir'], cached_file_name(self.search_query, self._SEARCH_URL, self._SEARCH_PARAMS))

        if not html:
            try:
                r = requests.get(self._SEARCH_URL, headers=self._HEADERS,
                                 params=self._SEARCH_PARAMS, timeout=3.0)

                logger.debug("Scraped with url: {} and User-Agent: {}".format(r.url, self._HEADERS['User-Agent']))

            except requests.ConnectionError as cerr:
                print('Network problem occurred {}'.format(cerr.msg))
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
            cache_results(html, self.search_query, url=self._SEARCH_URL, params=self._SEARCH_PARAMS)
            self.SEARCH_RESULTS['cache_file'] = os.path.join(Config['cachedir'], cached_file_name(self.search_query, self._SEARCH_URL, self._SEARCH_PARAMS))

        self.parser = Google_SERP_Parser(html, searchtype=self.searchtype)
        self.SEARCH_RESULTS.update(self.parser.all_results)

    @property
    def results(self):
        return self.SEARCH_RESULTS


class SelScraper(threading.Thread):
    """Instances of this class make use of selenium browser objects to query Google."""

    def __init__(self, keywords, rlock, queue, config={}, proxy=None, browser_num=0):
        super().__init__()
        # the google search url
        logger.info('[+] SelScraper object created. Number of keywords to scrape={}, using proxy={}, number of pages={}, browser_num={}'.format(len(keywords), proxy, config.get('num_pages', '1'), browser_num))
        self.url = Config['sel_scraper_base_url']
        self.proxy = proxy
        self.browser_num = browser_num
        self.queue = queue
        self.rlock = rlock
        self.keywords = set(keywords)
        self.ip = '127.0.0.1'
        self._parse_config(config)

    def _parse_config(self, config):
        """Parse the config parameter given in the constructor.

        First apply some default values. The config parameter overwrites them, if given.
        """
        assert isinstance(config, dict)

        self.config = {}
        # Set some defaults
        # How long to sleep (ins seconds) after every n-th request
        self.config['sleeping_ranges'] = {
            7: (1, 5),
            # 19: (20, 40),
            57: (50, 120),
            # 127: (60*3, 60*6)
        }
        self.config['num_results'] = 10
        self.config['num_pages'] = 1
        # and overwrite with options given with the constructors parameter
        for key, value in config.items():
            self.config.update({key: value})

    def _largest_sleep_range(self, i):
        assert i >= 0
        if i != 0:
            s = sorted(self.config['sleeping_ranges'].keys(), reverse=True)
            for n in s:
                if i % n == 0:
                    return self.config['sleeping_ranges'][n]
        # sleep one second
        return (1, 2)

    def _maybe_crop(self, html):
        """Crop Google SERP pages if we find the needle that indicates the beginning of the main content.

        Use lxml.html (fast) to crop the selections.

        Args:
        html -- The html to crop.

        Returns:
        The cropped html.
        """
        parsed = lxml.html.fromstring(html)
        for bad in parsed.xpath('//script|//style'):
            bad.getparent().remove(bad)

        return lxml.html.tostring(parsed)

    def _get_webdriver(self):
        """Return a webdriver instance and set it up with the according profile/ proxies.

        May either return a Firefox or Chrome instance, according to availabilit. Chrome has
        precedence, because it's more lightweight.
        """
        if Config['sel_browser'].lower() == 'chrome':
            self._get_Chrome()
            return True
        elif Config['sel_browser'].lower() == 'firefox':
            self._get_Firefox()
            return True

        # if the config remains silent, try to get Chrome, else Firefox
        if not self._get_Chrome():
            self._get_Firefox()

        return True

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
            logger.info(e)
            # we dont have a chrome executable or a chrome webdriver installed
        return False

    def _get_Firefox(self):
        try:
            if self.proxy:
                profile = webdriver.FirefoxProfile()
                profile.set_preference("network.proxy.type", 1) # this means that the proxy is user set, regardless of the type
                if self.proxy.proto.startswith('socks'):
                    profile.set_preference("network.proxy.socks", self.proxy.host)
                    profile.set_preference("network.proxy.socks_port", self.proxy.ip)
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
            logger.info(e)
            # reaching here is bad, since we have no available webdriver instance.
        return False

    def run(self):
        # Create the browser and align it according to its number
        # and in maximally two rows
        if len(self.keywords) <= 0:
            return True

        self._get_webdriver()
        self.webdriver.set_window_size(400, 400)
        self.webdriver.set_window_position(400*(self.browser_num % 4), 400*(self.browser_num > 4))

        next_url = ''
        write_kw = True
        for i, kw in enumerate(self.keywords):
            if not kw:
                continue
            for page_num in range(0, int(self.config.get('num_pages'))):
                if not next_url:
                    next_url = self.url
                self.webdriver.get(next_url)
                # match the largest sleep range
                r = self._largest_sleep_range(i)
                j = random.randrange(*r)
                if self.proxy:
                    logger.info('[i] Page number={}, ScraperThread({url}) ({ip}:{port} {} is sleeping for {} seconds...Next keyword: ["{kw}"]'.format(page_num, self._ident, j, url= next_url, ip=self.proxy.host, port=self.proxy.port, kw=kw))
                else:
                    logger.info('[i] Page number={}, ScraperThread({url}) ({} is sleeping for {} seconds...Next keyword: ["{}"]'.format(page_num, self._ident, j, kw, url=next_url))
                time.sleep(j)
                try:
                    self.element = WebDriverWait(self.webdriver, 30).until(EC.presence_of_element_located((By.NAME, "q")))
                except Exception as e:
                    raise Exception(e) # fix that later
                if write_kw:
                    self.element.clear()
                    time.sleep(.25)
                    self.element.send_keys(kw + Keys.ENTER)
                    write_kw = False
                # Waiting until the keyword appears in the title may
                # not be enough. The content may still be off the old page.
                try:
                    WebDriverWait(self.webdriver, 30).until(EC.title_contains(kw))
                except TimeoutException as e:
                    print('Keyword not found in title: {}'.format(e))
                    continue

                try:
                    next_url = self.webdriver.find_element_by_css_selector('#pnnext').get_attribute('href')
                except WebDriverException as e:
                    # leave if no next results page is available
                    break

                # That's because we sleep explicitly one second, so the site and
                # whatever js loads all shit dynamically has time to update the
                # DOM accordingly.
                time.sleep(2.5)

                html = self._maybe_crop(self.webdriver.page_source)
                # Lock for the sake that two threads write to same file (not probable)
                self.rlock.acquire()
                cache_results(html, kw, url=self.url)
                self.rlock.release()
                # commit in intervals specified in the config
                self.queue.put(_get_parse_links(html, kw, ip=self.ip))

        self.webdriver.close()

class Google_SERP_Parser():
    """Parses data from Google SERPs."""

    # Named tuple type for the search results
    Result = namedtuple('LinkResult', 'link_title link_snippet link_url link_position')

    # short alias because we use it so extensively
    _xp = HTMLTranslator().css_to_xpath

    # Valid URL (taken from django)
    _REGEX_VALID_URL = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    _REGEX_VALID_URL_SIMPLE = re.compile(
        'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')

    def __init__(self, html, searchtype='normal'):
        self.html = html
        self.searchtype = searchtype
        self.dom = None

        self.SEARCH_RESULTS = {'num_results_for_kw': []}

        # Try to parse the google HTML result using lxml
        try:
            doc = UnicodeDammit(self.html, is_html=True)
            parser = lxml.html.HTMLParser(encoding=doc.declared_html_encoding)
            self.dom = lxml.html.document_fromstring(self.html, parser=parser)
            self.dom.resolve_base_href()
        except Exception as e:
            print('Some error occurred while lxml tried to parse: {}'.format(e))

        # Very redundant by now, but might change in the soon future
        if self.searchtype == 'normal':
            self.SEARCH_RESULTS.update({
                'results': [],  # List of Result, list of named tuples
                'ads_main': [],  # The google ads in the main result set.
                'ads_aside': [],  # The google ads on the right aside.
            })
        elif self.searchtype == 'video':
            self.SEARCH_RESULTS.update({
                'results': [],  # Video search results
                'ads_main': [],  # The google ads in the main result set.
                'ads_aside': [],  # The google ads on the right aside.
            })
        elif self.searchtype == 'image':
            self.SEARCH_RESULTS.update({
                'results': [],  # Images links
            })
        elif self.searchtype == 'news':
            self.SEARCH_RESULTS.update({
                'results': [],  # Links from news search
                'ads_main': [],  # The google ads in the main result set.
                'ads_aside': [],  # The google ads on the right aside.
            })

        ### the actual PARSING happens here
        parsing_actions = {
            'normal': self._parse_normal_search,
            'image': self._parse_image_search,
            'video': self._parse_video_search,
            'news': self._parse_news_search,
        }
        # Call the correct parsing method
        parsing_actions.get(self.searchtype)(self.dom)

        # Clean the results
        self._clean_results()

    def __iter__(self):
        """Simple magic method to iterate quickly over found non ad results"""
        for link_title, link_snippet, link_url in self.result['results']:
            yield (link_title, link_snippet, link_url)

    def num_results(self):
        """Returns the number of pages found by keyword as shown in top of SERP page."""
        return self.SEARCH_RESULTS['num_results_for_kw']

    @property
    def results(self):
        """Returns all results including sidebar and main result advertisements"""
        return {k: v for k, v in self.SEARCH_RESULTS.items() if k not in
                                                                ('num_results_for_kw', )}
    @property
    def all_results(self):
        return self.SEARCH_RESULTS

    @property
    def links(self):
        """Only returns non ad results"""
        return self.SEARCH_RESULTS['results']

    def _clean_results(self):
        """Cleans/extracts the found href or data-href attributes."""

        # Now try to create ParseResult objects from the URL
        for key in ('results', 'ads_aside', 'ads_main'):
            for i, e in enumerate(self.SEARCH_RESULTS[key]):
                # First try to extract the url from the strange relative /url?sa= format
                matcher = re.search(r'/url\?q=(?P<url>.*?)&sa=U&ei=', e.link_url)
                if matcher:
                    url = matcher.group(1)
                else:
                    url = e.link_url

                self.SEARCH_RESULTS[key][i] = \
                    self.Result(link_title=e.link_title, link_url=urllib.parse.urlparse(url),
                                link_snippet=e.link_snippet, link_position=e.link_position)

    def _parse_num_results(self):
        # try to get the number of results for our search query
        try:
            self.SEARCH_RESULTS['num_results_for_kw'] = \
                self.dom.xpath(self._xp('div#resultStats'))[0].text_content()
        except Exception as e:
            logger.critical(e)
            print(sys.exc_info())

    def _parse_normal_search(self, dom):
        """Specifies the CSS selectors to extract links/snippets for a normal search.

        @param dom The page source to parse.
        """

        # There might be several list of different css selectors to handle different SERP formats
        css_selectors = {
            # to extract all links of non-ad results, including their snippets(descriptions) and titles.
            'results': (['li.g', 'h3.r > a:first-child', 'div.s span.st'], ),
            # to parse the centered ads
            'ads_main': (['div#center_col li.ads-ad', 'h3.r > a', 'div.ads-creative'],
                         ['div#tads li', 'h3 > a:first-child', 'span:last-child']),
            # the ads on on the right
            'ads_aside': (['#rhs_block li.ads-ad', 'h3.r > a', 'div.ads-creative'], ),
        }
        self._parse(dom, css_selectors)

    def _parse_image_search(self, dom):
        """Specifies the CSS selectors to extract links/snippets for a image search."""
        css_selectors = {
            'results': (['div.rg_di', 'a:first-child', 'span.rg_ilmn'], )
        }
        self._parse(dom, css_selectors)

    def _parse_video_search(self, dom):
        """Specifies the CSS selectors to extract links/snippets for a video search.

        Very similar to a normal search. Basically the same. But this is a unique method
        because the parsing logic may change over time.
        """
        css_selectors = {
            # to extract all links of non-ad results, including their snippets(descriptions) and titles.
            'results': (['li.g', 'h3.r > a:first-child', 'div.s > span.st'], ),
            # to parse the centered ads
            'ads_main': (['div#center_col li.ads-ad', 'h3.r > a', 'div.ads-creative'],
                         ['div#tads li', 'h3 > a:first-child', 'span:last-child']),
            # the ads on on the right
            'ads_aside': (['#rhs_block li.ads-ad', 'h3.r > a', 'div.ads-creative'], ),
        }
        self._parse(dom, css_selectors)

    def _parse_news_search(self, dom):
        """Specifies the CSS selectors to extract links/snippets for a news search.

        Is also similar to a normal search. But must be a separate function since
        https://news.google.com/nwshp? needs own parsing code...
        """
        css_selectors = {
            # to extract all links of non-ad results, including their snippets(descriptions) and titles.
            # The first CSS selector is the wrapper element where the search results are situated
            # the second CSS selector selects the link and the title. If there are 4 elements in the list, then
            # the second and the third element are for the link and the title.
            # the 4th selector is for the snippet.
            'results': (['li.g', 'h3.r > a:first-child', 'div.s span.st'], ),
            # to parse the centered ads
            'ads_main': (['div#center_col li.ads-ad', 'h3.r > a', 'div.ads-creative'],
                         ['div#tads li', 'h3 > a:first-child', 'span:last-child']),
            # the ads on on the right
            'ads_aside': (['#rhs_block li.ads-ad', 'h3.r > a', 'div.ads-creative'], ),
        }
        self._parse(dom, css_selectors)

    def _parse(self, dom, css_selectors):
        """Generic parse method"""
        for key, slist in css_selectors.items():
            for selectors in slist:
                self.SEARCH_RESULTS[key].extend(self._parse_links(dom, *selectors))
        self._parse_num_results()

    def _parse_links(self, dom, container_selector, link_selector, snippet_selector):
        links = []
        # Try to extract all links of non-ad results, including their snippets(descriptions) and titles.
        # The parsing should be as robust as possible. Sometimes we can't extract all data, but as much as humanly
        # possible.
        rank = 0
        try:
            li_g_results = dom.xpath(self._xp(container_selector))
            for i, e in enumerate(li_g_results):
                snippet = link = title = ''
                try:
                    link_element = e.xpath(self._xp(link_selector))
                    link = link_element[0].get('href')
                    title = link_element[0].text_content()
                    # For every result where we can parse the link and title, increase the rank
                    rank += 1
                except IndexError as err:
                    logger.debug(
                        'Error while parsing link/title element with selector={}: {}'.format(link_selector, err))
                try:
                    for r in e.xpath(self._xp(snippet_selector)):
                        snippet += r.text_content()
                except Exception as err:
                    logger.debug('Error in parsing snippet with selector={}.Error: {}'.format(
                                            snippet_selector, repr(e), err))

                links.append(self.Result(link_title=title, link_url=link, link_snippet=snippet, link_position=rank))
        # Catch further errors besides parsing errors that take shape as IndexErrors
        except Exception as err:
            logger.error('Error in parsing result links with selector={}: {}'.format(container_selector, err))
        return links or []


class ResultsHandler(threading.Thread):
    """Consume data that the SelScraper/GoogleScrape threads put in the queue.

    Opens a database connection and puts data in it. Intended to run be run in the main thread.

    Implements the multi-producer pattern.

    The ResultHandler cannot necessarily know when he should stop waiting. Thats why we
    have a special DONE element in the Config that signals that all threads have finished and
    all data was processed.
    """
    def __init__(self, queue, conn):
        super().__init__()
        self.queue = queue
        self.conn = conn
        self.cursor = self.conn.cursor()

    def _insert_in_db(self, e):
        assert isinstance(e, tuple) and len(e) == 2
        first, second = e
        self.cursor.execute(
            'INSERT INTO serp_page (requested_at, num_results, num_results_for_kw_google, search_query, requested_by) VALUES(?, ?, ?, ?, ?)', first)
        lastrowid = self.cursor.lastrowid
        #logger.debug('Inserting in link: search_query={}, title={}, url={}'.format(kw, ))
        self.cursor.executemany('''INSERT INTO link
        (search_query,
         title,
         url,
         snippet,
         rank,
         domain,
         serp_id) VALUES(?, ?, ?, ?, ?, ?, ?)''', [tuple(t)+ (lastrowid, ) for t in second])

    def run(self):
        i = 0
        while True:
            #  If optional args block is true and timeout is None (the default), block if necessary until an item is available.
            item = self.queue.get(block=True)
            if item == Config['all_processed_sig']:
                print('turning down. All results processed.')
                break
            self._insert_in_db(item)
            self.queue.task_done()
            # Store the
            if i > 0 and (i % Config['commit_interval']) == 0:
                # commit in intervals specified in the config
                self.conn.commit()
            i += 1


def scrape(query, num_results_per_page=100, num_pages=1, offset=0, searchtype='normal'):
    """Public API function to search for terms and return a list of results.

    A default scrape does start each thread in intervals of 1 second.
    This (maybe) prevents Google to sort us out because of aggressive behaviour.

    arguments:
    query -- the search query. Can be whatever you want to crawl google for.

    Keyword arguments:
    num_results_per_page -- the number of results per page. Either 10, 25, 50 or 100.
    num_pages -- The number of pages to search for.
    offset -- specifies the offset to the page to begin searching.

    """
    threads = [GoogleScrape(query, num_results_per_page, i, searchtype=searchtype, interval=i)
                   for i in range(offset, num_pages + offset, 1)]

    for t in threads:
        t.start()

    # wait for all threads to end running
    for t in threads:
        t.join(3.0)

    return [t.results for t in threads]


def deep_scrape(query):
    """Launches many different Google searches with different parameter combinations to maximize return of results. Depth first.

    This is the heart of GoogleScraper.py. The aim of deep_scrape is to maximize the number of links for a given keyword.
    In order to achieve this goal, we'll heavily combine and rearrange a predefined set of search parameters to force Google to
    yield unique links:
    - different date-ranges for the keyword
    - using synonyms of the keyword
    - search for by different reading levels
    - search by different target languages (and translate the query in this language)
    - diversify results by scraping image search, news search, web search (the normal one) and maybe video search...

    From the google reference:
    When the Google Search Appliance filters results, the top 1000 most relevant URLs are found before the
    filters are applied. A URL that is beyond the top 1000 most relevant results is not affected if you change
    the filter settings.

    This means that altering filters (duplicate snippet filter and duplicate directory filter) wont' bring us further.

    @param query: The query/keyword to search for.
    @return: All the result sets.
    """

    # First obtain some synonyms for the search query

    # For each proxy, run the scrapes

def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    groups = itertools.zip_longest(*args, fillvalue=fillvalue)
    return [list(filter(None.__ne__, list(group))) for group in groups]

def maybe_create_db():
    """Creates a little sqlite database to include at least the columns:
        - query
       - rank (1-10)
       - title
       - snippet
       - url
       - domain

    Test sql query: SELECT L.title, L.snippet, SP.search_query FROM link AS L LEFT JOIN serp_page AS SP ON L.serp_id = SP.id
    """
    # Save the database to a unique file name (with the timestamp as suffix)
    Config['db'] = Config['db'].format(asctime=str(time.asctime()).replace(' ', '_').replace(':', '-'))

    if os.path.exists(Config['db']) and os.path.getsize(Config['db']) > 0:
        conn = sqlite3.connect(Config['db'], check_same_thread=False)
        cursor = conn.cursor()
        return conn
    else:
        # set that bitch up the first time
        conn = sqlite3.connect(Config['db'], check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE serp_page
        (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             requested_at TEXT NOT NULL,
             num_results INTEGER NOT NULL,
             num_results_for_kw_google TEXT,
             search_query TEXT NOT NULL,
             requested_by TEXT
         )''')
        cursor.execute('''
        CREATE TABLE link
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_query TEXT NOT NULL,
            title TEXT,
            snippet TEXT,
            url TEXT,
            domain TEXT,
            rank INTEGER NOT NULL,
            serp_id INTEGER NOT NULL,
            FOREIGN KEY(serp_id) REFERENCES serp_page(id)
        )''')

        conn.commit()
        return conn

def parse_proxy_file(fname):
    """Parses a proxy file
        The format should be like the following:

        socks5 23.212.45.13:1080 username:password
        socks4 23.212.45.13:80 username:password
        http 23.212.45.13:80

        If username and password aren't provided, GoogleScraper assumes
        that the proxy doesn't need auth credentials.
    """
    proxies = []
    Proxy = namedtuple('Proxy', 'proto, host, port, username, password')
    path = os.path.join(os.getcwd(), fname)
    if os.path.exists(path):
        with open(path, 'r') as pf:
            for line in pf.readlines():
                tokens = line.replace('\n', '').split(' ')
                try:
                    proto = tokens[0]
                    host, port = tokens[1].split(':')
                except:
                    raise Exception('Invalid proxy file. Should have the following format: {}'.format(parse_proxy_file.__doc__))
                if len(tokens) == 3:
                    username, password = tokens[2].split(':')
                    proxies.append(Proxy(proto=proto, host=host, port=port, username=username, password=password))
                else:
                    proxies.append(Proxy(proto=proto, host=host, port=port, username='', password=''))
        return proxies
    else:
        raise ValueError('No such file')

def print_scrape_results_http(results, verbosity=1, view=False):
    """Print the results obtained by "http" method."""
    for t in results:
        for result in t:
            logger.info('{} links found! The search with the keyword "{}" yielded the result:{}'.format(
                len(result['results']), result['search_keyword'], result['num_results_for_kw']))
            if view:
                import webbrowser
                webbrowser.open(result['cache_file'])
            import textwrap

            for result_set in ('results', 'ads_main', 'ads_aside'):
                if result_set in result.keys():
                    print('### {} link results for "{}" ###'.format(len(result[result_set]), result_set))
                    for link_title, link_snippet, link_url, link_position in result[result_set]:
                        try:
                            print('  Link: {}'.format(urllib.parse.unquote(link_url.geturl())))
                        except AttributeError as ae:
                            print(ae)
                        if verbosity > 1:
                            print(
                                '  Title: \n{}'.format(textwrap.indent('\n'.join(textwrap.wrap(link_title, 50)), '\t')))
                            print(
                                '  Description: \n{}\n'.format(
                                    textwrap.indent('\n'.join(textwrap.wrap(link_snippet, 70)), '\t')))
                            print('*' * 70)
                            print()

def get_command_line():
    """Parses command line arguments for scraping with selenium browser instances"""
    parser = argparse.ArgumentParser(prog='GoogleScraper',
                                     description='Scrapes the Google search engine by forging http requests that imitate '
                                                 'browser searches or by using real browsers controlled with selenium.',
                                     epilog='This program might infringe the Google TOS, so use it on your own risk. (c) by Nikolai Tschacher, 2012-2014. incolumitas.com')

    parser.add_argument('scrapemethod', type=str,
                        help='The scraping type. There are currently two types: "http" and "sel". Http scrapes with raw http requests whereas "sel" uses selenium remote browser programming',
                        choices=('http', 'sel'), default='sel')
    parser.add_argument('-q', '--keyword', metavar='keyword', type=str, action='store', dest='keyword', help='The search keyword to scrape for. If you need to scrape multiple keywords, use the --keyword-file flag')
    parser.add_argument('--keyword-file', type=str, action='store', dest='kwfile',
                        help='Keywords to search for. One keyword per line. Empty lines are ignored.')
    parser.add_argument('-n', '--num-results-per-page', metavar='number_of_results_per_page', type=int,
                         action='store', default=50,
                        help='The number of results per page. Most be >= 100')
    parser.add_argument('-p', '--num-pages', metavar='num_of_pages', type=int, dest='num_pages', action='store',
                        default=1, help='The number of pages to request for each keyword. Each page is requested by a unique connection and if possible by a unique IP (at least in "http" mode).')
    parser.add_argument('-s', '--storing-type', metavar='results_storing', type=str, dest='storing_type',
                        action='store',
                        default='stdout', choices=('database', 'stdout'), help='Where/how to put/show the results.')
    parser.add_argument('-t', '--search_type', metavar='search_type', type=str, dest='searchtype', action='store',
                        default='normal',
                        help='The searchtype to launch. May be normal web search, image search, news search or video search.')
    parser.add_argument('--proxy-file', metavar='proxyfile', type=str, dest='proxy_file', action='store',
                        required=False,  #default='.proxies'
                        help='''A filename for a list of proxies (supported are HTTP PROXIES, SOCKS4/5) with the following format: "Proxyprotocol (proxy_ip|proxy_host):Port\\n"
                        Example file: socks4 127.0.0.1:99\nsocks5 33.23.193.22:1080\n''')
    parser.add_argument('--simulate', action='store_true', default=False, required=False, help='''If this flag is set to True, the scrape job and its rough length will be printed.''')
    parser.add_argument('--print', action='store_true', default=True, required=False, help='''If set, print all scraped output GoogleScraper finds. Don't use it when scraping a lot, results are stored in a sqlite3 database anyway.''')
    parser.add_argument('-x', '--deep-scrape', action='store_true', default=False,
                        help='Launches a wide range of parallel searches by modifying the search ' \
                             'query string with synonyms and by scraping with different Google search parameter combinations that might yield more unique ' \
                             'results. The algorithm is optimized for maximum of results for a specific keyword whilst trying avoid detection. This is the heart of GoogleScraper.')
    parser.add_argument('--view', action='store_true', default=False, help="View the response in a default browser tab."
                                                                           " Mainly for debug purposes. Works only when caching is enabled.")
    parser.add_argument('--fix-cache-names', action='store_true', default=False, help="For internal use only. Renames the cache files after a hash constructed after the keywords located in the <title> tag.")
    parser.add_argument('--check-oto', action='store_true', default=False, help="For internal use only. Checks whether all the keywords are cached in different files.")
    parser.add_argument('-v', '--verbosity', type=int, default=1,
                        help="The verbosity of the output reporting for the found search results.")
    parser.add_argument('--debug', action='store_true', default=False, help='Whether to set logging to level DEBUG.')
    return parser.parse_args()


def handle_commandline(args):
    """Handles the command line arguments as supplied by get_command_line()"""

    if args.debug:
        setup_logger(logging.DEBUG)
    else:
        setup_logger(logging.INFO)

    if args.keyword and args.kwfile:
        raise ValueError(
           'Invalid command line usage. Either set keywords as a string or provide a keyword file, but not both you dirty cocksucker')
    elif not args.keyword and not args.kwfile:
        raise ValueError('You must specify a keyword file (separated by newlines, each keyword on a line) with the flag `--keyword-file {filepath}~')

    if args.fix_cache_names:
        fix_broken_cache_names()
        sys.exit('renaming done. restart for normal use.')

    keywords = [args.keyword,]
    if args.kwfile:
        if not os.path.exists(args.kwfile):
            raise ValueError('The keyword file {} does not exist.'.format(args.kwfile))
        else:
            # Clean the keywords of duplicates right in the beginning
            keywords = set([line.strip() for line in open(args.kwfile, 'r').read().split('\n')])

    if args.check_oto:
        _caching_is_one_to_one(args.keyword)

    if int(args.num_results_per_page) > 100:
        raise ValueError('Not more that 100 results per page available for google.com')

    if args.proxy_file:
        proxies = parse_proxy_file(args.proxy_file)
    else:
        proxies = []

    valid_search_types = ('normal', 'video', 'news', 'image')
    if args.searchtype not in valid_search_types:
        ValueError('Invalid search type! Select one of {}'.format(repr(valid_search_types)))

    # Let the games begin
    if args.scrapemethod == 'sel':
        conn = maybe_create_db()
        # First of all, lets see how many keywords remain to scrape after parsing the cache
        if Config['do_caching']:
            remaining = parse_all_cached_files(keywords, conn, simulate=args.simulate)
        else:
            remaining = keywords

        if args.simulate:
            # TODO: implement simulation
            raise NotImplementedError('simulating is not implemented yet!')

        rlock = threading.RLock()

        if len(remaining) > Config['max_sel_browsers']:
            kwgroups = grouper(remaining, len(remaining)//Config['max_sel_browsers'], fillvalue=None)
        else:
            # thats a little special there :)
            kwgroups = [[kw, ] for kw in remaining]

        # Distribute the proxies evenly on the kws to search
        scrapejobs = []
        Q = queue.Queue()
        proxies.append(None) if Config['use_own_ip'] else None
        if not proxies:
            logger.info("No ip's available for scanning.")

        config = {
            'num_results': args.num_results_per_page,
            'num_pages': args.num_pages
        }
        chunks_per_proxy = math.ceil(len(kwgroups)/len(proxies))
        for i, chunk in enumerate(kwgroups):
            if args.scrapemethod == 'sel':
                scrapejobs.append(SelScraper(chunk, rlock, Q, browser_num=i, config=config, proxy=proxies[i//chunks_per_proxy]))

        for t in scrapejobs:
            t.start()

        handler = ResultsHandler(Q, conn)
        handler.start()

        for t in scrapejobs:
            t.join()

        # All scrape jobs done, signal the db handler to stop
        Q.put(Config['all_processed_sig'])
        handler.join()

        conn.commit()
        conn.close()
    elif args.scrapemethod == 'http':
        if args.deep_scrape:
            # TODO: implement deep scrape
            raise NotImplementedError('Sorry. Currently deep_scrape is not implemented.')

        else:
            results = []
            for kw in keywords:
                r = scrape(kw, args.num_results_per_page, args.num_pages, searchtype=args.searchtype)
                results.append(r)
        if args.print:
            print_scrape_results_http(results, args.verbosity, view=args.view)
    else:
        raise ValueError('No such scrapemethod. Use "http" or "sel"')

if __name__ == '__main__':
    handle_commandline(get_command_line())
