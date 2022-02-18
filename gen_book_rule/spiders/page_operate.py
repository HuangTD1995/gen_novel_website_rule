from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement


class WebPage:
    driver_path = "E:\\temp\\chromedriver_win32\\chromedriver.exe"

    def __new__(cls, url, show_browser=False, *args, **kwargs):
        option = webdriver.ChromeOptions()
        if show_browser is False:
            option.add_argument('headless')  # 设置option
            option.add_argument('--disable-gpu')
        prefs = {
            'profile.default_content_setting_values': {
                'images': 2,
            }
        }
        option.add_experimental_option('prefs', prefs)
        driver = webdriver.Chrome(cls.driver_path, chrome_options=option)  # 调用带参数的谷歌浏览器
        driver.get(url)
        return driver

    def get_full_xpath(self, ele: WebElement):
        full_xpath = ""
        tag = ele.tag_name
        while True:
            ele.parent


if __name__ == '__main__':
    page = WebPage("https://www.pan5.net", show_browser=False)
    input_box = page.find_element(value="key")
    print(input_box.get_attribute("name"))
    print(input_box.get_property("name"))
    input_box.send_keys("完美世界")
    # page.find_element(by=By.CLASS_NAME, value="searchbtn").click()
