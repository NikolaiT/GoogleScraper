GoogleScraper - A simple module to scrape and extract links from Google. 
========================================================================

GoogleScraper supports the following scenarious:

+ Written in Python 3
+ Uses multihreading/asynchroneous IO.
+ Supports parallel google scraping with multiple IP addresses.
+ Provides proxy support:
	..* Socks5
	..* Socks4
	..* HttpProxy
+ Support for additional google search futures.


Examle Usage
------------

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
