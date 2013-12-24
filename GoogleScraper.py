#!/usr/bin/python3
# -*- coding: utf-8 -*-

# This is a little module that uses Google to automate
# search queries. It gives access to all data of a search page:
# - The links of the result page
# - The title of the links
# - The caption/description below each link
# - The number of results for this keyword.

# GoogleScraper's architecture outlined:
# Proxy support (Socks5, Socks4, HTTP Proxy).
# Threading support.

# The module implements some countermeasures to circumvent spamming detection
# from the Google Servers:
# {List them here}

# Note: Scrapign compromises the google terms of service (TOS).

__VERSION__ = '0.2'
__UPDATED__ = '24.12.2013' # day.month.year
__AUTHOR__ = 'Nikolai'
__WEBSITE__ = 'incolumitas.com'

import sys
import os
import argparse
import hashlib
import re
import lxml.html
import urllib.parse
from random import choice
try:
    import requests
    import cssselect
    from bs4 import UnicodeDammit
except ImportError as e:
    print(e.msg)
    print('You can install missing modules with `pip install modulename`')
    sys.exit(1)

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

def cache_req(search_params, html):
    '''
    logs/caches a search response to logs/fname.cache
    in order to intensify testing and avoid requesting
    the same resources again and again (such that google would
    requests us as what we are: Sneaky seo crawlers!)
    '''
    sha = hashlib.sha256()
    sha.update(b''.join(str(s).encode() for s in search_params.values()))
    fname = '{}.{}'.format(sha.hexdigest(), 'cache')
    if os.path.exists('scrapecache/') and os.access('scrapecache/', os.R_OK | os.W_OK | os.F_OK):
        try:
            if fname in os.listdir('scrapecache/'):
                with open(fname, 'r') as fd:
                    return fd.read()
            else:
                with open(fname, 'w') as fd:
                    fd.write(html)
        except FileNotFoundError as err:
            raise Exception('Unexpected file not found.')
    else: # First call ever to cache_req
        os.mkdir('scrapecache/', 0o644)


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
        cache_req(self._GOOGLE_SEARCH_PARAMS, html)

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
            print(ee.msg)
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


# For unit tests and direct use of the module
if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='GoogleScraper', description='Scrape the Google search engine',
                                        epilog='This program might infringe Google TOS, so use at your own risk')
    parser.add_argument('-q', '--query', metavar='search_string', type=str, action='store', dest='query', required=True,
                       help='The search query.')
    parser.add_argument('-n', '--num_search_results', metavar='number_of_search_results', type=int, dest='num_search_results', action='store', default=100,
                       help='The number of results per page. Most be one of [10, 25, 50, 100]')
    parser.add_argument('-p', '--num_pages', metavar='num_of_pages', type=int, dest='num_pages', action='store', default=1,
                       help='The number of pages to search in. Each page is requested by a unique connection and if possible by a unique IP.')
    args = parser.parse_args()

    scrape(args.query, args.num_search_results, args.num_pages)