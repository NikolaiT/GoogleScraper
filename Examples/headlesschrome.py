from selenium import webdriver

chromedriver = '/usr/bin/chromedriver'

options = webdriver.ChromeOptions()
options.add_argument('headless')
options.add_argument('window-size=1200x600') # optional

#browser = webdriver.Chrome(executable_path=chromedriver, chrome_options=options)
browser = webdriver.Chrome(chrome_options=options, executable_path=chromedriver)

browser.get('https://www.google.com')

browser.save_screenshot('headless_chrome_test.png')

browser.quit()
