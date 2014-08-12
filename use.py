#!/usr/bin/python3
# -*- coding: utf-8 -*-

import GoogleScraper
from GoogleScraper import Proxy, core
import urllib.parse

if __name__ == '__main__':
    # See in the config.cfg file for possible values
    GoogleScraper.Config['SCRAPING']['use_own_ip'] = 'False'
    GoogleScraper.Config['SCRAPING']['keyword'] = 'Hello World'
    GoogleScraper.Config['SELENIUM']['sel_browser'] = 'chrome' # change this to 'phantomjs' for awesomeness
    GoogleScraper.Config['SELENIUM']['manual_captcha_solving'] = 'True'

    # sample proxy
    proxy = Proxy(proto='socks5', host='localhost', port=9050, username='', password='')

    try:
        results = core.scrape('Best SEO tool', scrapemethod='sel')#, proxy=proxy)
        for page in results:
            for link_title, link_snippet, link_url, *rest in page['results']:
                # You can access all parts of the search results like that
                # link_url.scheme => URL scheme specifier (Ex: 'http')
                # link_url.netloc => Network location part (Ex: 'www.python.org')
                # link_url.path => URL scheme specifier (Ex: ''help/Python.html'')
                # link_url.params => Parameters for last path element
                # link_url.query => Query component
                try:
                    print(urllib.parse.unquote(link_url.geturl())) # This reassembles the parts of the url to the whole thing
                except:
                    pass
            # How many urls did we get on all pages?
            print(sum(len(page['results']) for page in results))

            # How many hits has google found with our keyword (as shown on the first page)?
            print(page['num_results_for_kw'])

    except GoogleScraper.GoogleSearchError as e:
        # e contains the reason why the proxy failed
        print(e)



