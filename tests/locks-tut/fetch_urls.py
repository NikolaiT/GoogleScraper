__author__ = 'nikolai'

import urllib.request
import threading
from bs4 import UnicodeDammit

class FetchUrls(threading.Thread):
    """
    Thread checking URLs.
    """

    def __init__(self, urls, output, lock):
        """
        Constructor.

        @param urls: list of urls to check
        @param output: file to write urls output
        @param lock : a lock to protect simultaneous file writes
        """
        threading.Thread.__init__(self)
        self.urls = urls
        self.output = output
        self.lock = lock

    def run(self):
        """
        Thread run method. Chek URLs one by one.
        """

        while self.urls:
            url = self.urls.pop()
            req = urllib.request.Request(url)
            try:
                d = urllib.request.urlopen(url)
            except urllib.request.URLError as e:
                print('URL {} failed: {}'.format(url, e))

            html = d.read()
            dom = UnicodeDammit(html, is_html=True)
            self.lock.acquire()
            print('lock acquired by {}'.format(self.name))
            self.output.write(html.decode(dom.declared_html_encoding))
            print('write done by {}'.format(self.name))
            print('lock released by {}'.format(self.name))
            self.lock.release()
            print('write done by {}'.format(self.name))
            print('URL {} fetched by {}'.format(url, self.name))

def main():
    urls = ['http://spiegel.de', 'http://heise.de']
    urls2 = ['http://de.yahoo.com/?p=us', 'http://golem.de']

    lock = threading.Lock()

    f = open('output.txt', 'w')

    t1, t2 = FetchUrls(urls, f, lock), FetchUrls(urls2, f, lock)

    t1.start()
    t2.start()
    t1.join()
    t2.join()
    f.close()

if __name__ == '__main__':
    main()