from selenium import webdriver
import time

height = 800

webdriver = webdriver.Chrome()
webdriver.set_window_size(800, height)
webdriver.set_window_position(600, 200)

js = '''
var w = window,
    d = document,
    e = d.documentElement,
    g = d.getElementsByTagName('body')[0],
    y = w.innerHeight|| e.clientHeight|| g.clientHeight;

window.scrollBy(0,y);
return y;
'''

webdriver.get('https://www.google.ch/search?q=what+how&num=50')
time.sleep(2)
sheight = webdriver.execute_script(js)

print('Scrolled by {}, window size = {}'.format(sheight, height))
