# -*- coding: utf-8 -*-

import sys
import logging
from GoogleScraper.config import Config

def setup_logger(level=logging.INFO):
        """Setup the global configuration logger for GoogleScraper"""
        logger = logging.getLogger('GoogleScraper')
        logger.setLevel(level)

        ch = logging.StreamHandler(stream=sys.stderr)
        ch.setLevel(level)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)


logger = logging.getLogger('GoogleScraper')

def out(msg, lvl=2):
    level = Config['GLOBAL'].getint('verbosity', 2)
    if lvl <= level:
        logger.info(msg)


def raise_or_log(msg, exception_obj=Exception):
    if Config['SCRAPING'].getboolean('raise_exceptions_while_scraping', False):
        raise exception_obj(msg)
    else:
        logger.warning(msg)

