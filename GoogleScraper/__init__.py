# -*- coding: utf-8 -*-

__author__ = 'Nikolai Tschacher'
__updated__ = '04.11.2014'  # day.month.year
__home__ = 'incolumitas.com'

from GoogleScraper.proxies import Proxy
from GoogleScraper.config import get_config
from GoogleScraper.log import setup_logger

"""
All objects imported here are exposed as the public API of GoogleScraper
"""

from GoogleScraper.core import scrape, scrape_with_config
from GoogleScraper.scraping import GoogleSearchError

Config = get_config()
setup_logger()
