import time
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException, ElementNotVisibleException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

chromedriver = '/home/nikolai/projects/work/aws-lambda-scraping/bin/chromedriver'
binary = '/home/nikolai/projects/work/aws-lambda-scraping/bin/headless-chromium'

options = webdriver.ChromeOptions()
options.add_argument('headless')
options.add_argument('window-size=1200x600') # optional
options.add_argument('--no-sandbox')
options.add_argument('--disable-gpu')
options.add_argument('--user-data-dir=/tmp')
options.add_argument('--hide-scrollbars')
options.add_argument('--enable-logging')
options.add_argument('--log-level=0')
options.add_argument('--v=99')
options.add_argument('--single-process')
options.add_argument('--data-path=/tmp')
options.add_argument('--ignore-certificate-errors')
options.add_argument('--homedir=/tmp')
options.add_argument('--disk-cache-dir=/tmp')
#options.add_argument('user-agent=bot')

options.binary_location = binary

browser = webdriver.Chrome(executable_path=chromedriver, options=options)

browser.get('https://www.google.com/search?num=100')

search_input = None
try:
    search_input = WebDriverWait(browser, 5).until(
        EC.visibility_of_element_located((By.NAME, 'q')))
    print('Got a search input field.')
except TimeoutException:
    print('No search input field located after 5 seconds.')

keyword = 'startup berlin'

search_input = browser.find_element_by_xpath('//*[@name="q"]')

try:
    search_input.send_keys(keyword + Keys.ENTER)
    print('Google search for "{}" successful! '.format(keyword))
except WebDriverException as e:
    print('Cannot make a google search: {}'.format(e))

time.sleep(1)

try:
    all_links = browser.find_elements_by_css_selector('#center_col .g')
except NoSuchElementException as e:
    print('Cannot find serp page: {}'.format(e))

print('Found {} results'.format(len(all_links)))

# browser.save_screenshot('headless_chrome_test.png')
# browser.quit()
