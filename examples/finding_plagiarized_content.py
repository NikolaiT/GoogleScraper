#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from GoogleScraper import scrape_with_config, GoogleSearchError


text = """
Python is a multi-paradigm programming language: object-oriented programming and structured programming are fully supported, and there are a number of language features which support functional programming and aspect-oriented programming (including by metaprogramming[32] and by magic methods).[33] Many other paradigms are supported using extensions, including design by contract[34][35] and logic programming.[36]

Python uses dynamic typing and a combination of reference counting and a cycle-detecting garbage collector for memory management. An important feature of Python is dynamic name resolution (late binding), which binds method and variable names during program execution.

The design of Python offers only limited support for functional programming in the Lisp tradition. The language has map(), reduce() and filter() functions; comprehensions for lists, dictionaries, and sets; as well as generator expressions.[37] The standard library has two modules (itertools and functools) that implement functional tools borrowed from Haskell and Standard ML.[38]

The core philosophy of the language is summarized by the document "PEP 20 (The Zen of Python)", which includes aphorisms such as:[39]

    Beautiful is better than ugly
    Explicit is better than implicit
    Simple is better than complex
    Complex is better than complicated
    Readability counts

Rather than requiring all desired functionality to be built into the language's core, Python was designed to be highly extensible. Python can also be embedded in existing applications that need a programmable interface. This design of a small core language with a large standard library and an easily extensible interpreter was intended by Van Rossum from the very start because of his frustrations with ABC (which espoused the opposite mindset).[25]

While offering choice in coding methodology, the Python philosophy rejects exuberant syntax, such as in Perl, in favor of a sparser, less-cluttered grammar. As Alex Martelli put it: "To describe something as clever is not considered a compliment in the Python culture."[40] Python's philosophy rejects the Perl "there is more than one way to do it" approach to language design in favor of "there should be one—and preferably only one—obvious way to do it".[39]

Python's developers strive to avoid premature optimization, and moreover, reject patches to non-critical parts of CPython which would offer a marginal increase in speed at the cost of clarity.[41] When speed is important, Python programmers use PyPy, a just-in-time compiler, or move time-critical functions to extension modules written in languages such as C. Cython is also available which translates a Python script into C and makes direct C level API calls into the Python interpreter.

An important goal of the Python developers is making Python fun to use. This is reflected in the origin of the name which comes from Monty Python,[42] and in an occasionally playful approach to tutorials and reference materials, for example using spam and eggs instead of the standard foo and bar.[43][44]
"""

def make_chunks(text):
    """Splits the text in chunks suitable for a single search query.

    The algorithm works the following way:

        If a sentence is between 25 and 125 chars long, then use it as a chunk.
            If the sentence is shorter, do nothing.
            If the sentence is longer, then split by commatas.

    Args:
        The text to check.

    Returns:
        Quoted chunks to use in google.
    """
    # normalize text
    text = text.replace('\n', '').replace('\t', '')

    chunks = []

    sentences = text.split('.')
    for sentence in sentences:

        if len(sentence) in range(25, 125):
            chunks.append('"{}"'.format(sentence))
        elif len(sentence) < 25:
            consume_next = True
            # just ignore this for now. Short sentences are not usable anyways.
        elif len(sentence) > 125:
            chunks.extend(
                ['"{}"'.format(s) for s in sentence.split(',') if len(s) > 25]
            )

    return chunks

# write the chunks to a file
with open('chunks.txt', 'wt') as f:

    for chunk in make_chunks(text):
        f.write(chunk + '\n')

# # See in the config.cfg file for possible values
config = {
    'use_own_ip': True,
    'keyword_file': 'chunks.txt',
    'search_engines': ['google'],
    'num_pages_for_keyword': 1,
    'scrape_method': 'selenium',
    'sel_browser': 'chrome',
}

try:
    search = scrape_with_config(config)
except GoogleSearchError as e:
    print(e)

for serp in search.serps:

    # if the original query yielded some results and thus was found by google.
    if not serp.effective_query:
        print('Found plagiarized content: "{}"'.format(serp.query))