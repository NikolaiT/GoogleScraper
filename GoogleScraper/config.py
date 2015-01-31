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
        # which scrape_method to use
        'scrape_method': 'http'
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
        'num_workers': 4,
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

def parse_config(parse_command_line=True):
    """Parse and normalize the config file and return a dictionary with the arguments.

    There are several places where GoogleScraper can be configured. The configuration is
    determined (in this order, a key/value pair emerging further down the list overwrites earlier occurrences)
    from the following places:
      - Program internal configuration found in the global variable Config in this file
      - Configuration parameters given in the config file CONFIG_FILE
      - Params supplied by command line arguments

    So for example, program internal params are overwritten by the config file which in turn
    are shadowed by command line arguments.

    """
    global Config, CONFIG_FILE

    cfg_parser = configparser.RawConfigParser()
    # Add internal configuration
    cfg_parser.read_dict(Config)

    if parse_command_line:
        cargs = get_command_line()

    if parse_command_line:
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
    if parse_command_line:
        cfg_parser = update_config(cargs, cfg_parser)

    # and replace the global Config variable with the real thing
    Config = cfg_parser

    # if we got extended config via command line, update the Config
    # object accordingly.
    if parse_command_line:
        if cargs['GLOBAL'].get('extended_config'):
            d = {}
            for option in cargs['GLOBAL'].get('extended_config').split('|'):

                assert ':' in option, '--extended_config "key:option, key2: option"'
                key, value = option.strip().split(':')
                d[key.strip()] = value.strip()

            for section, section_proxy in Config.items():
                for key, option in section_proxy.items():
                    if key in d and key != 'extended_config':
                        Config.set(section, key, str(d[key]))


def update_config_with_file(external_cfg_file):
    """Updates the global Config with the configuration of an
    external file.

    Args:
        external_cfg_file: The external configuration file to update from.
    """
    if external_cfg_file and os.path.exists(external_cfg_file):
        external = configparser.RawConfigParser()
        external.read_file(open(external_cfg_file, 'rt'))
        external.remove_section('DEFAULT')
        update_config(dict(external))

def parse_cmd_args():
    """Parse the command line

    """
    global Config
    update_config(get_command_line(), Config)

def get_config(force_reload=False, parse_command_line=True):
    """Returns the GoogleScraper configuration.

    Args:
        force_reload: If true, ignores the flag already_parsed
    Returns:
        The configuration after parsing it.
    """
    global already_parsed
    if not already_parsed or force_reload:
        already_parsed = True
        parse_config(parse_command_line=parse_command_line)
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
        if not Config.has_section(section) and section != 'DEFAULT':
            Config.add_section(section)

        for option, value in mapping.items():
            Config.set(section, option, str(value))

    return Config


Config = get_config(parse_command_line=False)