# -*- coding: utf-8 -*-

from itertools import zip_longest

def grouper(iterable, n, fillvalue=None):
    """Collect data into fixed-length chunks or blocks.

    >>> grouper('ABCDEFG', 3, 'x')
    [['A', 'B', 'C'], ['D', 'E', 'F'], ['G', 'x', 'x']]

    Args:
        iterable: An iterable
        n: How long should the tokens be
        fillvalue: What to pad non complete tokens with

    Returns:
        The tokens as list.
    """
    args = [iter(iterable)] * n
    groups = zip_longest(*args, fillvalue=fillvalue)
    return [list(filter(None.__ne__, list(group))) for group in groups]


def chunk_it(seq, num):
    """Make num chunks from elements in seq.

    >>> keywords = ['what', 'is', 'going', 'on', 'exactly']
    >>> chunk_it(keywords, 6)
    [['what'], ['is'], ['going'], ['on'], ['exactly']]
    >>> chunk_it(keywords, 2)
    [['what', 'is'], ['going', 'on', 'exactly']]

    Args:
        seq: A collection to be chunked
        num: The number of chunks to yield.

    Returns:
        A list of num chunks.
    """
    if num >= len(seq):
        num = len(seq)

    avg = len(seq) / float(num)
    out = []
    last = 0.0

    while last < len(seq):
        out.append(seq[int(last):int(last + avg)])
        last += avg

    return out

if __name__ == '__main__':
    import doctest
    doctest.testmod()