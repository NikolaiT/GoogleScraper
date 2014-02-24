import threading
import time

class Test(threading.Timer):
    def __init__(self, interval):
        super().__init__(interval, self.scrape)

    def scrape(self):
        print('{} was executed at {}'.format(self.ident, time.ctime(time.time())))

    def pause(self, n):
        time.sleep(n)

threads = [Test(t**2) for t in range(5)]
print('Created threads at {}'.format(time.ctime(time.time())))

for t in threads:
    t.start()

for t in threads:
    t.join()
