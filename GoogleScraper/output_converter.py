# -*- coding: utf-8 -*-

import csv
import sys
import json
import datetime
from GoogleScraper.config import Config

"""Stores SERP results in the appropriate output format.

Streamline process, one serp object at the time, because GoogleScraper works incrementally.
Furthermore we cannot accumulate all results and then process them, because it would be
impossible to launch lang scrape jobs with millions of keywords.
"""

output_format = 'stdout'
outfile = None
wrote_json_start = False

class JsonStreamWriter():
    """Writes consecutive objects to an json output file."""

    def __init__(self, filename):
        self.file = open(filename, 'wt')
        self.file.write('[')

    def write(self, obj):
        json.dump(obj, self.file, indent=2, sort_keys=True, ensure_ascii=True)
        self.file.write(',')

    def __del__(self):
        self.file.write(']')


def init_output_storage():
    """Init an outfile."""
    global outfile, output_format

    output_file = Config['OUTPUT'].get('output_filename')
    if '.' in output_file:
        output_format = output_file.split('.')[-1]

    if not outfile:
        # the output files. Either CSV or JSON or STDOUT
        # It's little bit tricky to write the JSON output file, since we need to
        # create the array of the most outer results ourselves because we write
        # results as soon as we get them (it's impossible to hold the whole search in memory).
        if output_format == 'json':
            outfile = JsonStreamWriter(output_file)
        elif output_format == 'csv':
            outfile = csv.DictWriter(open(output_file, 'wt'),
                    fieldnames=('rank', 'link', 'title', 'snippet', 'visible_link', 'num_results',
                                'query', 'search_engine_name', 'requested_by',
                                'scrapemethod', 'page_number', 'requested_at'))
            outfile.writeheader()
        elif output_format == 'stdout':
            outfile = sys.stdout

def store_serp_result(obj, serps=None, parser=None):
    """Store the parsed SERP page in the suited output format.

    If there is no parser object given, the links are available over
    serp.links.

    Args:
        obj: The serp object as dict.
        serp: The serp object
        parser: A parse object.
    """
    global outfile, output_format

    if not outfile:
        init_output_storage()

    if outfile:
        def results():
            rows = []
            if parser:
                for result_type, value in parser.search_results.items():
                    if isinstance(value, list):
                        for link in value:
                            rows.append(link)
            return rows
        if output_format == 'json':
            # The problem here is, that we need to stream write the json data.

            if parser:
                if not obj:
                    obj = {}
                obj['results'] = results()
            elif serps:
                for serp in serps:
                    data = {}
                    data.update(dict_from_serp_object(serp))
                    data['results'] = []
                    for link in serp.links:
                        d = row2dict(link)
                        data['results'].append(d)
                    outfile.write(data)

            elif parser:
                outfile.write(obj)
        elif output_format == 'csv':
            if parser:
                for row in results():
                    row.update(obj)
                    outfile.writerow(row)

        elif output_format == 'stdout' and Config['GLOBAL'].getint('verbosity', 1) > 2:
            print(parser if parser else '', file=outfile)


def dict_from_serp_object(serp):
    """Creates an dictionary from an SERP object."""
    keys = ('query', 'search_engine_name', 'requested_by', 'scrapemethod', 'page_number', 'requested_at', 'num_results')
    d = {key: getattr(serp, key) for key in keys}

    for key, value in d.items():
        if isinstance(value, datetime.datetime):
            d[key] = value.isoformat()

    return d

def dict_from_scraping_object(obj):
    """Little helper that creates a dict from a SearchEngineScrape object."""
    d = {}
    d['query'] = obj.current_keyword
    d['search_engine_name'] = obj.search_engine
    d['requested_by'] = obj.ip
    d['scrapemethod'] = obj.scrapemethod
    d['page_number'] = obj.current_page
    d['requested_at'] = obj.current_request_time.isoformat()
    d['num_results'] = obj.parser.search_results['num_results']
    return d


def row2dict(obj):
    """Convert sql alchemy object to dictionary."""
    d = {}
    for column in obj.__table__.columns:
        d[column.name] = str(getattr(obj, column.name))

    return d