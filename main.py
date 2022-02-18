import collections
import logging
import re

from lxml import etree
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings


def get_html_element_info(html_text, xpath_str):
    html = etree.HTML(html_text)
    return html.xpath(xpath_str)


if __name__ == '__main__':
    process = CrawlerProcess(get_project_settings())
    process.crawl('website_spider')
    process.start()
    # with open("bqg.html", "r") as f:
    #     data = f.read()
    # ele_list = get_html_element_info(data, "/html/body//*")
    # print(ele_list)
    # results = [str_info.strip().replace("\n", "").replace("\t", "") for str_info in [ele.xpath("string()") for ele in ele_list]]
    # # results = [str_info.strip().replace("\n", "").replace("\t", "") for str_info in ele_list]
    # # print(results)
    # print(len(results))
    # max_length = 0
    # max_item = None
    # for item in results:
    #     if len(item) > max_length:
    #         max_length = len(item)
    #         max_item = item
    # print(max_item)
    # print(max_length)  //*[contains(string(.), '辰东') and string-length(string(.))<10]/text()
    # print(re.sub(r"tr\[[0-9]{1,3}]/.*", "tr[1]/th", "/html/body/div[1]/div[4]/div/table/tbody/tr[1]/td[2]/a"))
    # print(re.search(r"第.{1,8}[章节篇]{1}", "woasjf第五章aljklasjdfiew"))
