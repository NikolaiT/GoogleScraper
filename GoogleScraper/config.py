# -*- coding: utf-8 -*-

import GoogleScraper.scrape_config
import inspect
import os

try:
    # SourceFileLoader is the recommended way in 3.3+
    from importlib.machinery import SourceFileLoader

    def load_source(name, path):
        return SourceFileLoader(name, path).load_module()
except ImportError:
    # but it does not exist in 3.2-, so fall back to imp
    import imp
    load_source = imp.load_source


def get_config(command_line_args=None, external_configuration_file=None, config_from_library_call=None):
    """
    Parse the configuration from different sources:
        - Internal config file
        - External config file (As specified by the end user)
        - Command Line args
        - Config that is passed to GoogleScraper if it is used as library.

    The order in which configuration is overwritten:

    Config from library call > Command Line args > External config file > internal config file

    So for example, a command line args overwrites an option in a user specified
    config file. But the user specified config file is still more valued than the
    same named option in the internal config file. But if GoogleScraper is called
    as library, the config passed there will overwrite everything else (Even if this config
    has specified an external config file...).

    External configuration files may be only specified in the command line args.
    """

    config = GoogleScraper.scrape_config

    def update_members(d):
        for k, v in d.items():
            setattr(config, k, v)

    if external_configuration_file:
        if os.path.exists(external_configuration_file) and external_configuration_file.endswith('.py'):
            exernal_config = load_source('external_config', external_configuration_file)
            members = inspect.getmembers(exernal_config)
            if isinstance(members, list):
                members = dict(members)
            update_members(members)

    if command_line_args:
        update_members(command_line_args)

    if config_from_library_call:
        update_members(config_from_library_call)

    config = {k: v for k, v in vars(config).items() if not k.startswith('_')}

    return config
