# -*- coding: utf-8 -*-


import queue
import threading
import datetime
import os
import logging
from GoogleScraper.utils import chunk_it
from GoogleScraper.database import ScraperSearch, SERP, Link, get_session
from GoogleScraper.proxies import parse_proxy_file, get_proxies_from_mysql_db
from GoogleScraper.scraping import SelScrape, HttpScrape
from GoogleScraper.caching import maybe_clean_cache, fix_broken_cache_names, _caching_is_one_to_one, parse_all_cached_files, clean_cachefiles
from GoogleScraper.config import InvalidConfigurationException, parse_cmd_args, Config
from GoogleScraper.log import out
import GoogleScraper.config

logger = logging.getLogger('GoogleScraper')

def scrape_with_config(config, **kwargs):
    """Runs GoogleScraper with the dict in config.

    Args:
        config: A configuration dictionary that updates the global configuration.
        kwargs: Further options that cannot be handled by the configuration.

    Returns:
        The result of the main() function. May be sqlalchemy session.
    """
    if not isinstance(config, dict):
        raise ValueError('The config parameter needs to be a configuration dictionary. Given parameter has type: {}'.format(type(config)))

    GoogleScraper.config.update_config(config)
    return main(return_results=True, parse_cmd_line=False, **kwargs)

def assign_keywords_to_scrapers(all_keywords):
    """Scrapers are threads or asynchronous objects.

    Splitting the keywords equally on the workers is crucial
    for maximal performance.

    Args:
        all_keywords: All keywords to scrape

    Returns:
        A list of list. The elements of the inner list should be assigned to individual scraper instances, e. g. threads.
    """
    mode = Config['SCRAPING'].get('scrapemethod')

    num_workers = Config['SCRAPING'].getint('num_workers', 1)

    if len(all_keywords) > num_workers:
        kwgroups = chunk_it(all_keywords, num_workers)
    else:
        # thats a little special there :)
        kwgroups = [[kw, ] for kw in all_keywords]

    return kwgroups


# taken from https://github.com/scrapy/utils/console.py
def start_python_console(namespace=None, noipython=False, banner=''):
    """Start Python console bound to the given namespace. If IPython is
    available, an IPython console will be started instead, unless `noipython`
    is True. Also, tab completion will be used on Unix systems.
    """
    if namespace is None:
        namespace = {}

    try:
        try: # use IPython if available
            if noipython:
                raise ImportError()

            try:
                from IPython.terminal.embed import InteractiveShellEmbed
                from IPython.terminal.ipapp import load_default_config
            except ImportError:
                from IPython.frontend.terminal.embed import InteractiveShellEmbed
                from IPython.frontend.terminal.ipapp import load_default_config

            config = load_default_config()
            shell = InteractiveShellEmbed(
                banner1=banner, user_ns=namespace, config=config)
            shell()
        except ImportError:
            import code
            try: # readline module is only available on unix systems
                import readline
            except ImportError:
                pass
            else:
                import rlcompleter
                readline.parse_and_bind("tab:complete")
            code.interact(banner=banner, local=namespace)
    except SystemExit: # raised when using exit() in python code.interact
        pass


class ShowProgressQueue(threading.Thread):
    """Prints the number of keywords scraped already to show the user the progress of the scraping process.

    In order to achieve this, we need to update the status whenever a new keyword is scraped.
    """
    def __init__(self, queue, num_keywords):
        """Create a ShowProgressQueue thread instance.

        Args:
            queue: A queue.Queue instance to share among the worker threads.
            num_keywords: The number of total keywords that need to be scraped.

        """
        super().__init__()
        self.queue = queue
        self.num_keywords = num_keywords
        self.num_already_processed = 0

    def run(self):
        while self.num_already_processed < self.num_keywords:
            e = self.queue.get()
            self.num_already_processed += 1
            print('{}/{} keywords processed.'.format(self.num_already_processed, self.num_keywords), end='\r')
            self.queue.task_done()


def main(return_results=False, parse_cmd_line=True):
    """Runs the GoogleScraper application as determined by the various configuration points.

    The main() function encompasses the core functionality of GoogleScraper. But it
    shouldn't be the main() functions job to check the validity of the provided
    configuration.

    Args:
        return_results: When GoogleScrape is used from within another program, don't print results to stdout,
                        store them in a database instead.
    Returns:
        A database session to the results when return_results is True
    """
    if parse_cmd_line:
        parse_cmd_args()

    if Config['GLOBAL'].getboolean('view_config'):
        from GoogleScraper.config import CONFIG_FILE
        print(open(CONFIG_FILE).read())
        return

    if Config['GLOBAL'].getboolean('version'):
        from GoogleScraper.version import __version__
        print(__version__)
        return

    maybe_clean_cache()

    kwfile = Config['SCRAPING'].get('keyword_file')
    keyword = Config['SCRAPING'].get('keyword')
    keywords = {keyword for keyword in set(Config['SCRAPING'].get('keywords', []).split('\n')) if keyword}
    proxy_file = Config['GLOBAL'].get('proxy_file', '')
    proxy_db = Config['GLOBAL'].get('mysql_proxy_db', '')

    if Config['GLOBAL'].getboolean('shell', False):
        namespace = {}
        Session = get_session(scoped=False, create=False)
        namespace['session'] = Session()
        namespace['ScraperSearch'] = ScraperSearch
        namespace['SERP'] = SERP
        namespace['Link'] = Link
        print('Available objects:')
        print('session - A sqlalchemy session of the results database')
        print('ScraperSearch - Search/Scrape job instances')
        print('SERP - A search engine results page')
        print('Link - A single link belonging to a SERP')
        start_python_console(namespace)
        return

    if not (keyword or keywords) and not kwfile:
        logger.error('No keywords to scrape for. Please provide either an keyword file (Option: --keyword-file) or specify and keyword with --keyword.')
        return

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

    search_engines = list({search_engine for search_engine in Config['SCRAPING'].get('search_engines', 'google').split(',') if search_engine})
    assert search_engines, 'No search engine specified'

    if Config['GLOBAL'].getboolean('clean_cache_files', False):
        clean_cachefiles()
        return

    if Config['GLOBAL'].getboolean('check_oto', False):
        _caching_is_one_to_one(keyword)

    if Config['SCRAPING'].getint('num_results_per_page') > 100:
        raise InvalidConfigurationException('Not more that 100 results per page available for searches.')

    proxies = []

    if proxy_db:
        proxies = get_proxies_from_mysql_db(proxy_db)
    elif proxy_file:
        proxies = parse_proxy_file(proxy_file)

    if Config['SCRAPING'].getboolean('use_own_ip'):
        proxies.append(None)
        
    if not proxies:
        raise InvalidConfigurationException("No proxies available and using own IP is prohibited by configuration. Turning down.")

    valid_search_types = ('normal', 'video', 'news', 'image')
    if Config['SCRAPING'].get('search_type') not in valid_search_types:
        InvalidConfigurationException('Invalid search type! Select one of {}'.format(repr(valid_search_types)))

    if Config['GLOBAL'].getboolean('simulate', False):
        print('*' * 60 + 'SIMULATION' + '*' * 60)
        logger.info('If GoogleScraper would have been run without the --simulate flag, it would have:')
        logger.info('Scraped for {} keywords, with {} results a page, in total {} pages for each keyword'.format(
            len(keywords), Config['SCRAPING'].getint('num_results_per_page', 0), Config['SCRAPING'].getint('num_pages_for_keyword')))
        if None in proxies:
            logger.info('Also using own ip address to scrape.')
        else:
            logger.info('Not scraping with own ip address.')
        logger.info('Used {} unique ip addresses in total'.format(len(proxies)))
        if proxies:
            logger.info('The following proxies are used: \n\t\t{}'.format('\n\t\t'.join([proxy.host + ':' + proxy.port for proxy in proxies if proxy])))

        logger.info('By using {} mode with {} worker instances'.format(Config['SCRAPING'].get('scrapemethod'), Config['SCRAPING'].getint('num_workers')))
        return

    # get a scoped sqlalchemy session
    Session = get_session(scoped=False, create=True)
    session = Session()

    scraper_search = ScraperSearch(
        number_search_engines_used=1,
        number_proxies_used=len(proxies),
        number_search_queries=len(keywords),
        started_searching=datetime.datetime.utcnow()
    )

    # First of all, lets see how many keywords remain to scrape after parsing the cache
    if Config['GLOBAL'].getboolean('do_caching'):
        remaining = parse_all_cached_files(keywords, search_engines, session, scraper_search)
    else:
        remaining = keywords

    # remove duplicates and empty keywords
    remaining = [keyword for keyword in set(remaining) if keyword]

    kwgroups = assign_keywords_to_scrapers(remaining)

    # Create a lock to synchronize database access in the sqlalchemy session
    db_lock = threading.Lock()

    # create a lock to cache results
    cache_lock = threading.Lock()

    # final check before going into the loop
    num_workers_to_allocate = len(kwgroups) * len(search_engines) > Config['SCRAPING'].getint('maximum_workers')
    if (len(kwgroups) * len(search_engines)) > Config['SCRAPING'].getint('maximum_workers'):
        logger.error('Too many workers: {} , might crash the app'.format(num_workers_to_allocate))


    out('Going to scrape {num_keywords} keywords with {num_proxies} proxies by using {num_threads} threads.'.format(
        num_keywords=len(remaining),
        num_proxies=len(proxies),
        num_threads=Config['SCRAPING'].getint('num_workers', 1)
    ), lvl=1)

    # Show the progress of the scraping
    q = None
    if Config['GLOBAL'].getint('verbosity', 1) == 1:
        q = queue.Queue()
        progress_thread = ShowProgressQueue(q, len(remaining))
        progress_thread.start()

    # Let the games begin
    if Config['SCRAPING'].get('scrapemethod') in ('selenium', 'http'):
        # A lock to prevent multiple threads from solving captcha.
        captcha_lock = threading.Lock()

        # Distribute the proxies evenly on the keywords to search for
        scrapejobs = []

        for k, search_engine in enumerate(search_engines):
            for i, keyword_group in enumerate(kwgroups):
                
                proxy_to_use = proxies[i % len(proxies)]
                
                if Config['SCRAPING'].get('scrapemethod', 'http') == 'selenium':
                    scrapejobs.append(
                        SelScrape(
                            search_engine=search_engine,
                            session=session,
                            keywords=keyword_group,
                            db_lock=db_lock,
                            cache_lock=cache_lock,
                            scraper_search=scraper_search,
                            captcha_lock=captcha_lock,
                            browser_num=i,
                            proxy=proxy_to_use,
                            progress_queue=q,
                        )
                    )
                elif Config['SCRAPING'].get('scrapemethod') == 'http':
                    scrapejobs.append(
                        HttpScrape(
                            search_engine=search_engine,
                            keywords=keyword_group,
                            session=session,
                            scraper_search=scraper_search,
                            cache_lock=cache_lock,
                            db_lock=db_lock,
                            proxy=proxy_to_use,
                            progress_queue=q,
                        )
                    )

        for t in scrapejobs:
            t.start()

        for t in scrapejobs:
            t.join()

    elif Config['SCRAPING'].get('scrapemethod') == 'http-async':
        raise NotImplemented('soon my dear friends :)')

    else:
        raise InvalidConfigurationException('No such scrapemethod. Use "http" or "sel"')

    scraper_search.stopped_searching = datetime.datetime.utcnow()
    session.add(scraper_search)
    session.commit()

    if Config['GLOBAL'].getint('verbosity', 1) == 1:
        progress_thread.join()

    if return_results:
        return session
