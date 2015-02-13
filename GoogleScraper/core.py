# -*- coding: utf-8 -*-

import threading
import datetime
import sys
import hashlib
import os
import logging
import queue
from GoogleScraper.commandline import get_command_line
from GoogleScraper.database import ScraperSearch, SERP, Link, get_session, fixtures
from GoogleScraper.proxies import parse_proxy_file, get_proxies_from_mysql_db, add_proxies_to_db
from GoogleScraper.caching import fix_broken_cache_names, _caching_is_one_to_one, parse_all_cached_files, clean_cachefiles
from GoogleScraper.config import InvalidConfigurationException, parse_cmd_args, Config, update_config_with_file
from GoogleScraper.log import out, raise_or_log
from GoogleScraper.scrape_jobs import default_scrape_jobs_for_keywords
from GoogleScraper.scraping import ScrapeWorkerFactory, GoogleSearchError
from GoogleScraper.output_converter import init_outfile
from GoogleScraper.async_mode import AsyncScrapeScheduler
import GoogleScraper.config

logger = logging.getLogger('GoogleScraper')


def id_for_keywords(keywords):
    """Determine a unique id for the keywords.

    Helps to continue the last scrape and to identify the last
    scrape object.

    Args:
        keywords: All the keywords in the scrape process
    Returns:
        The unique md5 string of all keywords.
    """

    m = hashlib.md5()
    for kw in keywords:
        m.update(kw.encode())
    return m.hexdigest()


def scrape_with_config(config, **kwargs):
    """Runs GoogleScraper with the dict in config.

    Args:
        config: A configuration dictionary that updates the global configuration.
        kwargs: Further options that cannot be handled by the configuration.

    Returns:
        The result of the main() function. Is a scraper search object.
        In case you want to access the session, import it like this:
        ```from GoogleScraper database import session```
    """
    if not isinstance(config, dict):
        raise ValueError('The config parameter needs to be a configuration dictionary. Given parameter has type: {}'.format(type(config)))

    # make exceptions from GoogleScraper catchable.
    config['SCRAPING'].update({'raise_exceptions_while_scraping': True})

    GoogleScraper.config.update_config(config)
    return main(return_results=True, parse_cmd_line=False, **kwargs)


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
        self.verbosity = Config['GLOBAL'].getint('verbosity', 1)
        self.progress_fmt = '\033[92m{}/{} keywords processed.\033[0m'

    def run(self):
        while self.num_already_processed < self.num_keywords:
            e = self.queue.get()

            if e == 'done':
                break

            self.num_already_processed += 1

            if self.verbosity == 1:
                print(self.progress_fmt.format(self.num_already_processed, self.num_keywords), end='\r')
            elif self.verbosity == 2 and self.num_already_processed % 5 == 0:
                print(self.progress_fmt.format(self.num_already_processed, self.num_keywords))

            self.queue.task_done()


def main(return_results=False, parse_cmd_line=True):
    """Runs the GoogleScraper application as determined by the various configuration points.

    The main() function encompasses the core functionality of GoogleScraper. But it
    shouldn't be the main() functions job to check the validity of the provided
    configuration.

    Args:
        return_results: When GoogleScrape is used from within another program, don't print results to stdout,
                        store them in a database instead.
        parse_cmd_line: Whether to get options from the command line or not.
    Returns:
        A database session to the results when return_results is True
    """
    if parse_cmd_line:
        parse_cmd_args()

    # If the configuration file to use is explicitly specified, update the current configuration
    # with it.
    if Config['GLOBAL'].get('config_file', None):
        update_config_with_file(Config['GLOBAL'].get('config_file', None))

    if Config['GLOBAL'].getboolean('view_config'):
        from GoogleScraper.config import CONFIG_FILE
        print(open(CONFIG_FILE).read())
        return

    if Config['GLOBAL'].getboolean('version'):
        from GoogleScraper.version import __version__
        print(__version__)
        return

    if Config['GLOBAL'].getboolean('clean', False):
        try:
            os.remove('google_scraper.db')
            if sys.platform == 'linux':
                os.system('rm {}/*'.format(Config['GLOBAL'].get('cachedir')))
        except:
            pass
        return

    init_outfile(force_reload=True)

    kwfile = Config['SCRAPING'].get('keyword_file', '')
    if kwfile:
        kwfile = os.path.abspath(kwfile)

    keyword = Config['SCRAPING'].get('keyword')
    keywords = {keyword for keyword in set(Config['SCRAPING'].get('keywords', []).split('\n')) if keyword}
    proxy_file = Config['GLOBAL'].get('proxy_file', '')
    proxy_db = Config['GLOBAL'].get('mysql_proxy_db', '')

    se = Config['SCRAPING'].get('search_engines', 'google')
    if se.strip() == '*':
        se = Config['SCRAPING'].get('supported_search_engines', 'google')

    search_engines = list({search_engine.strip() for search_engine in se.split(',') if search_engine.strip()})
    assert search_engines, 'No search engine specified'
    num_search_engines = len(search_engines)
    num_workers = Config['SCRAPING'].getint('num_workers')
    scrape_method = Config['SCRAPING'].get('scrape_method')
    pages = Config['SCRAPING'].getint('num_pages_for_keyword', 1)
    method = Config['SCRAPING'].get('scrape_method', 'http')

    if Config['GLOBAL'].getboolean('shell', False):
        namespace = {}
        Session = get_session(scoped=False)
        namespace['session'] = Session()
        namespace['ScraperSearch'] = ScraperSearch
        namespace['SERP'] = SERP
        namespace['Link'] = Link
        namespace['Proxy'] = GoogleScraper.database.Proxy
        print('Available objects:')
        print('session - A sqlalchemy session of the results database')
        print('ScraperSearch - Search/Scrape job instances')
        print('SERP - A search engine results page')
        print('Link - A single link belonging to a SERP')
        print('Proxy - Proxies stored for scraping projects.')
        start_python_console(namespace)
        return

    if not (keyword or keywords) and not kwfile:
        raise_or_log('No keywords to scrape for. Please provide either an keyword file (Option: --keyword-file) or specify and keyword with --keyword.')
        # Just print the help.
        get_command_line(True)
        return

    if Config['GLOBAL'].getboolean('fix_cache_names'):
        fix_broken_cache_names()
        logger.info('renaming done. restart for normal use.')
        return

    keywords = [keyword, ] if keyword else keywords
    scrape_jobs = {}
    if kwfile:
        if not os.path.exists(kwfile):
            raise_or_log('The keyword file {} does not exist.'.format(kwfile), exception_obj=InvalidConfigurationException)
        else:
            if kwfile.endswith('.py'):
                # we need to import the variable "scrape_jobs" from the module.
                sys.path.append(os.path.dirname(kwfile))
                try:
                    modname = os.path.split(kwfile)[-1].rstrip('.py')
                    scrape_jobs = getattr(__import__(modname, fromlist=['scrape_jobs']), 'scrape_jobs')
                except ImportError as e:
                    logger.warning(e)
            else:
                # Clean the keywords of duplicates right in the beginning
                keywords = set([line.strip() for line in open(kwfile, 'r').read().split('\n') if line.strip()])

    if not scrape_jobs:
        scrape_jobs = default_scrape_jobs_for_keywords(keywords, search_engines, scrape_method, pages)

    scrape_jobs = list(scrape_jobs)

    if Config['GLOBAL'].getboolean('clean_cache_files', False):
        clean_cachefiles()
        return

    if Config['GLOBAL'].getboolean('check_oto', False):
        _caching_is_one_to_one(keyword)

    if Config['SCRAPING'].getint('num_results_per_page') > 100:
        raise_or_log('Not more that 100 results per page available for searches.', exception_obj=InvalidConfigurationException)

    proxies = []

    if proxy_db:
        proxies = get_proxies_from_mysql_db(proxy_db)
    elif proxy_file:
        proxies = parse_proxy_file(proxy_file)

    if Config['SCRAPING'].getboolean('use_own_ip'):
        proxies.append(None)
        
    if not proxies:
        raise InvalidConfigurationException('No proxies available and using own IP is prohibited by configuration. Turning down.')

    valid_search_types = ('normal', 'video', 'news', 'image')
    if Config['SCRAPING'].get('search_type') not in valid_search_types:
        raise_or_log('Invalid search type! Select one of {}'.format(repr(valid_search_types)), exception_obj=InvalidConfigurationException)

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

        logger.info('By using {} mode with {} worker instances'.format(Config['SCRAPING'].get('scrape_method'), Config['SCRAPING'].getint('num_workers')))
        return

    # get a scoped sqlalchemy session
    Session = get_session(scoped=False)
    session = Session()
    
    # add fixtures
    fixtures(session)

    # add proxies to the database
    add_proxies_to_db(proxies, session)

    # ask the user to continue the last scrape. We detect a continuation of a
    # previously established scrape, if the keyword-file is the same and unmodified since
    # the beginning of the last scrape.
    scraper_search = None
    if kwfile and Config['GLOBAL'].getboolean('continue_last_scrape', False):
        searches = session.query(ScraperSearch).\
            filter(ScraperSearch.keyword_file == kwfile).\
            order_by(ScraperSearch.started_searching).\
            all()

        if searches:
            last_search = searches[-1]
            last_modified = datetime.datetime.utcfromtimestamp(os.path.getmtime(last_search.keyword_file))

            # if the last modification is older then the starting of the search
            if last_modified < last_search.started_searching:
                scraper_search = last_search
                logger.info('Continuing last scrape.')

    if not scraper_search:
        scraper_search = ScraperSearch(
            keyword_file=os.path.abspath(kwfile),
            number_search_engines_used=num_search_engines,
            number_proxies_used=len(proxies),
            number_search_queries=len(keywords),
            started_searching=datetime.datetime.utcnow(),
            used_search_engines=','.join(search_engines)
        )

    # First of all, lets see how many requests remain to issue after searching the cache.
    if Config['GLOBAL'].getboolean('do_caching'):
        scrape_jobs = parse_all_cached_files(scrape_jobs, session, scraper_search)

    if scrape_jobs:

        # Create a lock to synchronize database access in the sqlalchemy session
        db_lock = threading.Lock()

        # create a lock to cache results
        cache_lock = threading.Lock()

        # A lock to prevent multiple threads from solving captcha, used in selenium instances.
        captcha_lock = threading.Lock()

        out('Going to scrape {num_keywords} keywords with {num_proxies} proxies by using {num_threads} threads.'.format(
            num_keywords=len(list(scrape_jobs)),
            num_proxies=len(proxies),
            num_threads=num_search_engines
        ), lvl=1)

        # Let the games begin
        if method in ('selenium', 'http'):

            # Show the progress of the scraping
            q = queue.Queue()
            progress_thread = ShowProgressQueue(q, len(scrape_jobs))
            progress_thread.start()

            workers = queue.Queue()
            num_worker = 0
            for search_engine in search_engines:

                for proxy in proxies:

                    for worker in range(num_workers):
                        num_worker += 1
                        workers.put(
                            ScrapeWorkerFactory(
                                mode=method,
                                proxy=proxy,
                                search_engine=search_engine,
                                session=session,
                                db_lock=db_lock,
                                cache_lock=cache_lock,
                                scraper_search=scraper_search,
                                captcha_lock=captcha_lock,
                                progress_queue=q,
                                browser_num=num_worker
                            )
                        )

            for job in scrape_jobs:

                while True:
                    worker = workers.get()
                    workers.put(worker)
                    if worker.is_suitabe(job):
                        worker.add_job(job)
                        break

            threads = []

            while not workers.empty():
                worker = workers.get()
                thread = worker.get_worker()
                if thread:
                    threads.append(thread)

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            # after threads are done, stop the progress queue.
            q.put('done')

        elif method == 'http-async':


            scheduler = AsyncScrapeScheduler(scrape_jobs, session=session, scraper_search=scraper_search,
                                             db_lock=db_lock)
            scheduler.run()

        else:
            raise InvalidConfigurationException('No such scrape_method {}'.format(Config['SCRAPING'].get('scrape_method')))


        if method in ('selenium', 'http'):
            progress_thread.join()

    # in the end, close the json file.
    from GoogleScraper.output_converter import outfile, output_format

    if output_format == 'json':
        outfile.end()

    scraper_search.stopped_searching = datetime.datetime.utcnow()
    session.add(scraper_search)
    session.commit()

    if return_results:
        return scraper_search
