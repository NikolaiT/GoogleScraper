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


if __name__ == '__main__':
    import doctest
    doctest.testmod()