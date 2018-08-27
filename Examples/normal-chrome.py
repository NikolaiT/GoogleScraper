from selenium import webdriver

chromedriver = '/home/nikolai/projects/private/Drivers/chromedriver'

options = webdriver.ChromeOptions()
#options.add_argument('headless')
options.add_argument('window-size=1200x600') # optional

browser = webdriver.Chrome(executable_path=chromedriver, chrome_options=options)

browser.get('https://www.google.com/search?num=100')

# browser.save_screenshot('headless_chrome_test.png')
# browser.quit()
