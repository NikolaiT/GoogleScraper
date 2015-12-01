# GoogleScraper - Scraping search engines professionally

## News

GoogleScraper becomes **finally mature!** In the last months I didn't work at all on GoogleScraper. Reason for this was my overall
unhappiness with the Project. It is a very complex project with lot's of dependencies and pitfalls where newcomers may stumble.

And most importantly, *I was never satisfied with it's use case.* My initial goal was to make the whole internet searchable and give ordinary people like me independent access to the internet's information again. But this is never going to work by scraping search engines. This is the completely wrong way. Search engines cannot represent the internet and do hide information from you.

#### Why continuing this Project then?

Because GoogleScraper has its reason to live: Gain information on how search engines see the internet. Especially when it comes to **SEO and marketing**. For this very reason I will continue to maintain this project. But to say it: GoogleScraper will never support **massive gathering of data**. If you want to know which servers are running Drupal or Wordpress, you are wrong here. If you want to know all servers with a specific string in it's html body you are also wrong. This leads us to...

#### But how can I scrape the internet then :/ ?

Well my son, I am working on this. Let's just say I need to learn some Rust the next weeks. Or maybe I will use C. But Rust looks sooooo neat. And it's time ot learn some concepts about computer networks and about real scraping & indexing & crawling...

Look [here to get an idea how to use asynchronous mode](http://scrapeulous.com/googlescraper-260-keywords-in-a-second.html).


### Table of Contents

1. [Installation](#install)
2. [Quick Start](#quick)
3. [Asynchronous mode](#async)
4. [About](#about)
5. [Usage with Python](#usage)
6. [Command line usage (read this!)](#cli-usage)
7. [Contact](#contact)


<a name="install" \>
## Installation

GoogleScraper is written in Python 3. You should install at least Python 3.4. The last major development was all done with Python3.5. So when using 
Ubuntu 15.10 and Python3.5 for instance, please install:

```
sudo apt-get install python3.5-dev
```

Furthermore, you need to install the Chrome Browser, maybe even the ChromeDriver for Selenium mode. On Ubuntu 14.04 for instance,
you certainly have to install the Chrome driver.

You can install GoogleScraper comfortably with pip:

```
virtualenv --python python3 env
source env/bin/activate
pip install GoogleScraper
```

#### Alternatively install directly from Github:

Sometimes the newest and most awesome stuff is not available in the cheeseshop (That's how they call
https://pypi.python.org/pypi/pip). Therefore you maybe want to install GoogleScraper from the latest source that resides in this Github repository. You can do so like this:

```
virtualenv --python python3 env
source env/bin/activate
pip install git+git://github.com/NikolaiT/GoogleScraper/
```

Please note however, that some features and examples might not work as expected. I also don't guarantee that
the app even runs. I only guarantee (to a certain degree at least) that installing from pip will yield a
usable version.

### On Windows

On windows, you need to install some extensions manually: Lxml and Chromedriver:

#### lxml

Download the correct wheel file here: http://www.lfd.uci.edu/~gohlke/pythonlibs/#lxml

Then copy the downloaded file in your python root directory: C:\Python34\Scripts\
Then from this directory, issue the command in a cmd shell: ```pip install wheel_file.whl```
Of course the file has the name as it was downloaded.

#### chromedriver

Download the latest chromedriver from here: https://sites.google.com/a/chromium.org/chromedriver/downloads
Then copy the **chromedriver.exe** in the C:\Python34\ directory.

Then go back to C:\Python34\Scripts\ and issue the command: ```pip install GoogleScraper```

This should be it.

<a name="quick" />
## Quick Start

Install as described above.

See all options
```
GoogleScraper -h
```

Scrape the single keyword "apple" with http mode:
```
GoogleScraper -m http --keyword "apple" -v2
```

Scrape all keywords that are in keywords.txt in selenium mode (with real browsers):
```
GoogleScraper -m selenium --keyword-file keywords.txt -v2
```

Scrape all keywords that are in 
+ keywords.txt
+ with http mode
+ using 10 threads
+ scrape in the search engines google, bing and yahoo
+ store the output in a JSON file
+ increase verbosity
+ and use a proxy file named "proxies.txt"
```
GoogleScraper -m http --keyword-file keywords.txt --num-workers 10 --proxy-file proxies.txt --search-engines "google,bing,yahoo" --output-filename output.json -v2
```

Do an image search for the keyword "K2 mountain" on some search engines:

```
GoogleScraper -s "bing,baidu,yahoo,google,yandex" -q "K2 mountain" -t image -v2
```

Have fun :D

<a name="async" />

## Asynchronous mode

This is probably the most awesome feature of GoogleScraper. You can scrape with thousands of requests per second if either

+ The search engine doesn't block you (Bing didn't block me when requesting **100 keywords / second**)
+ You have enough proxies

Example for Asynchronous mode:

Search the keywords in the keyword file **keywords.txt** on bing and yahoo. By default asynchronous mode
spawns 100 requests at the same time. This means around 100 requests per second (depends on the actual connection...).

```
GoogleScraper -s "bing,yahoo" --keyword-file keywords.txt -m http-async -v3
```


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
+ Scraping with low level http libraries such as `urllib.request` or `requests` modules. This simulates the http packets sent by real browsers.
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
+ Yahoo
+ Yandex
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
Shows how to control GoogleScraper programmatically.
"""

import sys
from GoogleScraper import scrape_with_config, GoogleSearchError
from GoogleScraper.database import ScraperSearch, SERP, Link


### EXAMPLES OF HOW TO USE GoogleScraper ###

# very basic usage
def basic_usage():
    # See in the config.cfg file for possible values
    config = {
        'SCRAPING': {
            'use_own_ip': 'True',
            'keyword': 'Let\'s go bubbles!',
            'search_engines': 'yandex',
            'num_pages_for_keyword': 1
        },
        'SELENIUM': {
            'sel_browser': 'chrome',
        },
        'GLOBAL': {
            'do_caching': 'False'
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


# simulating a image search for all search engines that support image search
# then download all found images :)
def image_search():
    target_directory = 'images/'

    # See in the config.cfg file for possible values
    config = {
        'SCRAPING': {
            'keyword': 'beautiful landscape', # :D hehe have fun my dear friends
            'search_engines': 'yandex,google,bing,baidu,yahoo', # duckduckgo not supported
            'search_type': 'image',
            'scrapemethod': 'selenium'
        }
    }

    try:
        sqlalchemy_session = scrape_with_config(config)
    except GoogleSearchError as e:
        print(e)

    image_urls = []
    search = sqlalchemy_session.query(ScraperSearch).all()[-1]

    for serp in search.serps:
        image_urls.extend(
            [link.link for link in serp.links]
        )

    print('[i] Going to scrape {num} images and saving them in "{dir}"'.format(
        num=len(image_urls),
        dir=target_directory
    ))

    import threading,requests, os, urllib

    class FetchResource(threading.Thread):
        """Grabs a web resource and stores it in the target directory"""
        def __init__(self, target, urls):
            super().__init__()
            self.target = target
            self.urls = urls

        def run(self):
            for url in self.urls:
                url = urllib.parse.unquote(url)
                with open(os.path.join(self.target, url.split('/')[-1]), 'wb') as f:
                    try:
                        content = requests.get(url).content
                        f.write(content)
                    except Exception as e:
                        pass
                    print('[+] Fetched {}'.format(url))

    # make a directory for the results
    try:
        os.mkdir(target_directory)
    except FileExistsError:
        pass

    # fire up 100 threads to get the images
    num_threads = 100

    threads = [FetchResource('images/', []) for i in range(num_threads)]

    while image_urls:
        for t in threads:
            try:
                t.urls.append(image_urls.pop())
            except IndexError as e:
                break

    threads = [t for t in threads if t.urls]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    # that's it :)

### MAIN FUNCTION ###

if __name__ == '__main__':

    usage = 'Usage: {} [basic|image]'.format(sys.argv[0])
    if len(sys.argv) != 2:
        print(usage)
    else:
        arg = sys.argv[1]
        if arg == 'basic':
            basic_usage()
        elif arg == 'image':
            image_search()
        else:
            print(usage)
```

<a name="cli-usage" \>
## Direct command line usage

Probably the best way to use GoogleScraper is to use it from the command line and fire a command such as
the following:
```
GoogleScraper --keyword-file /tmp/keywords --search-engine bing --num-pages-for-keyword 3 --scrape-method selenium
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
