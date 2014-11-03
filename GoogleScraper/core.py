# -*- coding: utf-8 -*-

"""
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
- three different modes:
    + requesting with raw http packets
    + using the selenium web driver framework
    + scraping with phantomjs (planned)

Note: Scraping compromises the google terms of service (TOS).
"""
import math
import threading
import queue
from urllib.parse import urlparse, unquote
import datetime

from GoogleScraper.utils import grouper
from GoogleScraper.proxies import parse_proxy_file, get_proxies_from_mysql_db
from GoogleScraper.res import maybe_create_db
from GoogleScraper.scraping import SelScraper, GoogleScrape
from GoogleScraper.caching import *
from GoogleScraper.config import get_config, InvalidConfigurationException, parse_cmd_args, Config
import GoogleScraper.config

try:
    from cssselect import HTMLTranslator, SelectorError
    from bs4 import UnicodeDammit
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait  # available since 2.4.0
    from selenium.webdriver.support import expected_conditions as EC  # available since 2.26.0
except ImportError as ie:
    if hasattr(ie, 'name') and ie.name == 'bs4' or hasattr(ie, 'args') and 'bs4' in str(ie):
        sys.exit('Install bs4 with the command "sudo pip3 install beautifulsoup4"')
    if ie.name == 'socks':
        sys.exit('socks is not installed. Try this one: https://github.com/Anorov/PySocks')

    print(ie)
    sys.exit('You can install missing modules with `pip3 install [modulename]`')

logger = logging.getLogger('GoogleScraper')

def deep_scrape(query):
    """Launches many different Google searches with different parameter combinations to maximize return of results. Depth first.

    This is the heart of core.py. The aim of deep_scrape is to maximize the number of links for a given keyword.
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

def scrape(keyword='', scrapemethod='sel', num_results_per_page=10, num_pages=1, offset=0, proxy=None):
    """Public API function to search for terms and return a list of results.

    This (maybe) prevents Google to sort us out because of aggressive behaviour.

    arguments:
    query -- the search query. Can be whatever you want to crawl google for.

    Keyword arguments:
    scrapemethod -- the scrapemethod
    num_results_per_page -- the number of results per page. Either 10, 25, 50 or 100.
    num_pages -- The number of pages to search for.
    offset -- specifies the offset to the page to begin searching.
    """
    if scrapemethod == 'http':
        threads = [GoogleScrape(keyword, num_results_per_page, i, interval=i, proxy=proxy)
                       for i in range(offset, num_pages + offset, 1)]
    elif scrapemethod == 'sel':
        threads = [SelScraper([keyword], proxy=proxy, captcha_lock=threading.Lock)]

    for t in threads:
        t.start()

    # wait for all threads to end running
    for t in threads:
        t.join()

    if scrapemethod == 'http':
        return [t.results for t in threads]
    else:
        return threads[0].results

def scrape_with_config(config, **kwargs):
    """First updates the global GoogleScraper configuration with the provided dictionary.

    Arguments:
    config -- A configuration dictionary that updates the global configuration.

    Keyword arguments:
    kwargs -- Further options that cannot be handled by the configuration.
    """

    if not isinstance(config, dict):
        raise ValueError('The config parameter needs to be a configuration dictionary. Given parameter has type: {}'.format(type(config)))

    GoogleScraper.config.already_parsed = True
    GoogleScraper.config.update_config(config)
    return main(return_results=True, force_reload=False, **kwargs)

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
            'INSERT INTO serp_page (page_number, requested_at, num_results, num_results_for_kw_google, search_query, requested_by) VALUES(?, ?, ?, ?, ?, ?)', first)
        lastrowid = self.cursor.lastrowid
        #logger.debug('Inserting in link: search_query={}, title={}, url={}'.format(kw, ))
        self.cursor.executemany('''INSERT INTO link
        ( title,
         url,
         snippet,
         rank,
         domain,
         serp_id) VALUES(?, ?, ?, ?, ?, ?)''', [tuple(t)+ (lastrowid, ) for t in second])

    def run(self):
        i = 0
        while True:
            #  If optional args block is true and timeout is None (the default), block if necessary until an item is available.
            item = self.queue.get(block=True)
            if item == Config['GLOBAL']['all_processed_sig']:
                logger.info('turning down. All results processed.')
                break
            self._insert_in_db(item)
            self.queue.task_done()
            if i > 0 and (i % Config['GLOBAL'].getint('commit_interval')) == 0:
                # commit in intervals specified in the config
                self.conn.commit()
            i += 1

def print_scrape_results_http(results, verbosity=1):
    """Print the results obtained by "http" method."""
    for t in results:
        for result in t:
            logger.info('{} links found. The search with the keyword "{}" yielded the result: "{}"'.format(
                len(result['results']), result['search_keyword'], result['num_results_for_kw']))
            import textwrap
            for result_set in ('results', 'ads_main', 'ads_aside'):
                if result_set in result.keys():
                    print('### {} link results for "{}" ###'.format(len(result[result_set]), result_set))
                    for link_title, link_snippet, link_url, link_position in result[result_set]:
                        try:
                            print('  Link: {}'.format(unquote(link_url.geturl())))
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

def main(return_results=True, force_reload=False, proxies=[]):
    """Runs the GoogleScraper application as determined by the various configuration points.

    Keyword arguments:
    return_results -- Whether the GoogleScraper application is run programmatically. Will return all scraped results.
    """
    parse_cmd_args()

    if Config['GLOBAL'].getboolean('view_config'):
        from GoogleScraper.config import CONFIG_FILE
        print(open(CONFIG_FILE).read())
        sys.exit(0)

    if Config['GLOBAL'].getboolean('do_caching'):
        d = Config['GLOBAL'].get('cachedir')
        if not os.path.exists(d):
            os.mkdir(d, 0o744)
        else:
            maybe_clean_cache()

    kwfile = Config['SCRAPING'].get('keyword_file')
    keyword = Config['SCRAPING'].get('keyword')
    keywords = set(Config['SCRAPING'].get('keywords', '').split('\n'))
    proxy_file = Config['GLOBAL'].get('proxy_file', '')
    proxy_db = Config['GLOBAL'].get('mysql_proxy_db', '')

    if not (keyword or keywords) and not kwfile:
        raise InvalidConfigurationException('You must specify a keyword file (separated by newlines, each keyword on a line) with the flag `--keyword-file {filepath}~')

    if Config['GLOBAL'].getboolean('fix_cache_names'):
        fix_broken_cache_names()
        sys.exit('renaming done. restart for normal use.')

    keywords = [keyword, ] if keyword else keywords
    if kwfile:
        if not os.path.exists(kwfile):
            raise InvalidConfigurationException('The keyword file {} does not exist.'.format(kwfile))
        else:
            # Clean the keywords of duplicates right in the beginning
            keywords = set([line.strip() for line in open(kwfile, 'r').read().split('\n')])

    if Config['GLOBAL'].getboolean('check_oto', False):
        _caching_is_one_to_one(keyword)

    if Config['SCRAPING'].getint('num_results_per_page') > 100:
        raise InvalidConfigurationException('Not more that 100 results per page available for Google searches.')

    if not proxies:
        # look for proxies in mysql database or a proxy file if not given as keyword argument
        if proxy_db:
            proxies = get_proxies_from_mysql_db(proxy_db)
        elif proxy_file:
            proxies = parse_proxy_file(proxy_file)

    valid_search_types = ('normal', 'video', 'news', 'image')
    if Config['SCRAPING'].get('search_type') not in valid_search_types:
        InvalidConfigurationException('Invalid search type! Select one of {}'.format(repr(valid_search_types)))

    # Create a sqlite database to store the results
    conn = maybe_create_db()
    if Config['GLOBAL'].getboolean('simulate'):
        print('*' * 60 + 'SIMULATION' + '*' * 60)
        logger.info('If GoogleScraper would have been run without the --simulate flag, it would have')
        logger.info('Scraped for {} keywords (before caching), with {} results a page, in total {} pages for each keyword'.format(
            len(keywords), Config['SCRAPING'].getint('num_results_per_page', 0), Config['SCRAPING'].getint('num_of_pages')))
        logger.info('Used {} distinct proxies in total, with the following ip addresses: {}'.format(
            len(proxies), '\t\t\n'.join(proxies)
        ))
        if Config['SCRAPING'].get('scrapemethod') == 'sel':
            mode = 'selenium mode with {} browser instances'.format(Config['SELENIUM'].getint('num_browser_instances'))
        else:
            mode = 'http mode'
        logger.info('By using {}'.format(mode))
        sys.exit(0)

    # Let the games begin
    if Config['SCRAPING'].get('scrapemethod', '') == 'sel':
        # First of all, lets see how many keywords remain to scrape after parsing the cache
        if Config['GLOBAL'].getboolean('do_caching'):
            remaining = parse_all_cached_files(keywords, conn, simulate=Config['GLOBAL'].getboolean('simulate'))
        else:
            remaining = keywords


        # Create a lock to sync file access
        rlock = threading.RLock()

        # A lock to prevent multiple threads from solving captcha.
        lock = threading.Lock()

        max_sel_browsers = Config['SELENIUM'].getint('num_browser_instances')
        if len(remaining) > max_sel_browsers:
            kwgroups = grouper(remaining, len(remaining)//max_sel_browsers, fillvalue=None)
        else:
            # thats a little special there :)
            kwgroups = [[kw, ] for kw in remaining]

        # Distribute the proxies evenly on the keywords to search for
        scrapejobs = []
        Q = queue.Queue()

        if Config['SCRAPING'].getboolean('use_own_ip'):
            proxies.append(None)
        elif not proxies:
            raise InvalidConfigurationException("No proxies available and using own IP is prohibited by configuration. Turning down.")

        chunks_per_proxy = math.ceil(len(kwgroups)/len(proxies))
        for i, chunk in enumerate(kwgroups):
            scrapejobs.append(SelScraper(chunk, rlock, Q, captcha_lock=lock, browser_num=i, proxy=proxies[i//chunks_per_proxy]))

        for t in scrapejobs:
            t.start()

        handler = ResultsHandler(Q, conn)
        handler.start()

        for t in scrapejobs:
            t.join()

        # All scrape jobs done, signal the db handler to stop
        Q.put(Config['GLOBAL'].get('all_processed_sig'))
        handler.join()

        conn.commit()

        if return_results:
            return conn
        else:
            conn.close()

    elif Config['SCRAPING'].get('scrapemethod') == 'http':
        results = []
        cursor = conn.cursor()
        if Config['SCRAPING'].getboolean('deep_scrape', False):
            # TODO: implement deep scrape
            raise NotImplementedError('Sorry. Currently deep scrape is not implemented.')
        else:
            for i, kw in enumerate(keywords):
                r = scrape(kw, num_results_per_page=Config['SCRAPING'].getint('num_results_per_page', 10),
                           num_pages=Config['SCRAPING'].getint('num_pages', 1), scrapemethod='http')

                if r:
                    cursor.execute('INSERT INTO serp_page (page_number, requested_at, num_results, num_results_for_kw_google, search_query) VALUES(?,?,?,?,?)',
                                 (i, datetime.datetime.utcnow(), 0, 0, kw))
                    serp_id = cursor.lastrowid
                    for result in r:
                        for result_set in ('results', 'ads_main', 'ads_aside'):
                            if result_set in result.keys():
                                for title, snippet, url, pos in result[result_set]:
                                    cursor.execute('INSERT INTO link (title, snippet, url, domain, rank, serp_id) VALUES(?, ?, ?, ?, ?, ?)',
                                        (title, snippet, url.geturl(), url.netloc, pos, serp_id))
                results.append(r)
            cursor.close()
        if Config['GLOBAL'].get('print'):
            print_scrape_results_http(results, Config['GLOBAL'].getint('verbosity', 0))
        return conn
    else:
        raise InvalidConfigurationException('No such scrapemethod. Use "http" or "sel"')