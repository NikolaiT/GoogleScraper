# -*- coding: utf-8 -*-

import os
import time
import itertools
import hashlib
import zlib
import sys
import re
import logging
import functools
from GoogleScraper.config import Config
from GoogleScraper.res import parse_links

"""
GoogleScraper is a complex application and thus searching is error prone. While developing,
you may need to repeat the same searches several times and you might end being banned by
Google. This is why all searches are chached by default.

Every SERP page is cached in a separate file. In the future, it might be more straightforward to
merge several logically adjacent search result HTML code together.
"""

logger = logging.getLogger('GoogleScraper')


def maybe_create_cache_dir():
    if Config['GLOBAL'].getboolean('do_caching'):
        cd = Config['GLOBAL'].get('cachedir', '.scrapecache')
        if not os.path.exists(cd):
            os.mkdirs(cd)

def if_caching(f):
    @functools.wraps(f)
    def wraps(*args, **kwargs):
        if Config['GLOBAL'].getboolean('do_caching'):
            maybe_create_cache_dir()
            return f(*args, **kwargs)
    return wraps

def maybe_clean_cache():
    """Clean the cache.

     Clean all cached searches (the obtained html code) in the cache directory iff
     the respective files are older than specified in the configuration. Defaults to 12 hours.
     """
    for fname in os.listdir(Config['GLOBAL'].get('cachedir', '.scrapecache')):
        path = os.path.join(Config['GLOBAL'].get('cachedir'), fname)
        if time.time() > os.path.getmtime(path) + (60 * 60 * Config['GLOBAL'].getint('clean_cache_after', 12)):
            # Remove the whole directory if necessary
            if os.path.isdir(path):
                import shutil
                shutil.rmtree(path)
            else:
                os.remove(os.path.join(Config['GLOBAL'].get('cachedir'), fname))


def cached_file_name(kw, url, params):
    """Make a unique file name from the Google search request.

    Important! The order of the sequence is darn important! If search queries have the same
    words but in a different order, they are unique searches.

    Args:
        kw: The search keyword
        url: The url for the search (without params)
        params: The parameters used in the search url without the "q" parameter.

    Returns:
        A unique file name based on the parameters of the search request.

    """
    assert isinstance(kw, str), kw
    assert isinstance(url, str), url
    assert isinstance(params, dict)

    unique = list(itertools.chain([kw, ], url, params.keys(), params.values()))

    sha = hashlib.sha256()
    sha.update(b''.join(str(s).encode() for s in unique))
    return '{file_name}.{extension}'.format(file_name=sha.hexdigest(), extension='cache')


@if_caching
def get_cached(kw, url, params):
    """Loads a cached SERP result.

    Args:
        kw: The keyword used in the search request. Value of "q" parameter.
        url: The base search url used while requesting.
        params: The search parameters as a dictionary.

    Returns:
        The contents of the HTML that was shipped while searching. False if there couldn't
        be found a file based on the above params.

    """
    fname = cached_file_name(kw, url, params)

    cdir = Config['GLOBAL'].get('cachedir', '.scrapecache')

    if fname in os.listdir(cdir):
        # If the cached file is older than 12 hours, return False and thus
        # make a new fresh request.
        try:
            modtime = os.path.getmtime(os.path.join(cdir, fname))
        except FileNotFoundError as err:
            return False

        if (time.time() - modtime) / 60 / 60 > Config['GLOBAL'].getint('clean_cache_after', 12):
            return False

        path = os.path.join(cdir, fname)
        return read_cached_file(path)
    else:
        return False

@if_caching
def read_cached_file(path, n=2):
    """Read a zipped or unzipped cache file.


    """
    assert n != 0

    if Config['GLOBAL'].getboolean('compress_cached_files'):
        with open(path, 'rb') as fd:
            try:
                data = zlib.decompress(fd.read()).decode()
                return data
            except zlib.error:
                Config.set('GLOBAL', 'compress_cached_files',  False)
                return read_cached_file(path, n-1)
    else:
        with open(path, 'r') as fd:
            try:
                data = fd.read()
                return data
            except UnicodeDecodeError as e:
                # If we get this error, the cache files are probably
                # compressed but the 'compress_cached_files' flag was
                # set to false. Try to decompress them, but this may
                # lead to a infinite recursion. This isn't proper coding,
                # but convenient for the end user.
                Config.set('GLOBAL', 'compress_cached_files', True)

                return read_cached_file(path, n-1)

@if_caching
def cache_results(html, kw, url=Config['SELENIUM']['sel_scraper_base_url'], params={}):
    """Stores a html resource as a file in the current cachedirectory.

    This will always write(overwrite) the cache file. If compress_cached_files is
    True, the page is written in bytes (obviously).
    """
    fname = cached_file_name(kw, url=url, params=params)
    path = os.path.join(Config['GLOBAL'].get('cachedir'), fname)

    if Config['GLOBAL'].getboolean('compress_cached_files'):
        with open(path, 'wb') as fd:
            if isinstance(html, bytes):
                fd.write(zlib.compress(html, 5))
            else:
                fd.write(zlib.compress(html.encode('utf-8'), 5))
    else:
        with open(os.path.join(Config['GLOBAL'].get('cachedir'), fname), 'w') as fd:
            if isinstance(html, bytes):
                fd.write(html.decode())
            else:
                fd.write(html)


def _get_all_cache_files():
    """Return all files found in Config['GLOBAL'].get('cachedir')."""
    files = set()
    for dirpath, dirname, filenames in os.walk(Config['GLOBAL'].get('cachedir')):
        for name in filenames:
            files.add(os.path.join(dirpath, name))
    return files

def _caching_is_one_to_one(keywords, url=Config['SELENIUM']['sel_scraper_base_url']):
    mappings = {}
    for kw in keywords:
        hash = cached_file_name(kw, url)
        if hash not in mappings:
            mappings.update({hash: [kw, ]})
        else:
            mappings[hash].append(kw)

    duplicates = [v for k, v in mappings.items() if len(v) > 1]
    if duplicates:
        print('Not one-to-one. Hash function sucks. {}'.format(duplicates))
    else:
        print('one-to-one')
    sys.exit(0)

def parse_all_cached_files(keywords, conn, url=Config['SELENIUM']['sel_scraper_base_url'], try_harder=True, simulate=False):
    """Walk recursively through the cachedir (as given by the Config) and parse cache files.

    Arguments:
    keywords -- A sequence of keywords which were used as search query strings.

    Keyword arguments:
    dtokens -- A list of strings to add to each cached_file_name() call.
    with the contents of the <title></title> elements if necessary.
    conn -- A sqlite3 database connection.
    try_harder -- If there is a cache file that cannot be mapped to a keyword, read it and try it again with the query.

    Return:
    A list of keywords that couldn't be parsed and which need to be scraped freshly.
    """
    r = re.compile(r'<title>(?P<kw>.*?) - Google Search</title>')
    files = _get_all_cache_files()
    mapping = {cached_file_name(kw, url): kw for kw in keywords}
    diff = set(mapping.keys()).difference({os.path.split(path)[1] for path in files})
    logger.info('{} cache files found in {}'.format(len(files), Config['GLOBAL'].get('cachedir')))
    logger.info('{}/{} keywords have been cached and are ready to get parsed. {} remain to get scraped.'.format(len(keywords)-len(diff), len(keywords), len(diff)))
    if simulate:
        sys.exit(0)
    for path in files:
        fname = os.path.split(path)[1]
        query = mapping.get(fname)
        data = read_cached_file(path)
        if not query and try_harder:
            m = r.search(data)
            if m:
                query = m.group('kw').strip()
                if query in mapping.values():
                    logger.debug('The request with the keywords {} was wrongly cached.'.format(query))
                else:
                    continue
            else:
                continue
        parse_links(data, conn.cursor(), query)
        mapping.pop(fname)
    conn.commit()

    # return the remaining keywords to scrape
    return mapping.values()

def fix_broken_cache_names(url=Config['SELENIUM']['sel_scraper_base_url']):
    """Fix the fucking broken cache fuck shit.

    @param url: A list of strings to add to each cached_file_name() call.
    @return: void you cocksucker
    """
    files = _get_all_cache_files()
    logger.debug('{} cache files found in {}'.format(len(files), Config['GLOBAL'].get('cachedir')))
    r = re.compile(r'<title>(?P<kw>.*?) - Google Search</title>')

    for i, path in enumerate(files):
        fname = os.path.split(path)[1].strip()
        data = read_cached_file(path)
        infilekws = r.search(data).group('kw')
        realname = cached_file_name(infilekws, url)
        if fname != realname:
            logger.debug('The search query in the title element in file {} differ from that hash of its name. Fixing...'.format(path))
            src = os.path.abspath(path)
            dst = os.path.abspath(os.path.join(os.path.split(path)[0], realname))
            logger.debug('Renamed from {} => {}'.format(src, dst))
            os.rename(src, dst)
    logger.debug('Renamed {} files.'.format(i))