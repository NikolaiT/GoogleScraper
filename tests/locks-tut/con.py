__author__ = 'nikolai'

import threading
import random
import time

class Producer(threading.Thread):
    """
    Produces random integers to a list
    """

    def __init__(self, integers, condition):
        """
        Constructor.

        @param integers list of integers
        @param condition condition synchronization object
        """
        threading.Thread.__init__(self)
        self.integers = integers
        self.condition = condition

    def run(self):
        """
        Thread run method. Append random integers to the integers list
        at random time.
        """
        while True:
            integer = random.randint(0, 256)
            self.condition.acquire()
            print 'condition acquired by %s' % self.name
            self.integers.append(integer)
            print '%d appended to list by %s' % (integer, self.name)
            print 'condition notified by %s' % self.name
            self.condition.notify()
            print 'condition released by %s' % self.name
            self.condition.release()
            time.sleep(1)

class Consumer(threading.Thread):
    """
    Consumes random integers from a list
    """

    def __init__(self, integers, condition):
        """
        Constructor.

        @param integers list of integers
        @param condition condition synchronization object
        """
        threading.Thread.__init__(self)
        self.integers = integers
        self.condition = condition

    def run(self):
        """
        Thread run method. Consumes integers from list
        """
        while True:
            self.condition.acquire()
            print 'condition acquired by %s' % self.name
            while True:
                if self.integers:
                    integer = self.integers.pop()
                    print '%d popped from list by %s' % (integer, self.name)
                    break
                print 'condition wait by %s' % self.name
                self.condition.wait()
            print 'condition released by %s' % self.name
            self.condition.release()

def main():
    integers = []
    condition = threading.Condition()
    t1 = Producer(integers, condition)
    t2 = Consumer(integers, condition)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

if __name__ == '__main__':
    main()

