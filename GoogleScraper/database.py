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
        return '<ScraperSearch started: {} stopped: {}>'.format(self.started_searching, self.stopped_searching)

class SearchEngineResultsPage(Base):
    __tablename__ = 'serp'

    id = Column(Integer, primary_key=True)
    search_engine_name = Column(String)
    page_number = Column(Integer)
    requested_at = Column(DateTime)
    requested_by = Column(String)
    num_results = Column(Integer)
    query = Column(String)
    num_results_for_keyword = Column(String)

    scraper_search_id = Column(Integer, ForeignKey('scraper_search.id'))
    search = relationship(ScraperSearch, backref=backref('serps', uselist=True))

    def __str__(self):
        return '<SERP number of results[{}] for query {}>'.format(self.num_results, self.query)

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
        return '<Link url: {}>'.format(self.url)


engine = create_engine('sqlite:///' + Config['GLOBAL'].get('database_name'), echo=True)
Base.metadata.create_all(engine)

