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



