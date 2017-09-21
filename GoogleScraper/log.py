# -*- coding: utf-8 -*-

import sys
import logging

"""
Loggers are created at the top of modules. Therefore each code may access
a logger. But there is a fundamental problem to this approach:

The configuration that determines the state of GoogleScraper may come from various
sources and is parsed only at runtime in the config.py module. In this config, the
loglevel is also specified.

So we need to adjust the loglevel to the value set in
the configuration for each submodule.
"""

def setup_logger(level=logging.INFO):
    """
    Configure global log settings for GoogleScraper
    """
    logger = logging.getLogger()
    logger.setLevel(level)

    # See here: http://stackoverflow.com/questions/7173033/duplicate-log-output-when-using-python-logging-module
    if not len(logger.handlers):
        ch = logging.StreamHandler(stream=sys.stderr)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
