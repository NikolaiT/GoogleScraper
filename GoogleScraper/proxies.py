# -*- coding: utf-8 -*-

from collections import namedtuple
import os

Proxy = namedtuple('Proxy', 'proto, host, port, username, password')

def parse_proxy_file(fname):
    """Parses a proxy file
        The format should be like the following:

        socks5 23.212.45.13:1080 username:password
        socks4 23.212.45.13:80 username:password
        http 23.212.45.13:80

        If username and password aren't provided, GoogleScraper assumes
        that the proxy doesn't need auth credentials.
    """
    proxies = []
    path = os.path.join(os.getcwd(), fname)
    if os.path.exists(path):
        with open(path, 'r') as pf:
            for line in pf.readlines():
                tokens = line.replace('\n', '').split(' ')
                try:
                    proto = tokens[0]
                    host, port = tokens[1].split(':')
                except:
                    raise Exception('Invalid proxy file. Should have the following format: {}'.format(parse_proxy_file.__doc__))
                if len(tokens) == 3:
                    username, password = tokens[2].split(':')
                    proxies.append(Proxy(proto=proto, host=host, port=port, username=username, password=password))
                else:
                    proxies.append(Proxy(proto=proto, host=host, port=port, username='', password=''))
        return proxies
    else:
        raise ValueError('No such file')