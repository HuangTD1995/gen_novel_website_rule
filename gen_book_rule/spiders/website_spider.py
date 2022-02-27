import re

import scrapy
from lxml import etree

from gen_book_rule import constant
from gen_book_rule.utils import get_prefix_url, url_join
from gen_book_rule.spiders.website_parse import WebsiteParse


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
        self.start_urls = ['https://www.wangshuge.com/']
        # self.start_urls = ['https://www.23us.cc/']
        self.search_keywords = constant.search_keywords
        self.website = None
        self.content_pages = [""] * 5
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
                "chapterUrl": "//a[@itemprop='url']/@href",
                "nextTocUrl": ""  # 目录下一页，没有下一页则不用填
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
        with open("gen_book_rule/pages/home_page.html", "wb") as f:
            f.write(response.body)
        self.website = WebsiteParse(response.request.url)
        self.website.parse_basic(response.text)
        print(self.website.rule_dict)
        yield self.get_search_request_obj(self.search_keywords[0].get("book_name"),
                                          meta={"search_info": self.search_keywords[0],
                                                "search_index": 0},
                                          # encoding=response.encoding
                                          )

    def get_search_request_obj(self, keyword, **kwargs):
        search_url = self.website.rule_dict.get("searchUrl")
        if '"method": "' in search_url:
            request_url = search_url.split(",", maxsplit=1)[0]
            result = re.search(r'"body": "(?P<field_name>.*?)=', search_url)
            field_name = result.group("field_name")
            return scrapy.FormRequest(url=request_url,
                                      formdata={field_name: keyword},
                                      headers=constant.headers,
                                      callback=self.parse_novel_search_page,
                                      **kwargs)
        else:
            request_url = search_url.replace("{{key}}", keyword)
            return scrapy.Request(url=request_url,
                                  headers=constant.headers,
                                  callback=self.parse_novel_search_page,
                                  **kwargs)

    def parse_novel_search_page(self, response):
        with open("gen_book_rule/pages/search_page.html", "wb") as f:
            f.write(response.body)
        search_info = response.meta.get("search_info")
        search_index = response.meta.get("search_index")
        result = self.website.parse_search(response.text, search_info)
        if result is False and search_index < len(self.search_keywords) - 1:
            yield self.get_search_request_obj(self.search_keywords[search_index + 1].get("book_name"),
                                              meta={"search_info": self.search_keywords[search_index + 1],
                                                    "search_index": search_index + 1,
                                                    },
                                              # encoding=response.encoding
                                              )
        elif result is True:
            yield scrapy.Request(url=self.website.book_info_page_url,
                                 meta={"search_info": self.search_keywords[search_index + 1],
                                       "search_index": search_index + 1,
                                       },
                                 headers=constant.headers,
                                 callback=self.parse_book_info_page)
        print(self.website.rule_dict)
        return

    def parse_book_info_page(self, response):
        with open("gen_book_rule/pages/book_info_page.html", "wb") as f:
            f.write(response.body)
        self.website.parse_book_info(response.text)
        self.website.chapter_list_page_url = response.request.url
        self.website.parse_toc(response.text)
        print(self.website.rule_dict)
        yield scrapy.Request(url=self.website.content_pages_url[0],
                             meta={"page_index": 0},
                             headers=constant.headers,
                             callback=self.parse_content_page)

    def parse_content_page(self, response):
        page_index = response.meta.get("page_index")
        with open(f"gen_book_rule/pages/content_page_{page_index}.html", "wb") as f:
            f.write(response.body)
        self.content_pages[page_index] = response.text
        if "" not in self.content_pages:
            self.website.parse_content(self.content_pages)
            print(self.website.rule_dict)
        else:
            yield scrapy.Request(url=self.website.content_pages_url[page_index + 1],
                                 meta={"page_index": page_index + 1},
                                 headers=constant.headers,
                                 callback=self.parse_content_page)

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

