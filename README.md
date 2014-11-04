## GoogleScraper - Scraping the Google Search Engine

### Table of Contents

1. [Installation](#install)
2. [About](#about)
3. [Usage with Python](#usage)
4. [Command line usage (read this!)](#cli-usage)
5. [Contact](#contact)


<a name="install" \>
### Installation

GoogleScraper is written in Python 3. You should install at least Python 3.3
Furthermore, you need to install the Chrome Browser, maybe even the ChromeDriver for Selenium mode (I didn't have to).

From now on (August 2014), you can install GoogleScraper comfortably with pip:

```
pip3 install GoogleScraper
```

#### Alternatively install from Github:

First clone and change into the project tree.

Begin with installing the following third party modules:

```
selenium
beautifulsoup4
cssselect
requests
PyMySql
```

You can do so with:

`pip3 install module1, module2, ..` or better by `pip install -r requirements.txt`


If you don't want to install GoogleScraper system wide, just make a virtual environment (Run all commands in the GoogleScraper.py directory):

```bash
git clone https://github.com/NikolaiT/GoogleScraper
cd GoogleScraper
virtualenv --no-site-packages --python=python3 .venv
source .venv/bin/activate
.venv/bin/python setup.py install
# now you can run GoogleScraper from withing the virtual environment
./venv/bin/GoogleScraper
```

<a name="about" />
### What does GoogleScraper.py?

GoogleScraper parses Google search engine results easily and in a performant way. It allows you to extract all found
links and their titles and descriptions programmatically which enables you to process scraped data further.

There are unlimited *usage scenarios*:

+ Quickly harvest masses of [google dorks][1].
+ Use it as a SEO tool.
+ Discover trends.
+ Compile lists of sites to feed your own database.
+ Many more use cases...

First of all you need to understand that GoogleScraper uses **two completely different scraping approaches**:
+ Scraping with low level networking libraries such as `urllib.request` or `requests` modules. This simulates the http packets sent by real browsers.
+ Scrape by controlling a real browser with Python

Whereas the later approach was implemented first, the former approach looks much more promising in comparison, because
Google has no easy way detecting it.

GoogleScraper is implemented with the following techniques/software:

+ Written in Python 3.4
+ Uses multithreading/asynchroneous IO. (two possible approaches, currently only multi-threading is implemented)
+ Supports parallel google scraping with multiple IP addresses.
+ Provides proxy support using [socksipy][2] and built in browser proxies:
  * Socks5
  * Socks4
  * HttpProxy
+ Support for additional google search features like news/image/video search.

### How does GoogleScraper maximize the amount of extracted information per IP address?

Scraping is a critical and highly complex subject. Google and other search engine giants have a strong inclination
to make the scrapers life as hard as possible. There are several ways for the Google Servers to detect that a robot is using
their search engine:

+ The User-Agent is not one of a browser.
+ The search params are not identical to the ones that browser used by a human sets:
  * Javascript generates challenges dynamically on the client side. This might include heuristics that try to detect human behaviour. Example: Only humans move their mouses and hover over the interesting search results.
+ Robots have a strict requests pattern (very fast requests, without a random time between the sent packets).
+ Dorks are heavily used
+ No pictures/ads/css/javascript are loaded (like a browser does normally) which in turn won't trigger certain javascript events

So the biggest hurdle to tackle is the javascript detection algorithms. I don't know what Google does in their javascript, but I will soon investigate it further and then decide if it's not better to change strategies and
switch to a **approach that scrapes by simulating browsers in a browserlike environment** that can execute javascript. The networking of each of these virtual browsers is proxified and manipulated such that it behaves like
a real physical user agent. I am pretty sure that it must be possible to handle 20 such browser sessions in a parallel way without stressing resources too much. The real problem is as always the lack of good proxies...

### How to overcome difficulties of low level (http) scraping?

As mentioned above, there are several drawbacks when scraping with `urllib.request` or `requests` modules and doing the networking on my own:

Browsers are ENORMOUSLY complex software systems. Chrome has around 8 millions line of code and firefox even 10 LOC. Huge companies invest a lot of money to push technology forward (HTML5, CSS3, new standards) and each browser
has a unique behaviour. Therefore it's almost impossible to simulate such a browser manually with HTTP requests.  This means Google has numerous ways to detect anomalies and inconsistencies in the browsing usage. Alone the
dynamic nature of Javascript makes it impossible to scrape undetected.

This cries for an alternative approach, that automates a **real** browser with Python. Best would be to control the Chrome browser since Google has the least incentives to restrict capabilities for their own native browser.
Hence I need a way to automate Chrome with Python and controlling several independent instances with different proxies set. Then the output of result grows linearly with the number of used proxies...

Some interesting technologies/software to do so:
+ [Selenium](https://pypi.python.org/pypi/selenium)
+ [Mechanize](http://wwwsearch.sourceforge.net/mechanize/)


<a name="usage" \>
### Example Usage
Here you can learn how to use GoogleScrape from within your own Python scripts.

If you want to play with GoogleScraper programmatically, dig into the ```examples/``` directory in the source tree.
You will find some examples, including how to enable proxy support.

Keep in mind that the bottom example source uses the not very powerful *http* scrape method. Look [here](#cli-usage) if you
need to unleash the full power of GoogleScraper.

```python
#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Shows how to control GoogleScraper programmatically. Uses selenium mode.
"""

from GoogleScraper import scrape_with_config, GoogleSearchError

if __name__ == '__main__':
    # See in the config.cfg file for possible values
    config = {
        'SCRAPING': {
            'use_own_ip': 'True',
            'keyword': 'Hello World'
        },
        'SELENIUM': {
            'sel_browser': 'chrome',
            'manual_captcha_solving': 'True'
        },
        'GLOBAL': {
            'do_caching': 'True'
        }
    }

    try:
        # scrape() and scrape_with_config() will reuturn a handle to a sqlite database with the results
        db = scrape_with_config(config)

        print(db.execute('SELECT * FROM link').fetchall())

    except GoogleSearchError as e:
        print(e)
```

### Example Output

This is a example output of the above *use.py*. You can execute it by just firing `python use.py` in the project directory:

```
[nikolai@niko-arch GoogleScraper]$ python use.py
http://searchenginewatch.com/article/2303494/21-Best-FREE-SEO-Tools-for-On-Page-Optimization
http://seo-tools-review.toptenreviews.com/
http://www.seobook.com/seo-tools-for-2014
http://moz.com/blog/100-free-seo-tools
https://blog.kissmetrics.com/6-indispensable-seo-tools/
http://www.targetinternet.com/seo-tools-comparison-raven-seomoz-buzzstream/
http://www.hobo-web.co.uk/best-seo-tools/
http://www.creativebloq.com/netmag/30-best-new-seo-tools-7133746
http://www.best-seo-tools.net/
http://www.traffictravis.com/
http://seotools.scrubtheweb.com/
http://www.youtube.com/watch?v=WWPzgsojW8w
https://www.brightlocal.com/
http://www.wordstream.com/blog/ws/2013/09/18/best-keyword-research-tools
http://www.matthewwoodward.co.uk/tips/the-best-free-seo-tools-internet-marketing-software/
http://socialmediatoday.com/amanda-disilvestro/1377151/top-7-must-have-free-seo-tools-beginners
http://www.poweredbysearch.com/top-10-seo-tools-worth-it/
http://www.ragesw.com/products/iweb-seo-tool.html
http://www.searchenginejournal.com/the-best-seo-tools-what-how-and-why/60842/
http://withnoble.com/10-best-seo-tools-for-keyword-research/
http://searchengineland.com/moz-2014-industry-survey-google-webmaster-tools-top-ranked-seo-tool-182767
https://yoast.com/wordpress/plugins/seo/
https://yoast.com/tools/seo/
http://www.webceo.com/
http://www.myseotool.com/
http://www.smashingmagazine.com/2006/09/22/complete-list-of-best-seo-tools/
http://www.strategyinternetmarketing.co.uk/best-online-seo-tools/
http://seoimpression.blogspot.com/2013/02/top-ten-seo-tools-of-2013.html
http://www.socialable.co.uk/25-best-seo-tools-wordpress-plugins/
http://vlexo.net/blog-tips-tricks/search/best-seo-tools-resources-youll-need-in-2014/
https://forums.digitalpoint.com/threads/best-seo-tools-for-2014.2700177/
http://www.majesticseo.com/
http://seo-software.findthebest.com/
http://seometamanager.com/
https://twitter.com/JohnHen99387191
http://www.link-assistant.com/
http://www.techrepublic.com/blog/five-apps/five-seo-tools-that-will-increase-visitors-to-your-website/
http://www.razorsocial.com/seo-tools-blogging/
http://www.ibusinesspromoter.com/seo-tools/top-10-seo-software
http://zoomspring.com/learn-importxml-tutorial/
http://www.prweb.com/releases/best-seo-tools/seo-in-2014-tips/prweb11381533.htm
http://seoertools.com/
http://www.internetmarketingninjas.com/tools/
http://www.seosuite.com/
http://www.clickminded.com/free-seo-tools/
http://www.dreamscapedesign.co.uk/the-best-free-online-seo-tools/
http://cognitiveseo.com/
https://support.google.com/webmasters/answer/35291?hl=en
http://www.wpseotricks.com/best-seo-tools-2013/
http://www.facebook.com/615013581900538
http://www.webconfs.com/15-minute-seo.php
http://www.screamingfrog.co.uk/seo-spider/
http://www.coconutheadphones.com/search-engine-tools-some-of-the-best-seo-tools-are-free/
http://zadroweb.com/best-seo-tools-get-site-ranking/
http://www.seoeffect.com/
http://www.seoworkers.com/tools/analyzer.html
http://travisleestreet.com/2013/07/best-seo-tools-for-online-marketers/
http://2thetopdesign.com/the-4-seo-tools-you-need-to-know/
http://www.bruceclay.com/seo/search-engine-optimization.htm
http://www.bestseotool.com/
http://www.papercutinteractive.com/blog/entry/the-best-seo-tools-for-beginners
http://rankmondo.com/seo-tools/best-link-building-tools/
http://blog.dh42.com/best-seo-tools/
http://www.webseoanalytics.com/
http://www.seotools.com/
http://www.3rank.com/top-10-best-seo-tools-for-bloggers-and-webmasters/
http://www.blogherald.com/2013/11/04/the-best-seo-tools-for-keyword-research/
https://www.visibilitymagazine.com/buyersguide/best_seo_software
http://www.localseoguide.com/local-seo-tools/
http://www.business2community.com/seo/top-emerging-seo-tools-use-2014-0747745
http://www.benchmarkemail.com/blogs/detail/best-seo-tools
http://smallbusiness.yahoo.com/advisor/25-best-seo-tools-wordpress-plugins-195102924.html
http://sourceforge.net/projects/seotoolkit/
http://seocombine.com/
http://www.conductor.com/resource-center/presentations/pubcon-new-orleans-2013-brian-mcdowell-best-seo-tools
http://www.smallbiztechnology.com/archive/2012/06/13-top-seo-tools-for-startups.html/
http://www.ask.com/question/what-are-the-best-free-online-seo-tools
http://www.blackhatworld.com/blackhat-seo/f9-black-hat-seo-tools/
http://www.bestseosuite.com/
http://www.bestseobot.com/
http://www.webmaster-talk.com/threads/200470-Which-is-the-best-SEO-tool-for-MAC
http://blog.jimdo.com/top-5-free-seo-tools/
http://www.searchenginexperts.com.au/seo-blog/top-10-free-seo-tools
http://www.theseoace.com/resources/
http://dashburst.com/top-seo-tools-to-combat-google-panda-and-penguin/
http://www.atozbuzz.com/2013/02/5-best-seo-tools-for-your-websites.html
http://www.seoworks.com/seo-tools-tips/best-seo-software-tools/
http://smallseotools.com/backlink-maker/
http://www.urlmd.com/seo/best-seo-tool-of-2013/
http://www.siteopsys.com/
http://www.trendmx.com/
http://www.seochat.com/
http://intechseo.com/seo-tools
http://vkool.com/11-best-online-seo-tools/
http://blogsuccessjournal.com/seo-search-engine-optimization/seo-tools/seo-tools-top-free-video/
http://www.webseotoolbox.com/index.php?/Knowledgebase/List/Index/23/webmaster-tools
http://www.seocompany.ca/tool/seo-tools.html
http://www.blackhatprotools.com/
http://seowebhosting.net/best-seo-tools/
http://www.grademyseo.com/index.php?do=tools
http://webmeup.com/seo-tools-review/
http://seotoolsvps.ca/
http://extremeseotools.com/signup/knowledgebase.php
http://sickseo.co.uk/
http://backlinko.com/white-hat-seo
http://www.bloggingtips.com/2013/12/28/top-seo-tools-find-targeted-keywords/
http://www.fatbit.com/fab/tag/best-seo-tool/
http://seo.venturebeat.com/
http://www.sheerseo.com/
http://zwinks.org/blog/general/seo-tools-and-internet-marketing-software-of-choice/
http://www.clambr.com/link-building-tools/
http://www.bloggeryard.com/2013/11/best-free-seo-tools.html
http://my.opera.com/tabreraliboldri/about/
http://www.seoserviceslosangeles.com/free-seo-tools.php
https://todaymade.com/blog/google-adwords-seo/
http://inblurbs.com/blog/the-best-seo-tools-for-keyword-research/
http://www.webhostingtalk.com/showthread.php?t=1324995
http://www.hittail.com/
http://thecreativemomentum.com/blog/2013/12/04/why-blogs-are-one-of-your-best-seo-tools/
http://www.hubspot.com/products/seo
http://www.quora.com/SEO-Tools/What-are-the-best-paid-tools-for-link-building
http://www.getapp.com/seo-sem-software
http://bestfreeseo.webs.com/
http://www.seotoolset.com/tools/free_tools.html
http://www.lakanephotography.co.uk/articles/free-seo-tools
http://seositecheckup.com/
http://spydermate.com/
http://www.best-5.com/seo-tools/
http://wpvkp.com/best-wordpress-seo-plugins/
http://www.advancedwebranking.com/
http://www.linkresearchtools.com/
http://tripleseo.com/free-seo-tools/
http://www.linkcollider.com/
http://nohandsseo.com/
http://5000best.com/tools/SEO_Tools/
http://www.tipsandtricks-hq.com/top-10-seo-tools-and-add-ons-for-your-online-business-6510
http://seotoolonline.com/
http://www.staples.com/sbd/cre/tech-services/explore-tips-and-advice/tech-articles/optimize-away-top-seo-tools-tricks-to-dominate-google.html
http://www.blackwoodproductions.com/blackwoodproductions.php?Action=cms&k=rebrand
http://solutionsbydave.com/best-free-seo-tools-all-on-this-page-seo-expert-tools/
http://www.bing.com/toolbox/seo-analyzer
http://www.digitalmillionaires.com/forum/main-category/seo-tools/278-what-is-the-best-seo-tool-this-year
http://www.quicksprout.com/2013/10/10/are-you-doing-your-seo-wrong/
http://www.wordtracker.com/
http://acodez.in/best-free-online-seo-tools-part-3/
https://monitorbacklinks.com/seo-tools/free-backlink-checker
http://www.practicalecommerce.com/articles/60622-27-WordPress-SEO-Plugins
https://swissmademarketing.com/secockpit/
http://www.seoinpractice.com/seo-software-bundle.html
http://www.whitespark.ca/
151
About 14,100,000 results
```

<a name="cli-usage" \>
### Direct command line usage

Probably the best way to use GoogleScraper is to use it from the command line and fire a command such as
the following:
```
python GoogleScraper.py sel --keyword-file path/to/keywordfile
```

Here *sel* marks the scraping mode as 'selenium'. This means GoogleScraper.py scrapes with real browsers. This is pretty powerful, since
you can scrape long and a lot of sites (Google has a hard time blocking real browsers). The argument of the flag `--keyword-file` must be a file with keywords separated by
newlines. So: For every google query one line. Easy, isnt' it?

Example keyword-file:
```
keyword number one
how to become a good rapper
inurl:"index.php?sl=43"
filetype:.cfg
allintext:"You have a Mysql Error in your"
intitle:"admin config"
Best brothels in atlanta
```

By default, *sel* mode only requests the first 10 results for each keyword. But you can specify on how many Google result pages
you want to scrape every keyword. Just use the **-p** parameter as shown below:

```
# searches all keywords in the keywordfile on 10 result pages
python GoogleScraper.py sel --keyword-file path/to/keywordfile -p 10
```

By now, you have 10 results per page by default (google returns up to 100 results per page), but this will also be configurable in the near future. *http* mode
supports up to 100 results per page.

After the scraping you'll automatically have a new sqlite3 database in the ```google_scraper_results``` directory (with a date time string as file name). You can open the database with any sqlite3 command
line tool or other software.

It shouldn't be a problem to scrape **_10'000 keywords in 2 hours_**. If you are really crazy, set the maximal browsers in the config a little
bit higher (in the top of the script file).

If you want, you can specify the flag `--proxy-file`. As argument you need to pass a file with proxies in it and with the following format:

```
protocol proxyhost:proxyport username:password
(...)
```
Example:
```
socks5 127.0.0.1:1080 blabla:12345
socks4 77.66.55.44:9999 elite:js@fkVA3(Va3)
```

That's basically all for the *sel* modeHave fun.

In case you want to use GoogleScraper.py in *http* mode (which means that raw http headers are sent), use it as follows:

```
python GoogleScraper.py http -p 1 -n 25 -q "keywords separated by whitespaces"
```

<a name="contact" \>
### Contact

If you feel like contacting me, do so and send me a mail. You can find my contact information on my [blog][3].

[1]: http://www.webvivant.com/google-hacking.html "Google Dorks"
[2]: https://code.google.com/p/socksipy-branch/ "Socksipy Branch"
[3]: http://incolumitas.com/about/contact/ "Contact with author"
[4]: http://incolumitas.com/2013/01/06/googlesearch-a-rapid-python-class-to-get-search-results/
