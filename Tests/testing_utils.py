#!/usr/bin/python3
# -*- coding: utf-8 -*-

import random
from GoogleScraper.utils import get_some_words


def assert_atleast_delta_percent_of_items(data, attr_name, delta=0.9):
    """Checks that at least delta percent of the results are not None.
    """
    n=k=0
    for obj in data:
    	n+=1
    	if not getattr(obj, attr_name):
    		k += 1

    return k/n <= (1-delta)

def assert_atleast_delta_percent_of_items_dict(data, key, delta=0.9):
    """Checks that at least delta percent of the results are not None.
    """
    n=k=0
    for obj in data:
    	n+=1
    	if not obj[key]:
    		k += 1

    return k/n <= (1-delta)

def random_word():
    return random.choice(words)

words = get_some_words(n=100)