#!/usr/bin/python3

import os
import time
import sqlite3
from GoogleScraper.config import get_config
from GoogleScraper.parsing import GoogleParser

Config = get_config()

def maybe_create_db():
    """Creates a little sqlite database to include at least the columns:
        - query
       - rank (1-10)
       - title
       - snippet
       - url
       - domain

    Test sql query: SELECT L.title, L.snippet, SP.search_query FROM link AS L LEFT JOIN serp_page AS SP ON L.serp_id = SP.id
    """
    # Save the database to a unique file name (with the timestamp as suffix)
    Config.set('GLOBAL', 'db', Config['GLOBAL'].get('db').format(asctime=str(time.asctime()).replace(' ', '_').replace(':', '-')))

    if os.path.exists(Config['GLOBAL'].get('db')) and os.path.getsize(Config['GLOBAL'].get('db')) > 0:
        conn = sqlite3.connect(Config['GLOBAL'].get('db'), check_same_thread=False)
        cursor = conn.cursor()
        return conn
    else:
        # set that bitch up the first time
        conn = sqlite3.connect(Config['GLOBAL'].get('db'), check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE serp_page
        (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             page_number INT NOT NULL,
             requested_at TEXT NOT NULL,
             num_results INTEGER NOT NULL,
             num_results_for_kw_google TEXT,
             search_query TEXT NOT NULL,
             requested_by TEXT
         )''')
        cursor.execute('''
        CREATE TABLE link
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            snippet TEXT,
            url TEXT,
            domain TEXT,
            rank INTEGER NOT NULL,
            serp_id INTEGER NOT NULL,
            FOREIGN KEY(serp_id) REFERENCES serp_page(id)
        )''')

        conn.commit()
        return conn


def parse_links(data, conn, kw, page_num=1, ip='127.0.0.1'):
    """Insert parsed data into the database. High level parsing function.

    Args:
    conn -- Either a sqlite3 cursor or connection object. If called in threads, make sure
    to wrap this function in some kind of synchronization functionality.
    """
    parser = GoogleParser(data)
    results = parser.links
    conn.execute('''
        INSERT INTO serp_page
         (page_number, requested_at,
         num_results, num_results_for_kw_google,
         search_query, requested_by)
         VALUES(?, ?, ?, ?, ?, ?)''',
           (page_num, time.asctime(), len(results), parser.num_results() or '',  kw, ip))
    lastrowid = conn.lastrowid
    #logger.debug('Inserting in link: search_query={}, title={}, url={}'.format(kw, ))
    conn.executemany('''INSERT INTO link
    ( title,
     url,
     snippet,
     rank,
     domain,
     serp_id) VALUES(?, ?, ?, ?, ?, ?)''',
    [(
      result.link_title,
      result.link_url.geturl(),
      result.link_snippet,
      result.link_position,
      result.link_url.hostname) +
     (lastrowid, ) for result in results])