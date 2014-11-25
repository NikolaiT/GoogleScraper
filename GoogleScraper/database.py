# -*- coding: utf-8 -*-

"""
The database schema of GoogleScraper.

There are three entities:

    ScraperSearch: Represents a call to GoogleScraper. A search job.
    SearchEngineResultsPage: Represents a SERP result page of a search_engine
    Link: Represents a LINK on a SERP

Because searches repeat themselves and we avoid doing them again (caching), one SERP page
can be assigned to more than one ScraperSearch. Therefore we need a n:m relationship.
"""

import datetime
from GoogleScraper.config import Config
from sqlalchemy import Column, String, Integer, ForeignKey, Table, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

scraper_searches_serps = Table('scraper_searches_serps', Base.metadata,
    Column('scraper_search_id', Integer, ForeignKey('scraper_search.id')),
    Column('serp_id', Integer, ForeignKey('serp.id'))
)

class ScraperSearch(Base):
    __tablename__ = 'scraper_search'

    id = Column(Integer, primary_key=True)
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
        return '<ScraperSearch[{id}] scraped for {number_search_queries} unique keywords. Started scraping: {started_searching} and stopped: {stopped_searching}>'.format(**self.__dict__)

    def __repr__(self):
        return self.__str__()

class SearchEngineResultsPage(Base):
    __tablename__ = 'serp'

    id = Column(Integer, primary_key=True)
    search_engine_name = Column(String)
    scrapemethod = Column(String)
    page_number = Column(Integer)
    requested_at = Column(DateTime, default=datetime.datetime.utcnow)
    requested_by = Column(String, default='127.0.0.1')
    num_results = Column(Integer)
    query = Column(String)
    num_results_for_keyword = Column(String)

    def __str__(self):
        return '<SERP[{search_engine_name}] has [{num_results}] link results for query "{query}">'.format(**self.__dict__)

    def __repr__(self):
        return self.__str__()

# Alias as a shorthand for working in the shell
SERP = SearchEngineResultsPage

class Link(Base):
    __tablename__= 'link'

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
        return '<Link at rank {rank} has url: {url}>'.format(**self.__dict__)

    def __repr__(self):
        return self.__str__()


def get_engine(path=None):
    """Return the sqlalchemy engine.

    Returns:
        The sqlalchemy engine.
    """
    db_path = path if path else Config['GLOBAL'].get('output_filename', 'google_scraper') + '.db'
    echo = True if (Config['GLOBAL'].getint('verbosity', 0) >= 3) else False
    engine = create_engine('sqlite:///' + db_path, echo=echo)
    Base.metadata.create_all(engine)

    return engine


def get_session(scoped=False, create=False, engine=None, path=None):
    if not engine:
        engine = get_engine(path=path)

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
