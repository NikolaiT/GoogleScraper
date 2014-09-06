# -*- coding: utf-8 -*-

__author__ = 'Nikolai Tschacher'
__updated__ = '06.09.2014'  # day.month.year
__home__ = 'incolumitas.com'
__version__ = '0.1.0'

from GoogleScraper.proxies import Proxy
from GoogleScraper.config import get_config
from GoogleScraper.log import setup_logger

# Exposed as public interface
from GoogleScraper.core import scrape, scrape_with_config
from GoogleScraper.scraping import GoogleSearchError

Config = get_config()
setup_logger()