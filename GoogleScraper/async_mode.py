import asyncio
import aiohttp
import datetime
from urllib.parse import urlencode
from GoogleScraper.parsing import get_parser_by_search_engine, parse_serp
from GoogleScraper.http_mode import get_GET_params_for_search_engine, headers
from GoogleScraper.scraping import get_base_search_url_by_search_engine
from GoogleScraper.utils import get_some_words
from GoogleScraper.output_converter import store_serp_result
import logging

logger = logging.getLogger(__name__)

class AsyncHttpScrape(object):
    """Scrape asynchronously using asyncio.
    
    Some search engines don't block after a certain amount of requests.
    Google surely does (after very few parallel requests).
    But with bing or example, it's now (18.01.2015) no problem to
    scrape 100 unique pages in 3 seconds.
    """

    def __init__(self, config, query='', page_number=1, search_engine='google', scrape_method='http-async'):
        """
        """
        self.config = config
        self.query = query
        self.page_number = page_number
        self.search_engine_name = search_engine
        self.search_type = 'normal'
        self.scrape_method = scrape_method
        self.requested_at = None
        self.requested_by = 'localhost'
        self.parser = get_parser_by_search_engine(self.search_engine_name)
        self.base_search_url = get_base_search_url_by_search_engine(self.config, self.search_engine_name, 'http')
        self.params = get_GET_params_for_search_engine(self.query, self.search_engine_name,
                                                       search_type=self.search_type)
        self.headers = headers
        self.status = 'successful'

    def __call__(self):

        @asyncio.coroutine
        def request():
            url = self.base_search_url + urlencode(self.params)

            response = yield from aiohttp.request('GET', url, params=self.params, headers=self.headers)

            if response.status != 200:
                self.status = 'not successful: ' + str(response.status)

            self.requested_at = datetime.datetime.utcnow()

            logger.info('[+] {} requested keyword \'{}\' on {}. Response status: {}'.format(
                self.requested_by,
                self.query,
                self.search_engine_name,
                response.status))

            logger.debug('[i] URL: {} HEADERS: {}'.format(
                url,
                self.headers))

            if response.status == 200:
                body = yield from response.read_and_close(decode=False)
                self.parser = self.parser(config=self.config, html=body)
                return self

            return None

        return request


class AsyncScrapeScheduler(object):
    """
    Processes the single requests in an asynchronous way.
    """

    def __init__(self, config, scrape_jobs, cache_manager=None, session=None, scraper_search=None, db_lock=None):
        self.cache_manager = cache_manager
        self.config = config
        self.max_concurrent_requests = self.config.get('max_concurrent_requests')
        self.scrape_jobs = scrape_jobs
        self.session = session
        self.scraper_search = scraper_search
        self.db_lock = db_lock

        self.loop = asyncio.get_event_loop()
        self.requests = []
        self.results = []

    def get_requests(self):

        self.requests = []
        request_number = 0

        while True:
            request_number += 1
            try:
                job = self.scrape_jobs.pop()
            except IndexError:
                break

            if job:
                self.requests.append(AsyncHttpScrape(self.config, **job))

            if request_number >= self.max_concurrent_requests:
                break

    def run(self):

        while True:
            self.get_requests()

            if not self.requests:
                break

            self.results = self.loop.run_until_complete(asyncio.wait([r()() for r in self.requests]))

            for task in self.results[0]:
                scrape = task.result()

                if scrape:

                    if self.cache_manager:
                        self.cache_manager.cache_results(scrape.parser, scrape.query, scrape.search_engine_name, scrape.scrape_method,
                                      scrape.page_number)

                    if scrape.parser:
                        serp = parse_serp(self.config, parser=scrape.parser, scraper=scrape, query=scrape.query)

                        if self.scraper_search:
                            self.scraper_search.serps.append(serp)

                        if self.session:
                            self.session.add(serp)
                            self.session.commit()

                        store_serp_result(serp, self.config)


if __name__ == '__main__':
    from GoogleScraper.config import get_config
    from GoogleScraper.scrape_jobs import default_scrape_jobs_for_keywords

    some_words = get_some_words(n=1)

    cfg = get_config()
    scrape_jobs = list(default_scrape_jobs_for_keywords(some_words, ['bing'], 'http-async', 1))

    manager = AsyncScrapeScheduler(cfg, scrape_jobs)
    manager.run()

