#!/usr/bin/python3
# -*- coding: utf-8 -*-

# This is a little module to use the google search engine
# It compromises the google terms of service. Please note
# that.

# Of course, when searching for suspicious terms (including
# dorks or patterns of vulnerable applicatios) google rec-
# ognizes you pretty fast and blocks your IP address and 
# maybe even your broswer signature (UA the most notorious
# needle here). I could implement proxy (socks 4/5, http/s)
# support, but it seems that urllib3 doesn't support proxies
# yet. Then I could fall back to use urllib.request instead
# of requests, but it seems that the module which provides
# the possibility to socksify your requests (SocksiPy) looks
# pretty much outdated. Therefore I decided not to implement
# any complex partly functional solution. Does this mean we 
# are limited until Google blocks our IP address?

# Absolutely not. There is a wonderful tool called proxychains
# which hooks all the low level socket stuff and reroutes all
# traffic through the proxy (Yes, including DNS queries).

# I will work on a not too slow solution to combine proxychains
# with this module. Seems like it's not a trivial task, since 
# proxychains only supports configuration files and I need a dynamic
# configuration, because I want to call proxychains once for google
# search request with exactly one proxy (no chaining). Proxychains isn't
# directly made for it, maybe I have to hack some additional functionality
# into proxychains...

__VERSION__ = '0.2'
__UPDATED__ = '06.12.2013' # day.month.year
__AUTHOR__ = 'Nikolai'
__WEBSITE__ = 'incolumitas.com'

import sys
import gzip
import re
import lxml.html
import urllib.parse
from random import choice
try:
    from bs4 import UnicodeDammit
except ImportError as e:
    print(e.msg)
    print('You can install beuatifulsoup with "pip install beautifulsoup4" or "easy_install beautifulsoup4".')

try:
    import requests
except ImportError as ierr:
    print('[-] Required module not found: {}'.format(ierr))
    print('[-] You have to install the module with '
          'a command like this %s , whereby X.X '
          'stands for the python version.'
            % '/usr/bin/pip-X.X install requests')
    sys.exit(2)

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
        'q': '',        # the search term
        'num': '',      # the number of results per page
        'start': '0',   # the offset to the search results. page number = (start / num) + 1
        'pws': '0'      # personalization turned off
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
'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.97 Safari/537.11',
'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:17.0) Gecko/20100101 Firefox/17.0',
'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_2) AppleWebKit/536.26.17 (KHTML, like Gecko) Version/6.0.2 Safari/536.26.17',
'Mozilla/5.0 (Linux; U; Android 2.2; fr-fr; Desire_A8181 Build/FRF91) App3leWebKit/53.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1',
'Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; FunWebProducts; .NET CLR 1.1.4322; PeoplePal 6.2)',
'Mozilla/5.0 (Windows NT 5.1; rv:13.0) Gecko/20100101 Firefox/13.0.1',
'Opera/9.80 (Windows NT 5.1; U; en) Presto/2.10.289 Version/12.01',
'Mozilla/5.0 (Windows NT 5.1; rv:5.0.1) Gecko/20100101 Firefox/5.0.1',
'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.0; Trident/4.0; Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1) ; .NET CLR 3.5.30729)'
    ]

    def __init__(self, search_term, number_results_page=50, offset=0):
        self.search_term = search_term
        if number_results_page not in [10, 25, 50, 100]:
            raise InvalidNumberResultsException(number_results_page)
            
        self.number_results_page = number_results_page
        self.offset = offset
        
    # Front end
    # This function returns a list of 5-tuples: 
    # (addressing scheme, network location, path, query, fragment identifier).
    def search(self, number_pages=1):
        res = []
        for i in range(number_pages):
            self.offset = int(self.number_results_page * 100 * i)
            href_list = self._search()

            urls = self._clean_results(href_list)
            
            # Now try to create ParseResult objects from the URL
            for u in urls:
                try:
                    res.append(urllib.parse.urlparse(u))
                except:
                    pass
        return res
                
    # private internal functions who implement the actual stuff 
    
    # When random == True, several headers (like the UA) are chosen
    # randomly.
    def _build_query(self, random=False):
        self._GOOGLE_SEARCH_PARAMS['q'] = self.search_term
        self._GOOGLE_SEARCH_PARAMS['num'] = self.number_results_page
        self._GOOGLE_SEARCH_PARAMS['start'] = str(self.offset)
        
        if random:
            self._HEADERS['User-Agent'] = choice(_UAS)
        
    # Search via google and parse with lxml
    # private function
    def _search(self):
        self._build_query()

        try:
            r = requests.get(self._GOOGLE_SEARCH, headers=self._HEADERS,
                            params=self._GOOGLE_SEARCH_PARAMS, timeout=3.0)
        except requests.ConnectionError as cerr:
            print('Network problem occured')
            sys.exit(1)
        except requests.Timeout as terr:
            print('Connection timeout')
            sys.exit(1)
        
        if not r.ok:
            print('HTTP Error:', r.status_code)
            if str(r.status_code)[0] == '5':
                print('Maybe google recognizes you as sneaky spammer after'
                      ' you requested their services too inexhaustibly :D')
            sys.exit(1)
       
        html = r.text

        try:
            doc = UnicodeDammit(html, is_html=True)
            parser = lxml.html.HTMLParser(encoding=doc.declared_html_encoding)
            dom = lxml.html.document_fromstring(html, parser=parser)
            dom.resolve_base_href()

        except Exception as e:
            print('Some error occured while lxml tried to parse: {}'.format(e.msg))
            sys.exit(1)
            
        try:
            links = dom.cssselect('a')
            return [e.get('href') for e in links]
        except Exception as ee:
            # Most likely cssselect() is not installed!
            # Try iterlinks() [Its probably better anyways]
            return [link for element, attribute, link, position in dom.iterlinks() if attribute == 'href']


    # Clean all href attributes within a a element and returns
    # the bare search results. This is actually not trivial.
    # Returns urls, not domains. So duplicate domains are common.
    # Cleaning is made rather harsh and reckless.
    def _clean_results(self, list_href):

        # List of list (when more than one URL
        # in href) and (mostly strings).
        urls = []
        
        # Match all valid URLS within a href attribute.
        # We match with a greedy/frindly regex, otherwise
        # too much valid URL's would be stripped.
        for href in list_href:
            try:
                urls.append(self._REGEX_VALID_URL_SIMPLE.search(href).group(0))
            except:
                pass
        
        BADBOYS = ['gstatic', 'wikipedia', 'gmail', 'google', '/search?', 'youtube']
        cleaned = []
        
        # Remove badboys
        for i, e in enumerate(urls):
            if isinstance(e, list):
                for u in e:
                    hit = ['found' for b in BADBOYS if b in u]
                    if not hit:
                        cleaned.append(u)
            elif isinstance(e, str):
                hit = ['found' for b in BADBOYS if b in e]
                if not hit:
                    cleaned.append(e)
                                  
        # Remove duplicates
        cleaned = list(set(cleaned))
        
        # dirty trick for bugfix to remove google noise [Need to read there something]
        return [link.split('&sa=U&ei=')[0] for link in cleaned]

def scrape(query, results_per_page=100, number_pages=1, offset=0):
    '''Search for terms and return a list of all URLs.'''
    scraper = GoogleScraper(query, number_results_page=results_per_page)
    results = scraper.search(number_pages=number_pages)
    return [url for url in results]
