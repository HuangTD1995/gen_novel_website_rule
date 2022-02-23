import collections
import logging
import re
import urllib.parse

from lxml import etree
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from gen_book_rule.utils import get_html_element_info, get_full_xpath

if __name__ == '__main__':
    process = CrawlerProcess(get_project_settings())
    process.crawl('website_spider')
    process.start()
    # with open("gen_book_rule/pages/content_page_0.html", "r", encoding="utf8") as f:
    #     data = f.read()
    # print("".join(get_html_element_info(data, "/html/body//*[not(name()='script') and not(name()='style')]/text()")))
    # print(len("".join(get_html_element_info(data, "/html/body//*[not(name()='script') and not(name()='style')]/text()"))))
    pass
