# -*- coding: utf-8 -*-

import argparse

def get_command_line(static_args=False):
    """Parse command line arguments when GoogleScraper is used from the CLI.

    Args:
        static_args: A Namespace object that contains config parameters.
                        If supplied, don't parse from the command line and
                        apply the command parser on them instead.
    Returns:
        The configuration as a dictionary that determines the behaviour of the app.
    """

    parser = argparse.ArgumentParser(prog='GoogleScraper',
                                     description='Scrapes the Google, Yandex, Bing and many other  search engines by forging http requests that imitate '
                                                 'browser searches or by using real browsers controlled by the selenium framework. Multithreading support.',
                                     epilog='This program might infringe the TOS of the search engines. Please use it on your own risk. (c) by Nikolai Tschacher, 2012-2014. incolumitas.com')

    parser.add_argument('-m', '--scrapemethod', type=str, default='http',
                        help='''The scraping type. There are currently three types: "http", "selenium" and "http-async".
                         "Http" scrapes with raw http requests, whereas "selenium" uses the selenium framework to remotely control browsers'.
                         "http-async" makes use of gevent and is well suited for extremely fast and explosive scraping jobs.
                         You may search more than 1000 requests per second if you have the necessary number of proxies available.
                         ''', choices=('http', 'selenium', 'http-async'))

    parser.add_argument('-q', '--keyword', type=str, action='store', dest='keyword', help='The search keyword to scrape for. If you need to scrape multiple keywords, use the --keyword-file flag')

    parser.add_argument('--keyword-file', type=str, action='store',
                        help='Keywords to search for. One keyword per line. Empty lines are ignored.')

    parser.add_argument('-f', '--output-format', type=str, action='store', default='stdout', choices=['stdout', 'json', 'csv'],
                        help='''How to save the output of the scrape. The results are always saved in the database. But for '
                             the purpose of immediate exploration, the results may be also saved as JSON and CSV files.''')

    parser.add_argument('-o-', '--output-filename', type=str, action='store', default='google_scraper',
                        help='The name of the output file. Depends on the output format. Sqlite3 files will have a .db suffix, json results a .json ending and csv output a .csv ending. This means: Do not provide your own suffix!')

    parser.add_argument('--shell', action='store_true', default=False, help='Fire up a shell with a loaded sqlalchemy session.')

    parser.add_argument('-n', '--num-results-per-page', type=int,
                         action='store', default=50,
                        help='The number of results per page. Must be smaller than 100, by default 50 for raw mode and 10 for selenium mode. Some search engines do not support this.')

    parser.add_argument('-p', '--num-pages-for-keyword', type=int, action='store',
                        default=1, help='The number of pages to request for each keyword. Each page is requested by a unique connection and if possible by a unique IP (at least in "http" mode).')

    parser.add_argument('-z', '--num-workers', type=int, default=1,
                        action='store',  help='This arguments sets the number of browser instances for selenium mode or the number of worker threads in http mode.')

    parser.add_argument('-t', '--search-type', type=str, action='store', default='normal',
                        help='The searchtype to launch. May be normal web search, image search, news search or video search.')

    parser.add_argument('--proxy-file', type=str, dest='proxy_file', action='store',
                        required=False, help='''A filename for a list of proxies (supported are HTTP PROXIES, SOCKS4/5) with the following format: "Proxyprotocol (proxy_ip|proxy_host):Port\\n"
                        Example file: socks4 127.0.0.1:99\nsocks5 33.23.193.22:1080\n''')

    parser.add_argument('--config-file', type=str, dest='config_file', action='store',
                        help='''The path to the configuration file for GoogleScraper. Normally you won't need this, because GoogleScrape
                        comes shipped with a thoroughly commented configuration file named `config.cfg`''')

    parser.add_argument('--simulate', action='store_true', default=False, required=False, help='''If this flag is set, the scrape job and its rough length will be printed.''')

    parser.add_argument('-v', '--verbosity', type=int, default=1,
                        help='The verbosity of GoogleScraper output. 0: no ouput, 1: most necessary info, summary (no results), 2: detailed scraping info (still without results), 3: show parsed results:, > 3:  Degbug info.')

    parser.add_argument('--view-config', action='store_true', default=False,
                        help="Print the current configuration to stdout. You may use it to create and tweak your own config file from it.")

    parser.add_argument('--version', action='store_true', default=False,
                        help='Prints the version of GoogleScraper')

    parser.add_argument('--mysql-proxy-db', action='store',
                        help="A mysql connection string for proxies to use. Format: mysql://<username>:<password>@<host>/<dbname>. Has precedence over proxy files.")

    parser.add_argument('--search-engines', action='store',
                        help='What search engines to use. Supported search engines: google, yandex, bing, yahoo, baidu, duckduckgo. If you want to use more than one concurrently, just separate with commatas: "google, bing, yandex"')


    if static_args:
        args = parser.parse_args(static_args)
    else:
        args = parser.parse_args()

    make_dict = lambda L: dict([(key, value) for key, value
                                in args.__dict__.items() if (key in L and value is not None)])

    return {
        'SCRAPING': make_dict(['search_engines', 'scrapemethod', 'num_pages_for_keyword', 'num_results_per_page', 'search_type', 'keyword', 'keyword_file', 'num_workers']),
        'GLOBAL':  make_dict(['debug', 'simulate', 'proxy_file', 'view_config', 'config_file', 'mysql_proxy_db', 'verbosity', 'output_format', 'shell', 'output_filename', 'output_format', 'version'])
    }
