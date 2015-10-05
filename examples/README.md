## Examples of using GoogleScraper

In this directory you can find a wide range of examples of how to use GoogleScraper. It would be 
great if People could create Pull Requests with their own examples of how to use GoogleScraper!


### Asynchronous Mode

In this example asynchronous, which is quite fast, is used. Two pages are requested and the results
stored in a file `out.csv` which may be found in the same directory where the script is created.

### Basic Usage

In the [basic usage program](basic.py) the script scrapes a single keyword (*Let's go bubbles!*) with
one page. Selenium mode is used with Chrome Browser as frontend. Caching is disabled, so the results are
always fresh!

### Basic Usage with two pages per keyword

This example shows how to scrape more than one SERP page per keyword. The config that is passed
looks like this:
    :::python
    config = {
        'use_own_ip': True,
        'keyword': 'reddit',
        'search_engines': ['bing',],
        'num_pages_for_keyword': 2,
        'scrape_method': 'selenium',
        'sel_browser': 'chrome',
    }


### Finding plagiarized content

This is a [slightly more complex use case](finding_plagiarized_content.py), where plagiarized content is found with GoogleScraper. Google as a search engine is used and selenium mode with
Chrome as frontend.


### Http Mode example

[This example](http_mode_example.py) demonstrates the most simple mode: HTTP mode.

### Image Scraping

This is another quite cute use case of GoogleScraper. In [this example](image_search.py), images are scraped and saved in a `images/` directory. The configuration used looks like this:

    :::python
    config = {
        'keyword': 'beautiful landscape', # :D hehe have fun my dear friends
        'search_engines': ['yandex', 'google', 'bing', 'yahoo'], # duckduckgo not supported
        'search_type': 'image',
        'scrape_method': 'selenium',
        'do_caching': True,
    }
    
### Phantomjs Scraping

If you want to scrape with a headless browser, then [this](phantomjs_example.py) is the perfect example. Phantomjs doesn't need as much resources as Chrome and Firefox and may be run on servers also.