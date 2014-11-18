# GoogleScraper - Scraping search engines professionally

### Updated README on 17th november 2014

**Thanks for your patience. A more or less stable version (0.1.6) is on pypy available! **

*If you need the latest bug fixes and the most recent version, just install directly from this repo here:*

```
virtualenv --python python3 env
source env/bin/activate
pip install git+git://github.com/NikolaiT/GoogleScraper/
```

### Table of Contents

1. [Installation](#install)
2. [About](#about)
3. [Usage with Python](#usage)
4. [Command line usage (read this!)](#cli-usage)
5. [Contact](#contact)


<a name="install" \>
## Installation

GoogleScraper is written in Python 3. You should install at least Python 3.4
Furthermore, you need to install the Chrome Browser, maybe even the ChromeDriver for Selenium mode (I didn't have to). On Ubuntu 14.04
you certainly have to install the Chrome driver.

From now on (August 2014), you can install GoogleScraper comfortably with pip:

```
virtualenv --python python3 env
source env/bin/activate
pip install GoogleScraper

# then have a look how to use it:
GoogleScraper -h
```

#### Alternatively install directly from Github:

Sometimes the newest and most awesome stuff is not available in the cheeseshop (That's how the call
https://pypi.python.org/pypi/pip). Therefore you maybe want to install the latest source directly from
the Github repository. You can do so like this:

```
virtualenv --python python3 env
source env/bin/activate
pip install git+git://github.com/NikolaiT/GoogleScraper/
```

Please note however, that some features and examples might not work as expected. I also don't guarantee that 
the app even runs. I only guarantee (to a certain degree at least) that installing from pip will yield a 
usable version.


<a name="about" />
## What does GoogleScraper.py?

GoogleScraper parses Google search engine results (and many other search engines *_*) easily and in a fast way. It allows you to extract all found
links and their titles and descriptions programmatically which enables you to process scraped data further.

There are unlimited *usage scenarios*:

+ Quickly harvest masses of [google dorks][1].
+ Use it as a SEO tool.
+ Discover trends.
+ Compile lists of sites to feed your own database.
+ Many more use cases...
+ quite easily extendable since the code is well documented

First of all you need to understand that GoogleScraper uses **two completely different scraping approaches**:
+ Scraping with low level networking libraries such as `urllib.request` or `requests` modules. This simulates the http packets sent by real browsers.
+ Scrape by controlling a real browser with the selenium framework

Whereas the former approach was implemented first, the later approach looks much more promising in comparison, because
search engines have no easy way detecting it.

GoogleScraper is implemented with the following techniques/software:

+ Written in Python 3.4
+ Uses multithreading/asynchronous IO. (two possible approaches, currently only multi-threading is implemented)
+ Supports parallel google scraping with multiple IP addresses.
+ Provides proxy support using [socksipy][2] and built in browser proxies:
  * Socks5
  * Socks4
  * HttpProxy
+ Support for alternative search modes like news/image/video search.

### What search engines are suppported ?
Currently the following search engines are supported:
+ Google
+ Bing
+ Qandex
+ Baidu
+ Duckduckgo

### How does GoogleScraper maximize the amount of extracted information per IP address?

Scraping is a critical and highly complex subject. Google and other search engine giants have a strong inclination
to make the scrapers life as hard as possible. There are several ways for the search engine providers to detect that a robot is using
their search engine:

+ The User-Agent is not one of a browser.
+ The search params are not identical to the ones that browser used by a human sets:
  * Javascript generates challenges dynamically on the client side. This might include heuristics that try to detect human behaviour. Example: Only humans move their mouses and hover over the interesting search results.
+ Robots have a strict requests pattern (very fast requests, without a random time between the sent packets).
+ Dorks are heavily used
+ No pictures/ads/css/javascript are loaded (like a browser does normally) which in turn won't trigger certain javascript events

So the biggest hurdle to tackle is the javascript detection algorithms. I don't know what Google does in their javascript, but I will soon investigate it further and then decide if it's not better to change strategies and
switch to a **approach that scrapes by simulating browsers in a browserlike environment** that can execute javascript. The networking of each of these virtual browsers is proxified and manipulated such that it behaves like
a real physical user agent. I am pretty sure that it must be possible to handle 20 such browser sessions in a parallel way without stressing resources too much. The real problem is as always the lack of good proxies...

### How to overcome difficulties of low level (http) scraping?

As mentioned above, there are several drawbacks when scraping with `urllib.request` or `requests` modules and doing the networking on my own:

Browsers are ENORMOUSLY complex software systems. Chrome has around 8 millions line of code and firefox even 10 LOC. Huge companies invest a lot of money to push technology forward (HTML5, CSS3, new standards) and each browser
has a unique behaviour. Therefore it's almost impossible to simulate such a browser manually with HTTP requests.  This means Google has numerous ways to detect anomalies and inconsistencies in the browsing usage. Alone the
dynamic nature of Javascript makes it impossible to scrape undetected.

This cries for an alternative approach, that automates a **real** browser with Python. Best would be to control the Chrome browser since Google has the least incentives to restrict capabilities for their own native browser.
Hence I need a way to automate Chrome with Python and controlling several independent instances with different proxies set. Then the output of result grows linearly with the number of used proxies...

Some interesting technologies/software to do so:
+ [Selenium](https://pypi.python.org/pypi/selenium)
+ [Mechanize](http://wwwsearch.sourceforge.net/mechanize/)


<a name="usage" \>
## Example Usage
Here you can learn how to use GoogleScrape from within your own Python scripts.

```python
#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Shows how to control GoogleScraper programmatically. Uses selenium mode.
"""

from GoogleScraper import scrape_with_config, GoogleSearchError
from GoogleScraper.database import ScraperSearch, SERP, Link

if __name__ == '__main__':
    # See in the config.cfg file for possible values
    config = {
        'SCRAPING': {
            'use_own_ip': 'True',
            'keyword': 'Let\'s go bubbles!',
            'search_engine': 'yandex'
        },
        'SELENIUM': {
            'sel_browser': 'chrome',
        },
        'GLOBAL': {
            'do_caching': 'True'
        }
    }

    try:
        sqlalchemy_session = scrape_with_config(config)
    except GoogleSearchError as e:
        print(e)

    # let's inspect what we got

    for search in sqlalchemy_session.query(ScraperSearch).all():
        for serp in search.serps:
            print(serp)
            for link in serp.links:
                print(link)

```

<a name="cli-usage" \>
## Direct command line usage

Probably the best way to use GoogleScraper is to use it from the command line and fire a command such as
the following:
```
GoogleScraper --keyword-file /tmp/keywords --search-engine bing --num-pages-for-keyword 3 --scrapemethod selenium
```

Here *sel* marks the scraping mode as 'selenium'. This means GoogleScraper.py scrapes with real browsers. This is pretty powerful, since
you can scrape long and a lot of sites (Google has a hard time blocking real browsers). The argument of the flag `--keyword-file` must be a file with keywords separated by
newlines. So: For every google query one line. Easy, isnt' it?

Furthermore, the option `--num-pages-for-keyword` means that GoogleScraper will fetch 3 consecutive pages for each keyword.

Example keyword-file:
```
keyword number one
how to become a good rapper
inurl:"index.php?sl=43"
filetype:.cfg
allintext:"You have a Mysql Error in your"
intitle:"admin config"
Best brothels in atlanta
```

After the scraping you'll automatically have a new sqlite3 database in the named `google_scraper.db` in the same directory. You can open and inspect the database with the command:
```
GoogleScraper --shell
```

It shouldn't be a problem to scrape **_10'000 keywords in 2 hours_**. If you are really crazy, set the maximal browsers in the config a little
bit higher (in the top of the script file).

If you want, you can specify the flag `--proxy-file`. As argument you need to pass a file with proxies in it and with the following format:

```
protocol proxyhost:proxyport username:password
(...)
```
Example:
```
socks5 127.0.0.1:1080 blabla:12345
socks4 77.66.55.44:9999 elite:js@fkVA3(Va3)
```

In case you want to use GoogleScraper.py in *http* mode (which means that raw http headers are sent), use it as follows:

```
GoogleScraper -m http -p 1 -n 25 -q "white light"
```
<a name="contact" \>
## Contact

If you feel like contacting me, do so and send me a mail. You can find my contact information on my [blog][3].

[1]: http://www.webvivant.com/google-hacking.html "Google Dorks"
[2]: https://code.google.com/p/socksipy-branch/ "Socksipy Branch"
[3]: http://incolumitas.com/about/contact/ "Contact with author"
[4]: http://incolumitas.com/2013/01/06/googlesearch-a-rapid-python-class-to-get-search-results/
[5]: http://incolumitas.com/2014/11/12/scraping-and-extracting-links-from-any-major-search-engine-like-google-yandex-baidu-bing-and-duckduckgo/
