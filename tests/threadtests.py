__author__ = 'nikolai'

import threading
import requests
import socket
import random
import bs4
from cssselect import HTMLTranslator, SelectorError
from bs4 import UnicodeDammit
import lxml.html
from urllib.parse import urlparse


class TestThread(threading.Thread):
    def __init__(self, url='http://httpbin.org/get', uparam=None, gsearch={}):
        super().__init__()
        self.url = url
        if not uparam:
            self.uparam = {'uparam': random.randint(0, 100000)}
        else:
            self.uparam = {'uparam': uparam}

        self.gsearch = gsearch

    def run(self):
        self.google_search()

    def google_search(self):
        params = {
            'q': self.gsearch['query'], # the search term
            'num': self.gsearch['n_res_page'], # the number of results per page
            'start': self.gsearch['n_res_page']*self.gsearch['n_page'], # the offset to the search results. page number = (start / num) + 1
            'pws': '0'      # personalization turned off by default
        }
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'close',
            'DNT': '1'
        }
        r = requests.get('http://www.google.com/search', params=params, headers=headers)
        html = r.text
        # Try to parse the google HTML llresult using lxml
        try:
            doc = UnicodeDammit(html, is_html=True)
            parser = lxml.html.HTMLParser(encoding=doc.declared_html_encoding)
            dom = lxml.html.document_fromstring(html, parser=parser)
            dom.resolve_base_href()
        except Exception as e:
            print('Some error occurred while lxml tried to parse: {}'.format(e.msg))
            return False

        try:
            res = dom.xpath(HTMLTranslator().css_to_xpath('div#resultStats'))[0].text_content()
            print("Got number of results: `{}` for query {}".format(res, self.gsearch['query']))
        except Exception as e:
            print(e.msg)


def with_requests(self):
    r = requests.get(self.url, params=self.uparam)
    print(r.text)


def with_socket(self):
    host, path = urlparse(self.url).netloc, urlparse(self.url).path

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        s.connect((host, 80))
        payload = 'GET {}?uparam={} HTTP/1.1\r\nHost: {}\r\nConnection: close\r\n\r\n'.format(path, self.uparam.get(
            'uparam'), host)
        #print("Sending: {}".format(payload))
        s.send(payload.encode())
    except socket.error as se:
        print(se.args)

    response = s.recv(4096)
    print(response)


if __name__ == '__main__':
    searches = ['casablance', 'travel']
    configs = [{'query': query, 'n_res_page': 10, 'n_page': 0} for query in searches]
    threads = [TestThread(gsearch=config) for config in configs]
    for t in threads:
        t.start()

    for t in threads:
        t.join()
