#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Shows how to control GoogleScraper programmatically.
"""

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
            'keyword': 'sexy girl', # :D hehe have fun my dear friends
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
    # basic_usage()
    image_search()



