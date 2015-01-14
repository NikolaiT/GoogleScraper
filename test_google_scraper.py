#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import unittest
from pprint import pprint

from GoogleScraper.parsing import get_parser_by_search_engine

# where to find the test html files

u_sample_serp_path = 'data/uncompressed_serp_pages'


class GoogleScraperTestCase(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def get_parser_for_file(self, se, file):
        path = os.path.join(u_sample_serp_path, file)

        with open(path, 'r') as f:
            html = f.read()
            parser = get_parser_by_search_engine(se)
            parser = parser(html)

        return parser

    def test_parse_google(self):
        parser = self.get_parser_for_file('google', 'abrakadabra_google_de_ip.html')

        assert '232.000.000 Ergebnisse' in parser.search_results['num_results']
        assert len(parser.search_results['results']) == 12, len(parser.search_results)

    

if __name__ == '__main__':
    unittest.main()
