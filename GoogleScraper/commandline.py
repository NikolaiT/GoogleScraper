# -*- coding: utf-8 -*-

import argparse
from GoogleScraper.version import __version__


def get_command_line(only_print_help=False):
    """
    Parse command line arguments when GoogleScraper is used as a CLI application.

    Returns:
        The configuration as a dictionary that determines the behaviour of the app.
    """

    parser = argparse.ArgumentParser(prog='GoogleScraper',
                                     description='Scrapes the Google, Yandex, Bing and many other  search engines by '
                                                 'forging http requests that imitate browser searches or by using real '
                                                 'browsers controlled by the selenium framework. '
                                                 'Multithreading support.',
                                     epilog='GoogleScraper {version}. This program might infringe the TOS of the '
                                            'search engines. Please use it on your own risk. (c) by Nikolai Tschacher'
                                            ', 2012-2015. incolumitas.com'.format(version=__version__))

    parser.add_argument('-m', '--scrape-method', type=str, default='http',
                        help='The scraping type. There are currently three types: "http", "selenium" and "http-async". '
                             '"Http" scrapes with raw http requests, whereas "selenium" uses the selenium framework to '
                             'remotely control browsers. "http-async" makes use of gevent and is well suited for '
                             'extremely fast and explosive scraping jobs. You may search more than 1000 requests per '
                             'second if you have the necessary number of proxies available. ',
                        choices=('http', 'selenium', 'http-async'))

    parser.add_argument('--sel-browser', choices=['firefox', 'chrome', 'phantomjs'], default='phantomjs',
                        help='The browser frontend for selenium scraping mode. Does only make sense if --scrape-method is set to "selenium"')

    keyword_group = parser.add_mutually_exclusive_group()

    keyword_group.add_argument('-q', '--keyword', type=str, action='store', dest='keyword',
                               help='The search keyword to scrape for. If you need to scrape multiple keywords, use '
                                    'the --keyword-file flag')

    keyword_group.add_argument('--keyword-file', type=str, action='store', default='',
                               help='Keywords to search for. One keyword per line. Empty lines are ignored. '
                                    'Alternatively, you may specify the path to an python module (must end with the '
                                    '.py suffix) where the keywords must be held in a dictionary with the name "scrape_'
                                    'jobs".')

    parser.add_argument('-o-', '--output-filename', type=str, action='store', default='',
                        help='The name of the output file. If the file ending is "json", write a json file, if the '
                             'ending is "csv", write a csv file.')

    parser.add_argument('--shell', action='store_true', default=False,
                        help='Fire up a shell with a loaded sqlalchemy session.')

    parser.add_argument('-n', '--num-results-per-page', type=int,
                        action='store', default=10,
                        help='The number of results per page. Must be smaller than 100, by default 50 for raw mode and '
                             '10 for selenium mode. Some search engines ignore this setting.')

    parser.add_argument('-p', '--num-pages-for-keyword', type=int, action='store',
                        default=1,
                        help='The number of pages to request for each keyword. Each page is requested by a unique '
                             'connection and if possible by a unique IP (at least in "http" mode).')

    parser.add_argument('-z', '--num-workers', type=int, default=1,
                        action='store',
                        help='This arguments sets the number of browser instances for selenium mode or the number of '
                             'worker threads in http mode.')

    parser.add_argument('-t', '--search-type', type=str, action='store', default='normal',
                        help='The searchtype to launch. May be normal web search, image search, news search or video '
                             'search.')

    parser.add_argument('--proxy-file', type=str, dest='proxy_file', action='store',
                        required=False, help='A filename for a list of proxies (supported are HTTP PROXIES, SOCKS4/5) '
                                             'with the following format: "Proxyprotocol (proxy_ip|proxy_host):Port\n"'
                                             'Example file: socks4 127.0.0.1:99\nsocks5 33.23.193.22:1080\n')

    parser.add_argument('--config-file', type=str, dest='config_file', action='store',
                        help='The path to the configuration file for GoogleScraper. Normally you won\'t need this, '
                             'because GoogleScrape comes shipped with a thoroughly commented configuration file named '
                             '"scrape_config.py"')

    parser.add_argument('--simulate', action='store_true', default=False, required=False,
                        help='''If this flag is set, the scrape job and its estimated length will be printed.''')

    loglevel_help = '''
Set the debug level of the application. Use the string representation
instead of the numbers. High numbers will output less, lower numbers more.
CRITICAL = 50,
FATAL = CRITICAL,
ERROR = 40,
WARNING = 30,
WARN = WARNING,
INFO = 20,
DEBUG = 10,
NOTSET = 0
    '''

    parser.add_argument('-v', '--verbosity', '--loglevel', '--log-level',
                        type=str, dest='log_level', default='INFO', help=loglevel_help)

    parser.add_argument('--print-results', choices=['all', 'summarize'], default='all',
                        help='Whether to print all results ("all"), or only print a summary ("summarize")')

    parser.add_argument('--view-config', action='store_true', default=False,
                        help="Print the current configuration to stdout. You may use it to create and tweak your own "
                             "config file from it.")

    parser.add_argument('-V', '--v', '--version', action='store_true', default=False, dest='version',
                        help='Prints the version of GoogleScraper')

    parser.add_argument('--clean', action='store_true', default=False,
                        help='Cleans all stored data. Please be very careful when you use this flag.')

    parser.add_argument('--mysql-proxy-db', action='store',
                        help="A mysql connection string for proxies to use. Format: mysql://<username>:<password>@"
                             "<host>/<dbname>. Has precedence over proxy files.")

    parser.add_argument('-s', '--search-engines', action='store', default=['google'],
                        help='What search engines to use (See GoogleScraper --config for the all supported). If you '
                             'want to use more than one at the same time, just separate with commatas: "google, bing, '
                             'yandex". If you want to use all search engines that are available, give \'*\' as '
                             'argument.')

    if only_print_help:
        parser.print_help()
    else:
        args = parser.parse_args()

        return vars(args)
