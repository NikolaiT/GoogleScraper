import csv
import sys
import json
import datetime
from GoogleScraper.config import Config

"""Stores serp results in the appropriate output format.

Streamig process, one serp object at the time.
"""

outfile = None

def init_output_storage():
    """Init an outfile."""
    global outfile

    output_format = Config['GLOBAL'].get('output_format', 'stdout')
    output_file = Config['GLOBAL'].get('output_filename', 'google_scraper')

    if not outfile:
        # the output files. Either CSV or JSON or STDOUT
        # It's little bit tricky to write the JSON output file, since we need to
        # create the array of the most outer results ourselves because we write
        # results as soon as we get them (it's impossible to hold the whole search in memory).
        if output_format == 'json':
            outfile = open(output_file + '.json', 'a')
            outfile.write('[')
        elif output_format == 'csv':
            outfile = csv.DictWriter(open(output_file + '.csv', 'a'),
                    fieldnames=('link', 'title', 'snippet', 'visible_link', 'num_results',
                                'query', 'search_engine_name', 'requested_by',
                                'scrapemethod', 'page_number', 'requested_at'))
            outfile.writeheader()
        elif output_format == 'stdout':
            outfile = sys.stdout

def store_serp_result(serp, parser):
    global outfile

    output_format = Config['GLOBAL'].get('output_format', 'stdout')

    if not outfile:
        init_output_storage()

    if outfile:
        def results():
            rows = []
            for result_type, value in parser.search_results.items():
                if isinstance(value, list):
                    for link in value:
                        rows.append(link)
            return rows

        if output_format == 'json':
            serp['results'] = results()
            json.dump(serp, outfile, indent=2, sort_keys=True)
            outfile.write(',')
        elif output_format == 'csv':
            for row in results():
                row.update(serp)
                outfile.writerow(row)
        elif output_format == 'stdout':
            outfile.write(str(serp))


def dict_from_serp_object(serp):
    """Creates an dictionary from an SERP object."""
    keys = ('query', 'search_engine_name', 'requested_by', 'scrapemethod', 'page_number', 'requested_at', 'num_results')
    d =  {key: getattr(serp, key) for key in keys}

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

def end():
    """Close the json array if necessary."""
    output_format = Config['GLOBAL'].get('output_format', 'stdout')

    if output_format == 'json':
        outfile.write(']')