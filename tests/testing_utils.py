#!/usr/bin/python3
# -*- coding: utf-8 -*-

import random
from GoogleScraper.utils import get_some_words

def random_word():
    return random.choice(words)

words = get_some_words(n=100)