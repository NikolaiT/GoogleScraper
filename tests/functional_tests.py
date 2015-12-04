#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
These functional tests cannot cover the whole functionality of GoogleScraper.

But it is tried to cover at least the most common use cases with GoogleScraper, such that
a basic functionality is proved to be correct. The functional tests are run on git hook pre-push time,
so it is enforced that only minimally stable versions are online.

When testing single functions:

python -m pytest tests/functional_tests.py::GoogleScraperFunctionalTestCase::test_google_with_phantomjs_and_json_output
"""

import csv
import json
import tempfile
import os
import unittest
from GoogleScraper import scrape_with_config
from GoogleScraper.config import get_config

base_config = get_config()
all_search_engines = base_config['supported_search_engines']


def is_string_and_longer_than(s, n):
    return isinstance(s, str) and len(s) > n


def predicate_true_at_least_n_times(pred, collection, n, key):
    """
    Ensures that the predicate is at least n times true for
    items in a collection with the key.
    """
    if hasattr(collection[0], key):
        assert len([getattr(v, key) for v in collection if pred(getattr(v, key))]) > n
    elif key in collection[0]:
        assert len([v[key] for v in collection if pred(v[key])]) > n

class GoogleScraperFunctionalTestCase(unittest.TestCase):

    def test_google_with_phantomjs_and_json_output(self):
        """
        Very common use case:

        Ensures that we can scrape three continuous sites with Google using
        phantomjs and save the results to a JSON file.
        """
        results_file = os.path.join(tempfile.gettempdir(), 'results.json')
        if os.path.exists(results_file):
            os.remove(results_file)

        config = {
            'keyword': 'apple tree',
            'search_engines': ['Google'],
            'num_results_per_page': 10,
            'num_pages_for_keyword': 3,
            'scrape_method': 'selenium',
            'sel_browser': 'phantomjs',
            'output_filename': results_file,
            'do_caching': 'False',
        }

        search = scrape_with_config(config)

        self.assertLess(search.started_searching, search.stopped_searching)
        self.assertEqual(search.number_proxies_used, 1)
        self.assertEqual(search.number_search_engines_used, 1)
        self.assertEqual(search.number_search_queries, 1)
        self.assertEqual(len(search.serps), 3)

        self.assertEqual(search.serps[0].page_number, 1)
        self.assertEqual(search.serps[1].page_number, 2)
        self.assertEqual(search.serps[2].page_number, 3)

        for serp in search.serps:
            self.assertEqual(serp.status, 'successful')
            self.assertEqual(serp.search_engine_name.lower(), 'google')
            self.assertEqual(serp.scrape_method, 'selenium')
            self.assertTrue(serp.num_results_for_query)
            self.assertAlmostEqual(serp.num_results, 10, delta=2)
            self.assertFalse(is_string_and_longer_than(serp.effective_query, 1), msg=serp.effective_query)
            self.assertEqual(serp.no_results, False)

            self.assertEqual(serp.num_results, len(serp.links))

            for j, link in enumerate(serp.links):
                if link.link_type == 'results':
                    self.assertTrue(is_string_and_longer_than(link.title, 3))
                    self.assertTrue(is_string_and_longer_than(link.snippet, 3))

                self.assertTrue(is_string_and_longer_than(link.link, 10))
                self.assertTrue(isinstance(link.rank, int))


        # test that the json output is correct
        self.assertTrue(os.path.isfile(results_file))

        with open(results_file, 'rt') as file:
            obj = json.load(file)

            # check the same stuff again for the json file
            for i, page in enumerate(obj):
                self.assertEqual(page['effective_query'], '')
                self.assertEqual(page['no_results'], 'False')
                self.assertEqual(page['num_results'], str(len(page['results'])))
                self.assertTrue(is_string_and_longer_than(page['num_results_for_query'], 5))
                self.assertEqual(page['page_number'], str(i+1))
                self.assertEqual(page['query'], 'apple tree')
                # todo: Test requested_at
                self.assertEqual(page['requested_by'], 'localhost')

                for j, result in enumerate(page['results']):
                    if result['link_type'] == 'results':
                        self.assertTrue(is_string_and_longer_than(result['title'], 3))
                        self.assertTrue(is_string_and_longer_than(result['snippet'], 3))

                    self.assertTrue(is_string_and_longer_than(result['link'], 10))
                    self.assertTrue(isinstance(int(result['rank']), int))



    def test_http_mode_google_csv_output(self):

        results_file = os.path.join(tempfile.gettempdir(), 'results.csv')
        if os.path.exists(results_file):
            os.remove(results_file)

        config = {
            'keyword': 'banana',
            'search_engines': ['Google'],
            'num_results_per_page': 10,
            'num_pages_for_keyword': 2,
            'scrape_method': 'http',
            'output_filename': results_file,
            'do_caching': 'False',
        }

        search = scrape_with_config(config)

        self.assertLess(search.started_searching, search.stopped_searching)
        self.assertEqual(search.number_proxies_used, 1)
        self.assertEqual(search.number_search_engines_used, 1)
        self.assertEqual(search.number_search_queries, 1)
        self.assertEqual(len(search.serps), 2)

        self.assertEqual(search.serps[0].page_number, 1)
        self.assertEqual(search.serps[1].page_number, 2)

        for serp in search.serps:
            self.assertEqual(serp.query, 'banana')
            self.assertEqual(serp.status, 'successful')
            self.assertEqual(serp.search_engine_name.lower(), 'google')
            self.assertEqual(serp.scrape_method, 'http')
            self.assertTrue(serp.num_results_for_query)
            self.assertAlmostEqual(serp.num_results, 10, delta=2)
            self.assertFalse(is_string_and_longer_than(serp.effective_query, 1), msg=serp.effective_query)
            self.assertEqual(serp.no_results, False)

            self.assertEqual(serp.num_results, len(serp.links))

            predicate_true_at_least_n_times(lambda v: is_string_and_longer_than(v, 3),
                                                    serp.links, 7, 'snippet')
            for link in serp.links:
                if link.link_type == 'results':
                    self.assertTrue(is_string_and_longer_than(link.title, 3))

                self.assertTrue(is_string_and_longer_than(link.link, 10))
                self.assertTrue(isinstance(link.rank, int))

        # test that the csv output is correct
        self.assertTrue(os.path.isfile(results_file))

        with open(results_file, 'rt') as file:
            reader = csv.DictReader(file, delimiter=',')

            rows = [row for row in reader]

            self.assertAlmostEqual(20, len(rows), delta=3)

            for row in rows:
                self.assertEqual(row['query'], 'banana')
                self.assertTrue(is_string_and_longer_than(row['requested_at'], 5))
                self.assertTrue(int(row['num_results']))
                self.assertEqual(row['scrape_method'], 'http')
                self.assertEqual(row['requested_by'], 'localhost')
                self.assertEqual(row['search_engine_name'], 'google')
                self.assertIn(int(row['page_number']), [1,2])
                self.assertEqual(row['status'], 'successful')
                self.assertTrue(is_string_and_longer_than(row['num_results_for_query'], 3))
                self.assertTrue(row['no_results'] == 'False')
                self.assertTrue(row['effective_query'] == '')

                if row['link_type'] == 'results':
                    self.assertTrue(is_string_and_longer_than(row['title'], 3))
                    self.assertTrue(is_string_and_longer_than(row['snippet'], 3))
                    self.assertTrue(is_string_and_longer_than(row['domain'], 5))
                    self.assertTrue(is_string_and_longer_than(row['visible_link'], 5))

                self.assertTrue(is_string_and_longer_than(row['link'], 10))
                self.assertTrue(row['rank'].isdigit())

            # ensure that at least 90% of all entries have a string as snippet
            predicate_true_at_least_n_times(lambda v: is_string_and_longer_than(v, 3), rows, int(0.8*len(rows)), 'snippet')


    def test_asynchronous_mode_bing_and_yandex(self):
        results_file = os.path.join(tempfile.gettempdir(), 'async_results.json')
        config = {
            'keyword': 'banana',
            'search_engines': ['Google'],
            'num_results_per_page': 10,
            'num_pages_for_keyword': 2,
            'scrape_method': 'http',
            'output_filename': results_file,
            'do_caching': 'False',
        }

        search = scrape_with_config(config)



if __name__ == '__main__':
    unittest.main(warnings='ignore')