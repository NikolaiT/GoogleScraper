from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary

binary = FirefoxBinary('/home/nikolai/ff/firefox/firefox')

options = Options()
options.set_headless(headless=True)
driver = webdriver.Firefox(firefox_binary=binary,
    firefox_options=options, executable_path='../Drivers/geckodriver')
driver.get("http://google.com/")
print ("Headless Firefox Initialized")
driver.quit()
