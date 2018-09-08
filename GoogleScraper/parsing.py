# -*- coding: utf-8 -*-

import sys
import os
import re
import lxml.html
from lxml.html.clean import Cleaner
from urllib.parse import unquote
import pprint
from GoogleScraper.database import SearchEngineResultsPage
import logging
from cssselect import HTMLTranslator

logger = logging.getLogger(__name__)


class InvalidSearchTypeException(Exception):
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

    # this selector specified the element that notifies the user whether the search
    # had any results.
    no_results_selector = []

    # if subclasses specify an value for this attribute and the attribute
    # targets an element in the serp page, then there weren't any results
    # for the original query.
    effective_query_selector = []

    # the selector that gets the number of results (guessed) as shown by the search engine.
    num_results_search_selectors = []

    # some search engine show on which page we currently are. If supportd, this selector will get this value.
    page_number_selectors = []

    # The supported search types. For instance, Google supports Video Search, Image Search, News search
    search_types = []

    # Each subclass of Parser may declare an arbitrary amount of attributes that
    # follow a naming convention like this:
    # *_search_selectors
    # where the asterix may be replaced with arbitrary identifier names.
    # Any of these attributes represent css selectors for a specific search type.
    # If you didn't specify the search type in the search_types list, this attribute
    # will not be evaluated and no data will be parsed.

    def __init__(self, config={}, html='', query=''):
        """Create new Parser instance and parse all information.

        Args:
            html: The raw html from the search engine search. If not provided, you can parse 
                    the data later by calling parse(html) directly.
            searchtype: The search type. By default "normal"
            
        Raises:
            Assertion error if the subclassed
            specific parser cannot handle the the settings.
        """
        self.config = config
        self.searchtype = self.config.get('search_type', 'normal')
        assert self.searchtype in self.search_types, 'search type "{}" is not supported in {}'.format(
            self.searchtype,
            self.__class__.__name__
        )

        self.query = query
        self.html = html
        self.dom = None
        self.search_results = {}
        self.num_results_for_query = ''
        self.num_results = 0
        self.effective_query = ''
        self.page_number = -1
        self.no_results = False

        # to be set by the implementing sub classes
        self.search_engine = ''

        # short alias because we use it so extensively
        self.css_to_xpath = HTMLTranslator().css_to_xpath

        if self.html:
            self.parse()

    def parse(self, html=None):
        """Public function to start parsing the search engine results.
        
        Args: 
            html: The raw html data to extract the SERP entries from.
        """
        if html:
            self.html = html

        # lets do the actual parsing
        self._parse()

        # Apply subclass specific behaviour after parsing has happened
        # This is needed because different parsers need to clean/modify
        # the parsed data uniquely.
        self.after_parsing()

    def _parse_lxml(self, cleaner=None):
        try:
            parser = lxml.html.HTMLParser(encoding='utf-8')
            if cleaner:
                self.dom = cleaner.clean_html(self.dom)
            self.dom = lxml.html.document_fromstring(self.html, parser=parser)
            self.dom.resolve_base_href()
        except Exception as e:
            # maybe wrong encoding
            logger.error(e)

    def _parse(self, cleaner=None):
        """Internal parse the dom according to the provided css selectors.
        
        Raises: InvalidSearchTypeException if no css selectors for the searchtype could be found.
        """
        self.num_results = 0
        self._parse_lxml(cleaner)

        # try to parse the number of results.
        attr_name = self.searchtype + '_search_selectors'
        selector_dict = getattr(self, attr_name, None)

        # get the appropriate css selectors for the num_results for the keyword
        num_results_selector = getattr(self, 'num_results_search_selectors', None)

        self.num_results_for_query = self.first_match(num_results_selector, self.dom)
        if not self.num_results_for_query:
            logger.debug('{}: Cannot parse num_results from serp page with selectors {}'.format(self.__class__.__name__,
                                                                                       num_results_selector))

        # get the current page we are at. Sometimes we search engines don't show this.
        try:
            self.page_number = int(self.first_match(self.page_number_selectors, self.dom))
        except ValueError:
            self.page_number = -1

        # let's see if the search query was shitty (no results for that query)
        self.effective_query = self.first_match(self.effective_query_selector, self.dom)
        if self.effective_query:
            logger.debug('{}: There was no search hit for the search query. Search engine used {} instead.'.format(
                self.__class__.__name__, self.effective_query))
        else:
            self.effective_query = ''

        # the element that notifies the user about no results.
        self.no_results_text = self.first_match(self.no_results_selector, self.dom)

        # get the stuff that is of interest in SERP pages.
        if not selector_dict and not isinstance(selector_dict, dict):
            raise InvalidSearchTypeException('There is no such attribute: {}. No selectors found'.format(attr_name))

        for result_type, selector_class in selector_dict.items():

            self.search_results[result_type] = []

            for selector_specific, selectors in selector_class.items():

                if 'result_container' in selectors and selectors['result_container']:
                    css = '{container} {result_container}'.format(**selectors)
                else:
                    css = selectors['container']

                results = self.dom.xpath(
                    self.css_to_xpath(css)
                )

                to_extract = set(selectors.keys()) - {'container', 'result_container'}
                selectors_to_use = {key: selectors[key] for key in to_extract if key in selectors.keys()}

                for index, result in enumerate(results):
                    # Let's add primitive support for CSS3 pseudo selectors
                    # We just need two of them
                    # ::text
                    # ::attr(attribute)

                    # You say we should use xpath expressions instead?
                    # Maybe you're right, but they are complicated when it comes to classes,
                    # have a look here: http://doc.scrapy.org/en/latest/topics/selectors.html
                    serp_result = {}
                    # key are for example 'link', 'snippet', 'visible-url', ...
                    # selector is the selector to grab these items
                    for key, selector in selectors_to_use.items():
                        serp_result[key] = self.advanced_css(selector, result)

                    serp_result['rank'] = index + 1

                    # Avoid duplicates. Duplicates are serp_result elemnts where the 'link' and 'title' are identical
                    # If statement below: Lazy evaluation. The more probable case first.
                    if not [e for e in self.search_results[result_type] if (e['link'] == serp_result['link'] and e['title'] == serp_result['title']) ]:
                        self.search_results[result_type].append(serp_result)
                        self.num_results += 1

    def advanced_css(self, selector, element):
        """Evaluate the :text and ::attr(attr-name) additionally.

        Args:
            selector: A css selector.
            element: The element on which to apply the selector.

        Returns:
            The targeted element.

        """
        value = None

        if selector.endswith('::text'):
            try:
                value = element.xpath(self.css_to_xpath(selector.split('::')[0]))[0].text_content()
            except IndexError:
                pass
        else:
            match = re.search(r'::attr\((?P<attr>.*)\)$', selector)

            if match:
                attr = match.group('attr')
                try:
                    value = element.xpath(self.css_to_xpath(selector.split('::')[0]))[0].get(attr)
                except IndexError:
                    pass
            else:
                try:
                    value = element.xpath(self.css_to_xpath(selector))[0].text_content()
                except IndexError:
                    pass

        return value

    def first_match(self, selectors, element):
        """Get the first match.

        Args:
            selectors: The selectors to test for a match.
            element: The element on which to apply the selectors.

        Returns:
            The very first match or False if all selectors didn't match anything.
        """
        assert isinstance(selectors, list), 'selectors must be of type list!'

        for selector in selectors:
            if selector:
                try:
                    match = self.advanced_css(selector, element=element)
                    if match:
                        return match
                except IndexError as e:
                    pass

        return False

    def after_parsing(self):
        """Subclass specific behaviour after parsing happened.
        
        Override in subclass to add search engine specific behaviour.
        Commonly used to clean the results.
        """

    def __str__(self):
        """Return a nicely formatted overview of the results."""
        return pprint.pformat(self.search_results)

    @property
    def cleaned_html(self):
        # Try to parse the provided HTML string using lxml
        # strip all unnecessary information to save space
        cleaner = Cleaner()
        cleaner.scripts = True
        cleaner.javascript = True
        cleaner.comments = True
        cleaner.style = True
        self.dom = cleaner.clean_html(self.dom)
        assert len(self.dom), 'The html needs to be parsed to get the cleaned html'
        return lxml.html.tostring(self.dom)

    def iter_serp_items(self):
        """Yields the key and index of any item in the serp results that has a link value"""

        for key, value in self.search_results.items():
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict) and item['link']:
                        yield (key, i)


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

    search_engine = 'google'

    search_types = ['normal', 'image']

    effective_query_selector = ['#topstuff .med > b::text', '.med > a > b::text']

    no_results_selector = []

    num_results_search_selectors = ['#resultStats']

    page_number_selectors = ['#navcnt td.cur::text']

    normal_search_selectors = {
        'results': {
            'us_ip': {
                'container': '#center_col',
                'result_container': 'div.g ',
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
            },
            'de_ip_news_items': {
                'container': 'li.card-section',
                'link': 'a._Dk::attr(href)',
                'snippet': 'span._dwd::text',
                'title': 'a._Dk::text',
                'visible_link': 'cite::text'
            },
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
        # those css selectors are probably not worth much
        'maps_local': {
            'de_ip': {
                'container': '#center_col',
                'result_container': '.ccBEnf > div',
                'link': 'link::attr(href)',
                'snippet': 'div.rl-qs-crs-t::text',
                'title': 'div[role="heading"] span::text',
                'rating': 'span.BTtC6e::text',
                'num_reviews': '.rllt__details::text',
            }
        },
        'ads_aside': {

        }
    }

    image_search_selectors = {
        'results': {
            'de_ip': {
                'container': 'li#isr_mc',
                'result_container': 'div.rg_di',
                'link': 'a.rg_l::attr(href)'
            },
            'de_ip_raw': {
                'container': '.images_table',
                'result_container': 'tr td',
                'link': 'a::attr(href)',
                'visible_link': 'cite::text',
            }
        }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def after_parsing(self):
        """Clean the urls.
        
        A typical scraped results looks like the following:
        
        '/url?q=http://www.youtube.com/user/Apple&sa=U&ei=\
        lntiVN7JDsTfPZCMgKAO&ved=0CFQQFjAO&usg=AFQjCNGkX65O-hKLmyq1FX9HQqbb9iYn9A'
        
        Clean with a short regex.
        """
        super().after_parsing()

        if self.searchtype == 'normal':
            if self.num_results > 0:
                self.no_results = False
            elif self.num_results <= 0:
                self.no_results = True

            if 'No results found for' in self.html or 'did not match any documents' in self.html:
                self.no_results = True

            # finally try in the snippets
            if self.no_results is True:
                for key, i in self.iter_serp_items():

                    if 'snippet' in self.search_results[key][i] and self.query:
                        if self.query.replace('"', '') in self.search_results[key][i]['snippet']:
                            self.no_results = False

        clean_regexes = {
            'normal': r'/url\?q=(?P<url>.*?)&sa=U&ei=',
            'image': r'imgres\?imgurl=(?P<url>.*?)&'
        }

        for key, i in self.iter_serp_items():
            result = re.search(
                clean_regexes[self.searchtype],
                self.search_results[key][i]['link']
            )
            if result:
                self.search_results[key][i]['link'] = unquote(result.group('url'))


class YandexParser(Parser):
    """Parses SERP pages of the Yandex search engine."""

    search_engine = 'yandex'

    search_types = ['normal', 'image']

    no_results_selector = ['.message .misspell__message::text']

    effective_query_selector = ['.misspell__message .misspell__link']

    # @TODO: In december 2015, I saw that yandex only shows the number of search results in the search input field
    # with javascript. One can scrape it in plain http mode, but the values are hidden in some javascript and not
    # accessible with normal xpath/css selectors. A normal text search is done.
    num_results_search_selectors = ['.serp-list .serp-adv__found::text', '.input__found_visibility_visible font font::text']

    page_number_selectors = ['.pager__group .button_checked_yes span::text']

    normal_search_selectors = {
        'results': {
            'de_ip': {
                'container': '.serp-list',
                'result_container': '.serp-item',
                'link': 'a.link::attr(href)',
                'snippet': 'div.text-container::text',
                'title': 'div.organic__url-text::text',
                'visible_link': '.typo_type_greenurl::text'
            }
        }
    }

    image_search_selectors = {
        'results': {
            'de_ip': {
                'container': '.page-layout__content-wrapper',
                'result_container': '.serp-item__preview',
                'link': '.serp-item__preview .serp-item__link::attr(onmousedown)'
            },
            'de_ip_raw': {
                'container': '.page-layout__content-wrapper',
                'result_container': '.serp-item__preview',
                'link': '.serp-item__preview .serp-item__link::attr(href)'
            }
        }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def after_parsing(self):
        """Clean the urls.

        Normally Yandex image search store the image url in the onmousedown attribute in a json object. Its
        pretty messsy. This method grabs the link with a quick regex.

        c.hit({"dtype":"iweb","path":"8.228.471.241.184.141","pos":69,"reqid":\
        "1418919408668565-676535248248925882431999-ws35-986-IMG-p2"}, \
        {"href":"http://www.thewallpapers.org/wallpapers/3/382/thumb/600_winter-snow-nature002.jpg"});

        Sometimes the img url is also stored in the href attribute (when requesting with raw http packets).
        href="/images/search?text=snow&img_url=\
        http%3A%2F%2Fwww.proza.ru%2Fpics%2F2009%2F12%2F07%2F1290.jpg&pos=2&rpt=simage&pin=1">
        """
        super().after_parsing()

        if self.searchtype == 'normal':
            self.no_results = False

            if self.no_results_text:
                self.no_results = 'По вашему запросу ничего не нашлось' in self.no_results_text

            if self.num_results == 0:
                self.no_results = True

            # very hackish, probably prone to all kinds of errors.
            if not self.num_results_for_query:
                substr = 'function() { var title = "%s —' % self.query
                try:
                    i = self.html.index(substr)
                    if i:
                        self.num_results_for_query = re.search(r'— (.)*?"', self.html[i:i+len(self.query) + 150]).group()
                except Exception as e:
                    logger.debug(str(e))


        if self.searchtype == 'image':
            for key, i in self.iter_serp_items():
                for regex in (
                        r'\{"href"\s*:\s*"(?P<url>.*?)"\}',
                        r'img_url=(?P<url>.*?)&'
                ):
                    result = re.search(regex, self.search_results[key][i]['link'])
                    if result:
                        self.search_results[key][i]['link'] = result.group('url')
                        break


class BingParser(Parser):
    """Parses SERP pages of the Bing search engine."""

    search_engine = 'bing'

    search_types = ['normal', 'image']

    no_results_selector = ['#b_results > .b_ans::text']

    num_results_search_selectors = ['.sb_count']

    effective_query_selector = ['#sp_requery a > strong', '#sp_requery + #sp_recourse a::attr(href)']

    page_number_selectors = ['.sb_pagS::text']

    normal_search_selectors = {
        'results': {
            'us_ip': {
                'container': '#b_results',
                'result_container': '.b_algo',
                'link': 'h2 > a::attr(href)',
                'snippet': '.b_caption > p::text',
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
            },
            'de_ip_news_items': {
                'container': 'ul.b_vList li',
                'link': ' h5 a::attr(href)',
                'snippet': 'p::text',
                'title': ' h5 a::text',
                'visible_link': 'cite::text'
            },
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

    image_search_selectors = {
        'results': {
            'ch_ip': {
                'container': '#dg_c .imgres',
                'result_container': '.dg_u',
                'link': 'a.dv_i::attr(m)'
            },
        }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def after_parsing(self):
        """Clean the urls.

        The image url data is in the m attribute.

        m={ns:"images.1_4",k:"5018",mid:"46CE8A1D71B04B408784F0219B488A5AE91F972E",
        surl:"http://berlin-germany.ca/",imgurl:"http://berlin-germany.ca/images/berlin250.jpg",
        oh:"184",tft:"45",oi:"http://berlin-germany.ca/images/berlin250.jpg"}
        """
        super().after_parsing()

        if self.searchtype == 'normal':

            self.no_results = False
            if self.no_results_text:
                self.no_results = self.query in self.no_results_text \
                    or 'Do you want results only for' in self.no_results_text

        if self.searchtype == 'image':
            for key, i in self.iter_serp_items():
                for regex in (
                        r'imgurl:"(?P<url>.*?)"',
                ):
                    result = re.search(regex, self.search_results[key][i]['link'])
                    if result:
                        self.search_results[key][i]['link'] = result.group('url')
                        break


class YahooParser(Parser):
    """Parses SERP pages of the Yahoo search engine."""

    search_engine = 'yahoo'

    search_types = ['normal', 'image']

    no_results_selector = []

    effective_query_selector = ['.msg #cquery a::attr(href)']

    num_results_search_selectors = ['#pg > span:last-child', '.compPagination span::text']

    page_number_selectors = ['#pg > strong::text']

    normal_search_selectors = {
        'results': {
            'de_ip': {
                'container': '#main',
                'result_container': '.res',
                'link': 'div > h3 > a::attr(href)',
                'snippet': 'div.abstr::text',
                'title': 'div > h3 > a::text',
                'visible_link': 'span.url::text'
            },
            'de_ip_december_2015': {
                'container': '#main',
                'result_container': '.searchCenterMiddle li',
                'link': 'h3.title a::attr(href)',
                'snippet': '.compText p::text',
                'title': 'h3.title a::text',
                'visible_link': 'span::text'
            },
        },
    }

    image_search_selectors = {
        'results': {
            'ch_ip': {
                'container': '#results',
                'result_container': '#sres > li',
                'link': 'a::attr(href)'
            },
        }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def after_parsing(self):
        """Clean the urls.

        The url is in the href attribute and the &imgurl= parameter.

        <a id="yui_3_5_1_1_1419284335995_1635" aria-label="<b>Matterhorn</b> sunrise"
        href="/images/view;_ylt=AwrB8phvj5hU7moAFzOJzbkF;_ylu=\
        X3oDMTIyc3ZrZ3RwBHNlYwNzcgRzbGsDaW1nBG9pZANmNTgyY2MyYTY4ZmVjYTI5YmYwNWZlM2E3ZTc1YzkyMARncG9zAzEEaXQDYmluZw--?
        .origin=&back=https%3A%2F%2Fimages.search.yahoo.com%2Fsearch%2Fimages%3F\
        p%3Dmatterhorn%26fr%3Dyfp-t-901%26fr2%3Dpiv-web%26tab%3Dorganic%26ri%3D1&w=4592&h=3056&
        imgurl=www.summitpost.org%2Fimages%2Foriginal%2F699696.JPG&rurl=http%3A%2F%2Fwww.summitpost.org\
        %2Fmatterhorn-sunrise%2F699696&size=5088.0KB&
        name=%3Cb%3EMatterhorn%3C%2Fb%3E+sunrise&p=matterhorn&oid=f582cc2a68feca29bf05fe3a7e75c920&fr2=piv-web&
        fr=yfp-t-901&tt=%3Cb%3EMatterhorn%3C%2Fb%3E+sunrise&b=0&ni=21&no=1&ts=&tab=organic&
        sigr=11j056ue0&sigb=134sbn4gc&sigi=11df3qlvm&sigt=10pd8j49h&sign=10pd8j49h&.crumb=qAIpMoHvtm1&\
        fr=yfp-t-901&fr2=piv-web">
        """
        super().after_parsing()

        if self.searchtype == 'normal':

            self.no_results = False
            if self.num_results == 0:
                self.no_results = True

            if len(self.dom.xpath(self.css_to_xpath('#cquery'))) >= 1:
                self.no_results = True

            for key, i in self.iter_serp_items():
                if self.search_results[key][i]['visible_link'] is None:
                    del self.search_results[key][i]

        if self.searchtype == 'image':
            for key, i in self.iter_serp_items():
                for regex in (
                        r'&imgurl=(?P<url>.*?)&',
                ):
                    result = re.search(regex, self.search_results[key][i]['link'])
                    if result:
                        # TODO: Fix this manual protocol adding by parsing "rurl"
                        self.search_results[key][i]['link'] = 'http://' + unquote(result.group('url'))
                        break


class BaiduParser(Parser):
    """Parses SERP pages of the Baidu search engine."""

    search_engine = 'baidu'

    search_types = ['normal', 'image']

    num_results_search_selectors = ['#container .nums']

    no_results_selector = []

    # no such thing for baidu
    effective_query_selector = ['']

    page_number_selectors = ['.fk_cur + .pc::text']

    normal_search_selectors = {
        'results': {
            'de_ip': {
                'container': '#content_left',
                'result_container': '.result-op',
                'link': 'h3 > a.t::attr(href)',
                'snippet': '.c-abstract::text',
                'title': 'h3 > a.t::text',
                'visible_link': 'span.c-showurl::text'
            },
            'nojs': {
                'container': '#content_left',
                'result_container': '.result',
                'link': 'h3 > a::attr(href)',
                'snippet': '.c-abstract::text',
                'title': 'h3 > a::text',
                'visible_link': 'span.g::text'
            }
        },
    }

    image_search_selectors = {
        'results': {
            'ch_ip': {
                'container': '#imgContainer',
                'result_container': '.pageCon > li',
                'link': '.imgShow a::attr(href)'
            },
        }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def after_parsing(self):
        """Clean the urls.

        href="/i?ct=503316480&z=&tn=baiduimagedetail&ipn=d&word=matterhorn&step_word=&ie=utf-8&in=9250&
        cl=2&lm=-1&st=&cs=3326243323,1574167845&os=1495729451,4260959385&pn=0&rn=1&di=69455168860&ln=1285&
        fr=&&fmq=1419285032955_R&ic=&s=&se=&sme=0&tab=&width=&height=&face=&is=&istype=&ist=&jit=&
        objurl=http%3A%2F%2Fa669.phobos.apple.com%2Fus%2Fr1000%2F077%2FPurple%2F\
        v4%2F2a%2Fc6%2F15%2F2ac6156c-e23e-62fd-86ee-7a25c29a6c72%2Fmzl.otpvmwuj.1024x1024-65.jpg&adpicid=0"
        """
        super().after_parsing()

        if self.search_engine == 'normal':
            if len(self.dom.xpath(self.css_to_xpath('.hit_top_new'))) >= 1:
                self.no_results = True

        if self.searchtype == 'image':
            for key, i in self.iter_serp_items():
                for regex in (
                        r'&objurl=(?P<url>.*?)&',
                ):
                    result = re.search(regex, self.search_results[key][i]['link'])
                    if result:
                        self.search_results[key][i]['link'] = unquote(result.group('url'))
                        break


class DuckduckgoParser(Parser):
    """Parses SERP pages of the Duckduckgo search engine."""

    search_engine = 'duckduckgo'

    search_types = ['normal']

    num_results_search_selectors = []

    no_results_selector = []

    effective_query_selector = ['']

    # duckduckgo is loads next pages with ajax
    page_number_selectors = ['']

    normal_search_selectors = {
        'results': {
            'de_ip': {
                'container': '#links',
                'result_container': '.result',
                'link': '.result__title > a::attr(href)',
                'snippet': 'result__snippet::text',
                'title': '.result__title > a::text',
                'visible_link': '.result__url__domain::text'
            },
            'non_javascript_mode': {
                'container': '#content',
                'result_container': '.results_links',
                'link': '.links_main > a::attr(href)',
                'snippet': '.snippet::text',
                'title': '.links_main > a::text',
                'visible_link': '.url::text'
            },
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def after_parsing(self):
        super().after_parsing()

        if self.searchtype == 'normal':

            try:
                if 'No more results.' in self.dom.xpath(self.css_to_xpath('.no-results'))[0].text_content():
                    self.no_results = True
            except:
                pass

            if self.num_results > 0:
                self.no_results = False
            elif self.num_results <= 0:
                self.no_results = True


class AskParser(Parser):
    """Parses SERP pages of the Ask search engine."""

    search_engine = 'ask'

    search_types = ['normal']

    num_results_search_selectors = []

    no_results_selector = []

    effective_query_selector = ['#spell-check-result > a']

    page_number_selectors = ['.pgcsel .pg::text']

    normal_search_selectors = {
        'results': {
            'de_ip': {
                'container': '#midblock',
                'result_container': '.ptbs.ur',
                'link': '.abstract > a::attr(href)',
                'snippet': '.abstract::text',
                'title': '.txt_lg.b::text',
                'visible_link': '.durl span::text'
            },
            'de_ip_december_2015': {
                'container': '.l-mid-content',
                'result_container': '.web-result',
                'link': '.web-result-title > a::attr(href)',
                'snippet': '.web-result-description::text',
                'title': '.web-result-title > a::text',
                'visible_link': '.web-result-url::text'
            },
            # as requested by httm mode
            'de_ip_december_2015_raw_http': {
                'container': '#midblock',
                'result_container': '#teoma-results .wresult',
                'link': 'a.title::attr(href)',
                'snippet': '.abstract::text',
                'title': 'a.title::text',
                'visible_link': '.durl span::text'
            }
        },
    }


class BlekkoParser(Parser):
    """Parses SERP pages of the Blekko search engine."""

    search_engine = 'blekko'

    search_types = ['normal']

    effective_query_selector = ['']

    no_results_selector = []

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
    if re.search(r'^http[s]?://[a-z]{2}?\.ask', url):
        parser = AskParser
    if re.search(r'^http[s]?://blekko', url):
        parser = BlekkoParser
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
    if search_engine == 'google' or search_engine == 'googleimg':
        return GoogleParser
    elif search_engine == 'yandex':
        return YandexParser
    elif search_engine == 'bing':
        return BingParser
    elif search_engine == 'yahoo':
        return YahooParser
    elif search_engine == 'baidu' or search_engine == 'baiduimg':
        return BaiduParser
    elif search_engine == 'duckduckgo':
        return DuckduckgoParser
    elif search_engine == 'ask':
        return AskParser
    elif search_engine == 'blekko':
        return BlekkoParser
    else:
        raise NoParserForSearchEngineException('No such parser for "{}"'.format(search_engine))


def parse_serp(config, html=None, parser=None, scraper=None, search_engine=None, query=''):
    """Store the parsed data in the sqlalchemy session.

    If no parser is supplied then we are expected to parse again with
    the provided html.

    This function may be called from scraping and caching.
    When called from caching, some info is lost (like current page number).

    Args:
        TODO: A whole lot

    Returns:
        The parsed SERP object.
    """

    if not parser and html:
        parser = get_parser_by_search_engine(search_engine)
        parser = parser(config, query=query)
        parser.parse(html)

    serp = SearchEngineResultsPage()

    if query:
        serp.query = query

    if parser:
        serp.set_values_from_parser(parser)
    if scraper:
        serp.set_values_from_scraper(scraper)

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

    assert len(sys.argv) >= 2, 'Usage: {} url/file'.format(sys.argv[0])
    url = sys.argv[1]
    if os.path.exists(url):
        raw_html = open(url, 'r').read()
        parser = get_parser_by_search_engine(sys.argv[2])
    else:
        raw_html = requests.get(url).text
        parser = get_parser_by_url(url)

    parser = parser(raw_html)
    parser.parse()
    print(parser)

    with open('/tmp/testhtml.html', 'w') as of:
        of.write(raw_html)
