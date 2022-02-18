import re
from urllib.parse import urlparse, parse_qs, urlsplit
from pprint import pprint

import scrapy
from lxml import etree
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from gen_book_rule import constant
from gen_book_rule.spiders.page_operate import WebPage
from gen_book_rule.utils import get_prefix_url, url_join, get_html_element_info
from gen_book_rule.website_parse import WebsiteParse


class WebsiteSpiderSpider(scrapy.Spider):
    name = 'website_spider'
    allowed_domains = []

    def __init__(self, *args, **kwargs):
        self.novel_website_list_xpath = "///div/div/h3/a"
        self.novel_website_next_page_xpath = "//div[@id='wrapper_wrapper']/div[2]/div/div/a[last()]/@href"
        self.novel_website_exclude_keywords = constant.novel_website_exclude_keywords
        self.novel_website_max_page = 200
        self.novel_website_url_dict = dict()
        self.success_url_list = list()
        self.search_info_list = list()
        self.fail_url_list = list()
        self.website_list = False
        # self.start_urls = ['https://www.baidu.com/s?ie=UTF-8&wd=小说网站']
        self.start_urls = ['http://www.ibiqu.net/']
        self.search_keywords = constant.search_keywords
        super().__init__(*args, **kwargs)
        self.rule_template = {
            "bookSourceGroup": "书源分组",
            "bookSourceName": "书源名称",
            "bookSourceUrl": "书源URL",
            "enable": True,
            "httpUserAgent": "httpuseragent",
            "loginUrl": "登陆URL",
            "ruleBookAuthor": "作者规则",
            "ruleBookContent": "正文规则",
            "ruleBookKind": "分类规则",
            "ruleBookLastChapter": "最新章节规则",
            "ruleBookName": "书名规则",
            "ruleBookUrlPattern": "书籍详情URL正则",
            "ruleChapterList": "目录列表规则",
            "ruleChapterName": "章节名称规则",
            "ruleChapterUrl": "目录URL规则",
            "ruleChapterUrlNext": "目录下一页规则",
            "ruleContentUrl": "章节URL规则",
            "ruleContentUrlNext": "正文下一页URL规则",
            "ruleCoverUrl": "封面规则",
            "ruleFindUrl": "发现规则",
            "ruleIntroduce": "简介规则",
            "ruleSearchAuthor": "搜索结果作者规则",
            "ruleSearchCoverUrl": "搜索结果封面规则",
            "ruleSearchKind": "搜索结果分类规则",
            "ruleSearchLastChapter": "搜索结果最新章节规则",
            "ruleSearchList": "搜索结果列表规则",
            "ruleSearchName": "搜索结果书名规则",
            "ruleSearchNoteUrl": "搜索结果书籍URL规则",
            "ruleSearchUrl": "搜索地址",
            "serialNumber": 0,
            "weight": 0
        }
        self.new_template = {
            "bookSourceUrl": "http://quanben-xiaoshuo.com/",
            "bookSourceType": "0",
            "bookSourceName": "全本小说网quanben-xiaoshuo",
            "bookSourceGroup": "",
            "bookSourceComment": "",
            "loginUrl": "",
            "loginUi": "",
            "loginCheckJs": "",
            "concurrentRate": "",
            "header": "",
            "bookUrlPattern": "",
            "searchUrl": "http://quanben-xiaoshuo.com/?c=book&a=search&keyword={{key}}",
            "searchUrl1": "/search.html,{\n  \"method\": \"POST\",\n  \"body\": \"searchkey={{key}}\"\n}",
            "exploreUrl": "",
            "enabled": True,
            "enabledExplore": True,
            "weight": 0,
            "customOrder": 0,
            "lastUpdateTime": 1639806184341,
            "ruleSearch": {  # 搜索页
                "checkKeyWord": "三国",
                "bookList": "//div[@class='book']",
                "name": "//h1/a//text()##\\s*",
                "author": "//span[@itemprop='author']/text()",
                "kind": "//p/a/text()",
                "intro": "//div[@class='description']//text()",
                "bookUrl": "//h1/a/@href"
            },
            "ruleExplore": {},
            "ruleBookInfo": {  # 详情页
                "name": "//h1[@itemprop='name']//text()",
                "author": "//*[@itemprop='author']//text()",
                "kind": "//*[@itemprop='category']//text()",
                "intro": "//*[@class='articlebody']//p//text()",
                "coverUrl": "//*[@itemprop='image']/href",
                "tocUrl": "//a[text()='开始阅读']/@href",
                "lastChapter": "最新章节",
            },
            "ruleToc": {  # 目录页
                "chapterList": "//*[@class='content']//li",
                "chapterName": "//text()",
                "chapterUrl": "//a[@itemprop='url']/@href"
            },
            "ruleContent": {  # 正文页
                "content": "//div[@itemprop='articleBody']//text()",
                "nextContentUrl": "//a[@rel='next']/@href"
            }
        }

    def start_requests(self):
        if self.website_list:
            for url in self.start_urls:
                yield scrapy.Request(url=url, headers=constant.baidud_headers, callback=self.parse_novel_website_list,
                                     meta={"page": 1})
        else:
            for url in self.start_urls:
                yield scrapy.Request(url=url, headers=constant.headers, callback=self.parse_novel_home_page)

    def parse_novel_website_list(self, response):
        """通过百度搜索小说网站，返回网站列表"""
        with open("temp.html", "wb") as f:
            f.write(response.body)
        # 解析搜索结果的网站url列表
        self.__parse_novel_website_url_list(response.text)
        page_num = response.meta.get("page")
        if page_num < self.novel_website_max_page:
            # 爬取未完成，爬取下一页
            result_list = self.get_html_element_info(response.text, self.novel_website_next_page_xpath)
            if len(result_list) == 0:
                print("invalid next_page_url xpath")
                return
            next_page_url = result_list[0]
            next_page_url = self.get_full_url(response.request.url, next_page_url)
            yield scrapy.Request(url=next_page_url, headers=constant.baidud_headers,
                                 callback=self.parse_novel_website_list,
                                 meta={"page": page_num + 1}, )
        # 网站过滤
        self.__novel_website_filter()
        # 请求每一个小说网站
        for novel_website_url in list(self.novel_website_url_dict.keys())[:]:
            yield scrapy.Request(url=novel_website_url, meta={"title": self.novel_website_url_dict[novel_website_url]},
                                 headers=constant.headers, callback=self.parse_novel_home_page)

    def parse_novel_home_page(self, response):
        website = WebsiteParse(response.request.url)
        website.parse_basic(response.text)
        search_url = website.rule_dict.get("searchUrl")
        search_url = search_url.replace("{{key}}", self.search_keywords[0].get("book_name"))
        yield scrapy.Request(url=search_url,
                             meta={"website": website,
                                   "search_info": self.search_keywords[0],
                                   "search_index": 0,
                                   },
                             headers=constant.headers,
                             callback=self.parse_novel_search_page)

    def parse_novel_search_page(self, response):
        with open("gen_book_rule/pages/search_page.html", "wb") as f:
            f.write(response.body)
        website: WebsiteParse = response.meta.get("website")
        search_info = response.meta.get("search_info")
        search_index = response.meta.get("search_index")
        result = website.parse_search(response.text, search_info)
        if result is False and search_index < len(self.search_keywords) - 1:
            search_url = website.rule_dict.get("searchUrl")
            search_url = search_url.replace("{{key}}", self.search_keywords[search_index + 1].get("book_name"))
            yield scrapy.Request(url=search_url,
                                 meta={"website": website,
                                       "search_info": self.search_keywords[search_index + 1],
                                       "search_index": search_index + 1,
                                       },
                                 headers=constant.headers,
                                 callback=self.parse_novel_search_page)
        elif result is True:
            yield scrapy.Request(url=website.book_info_page_url,
                                 meta={"website": website,
                                       "search_info": self.search_keywords[search_index + 1],
                                       "search_index": search_index + 1,
                                       },
                                 headers=constant.headers,
                                 callback=self.parse_book_info_page)
        print(website.rule_dict)
        return

    def parse_book_info_page(self, response):
        with open("gen_book_rule/pages/book_info_page.html", "wb") as f:
            f.write(response.body)
        website: WebsiteParse = response.meta.get("website")
        website.parse_book_info(response.text)
        website.parse_toc(response.text)
        print(website.rule_dict)

    def parse_content_page(self):

        pass

    def find_search_site(self, response):
        # search_info = dict()
        # search_keyword = "完美世界"
        # # 获取输入框xpath
        # search_xpath = self.__get_search_input_box_path(response.text)
        # if search_xpath == "":
        #     print(f"获取search_xpath失败，url = {response.request.url}")
        #     # 获取输入框xpath失败处理 TODO 可以使用selenium打开页面后重新获取完整页面进行解析
        #     file_name = re.sub(u"([^\u4e00-\u9fa5\u0030-\u0039\u0041-\u005a\u0061-\u007a])", "",
        #                        response.meta.get('title'))
        #     with open(f"gen_book_rule/pages/{file_name}.html", "wb") as f:
        #         f.write(response.body)
        #     return search_info
        # # print(search_xpath)
        # request_method = "get"
        # search_url = ""
        # field_name = ""
        # # 检测是否为表单提交，是表单提交则获取表单信息
        # if "/form" in search_xpath:
        #     form_xpath = f"{search_xpath.split('/form')[0]}/form"
        #     # print(f"form_xpath = {form_xpath}")
        #     result = self.get_html_element_info(response.text, f"{form_xpath}/@method")
        #     if len(result) == 0:
        #         request_method = "post"
        #     else:
        #         request_method = result[0]
        #     result = self.get_html_element_info(response.text, f"{form_xpath}/@action")
        #     if len(result) <= 0:
        #         print("获取action url失败")
        #         return search_info
        #     search_url = self.get_full_url(response.request.url, result[0])
        #     field_name = self.get_html_element_info(response.text, f"{search_xpath}/@name")
        # else:
        #     # 非表单提交处理
        #     page = WebPage(url=response.request.url)
        #     # 完整页面和原始页面有差别，进行定位需要使用各种属性完整定位或直接使用哦个完整页面进行解析
        #     # 拼接出相对xpath定位元素
        #     filter_list = list()
        #     attr_list = ["type", "id", "value", "placeholder", "class", "name", "autocomplete"]
        #     for attr in attr_list:
        #         result = self.get_html_element_info(response.text, f"{search_xpath}/@{attr}")
        #         if result:
        #             filter_list.append(f"@{attr}='{result[0]}'")
        #     result = self.get_html_element_info(response.text, f"{search_xpath}/@placeholder")
        #     if result:
        #         filter_list.append(f"@value='{result[0]}'")
        #     full_xpath = f"//input[{' and '.join(filter_list)}]"
        #     search_input_box = page.find_element(by=By.XPATH, value=full_xpath)
        #     search_input_box.send_keys(search_keyword)
        #     search_input_box.send_keys(Keys.ENTER)
        #     new_url = page.current_url
        #     # 查询参数判断
        #     # print(parse_qs(urlsplit(new_url).query))
        #     for key, value in parse_qs(urlsplit(new_url).query).items():
        #         if value and value[0] == search_keyword:
        #             field_name = key
        #             break
        #     # 路径参数判断
        #     if field_name == "":
        #         print(f"路径参数： url = {new_url}")
        #         return search_info
        #     # print(f"new_url = {new_url}")
        # print(f"field_name = {field_name}, request_method = {request_method}, url = {search_url}")
        # search_info = {"field_name": field_name, "method": request_method, "url": search_url}
        # return search_info
        pass

    @staticmethod
    def __get_search_input_box_path(html_text):
        # type_list = ["text", "search"]
        # for tag_type in type_list:
        #     # 直接查找input标签
        #     html = etree.HTML(html_text)
        #     element_list = html.xpath(f"//input[@type='{tag_type}']")
        #     if len(element_list) == 1:
        #         tree = etree.ElementTree(element_list[0])
        #         xpath_str = tree.getpath(element_list[0])
        #         return xpath_str
        #     # 标签数量不为一，查找form标签下所有的input标签
        #     element_list = html.xpath(f"//form/*/input[@type='{tag_type}']")
        #     if len(element_list) == 1:
        #         tree = etree.ElementTree(element_list[0])
        #         xpath_str = tree.getpath(element_list[0])
        #         return xpath_str
        #     elif len(element_list) > 1:
        #         # input标签不唯一，对标签进行判断是不是是多个相同标签
        #         if len(set(html.xpath(f"//form/*/input[@type='{tag_type}']/@name"))) == 1:
        #             tree = etree.ElementTree(element_list[0])
        #             xpath_str = tree.getpath(element_list[0])
        #             return xpath_str
        #     print(len(element_list))
        return ""

    @staticmethod
    def get_html_element_info(html_text, xpath_str):
        html = etree.HTML(html_text)
        return html.xpath(xpath_str)

    @staticmethod
    def get_full_url(request_url, url):
        if not url.startswith('http'):
            if url.startswith('/'):
                base_url = get_prefix_url(request_url)
            else:
                base_url = request_url
            return url_join(base_url, url)
        return url

    def __parse_novel_website_url_list(self, html_content):
        title_list = self.get_html_element_info(html_content, f"{self.novel_website_list_xpath}/@href")
        url_list = [element.xpath('string(.)') for element in self.get_html_element_info(html_content,
                                                                                         self.novel_website_list_xpath)]
        self.novel_website_url_dict.update(dict(zip(title_list, url_list)))

    def __novel_website_filter(self):

        del_key_list = set()
        # 查找
        for key, title in self.novel_website_url_dict.items():
            for keyword in self.novel_website_exclude_keywords:
                if keyword in title:
                    del_key_list.add(key)
                    break
        # 删除
        [self.novel_website_url_dict.pop(key) for key in del_key_list]

    def __get_novel_website_url(self):
        pass

    def __get_novel_website_name(self):
        pass
