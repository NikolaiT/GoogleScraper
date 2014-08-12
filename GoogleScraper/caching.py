#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import time
import itertools
import hashlib
import zlib
import sys
import re
import logging
from GoogleScraper.config import get_config
from GoogleScraper.results import parse_links

logger = logging.getLogger('GoogleScraper')
Config = get_config()

def maybe_clean_cache():
    """Delete all .cache files in the cache directory that are older than 12 hours."""
    for fname in os.listdir(Config['GLOBAL'].get('cachedir')):
        path = os.path.join(Config['GLOBAL'].get('cachedir'), fname)
        if time.time() > os.path.getmtime(path) + (60 * 60 * Config['GLOBAL'].getint('clean_cache_after')):
            if os.path.isdir(path):
                import shutil
                shutil.rmtree(path)
            else:
                os.remove(os.path.join(Config['GLOBAL'].get('cachedir'), fname))


def cached_file_name(kw, url=Config['SELENIUM']['sel_scraper_base_url'], params={}):
    """Make a unique file name based on the values of the google search parameters.

        kw -- The search keyword
        url -- The url for the search (without params)
        params -- GET params in the URL string

        If search_params is a dict, include both keys/values in the calculation of the
        file name. If a sequence is provided, just use the elements of the sequence to
        build the hash.

        Important! The order of the sequence is darn important! If search queries have same
        words but in a different order, they are individua searches.
    """
    assert isinstance(kw, str), kw
    assert isinstance(url, str), url
    if params:
        assert isinstance(params, dict)

    if params:
        unique = list(itertools.chain([kw], url, params.keys(), params.values()))
    else:
        unique = list(itertools.chain([kw], url))

    sha = hashlib.sha256()
    sha.update(b''.join(str(s).encode() for s in unique))
    return '{}.{}'.format(sha.hexdigest(), 'cache')

def get_cached(kw, url=Config['SELENIUM']['sel_scraper_base_url'], params={}, cache_dir=''):
    """Loads a cached search results page from CACHEDIR/fname.cache

    It helps in testing and avoid requesting
    the same resources again and again (such that google may
    recognize us as what we are: Sneaky SEO crawlers!)

    --search_params The parameters that identify the resource
    --decompress What algorithm to use for decompression
    """

    if Config['GLOBAL'].getboolean('do_caching'):
        fname = cached_file_name(kw, url, params)

        if os.path.exists(cache_dir) and cache_dir:
            cdir = cache_dir
        else:
            cdir = Config['GLOBAL'].get('cachedir')

        try:
            if fname in os.listdir(cdir):
                # If the cached file is older than 12 hours, return False and thus
                # make a new fresh request.
                modtime = os.path.getmtime(os.path.join(cdir, fname))
                if (time.time() - modtime) / 60 / 60 > Config['GLOBAL'].getint('clean_cache_after'):
                    return False
                path = os.path.join(cdir, fname)
                return read_cached_file(path)
        except FileNotFoundError as err:
            raise Exception('Unexpected file not found: {}'.format(err.msg))

    return False


def read_cached_file(path, n=2):
    """Read a zipped or unzipped cache file."""
    if Config['GLOBAL'].getboolean('do_caching'):
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

def cache_results(html, kw, url=Config['SELENIUM']['sel_scraper_base_url'], params={}):
    """Stores a html resource as a file in Config['GLOBAL'].get('cachedir')/fname.cache

    This will always write(overwrite) the cache file. If compress_cached_files is
    True, the page is written in bytes (obviously).
    """
    if Config['GLOBAL'].getboolean('do_caching'):
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