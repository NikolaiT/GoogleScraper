# -*- coding: utf-8 -*-

import os
import configparser
import logging

from GoogleScraper.commandline import get_command_line

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.cfg')
already_parsed = False
logger = logging.getLogger('GoogleScraper')

Config = {
    'SCRAPING': {
        # Whether to scrape with own ip address or just with proxies
        'use_own_ip': True,
        'scrapemethod': 'http'
    },
    'GLOBAL': {
        # The directory path for cached google results
        'do_caching': True,
        # If set, then compress/decompress files
        'compress_cached_files': True,
        # If set, use this compressing algorithm, else just use zip
        'compressing_algorithm': 'gz',
        # Whether caching shall be enabled
        'cachedir': '.scrapecache/',
        # After how many hours should the cache be cleaned
        'clean_cache_after': 48,
    },
    'SELENIUM': {
        # The maximal amount of selenium browser windows running in parallel
        'num_browser_instances': 4,
        # The base Google URL for SelScraper objects
        'sel_scraper_base_url': 'http://www.google.com/ncr',
        # which browser to use with selenium. Valid values: ('Chrome', 'Firefox')
        'sel_browser': 'Chrome',
    },
    'HTTP': {

    },
    'HTTP_ASYNC': {

    }
}

class InvalidConfigurationException(Exception):
    pass

def parse_config(cmd_args=False):
    """Parse and normalize the config file and return a dictionary with the arguments.

    There are several places where GoogleScraper can be configured. The configuration is
    determined (in this order, a key/value pair emerging further down the list overwrites earlier occurrences)
    from the following places:
      - Program internal configuration found in the global variable Config in this file
      - Configuration parameters given in the config file CONFIG_FILE
      - Params supplied by command line arguments

    So for example, program internal params are overwritten by the config file which in turn
    are shadowed by command line arguments.

    Args:
        cmd_args; An optional namespace object. If given, replaces command line parsing with this dict.
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
        logger.error('Exception trying to parse config file {}: {}'.format(CONFIG_FILE, e))

    logger.setLevel(cfg_parser['GLOBAL'].get('debug', 'INFO'))
    # add configuration parameters retrieved from command line
    if cargs:
        cfg_parser = update_config(cargs, cfg_parser)

    # and replace the global Config variable with the real thing
    Config = cfg_parser

def parse_cmd_args(cmd_args=None):
    """Parse the command line

    Args:
        cmd_args: Optional dictionary, if given, don't parse the command line,
                  prepopulate the config with this dicionary.
    """
    if isinstance(cmd_args, list):
        cargs = get_command_line(cmd_args)
    else:
        cargs = get_command_line()

    global Config
    update_config(cargs, Config)

def get_config(cmd_args=False, force_reload=False):
    """Returns the GoogleScraper configuration.

    Args:
        cmd_args; The command line arguments that should be passed to the cmd line argument parser.
        force_reload: If true, ignores the flag already_parsed
    Returns:
        The configuration after parsing it.
    """
    global already_parsed
    if not already_parsed or force_reload:
        already_parsed = True
        parse_config(cmd_args)
    return Config

def update_config(d, target=None):
    """Updates the config with a dictionary.

    In comparison to the native dictionary update() method,
    update_config() will only extend or overwrite options in sections. It won't forget
    options that are not explicitly specified in d.

    Will overwrite existing options.

    Args:
        d: The dictionary to update the configuration with.
        target; The configuration to be updated.

    Returns:
        The configuration after possibly updating it.
    """
    if not target:
        global Config
    else:
        Config = target

    for section, mapping in d.items():
        if not Config.has_section(section):
            Config.add_section(section)

        for option, value in mapping.items():
            Config.set(section, option, str(value))

    return Config


Config = get_config()