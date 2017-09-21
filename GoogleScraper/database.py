# -*- coding: utf-8 -*-

"""
The database schema of GoogleScraper.

There are four entities:

    ScraperSearch: Represents a call to GoogleScraper. A search job.
    SearchEngineResultsPage: Represents a SERP result page of a search_engine
    Link: Represents a LINK on a SERP
    Proxy: Stores all proxies and their statuses.

Because searches repeat themselves and we avoid doing them again (caching), one SERP page
can be assigned to more than one ScraperSearch. Therefore we need a n:m relationship.
"""

import datetime
from urllib.parse import urlparse
from sqlalchemy import Column, String, Integer, ForeignKey, Table, DateTime, Enum, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy import create_engine, UniqueConstraint
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

scraper_searches_serps = Table('scraper_searches_serps', Base.metadata,
                               Column('scraper_search_id', Integer, ForeignKey('scraper_search.id')),
                               Column('serp_id', Integer, ForeignKey('serp.id')))


class ScraperSearch(Base):
    __tablename__ = 'scraper_search'

    id = Column(Integer, primary_key=True)
    keyword_file = Column(String)
    number_search_engines_used = Column(Integer)
    used_search_engines = Column(String)
    number_proxies_used = Column(Integer)
    number_search_queries = Column(Integer)
    started_searching = Column(DateTime, default=datetime.datetime.utcnow)
    stopped_searching = Column(DateTime)

    serps = relationship(
        'SearchEngineResultsPage',
        secondary=scraper_searches_serps,
        backref=backref('scraper_searches', uselist=True)
    )

    def __str__(self):
        return '<ScraperSearch[{id}] scraped for {number_search_queries} unique keywords. Started scraping: {started_' \
               'searching} and stopped: {stopped_searching}>'.format(**self.__dict__)

    def __repr__(self):
        return self.__str__()


class SearchEngineResultsPage(Base):
    __tablename__ = 'serp'

    id = Column(Integer, primary_key=True)
    status = Column(String, default='successful')
    search_engine_name = Column(String)
    scrape_method = Column(String)
    page_number = Column(Integer)
    requested_at = Column(DateTime, default=datetime.datetime.utcnow)
    requested_by = Column(String, default='127.0.0.1')

    # The string in the SERP that indicates how many results we got for the search term.
    num_results_for_query = Column(String, default='')

    # Whether we got any results at all. This is the same as len(serp.links)
    num_results = Column(Integer, default=-1)

    query = Column(String)

    # if the query was modified by the search engine because there weren't any
    # results, this variable is set to the query that was used instead.
    # Otherwise it remains empty.
    effective_query = Column(String, default='')

    # Whether the search engine has no results.
    # This is not the same as num_results, because some search engines
    # automatically search other similar search queries when they find no results.
    # Sometimes they have results for the query, but detect a spelling mistake and only
    # suggest an alternative. This is another case!
    # If no_results is true, then there weren't ANY RESULTS FOUND FOR THIS QUERY!!! But there
    # could have been results for an auto corrected query.
    no_results = Column(Boolean, default=False)

    def __str__(self):
        return '<SERP[{search_engine_name}] has [{num_results}] link results for query "{query}">'.format(
            **self.__dict__)

    def __repr__(self):
        return self.__str__()

    def has_no_results_for_query(self):
        """
        Returns True if the original query did not yield any results.
        Returns False if either there are no serp entries, or the search engine auto corrected the query.
        """
        return self.num_results == 0 or self.effective_query

    def set_values_from_parser(self, parser):
        """Populate itself from a parser object.

        Args:
            A parser object.
        """

        self.num_results_for_query = parser.num_results_for_query
        self.num_results = parser.num_results
        self.effective_query = parser.effective_query
        self.no_results = parser.no_results

        for key, value in parser.search_results.items():
            if isinstance(value, list):
                for link in value:
                    parsed = urlparse(link['link'])

                    # fill with nones to prevent key errors
                    [link.update({key: None}) for key in ('snippet', 'title', 'visible_link') if key not in link]

                    Link(
                        link=link['link'],
                        snippet=link['snippet'],
                        title=link['title'],
                        visible_link=link['visible_link'],
                        domain=parsed.netloc,
                        rank=link['rank'],
                        serp=self,
                        link_type=key
                    )

    def set_values_from_scraper(self, scraper):
        """Populate itself from a scraper object.

        A scraper may be any object of type:

            - SelScrape
            - HttpScrape
            - AsyncHttpScrape

        Args:
            A scraper object.
        """

        self.query = scraper.query
        self.search_engine_name = scraper.search_engine_name
        self.scrape_method = scraper.scrape_method
        self.page_number = scraper.page_number
        self.requested_at = scraper.requested_at
        self.requested_by = scraper.requested_by
        self.status = scraper.status

    def was_correctly_requested(self):
        return self.status == 'successful'


# Alias as a shorthand for working in the shell
SERP = SearchEngineResultsPage


class Link(Base):
    __tablename__ = 'link'

    id = Column(Integer, primary_key=True)
    title = Column(String)
    snippet = Column(String)
    link = Column(String)
    domain = Column(String)
    visible_link = Column(String)
    rank = Column(Integer)
    link_type = Column(String)

    serp_id = Column(Integer, ForeignKey('serp.id'))
    serp = relationship(SearchEngineResultsPage, backref=backref('links', uselist=True))

    def __str__(self):
        return '<Link at rank {rank} has url: {link}>'.format(**self.__dict__)

    def __repr__(self):
        return self.__str__()


class Proxy(Base):
    __tablename__ = 'proxy'

    id = Column(Integer, primary_key=True)
    ip = Column(String)
    hostname = Column(String)
    port = Column(Integer)
    proto = Column(Enum('socks5', 'socks4', 'http'))
    username = Column(String)
    password = Column(String)

    online = Column(Boolean)
    status = Column(String)
    checked_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    city = Column(String)
    region = Column(String)
    country = Column(String)
    loc = Column(String)
    org = Column(String)
    postal = Column(String)

    UniqueConstraint(ip, port, name='unique_proxy')

    def __str__(self):
        return '<Proxy {ip}>'.format(**self.__dict__)

    def __repr__(self):
        return self.__str__()


db_Proxy = Proxy


class SearchEngine(Base):
    __tablename__ = 'search_engine'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    http_url = Column(String)
    selenium_url = Column(String)
    image_url = Column(String)


class SearchEngineProxyStatus(Base):
    """Stores last proxy status for the given search engine.
    
    A proxy can either work on a search engine or not.
    """

    __tablename__ = 'search_engine_proxy_status'

    id = Column(Integer, primary_key=True)
    proxy_id = Column(Integer, ForeignKey('proxy.id'))
    search_engine_id = Column(Integer, ForeignKey('search_engine.id'))
    available = Column(Boolean)
    last_check = Column(DateTime)


def get_engine(config, path=None):
    """Return the sqlalchemy engine.

    Args:
        path: The path/name of the database to create/read from.

    Returns:
        The sqlalchemy engine.
    """
    db_path = path if path else config.get('database_name', 'google_scraper') + '.db'
    echo = config.get('log_sqlalchemy', False)
    engine = create_engine('sqlite:///' + db_path, echo=echo, connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)

    return engine


def get_session(config, scoped=False, engine=None, path=None):
    if not engine:
        engine = get_engine(config, path=path)

    session_factory = sessionmaker(
        bind=engine,
        autoflush=True,
        autocommit=False,
    )

    if scoped:
        ScopedSession = scoped_session(session_factory)
        return ScopedSession
    else:
        return session_factory


def fixtures(config, session):
    """Add some base data."""

    for se in config.get('supported_search_engines', []):
        if se:
            search_engine = session.query(SearchEngine).filter(SearchEngine.name == se).first()
            if not search_engine:
                session.add(SearchEngine(name=se))

    session.commit()
