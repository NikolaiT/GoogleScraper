__author__ = 'nikolai'

import requests
import re
import GoogleScraper
import lxml.html
from bs4 import UnicodeDammit

def random_words(n=50, wordlength=range(10, 15)):
    """Read a random english wiki article and extract some words.

    Arguments:
    n -- The number of words to return. Returns all found ones, if n is more than we were able to found.
    KeywordArguments:
    wordlength -- A range that forces the words to have a specific length.
    """
    valid_words = re.compile(r'[a-zA-Z]{{{},{}}}'.format(wordlength.start, wordlength.stop))
    found = list(set(valid_words.findall(requests.get('http://en.wikipedia.org/wiki/Special:Random').text)))
    try:
        return found[:n]
    except IndexError:
        return found

def get_proxies(n=5):
    """Read some notoriously known sites and extract some public proxies.

    Scrapes
        - http://www.samair.ru/proxy/

    The quality of these proxies is probably not worth to be mentioned, but it's
    nice to test the lack of quality and the behaviour of GoogleScraper.
    """
    r = requests.get('http://www.samair.ru/proxy/')
    # Try to parse the google HTML result using lxml
    try:
        doc = UnicodeDammit(r.text, is_html=True)
        parser = lxml.html.HTMLParser(encoding=doc.declared_html_encoding)
        dom = lxml.html.document_fromstring(r.text, parser=parser)
        dom.resolve_base_href()
    except Exception as e:
        print('Some error occurred while lxml tried to parse: {}'.format(e))

    table = dom.xpath('//table[@id=\'proxylist\']')[0]
    for row in table.findall('tr'):
        print(row.xpath('//td[1]')[0].text_content())

    return GoogleScraper.Proxy()