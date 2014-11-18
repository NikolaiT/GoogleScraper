#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from setuptools import setup

version = re.search(
    "^__version__\s*=\s*'(.*)'",
    open('GoogleScraper/version.py').read(),
    re.M).group(1)

requirements = [r for r in open('requirements.txt', 'r').read().split('\n') if r]

setup(name='GoogleScraper',
      version=version,
      description='A module to scrape and extract links, titles and descriptions from Google search results',
      long_description=open('README.md').read(),
      author='Nikolai Tschacher',
      author_email='admin@incolumitas.com',
      url='http://incolumitas.com',
      py_modules=['usage'],
      packages=['GoogleScraper'],
      entry_points={'console_scripts': ['GoogleScraper = GoogleScraper.core:main']},
      package_data={
          'GoogleScraper': ['config.cfg'],
      },
      install_requires=requirements
)
