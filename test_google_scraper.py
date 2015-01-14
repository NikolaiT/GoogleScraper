#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from GoogleScraper.parsing import get_parser_by_search_engine


class GoogleScraperTestCase(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    ### Test static parsing for all search engines. The html files are saved in u_sample_serp_path

    def get_parser_for_file(self, se, file):
        with open(file, 'r') as f:
            html = f.read()
            parser = get_parser_by_search_engine(se)
            parser = parser(html)

        return parser

    def test_parse_google(self):
        parser = self.get_parser_for_file('google', 'data/uncompressed_serp_pages/abrakadabra_google_de_ip.html')

        assert '232.000.000 Ergebnisse' in parser.search_results['num_results']
        assert len(parser.search_results['results']) == 12, len(parser.search_results)
        assert all([v['visible_link'] for v in parser.search_results['results']])
        assert all([v['link'] for v in parser.search_results['results']])
        self.assertAlmostEqual(len([v['snippet'] for v in parser.search_results['results'] if v['snippet'] is not None]), 10, delta=4)

    def test_parse_bing(self):

        parser = self.get_parser_for_file('bing', 'data/uncompressed_serp_pages/hello_bing_de_ip.html')

        assert '16.900.000 results' == parser.search_results['num_results']
        assert len(parser.search_results['results']) == 12, len(parser.search_results['results'])
        assert all([v['visible_link'] for v in parser.search_results['results']])
        assert all([v['link'] for v in parser.search_results['results']])
        self.assertAlmostEqual(len([v['snippet'] for v in parser.search_results['results'] if v['snippet'] is not None]), 10, delta=4)
        
    def test_parse_yahoo(self):
        
        parser = self.get_parser_for_file('yahoo', 'data/uncompressed_serp_pages/snow_yahoo_de_ip.html')

        assert '19,400,000 Ergebnisse' == parser.search_results['num_results']
        assert len(parser.search_results['results']) >= 10, len(parser.search_results['results'])
        assert len([v['visible_link'] for v in parser.search_results['results'] if v['visible_link']]) == 10, 'Not 10 elements with a visible link in yahoo serp page'
        assert all([v['link'] for v in parser.search_results['results']])
        self.assertAlmostEqual(len([v['snippet'] for v in parser.search_results['results'] if v['snippet'] is not None]), 10, delta=4)


    ### test dynamic parsing for http mode

    ### test dynamic parsing for selenium mode with Chrome

    ### test dynamic parsing for selenium with phantomsjs


    ### test csv output

    ### test json output

    ### test proxies

    ### test correct handling of SERP page that has no results for search query.

    def test_no_results_for_query_google(self):
        parser = self.get_parser_for_file('google', 'data/uncompressed_no_results_serp_pages/google.html')

        assert parser.search_results['effective_query'] == '"be dealt and be evaluated"', 'No effective query.'

if __name__ == '__main__':
    unittest.main()
