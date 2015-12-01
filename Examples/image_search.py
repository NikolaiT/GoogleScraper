#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from GoogleScraper import scrape_with_config, GoogleSearchError

# simulating a image search for all search engines that support image search.
# Then download all found images :)

target_directory = 'images/'

# See in the config.cfg file for possible values
config = {
    'keyword': 'beautiful landscape', # :D hehe have fun my dear friends
    'search_engines': ['yandex', 'google', 'bing', 'yahoo'], # duckduckgo not supported
    'search_type': 'image',
    'scrape_method': 'selenium',
    'do_caching': True,
}

try:
    search = scrape_with_config(config)
except GoogleSearchError as e:
    print(e)

image_urls = []

for serp in search.serps:
    image_urls.extend(
        [link.link for link in serp.links]
    )

print('[i] Going to scrape {num} images and saving them in "{dir}"'.format(
    num=len(image_urls),
    dir=target_directory
))

import threading,requests, os, urllib

# In our case we want to download the
# images as fast as possible, so we use threads.
class FetchResource(threading.Thread):
    """Grabs a web resource and stores it in the target directory.

    Args:
        target: A directory where to save the resource.
        urls: A bunch of urls to grab

    """
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
