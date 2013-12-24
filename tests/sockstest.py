# This script implements a little test that attempts to make socksipy working
# with the popular requests module.

# Apparently there were attempts before to incorporate socksipy into requests module.
# See: https://github.com/kennethreitz/requests/pull/478

# Recommendation: Use this version of socksipy: https://github.com/Anorov/PySocks/blob/master/socks.py
# You need to download it in order to execute this script.

# Also:
# You need the tor server running. That means you have to download and install TOR.

import sys
# patch the path (bad ugly ugly hack)
sys.path.append('..')
# now we can import the socksipy module
import socks
import socket
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

socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, 'localhost', 9050, rdns=True) # rdns is by default on true. Never use rnds=False with TOR, otherwise you are screwed!
socks.wrap_module(socket)
socket.create_connection = create_connection

import requests

r = requests.get('http://icanhazip.com/')
print(r.text)

