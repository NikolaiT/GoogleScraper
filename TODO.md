- edit caching with decorator pattern
- add all google search params to config
- write functional tests
- add sqlalchemy support for results
- add better proxy handling
- extend parsing functionality
- update readme
- prevent parsing config two times

04.11.2014:

  - Refactor code, change docstrings to google format
      https://google-styleguide.googlecode.com/svn/trunk/pyguide.html#Commentss [done]

15.11.2014:
  - add shell access with sqlalchemy session [done]
  - test selenium mode thoroughly [done]
  - double check selectors
  - add alternative selectors
  - Add gevent support
  - make all modes workable through proxies [done for http and sel]
  - update README [done]
  - write blog post that illustrates usage of GoogleScraper
  - some testing
  - release version 0.2.0 on the cheeseshop
      - released version 0.1.5 on pypy [done]

11.12.2014
  - JSON output is still slightly corrupt
  - CSV output probably also not ideal.
  - Improve documentation after Google style guide
  - Maybe add other search engines!
  - finally implement async mode!!!

30.12.2014:
  - Fixed issue #45 [done]

02.01.2015:
  - Check output verbosity levels and modify them. [done]

13.01.2015:
  - Handle sigint. Then close all open files (csv, json).

15.01.2015:
  - Implement JSON static tests [done]
  - Implement CSV static tests [done]
  - Catch Resource warnings in testing [done]

  - Add no_results_selectors for all SE [done]
    - add test for no_results_selectors parsing [done]
  - Add page number selectors for all SE [done]
    - add static tests [done]

  - add fabfile (google a basic template) for []
      - adding & committing and uploading to master []
      - push to the cheeseshop []
  - add function in fabfile that pushes to cheeseshop only after all tests were successful []
  - Add functionality that distinguishes the page number of serp pages when caching []

  - implement async mode [done]
    - reade 20 minutes about asyncio built in moduel and decide whether if feets my needs [done]


18.01.2015

    - add four different examples:
        - a basic usage [done]
        - using selenium mode [done]
        - using http mode [done]
        - using async mode [done]
        - scraping with a keywords.py module
        - scraping images [done]
        - finding plagiarized content [done]


- Add dynamic tests for selenium mode:

    - Add event: No results for this query.

    - Test Impossible query:
        -> Cannot have next_results page
        -> No results [done]
        -> But still save serp page. [done]
        -> add to missed keywords []

    - What is the best way to detect that the page loaded????
        -> Research, read about selenium

    - Add test for duckduckgo


- Fix: If there's no internet connection, Malicious request detected is show. Show no internet connection instead.

- FIGURE OUT: WHY THE HELLO DOES DUCKDUCKGO NOT WORK IN PHANTOMJS?


05.10.2015

    - Switch configuration from INI format to plain python code [Done]
    - recode parse logic for configuration [Done]
        Command Line Settings > Command Line Configuration File > Builtin Configuration File
    - rebuild logging system. Create a dedicate logger for each submodule. [Done]
        Set the loglevel for each logger to the value which was specified in the configuration [Done]
        => Logging only reports events. Results are printed according to a dedicate option in the config file.
    - write tests for all search engines and for all major modes in the source directory.
       Enable Flag which runs the tests automatically. Differ between long tests and short ones.
       - Look at some big open source python projects where tests are stored (pelican, requests)


30.11.2015

    - Find good resources about to learn how to test code correctly
        [DONE: 12min], found the following links:
            - http://docs.python-guide.org/en/latest/writing/tests/
                ==> LEARNED:
                    - put test suites that require some complex data structures to load (such as websites to scrape) in separate test suites
                    - run all (fast) tests before committing code
                    - run all (including slow ones) before pushing code to master
                    - use tox for testing the code with multiple interpreter configurations
                    - mock allows to monkey patch functionality in the code such that it returns whatever you want
            - http://codeutopia.net/blog/2015/04/11/what-are-unit-testing-integration-testing-and-functional-testing/
                ==> LEARNED:
                    - unittets don't make use of external resources such as databases or network
                    - code that is hard to unit test is often poorly designed
                    - integration test: tests how parts of the system work together
                    - functional tests: test the complete functionality of the system
                    - only a small amount of functional tests are required: They make sure the app works as a whole.
                    - "testing common user interactions"
                    - functional tests are validated in the same way as a user who uses the tool.
                    - unit/integration tests are validated with code
                    - don't make them too fine grained!
            - https://code.google.com/p/robotframework/wiki/HowToWriteGoodTestCases
                ==> LEARNED:
                    - never sleep in the code: safety margins take too long in your code (use polls instead)
            - http://blog.agilistic.nl/how-writing-unit-tests-force-you-to-write-good-code-and-6-bad-arguments-why-you-shouldnt/
                ==> LEARNED:
                    - Classes should be loosly coupled
                    - avoid cascade of changes when changing one class
                    - maximize encapsulation in classes
                    - classes should have one responsibility
                    - avoid large and tightly coupled classes
                    - unit test should test the function/class without any dependencies
                    - unit test tests one thing
                    - avoid like the PEST: tightly coupled functions/classes, difficult to understand classes/functions,
                        functions that do many things, not intuitive classes/functions (bad interface)
            - http://www.toptal.com/python/an-introduction-to-mocking-in-python
                ==> LEARNED:
                    - instead of testing a functions effects, we can mock the underlying operating system api by
                        ensuring that a os function was called with certain parameters. This enables us to verify
                        that os code was called with the correct parameters.
            - http://pytest.org/
                ==> LEARNED:
                    - How pytest can be invoked: http://pytest.org/latest/usage.html
                    - pytest can yield more information in the traceback with the -l option
                    - pytest can be called within python: http://pytest.org/latest/usage.html
                    - how the directory structure for tests should look like: http://pytest.org/latest/goodpractises.html

    - Read and understand the test links collected in the previous task.
        [Done: 75min + 25min]

    - Add hook to run unit tests before committing code
        [Done: 9 min]: Found pre-commit hook that checks pep8 stuff and that runs unit tests
            here: https://gist.githubusercontent.com/snim2/6444684/raw/c7f1ec75c3cc0306bd8f36faee7dd201902528e8/pre-commit.py

--- 12 + 100 + 9 + 5 = 126min ---


1.12.2015
    - Read that again: http://pytest.org/latest/example/parametrize.html
        [Done: 9min], not learned anything really. Is about meta programming in test suites I guess.

    - Create virtualenv in Project directory.
        [Done: 5min]

    - Add hook that runs all tests before pushing to master
        [Done: 11min], Hook is a pre-commit hook and will execute all tests found in the directory tests/

    - See whether existing test suites do work and fix all issues there.
        [Started: 122min], integration tests do work. Functional  tests fail, because there is a issue in GoogleScraper. Update: Both integration and functional tests do work.

--- 9 + 5 + 11 + 122 = 147min ---


2.12

    - Find out why the test test_google_with_phantomjs_and_json_output fails. Why is it not possible to scrape 3 pages with Google in selenium mode?
        [Done: 42min]: Because the next page element cannot be located in phantomjs mode for some reason.

    - Why cant phantomjs locate the next page?
        [Done:  46min]:
        - Check version of phantomjs: 1.9.0 is my version
        - Newest version of phantomjs: 2.0, but it is too hard to install/compile
        - Reason that search is interrupted: Exception is thrown in line

    - Read about worker and job patterns (consumer-producer patterns) in python. Learn about queues patterns.
        Read the following ressources:
            - http://www.bogotobogo.com/python/Multithread/python_multithreading_Synchronization_Producer_Consumer_using_Queue.php
            - https://pymotw.com/2/Queue/
            - http://www.informit.com/articles/article.aspx?p=1850445&seqNum=8
            - http://codefudge.com/2015/09/scraping-alchemist-celery-selenium-phantomjs-and-tor.html

    - read about casperJS and evaluate whether it might be interesting for GoogleScraper


3.12

    - Make functional tests work again
        [Done: 120min]


-- Fix bug in `GoogleScraper -q 'apples' -s google -m selenium --sel-browser phantomjs -p 10`


7.12

    - test that serp rank is cumulative among pages
        [Done: 10min] Rank testing doesn't make any sense. Reasons:
            - ranks start again in different type of serp results (ads vs normal)
            - results aren't ordered by rank in json or csv/output
            - ranks doesn't need to be cumulative, since their absolute rank can be
                recalculated by multiplying with the page number.

    - fix functional test issues of `test_all_search_engines_in_http_mode
        [Began: 52min], duckduckgo works. yahoo improved.


### 18.8.2018
- Integrate Google Maps Search into GoogleScraper
- Integrate [http://scrapoxy.io/](http://scrapoxy.io/) into Google Scraper
- Integrate Amazon Lambda into Google Scraper. Maybe don't make this feature Open Source
    + https://stackoverflow.com/questions/49953271/running-selenium-webdriver-in-amazon-lambda-python
    + http://robertorocha.info/setting-up-a-selenium-web-scraper-on-aws-lambda-with-python/
- Integrate Amazon Search and Ebay Search

### 23.8.2018
Problem: As http://phantomjs.org/ suggests, Important: PhantomJS development is suspended until further notice (more details).

Use headless version of chrome: https://github.com/dhamaniasad/HeadlessBrowsers
    Selenium support for PhantomJS has been deprecated, please use headless versions of Chrome or Firefox instead
    warnings.warn('Selenium support for PhantomJS has been deprecated, please use headless '

**Solution**: It seems that the way to go is to use https://github.com/GoogleChrome/puppeteer a mature project with 36000 stars.
Thus I will deprecate usign phantomjs as the headless API. But there is a problem, puppeteer is written in NodeJS. There is a Python Port called https://github.com/miyakogi/pyppeteer , but I distrust that the Python port is the same quality as the Google supported development
of the NodeJS version. Thus I will use https://github.com/GoogleChrome/puppeteer

Alternative to using puppeteer: use selenium with chrome headless:
https://duo.com/decipher/driving-headless-chrome-with-python

### 27.8.18

+ Write functional test for Google and Bing [DONE]
+ Think about integrating https://2captcha.com/2captcha-api#rates

### 29.8.18

+ Add possibility to change search settings to selenium mode for Google
  + Change country/region
  + Change language
  + Change number of search results


### 05.09.2018

+ Implement reliable google "request denied" detection [Halfway done, more testing required]
  + Code something that detects when google asks for it's recaptcha v2
  + Scraping 300 keywords with selenium mode and 5 browser instaces is no problem after initialling inputing a captcha
  + Test 10 simultaenous browsers and 1000 keywords (50 cities plus suffixes ('best coffee', 'best restaurant', 'best dentist', 'best hairdresser'))

+ Integrate captcha solving service such as https://2captcha.com/
+ Look for good captcha solving services such as https://2captcha.com/   

### 07.09.2018

+ fix sleeping ranges [DONE]
+ add option to sleep X minutes after N scrapes. [DONE]


### 08.09.2018
 
+ Parce Google Map Recommondations [DONE]
+ Minimize resouce consumation in selenium scraping with chrome [DONE]
	- https://stackoverflow.com/questions/49008008/chrome-headless-puppeteer-too-much-cpu
	- https://news.ycombinator.com/item?id=14103503
	- https://news.ycombinator.com/item?id=14103503
	- Its better to use tabs than new instances: https://github.com/GoogleChrome/puppeteer/issues/1569

+ Write code that manages X tabs within Y browser instances to yield X*Y scraper instances
	+ https://blog.phantombuster.com/web-scraping-in-2017-headless-chrome-tips-tricks-4d6521d695e8?gi=7edcb5e70c66
+ Very good article about web scraping in general: https://blog.phantombuster.com/web-scraping-in-2017-headless-chrome-tips-tricks-4d6521d695e8


+ Add detection check