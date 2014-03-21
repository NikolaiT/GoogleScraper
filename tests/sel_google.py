__author__ = 'nikolai'

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait # available since 2.4.0
from selenium.webdriver.support import expected_conditions as EC # available since 2.26.0
from selenium.webdriver.common.by import By
import pprint

def test():
    wd = webdriver.Firefox()
    wd.get('http://google.com')
    try:
        element = WebDriverWait(wd, 10).until(EC.presence_of_element_located((By.NAME, "q")))
    except Exception as e:
        print(e)
    finally:
        element.send_keys('hotel' + Keys.ENTER)

    wd.implicitly_wait(1)

    results = wd.find_elements_by_css_selector('li.g')
    parsed = []
    for result in results:
        link = title = snippet = ''
        try:
            link_element = result.find_element_by_css_selector('h3.r > a:first-child')
            link = link_element.get_attribute('href')
            title = link_element.text
        except Exception as e:
            print('link element couldnt be parsed')
        try:
            snippet = result.find_element_by_css_selector('div.s > span.st').text
        except Exception as e:
            print('snippet element couldnt be parsed')

        parsed.append((link, title, snippet))

    pprint.pprint(parsed)

    wd.close()


if __name__ == '__main__':
    test()