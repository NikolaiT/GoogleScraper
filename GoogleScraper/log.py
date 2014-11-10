# -*- coding: utf-8 -*-

import sys
import logging

def setup_logger(level=logging.INFO):
        """Setup the global configuration logger for GoogleScraper"""
        logger = logging.getLogger('GoogleScraper')
        logger.setLevel(level)

        ch = logging.StreamHandler(stream=sys.stderr)
        ch.setLevel(level)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
