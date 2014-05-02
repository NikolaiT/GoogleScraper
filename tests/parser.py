__author__ = 'nikolai'

import logging
import os
import zlib
import re
import sqlite3
import time
from GoogleScraper import setup_logger
from GoogleScraper import Google_SERP_Parser
from GoogleScraper import maybe_create_db

setup_logger(logging.INFO)

path_to_kws = 'kwfiles/10k'

conn = maybe_create_db()
cursor = conn.cursor()

r = re.compile(r'<title>(?P<kw>.*?) - Google Search</title>')

def _parse_links(kw, html):
    """Parses links with Google_SERP_Parser"""
    parser = Google_SERP_Parser(html)
    results = parser.links
    cursor.execute(
        'INSERT INTO serp_page (requested_at, num_results, num_results_for_kw_google, search_query, requested_by) VALUES(?, ?, ?, ?, ?)',
        (time.asctime(), len(results), parser.num_results(),  kw, '127.0.0.1'))
    lastrowid = cursor.lastrowid
    cursor.executemany('''INSERT INTO link
    (search_query,
     title,
     url,
     snippet,
     rank,
     domain,
     serp_id) VALUES(?, ?, ?, ?, ?, ?, ?)''',
    [(kw,
      result.link_title,
      result.link_url.geturl(),
      result.link_snippet,
      result.link_position,
      result.link_url.hostname) +
     (lastrowid, ) for result in results])

if __name__ == '__main__':
    search_kws = sorted(open(path_to_kws, 'r').read().split('\n'), key=str.lower)
    kws = []
    for root, dirs, files in os.walk('.scrapecache'):
        for file in files:
            with open(os.path.join(root, file), 'rb') as bf:
                html = zlib.decompress(bf.read()).decode()
                kw = r.search(html).group('kw')
                print(kw)
                kws.append(kw)
                _parse_links(kw, html)
    conn.commit()
    conn.close()

    print(len(set(kws).intersection((search_kws))))
    assert set(kws) == set(search_kws)