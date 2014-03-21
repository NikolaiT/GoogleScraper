__author__ = 'nikolai'

import sqlite3
import threading
import os
import random
import time

DB = 'results.db'

def maybe_create_db():
    if os.path.exists(DB) and os.path.getsize(DB) > 0:
        conn = sqlite3.connect(DB, check_same_thread=False)
        cursor = conn.cursor()
        return (conn, cursor)
    else:
        # set that bitch up the first time
        conn = sqlite3.connect(DB, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE serp_page
        (id INTEGER PRIMARY KEY NOT NULL, requested_at TEXT NOT NULL,
           num_results INTEGER NOT NULL, search_query TEXT NOT NULL)''')
        cursor.execute('''CREATE TABLE results
        (id INTEGER PRIMARY KEY NOT NULL, link_title TEXT NOT NULL,
           link_snippet TEXT NOT NULL, link_url TEXT NOT NULL,
           serp_id INTEGER NOT NULL, FOREIGN KEY(serp_id) REFERENCES serp_page(id))''')

        conn.commit()
        return (conn, cursor)

class TestThread(threading.Thread):
    def __init__(self, cursor, *args):
        self.cursor = cursor
        super().__init__(*args)
    def run(self):
        for i in range(10):
            time.sleep(.2)
            self.__write()
        for i in range(5):
            time.sleep(.5)
            self.__read()
    def __str__(self):
        return "Thread number {}".format(self.ident)
    def __write(self):
        self.cursor.execute('INSERT INTO serp_page(requested_at, num_results, search_query) VALUES(?, ?, ?)',
                            (time.asctime(), random.randint(10, 100), 'somekey'))
    def __read(self):
        print(self.cursor.execute('SELECT * FROM serp_page').fetchone())


# script

conn, cursor = maybe_create_db()

# some threads
threads = [TestThread(cursor) for i in range(10)]

for t in threads:
    t.start()

for t in threads:
    t.join()
