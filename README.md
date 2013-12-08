# GoogleScraper - A simple module to scrape and extract links from Google. 

### What does GoogleScraper?

GoogleScraper parses Google search engine results easily and in a performant way. It allows you to extract all found
links programmatically and then your application can do whatever it want with them.

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
	
	urls = GoogleScraper.scrape('inurl:"view.php?tid=23"', number_pages=2)
	for url in urls:
		# You can access all parts of the search results like that
		# url.scheme => URL scheme specifier (Ex: 'http')
		# url.netloc => Network location part (Ex: 'www.python.org')
		# url.path => URL scheme specifier (Ex: ''help/Python.html'')
		# url.params => Parameters for last path element
		# url.query => Query component
		print(urllib.parse.unquote(url.geturl()))

	print('#################################################################')	
	print('[!] Received %d results by asking %d pages with %d results per page' %
				(len(urls), 2, 100))

```

### Example Output

This is a example output of *GoogleScraper.py* using the search query **cute cats**:

```
author@arch-linux GoogleScraper]$ python3 use.py 
http://www.cutecatgifs.com/
http://imgur.com/QnkFrG3
http://www.sadanduseless.com/2012/10/hard-truth-from-cats/
http://www.petmd.com/cat/centers/kitten/top-male-cat-names-for-kittens-cute-popular
http://www.swcp.com/
http://www.blogger.com/?tab=wj
http://stuffonmycat.com/
http://agentmlovestacos.com/post/1671470859/9-gifs-of-cats-being-cute
http://www.pinterest.com/lovemypetpics/cute-cats/
http://greatinspire.com/cute-cat-pictures/
http://www.boredpanda.com/tag/cute-cats/
http://www.petmd.com/cat/centers/kitten/top-female-cat-names-for-kittens-cute-popular
http://on.aol.com/video/viral-video--cute-cat-gets-caught-stealing-from-drawer-517912359
http://allcutecats.blogspot.com/
http://i-justreally-like-cats-okay.tumblr.com/
http://icanhas.cheezburger.com/
http://www.lifewithcats.tv/category/video/cute-cat-videos/
http://weheartit.com/tag/cute%20cat
http://www.bbc.co.uk/news/technology-25103362
http://lolomoda.com/cute-cats-pictures/
http://cutecatsdaily.tumblr.com/
http://www.cute-cats.com/
http://www.reallycutecats.com/
http://www.flixxy.com/cute-cats-compilation.htm
http://photobucket.com/images/cute%20cat
http://cutecatfaith.com/
https://www.facebook.com/CatsCuteCat+cute+cats&tbo=1&sa=X&ei=bmOiUqOGHc3bsgaH4ID4DQ&ved=0CE4QHzAK
http://www.fanpop.com/clubs/cats/images/8477446/title/cute-cats-photo
http://seenive.com/u/922490028846882816
http://iheartcatgifs.tumblr.com/
http://metro.co.uk/2013/08/16/are-these-the-ten-cutest-cats-on-the-internet-3924949/
http://www.telegraph.co.uk/news/newstopics/howaboutthat/10368191/Cute-cat-or-ugly-cat-The-new-feline-from-China-taking-the-internet-by-storm.html
http://on.aol.com/video/viral-video--cute-cat-gets-caught-stealing-from-drawer-517912359
http://hahacats.com/
http://profilepictures.weebly.com/cute-cats-profile-pictures.html
http://www.cracked.com/article/226_6-adorable-cat-behaviors-with-shockingly-evil-explanations/
http://www.pbh2.com/pets-animals/cutest-cat-gifs/
http://noisey.vice.com/you-review-show/do-cute-cats-like-gangnam-style
http://catvideooftheweek.com/
http://cuteboyswithcats.net/
http://www.girlsgogames.co.uk/games/cat_games/cat_games.html
http://metro.co.uk/2013/11/27/pictures-of-cute-cats-can-help-you-learn-new-languages-4204229/
http://we-love-cute-cats.tumblr.com/
http://www.roflcat.com/
http://www.cutecatcoverage.com/
http://www.hiddennumbersgames.com/cute-cats-hidden-numbers-game.html
http://its-a-cat-world.tumblr.com/
http://cutegirlswithcats.tumblr.com/
http://www.recycler.com/cats
http://www.kittenwar.com/
http://9meow.blogspot.com/2012/10/cute-cats-5.html
http://www.ebay.co.uk/bhp/cute-cat-t-shirt
http://www.the-cat-collection.com/cute-cats.html
http://cutest-cats.tumblr.com/
http://www.huffingtonpost.com/tag/cute-cats
http://slashdot.org/story/13/11/20/1733202/cute-cat-photos-are-data-driven-science-behind-cunning-new-language-learning-app
http://thefluffingtonpost.com/
http://www.lolcats.com/
http://www.amazon.com/Cats-Pajamas-101-Worlds-Cutest/dp/B004IK9F9K
http://www.telegraph.co.uk/news/newstopics/howaboutthat/10368191/Cute-cat-or-ugly-cat-The-new-feline-from-China-taking-the-internet-by-storm.html
http://matties3333.edublogs.org/2013/09/19/cute-cats/
http://www.oregonlive.com/pets/index.ssf/2013/11/pet_of_the_week_alice_is_a_won.html
http://www.glamour.com/entertainment/blogs/obsessed/2013/11/11-cute-cats-and-dogs-to-be-th.html
http://www.cutestpaw.com/articles/50-cute-cats-make-your-life-happier/
http://lolcat.com/
http://lovemeow.com/tag/cute-cat-video/
http://www.catsofaustralia.com/cute_kitten_pictures.htm
http://distractify.com/people/male-models-and-cats/
http://likes.com/cute/cute-cats-and-their-animal-friends
http://blogs.wsj.com/tech-europe/2013/11/20/cute-cats-that-help-you-learn-spanish-no-really/
http://www.pawnation.com/2012/12/26/50-cutest-pawnation-cats-of-2012/
http://www.slrlounge.com/hot-guys-cute-cats
http://www.fanpop.com/clubs/cats/images/248645/title/freakin-cute-wallpaper
http://cutestcats.us/
http://www.reddit.com/r/aww
http://techcrunch.com/2013/11/20/catacademy/
http://www.mnn.com/family/pets/stories/10-cute-quirky-commercials-starring-cats
http://www.itn.co.uk/And%20Finally/90248/can-cute-cat-pictures-actually-help-you-learn-spanish-
http://www.fanpop.com/clubs/cats/images/8477446/title/cute-cats-photo
http://www.buzzfeed.com/ariellecalderon/cats-having-a-way-worse-day-than-you
http://9meow.blogspot.com/2012/10/cute-cats-5.html
http://www.girlsgogames.com/game/cute_cat_dress_up.html
http://catsofinstagram.com/
http://all-free-download.com/free-photos/cute-cats.html
http://www.tumblr.com/tagged/cute-cats
http://www.cutecatvideos.net/
http://www.tumblr.com/tagged/cute-cat
http://fuckyeahcuteguyswithcats.tumblr.com/
http://www.ebay.com/bhp/cute-cat-figurine
https://www.facebook.com/CatsCuteCat
http://yamkote.com/channel/cats
http://www.zazzle.com/cute+cat+gifts
http://www.break.com/c/animals-videos/cats/
http://theberry.com/2012/01/19/daily-awww-fluffy-kitty-cats-31-photos/
http://animal.discovery.com/tv-shows/americas-cutest-pet/videos/americas-cutest-cat.htm
http://www.123greetings.com/pets/
http://www.funnycatpix.com/
http://www.parade.com/221433/jonathanhorowitz/the-daily-cute-national-cat-day/
http://www.thedailycute.com/category/cats/
http://www.dailymail.co.uk/news/article-2449836/Is-Snoopybabe-cutest-cat-internet.html
http://en.rocketnews24.com/2013/11/21/watch-out-for-cute-overload-see-these-cats-with-awesomely-unique-markings%E3%80%90pics%E3%80%91/
http://www.uproxx.com/gammasquad/2013/11/the-hunger-games-remade-with-cats/
http://www.huffingtonpost.co.uk/tag/cute-cats
http://www.smartplanet.com/blog/bulletin/can-cute-cats-help-you-learn-a-language/
http://9meow.blogspot.com/2012/10/cute-cats-5.html
http://www.blogger.com/?tab=wj
http://www.blogger.com/?tab=wj
http://www.blogger.com/?tab=wj
http://www.blogger.com/?tab=wj
#################################################################
[!] Received 109 results by asking 2 pages with 100 results per page
```


### Contact

If you feel like contacting me, do so and send me a mail. You can find my contact information on my [blog][3].


[1]: http://www.webvivant.com/google-hacking.html "Google Dorks"
[2]: https://code.google.com/p/socksipy-branch/ "Socksipy Branch"
[3]: http://incolumitas.com/about/contact/ "Contact with author"
