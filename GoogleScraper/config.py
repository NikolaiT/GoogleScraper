# -*- coding: utf-8 -*-

import os
import configparser
import logging

from GoogleScraper.commandline import get_command_line

__author__ = 'nikolai'

# a level up
# CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config/config.cfg')
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.cfg')

logger = logging.getLogger('GoogleScraper')

Config = {
    'SCRAPING': {
        # Whether to scrape with own ip address or just with proxies
        'use_own_ip': True,
    },
    'GLOBAL': {
        # The database name, with a timestamp as fmt
        'db': 'results_{asctime}.db',
        # The directory path for cached google results
        'do_caching': True,
        # If set, then compress/decompress files with this algorithm
        'compress_cached_files': True,
        # Whether caching shall be enabled
        'cachedir': '.scrapecache/',
        # After how many hours should the cache be cleaned
        'clean_cache_after': 24,
        # Commit changes to db every N requests per GET/POST request
        'commit_interval': 10,
        # unique identifier that is sent to signal that a queue has
        # processed all inputs
        'all_processed_sig': 'kLQ#vG*jatBv$32JKlAvcK90DsvGskAkVfBr',
    },
    'SELENIUM': {
        # The maximal amount of selenium browser windows running in parallel
        'num_browser_instances': 8,
        # The base Google URL for SelScraper objects
        'sel_scraper_base_url': 'http://www.google.com/ncr',
        # which browser to use with selenium. Valid values: ('Chrome', 'Firefox')
        'sel_browser': 'Chrome',
    },
    'HTTP': {

    },
    'GOOGLE_SEARCH_PARAMS': {

    }
}

def parse_config(cmd_args=False):
    """Parse and normalize the config file and return a dictionary with the arguments.

    There are several places where GoogleScraper can be configured. The configuration is
    determined (in this order, a key/value pair emerging in further down the list overwrites earlier occurrences)
    from the following places:
      - Program internal configuration found in the global variable Config
      - Configuration parameters given in the config file
      - Params supplied by command line arguments
    """
    global Config, CONFIG_FILE
    cargs = False

    cfg_parser = configparser.ConfigParser()
    # Add internal configuration
    cfg_parser.read_dict(Config)

    # if necessary, get command line configuration
    if isinstance(cmd_args, list):
        cargs = get_command_line(cmd_args)
    elif cmd_args:
        cargs = get_command_line()

    if cmd_args:
        cfg_file_cargs = cargs['GLOBAL'].get('config_file')
        if cfg_file_cargs and os.path.exists(cfg_file_cargs):
            CONFIG_FILE = cfg_file_cargs

    # Parse the config file
    try:
        with open(CONFIG_FILE, 'r', encoding='utf8') as cfg_file:
            cfg_parser.read_file(cfg_file)
    except Exception as e:
        logger.error('Exception trying to parse file {}: {}'.format(CONFIG_FILE, e))

    logger.setLevel(cfg_parser['GLOBAL'].getint('debug', 10))
    # add configuration parameters retrieved from command line
    if cargs:
        cfg_parser.read_dict(cargs)

    # and replace the global Config variable with the real thing
    Config = cfg_parser

def get_config(cmd_args=False, force_reload=False):
    if not isinstance(Config, configparser.ConfigParser) or force_reload:
        parse_config(cmd_args)
    return Config