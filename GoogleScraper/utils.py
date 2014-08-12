# -*- coding: utf-8 -*-

from itertools import zip_longest

def grouper(iterable, n, fillvalue=None):
    """Collect data into fixed-length chunks or blocks."""
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    groups = zip_longest(*args, fillvalue=fillvalue)
    return [list(filter(None.__ne__, list(group))) for group in groups]