import unittest
import os
import configparser
from pprint import pprint
import importlib

def _reload_GoogleScraper(self):
    if hasattr(self, 'GoogleScraper'):
        del self.GoogleScraper
    self.GoogleScraper = importlib.import_module('GoogleScraper.Scraper')

class ConfigTest(unittest.TestCase):
    """Test the three different levels of the configuration
    possibility"""
    def setUp(self):
        _reload_GoogleScraper(self)
        # set some values in the config file
        cfg = configparser.ConfigParser()
        cfg.read_file(open(self.GoogleScraper.CONFIG_FILE, 'r', encoding='utf8'))

        self.GoogleScraper.Config.update({
            'GLOBAL': {
                'do_caching': True,
                'clean_cache_after': 13,
            },
            'SELENIUM': {
                    'num_browser_instances': 8
            }})

        cfg.update(
        {'GLOBAL': {
            'do_caching': False,
            'clean_cache_after': 14,
         },
         'SELENIUM': {
            'num_browser_instances': 9
         }
        })

        cfg.write(open('tempconfig.cfg', 'w', encoding='utf8'))
        self.GoogleScraper.CONFIG_FILE = 'tempconfig.cfg'

        self.cmdargs = 'sel --num-browser-instances 10'.split()


    def test_config(self):
        self.GoogleScraper.parse_config(self.cmdargs)

        cfg = self.GoogleScraper.Config
        self.assertEqual(cfg['SELENIUM'].getint('num_browser_instances'), 10, 'num_browser_instances should be 10')
        self.assertFalse(cfg['GLOBAL'].getboolean('do_caching'), 'do_caching should be false')
        self.assertEqual(cfg['GLOBAL'].getint('clean_cache_after'), 14, 'clean_cache_after is expected to be 14')

    def tearDown(self):
        os.unlink('tempconfig.cfg')


class SeleniumModeTest(unittest.TestCase):
    def setUp(self):
        _reload_GoogleScraper(self)
        self.GoogleScraper.parse_config('sel --keyword scraping'.split())
        self.GoogleScrape.run()
    def testResults(self):
        pass
    def tearDown(self):
        os.system('rm results_*.db')


if __name__ == '__main__':
    unittest.main()


