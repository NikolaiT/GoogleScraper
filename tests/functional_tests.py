# some functional tests

# it'd be nice to test some key aspects of GoogleScraper
# Searching with selenium mode, phantomjs and the traditional http raw way
import requests
import re
import GoogleScraper
import random
import sqlite3
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

def test_scrape_selenium_mode(sel_browser, num_words=15, num_pages=2):
   """Run some none proxied normal selenium mode tests"""
   some_words = random_words(num_words, range(6, 17))
   GoogleScraper.Config['SCRAPING'].update(
           {
               'keywords': '\n'.join(some_words[0:num_words]),
               'scrapemethod': 'sel',
               'num_of_pages': str(num_pages)
           })
   GoogleScraper.Config['GLOBAL'].update(
       {
               'db': '{}_test.db'.format(sel_browser),
               'do_caching': 'False'
       })
   GoogleScraper.Config['SELENIUM'].update(
       {
           'sel_browser': sel_browser
       }
   )
   GoogleScraper.run()

   con = sqlite3.connect('{}_test.db'.format(sel_browser))
   con.row_factory = sqlite3.Row
   # check that we got a reasonable amount of urls
   cnt = con.execute('select count(*) as cnt from serp_page').fetchone()['cnt']
   assert int(cnt) >= (num_pages * num_words), 'Scraped {} keywords, with {} pages each, got only {}'.format(
       num_words,
       num_pages,
       cnt
   )
   # lets see if the links are really links
   for result in con.execute('select url, domain from link').fetchall():
       url, domain = result
       assert GoogleScraper.Google_SERP_Parser._REGEX_VALID_URL.match(url)

def test_all_selenium_modes():
    for browser in ('firefox', 'chrome', 'phantomjs'):
        test_scrape_selenium_mode('firefox', num_words=random.randint(5, 10), num_pages=random.randint(1, 3))


def test_raw_mode():
    """Run googlescraper in the traditional mode by sending raw http packets"""
    GoogleScraper.Config['SCRAPING'].update({'scrapemethod': 'raw'})
    GoogleScraper

def test_scrape_proxy_support(sel_browser, num_words=15, num_pages=2):
    proxy_file = open('proxies.txt', 'wt')
    proxy_file.writelines(get_proxies())
    GoogleScraper.Config['GLOBAL'].update({'proxy_file': 'proxies.txt'})
    test_raw_mode()
    test_all_selenium_modes()

if __name__ == '__main__':
    # get_proxies()
    test_all_selenium_modes()
    # test_raw_mode()

