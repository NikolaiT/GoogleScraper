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
- Small time interval between parallel requests

Note: Scraping compromises the google terms of service (TOS).

Debug:
Get a jQuery selector in a console: (function() {var e = document.createElement('script'); e.src = '//ajax.googleapis.com/ajax/libs/jquery/1.11.0/jquery.min.js'; document.getElementsByTagName('head')[0].appendChild(e); jQuery.noConflict(); })();
"""

__VERSION__ = '0.5'
__UPDATED__ = '10.03.2014'  # day.month.year
__AUTHOR__ = 'Nikolai Tschacher'
__WEBSITE__ = 'incolumitas.com'

import sys
import os
import socket
import types
import logging
import pprint
import argparse
import threading
from collections import namedtuple
import hashlib
import re
import time
import signal
import lxml.html
import urllib.parse
import sqlite3
import itertools
import random

try:
    import requests
    from cssselect import HTMLTranslator, SelectorError
    from bs4 import UnicodeDammit
    import socks  # should be in the same directory
except ImportError as ie:
    if hasattr(ie, 'name') and ie.name == 'bs4' or hasattr(ie, 'args') and 'bs4' in str(ie):
        print('Install bs4 with the command "sudo pip3 install beautifulsoup4"')
        sys.exit(1)
    print(ie)
    print('You can install missing modules with `pip3 install [modulename]`')
    sys.exit(1)
try:
    from selenium import webdriver
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait  # available since 2.4.0
    from selenium.webdriver.support import expected_conditions as EC  # available since 2.26.0
    from cssselect import HTMLTranslator, SelectorError
    from bs4 import UnicodeDammit
    import lxml.html
except ImportError as ie:
    print('Scrapemethod {} needs the following library to be installed {}'.format(args.scrapemethod, ie))

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

# The database name
DB = 'results.db'
# Whether caching shall be enabled
DO_CACHING = True
# The directory path for cached google results
CACHEDIR = '.scrapecache/'
# The maximal amount of selenium browser windows running in parallel
MAX_SEL_BROWSERS = 5

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
        return '{} is not a valid number of results per page'.format(self.nres)


def maybe_clean_cache():
    """Delete all .cache files in the cache directory that are older than 12 hours."""
    for fname in os.listdir(CACHEDIR):
        if time.time() > os.path.getmtime(os.path.join(CACHEDIR, fname)) + (60 * 60 * 12):
            os.remove(os.path.join(CACHEDIR, fname))


if DO_CACHING:
    # Clean the CACHEDIR once in a while
    maybe_clean_cache()


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

        if num_results_per_page not in range(0,
                                             1001):  # The maximum value of this parameter is 1000. See search appliance docs
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
            'gl': None,  # as if the search was conducted in a specified location. Can be unreliable.
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

    def reset_search_params(self):
        # Reset all search params to None
        # such that they won't be used in the query
        for k, v in self._SEARCH_PARAMS.items():
            self._SEARCH_PARAMS[k] = None

    def _build_query(self, searchtype='normal', random=False):
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

        if random:
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

        if DO_CACHING:
            html = get_cached(self._SEARCH_PARAMS)
            self.SEARCH_RESULTS['cache_file'] = os.path.join(CACHEDIR, cached_file_name(self._SEARCH_PARAMS))
        else:
            html = False

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
            if DO_CACHING:
                cache_results(self._SEARCH_PARAMS, html)
                self.SEARCH_RESULTS['cache_file'] = os.path.join(CACHEDIR, cached_file_name(self._SEARCH_PARAMS))

        self.parser = Google_SERP_Parser(html, searchtype=self.searchtype)
        self.SEARCH_RESULTS.update(self.parser.all_results)

    @property
    def results(self):
        return self.SEARCH_RESULTS


class SelScraper(threading.Thread):
    """Instances of this class make use of selenium browser objects to query Google"""
    # the google search url
    url = 'https://www.google.com'

    def __init__(self, keywords, rlock, cursor):
        super().__init__()
        self.cursor = cursor
        self.rlock = rlock
        self.html = ''
        self.keywords = keywords
        self.searchparams = dict(zip(self.keywords, [0]*len(self.keywords)))
        self.ip = '127.0.0.1'

    def use_proxy(self, proxycfg={}):
        if not set(proxycfg.keys()).issubset({'ip', 'port', 'password', 'proxytype', 'user'}):
            raise Exception('Invalid proxyconfig: {}'.format(proxycfg))
        # add pairs to class as attributes
        {setattr(self, key, value) for key, value in proxycfg.items()}
        # try to set the proxy for selenium instance

    def run(self):
        self.html = get_cached(self.searchparams)
        if not self.html:
            self.webdriver = webdriver.Firefox()
            self.webdriver.get(self.url)
            for self.kw in self.keywords:
                if not self.kw:
                    break
                time.sleep(random.randint(10, 50) // 10)
                try:
                    self.element = WebDriverWait(self.webdriver, 10).until(EC.presence_of_element_located((By.NAME, "q")))
                except Exception as e:
                    raise Exception(e) # fix that later
                self.element.clear()
                self.element.send_keys(self.kw + Keys.ENTER)
                WebDriverWait(self.webdriver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'li.g')))
                self.html = self.webdriver.page_source
                # Lock for the sake that two threads write to same file (not probable)
                self.rlock.acquire()
                cache_results(self.searchparams, self.html)
                self.rlock.release()
                self._parse_links()  # call here one of _parse_links_native or _parse_links_sel
            self.webdriver.close()
        else:
            for self.kw in self.keywords:
                if not self.kw:
                    break
                self._parse_links()

    def _parse_links(self):
        """Parses links with Google_SERP_Parser"""
        self.parser = Google_SERP_Parser(self.html)
        self.results = self.parser.links
        self.rlock.acquire()
        self.cursor.execute(
            'INSERT INTO serp_page (requested_at, num_results, search_query, requested_by) VALUES(?, ?, ?, ?)',
            (time.asctime(), len(self.results), self.kw, self.ip))
        lastrowid = self.cursor.lastrowid
        pprint.pprint(self.results)
        self.cursor.executemany('INSERT INTO results (link_title, link_url, link_snippet, link_rank, serp_id) VALUES(?, ?, ?, ?, ?)',
                            [(result.link_title, result.link_url.geturl(), result.link_snippet, result.link_position) + (lastrowid, ) for result in self.results])
        self.rlock.release()

    def _parse_links_sel(self):
        """Scrapes the google SERP page with selenium methods.

         (is slow, because css selectors are probably fired by javascript)
        """
        self.rlock.acquire()

        results = self.webdriver.find_elements_by_css_selector('li.g')

        self.cursor.execute('INSERT INTO serp_page (requested_at, num_results, search_query) VALUES(?, ?, ?)',
                            (time.ctime(), len(results), self.kw))
        lastrowid = self.cursor.lastrowid
        parsed = []
        for result in results:
            link = title = snippet = ''
            try:
                link_element = result.find_element_by_css_selector('h3.r > a:first-child')
                link = link_element.get_attribute('href')
                title = link_element.text
            except Exception as e:
                pass
            try:
                snippet = result.find_element_by_css_selector('div.s > span.st').text
            except Exception as e:
                pass
            parsed.append((link, title, snippet))

        self.cursor.executemany(
            'INSERT INTO results (link_title, link_title, link_snippet, serp_id) VALUES(?, ?, ?, ?)',
            [tuple + (lastrowid, ) for tuple in parsed])
        self.rlock.release()


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
            print('Some error occurred while lxml tried to parse: {}'.format(e.msg))

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
        for link_title, link_snippet, link_url in result['results']:
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
            'results': (['li.g', 'h3.r > a:first-child', 'div.s > span.st'], ),
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
            'results': (['li.g', 'h3.r > a:first-child', 'div.s > span.st'],
                        ['li.g', 'h3.r > a:first-child', 'div.s span.st']),
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
        try:
            li_g_results = dom.xpath(self._xp(container_selector))
            for i, e in enumerate(li_g_results):
                snippet = link = title = ''
                try:
                    link_element = e.xpath(self._xp(link_selector))
                    link = link_element[0].get('href')
                    title = link_element[0].text_content()
                except IndexError as err:
                    logger.debug(
                        'Error while parsing link/title element with selector={}: {}'.format(link_selector, err))
                try:
                    snippet_element = e.xpath(self._xp(snippet_selector))
                    snippet = snippet_element[0].text_content()
                except IndexError as err:
                    try:
                        previous_element = links[-1]
                    except IndexError as ie:
                        previous_element = None
                    logger.debug('Error in parsing snippet with selector={}. Previous element: {}.Error: {}'.format(
                        snippet_selector, previous_element, repr(e), err))

                links.append(self.Result(link_title=title, link_url=link, link_snippet=snippet, link_position=i))
        # Catch further errors besides parsing errors that take shape as IndexErrors
        except Exception as err:
            logger.error('Error in parsing result links with selector={}: {}'.format(container_selector, err))

        return links or []


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
    """
    if os.path.exists(DB) and os.path.getsize(DB) > 0:
        conn = sqlite3.connect(DB, check_same_thread=False)
        cursor = conn.cursor()
        return (conn, cursor)
    else:
        # set that bitch up the first time
        conn = sqlite3.connect(DB, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE serp_page
        (id INTEGER PRIMARY KEY AUTOINCREMENT, requested_at TEXT NOT NULL,
           num_results INTEGER NOT NULL, search_query TEXT NOT NULL, requested_by TEXT)''')
        cursor.execute('''CREATE TABLE results
        (id INTEGER PRIMARY KEY AUTOINCREMENT, link_title TEXT,
           link_snippet TEXT, link_url TEXT, link_domain TEXT, link_rank INTEGER NOT NULL,
           serp_id INTEGER NOT NULL, FOREIGN KEY(serp_id) REFERENCES serp_page(id))''')

        conn.commit()
        return (conn, cursor)


def get_command_line():
    """Parses command line arguments for scraping with selenium browser instances"""
    parser = argparse.ArgumentParser(prog='GoogleScraper',
                                     description='Scrapes the Google search engine by forging http requests that imitate '
                                                 'browser searches or by using real browsers (with selenium)',
                                     epilog='This program might infringe Google TOS, so use it on your own risk. (c) by Nikolai Tschacher, 2012-2014')

    parser.add_argument('scrapemethod', type=str,
                        help='The scraping type. There are currently two types: "http" and "sel".',
                        choices=('http', 'sel'), default='http')
    parser.add_argument('-q', '--keywords', metavar='keywords', type=str, action='store', dest='keywords', help='The search keywords to scrape for.')
    parser.add_argument('--keywords-file', type=str, action='store', dest='kwfile',
                        help='Keywords to search for. One keyword per line. Empty lines are ignored.')
    parser.add_argument('-n', '--num_results_per_page', metavar='number_of_results_per_page', type=int,
                        dest='num_results_per_page', action='store', default=50,
                        help='The number of results per page. Most be >= 100')
    parser.add_argument('-p', '--num_pages', metavar='num_of_pages', type=int, dest='num_pages', action='store',
                        default=1,
                        help='The number of pages to search in. Each page is requested by a unique connection and if possible by a unique IP.')
    parser.add_argument('-s', '--storing-type', metavar='results_storing', type=str, dest='storing_type',
                        action='store',
                        default='stdout', choices=('database', 'stdout'), help='Where/how to put/show the results.')
    parser.add_argument('-t', '--search_type', metavar='search_type', type=str, dest='searchtype', action='store',
                        default='normal',
                        help='The searchtype to launch. May be normal web search, image search, news search or video search.')
    parser.add_argument('--proxy', metavar='proxycredentials', type=str, dest='proxy', action='store',
                        required=False,  #default=('127.0.0.1', 9050)
                        help='A string such as "127.0.0.1:9050" specifying a single proxy server')
    parser.add_argument('--proxy_file', metavar='proxyfile', type=str, dest='proxy_file', action='store',
                        required=False,  #default='.proxies'
                        help='A filename for a list of proxies (supported are HTTP PROXIES, SOCKS4/4a/5) with the following format: "Proxyprotocol (proxy_ip|proxy_host):Port\\n"')
    parser.add_argument('-x', '--deep-scrape', action='store_true', default=False,
                        help='Launches a wide range of parallel searches by modifying the search ' \
                             'query string with synonyms and by scraping with different Google search parameter combinations that might yield more unique ' \
                             'results. The algorithm is optimized for maximum of results for a specific keyword whilst trying avoid detection. This is the heart of GoogleScraper.')
    parser.add_argument('--view', action='store_true', default=False, help="View the response in a default browser tab."
                                                                           " Mainly for debug purposes. Works only when caching is enabled.")
    parser.add_argument('-v', '--verbosity', type=int, default=1,
                        help="The verbosity of the output reporting for the found search results.")
    parser.add_argument('--debug', action='store_true', default=False, help='Whether to set logging to level DEBUG.')
    return parser.parse_args()


def handle_commandline(args):
    """Handles the command line arguments as given by get_command_line()"""

    if args.debug:
        setup_logger(logging.DEBUG)
    else:
        setup_logger(logging.INFO)

    if args.keywords and args.kwfile:
        raise ValueError(
            'Invalid command line usage. Either set keywords as a string or provide a keyword file, but not both you dirty whore')

    # Split keywords by whitespaces
    if args.keywords:
        args.keywords = re.split('\s', args.keywords)
        del args.kwfile
    elif args.kwfile:
        if not os.path.exists(args.kwfile):
            raise ValueError('The keyword file {} does not exist.'.format(args.kwfile))
        else:
            args.keywords = [line.replace('\n', '') for line in open(args.kwfile, 'r').readlines()]

    if int(args.num_results_per_page) > 100:
        raise ValueError('Not more that 100 results per page.')

    if int(args.num_pages) > 20:
        raise ValueError('Not more that 20 pages.')

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
                              rdns=True)  # rdns is by default on true. Never use rnds=False with TOR, otherwise you are screwed!
        socks.wrap_module(socket)
        socket.create_connection = create_connection

    valid_search_types = ('normal', 'video', 'news', 'image')
    if args.searchtype not in valid_search_types:
        ValueError('Invalid search type! Select one of {}'.format(repr(valid_search_types)))

    # Let the games begin
    if args.scrapemethod == 'sel':
        conn, cursor = maybe_create_db()

        rlock = threading.RLock()
        kwgroups = grouper(args.keywords, len(args.keywords)//MAX_SEL_BROWSERS, fillvalue=None)
        browsers = [SelScraper(kws, rlock, cursor) for kws in kwgroups]

        def signal_handler(signal, frame):
            print('Ctrl-c was pressed, shall I commit all changes to db?')
            if input('Yes (y) or No (n) ?\n>>> ').lower().strip() == 'y':
                conn.commit()
            conn.close()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        for t in browsers:
            t.start()

        for t in browsers:
            t.join()

        conn.commit()
        conn.close()
    else:

        if args.deep_scrape:
            results = deep_scrape(args.query)
        else:
            results = scrape(args.keywords[0], args.num_results_per_page, args.num_pages, searchtype=args.searchtype)

        for result in results:
            logger.info('{} links found! The search with the keyword "{}" yielded the result:{}'.format(
                len(result['results']), result['search_keyword'], result['num_results_for_kw']))
            if args.view:
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
                        if args.verbosity > 1:
                            print(
                                '  Title: \n{}'.format(textwrap.indent('\n'.join(textwrap.wrap(link_title, 50)), '\t')))
                            print(
                                '  Description: \n{}\n'.format(
                                    textwrap.indent('\n'.join(textwrap.wrap(link_snippet, 70)), '\t')))
                            print('*' * 70)
                            print()

if __name__ == '__main__':
    handle_commandline(get_command_line())
