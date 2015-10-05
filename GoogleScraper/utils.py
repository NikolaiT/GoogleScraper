# -*- coding: utf-8 -*-

from itertools import zip_longest
import re
import requests
import os


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


def random_words(n=100, wordlength=range(10, 15)):
    """Read a random english wiki article and extract some words.

    Args:
        n: The number of words to return. Returns all found ones, if n is more than we were able to found.
        wordlength: A range that forces the words to have a specific length.

    Returns:
        Random words. What else you motherfucker?
    """
    valid_words = re.compile(r'[a-zA-Z]{{{},{}}}'.format(wordlength.start, wordlength.stop))
    found = list(set(valid_words.findall(requests.get('http://en.wikipedia.org/wiki/Special:Random').text)))
    try:
        return found[:n]
    except IndexError:
        return found


def get_some_words(n=100):
    """Get some words. How the fuck know where we get them from."""
    if os.path.exists('/usr/share/dict/words'):
        words = open('/usr/share/dict/words').read().splitlines()
        if n < len(words):
            words = words[:n]
    else:
        words = random_words(n=n)

    return words


def get_base_path():
    return os.path.dirname(os.path.realpath(__file__))


if __name__ == '__main__':
    import doctest

    doctest.testmod()