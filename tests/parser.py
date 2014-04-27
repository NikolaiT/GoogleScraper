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
import lxml.html
import urllib.parse
from random import choice

try:
    import requests
    from cssselect import HTMLTranslator, SelectorError
    from bs4 import UnicodeDammit
except ImportError as ie:
    if hasattr(ie, 'name') and ie.name == 'bs4' or hasattr(ie, 'args') and 'bs4' in str(ie):
        print('Install bs4 with the command "sudo pip3 install beautifulsoup4"')
        sys.exit(1)
    print(ie)
    print('You can install missing modules with `pip3 install [modulename]`')
    sys.exit(1)

def setup_logger(level=logging.INFO):
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

setup_logger(logging.INFO)


class Google_SERP_Parser():
    """Parses data from Google SERPs."""

    # Named tuple type for the search results
    Result = namedtuple('LinkResult', 'link_title link_snippet link_url')

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
                'results': [], # Video search results
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

    @property
    def results(self):
        return self.SEARCH_RESULTS

    @property
    def links(self):
        return {k:v for k, v in self.SEARCH_RESULTS.items() if k not in
                                ('num_results_for_kw')}

    def _clean_results(self):
        """Cleans/extracts the found href attributes."""

        # Now try to create ParseResult objects from the URL
        for key in ('results', 'ads_aside', 'ads_main'):
            for i, e in enumerate(self.SEARCH_RESULTS[key]):
                try:
                    url = re.search(r'/url\?q=(?P<url>.*?)&sa=U&ei=', e.link_url).group(1)
                    assert self._REGEX_VALID_URL.match(url).group()
                    self.SEARCH_RESULTS[key][i] = \
                        self.Result(link_title=e.link_title, link_url=urllib.parse.urlparse(url),
                                    link_snippet=e.link_snippet)
                except Exception as err:
                    # In the case the above regex can't extract the url from the referrer, just use the original parse url
                    self.SEARCH_RESULTS[key][i] = \
                        self.Result(link_title=e.link_title, link_url=urllib.parse.urlparse(e.link_url),
                                    link_snippet=e.link_snippet)
                    logger.debug("URL={} found to be invalid.".format(e))

    def _parse_num_results(self):
        # try to get the number of results for our search query
        try:
            self.SEARCH_RESULTS['num_results_for_kw'] = \
                self.dom.xpath(self._xp('div#resultStats'))[0].text_content()
        except Exception as e:
            logger.critical(e.msg)

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
            'results': (['li.g', 'h3.r > a:first-child', 'div.s > span.st'], ),
            # to parse the centered ads
            'ads_main': (['div#center_col li.ads-ad', 'h3.r > a', 'div.ads-creative'],
                         ['div#tads li', 'h3 > a:first-child', 'span:last-child']),
            # the ads on on the right
            'ads_aside': (['#rhs_block li.ads-ad', 'h3.r > a', 'div.ads-creative'], ),
        }
        self._parse(dom, css_selectors)

    def _parse(self,dom, css_selectors):
        """Generic parse method"""
        for key, slist in css_selectors.items():
            for selectors in slist:
                self.SEARCH_RESULTS[key].extend(self._parse_links(dom, *selectors))
        self._parse_num_results()

    def _parse_links(self, dom, container_selector, link_selector, snippet_selector):
        links = []
        # Try to extract all links of non-ad results, including their snippets(descriptions) and titles.
        try:
            li_g_results = dom.xpath(self._xp(container_selector))
            for e in li_g_results:
                try:
                    link_element = e.xpath(self._xp(link_selector))
                    link = link_element[0].get('href')
                    title = link_element[0].text_content()
                except IndexError as err:
                    logger.debug(
                        'Error while parsing link/title element with selector={}: {}'.format(link_selector, err))
                    continue
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
                    continue

                links.append(self.Result(link_title=title, link_url=link, link_snippet=snippet))
        # Catch further errors besides parsing errors that take shape as IndexErrors
        except Exception as err:
            logger.error('Error in parsing result links with selector={}: {}'.format(container_selector, err))
            logger.info(li_g_results)

        return links or []