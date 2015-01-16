#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import unittest
import requests
import re
import random
from GoogleScraper import Config
from GoogleScraper import scrape_with_config
from GoogleScraper.parsing import get_parser_by_search_engine
from collections import Counter

all_search_engines = [se.strip() for se in Config['SCRAPING'].get('supported_search_engines').split(',')]


def random_words(n=100, wordlength=range(10, 15)):
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


if os.path.exists('/usr/share/dict/words'):
    words = open('/usr/share/dict/words').read().splitlines()
else:
    words = random_words()


def random_word():
    return random.choice(words)


class GoogleScraperStaticTestCase(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    ### Test (very) static parsing for all search engines. The html files are saved in 'data/uncompressed_serp_pages/'
    # The sample files may become old and the SERP format may change over time. But this is the only
    # way to assert that a certain url or piece must be in the results.
    # If the SERP format changes, update accordingly (after all, this shouldn't happen that often).

    def get_parser_for_file(self, se, file):
        with open(file, 'r') as f:
            html = f.read()
            parser = get_parser_by_search_engine(se)
            parser = parser(html)

        return parser


    def assert_around_10_results_with_snippets(self, parser, delta=4):
        self.assertAlmostEqual(len([v['snippet'] for v in parser.search_results['results'] if v['snippet'] is not None]), 10, delta=delta)

    def assert_atleast90percent_of_items_are_not_None(self, parser, exclude_keys={'snippet'}):
        for result_type, res in parser.search_results.items():

            c = Counter()
            for item in res:
                for key, value in item.items():
                    if value is None:
                        c[key] += 1
            for key, value in c.items():
                if key not in exclude_keys:
                    assert (len(res) / int(value)) >= 9, key + ' has too many times a None value: ' + '{}/{}'.format(int(value), len(res))

    def test_parse_google(self):
        parser = self.get_parser_for_file('google', 'data/uncompressed_serp_pages/abrakadabra_google_de_ip.html')

        assert '232.000.000 Ergebnisse' in parser.num_results
        assert len(parser.search_results['results']) == 12, len(parser.search_results)
        assert all([v['visible_link'] for v in parser.search_results['results']])
        assert all([v['link'] for v in parser.search_results['results']])
        self.assert_around_10_results_with_snippets(parser)
        assert any(['www.extremnews.com' in v['visible_link'] for v in parser.search_results['results']]), 'Theres a link in this serp page with visible url "www.extremnews.com"'
        assert any(['er Noise-Rock-Band Sonic Youth und wurde' in v['snippet'] for v in parser.search_results['results'] if v['snippet']]), 'Specific string not found in snippet.'
        self.assert_atleast90percent_of_items_are_not_None(parser)

    def test_parse_bing(self):

        parser = self.get_parser_for_file('bing', 'data/uncompressed_serp_pages/hello_bing_de_ip.html')

        assert '16.900.000 results' == parser.num_results
        assert len(parser.search_results['results']) == 12, len(parser.search_results['results'])
        assert all([v['visible_link'] for v in parser.search_results['results']])
        assert all([v['link'] for v in parser.search_results['results']])
        self.assert_around_10_results_with_snippets(parser)
        assert any(['Hello Kitty Online Shop - Hello' in v['title'] for v in parser.search_results['results']]), 'Specific title not found in snippet.'
        self.assert_atleast90percent_of_items_are_not_None(parser)

    def test_parse_yahoo(self):
        
        parser = self.get_parser_for_file('yahoo', 'data/uncompressed_serp_pages/snow_yahoo_de_ip.html')

        assert '19,400,000 Ergebnisse' == parser.num_results
        assert len(parser.search_results['results']) >= 10, len(parser.search_results['results'])
        assert len([v['visible_link'] for v in parser.search_results['results'] if v['visible_link']]) == 10, 'Not 10 elements with a visible link in yahoo serp page'
        assert all([v['link'] for v in parser.search_results['results']])
        self.assert_around_10_results_with_snippets(parser)
        assert any([' crystalline water ice that falls from clouds. Since snow is composed of small ic' in v['snippet'] for v in parser.search_results['results'] if v['snippet']]), 'Specific string not found in snippet.'
        self.assert_atleast90percent_of_items_are_not_None(parser)


    def test_parse_yandex(self):
        parser = self.get_parser_for_file('yandex', 'data/uncompressed_serp_pages/game_yandex_de_ip.html')

        assert '2 029 580' in parser.num_results
        assert len(parser.search_results['results']) == 10, len(parser.search_results['results'])
        assert len([v['visible_link'] for v in parser.search_results['results'] if v['visible_link']]) == 10, 'Not 10 elements with a visible link in yandex serp page'
        assert all([v['link'] for v in parser.search_results['results']])
        self.assert_around_10_results_with_snippets(parser)
        assert any(['n play games to compile games statist' in v['snippet'] for v in parser.search_results['results'] if v['snippet']]), 'Specific string not found in snippet.'
        self.assert_atleast90percent_of_items_are_not_None(parser)

    def test_parse_baidu(self):

        parser = self.get_parser_for_file('baidu', 'data/uncompressed_serp_pages/number_baidu_de_ip.html')

        assert '100,000,000' in parser.num_results
        assert len(parser.search_results['results']) >= 6, len(parser.search_results['results'])
        assert all([v['link'] for v in parser.search_results['results']])
        self.assert_around_10_results_with_snippets(parser, delta=5)
        self.assert_atleast90percent_of_items_are_not_None(parser)

    def test_parse_duckduckgo(self):

        parser = self.get_parser_for_file('duckduckgo', 'data/uncompressed_serp_pages/mountain_duckduckgo_de_ip.html')

        # duckduckgo is a biatch

    def test_parse_ask(self):

        parser = self.get_parser_for_file('ask', 'data/uncompressed_serp_pages/fellow_ask_de_ip.html')

        assert len(parser.search_results['results']) >= 10, len(parser.search_results['results'])
        assert len([v['visible_link'] for v in parser.search_results['results'] if v['visible_link']]) == 10, 'Not 10 elements with a visible link in ask serp page'
        assert all([v['link'] for v in parser.search_results['results']])
        self.assert_around_10_results_with_snippets(parser)
        self.assert_atleast90percent_of_items_are_not_None(parser)


    ### test csv output
    
    def test_csv_output_static(self):
        """Test csv output.

        Test parsing 4 html pages with two queries and two pages per query and
        transforming the results to csv format.

        The cached file should be saved in 'data/csv_tests/', there should
        be as many files as search_engine * pages_for_keyword

        The keyword used in the static SERP pages MUST be 'some words'

        The filenames must be in the GoogleScraper cache format.
        """
        
        import csv
        from GoogleScraper.output_converter import csv_fieldnames

        number_search_engines = len(all_search_engines)
        csv_outfile = 'data/tmp/csv_test.csv'

        config = {
            'SCRAPING': {
                'keyword': 'some words',
                'search_engines': ','.join(all_search_engines),
                'num_pages_for_keyword': 2,
            },
            'GLOBAL': {
                'cachedir': 'data/csv_tests/',
                'do_caching': 'True',
                'verbosity': 1
            },
            'OUTPUT': {
                'output_filename': csv_outfile
            }
        }
        session = scrape_with_config(config)

        assert os.path.exists(csv_outfile), '{} does not exist'.format(csv_outfile)

        reader = csv.reader(csv_outfile)
        header = set(reader.next())
        assert header.issubset(set(csv_fieldnames)), 'Invalid CSV header: {}'.format(header)

        # the items that should always have a value:
        notnull = ('link', 'query', 'rank', 'domain', 'title', 'link_type', 'scrapemethod', 'page_number', 'search_engine_name')

        num_lines = 0
        for row in reader:
            # There should be around number_search_engines * 2 * 10 rows
            num_lines +=1

            for item in notnull:
                assert row[header[item]], '{} has a item that has no value: {}'.format(item, row)

        self.assertAlmostEqual(number_search_engines * 2 * 10, num_lines, delta=20)

    ### test json output

    def test_json_output_static(self):
        """Test json output.

        """

        import json

        number_search_engines = len(all_search_engines)
        json_outfile = 'data/tmp/json_test.json'

        config = {
            'SCRAPING': {
                'keyword': 'some words',
                'search_engines': ','.join(all_search_engines),
                'num_pages_for_keyword': 2,
            },
            'GLOBAL': {
                'cachedir': 'data/json_tests/',
                'do_caching': 'True',
                'verbosity': 0
            },
            'OUTPUT': {
                'output_filename': json_outfile
            }
        }
        session = scrape_with_config(config)

        assert os.path.exists(json_outfile), '{} does not exist'.format(json_outfile)

        results = json.load(open(json_outfile))

        self.assertAlmostEqual(number_search_engines * 2 * 10, sum([len(i['results']) for i in results]), delta=20)

        # the items that should always have a value:
        notnull = ('link', 'query', 'rank', 'domain', 'title', 'link_type', 'scrapemethod', 'page_number', 'search_engine_name')

        for key, value in results:

            if key == 'results':

                for result in results:

                    for item in notnull:
                        assert result[item], '{} has a item that has no value: {}'.format(item, result)


    ### test correct handling of SERP page that has no results for search query.

    def test_no_results_for_query_google(self):
        parser = self.get_parser_for_file('google', 'data/uncompressed_no_results_serp_pages/google.html')

        assert parser.effective_query == '"be dealt and be evaluated"', 'No effective query.'



class GoogleScraperFunctionalTestCase(unittest.TestCase):
    # generic function for dynamic parsing
    def scrape_query(self, mode, search_engines, query='', random_query=False, sel_browser='Chrome'):

        if random_query:
            query = random_word()

        config = {
            'SCRAPING': {
                'use_own_ip': 'True',
                'keyword': query,
                'search_engines': ','.join(search_engines),
                'num_pages_for_keyword': 1,
                'scrapemethod': mode,
            },
            'GLOBAL': {
                'do_caching': 'False',
                'verbosity': 0
            },
            'SELENIUM': {
                'sel_browser': sel_browser
            }
        }
        session = scrape_with_config(config)

        return session

    ### test dynamic parsing for http mode


    def test_http_mode_all_engines(self):

        session = self.scrape_query('http', all_search_engines, random_query=True)


     ### test dynamic parsing for selenium with phantomsjs

    def test_selenium_phantomjs_all_engines(self):

        session = self.scrape_query('selenium', all_search_engines, sel_browser='phantoms', random_query=True)


    ### test dynamic parsing for selenium mode with Chrome

    def test_selenium_chrome_all_engines(self):

        session = self.scrape_query('selenium', all_search_engines, sel_browser='chrome', random_query=True)

    ### test proxies

if __name__ == '__main__':

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GoogleScraperStaticTestCase)
    unittest.TextTestRunner().run(suite)

    # import sys
    # if len(sys.argv) > 1:
    #     if sys.argv[1] == 'fast':
    #
    #         suite = unittest.defaultTestLoader.loadTestsFromTestCase(GoogleScraperStaticTestCase)
    #
    #     else:
    #
    #         suite = unittest.defaultTestLoader.loadTestsFromTestCase(GoogleScraperFunctionalTestCase)
    #
    #     unittest.TextTestRunner().run(suite)
    #
    # else:
    #     unittest.main()
