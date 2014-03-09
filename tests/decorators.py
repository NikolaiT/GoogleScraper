import threading
import types

def timer_support(Class):
    """In python versions prior to 3.3, threading.Timer
    seems to be a function that returns an instance
    of _Timer which is the class we want.
    """
    if isinstance(threading.Timer, (types.FunctionType, types.BuiltinFunctionType)) \
            and hasattr(threading, '_Timer'):
        timer_class = threading._Timer
    else:
        timer_class = threading.Timer

    class Test(timer_class):
        def __init__(self):
            super().__init__(2, self.test)
            self._init()
    
    for name, attribute in Class.__dict__.items():
        if name not in ('__dict__'):
            try:
                setattr(Test, name, attribute)
            except AttributeError as ae:
                pass
    return Test

@timer_support
class Test():
    def _init(self):
        self.var = 3453
        self.var2 = '435r3'
    def test(self):
        print('thread {} is running'.format(self.ident))
        print(self.var)
        print(self.var2)

t = Test()
t.start()
