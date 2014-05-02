# This script implements a little test that attempts to make socksipy working
# with the popular requests module.

# Apparently there were attempts before to incorporate socksipy into requests module.
# See: https://github.com/kennethreitz/requests/pull/478

# Recommendation: Use this version of socksipy: https://github.com/Anorov/PySocks/blob/master/socks.py
# You need to download it in order to execute this script.

# Also:
# You need the tor server running. That means you have to download and install TOR.
# http://www.blackhatworld.com/blackhat-seo/proxy-lists/453375-daily-proxies-all-proxy-protocols-18.html
import sys
# patch the path (bad ugly ugly hack)
sys.path.append('..')
# now we can import the socksipy module
import socks
import socket
import threading
# Monkey patch the socket.create_connection() method, because it uses
# getaddrinfo() C API call which doesn't use the socket.socket socket, so
# the wrap_module() call doesn't prevent DNS leakage.
# See here for the implementation of create_connection():
# https://github.com/python/cpython/blob/master/Lib/socket.py
# Implications: We MUST provide an IP address of the proxy to socks.setdefaultproxy(), otherwise
# we end up failing
def create_connection(address, timeout=None, source_address=None):
    sock = socks.socksocket()
    sock.connect(address)
    return sock

def test(host, port, username=None, password=None):
    """Tests whether the proxy is working"""
    for name, protocol in {'socks5': socks.PROXY_TYPE_SOCKS5, }.items():#'http_proxy': socks.PROXY_TYPE_HTTP, 'socks4': socks.PROXY_TYPE_SOCKS4}.items():
        # rdns is by default on true. Never use rnds=False with TOR, otherwise you are screwed!
        socks.setdefaultproxy(protocol, addr=host, port=port, username=username, password=password, rdns=True)
        socks.wrap_module(socket)
        socket.create_connection = create_connection
        import requests
        try:
            r = requests.get('http://icanhazip.com/')
            print(r.text)
        except requests.exceptions.ConnectionError as e:
            print("{} => {}:{} says: {} ".format(name, host, port, e))

if __name__ == '__main__':
    # for line in open('/home/nikolai/projects/workspace/GoogleScraper/kwfiles/proxies', 'r').read().split('\n'):
    #     if line.count(':') == 1:
    #         host, port = line.split(':')
    #         test(host, int(port))
    #test('212.224.92.182', 7777, username='nikolai', password='AiCa"f;ai3Quie0Thuaj')
    test('212.224.92.182', 7777)

class ProxyTester(threading.Thread):
    def __init__(self):
        super().__init__()
    def run(self):
        pass
