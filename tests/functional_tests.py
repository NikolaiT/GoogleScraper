#!/usr/bin/python3
# -*- coding: utf-8 -*-

import unittest
from testing_utils import random_word, words
from GoogleScraper import Config
from GoogleScraper import scrape_with_config

all_search_engines = [se.strip() for se in Config['SCRAPING'].get('supported_search_engines').split(',')]

class GoogleScraperFunctionalTestCase(unittest.TestCase):

    # generic function for dynamic parsing
    def scrape_query(self, mode, search_engines='*', query='', random_query=False, sel_browser='Chrome'):

        if random_query:
            query = random_word()

        config = {
            'SCRAPING': {
                'use_own_ip': 'True',
                'keyword': query,
                'search_engines': search_engines,
                'num_pages_for_keyword': 1,
                'scrape_method': mode,
            },
            'GLOBAL': {
                'do_caching': 'False',
                'verbosity': 0
            },
            'SELENIUM': {
                'sel_browser': sel_browser
            }
        }
        search = scrape_with_config(config)

        if search_engines == '*':
            assert search.number_search_engines_used == len(all_search_engines)
        else:
            assert search.number_search_engines_used == len(search_engines.split(','))

        if search_engines == '*':
            assert len(search.used_search_engines.split(',')) == len(all_search_engines)
        else:
            assert len(search.used_search_engines.split(',')) == len(search_engines.split(','))

        assert search.number_proxies_used == 1
        assert search.number_search_queries == 1
        assert search.started_searching < search.stopped_searching

        return search

    ### test dynamic parsing for http mode

    def test_http_mode_all_engines(self):

        search = self.scrape_query('http', all_search_engines, random_query=True)


     ### test dynamic parsing for selenium with phantomsjs

    def test_selenium_phantomjs_all_engines(self):

        search = self.scrape_query('selenium', all_search_engines, sel_browser='phantoms', random_query=True)


    ### test dynamic parsing for selenium mode with Chrome

    def test_selenium_chrome_all_engines(self):

        search = self.scrape_query('selenium', all_search_engines, sel_browser='chrome', random_query=True)

    ### test proxies


    ### test no results

    def test_no_results(self):

        query = 'kajkld85049nmbBBAAAbvan857438VAVATRE6543vaVTYUYTRE73739klahbnvc'
        search_engines = 'google,duckduckgo,bing'
        search = self.scrape_query(mode='selenium', sel_browser='phantomjs', search_engines=search_engines, query=query)

        for serp in search.serps:
            assert serp.no_results is True, 'There should be no results, but got: {} {} for {}'.format(serp.no_results, len(serp.links), serp.search_engine_name)

if __name__ == '__main__':
    unittest.main(warnings='ignore')