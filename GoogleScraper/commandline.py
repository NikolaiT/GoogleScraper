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
                                     description='Scrapes the Google search engine by forging http requests that imitate '
                                                 'browser searches or by using real browsers controlled by the selenium framework. Multithreading support.',
                                     epilog='This program might infringe the Google TOS. Please use it on your own risk. (c) by Nikolai Tschacher, 2012-2014. incolumitas.com')

    parser.add_argument('scrapemethod', type=str,
                        help='The scraping type. There are currently two types: "http" and "sel". "Http" scrapes with raw http requests whereas "sel" uses the selenium framework to remotely control browsers',
                        choices=('http', 'sel'), default='sel')
    parser.add_argument('-q', '--keyword', metavar='keyword', type=str, action='store', dest='keyword', help='The search keyword to scrape for. If you need to scrape multiple keywords, use the --keyword-file flag')
    parser.add_argument('--keyword-file', type=str, action='store',
                        help='Keywords to search for. One keyword per line. Empty lines are ignored.')
    parser.add_argument('-n', '--num-results-per-page', metavar='number_of_results_per_page', type=int,
                         action='store', default=50,
                        help='The number of results per page. Must be smaller than 100, by default 50 for raw mode and 10 for sel mode.')
    parser.add_argument('-z', '--num-browser-instances', metavar='num_browser_instances', type=int,
                        action='store',  help='This arguments sets the number of browser instances to use in `sel` mode. In raw mode, this argument is quitely ignored.')
    parser.add_argument('--base-search-url', type=str,
                        action='store',  help='This argument sets the search url for all searches. The defautl is `http://google.com/ncr`')
    parser.add_argument('-p', '--num-pages', metavar='num_of_pages', type=int, dest='num_pages', action='store',
                        default=1, help='The number of pages to request for each keyword. Each page is requested by a unique connection and if possible by a unique IP (at least in "http" mode).')
    parser.add_argument('-s', '--storing-type', metavar='results_storing', type=str, dest='storing_type',
                        action='store',
                        default='stdout', choices=('database', 'stdout'), help='Where/how to put/show the results. Default is stdout.')
    parser.add_argument('-t', '--search_type', metavar='search_type', type=str, dest='searchtype', action='store',
                        default='normal',
                        help='The searchtype to launch. May be normal web search, image search, news search or video search.')
    parser.add_argument('--proxy-file', type=str, dest='proxy_file', action='store',
                        required=False, help='''A filename for a list of proxies (supported are HTTP PROXIES, SOCKS4/5) with the following format: "Proxyprotocol (proxy_ip|proxy_host):Port\\n"
                        Example file: socks4 127.0.0.1:99\nsocks5 33.23.193.22:1080\n''')
    parser.add_argument('--config-file', type=str, dest='config_file', action='store',
                        help='''The path to the configuration file for GoogleScraper. Normally you won't need this, because GoogleScrape
                        comes shipped with a thoroughly commented configuration file named `config.cfg`''')
    parser.add_argument('--simulate', action='store_true', default=False, required=False, help='''If this flag is set, the scrape job and its rough length will be printed.''')
    parser.add_argument('--print', action='store_true', default=True, required=False, help='''If set, print all scraped output GoogleScraper finds. Don't use it when scraping a lot, results are stored in a sqlite3 database anyway.''')
    parser.add_argument('--view', action='store_true', default=False, help="View the response in a default browser tab."
                                                                           " Mainly for debug purposes. Works only when caching is enabled.")
    parser.add_argument('--fix-cache-names', action='store_true', default=False, help="For internal use only. Renames the cache files after a hash constructed after the keywords located in the <title> tag.")
    parser.add_argument('--check-oto', action='store_true', default=False, help="For internal use only. Checks whether all the keywords are cached in different files.")
    parser.add_argument('-v', '--verbosity', type=int, default=1,
                        help="The verbosity of the output reporting for the found search results.")
    parser.add_argument('--debug', action='store', choices=['INFO', 'DEBUG'], default='INFO', help='info or debug. or another debug level.')

    parser.add_argument('--view-config', action='store_true', default=False,
                        help="Print the current configuration to stdout. You may use it to create and tweak your own config file from it.")
    parser.add_argument('--mysql-proxy-db', action='store',
                        help="A mysql connection string for proxies to use. Format: mysql://<username>:<password>@<host>/<dbname>. Has precedence over proxy files.")

    if static_args:
        args = parser.parse_args(static_args)
    else:
        args = parser.parse_args()

    make_dict = lambda L: dict([(key, value) for key, value
                                in args.__dict__.items() if (key in L and value is not None)])

    return {
        'SCRAPING': make_dict(['scrapemethod', 'num_pages', 'num_results_per_page', 'search_type', 'keyword', 'keyword_file']),
        'GLOBAL':  make_dict(['base_search_url', 'check_oto', 'debug', 'fix_cache_names', 'simulate', 'print', 'proxy_file', 'view_config', 'config_file', 'mysql_proxy_db', 'verbosity']),
        'SELENIUM': make_dict(['num_browser_instances'])
    }
