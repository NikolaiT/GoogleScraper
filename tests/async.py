import asyncio
import aiohttp

@asyncio.coroutine
def print_page(url):
    response = yield from aiohttp.request('GET', url)
    body = yield from response.read_and_close(decode=False)
    print(len(body))


loop = asyncio.get_event_loop()
loop.run_until_complete(asyncio.wait([print_page('http://incolumitas.com'),
                                      print_page('http://scrapeulous.com')]))
