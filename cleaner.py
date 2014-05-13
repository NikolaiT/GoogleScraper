__author__ = 'nikolai'


from GoogleScraper import read_cached_file, cached_file_name
import sqlite3
import sys
import os
import re

map = {}
for dirpath, dirnames, filenames in os.walk('.scrapecache/'):
    for file in filenames:
        map.update({file: os.path.join(dirpath, file)})

def getfile(kw):
    fname = cached_file_name(kw)
    try:
        val = map[fname]
    except KeyError:
        val = ''
    finally:
        return val


def inspect_files():
    r = re.compile(r'<title>(?P<kw>.*?) - Google Search</title>')
    N = lambda x, html: len([m.group() for m in re.finditer(html, x)])

    for file in os.listdir('.scrapecache'):
        if os.path.isdir(file):
            continue
        html = read_cached_file(os.path.join('.scrapecache', file))
        title = r.search(html).group('kw')
        longest, second, *rest = reversed(sorted([word for word in title.split(' ')], key=len))
        print('{} appear {} times in {}'.format(longest, N(longest, html), file))
        print('{} appear {} times in {}'.format(second, N(second, html), file))
        print('*'*40)


if __name__ == '__main__':
    if len(sys.argv) not in range(2,4):
        print('Usage: {} [database]'.format(sys.argv[0]))
        sys.exit(0)

    connection = sqlite3.connect(sys.argv[1])
    cursor = connection.cursor()
    i = 0
    remove = set()
    for page in cursor.execute('SELECT L.title, L.snippet, SP.search_query FROM link AS L LEFT JOIN serp_page AS SP ON L.serp_id = SP.id').fetchall():
            title, snippet, query = page
            if query in remove:
                continue
            title = title.lower()
            snippet = snippet.lower()
            query = query.lower()
            longest = sorted([e for e in query.split(' ')], key=len)[-1]
            if longest not in title and longest not in snippet:
                i += 1
                remove.add(getfile(query))
                print('[{}] would delete file for keyword={} ====> {}'.format(longest, query, getfile(query)))
                print(title, snippet, '\n' + '-'*20)
    print('would delete {} files'.format(len(remove)))
    if sys.argv[2] == 'drop':
        for file in remove:
            try:
                os.remove(file)
            except FileNotFoundError:
                pass
