import sys
# patch the path (bad ugly ugly hack)
sys.path.append('..')
# now we can import the socksipy module
import socks
import socket
import argparse

def test_socks_server():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--proxy', required=True, help='Add a proxy in the format "host:port"')

    args = parser.parse_args()

    if not args.proxy or ':' not in args.proxy or not args.proxy.split(':')[1].isdigit():
        parser.error('Invalid Usage, invoke with --help directive to learn why')

    addr, port = args.proxy.split(':')
    port = int(port)
    # try first SOCKSv5
    if test_proxy(addr, port, socks.PROXY_TYPE_SOCKS5):
        print('SOCKSv5 proxy server {} seems to be open'.format(args.proxy))
        return
    # and if necessary socksv4
    if test_proxy(addr, port, socks.PROXY_TYPE_SOCKS4):
        print('SOCKSv4 proxy server {} seems to be open'.format(args.proxy))

def test_proxy(addr, port, sockstype):
    try:
        s = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
        s.set_proxy(sockstype, addr, port)
        try:
            s.connect(('incolumitas.com', 80))
        except socks.ProxyError as e4:
            print(e4.msg)
            raise

        s.send(b'''
GET http://incolumitas.com/logsocks.php HTTP/1.1
Host: incolumitas.com
User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:26.0) Gecko/20100101 Firefox/26.0
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8
Accept-Language: en-US,en;q=0.5
Accept-Encoding: gzip, deflate
Connection: close

    ''')

        answer = s.recv(4096)
        # the valid HTTP answer HEADER is the part up to the first
        # \r\n\r\n
        answer = answer.split(b'\r\n\r\n')[0]
        return 'HTTP/1.1 200 OK' in answer.decode()

    except socket.error as se:
        print(se.args)


if __name__ == '__main__':
    test_socks_server()
