"""
Contains all parameters and sources/information about the parameters of the supported search engines.

All values set to None, are NOT INCLUDED in the GET request! Everything else (also the empty string), is included in the request
"""

"""Google search params

Some good stuff:
    http://www.blueglass.com/blog/google-search-url-parameters-query-string-anatomy/
    http://www.rankpanel.com/blog/google-search-parameters/
    http://lifehacker.com/5933248/avoid-getting-redirected-to-country-specific-versions-of-google

All search requests must include the parameters site, client, q, and output. All parameter values
must be URL-encoded (see “Appendix B: URL Encoding” on page 94), except where otherwise noted.
"""
google_search_params = {
    'q': '',  # the search query string
    'oq': None,  # Shows the original query.
    'num': '',  # the number of results per page
    'numgm': None,
    # Number of KeyMatch results to return with the results. A value between 0 to 50 can be specified for this option.
    'start': '0',
    # Specifies the index number of the first entry in the result set that is to be returned.
    # page number = (start / num) + 1
    # The maximum number of results available for a query is 1,000, i.e., the value of the start parameter added to
    # the value of the num parameter cannot exceed 1,000.
    'rc': None,  # Request an accurate result count for up to 1M documents.
    'site': None,
    # Limits search results to the contents of the specified collection. If a user submits a search query without
    # the site parameter, the entire search index is queried.
    'sort': None,  # Specifies a sorting method. Results can be sorted by date.
    'client': 'firefox-a',
    # Required parameter. If this parameter does not have a valid value, other parameters in the query string
    # do not work as expected. Set to 'firefox-a' in mozilla firefox
    # A string that indicates a valid front end and the policies defined for it, including KeyMatches, related
    # queries, filters, remove URLs, and OneBox Modules. Notice that the rendering of the front end is
    # determined by the proxystylesheet parameter. Example: client=myfrontend
    'output': None,
    # required parameter. Selects the format of the search results. 'xml_no_dtd XML' : XML results or custom
    # HTML, 'xml': XML results with Google DTD reference. When you use this value, omit proxystylesheet.
    'partialfields': None,
    # Restricts the search results to documents with meta tags whose values contain the specified words or
    # phrases. Meta tag names or values must be double URL-encoded
    'requiredfields': None,
    # Restricts the search results to documents that contain the exact meta tag names or name-value pairs.
    # See “Meta Tags” on page 32 for more information.
    'pws': '0',  # personalization turned off
    'proxycustom': None,
    # Specifies custom XML tags to be included in the XML results. The default XSLT stylesheet uses these
    # values for this parameter: <HOME/>, <ADVANCED/>. The proxycustom parameter can be used in custom
    # XSLT applications. See “Custom HTML” on page 44 for more information.
    # This parameter is disabled if the search request does not contain the proxystylesheet tag. If custom
    # XML is specified, search results are not returned with the search request.
    'proxyreload': None,
    # Instructs the Google Search Appliance when to refresh the XSL stylesheet cache. A value of 1 indicates
    # that the Google Search Appliance should update the XSL stylesheet cache to refresh the stylesheet
    # currently being requested. This parameter is optional. By default, the XSL stylesheet cache is updated
    # approximately every 15 minutes.
    'proxystylesheet': None,
    # If the value of the output parameter is xml_no_dtd, the output format is modified by the
    # proxystylesheet value as follows:
    # 'Omitted': Results are in XML format.
    # 'Front End Name': Results are in Custom HTML format. The XSL stylesheet associated
    # with the specified Front End is used to transform the output.

    'cd': None,  # Passes down the keyword rank clicked.
    'filter': 0,  # Include omitted results if set to 0
    'complete': None,  # Turn auto-suggest and Google Instant on (=1) or off (=0)
    'nfpr': None,  # Turn off auto-correction of spelling on=1, off=0
    'ncr': None,
    # No country redirect: Allows you to set the Google country engine you would like to use despite your
    # current geographic location.
    'safe': 'off',  # Turns the adult content filter on or off
    'rls': None,
    #Source of query with version of the client and language set. With firefox set to 'org.mozilla:en-US:official'
    'sa': None,
    # User search behavior parameter sa=N: User searched, sa=X: User clicked on related searches in the SERP
    'source': None,  # Google navigational parameter specifying where you came from, univ: universal search
    'sourceid': None,  # When searching with chrome, is set to 'chrome'
    'tlen': None,
    # Specifies the number of bytes that would be used to return the search results title. If titles contain
    # characters that need more bytes per character, for example in utf-8, this parameter can be used to
    # specify a higher number of bytes to get more characters for titles in the search results.
    'ud': None,
    # Specifies whether results include ud tags. A ud tag contains internationalized domain name (IDN)
    # encoding for a result URL. IDN encoding is a mechanism for including non-ASCII characters. When a ud
    # tag is present, the search appliance uses its value to display the result URL, including non-ASCII
    # characters.The value of the ud parameter can be zero (0) or one (1):
    # • A value of 0 excludes ud tags from the results.
    # • A value of 1 includes ud tags in the results.
    # As an example, if the result URLs contain files whose names are in Chinese characters and the ud
    # parameter is set to 1, the Chinese characters appear. If the ud parameter is set to 0, the Chinese
    # characters are escaped.
    'tbm': None,  # Used when you select any of the “special” searches, like image search or video search
    'tbs': None,
    # Also undocumented as `tbm`, allows you to specialize the time frame of the results you want to obtain.
    # Examples: Any time: tbs=qdr:a, Last second: tbs=qdr:s, Last minute: tbs=qdr:n, Last day: tbs=qdr:d,
    # Time range: tbs=cdr:1,cd_min:3/2/1984,cd_max:6/5/1987
    # But the tbs parameter is also used to specify content:
    # Examples: Sites with images: tbs=img:1, Results by reading level, Basic level: tbs=rl:1,rls:0,
    # Results that are translated from another language: tbs=clir:1,
    # For full documentation, see http://stenevang.wordpress.com/2013/02/22/google-search-url-request-parameters/
    'lr': None,
    # Restricts searches to pages in the specified language. If there are no results in the specified language, the
    # search appliance displays results in all languages .
    # lang_xx where xx is the country code such as en, de, fr, ca, ...
    'hl': None,  # Language settings passed down by your browser
    'cr': None,  # The region the results should come from
    'gr': None,
    # Just as gl shows you how results look in a specified country, gr limits the results to a certain region
    'gcs': None,  # Limits results to a certain city, you can also use latitude and longitude
    'gpc': None,  # Limits results to a certain zip code
    'gm': None,  # Limits results to a certain metropolitan region
    'gl': None,  # as if the search was conducted in a specified location. Can be unreliable. for example: gl=countryUS
    'ie': 'UTF-8',  # Sets the character encoding that is used to interpret the query string.
    'oe': 'UTF-8',  # Sets the character encoding that is used to encode the results.
    'ip': None,
    # When queries are made using the HTTP protocol, the ip parameter contains the IP address of the user
    #who submitted the search query. You do not supply this parameter with the search request. The ip
    #parameter is returned in the XML search results. For example:
    'sitesearch': None,
    # Limits search results to documents in the specified domain, host, or web directory. Has no effect if the q
    # parameter is empty. This parameter has the same effect as the site special query term.
    # Unlike the as_sitesearch parameter, the sitesearch parameter is not affected by the as_dt
    # parameter. The sitesearch and as_sitesearch parameters are handled differently in the XML results.
    # The sitesearch parameter’s value is not appended to the search query in the results. The original
    # query term is not modified when you use the sitesearch parameter. The specified value for this
    # parameter must contain fewer than 125 characters.

    'access': 'a',  # Specifies whether to search public content (p), secure content (s), or both (a).
    'biw': None,  # Browser inner width in pixel
    'bih': None,  # Browser inner height in pixel

    'as_dt': None,  # If 'i' is supplied: Include only results in the web directory specified by as_sitesearch
    # if 'e' is given: Exclude all results in the web directory specified by as_sitesearch
    'as_epq': None,
    # Adds the specified phrase to the search query in parameter q. This parameter has the same effect as
    # using the phrase special query term (see “Phrase Search” on page 24).
    'as_eq': None,
    # Excludes the specified terms from the search results. This parameter has the same effect as using the
    # exclusion (-) special query term (see “Exclusion” on page 22).
    'as_filetype': None,
    # Specifies a file format to include or exclude in the search results. Modified by the as_ft parameter.
    'as_ft': None,
    # Modifies the as_filetype parameter to specify filetype inclusion and exclusion options. The values for as
    # ft are: 'i': filetype and 'e': -filetype
    'as_lq': None,
    # Specifies a URL, and causes search results to show pages that link to the that URL. This parameter has
    #the same effect as the link special query term (see “Back Links” on page 20). No other query terms can
    #be used when using this parameter.
    'as_occt': None,
    # Specifies where the search engine is to look for the query terms on the page: anywhere on the page, in
    #the title, or in the URL.
    'as_oq': None,
    # Combines the specified terms to the search query in parameter q, with an OR operation. This parameter
    # has the same effect as the OR special query term (see “Boolean OR Search” on page 20).
    'as_q': None,  # Adds the specified query terms to the query terms in parameter q.
    'as_sitesearch': None,
    # Limits search results to documents in the specified domain, host or web directory, or excludes results
    #from the specified location, depending on the value of as_dt. This parameter has the same effect as the
    #site or -site special query terms. It has no effect if the q parameter is empty.
    'entqr': None,  # This parameter sets the query expansion policy according to the following valid values:
    # 0: None
    # 1: Standard Uses only the search appliance’s synonym file.
    # 2: Local Uses all displayed and activated synonym files.
    # 3: Full Uses both standard and local synonym files.
}

"""
Yandex search params.


"""
yandex_search_params = {

}

"""
Bing search params.


"""
bing_search_params = {

}

"""
Yahoo search params.


"""
yahoo_search_params = {

}

"""
Baidu search params.


"""
baidu_search_params = {

}

"""Duckduckgo search params.


"""
duckduckgo_search_params = {

}

# ;The search params that control the Google search engine
# [GOOGLE_SEARCH_PARAMS]
#
# ; Shows the original query.
# oq: None
#
# ; the number of results per page
# num: 10
#
# ; Number of KeyMatch results to return with the results. A value between 0 to 50 can be specified for this option.
# numgm: None
#
# ; Specifies the index number of the first entry in the result set that is to be returned.
# page number = (start / num) + 1
# ; The maximum number of results available for a query is 1000 i.e. the value of the start parameter
# added to the value of the num parameter cannot exceed 1000.
# start: 0
#
# ; Request an accurate result count for up to 1M documents.
# rc: None
#
# ; Limits search results to the contents of the specified collection. If a user submits a search query without
# the site parameter the entire search index is queried.
# site: None
#
# ; Specifies a sorting method. Results can be sorted by date.
# sort: None
#
# ; Required parameter. If this parameter does not have a valid value other parameters in the query string
# ; do not work as expected. Set to firefox-a in mozilla firefox
# client: firefox-a
#
# output: None
# # required parameter. Selects the format of the search results. xml_no_dtd XML : XML results or custom HTML
# xml: XML results with Google DTD reference. When you use this value omit proxystylesheet.
# partialfields: None
# # Restricts the search results to documents with meta tags whose values contain the specified words or phrases.
# Meta tag names or values must be double URL-encoded
# requiredfields: None
# #Restricts the search results to documents that contain the exact meta tag names or name-value pairs.
# #See “Meta Tags” on page 32 for more information.
#
# ; personalization turned off
# pws: 0
#
# ; Specifies custom XML tags to be included in the XML results. The default XSLT stylesheet uses these
# ; values for this parameter: <HOME/> <ADVANCED/>. The proxycustom parameter can be used in custom
# ; XSLT applications. See “Custom HTML” on page 44 for more information.
# ; This parameter is disabled if the search request does not contain the proxystylesheet tag. If custom
# ; XML is specified search results are not returned with the search request.
# proxycustom: None
#
# ; Instructs the Google Search Appliance when to refresh the XSL stylesheet cache. A value of 1 indicates
# ; that the Google Search Appliance should update the XSL stylesheet cache to refresh the stylesheet
# ; currently being requested. This parameter is optional. By default the XSL stylesheet cache is updated
# ; approximately every 15 minutes.
# proxyreload: None
#
#
# ;If the value of the output parameter is xml_no_dtd the output format is modified by the
# ; proxystylesheet value as follows:
# ; Omitted: Results are in XML format.
# ; Front End Name: Results are in Custom HTML format. The XSL stylesheet associated
# ; with the specified Front End is used to transform the output.
# proxystylesheet: None
#
# ; Passes down the keyword rank clicked.
# cd: None
#
# ; Include omitted results if set to 0
# filter: 0
#
# ; Turn auto-suggest and Google Instant on (=1) or off (=0)
# complete: None
#
# ;Turn off auto-correction of spelling on=1 off=0
# nfpr: None
#
# ; No country redirect: Allows you to set the Google country engine you would like to use despite your
# current geographic location.
# ncr: None
#
# ; Turns the adult content filter on or off
# safe: off
#
# ; Source of query with version of the client and language set. With firefox set to org.mozilla:en-US:official
# rls: None
#
# ; User search behavior parameter sa=N: User searched sa=X: User clicked on related searches in the SERP
# sa: None
#
# ;Google navigational parameter specifying where you came from univ: universal search
# source: None
#
# ; When searching with chrome is set to chrome
# sourceid: None
#
# ;Specifies the number of bytes that would be used to return the search results title. If titles contain
# ; characters that need more bytes per character for example in utf-8 this parameter can be used to
# ; specify a higher number of bytes to get more characters for titles in the search results.
# tlen: None
#
# ;Specifies whether results include ud tags. A ud tag contains internationalized domain name (IDN)
# ; encoding for a result URL. IDN encoding is a mechanism for including non-ASCII characters. When a ud
# ; tag is present the search appliance uses its value to display the result URL including non-ASCII
# ; characters.The value of the ud parameter can be zero (0) or one (1):
# ; • A value of 0 excludes ud tags from the results.
# ; • A value of 1 includes ud tags in the results.
# ; As an example if the result URLs contain files whose names are in Chinese characters and the ud
# ; parameter is set to 1 the Chinese characters appear. If the ud parameter is set to 0 the Chinese
# ; characters are escaped.
# ud: None
#
# ; Used when you select any of the “special” searches like image search or video search
# tbm: None
#
# ; Also undocumented as `tbm` allows you to specialize the time frame of the results you want to obtain.
# ; Examples: Any time: tbs=qdr:a Last second: tbs=qdr:s Last minute: tbs=qdr:n Last day: tbs=qdr:d
# Time range: tbs=cdr:1cd_min:3/2/1984cd_max:6/5/1987
# ; But the tbs parameter is also used to specify content:
# ; Examples: Sites with images: tbs=img:1 Results by reading level Basic level: tbs=rl:1rls:0 Results that are
# translated from another language: tbs=clir:1
# ; For full documentation see http://stenevang.wordpress.com/2013/02/22/google-search-url-request-parameters/
# tbs: None
#
# ; Restricts searches to pages in the specified language. If there are no results in the specified language the
# search appliance displays results in all languages .
# ; lang_xx where xx is the country code such as en de fr ca ...
# lr: None
#
# ; Language settings passed down by your browser
# hl: None
#
# ; The region the results should come from
# cr: None
#
# ; Just as gl shows you how results look in a specified country gr limits the results to a certain region
# gr: None
#
# ; Limits results to a certain city you can also use latitude and longitude
# gcs: None
#
# ; Limits results to a certain zip code
# gpc: None
#
# ; Limits results to a certain metropolitan region
# gm: None
#
# ; as if the search was conducted in a specified location. Can be unreliable. for example: gl=countryUS
# gl: None
#
# ; Sets the character encoding that is used to interpret the query string.
# ie: UTF-8
#
# ; Sets the character encoding that is used to encode the results.
# oe: UTF-8
#
# ; When queries are made using the HTTP protocol the ip parameter contains the IP address of the user
# ; who submitted the search query. You do not supply this parameter with the search request. The ip
# ; parameter is returned in the XML search results. For example:
# ip: None
#
# ; Limits search results to documents in the specified domain host or web directory. Has no effect if the q
# ; parameter is empty. This parameter has the same effect as the site special query term.
# ; Unlike the as_sitesearch parameter the sitesearch parameter is not affected by the as_dt
# ; parameter. The sitesearch and as_sitesearch parameters are handled differently in the XML results.
# ; The sitesearch parameter’s value is not appended to the search query in the results. The original
# ; query term is not modified when you use the sitesearch parameter. The specified value for this
# ; parameter must contain fewer than 125 characters.
# sitesearch: None
#
# ; Specifies whether to search public content (p) secure content (s) or both (a).
# access: a
#
# ; Browser inner width in pixel
# biw: None
#
# ; Browser inner height in pixel
# bih: None
#
# ; If i is supplied: Include only results in the web directory specified by as_sitesearch
# as_dt: None
#
# ; if e is given: Exclude all results in the web directory specified by as_sitesearch
# as_epq: None
