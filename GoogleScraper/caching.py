# -*- coding: utf-8 -*-

import os
import time
import hashlib
import gzip
import bz2
import re
from sqlalchemy.orm.exc import NoResultFound
from GoogleScraper.database import SearchEngineResultsPage
from GoogleScraper.parsing import parse_serp
from GoogleScraper.output_converter import store_serp_result
import logging

"""
GoogleScraper is a complex application and thus searching is error prone. While developing,
you may need to repeat the same searches several times and you might end up being banned by
the search engine providers. This is why all searches are chached by default.

Every SERP page is cached in a separate file. In the future, it might be more straightforward to
cache scraping jobs in archives (zip files).

What determines the uniqueness of a SERP result?
- The complete url (because in URLs search queries and params are included)
- The scrape mode: Raw Http might request different resources than a browser.
- Optionally the http headers (because different User-Agents yield different results)

Using these three pieces of information would guarantee that we cache only unique requests,
but then we couldn't read back the information of the cache files, since these parameters
are only available at runtime of the scrapers. So we have to be satisfied with the
keyword, search_engine and scrapemode as identifying params.

How does caching work on a higher level?

Assume the user interrupted his scrape job at 1000/2000 keywords and there remain
quite some keywords to scrape for. Then the previously parsed 1000 results are already
stored in the database and shouldn't be added a second time.
"""

logger = logging.getLogger(__name__)

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
    >>> f = CompressedFile('/tmp/test.txt', algorithm='gz')
    >>> f.write('hello world')
    >>> assert os.path.exists('/tmp/test.txt.gz')

    >>> f2 = CompressedFile('/tmp/test.txt.gz', algorithm='gz')
    >>> assert f2.read() == 'hello world'
    """

    def __init__(self, path, algorithm='gz'):
        """Create a new compressed file to read and write data to.

        Args:
            algorithm: Which algorithm to use.
            path: A valid file path to the file to read/write. Depends
                on the action called.

        @todo: it would be a better approach to pass an Algorithm object instead of a string
        """

        self.algorithm = algorithm

        assert self.algorithm in ALLOWED_COMPRESSION_ALGORITHMS, \
            '{algo} is not an supported compression algorithm'.format(algo=self.algorithm)

        if path.endswith(self.algorithm):
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
            return f.read().decode()

    def read_bz2(self):
        with bz2.open(self.path, 'rb') as f:
            return f.read().decode()

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



class CacheManager():
    """
    Manages caching for GoogleScraper.
    """

    def __init__(self, config):
        self.config = config
        self.maybe_create_cache_dir()


    def maybe_create_cache_dir(self):
        if self.config.get('do_caching', True):
            cd = self.config.get('cachedir', '.scrapecache')
            if not os.path.exists(cd):
                os.mkdir(cd)


    def maybe_clean_cache(self):
        """
        Clean the cache.

        Clean all cached searches (the obtained html code) in the cache directory iff
        the respective files are older than specified in the configuration. Defaults to 12 hours.
        """
        cachedir = self.config.get('cachedir', '.scrapecache')
        if os.path.exists(cachedir):
            for fname in os.listdir(cachedir):
                path = os.path.join(cachedir, fname)
                if time.time() > os.path.getmtime(path) + (60 * 60 * int(self.config.get('clean_cache_after', 48))):
                    # Remove the whole directory if necessary
                    if os.path.isdir(path):
                        import shutil

                        shutil.rmtree(path)
                    else:
                        os.remove(os.path.join(cachedir, fname))


    def cached_file_name(self, keyword, search_engine, scrape_mode, page_number):
        """Make a unique file name from the search engine search request.

        Important! The order of the sequence is darn important! If search queries have the same
        words but in a different order, they are unique searches.

        Args:
            keyword: The keyword that was used in the search.
            search_engine: The search engine the keyword was scraped for.
            scrapemode: The scrapemode that was used.
            page_number: The number of the SERP page.

        Returns:
            A unique file name based on the parameters of the search request.

        """
        assert isinstance(keyword, str), 'Keyword {} must be a string'.format(keyword)
        assert isinstance(search_engine, str), 'Search engine {} must be a string'.format(search_engine)
        assert isinstance(scrape_mode, str), 'Scrapemode {} needs to be a string'.format(scrape_mode)
        assert isinstance(page_number, int), 'Page_number {} needs to be an int'.format(page_number)

        unique = [keyword, search_engine, scrape_mode, page_number]

        sha = hashlib.sha256()
        sha.update(b''.join(str(s).encode() for s in unique))
        return '{file_name}.{extension}'.format(file_name=sha.hexdigest(), extension='cache')


    def get_cached(self, keyword, search_engine, scrapemode, page_number):
        """Loads a cached SERP result.

        Args:
            keyword: The keyword that was used in the search.
            search_engine: The search engine the keyword was scraped for.
            scrapemode: The scrapemode that was used.
            page_number: page_number

        Returns:
            The contents of the HTML that was shipped while searching. False if there couldn't
            be found a file based on the above params.

        """
        if self.config.get('do_caching', False):
            fname = self.cached_file_name(keyword, search_engine, scrapemode, page_number)

            cdir = self.config.get('cachedir', '.scrapecache')

            if fname in os.listdir(cdir):
                # If the cached file is older than 12 hours, return False and thus
                # make a new fresh request.
                try:
                    modtime = os.path.getmtime(os.path.join(cdir, fname))
                except FileNotFoundError:
                    return False

                if (time.time() - modtime) / 60 / 60 > int(self.config('clean_cache_after', 48)):
                    return False

                path = os.path.join(cdir, fname)
                return self.read_cached_file(path)
            else:
                return False

    def read_cached_file(self, path):
        """Read a compressed or uncompressed file.

        The compressing schema is determined by the file extension. For example
        a file that ends with .gz needs to be gunzipped.

        Supported algorithms:
        gzip and bzip2

        Args:
            path: The path to the cached file.

        Returns:
            The data of the cached file as a string.

        Raises:
            InvalidConfigurationFileException: When the type of the cached file
                cannot be determined.
        """
        if self.config.get('do_caching', False):
            ext = path.split('.')[-1]

            # The path needs to have an extension in any case.
            # When uncompressed, ext is 'cache', else it is the
            # compressing scheme file ending like .gz or .bz2 ...
            assert ext in ALLOWED_COMPRESSION_ALGORITHMS or ext == 'cache', 'Invalid extension: {}'.format(ext)

            if ext == 'cache':
                with open(path, 'r') as fd:
                    try:
                        data = fd.read()
                        return data
                    except UnicodeDecodeError as e:
                        logger.warning(str(e))
                        # If we get this error, the cache files are probably
                        # compressed but the 'compress_cached_files' flag was
                        # set to False. Try to decompress them, but this may
                        # lead to a infinite recursion. This isn't proper coding,
                        # but convenient for the end user.
                        self.config['compress_cached_files'] = True
            elif ext in ALLOWED_COMPRESSION_ALGORITHMS:
                f = CompressedFile(path)
                return f.read()
            else:
                raise InvalidConfigurationFileException('"{}" is a invalid configuration file.'.format(path))


    def cache_results(self, parser, query, search_engine, scrape_mode, page_number, db_lock=None):
        """Stores the html of an parser in a file.

        The file name is determined by the parameters query, search_engine, scrape_mode and page_number.
        See cached_file_name() for more information.

        This will always write(overwrite) the cached file. If compress_cached_files is
        True, the page is written in bytes (obviously).

        Args:
            parser: A parser with the data to cache.
            query: The keyword that was used in the search.
            search_engine: The search engine the keyword was scraped for.
            scrape_mode: The scrapemode that was used.
            page_number: The page number that the serp page is.
            db_lock: If an db_lock is given, all action are wrapped in this lock.
        """

        if self.config.get('do_caching', False):
            if db_lock:
                db_lock.acquire()

            if self.config.get('minimize_caching_files', True):
                html = parser.cleaned_html
            else:
                html = parser.html

            fname = self.cached_file_name(query, search_engine, scrape_mode, page_number)
            cachedir = self.config.get('cachedir', '.scrapecache')
            path = os.path.join(cachedir, fname)

            if self.config.get('compress_cached_files'):
                algorithm = self.config.get('compressing_algorithm', 'gz')
                f = CompressedFile(path, algorithm=algorithm)
                f.write(html)
            else:
                with open(path, 'w') as fd:
                    if isinstance(html, bytes):
                        fd.write(html.decode())
                    else:
                        fd.write(html)

            if db_lock:
                db_lock.release()


    def _get_all_cache_files(self):
        """Return all files found in the cachedir.

        Returns:
            All files that have the string "cache" in it within the cache directory.
            Files are either uncompressed filename.cache or are compressed with a
            compression algorithm: "filename.cache.zip"
        """
        files = set()
        for dirpath, dirname, filenames in os.walk(self.config.get('cachedir', '.scrapecache')):
            for name in filenames:
                if 'cache' in name:
                    files.add(os.path.join(dirpath, name))
        return files


    def _caching_is_one_to_one(self, keywords, search_engine, scrapemode, page_number):
        """Check whether all keywords map to a unique file name.

        Args:
            keywords: All keywords for which to check the uniqueness of the hash
            search_engine: The search engine the keyword was scraped for.
            scrapemode: The scrapemode that was used.
            page_number: page_number

        Returns:
            True if all keywords map to a unique hash and False if not.
        """
        mappings = {}
        for kw in keywords:
            file_hash = self.cached_file_name(kw, search_engine, scrapemode, page_number)
            if file_hash not in mappings:
                mappings.update({file_hash: [kw, ]})
            else:
                mappings[file_hash].append(kw)

        duplicates = [v for k, v in mappings.items() if len(v) > 1]
        if duplicates:
            logger.info('Not one-to-one. {}'.format(duplicates))
            return False
        else:
            logger.info('one-to-one')
            return True


    def parse_all_cached_files(self, scrape_jobs, session, scraper_search):
        """Walk recursively through the cachedir (as given by the Config) and parse all cached files.

        Args:
            session: An sql alchemy session to add the entities
            scraper_search: Abstract object representing the current search.

        Returns:
            The scrape jobs that couldn't be parsed from the cache directory.
        """
        files = self._get_all_cache_files()
        num_cached = num_total = 0
        mapping = {}
        for job in scrape_jobs:
            cache_name = self.cached_file_name(
                job['query'],
                job['search_engine'],
                job['scrape_method'],
                job['page_number']
            )
            mapping[cache_name] = job
            num_total += 1

        for path in files:
            # strip of the extension of the path if it has eny
            fname = os.path.split(path)[1]
            clean_filename = fname
            for ext in ALLOWED_COMPRESSION_ALGORITHMS:
                if fname.endswith(ext):
                    clean_filename = fname.rstrip('.' + ext)

            job = mapping.get(clean_filename, None)

            if job:
                # We found a file that contains the keyword, search engine name and
                # search mode that fits our description. Let's see if there is already
                # an record in the database and link it to our new ScraperSearch object.
                serp = self.get_serp_from_database(session, job['query'], job['search_engine'], job['scrape_method'],
                                              job['page_number'])

                if not serp:
                    serp = self.parse_again(fname, job['search_engine'], job['scrape_method'], job['query'])

                serp.scraper_searches.append(scraper_search)
                session.add(serp)

                if num_cached % 200 == 0:
                    session.commit()

                store_serp_result(serp, self.config)
                num_cached += 1
                scrape_jobs.remove(job)

        logger.info('{} cache files found in {}'.format(len(files), self.config.get('cachedir')))
        logger.info('{}/{} objects have been read from the cache. {} remain to get scraped.'.format(
            num_cached, num_total, num_total - num_cached))

        session.add(scraper_search)
        session.commit()

        return scrape_jobs


    def parse_again(self, fname, search_engine, scrape_method, query):
        """
        @todo: `scrape_method` is not used here -> check if scrape_method is passed to this function and remove it
        """
        path = os.path.join(self.config.get('cachedir', '.scrapecache'), fname)
        html = self.read_cached_file(path)
        return parse_serp(
            self.config,
            html=html,
            search_engine=search_engine,
            query=query
        )


    def get_serp_from_database(self, session, query, search_engine, scrape_method, page_number):
        try:
            serp = session.query(SearchEngineResultsPage).filter(
                SearchEngineResultsPage.query == query,
                SearchEngineResultsPage.search_engine_name == search_engine,
                SearchEngineResultsPage.scrape_method == scrape_method,
                SearchEngineResultsPage.page_number == page_number).first()
            return serp
        except NoResultFound:
            # that shouldn't happen
            # we have a cache file that matches the above identifying information
            # but it was never stored to the database.
            return False


    def clean_cachefiles(self):
        """Clean silly html from all cachefiles in the cachdir"""
        if input(
                'Do you really want to strip all cache files from bloating tags such as <script> and <style>? ').startswith(
                'y'):
            import lxml.html
            from lxml.html.clean import Cleaner

            cleaner = Cleaner()
            cleaner.style = True
            cleaner.scripts = True
            cleaner.javascript = True
            for file in self._get_all_cache_files():
                cfile = CompressedFile(file)
                data = cfile.read()
                cleaned = lxml.html.tostring(cleaner.clean_html(lxml.html.fromstring(data)))
                cfile.write(cleaned)
                logger.info('Cleaned {}. Size before: {}, after {}'.format(file, len(data), len(cleaned)))


    def fix_broken_cache_names(self, url, search_engine, scrapemode, page_number):
        """Fix broken cache names.

        Args:
            url: A list of strings to add to each cached_file_name() call.

        @todo: `url` is not used here -> check if scrape_method is passed to this function and remove it
        """
        files = self._get_all_cache_files()
        logger.debug('{} cache files found in {}'.format(len(files), self.config.get('cachedir', '.scrapecache')))
        r = re.compile(r'<title>(?P<kw>.*?) - Google Search</title>')

        i = 0
        for path in files:
            fname = os.path.split(path)[1].strip()
            data = self.read_cached_file(path)
            infilekws = r.search(data).group('kw')
            realname = self.cached_file_name(infilekws, search_engine, scrapemode, page_number)
            if fname != realname:
                logger.debug('The search query in the title element in file {} differ from that hash of its name. Fixing...'.format(path))
                src = os.path.abspath(path)
                dst = os.path.abspath(os.path.join(os.path.split(path)[0], realname))
                logger.debug('Renamed from {} => {}'.format(src, dst))
                os.rename(src, dst)
            i += 1

        logger.debug('Renamed {} files.'.format(i))


    def cached(self, f, attr_to_cache=None):
        """Decorator that makes return value of functions cachable.

        Any function that returns a value and that is decorated with
        cached will be supplied with the previously calculated result of
        an earlier call. The parameter name with the cached value may
        be set with attr_to_cache.

        Args:
            attr_to_cache: The name of attribute whose data
                            is cachable.

        Returns: The modified and wrapped function.

        @todo: `attr_to_cache` is not used here -> check if scrape_method is passed to this function and remove it
        """

        def wraps(*args, **kwargs):
            cached_value = self.get_cached(*args, params=kwargs)
            if cached_value:
                f(*args, attr_to_cache=cached_value, **kwargs)
            else:
                # Nothing was cached for this attribute
                value = f(*args, attr_to_cache=None, **kwargs)
                self.cache_results(value, *args, params=kwargs)

        return wraps


if __name__ == '__main__':
    import doctest

    doctest.testmod()
