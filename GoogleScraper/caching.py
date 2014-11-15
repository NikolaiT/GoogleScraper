# -*- coding: utf-8 -*-

import os
import time
import itertools
import hashlib
import gzip
import bz2
import sys
import re
import logging
import functools
from GoogleScraper.config import Config

"""
GoogleScraper is a complex application and thus searching is error prone. While developing,
you may need to repeat the same searches several times and you might end up being banned by
the search engine providers. This is why all searches are chached by default.

Every SERP page is cached in a separate file. In the future, it might be more straightforward to
cache scraping jobs in archives (zip files).

What determines the uniqueness of a SERP result?
- The complete url (because there the search query and the params are included)
- The scrape mode: Raw Http might request different resources than a browser does.
- Optionally the http headers (because different User-Agents can yield different results)

Using these three pieces of information would guarantee that we cache only unique requests,
but then we couldn't read back the information of the cache files, since these parameters
are only available at runtime of the scrapers. So we have to be satisfied with the
keyword, search_engine and scrapemode as entropy params.
"""

logger = logging.getLogger('GoogleScraper')

ALLOWED_COMPRESSION_ALGORITHMS = ('gz', 'bz2')

class InvalidConfigurationFileException(Exception):
    """
    Used when the cache module cannot
    determine the kind (compression for instance) of a
    configuration file
    """
    pass


class CompressedFile(object):
    """Read and write the data of a compressed file.
    Used to cache files for GoogleScraper.s

    Supported algorithms: gz, bz2

    >>> import os
    >>> f = CompressedFile('gz', '/tmp/test.txt')
    >>> f.write('hello world')
    >>> assert os.path.exists('/tmp/test.txt.gz')

    >>> f2 = CompressedFile('gz', '/tmp/test.txt.gz')
    >>> assert f2.read() == 'hello world'
    """

    def __init__(self, algorithm, path):
        """Create a new compressed file to read and write data to.

        Args:
            algorithm: Which algorithm to use.
            path: A valid file path to the file to read/write. Depends
                on the action called.
        """

        assert algorithm in ALLOWED_COMPRESSION_ALGORITHMS,\
            '{algo} is not an supported compression utility'.format(algo=algorithm)

        self.algorithm = algorithm
        if path.endswith(algorithm):
            self.path = path
        else:
            self.path = '{path}.{ext}'.format(path=path, ext=algorithm)

        self.readers = {
            'gz': self.read_gz,
            'bz2': self.read_bz2
        }
        self.writers = {
            'gz': self.write_gz,
            'bz2': self.write_bz2
        }

    def read_gz(self):
        with gzip.open(self.path, 'rb') as f:
            return f.read()

    def read_bz2(self):
        with bz2.open(self.path, 'rb') as f:
            return f.read()

    def write_gz(self, data):
        with gzip.open(self.path, 'wb') as f:
            f.write(data)

    def write_bz2(self, data):
        with bz2.open(self.path, 'wb') as f:
            f.write(data)

    def read(self):
        assert os.path.exists(self.path)
        return self.readers[self.algorithm]()

    def write(self, data):
        if not isinstance(data, bytes):
            data = data.encode()
        return self.writers[self.algorithm](data)


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
    cachedir = Config['GLOBAL'].get('cachedir', '.scrapecache')
    if os.path.exists(cachedir):
        for fname in os.listdir(cachedir):
            path = os.path.join(cachedir, fname)
            if time.time() > os.path.getmtime(path) + (60 * 60 * Config['GLOBAL'].getint('clean_cache_after', 12)):
                # Remove the whole directory if necessary
                if os.path.isdir(path):
                    import shutil
                    shutil.rmtree(path)
                else:
                    os.remove(os.path.join(cachedir, fname))


def cached_file_name(keyword, search_engine, scrapemode):
    """Make a unique file name from the search engine search request.

    Important! The order of the sequence is darn important! If search queries have the same
    words but in a different order, they are unique searches.

    Args:
        keyword: The keyword that was used in the search.
        search_engine: The search engine the keyword was scraped for.
        scrapemode: The scrapemode that was used.

    Returns:
        A unique file name based on the parameters of the search request.

    """
    assert isinstance(keyword, str), 'Keyword {} must be a string'.format(keyword)
    assert isinstance(search_engine, str), 'Seach engine {} must be a string'.format(search_engine)
    assert isinstance(scrapemode, str), 'Scapemode {} needs to be a string'.format(scrapemode)

    unique = [keyword, search_engine, scrapemode]

    sha = hashlib.sha256()
    sha.update(b''.join(str(s).encode() for s in unique))
    return '{file_name}.{extension}'.format(file_name=sha.hexdigest(), extension='cache')


@if_caching
def get_cached(keyword, search_engine, scrapemode):
    """Loads a cached SERP result.

    Args:
        keyword: The keyword that was used in the search.
        search_engine: The search engine the keyword was scraped for.
        scrapemode: The scrapemode that was used.

    Returns:
        The contents of the HTML that was shipped while searching. False if there couldn't
        be found a file based on the above params.

    """
    fname = cached_file_name(keyword, search_engine, scrapemode)

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
def read_cached_file(path):
    """Read a zipped or unzipped.

    The compressing schema is determined by the file extension. For example
    a file that ends with .gz needs to be gunzipped.

    Supported algorithms:
    gzip, and bzip2

    Args:
        path: The path to the cached file.

    Returns:
        The data of the cached file.

    Raises:
        InvalidConfigurationFileException: When the type of the cached file
            cannot be determined.
    """

    ext = path.split('.')[-1]

    # The path needs to have an extension in any case.
    # When uncompressed, ext is 'cache', else it is the
    # compressing scheme file ending like .gz or .zip ...
    assert ext

    if ext == 'cache':
        with open(path, 'r') as fd:
            try:
                data = fd.read()
                return data
            except UnicodeDecodeError as e:
                # If we get this error, the cache files are probably
                # compressed but the 'compress_cached_files' flag was
                # set to False. Try to decompress them, but this may
                # lead to a infinite recursion. This isn't proper coding,
                # but convenient for the end user.
                Config.set('GLOBAL', 'compress_cached_files', True)
    elif ext in ALLOWED_COMPRESSION_ALGORITHMS:
        f = CompressedFile(ext)
        return f.read(path)
    else:
        raise InvalidConfigurationFileException('"{path}" is a invalid configuration file.')


@if_caching
def cache_results(data, keyword, search_engine, scrapemode):
    """Stores the data in a file.

    The file name is determined by the parameters kw, url and params.
    See cached_file_name() for more information.

    This will always write(overwrite) the cached file. If compress_cached_files is
    True, the page is written in bytes (obviously).

    Args:
        data: The data to cache.
        keyword: The keyword that was used in the search.
        search_engine: The search engine the keyword was scraped for.
        scrapemode: The scrapemode that was used.
    """
    fname = cached_file_name(keyword, search_engine, scrapemode)
    cachedir = Config['GLOBAL'].get('cachedir', '.scrapecache')
    path = os.path.join(cachedir, fname)

    if Config['GLOBAL'].getboolean('compress_cached_files'):
        algorithm = Config['GLOBAL'].get('compressing_algorithm', 'gz')
        f = CompressedFile(algorithm, path)
        f.write(data)
    else:
        with open(path, 'w') as fd:
            if isinstance(data, bytes):
                fd.write(data.decode())
            else:
                fd.write(data)


def _get_all_cache_files():
    """Return all files found in the cachedir.

    Returns:
        All files that have the string "cache" in it within the cache directory.
        Files are either uncompressed filename.cache or are compressed with a
        compression algorithm: "filename.cache.zip"
    """
    files = set()
    for dirpath, dirname, filenames in os.walk(Config['GLOBAL'].get('cachedir', '.scrapecache')):
        for name in filenames:
            if 'cache' in name:
                files.add(os.path.join(dirpath, name))
    return files


def _caching_is_one_to_one(keywords, search_engine, scrapemode):
    """Check whether all keywords map to a unique file name.

    Args:
        keywords: All keywords for which to check the uniqueness of the hash
        search_engine: The search engine the keyword was scraped for.
        scrapemode: The scrapemode that was used.

    Returns:
        True if all keywords map to a unique hash and False if not.
    """
    mappings = {}
    for kw in keywords:
        hash = cached_file_name(kw, search_engine, scrapemode)
        if hash not in mappings:
            mappings.update({hash: [kw, ]})
        else:
            mappings[hash].append(kw)

    duplicates = [v for k, v in mappings.items() if len(v) > 1]
    if duplicates:
        logger.info('Not one-to-one. {}'.format(duplicates))
        return False
    else:
        logger.info('one-to-one')
        return True


def parse_all_cached_files(keywords, session, try_harder=False):
    """Walk recursively through the cachedir (as given by the Config) and parse all cached files.

    Args:
        identifying_list: A list of list with elements that identify the result. The consist of the keyword, search_engine, scrapemode.
        session: An sql alchemy session to add the entities
        try_harder: If there is a cache file that cannot be mapped to a keyword, read it and try it again and try to
                    extract the search query from the html.

    Returns:
        A list of keywords that couldn't be parsed and which need to be scraped anew.
    """
    google_query_needle = re.compile(r'<title>(?P<kw>.*?) - Google Search</title>')
    files = _get_all_cache_files()
    mapping = {}
    for kw in keywords:
        key = cached_file_name(
            kw,
            Config['SCRAPING'].get('search_engine'),
            Config['SCRAPING'].get('scrapemethod')
        )
        mapping[key] = kw

    diff = set(mapping.keys()).difference({os.path.split(path)[1] for path in files})
    logger.info('{} cache files found in {}'.format(len(files), Config['GLOBAL'].get('cachedir')))
    logger.info('{}/{} keywords have been cached and are ready to get parsed. {} remain to get scraped.'.format(
        len(keywords) - len(diff), len(keywords), len(diff)))

    for path in files:
        fname = os.path.split(path)[1]
        query = mapping.get(fname, None)
        if query:
            mapping.pop(fname)
        if not query and try_harder:
            data = read_cached_file(path)
            m = google_query_needle.search(data)
            if m:
                query = m.group('kw').strip()
                if query in mapping.values():
                    logger.debug('The request with the keywords {} was wrongly cached.'.format(query))
                else:
                    continue
            else:
                continue

    # return the remaining keywords to scrape
    return mapping.values()


def fix_broken_cache_names(url, search_engine, scrapemode):
    """Fix broken cache names.

    Args:
        url: A list of strings to add to each cached_file_name() call.
    """
    files = _get_all_cache_files()
    logger.debug('{} cache files found in {}'.format(len(files), Config['GLOBAL'].get('cachedir', '.scrapecache')))
    r = re.compile(r'<title>(?P<kw>.*?) - Google Search</title>')

    for i, path in enumerate(files):
        fname = os.path.split(path)[1].strip()
        data = read_cached_file(path)
        infilekws = r.search(data).group('kw')
        realname = cached_file_name(infilekws, search_engine, scrapemode)
        if fname != realname:
            logger.debug(
                'The search query in the title element in file {} differ from that hash of its name. Fixing...'.format(
                    path))
            src = os.path.abspath(path)
            dst = os.path.abspath(os.path.join(os.path.split(path)[0], realname))
            logger.debug('Renamed from {} => {}'.format(src, dst))
            os.rename(src, dst)
    logger.debug('Renamed {} files.'.format(i))


def cached(f, attr_to_cache=None):
    """Decorator that makes return value of functions cachable.
    
    Any function that returns a value and that is decorated with
    cached will be supplied with the previously calculated result of
    an earlier call. The parameter name with the cached value may 
    be set with attr_to_cache.
    
    Args:
        attr_to_cache: The name of attribute whose data
                        is cachable.
    
    Returns: The modified and wrapped function.
    """
    def wraps(*args, **kwargs):
        cached_value = get_cached(*args, params=kwargs)
        if cached_value:
            value = f(*args, attr_to_cache=cached_value, **kwargs)
        else:
            # Nothing was cached for this attribute
            value = f(*args, attr_to_cache=None, **kwargs)
            cache_results(value, *args, params=kwargs)
    return wraps
    
if __name__ == '__main__':
    import doctest
    doctest.testmod()
