__author__ = 'nikolai'
__date__ = '12.03.2014'
__license__ = 'gimme beer'

import argparse
import sqlite3
import os
import re
import time
import random
import threading
import signal
import types
import sys
import pprint
try:
    from selenium import webdriver
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait # available since 2.4.0
    from selenium.webdriver.support import expected_conditions as EC # available since 2.26.0
    from cssselect import HTMLTranslator, SelectorError
    from bs4 import UnicodeDammit
    import lxml.html
except ImportError as ie:
    print(ie)

DB = 'results.db'

def get_command_line():
    parser = argparse.ArgumentParser(prog='SelScraper', description='Scrapes the Google search engine by using real browsers',
                                     epilog='This program might infringe Google TOS, so use at your own risk')
    parser.add_argument('-q', '--keywords', metavar='keywords', type=str, action='store', dest='keywords',
                        help='The search keywords to scrape for.')
    parser.add_argument('--keywords-file', type=str, action='store', dest='kwfile',
                        help='Keywords to search for. One keyword per line. Empty lines are ignored.')
    parser.add_argument('-n', '--num_results_per_page', metavar='number_of_results_per_page', type=int,
                        dest='num_results_per_page', action='store', default=50,
                        help='The number of results per page. Most be >= 100')
    parser.add_argument('-p', '--num_pages', metavar='num_of_pages', type=int, dest='num_pages', action='store',
                        default=1,
                        help='The number of pages to search in. Each page is requested by a unique connection and if possible by a unique IP.')

    args = parser.parse_args()

    if args.keywords and args.kwfile:
        raise ValueError('Invalid command line usage. Either set keywords as a string or provide a keyword file, but not both you dirty whore')

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

    return args

def maybe_create_db():
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
           num_results INTEGER NOT NULL, search_query TEXT NOT NULL)''')
        cursor.execute('''CREATE TABLE results
        (id INTEGER PRIMARY KEY AUTOINCREMENT, link_title TEXT,
           link_snippet TEXT, link_url TEXT,
           serp_id INTEGER NOT NULL, FOREIGN KEY(serp_id) REFERENCES serp_page(id))''')

        conn.commit()
        return (conn, cursor)

def setup_db():
    return maybe_create_db()

class SelScraper(threading.Thread):
    """A SelScraper automatic browser instance represented in a thread"""
    # the google search url
    url = 'https://www.google.com'

    def __init__(self, keywords, rlock, cursor):
        super().__init__()
        self.cursor = cursor
        self.rlock = rlock
        self.keywords = keywords

    def run(self):
        self.webdriver = webdriver.Firefox()
        self.webdriver.get(self.url)
        try:
            self.element = WebDriverWait(self.webdriver, 10).until(EC.presence_of_element_located((By.NAME, "q")))
        except Exception as e:
            pass
        while self.keywords:
            self.kw = self.keywords.pop()
            if not self.kw:
                break
            self.element.send_keys(self.kw + Keys.ENTER)
            self.webdriver.implicitly_wait(1)
            self._parse_links_sel() # call here one of _parse_links_native or _parse_links_sel
            time.sleep(random.randint(10, 20) // 10)
        self.webdriver.close()

    def _parse_links_sel(self):
        """Scrapes the google SERP page with selenium methods.

         (is slow, because css selectors are probably done with javascript)
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

        self.cursor.executemany('INSERT INTO results (link_title, link_title, link_snippet, serp_id) VALUES(?, ?, ?, ?)',
                                    [tuple + (lastrowid, ) for tuple in parsed])
        self.rlock.release()

    def _parse_links_native(self):
        """Injects the scraping methods of GoogleScrape in this class. That's some awesome metaprogramming here!"""
        # fix the path
        sys.path.append(re.sub(r'\/\w*?$', '', os.getcwd()))
        from GoogleScraper import GoogleScrape
        from GoogleScraper import setup_logger
        setup_logger()
        for attribute in ('_xp', '_parse_normal_search', '_parse_image_search',
                       '_parse_video_search', '_parse_news_search', '_parse', '_parse_links'):
            a = getattr(GoogleScrape, attribute)
            if not hasattr(self, attribute):
                # the method needs to be bound
                if isinstance(a, (types.FunctionType, types.BuiltinFunctionType)):
                    setattr(self, attribute, types.MethodType(a, self))
                else:
                    setattr(self, attribute, a)
        self.SEARCH_RESULTS = {
            'search_keyword': self.kw,  # The query keyword
            'num_results_for_kw': '',  # The number of results for the keyword. Valid vor all kind of searches
            'results': [],  # List of Result, list of named tuples
            'ads_main': [],  # The google ads in the main result set.
            'ads_aside': [],  # The google ads on the right aside.
        }
        # Try to parse the google HTML result using lxml
        try:
            doc = UnicodeDammit(self.webdriver.page_source, is_html=True)
            parser = lxml.html.HTMLParser(encoding=doc.declared_html_encoding)
            dom = lxml.html.document_fromstring(self.webdriver.page_source, parser=parser)
            dom.resolve_base_href()
        except Exception as e:
            print('Some error occurred while lxml tried to parse: {}'.format(e.msg))
            return False

        self._parse_normal_search(dom)
        pprint.pprint(self.SEARCH_RESULTS)


if __name__ == '__main__':
    args = get_command_line()
    conn, cursor = setup_db()

    rlock = threading.RLock()
    browsers = [SelScraper([kw], rlock, cursor) for kw in args.keywords]

    def signal_handler(signal, frame):
        print('Ctrl-c was pressed...')
        conn.close()
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    for t in browsers:
        t.start()

    for t in browsers:
        t.join()

    conn.commit()

    conn.close()


