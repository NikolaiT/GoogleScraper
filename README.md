# GoogleScraper - A simple module to scrape and extract links from Google. 

### What does GoogleScraper?

GoogleScraper parses Google search engine results easily and in a performant way. It allows you to extract all found
links problematically and then your application can do whatever it want with them.

There are unlimited use cases:

+ Quickly harvest masses of [google dorks][1].
+ Use it as a SEO tool.
+ Discover trends.
+ Compile lists of sites to feed your own database.
+ Many more use cases...

GoogleScraper is implemented with the following techniques/software:

+ Written in Python 3
+ Uses multihreading/asynchroneous IO.
+ Supports parallel google scraping with multiple IP addresses.
+ Provides proxy support using [socksipy][2]:
  * Socks5
  * Socks4
  * HttpProxy
+ Support for additional google search futures.


### Example Usage


```python
import GoogleScraper
import urllib.parse

if __name__ == '__main__':

    results = GoogleScraper.scrape('HOly shit', number_pages=1)
    for link_title, link_snippet, link_url in results['results']:
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

# How many urls did we get?
print(len(results['results']))

# How many hits has google found with our keyword?
print(results['num_results_for_kw'])
```

### Example Output

This is a example output of the above *use.py*:

```
http://www.urbandictionary.com/define.php?term=holy%20shit
http://idioms.thefreedictionary.com/holy+shit
http://www.youtube.com/watch?v=Uyz-Jk0d_ZM
http://veryholyshit.com/
http://en.wiktionary.org/wiki/holy_shit
https://www.facebook.com/holyshitfreethinkers
https://www.facebook.com/holyshitwisconsinrules
http://en.wikipedia.org/wiki/Holy_shit
http://www.last.fm/music/Holy+Shit
http://www.amazon.com/Holy-Shit-Oliver-Benjamin-ebook/dp/B004YEMYNY
https://myspace.com/holyshit
http://www.reddit.com/r/videos/comments/1lgunv/holy_shit/
http://www.redbull.com/cs/Satellite/en_INT/RedBull/HolyShit/011242745950125
http://www.holyshitshopping.de/index.php?id=59
http://tvtropes.org/pmwiki/pmwiki.php/Main/HolyShitQuotient
http://www.holy-shit.at/
http://www.chelseagreen.com/bookstore/item/holy_shit/
http://www.hotsauceworld.com/holshithabho.html
http://deadspin.com/tag/holy-shit
http://hellsheadbangers.bandcamp.com/album/holy-shit
http://www.redbull.com/cs/Satellite/en_US/Red-Bull-Home/HolyShit/011242746208542
http://www.tumblr.com/tagged/holy-shit
http://pitchfork.com/news/52370-watch-holy-shit-perform-at-ryan-mcginley-gallery-opening-in-san-francisco/
http://rapgenius.com/Sage-the-gemini-dont-you-lyrics/ho-ho-ho-ho-holy-shit?referent=(Ho-ho-ho-ho-holy%20shit)..
http://members.shaw.ca/rlongpre01/moon.html
http://www.southparkstudios.com/clips/152613/holy-shit
http://www.azlyrics.com/lyrics/snowthaproduct/holyshit.html
http://jalopnik.com/holy-shit-brz-wagon-1467880566
http://www.plyrics.com/lyrics/againstme/holyshit.html
http://www.reactiongifs.com/tag/holy-shit/
http://www.lrb.co.uk/v35/n18/colin-burrow/frogs-knickers
http://seenive.com/tag/holyshit
http://www.androidpolice.com/2013/10/28/holy-shit-motorola-announces-project-ara-an-open-modular-smartphone-hardware-platform/
http://www.poetryfoundation.org/poem/181460
http://www.wordreference.com/es/translation.asp?tranword=Holy%20shit
http://www.songkick.com/artists/440811-holy-shit
http://backtothefuture.wikia.com/wiki/Holy_shit
http://store.theonion.com/p-4741-holy-shit-man-walks-on-fucking-moon.aspx
http://gizmodo.com/holy-shit-i-just-spent-236-on-candy-crush-help-1032185653
http://holyshit.fr/
http://skunkpharmresearch.com/holy-anointing-oil-and-holy-shit/
http://holyshitkerorogunso.tumblr.com/
http://soundcloud.com/owlvision/holy-shit
http://pando.com/2013/10/15/voxs-new-mega-round-puts-a-bow-on-contents-holy-shit-moment/
http://holyshitters.com/
http://groupthink.jezebel.com/holy-shit-1476643223
https://www.goodreads.com/book/show/9520102-holy-shit
http://www.goodreads.com/book/show/16225525-holy-sh-t
http://store.jacvanek.com/ProductDetails.asp?ProductCode=HOLYSHIT-MUSCLETEE
http://imgur.com/BcEvR
http://www.penny-arcade.com/2013/07/01/holy-shit5
http://www.redpeters.com/undies/lyrics/christmas.html
http://www.pinterest.com/omgitzaimee/do-it-for-the-holy-shit-you-got-hot/
http://web.stagram.com/tag/holyshit/
https://twitter.com/medaShitFacts
http://www.memecenter.com/search/holy%20shit
http://holyshit.pl/
http://www.stubhub.com/holy-shit-tickets/
http://www.discogs.com/Holy-Shit-Stranded-At-Two-Harbors/release/943934
http://www.discogs.com/artist/Holy+Shit+(2)
http://n4g.com/comments/redirecttocomment/8326799
https://medium.com/startup-baby/573e6e7f6e53
http://dangerpark.storenvy.com/products/143878-holy-shit-a-comics-anthology
http://www.pbh2.com/wtf/the-14-craziest-holy-shit-gifs/
http://dictionary.reverso.net/english-french/holy%20shit
http://www.imdb.com/title/tt0077975/quotes
http://cargocollective.com/jfpoisson/holy-shit
http://www.theguardian.com/books/2013/may/23/holy-shit-history-swearing-mohr
http://kelley-ohara.tumblr.com/
http://songmeanings.com/songs/view/3530822107858556842/
http://www.details.com/style-advice/grooming-and-health/201010/why-do-skinny-healthy-men-think-they-are-fat
http://theoatmeal.com/blog/random_comics
http://www.ratebeer.com/beer/schoppe-holy-shit-christmas-ale/194835/
http://www.beatport.com/track/holy-shit-original-mix/4723265
http://holy-shit.biz/
http://terribleminds.com/ramble/holy-shit-free-thing/
http://randsinrepose.com/archives/the-dark-underbelly-of-holy-shit/
http://holy-shit-a-talking-daisy.tumblr.com/
http://statigr.am/tag/holyshit
http://statter911.com/2012/06/27/raw-video-rescue-from-chicagos-holy-shit-fire/
http://www.hotsauce.com/Holy-Shit-Habanero-Hot-Sauce-p/1907.htm
http://tabs.ultimate-guitar.com/j/johnny_hobo_and_the_freight_trains/politics_of_holy_shit_i_just_cut_open_my_hand_on_a_broken_bottle_crd.htm
http://www.amazon.ca/Holy-Shit-Managing-Manure-Mankind/dp/1603582517
http://www.allmusic.com/album/holy-shit-mw0002125073
https://itunes.apple.com/us/artist/holy-shit/id59428009
http://www.tshirthell.com/funny-shirts/holy-fucking-shit
http://newsbusters.org/blogs/noel-sheppard/2013/10/18/huffington-post-headline-obamacare-nearing-holy-sht-moment
http://knowyourmeme.com/memes/holy-shit-its-a-dinosaur
https://www.adbusters.org/magazine/94/holy-shit.html
http://www.yelp.com/biz/holy-shit-shopping-k%C3%B6ln
http://www.sing365.com/music/lyric.nsf/Holy-Shit-lyrics-Against-Me/33AB5809261EBE3C4825707E0029A0B6
http://holyshitamazingcosplay.tumblr.com/
http://www.patheos.com/blogs/friendlyatheist/2013/09/14/most-holy-water-found-to-contain-not-so-holy-shit/
http://www.animutationportal.com/modules/debaser/player.php?id=80
http://www.metacritic.com/music/holy-shit/living-with-lions
http://pt.bab.la/dicionario/ingles-portugues/holy-shit
http://fatpossum.com/artists/holy-shit
http://detail.chiebukuro.yahoo.co.jp/qa/question_detail/q1014176715
http://vimeo.com/75364288
http://www.amazon.co.uk/Holy-Shit-Managing-Manure-Mankind/dp/1603582517
100
About 55,100,000 results
```

### Direct command line usage

In case you want to use GoogleScraper.py as a CLI tool, use it somehow like this:

```
python GoogleScraper.py -p 1 -n 25 -q 'inurl:".php?id=555"'
```

But be aware that google might recognize you pretty fast as a abuser if you use such google dorks.

Maybe try a socks proxy then (But don't bet on TOR) [This is just a example, this socks will probably not work anymore when *you are here*]

```
python GoogleScraper.py -p 1 -n 25 -q 'i hate google' --proxy="221.132.35.5:2214"
```

### Contact

If you feel like contacting me, do so and send me a mail. You can find my contact information on my [blog][3].

### To-do list (As of 25.12.2013)
+ Figure out whether to use threads or asynchronous I/O for multiple connections.
+ Determine if is is possible to use one google search session with multiple connections that are independent of each other (They have different IP's)

### Stable version

This is a development repository. But you can always find a [working GoogleScraper.py script here][4].


[1]: http://www.webvivant.com/google-hacking.html "Google Dorks"
[2]: https://code.google.com/p/socksipy-branch/ "Socksipy Branch"
[3]: http://incolumitas.com/about/contact/ "Contact with author"
[4]: http://incolumitas.com/2013/01/06/googlesearch-a-rapid-python-class-to-get-search-results/
