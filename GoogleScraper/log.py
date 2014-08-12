# -*- coding: utf-8 -*-

import sys
import logging

__author__ = 'nikolai'

def setup_logger(level=logging.INFO):
        # First obtain a logger
        logger = logging.getLogger('GoogleScraper')
        logger.setLevel(level)

        ch = logging.StreamHandler(stream=sys.stderr)
        ch.setLevel(level)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
