# -*- coding: utf-8 -*-

import csv
import sys
import json
from pprint import pprint
from GoogleScraper.config import Config
from GoogleScraper.database import Link

"""Stores SERP results in the appropriate output format.

Streamline process, one serp object at the time, because GoogleScraper works incrementally.
Furthermore we cannot accumulate all results and then process them, because it would be
impossible to launch lang scrape jobs with millions of keywords.
"""

output_format = 'stdout'
outfile = None

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

def store_serp_result(serp):
    """Store the parsed SERP page.

    Stores the results from scraping in the appropriate output format.

    Either stdout, json or csv output format.

    This function may be called from a SearchEngineScrape or from
    caching functionality. When called from SearchEngineScrape, then
    a parser object is passed.
    When called from caching, a list of serp object are given.

    Args:
        serp: A serp object
    """
    global outfile, output_format

    if not outfile:

        output_file = Config['OUTPUT'].get('output_filename')
        if '.' in output_file:
            output_format = output_file.split('.')[-1]

        # the output files. Either CSV or JSON or STDOUT
        # It's little bit tricky to write the JSON output file, since we need to
        # create the array of the most outer results ourselves because we write
        # results as soon as we get them (it's impossible to hold the whole search in memory).
        if output_format == 'json':
            outfile = JsonStreamWriter(output_file)
        elif output_format == 'csv':
            outfile = csv.DictWriter(open(output_file, 'wt'), fieldnames=Link.__table__.columns._data.keys())
            outfile.writeheader()
        elif output_format == 'stdout':
            outfile = sys.stdout

    if outfile:
        data = row2dict(serp)
        data['results'] = []
        for link in serp.links:
            data['results'].append(row2dict(link))

        if output_format == 'json':
            # The problem here is, that we need to stream write the json data.
            outfile.write(data)
        elif output_format == 'csv':
            # one row per link
            for row in data['results']:
                outfile.writerow(row)
        elif output_format == 'stdout' and Config['GLOBAL'].getint('verbosity', 1) > 2:
            pprint(data)

def row2dict(obj):
    """Convert sql alchemy object to dictionary."""
    d = {}
    for column in obj.__table__.columns:
        d[column.name] = str(getattr(obj, column.name))

    return d