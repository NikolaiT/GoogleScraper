## GoogleScraper - Scraping the Google Search Engine

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
+ Scrape with low level networking libraries such as `urllib.request` or `requests` modules and thus emulate a browser
+ Scrape by controlling a real browser with Python

Whereas the first approach was implemented first, the second approach looks much more promising in comparison.
Effective: Development for the second approach started around 10.03.2014

GoogleScraper is implemented with the following techniques/software:

+ Written in Python 3.3
+ Uses multithreading/asynchroneous IO. (two approaches, currently only multi-threading is implemented)
+ Supports parallel google scraping with multiple IP addresses.
+ Provides proxy support using [socksipy][2]:
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

Browsers are ENORMOUSLY complex software systems. Chrome has around 8 millions line of code and firefox even 10 LOC. Huge companies invest a lot of money to push technoliges forward (HTML5, CSS3, new standards) and each browser
has a unique behaviour. Therefore it's almost impossible to simulate such a browser manually with HTTP requests.  This means Google has numerous ways to detect anomalies and inconsistencies in the browsing usage. Alone the
dynamic nature of Javascript makes it impossible to scrape undetected.

This cries for an alternative approach, that automates a **real** browser with Python. Best would be to control the Chrome browser since Google has the least incentives to restrict capabilities for their own native browser.
Hence I need a way to automate Chrome with Python and controlling several independent instances with different proxies set. Then the output of result grows linearly with the number of used proxies...

Some interesting technologies/software to do so:
+ [Selenium](https://pypi.python.org/pypi/selenium)
+ [Mechanize](http://wwwsearch.sourceforge.net/mechanize/)

### Example Usage

```python
import GoogleScraper
import urllib.parse

if __name__ == '__main__':

    results = GoogleScraper.scrape('Best SEO tool', num_results_per_page=50, num_pages=3, offset=0, searchtype='normal')
    for page in results:
        for link_title, link_snippet, link_url in page['results']:
            # You can access all parts of the search results like that
            # link_url.scheme => URL scheme specifier (Ex: 'http')
            # link_url.netloc => Network location part (Ex: 'www.python.org')
            # link_url.path => URL scheme specifier (Ex: ''help/Python.html'')
            # link_url.params => Parameters for last path element
            # link_url.query => Query component
            try:
                print(urllib.parse.unquote(link_url.geturl())) # This reassembles the parts of the url to the whole thing
            except:
                pass

# How many urls did we get on all pages?
print(sum(len(page['results']) for page in results))

# How many hits has google found with our keyword (as shown on the first page)?
print(results[0]['num_results_for_kw'])
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

### Direct command line usage

In case you want to use GoogleScraper.py as a CLI tool, use it somehow like this:

```
python GoogleScraper.py -p 1 -n 25 -q 'inurl:".php?id=555"'
```

But be aware that google might recognize you pretty fast as a abuser if you use such google dorks as given above.

Maybe try a socks proxy then (But don't bet on TOR) [This is just a example, this socks will probably not work anymore when *you are here*]

```
python GoogleScraper.py -p 1 -n 25 -q 'i hate google' --proxy="221.132.35.5:2214"
```

### Contact

If you feel like contacting me, do so and send me a mail. You can find my contact information on my [blog][3].

### To-do list (As of 25.12.2013, updated at 16th february 2014)
+ Figure out whether to use threads or asynchronous I/O for multiple connections. [x]
+ Determine if is is possible to use one google search session with multiple connections that are independent of each other (They have different IP's)
+ Implement the proxy manager that intelligently uses proxies to maximize the extracted information per IP.

### Stable version
I will experiment with a threading approach and asynchronous IO. There will always be a stable version that supports threading. It is simply
called `GoogleScraper.py`. The asynchronous version will be called `GoogleScraperAsync.py`.

**Last major update:** 10th march 2014

This is a development repository. But you can always find a [working GoogleScraper.py script here][4].

[1]: http://www.webvivant.com/google-hacking.html "Google Dorks"
[2]: https://code.google.com/p/socksipy-branch/ "Socksipy Branch"
[3]: http://incolumitas.com/about/contact/ "Contact with author"
[4]: http://incolumitas.com/2013/01/06/googlesearch-a-rapid-python-class-to-get-search-results/
