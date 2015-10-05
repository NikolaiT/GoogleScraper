# -*- coding: utf-8 -*-

import sys
import logging

LOGLEVEL_SHOW_RESULTS_SUMMARY = 12
LOGLEVEL_SHOW_ALL_RESULTS = 11

logging.addLevelName(LOGLEVEL_SHOW_RESULTS_SUMMARY, 'RESULTS_SUMMARY')
logging.addLevelName(LOGLEVEL_SHOW_ALL_RESULTS, 'RESULTS')

def summarize_results(self, message, *args, **kws):
    # Yes, logger takes its '*args' as 'args'.
    if self.isEnabledFor(LOGLEVEL_SHOW_RESULTS_SUMMARY):
        self._log(LOGLEVEL_SHOW_RESULTS_SUMMARY, message, args, **kws)
logging.Logger.summarize_results = summarize_results

def log_results(self, message, *args, **kws):
    # Yes, logger takes its '*args' as 'args'.
    if self.isEnabledFor(LOGLEVEL_SHOW_ALL_RESULTS):
        self._log(LOGLEVEL_SHOW_ALL_RESULTS, message, args, **kws)
logging.Logger.log_results = log_results

def setup_logger(name, level=20):
    """Setup the global configuration logger for GoogleScraper"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # See here: http://stackoverflow.com/questions/7173033/duplicate-log-output-when-using-python-logging-module
    if not len(logger.handlers):
        ch = logging.StreamHandler(stream=sys.stderr)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    return logger