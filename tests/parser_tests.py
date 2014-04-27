__author__ = 'nikolai'

from parser import Google_SERP_Parser
import pprint

f = open('serp_formats/non_tables_with_ads.htm')

parser = Google_SERP_Parser(f.read())
pprint.pprint(parser.results)

