# -*- coding: utf-8 -*-

"""
Creates a dynamic schema based on the CSS-Selectors from subclasses of
Parser in parsing.py.
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

class ScraperSearch(Base):
    __tablename__ = 'scraper_search'

    id = Column(Integer, primary_key=True)
    number_search_engines_used = Column(Integer)
    used_search_engines = Column(String)
    number_proxies_used = Column(Integer)
    number_search_queries = Column(Integer)
    started_searching = Column(DateTime, default=datetime.datetime.utcnow)
    stopped_searching = Column(DateTime)

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
    requested_at = Column(DateTime)
    requested_by = Column(String)
    num_results = Column(Integer)
    query = Column(String)
    num_results_for_keyword = Column(String)

    scraper_search_id = Column(Integer, ForeignKey('scraper_search.id'))
    search = relationship(ScraperSearch, backref=backref('serps', uselist=True))

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
    url = Column(String)
    visible_link = Column(String)
    rank = Column(Integer)
    link_type = Column(String)

    serp_id = Column(Integer, ForeignKey('serp.id'))
    serp = relationship(SearchEngineResultsPage, backref=backref('links', uselist=True))

    def __str__(self):
        return '<Link at rank {rank} has url: {url}>'.format(**self.__dict__)

    def __repr__(self):
        return self.__str__()


def get_engine(create=True):
    """Return the sqlalchemy engine.

    Returns:
        The sqlalchemy engine.
    """
    echo = True if (Config['GLOBAL'].getint('verbosity', 0) >= 3) else False
    engine = create_engine('sqlite:///' + Config['GLOBAL'].get('database_name'), echo=echo)
    if create:
        Base.metadata.create_all(engine)

    return engine


def get_session(scoped=False, create=False):
    engine = get_engine(create=create)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=True,
        autocommit=False,
    )
    if scoped:
        ScopedSession = scoped_session(session_factory)
        session = ScopedSession()
    else:
        session = session_factory()

    return session
