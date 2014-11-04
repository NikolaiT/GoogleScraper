import os
path = os.path.abspath('../GoogleScraper')
os.chdir(path)
print(os.popen('ls -lah').read())
from caching import CompressedFile

file = CompressedFile('zlib', '/tmp/test')
file.write('hello world')

print(file.read())