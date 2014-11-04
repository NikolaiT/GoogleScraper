# -*- coding: utf-8 -*-

import os
import time
import itertools
import hashlib
import zlib
import gzip
import bz2
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

ALLOWED_COMPRESSION_ALGORITHMS = ('zip', 'gz', 'bz2')

class InvalidConfigurationFileException(Exception):
    """
    Used when the cache module cannot
    determine the kind (compression for instance) of a
    configuration file
    """
    pass


class CompressedFile(object):
    """Open and return the data of a compressed file

    Supported algorithms: zlib, gz, bz2

    >>> import os
    >>> f = CompressedFile('zip', '/tmp/test.txt')
    >>> f.write('hello world')
    >>> assert os.path.exists('/tmp/test.txt.zip')

    >>> f2 = CompressedFile('zip', '/tmp/test.txt.zip')
    >>> assert f2.read() == 'hello world'
    """

    def __init__(self, algorithm, path):
        """Create a new compressed file to read and write data to.

        Args:
            algorithm: Which algorithm to use.
            path: A valid file path to the file to read/write. Depends
                on the action called.
        """

        assert algorithm in ALLOWED_COMPRESSION_ALGORITHMS, algorithm

        self.algorithm = algorithm
        if path.endswith(algorithm):
            self.path = path
        else:
            self.path = '{path}.{ext}'.format(path=path, ext=algorithm)

        self.data = b''
        self.readers = {
            'zip': self.read_zlib,
            'gz': self.read_gz,
            'bzw': self.read_bz2
        }
        self.writers = {
            'zip': self.write_zlib,
            'gz': self.write_gz,
            'bzw': self.write_bz2
        }

    def _read(self):
        if not self.data:
            with open(self.path, 'rb') as fd:
                self.data = fd.read()

    def _write(self, data):
        with open(self.path, 'wb') as f:
            f.write(data)

    def read_zlib(self):
        self._read()
        try:
            data = zlib.decompress(self.data).decode()
            return data
        except zlib.error as e:
            raise e

    def read_gz(self):
        try:
            file = gzip.GzipFile(self.path)
            return file.read()
        except Exception as e:
            raise

    def read_bz2(self):
        raise NotImplemented('yet')

    def write_zlib(self, data):
        if not isinstance(data, bytes):
            data = data.encode()

        try:
            self._write(zlib.compress(data, 5))
        except zlib.error as e:
            raise e

    def write_gz(self):
        pass

    def write_bz2(self):
        pass

    def read(self):
        assert os.path.exists(self.path)
        return self.readers[self.algorithm]()

    def write(self, data):
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
    for fname in os.listdir(Config['GLOBAL'].get('cachedir', '.scrapecache')):
        path = os.path.join(Config['GLOBAL'].get('cachedir'), fname)
        if time.time() > os.path.getmtime(path) + (60 * 60 * Config['GLOBAL'].getint('clean_cache_after', 12)):
            # Remove the whole directory if necessary
            if os.path.isdir(path):
                import shutil

                shutil.rmtree(path)
            else:
                os.remove(os.path.join(Config['GLOBAL'].get('cachedir'), fname))


def cached_file_name(kw, url, params={}):
    """Make a unique file name from the Google search request.

    Important! The order of the sequence is darn important! If search queries have the same
    words but in a different order, they are unique searches.

    Args:
        kw: The search keyword
        url: The url for the search (without params)
        params: The parameters used in the search url without the "q" parameter. Optional and may be empty.

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
def get_cached(kw, url, params={}):
    """Loads a cached SERP result.

    Args:
        kw: The keyword used in the search request. Value of "q" parameter.
        url: The base search url used while requesting.
        params: The search parameters as a dictionary, optional.

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
def read_cached_file(path):
    """Read a zipped or unzipped.

    The compressing schema is determined by the file extension. For example
    a file that ends with .zip needs to be unzipped.

    Supported algorithms:
    zlib, gzip, and bzip2

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
def cache_results(data, kw, url, params={}):
    """Stores the data in a file.

    The file name is determined by the parameters kw, url and params.
    See cached_file_name() for more information.

    This will always write(overwrite) the cached file. If compress_cached_files is
    True, the page is written in bytes (obviously).

    Args:
        data: The data to cache.
        kw: The search keyword
        url: The search url for the search request
        params: The search params, Optional
    Returns:
        Nothing.
    """
    fname = cached_file_name(kw, url, params)
    cachedir = Config['GLOBAL'].get('cachedir', '.scrapecache')
    path = os.path.join(cachedir, fname)

    if Config['GLOBAL'].getboolean('compress_cached_files'):
        algorithm = Config['GLOBAL'].get('compressing_algorithm', 'zip')
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
        compresssion algorithm: "filename.cache.zip"
    """
    files = set()
    for dirpath, dirname, filenames in os.walk(Config['GLOBAL'].get('cachedir')):
        for name in filenames:
            if 'cache' in name:
                files.add(os.path.join(dirpath, name))
    return files


def _caching_is_one_to_one(keywords, url):
    """Check whether all keywords map to a unique file name.

    Args:
        keywords: All keywords for which to check the uniqueness of the hash
        url: The search url

    Returns:
        True if all keywords map to a unique hash and False if not.
    """
    mappings = {}
    for kw in keywords:
        hash = cached_file_name(kw, url)
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


def parse_all_cached_files(keywords, conn, url, try_harder=True):
    """Walk recursively through the cachedir (as given by the Config) and parse all cached files.

    Args:
        keywords: A sequence of keywords which were used as search query strings.
        conn: A sqlite3 database connection.
        try_harder: If there is a cache file that cannot be mapped to a keyword, read it and try it again with the query.

    Returns:
        A list of keywords that couldn't be parsed and which need to be scraped anew.
    """
    r = re.compile(r'<title>(?P<kw>.*?) - Google Search</title>')
    files = _get_all_cache_files()
    mapping = {cached_file_name(kw, url): kw for kw in keywords}
    diff = set(mapping.keys()).difference({os.path.split(path)[1] for path in files})
    logger.info('{} cache files found in {}'.format(len(files), Config['GLOBAL'].get('cachedir')))
    logger.info('{}/{} keywords have been cached and are ready to get parsed. {} remain to get scraped.'.format(
        len(keywords) - len(diff), len(keywords), len(diff)))

    if Config['GLOBAL'].getboolean('simulate'):
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


def fix_broken_cache_names(url):
    """Fix broken cache names.

    Args:
        url: A list of strings to add to each cached_file_name() call.

    Returns;
        Nothing.
    """
    files = _get_all_cache_files()
    logger.debug('{} cache files found in {}'.format(len(files), Config['GLOBAL'].get('cachedir', '.scrapecache')))
    r = re.compile(r'<title>(?P<kw>.*?) - Google Search</title>')

    for i, path in enumerate(files):
        fname = os.path.split(path)[1].strip()
        data = read_cached_file(path)
        infilekws = r.search(data).group('kw')
        realname = cached_file_name(infilekws, url)
        if fname != realname:
            logger.debug(
                'The search query in the title element in file {} differ from that hash of its name. Fixing...'.format(
                    path))
            src = os.path.abspath(path)
            dst = os.path.abspath(os.path.join(os.path.split(path)[0], realname))
            logger.debug('Renamed from {} => {}'.format(src, dst))
            os.rename(src, dst)
    logger.debug('Renamed {} files.'.format(i))


if __name__ == '__main__':
    import doctest
    doctest.testmod()