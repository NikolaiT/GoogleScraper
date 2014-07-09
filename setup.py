#!/usr/bin/env python

from distutils.core import setup
from setuptools import find_packages

setup(name='GoogleScraper',
      version='0.0.1',
      description='A module to scrape and extract links, titles and descriptions of Google search results',
      author='Nikolai Tschacher',
      author_email='admin@incolumitas.com',
      url='http://incolumitas.com',
      keywords=[
            'Google Scrape',
            ],
      classifiers=[
            'Development Status :: 3 - Alpha',
            'Programming Language :: Python :: 3.4',
      ],
      packages=find_packages(),
     )
