# -*- coding: utf-8 -*-

import sys
import re
import lxml.html
from lxml.html.clean import Cleaner
import logging
from urllib.parse import urlparse
import pprint
from GoogleScraper.database import SearchEngineResultsPage, Link
from cssselect import HTMLTranslator

logger = logging.getLogger('GoogleScraper')

class InvalidSearchTypeExcpetion(Exception):
    pass


class UnknowUrlException(Exception):
    pass


class NoParserForSearchEngineException(Exception):
    pass

class Parser():
    """Parses SERP pages.

    Each search engine results page (SERP) has a similar layout:
    
    The main search results are usually in a html container element (#main, .results, #leftSide).
    There might be separate columns for other search results (like ads for example). Then each 
    result contains basically a link, a snippet and a description (usually some text on the
    target site). It's really astonishing how similar other search engines are to Google.
    
    Each child class (that can actual parse a concrete search engine results page) needs
    to specify css selectors for the different search types (Like normal search, news search, video search, ...).

    Attributes:
        search_results: The results after parsing.
    """
    
    # The supported search types. For instance, Google supports Video Search, Image Search, News search
    search_types = []


    # Each subclass of Parser may declare an arbitrary amount of attribute that
    # follow a naming convention like this:
    # *_search_selectors
    # where the asterix may be replaced with arbitrary identifier names.
    # Any of these attributes represent css selectors for a specific search type.
    # If you didn't specify the search type in the search_types list, this attribute
    # will not be evaluated and no data will be parsed.

    def __init__(self, html=None, searchtype='normal'):
        """Create new Parser instance and parse all information.

        Args:
            html: The raw html from the search engine search. If not provided, you can parse 
                    the data later by calling parse(html) directly.
            searchtype: The search type. By default "normal"
            
        Raises:
            Assertion error if the subclassed
            specific parser cannot handle the the settings.
        """
        assert searchtype in self.search_types
        
        self.html = html
        self.searchtype = searchtype
        self.dom = None
        self.search_results = {}
        self.search_results['num_results'] = ''
        
        if self.html:
            self.parse()
        
    def parse(self, html):
        """Public function to start parsing the search engine results.
        
        Args: 
            html: The raw html data to extract the SERP entries from.
        """
        self.html = html
        
        # lets do the actual parsing
        self._parse()
        
        # Apply subclass specific behaviour after parsing has happened
        self.after_parsing()

    def _parse(self):
        """Internal parse the dom according to the provided css selectors.
        
        Raises: InvalidSearchTypeExcpetion if no css selectors for the searchtype could be found.
        """
        
        # Try to parse the provided HTML string using lxml
        # strip all unnecessary information to save space
        cleaner = Cleaner()
        cleaner.scripts = True
        cleaner.javascript = True
        cleaner.style = True

        try:
            parser = lxml.html.HTMLParser(encoding='utf-8')
            self.dom = lxml.html.document_fromstring(self.html, parser=parser)
            self.dom = cleaner.clean_html(self.dom)
            self.dom.resolve_base_href()
        except Exception as e:
            # maybe wrong encoding
            logger.error(e)
        
        # try to parse the number of results.
        attr_name = self.searchtype + '_search_selectors'
        selector_dict = getattr(self, attr_name, None)

        # short alias because we use it so extensively
        css_to_xpath = HTMLTranslator().css_to_xpath

        # get the appropriate css selectors for the num_results for the keyword
        num_results_selector = getattr(self, 'num_results_search_selectors', None)
        self.search_results['num_results'] = ''

        if isinstance(num_results_selector, list) and num_results_selector:
            for selector in num_results_selector:
                try:
                    self.search_results['num_results'] = self.dom.xpath(css_to_xpath(selector))[0].text_content()
                except IndexError as e:
                    logger.warning('Cannot parse num_results from serp page with selector {}'.format(selector))
                else: # leave when first selector grabbed something
                    break

        if not selector_dict and not isinstance(selector_dict, dict):
            raise InvalidSearchTypeExcpetion('There is no such attribute: {}. No selectors found'.format(attr_name))

        for result_type, selector_class in selector_dict.items():

            self.search_results[result_type] = []

            for selector_specific, selectors in selector_class.items():

                results = self.dom.xpath(
                    css_to_xpath('{container} {result_container}'.format(**selectors))
                )

                to_extract = set(selectors.keys()) - {'container', 'result_container'}
                selectors_to_use = {key: selectors[key] for key in to_extract if key in selectors.keys()}

                for index, result in enumerate(results):
                    # Let's add primitive support for CSS3 pseudo selectors
                    # We just need two of them
                    # ::text
                    # ::attr(someattribute)

                    # You say we should use xpath expresssions instead?
                    # Maybe you're right, but they are complicated when it comes to classes,
                    # have a look here: http://doc.scrapy.org/en/latest/topics/selectors.html
                    serp_result = {}
                    for key, selector in selectors_to_use.items():
                        value = None
                        if selector.endswith('::text'):
                            try:
                                value = result.xpath(css_to_xpath(selector.split('::')[0]))[0].text_content()
                            except IndexError as e:
                                pass
                        else:
                            attr = re.search(r'::attr\((?P<attr>.*)\)$', selector).group('attr')
                            if attr:
                                try:
                                    value = result.xpath(css_to_xpath(selector.split('::')[0]))[0].get(attr)
                                except IndexError as e:
                                    pass
                            else:
                                try:
                                    value = result.xpath(css_to_xpath(selector))[0].text_content()
                                except IndexError as e:
                                    pass
                        serp_result[key] = value
                    if serp_result:
                        self.search_results[result_type].append(serp_result)
                    
    def after_parsing(self):
        """Subclass specific behaviour after parsing happened.
        
        Override in subclass to add search engine specific behaviour.
        Commonly used to clean the results.
        """
                
    def __str__(self):
        """Return a nicely formated overview of the results."""
        return pprint.pformat(self.search_results)

    @property
    def cleaned_html(self):
        assert self.dom, 'The html needs to be parsed to get the cleaned html'
        return lxml.html.tostring(self.dom)
                
"""
Here follow the different classes that provide CSS selectors 
for different types of SERP pages of several common search engines.

Just look at them and add your own selectors in a new class if you
want the Scraper to support them.

You can easily just add new selectors to a search engine. Just follow
the attribute naming convention and the parser will recognize them:

If you provide a dict with a name like finance_search_selectors,
then you're adding a new search type with the name finance.

Each class needs a attribute called num_results_search_selectors, that
extracts the number of searches that were found by the keyword.

Please note:
The actual selectors are wrapped in a dictionary to clarify with which IP
they were requested. The key to the wrapper div allows to specify distinct
criteria to whatever settings you used when you requested the page. So you
might add your own selectors for different User-Agents, distinct HTTP headers, what-
ever you may imagine. This allows the most dynamic parsing behaviour and makes
it very easy to grab all data the site has to offer.
"""


class GoogleParser(Parser):
    """Parses SERP pages of the Google search engine."""
    
    search_types = ['normal', 'image']
    
    num_results_search_selectors = ['#resultStats']
    
    normal_search_selectors = {
        'results': {
            'us_ip': {
                'container': '#center_col',
                'result_container': 'li.g ',
                'link': 'h3.r > a:first-child::attr(href)',
                'snippet': 'div.s span.st::text',
                'title': 'h3.r > a:first-child::text',
                'visible_link': 'cite::text'
            },
            'de_ip': {
                'container': '#center_col',
                'result_container': 'li.g ',
                'link': 'h3.r > a:first-child::attr(href)',
                'snippet': 'div.s span.st::text',
                'title': 'h3.r > a:first-child::text',
                'visible_link': 'cite::text'
            }
        },
        'ads_main': {
            'us_ip': {
                'container': '#center_col',
                'result_container': 'li.ads-ad',
                'link': 'h3.r > a:first-child::attr(href)',
                'snippet': 'div.s span.st::text',
                'title': 'h3.r > a:first-child::text',
                'visible_link': '.ads-visurl cite::text',
            },
            'de_ip': {
                'container': '#center_col',
                'result_container': '.ads-ad',
                'link': 'h3 > a:first-child::attr(href)',
                'snippet': '.ads-creative::text',
                'title': 'h3 > a:first-child::text',
                'visible_link': '.ads-visurl cite::text',
            }
        },
        'ads_aside': {

        }
    }
    
    image_search_selectors = {
        'de_ip': {
            'results': {
                'container': 'li#isr_mc',
                'result_container': 'div.rg_di',
                'imgurl': 'a.rg_l::attr(href)'
            }
        }
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def after_parsing(self):
        """Clean the urls.
        
        A typical scraped results looks like the following:
        
        '/url?q=http://www.youtube.com/user/Apple&sa=U&ei=lntiVN7JDsTfPZCMgKAO&ved=0CFQQFjAO&usg=AFQjCNGkX65O-hKLmyq1FX9HQqbb9iYn9A'
        
        Clean with a short regex.
        """
        super().after_parsing()
        for key, value in self.search_results.items():
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict) and item['link']:
                        result = re.search(r'/url\?q=(?P<url>.*?)&sa=U&ei=', item['link'])
                        if result:
                            self.search_results[key][i]['link'] = result.group('url')
                            

class YandexParser(Parser):
    """Parses SERP pages of the Yandex search engine."""

    search_types = ['normal']
    
    num_results_search_selectors = []
    
    normal_search_selectors = {
        'results': {
            'de_ip': {
                'container': 'div.serp-list',
                'result_container': 'div.serp-item__wrap ',
                'link': 'a.serp-item__title-link::attr(href)',
                'snippet': 'div.serp-item__text::text',
                'title': 'a.serp-item__title-link::text',
                'visible_link': 'a.serp-url__link::attr(href)'
            }
        }
    }
    
    
class BingParser(Parser):
    """Parses SERP pages of the Bing search engine."""
    
    search_types = ['normal']
    
    num_results_search_selectors = ['.sb_count']
    
    normal_search_selectors = {
        'results': {
            'us_ip': {
                'container': '#b_results',
                'result_container': '.b_algo',
                'link': 'h2 > a::attr(href)',
                'snippet': '.b_caption > .b_attribution > p::text',
                'title': 'h2::text',
                'visible_link': 'cite::text'
            },
            'de_ip': {
                'container': '#b_results',
                'result_container': '.b_algo',
                'link': 'h2 > a::attr(href)',
                'snippet': '.b_caption > p::text',
                'title': 'h2::text',
                'visible_link': 'cite::text'
            }
        },
        'ads_main': {
            'us_ip': {
                'container': '#b_results .b_ad',
                'result_container': '.sb_add',
                'link': 'h2 > a::attr(href)',
                'snippet': '.sb_addesc::text',
                'title': 'h2 > a::text',
                'visible_link': 'cite::text'
            },
            'de_ip': {
                'container': '#b_results .b_ad',
                'result_container': '.sb_add',
                'link': 'h2 > a::attr(href)',
                'snippet': '.b_caption > p::text',
                'title': 'h2 > a::text',
                'visible_link': 'cite::text'
            }
        }
    }


class YahooParser(Parser):
    """Parses SERP pages of the Yahoo search engine."""
    
    search_types = ['normal']
    
    num_results_search_selectors = ['#pg > span:last-child']
    
    normal_search_selectors = {
        'results': {
            'de_ip': {
                'container': '#main',
                'result_container': '.res',
                'link': 'div > h3 > a::attr(href)',
                'snippet': 'div.abstr::text',
                'title': 'div > h3 > a::text',
                'visible_link': 'span.url::text'
            }
        },
    }
    

class BaiduParser(Parser):
    """Parses SERP pages of the Baidu search engine."""
    
    search_types = ['normal']
    
    num_results_search_selectors = ['#container .nums']
    
    normal_search_selectors = {
        'results': {
            'de_ip': {
                'container': '#content_left',
                'result_container': '.result-op',
                'link': 'h3 > a.t::attr(href)',
                'snippet': '.c-abstract::text',
                'title': 'h3 > a.t::text',
                'visible_link': 'span.c-showurl::text'
            }
        },
    }


class DuckduckgoParser(Parser):
    """Parses SERP pages of the Duckduckgo search engine."""
    
    search_types = ['normal']
    
    num_results_search_selectors = []
    
    normal_search_selectors = {
        'results': {
            'de_ip': {
                'container': '#links',
                'result_container': '.result',
                'link': '.result__title > a::attr(href)',
                'snippet': 'result__snippet::text',
                'title': '.result__title > a::text',
                'visible_link': '.result__url__domain::text'
            }
        },
    }


def get_parser_by_url(url):
    """Get the appropriate parser by an search engine url.

    Args:
        url: The url that was used to issue the search

    Returns:
        The correct parser that can parse results for this url.

    Raises:
        UnknowUrlException if no parser could be found for the url.
    """
    parser = None

    if re.search(r'^http[s]?://www\.google', url):
        parser = GoogleParser
    elif re.search(r'^http://yandex\.ru', url):
        parser = YandexParser
    elif re.search(r'^http://www\.bing\.', url):
        parser = BingParser
    elif re.search(r'^http[s]?://search\.yahoo.', url):
        parser = YahooParser
    elif re.search(r'^http://www\.baidu\.com', url):
        parser = BaiduParser
    elif re.search(r'^https://duckduckgo\.com', url):
        parser = DuckduckgoParser

    if not parser:
        raise UnknowUrlException('No parser for {}.'.format(url))

    return parser


def get_parser_by_search_engine(search_engine):
    """Get the appropriate parser for the search_engine

    Args:
        search_engine: The name of a search_engine.

    Returns:
        A parser for the search_engine

    Raises:
        NoParserForSearchEngineException if no parser could be found for the name.
    """
    if search_engine == 'google':
        return GoogleParser
    elif search_engine == 'yandex':
        return YandexParser
    elif search_engine == 'bing':
        return BingParser
    elif search_engine == 'yahoo':
        return YahooParser
    elif search_engine == 'baidu':
        return BaiduParser
    elif search_engine == 'duckduckgo':
        return DuckduckgoParser
    else:
        raise NoParserForSearchEngineException('No such parser for {}'.format(search_engine))


def parse_serp(html=None, search_engine=None,
                    scrapemethod=None, current_page=None, requested_at=None,
                    requested_by='127.0.0.1', current_keyword=None, parser=None, serp=None):
        """Store the parsed data in the sqlalchemy session.

        Args:
            TODO: A whole lot

        Returns:
            The parsed SERP object.
        """

        if not parser:
            parser = get_parser_by_search_engine(search_engine)
            parser = parser()
            parser.parse(html)

        num_results = 0

        if not serp:
            serp = SearchEngineResultsPage(
                search_engine_name=search_engine,
                scrapemethod=scrapemethod,
                page_number=current_page,
                requested_at=requested_at,
                requested_by=requested_by,
                query=current_keyword,
                num_results_for_keyword=parser.search_results['num_results'],
            )

        for key, value in parser.search_results.items():
            if isinstance(value, list):
                rank = 1
                for link in value:
                    parsed = urlparse(link['link'])
                    l = Link(
                        link=link['link'],
                        snippet=link['snippet'],
                        title=link['title'],
                        visible_link=link['visible_link'],
                        domain=parsed.netloc,
                        rank=rank,
                        serp=serp
                    )
                    num_results += 1
                    rank += 1

        serp.num_results = num_results

        return serp

if __name__ == '__main__':
    """Originally part of https://github.com/NikolaiT/GoogleScraper.
    
    Only for testing purposes: May be called directly with an search engine 
    search url. For example:
    
    python3 parsing.py 'http://yandex.ru/yandsearch?text=GoogleScraper&lr=178&csg=82%2C4317%2C20%2C20%2C0%2C0%2C0'
    
    Please note: Using this module directly makes little sense, because requesting such urls
    directly without imitating a real browser (which is done in my GoogleScraper module) makes
    the search engines return crippled html, which makes it impossible to parse.
    But for some engines it nevertheless works (for example: yandex, google, ...).
    """
    import requests
    assert len(sys.argv) == 2, 'Usage: {} url'.format(sys.argv[0])
    url = sys.argv[1]
    raw_html = requests.get(url).text
    parser = get_parser_by_url(url)
    parser = parser(raw_html)
    parser.parse()
    print(parser)
    
    with open('/tmp/testhtml.html', 'w') as of:
        of.write(raw_html)
    
