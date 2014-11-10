# -*- coding: utf-8 -*-

"""
This file contains the core functionality of GoogleScraper.

This is a little module that uses Google to automate search
queries. It gives straightforward access to all relevant data of Google such as
- The links of the result page
- The title of the links
- The caption/description below each link
- The number of results for this keyword
- The rank for the specific results
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

def scrape(keyword='', scrapemethod='sel', num_results_per_page=10, num_pages=1, offset=0, proxy=None):
    """Public API function to search for keywords.

    Args:
        keyword: The search query. Can be whatever you want to crawl Google for.
        scrapemethod: The method of scraping to use.
        num_num_results_per_page: How many results should be displayed on a SERP page. Defaults to 10.
        num_pages: How many pages to scrape.
        offset: On which page to start scraping.
        proxy: Optional, If set to appropriate data, will use a proxy.

    Returns:
        The scraping results.
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
    """Runs GoogleScraper with the dict in config.

    Args:
        config: A configuration dictionary that updates the global configuration.
        kwargs: Further options that cannot be handled by the configuration.
    Returns:
        The result of the main() function. May be void or a sqlite3 connection.
    """
    if not isinstance(config, dict):
        raise ValueError('The config parameter needs to be a configuration dictionary. Given parameter has type: {}'.format(type(config)))

    GoogleScraper.config.already_parsed = True
    GoogleScraper.config.update_config(config)
    return main(return_results=True, force_reload=False, **kwargs)

class ResultsHandler(threading.Thread):
    """Consume data that the SelScraper/GoogleScrape threads put in the queue.

    Opens a database connection and puts data in it. Intended to be run in the main thread.

    Implements the multi-producer pattern.

    The ResultHandler cannot necessarily know when he should stop waiting. That's why we
    have a special DONE element in the Config that signals that all threads have finished and
    all data was processed.
    """
    def __init__(self, queue, conn):
        super().__init__()
        self.queue = queue
        self.conn = conn
        self.cursor = self.conn.cursor()

    def _insert_in_db(self, e):
        """Inserts elements obtained from the queue in the database.

        Args:
            e: A tuple that contains a serp_page and link result.
        """
        assert isinstance(e, tuple) and len(e) == 2
        first, second = e
        self.cursor.execute(
            'INSERT INTO serp_page (page_number, requested_at, num_results, num_results_for_kw_google, search_query, requested_by) VALUES(?, ?, ?, ?, ?, ?)', first)
        lastrowid = self.cursor.lastrowid
        self.cursor.executemany('''INSERT INTO link
        ( title,
         url,
         snippet,
         rank,
         domain,
         serp_id) VALUES(?, ?, ?, ?, ?, ?)''', [tuple(t)+ (lastrowid, ) for t in second])

    def run(self):
        """Waits for elements in the queue until a special token ends the endless loop"""
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

def print_scrape_results_http(results):
    """Print the results obtained by "http" method.

    Args:
        results: The results to be printed to stdout.
    """
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
                        if Config['GLOBAL'].getint('verbosity') > 1:
                            print(
                                '  Title: \n{}'.format(textwrap.indent('\n'.join(textwrap.wrap(link_title, 50)), '\t')))
                            print(
                                '  Description: \n{}\n'.format(
                                    textwrap.indent('\n'.join(textwrap.wrap(link_snippet, 70)), '\t')))
                            print('*' * 70)
                            print()

def main(return_results=True):
    """Runs the GoogleScraper application as determined by the various configuration points.

    The main() function encompasses the core functionality of GoogleScraper. But it
    shouldn't be the main() functions job to check the validity of the provided
    configuration.

    Args:
        return_results: When GoogleScrape is used from within another program, don't print results to stdout,
                        store them in a database instead.
    Returns:
        A database connection to the results when return_results is True
    """
    parse_cmd_args()

    if Config['GLOBAL'].getboolean('view_config'):
        from GoogleScraper.config import CONFIG_FILE
        print(open(CONFIG_FILE).read())
        return

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
        logger.info('renaming done. restart for normal use.')
        return

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

    if proxy_db:
        proxies = get_proxies_from_mysql_db(proxy_db)
    elif proxy_file:
        proxies = parse_proxy_file(proxy_file)

    valid_search_types = ('normal', 'video', 'news', 'image')
    if Config['SCRAPING'].get('search_type') not in valid_search_types:
        InvalidConfigurationException('Invalid search type! Select one of {}'.format(repr(valid_search_types)))

    # Create a sqlite3 database to store the results
    conn = maybe_create_db()
    if Config['GLOBAL'].getboolean('simulate'):
        print('*' * 60 + 'SIMULATION' + '*' * 60)
        logger.info('If GoogleScraper would have been run without the --simulate flag, it would have')
        logger.info('Scraped for {} keywords (before caching), with {} results a page, in total {} pages for each keyword'.format(
            len(keywords), Config['SCRAPING'].getint('num_results_per_page', 0), Config['SCRAPING'].getint('num_of_pages')))
        logger.info('Used {} distinct proxies in total, with the following proxies: {}'.format(len(proxies), '\t\t\n'.join(proxies)))
        if Config['SCRAPING'].get('scrapemethod') == 'sel':
            mode = 'selenium mode with {} browser instances'.format(Config['SELENIUM'].getint('num_browser_instances'))
        else:
            mode = 'http mode'
        logger.info('By using scrapemethod: {}'.format(mode))
        return

    # Let the games begin
    if Config['SCRAPING'].get('scrapemethod', 'http') == 'sel':
        # First of all, lets see how many keywords remain to scrape after parsing the cache
        if Config['GLOBAL'].getboolean('do_caching'):
            remaining = parse_all_cached_files(keywords, conn, url=Config['SELENIUM'].get('sel_scraper_base_url'))
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
        for i, kw in enumerate(keywords):
            r = scrape(kw, num_results_per_page=Config['SCRAPING'].getint('num_results_per_page', 10),
                       num_pages=Config['SCRAPING'].getint('num_pages', 1), scrapemethod='http')

            if r:
                cursor.execute('INSERT INTO serp_page (page_number, requested_at, num_results, num_results_for_kw_google, search_query) VALUES(?,?,?,?,?)',
                             (i, datetime.datetime.utcnow(), 0, 0, kw))
                serp_id = cursor.lastrowid
                for result in r:
                    results.append(r)
                    for result_set in ('results', 'ads_main', 'ads_aside'):
                        if result_set in result.keys():
                            for title, snippet, url, pos in result[result_set]:
                                cursor.execute('INSERT INTO link (title, snippet, url, domain, rank, serp_id) VALUES(?, ?, ?, ?, ?, ?)',
                                    (title, snippet, url.geturl(), url.netloc, pos, serp_id))
            cursor.close()
        if Config['GLOBAL'].get('print'):
            print_scrape_results_http(results, Config['GLOBAL'].getint('verbosity', 0))
        return conn
    else:
        raise InvalidConfigurationException('No such scrapemethod. Use "http" or "sel"')