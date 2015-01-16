#!/usr/bin/python

"""
Unittests
http://stackoverflow.com/questions/4904096/whats-the-difference-between-unit-functional-acceptance-and-integration-test
"""

import unittest
import importlib
import os
import GoogleScraper
import configparser

class ConfigTest(unittest.TestCase):
    """Test the three different levels of the configuration
    possibility for GoogleScraper"""
    def setUp(self):
        importlib.reload(GoogleScraper)
        # set some values in the config file
        cfg = configparser.ConfigParser()
        self.f = open(GoogleScraper.CONFIG_FILE, 'r', encoding='utf8')
        cfg.read_file(self.f)

        GoogleScraper.Config.update({
            'GLOBAL': {
                'do_caching': True,
                'clean_cache_after': 13,
            },
            'SELENIUM': {
                    'num_browser_instances': 8
            }})

        cfg.read_dict(
        {'GLOBAL': {
            'do_caching': False,
            'clean_cache_after': 14,
         },
         'SELENIUM': {
            'num_browser_instances': 9
         }
        })
        self.tempfile = open('tempconfig.cfg', 'w', encoding='utf8')

        cfg.write(self.tempfile)
        GoogleScraper.CONFIG_FILE = 'tempconfig.cfg'
        self.cmdargs = 'sel --num-browser-instances 10'.split()

    def test_config(self):
        GoogleScraper.parse_config(self.cmdargs)

        cfg = GoogleScraper.Config
        self.assertEqual(cfg['SELENIUM'].getint('num_browser_instances'), 10, 'num_browser_instances should be 10')
        self.assertFalse(cfg['GLOBAL'].getboolean('do_caching'), 'do_caching should be false')
        self.assertEqual(cfg['GLOBAL'].getint('clean_cache_after'), 14, 'clean_cache_after is expected to be 14')

    def tearDown(self):
        self.tempfile.close()
        os.unlink('tempconfig.cfg')
        self.f.close()

if __name__ == '__main__':
    unittest.main()


