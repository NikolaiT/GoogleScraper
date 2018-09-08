	# -*- coding: utf-8 -*-

"""
This is the basic GoogleScraper configuration file.

All options are basic Python data types. You may use all of Python's language
capabilities to specify settings in this file.
"""

"""
[OUTPUT]
Settings which control how GoogleScraper represents it's results
and handles output.
"""
# How and if results are printed when running GoogleScraper.
# if set to 'all', then all data from results are outputted
# if set to 'summarize', then only a summary of results is given.
# if set to anything else, no output will be given at all.
print_results = 'all'

# The name of the database that is written to the same
# directory where GoogleScraper will be called.
database_name = 'google_scraper'

# The file name of the output
# The file name also determine the format of how
# to store the results.
# filename.json => save results as json
# filename.csv => save a csv file
# If set to None, don't write any file.
output_filename = ''

# Whether sqlalchemy should log all stuff to stdout
# useful for devs. Don't set this to True if you don't know
# what you are doing.
log_sqlalchemy = False

# Set the debug level of the application. Use the string representation
# instead of the numbers. High numbers will output less, lower numbers more.
# CRITICAL = 50
# FATAL = CRITICAL
# ERROR = 40
# WARNING = 30
# WARN = WARNING
# INFO = 20
# DEBUG = 10
# NOTSET = 0
log_level = 'INFO'

# Log format string
log_format = '[%(threadName)s] - %(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Logfile
log_file = 'googlescraper.log'

"""
[SCRAPING]
Configuration parameters that control the scraping process. You will most
likely want to change these values.
"""

# The search queries to search for, separated by newlines. Intend every new
# keyword-line at least more than the next keyword.
keywords = []

# The keyword file. If this is a valid file path, the keywords params will be ignored and
# the ones from the file will be taken. Each keyword must be on a separate line.
keyword_file = ''

# How many results per SERP page
num_results_per_page = 10

# How many pages should be requested for each single keyword
num_pages_for_keyword = 1

# This arguments sets the number of browser instances for selenium mode or the number of worker threads in http mode.
num_workers = 1

# Maximum of workers
# When scraping with multiple search engines and more than one worker, the number of total workers
# becomes quite high very fast, so we set a upper limit here. Leaving this out, is quite dangerous in selenium mode.
maximum_workers = 20

# The search offset on which page to start scraping.
# Pages begin at 1
search_offset = 1

# In some countries the main search engine domain is blocked. Thus, search engines
# have different ip on which they are reachable. If you set a file with urls for the search engine,
# then GoogleScraper will pick a random url for any scraper instance.
# One url per line. It needs to be a valid url, not just an ip address!
google_ip_file = ''

# List of supported search engines
# If you add support for another search engine (of course implement it in the
# appropriate places) add it in this list.
supported_search_engines = ['google', 'yandex', 'bing', 'yahoo', 'baidu', 'duckduckgo', 'ask']

# The search engine(s) to use. For the supported search engines, see above "supported_search_engines"
search_engines = ['google', ]

# The base search urls
# Ready to append the parameters at the end to fine tune the search.

# The google base search url
google_search_url = 'https://www.google.com/search?'

# whether to change the search settings prior to scraping
# when this is set to False google will search with 
# the default search settings that your (selenium) browser supports
google_selenium_search_settings = False

# manually select search settings
# only possible in visible browsers
# when this is set, google won't block you as likely
google_selenium_manual_settings = False

# the following options only take effect when 
# google_selenium_search_settings is set to True

# Search Settings for Google Scraping in Selenium Mode
# 10, 20, 30, 50, 100
google_selenium_num_results = 100
# Private results help find more relevant content for you, including content and connections that only you can see.
google_selenium_personalization = False
# use a country code such as US, DE, GB, CH, ...
google_selenium_region = 'DE'
google_selenium_safe_search = False
# the language for google search results
google_selenium_language = 'English'


# The yandex base search url
yandex_search_url = 'http://yandex.ru/yandsearch?'

# The bing base search url
bing_search_url = 'http://www.bing.com/search?'

# The yahoo base search url
yahoo_search_url = 'https://de.search.yahoo.com/search?'

# The baidu base search url
baidu_search_url = 'http://www.baidu.com/s?'

# The duckduckgo base search url
duckduckgo_search_url = 'https://duckduckgo.com/'

# duckduckgo url for http mode
http_duckduckgo_search_url = 'https://duckduckgo.com/html/?'

# The ask base search url
ask_search_url = 'http://de.ask.com/web?'

# The search type. Currently, the following search modes are
# supported for some search engine=  normal, video, news and image search.
# "normal" search type is supported in all search engines.
search_type = 'normal'

# The scrape method. Can be 'http' or 'selenium' or 'http-async'
# http mode uses http packets directly, whereas selenium mode uses a real browser.
# http_async uses asyncio.
scrape_method = 'selenium'

# If scraping with the own IP address should be allowed.
# If this is set to False and you don't specify any proxies,
# GoogleScraper cannot run.
use_own_ip = True

# Whether to check proxies before starting the scrape
check_proxies = True

# You can set the internal behaviour of GoogleScraper here
# When GoogleScraper is invoked as a command line script, it is very much desirable
# to be as robust as possible. But when used from another program, we need immediate
# response when something fails.
raise_exceptions_while_scraping = True

# The following two options only make sense when search_engine is set to "googleimg"
# do NOT use them unless you are sure what you are going to do
image_type = None
image_size = None

"""
[GLOBAL]
Global configuration parameters that apply on all modes.
"""
# The proxy file. If this is a valid file path, each line will represent a proxy.
# Example file:
#        socks5 23.212.45.13= 1080 username= password
#        socks4 23.212.45.13= 80 username= password
#        http 23.212.45.13= 80
proxy_file = ''


# Whether to continue the last scrape when ended early.
continue_last_scrape = True

# Proxies stored in a MySQL database. If you set a parameter here, GoogleScraper will look for proxies
# in a table named 'proxies' for proxies with the following format=
# CREATE TABLE proxies (
#   id INTEGER PRIMARY KEY NOT NULL,
#   host VARCHAR(255) NOT NULL,
#   port SMALLINT,
#   username VARCHAR(255),
#   password VARCHAR(255),
#   protocol ENUM('socks5', 'socks4', 'http')
# );

# Specify the connection details in the following format=  mysql= //<username>= <password>@<host>/<dbname>
# Example=  mysql= //root= soemshittypass@localhost/supercoolproxies
mysql_proxy_db = ''

# Whether to manually clean cache files. For development purposes
clean_cache_files = False

# Proxy checker url
proxy_check_url = 'http://canihazip.com/s'

# Proxy info url
proxy_info_url = 'http://ipinfo.io/json'

# The basic search url
# Default is google
base_search_url = 'http://www.google.com/search'

# Whether caching shall be enabled
do_caching = False

# Whether the whole html files should be cached or
# if the file should be stripped from unnecessary data like javascripts, comments, ...
minimize_caching_files = True

# If set, then compress/decompress cached files
compress_cached_files = True

# Use either bz2 or gz to compress cached files
compressing_algorithm = 'gz'

# The relative path to the cache directory
cachedir = '.scrapecache/'

# After how many hours should the cache be cleaned
clean_cache_after = 48

# turn off sleeping pauses alltogether.
# Dont set this to False if you don't know what you are doing. 
do_sleep = True

# Sleeping distribution.
# Sleep a given amount of time as a function of the number of searches done.
# The scraper in selenium mode makes random pauses at certain times.
# Please add integer keys to sleeping_ranges such that the sum of 
# the keys amounts to 100. Then the key defines the probability of how many times
# this sleeping range occurs in a total of 100 searches.
# For example:
# sleeping_ranges = {
#     70:  (1, 2), # sleep between 1-2 seconds with probability 70/100
#     20:  (2, 6), # sleep between 2-6 seconds with probability 20/100
#     5: (10, 20), # sleep between 10-20 seconds with probability 5/100
#     3: (20, 30), # ...
#     2: (20, 40),
# }
sleeping_ranges = {
    70:  (1, 3),
    20:  (3, 6),
    5: (10, 20),
    3: (20, 25),
    2: (25, 30),
}

# Search engine specific sleeping ranges
# If you add the name of the search engine before a
# option {search_engine_name}_sleeping_ranges, then
# only this search engine will sleep the given ranges.
google_sleeping_ranges = {
    70:  (1, 3),
    20:  (3, 6),
    5: (10, 20),
    3: (20, 25),
    2: (25, 30),
}

# sleep a certain time after the Nth page has been scraped
fixed_sleeping_ranges = {
    1000:  (180, 420),
    2000:  (180, 420),
    3000:  (180, 420),
    4000:  (180, 420),
    5000:  (180, 420),
    6000:  (180, 420),
    7000:  (180, 420),
    8000:  (180, 420),
    9000:  (180, 420),
    10000:  (180, 420),
}

# If the search should be simulated instead of being done.
# Useful to learn about the quantity of keywords to scrape and such.
# Won't fire any requests.
simulate = False

# Internal use only
fix_cache_names = False

"""
[SELENIUM]
All settings that only apply for requesting with real browsers.
"""
# which browser to use in selenium mode. Valid values = ('chrome', 'firefox')
sel_browser = 'chrome'

# in which mode the browser is started. Valid values = ('normal', 'headless')
browser_mode = 'headless'

# chrome driver executable path
# get chrome drivers here: https://chromedriver.storage.googleapis.com/index.html?path=2.41/
chromedriver_path = '/home/nikolai/projects/private/Drivers/chromedriver'

# geckodriver executable path
# get gecko drivers here: https://github.com/mozilla/geckodriver/releases
geckodriver_path = '/home/nikolai/projects/private/Drivers/geckodriver'

# path to firefox binary
firefox_binary_path = '/home/nikolai/firefox/firefox'

# path to chromium browser binary
chrome_binary_path = '/usr/bin/chromium-browser'

# Manual captcha solving
# If this parameter is set to a Integer, the browser waits for the user
# to enter the captcha manually whenever Google detected the script as malicious.

# Set to False to disable.
# If the captcha isn't solved in the specified time interval, the browser instance
# with the current proxy is discarded.
manual_captcha_solving = True


# captch solving service

# enable captcha solving service
captcha_solving_service = False
# @TODO: Integrate https://2captcha.com/ 

# Xvfb display option
# You should start xvfb on your own before this option has any effect.
# Format=  [hostname]= displaynumber[.screennumber], see X(7) manuel for details
# will set environment variable $DISPLAY to it
xvfb_display = None


# how many tabs per instance
num_tabs = 1


"""
[HTTP]
All settings that target the raw http packet scraping mode.
"""

# You may overwrite the global search urls in the SCRAPING section
# for each mode
# search engine urls for the specific engines
# The google search url specifiably for http mode
google_search_url = 'https://www.google.com/search?'

"""
[HTTP_ASYNC]
Settings specific for the asynchronous mode.
"""

# The number of concurrent requests that are used for scraping
max_concurrent_requests = 100

"""
[PROXY_POLICY]
How the proxy policy works.
"""

# How long to sleep (in seconds) when the proxy got detected.
proxy_detected_timeout = 400

# Whether to stop workers when they got detected instead of waiting.
stop_on_detection = True
