import re
from collections import Counter
from typing import List
from urllib.parse import parse_qs, urlsplit, unquote

from lxml import etree
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By

from gen_book_rule import constant
from gen_book_rule.spiders.page_operate import WebPage
from gen_book_rule.utils import get_html_element_info, get_full_xpath, get_prefix_url, url_join


class WebsiteParse:
    def __init__(self, url):
        self.url = url
        self.home_page = None
        self.search_page = None
        self.novel_info_page = None
        self.chapter_list_page = None
        self.detail_page = None
        self.chapter_list_page_url = None
        self.content_pages = list()
        self.content_pages_url = list()

        self.title = None
        self.search_info = None
        self.rule_dict = dict()
        self.book_info_page_url = None

    def parse_basic(self, page: str):
        """基本信息解析"""
        self.home_page = page
        self.__parse_source_url()
        self.__parse_source_name()
        return self.__parse_search_url_rule()

    def parse_search(self, page: str, search_info: dict):
        """搜索页解析"""
        self.search_page = page
        self.search_info = search_info
        self.rule_dict["ruleSearch"] = dict()
        return self.__parse_search_page_rule()

    def parse_book_info(self, page: str):
        """详情页解析"""
        self.detail_page = page
        self.rule_dict["ruleBookInfo"] = dict()
        if self.__parse_book_name_rule() is False:
            return False
        if self.__parse_book_author_rule() is False:
            return False
        if self.__parse_book_kind_rule() is False:
            return False
        if self.__parse_book_introduce_rule() is False:
            return False
        if self.__parse_book_cover_url_rule() is False:
            return False
        if self.__parse_book_last_chapter_rule() is False:
            return False
        return True

    def parse_toc(self, page: str):
        """目录页解析"""
        self.chapter_list_page = page
        self.rule_dict["ruleToc"] = dict()
        if self.__parse_book_chapter_list_rule() is False:
            return False
        return True

    def parse_content(self, pages: List[str]):
        """正文页解析"""
        self.content_pages = pages
        self.rule_dict["ruleContent"] = dict()
        if self.__parse_book_content_rule() is False:
            return False
        if self.__parse_book_next_chapter_rule() is False:
            return False
        return True

    def __parse_source_url(self):
        self.rule_dict["bookSourceUrl"] = self.url

    def __parse_source_name(self):
        """解析书源名称"""
        # 暂时使用title作为书源名称
        self.title = get_html_element_info(self.home_page, "//title/text()")[0]
        self.rule_dict["bookSourceName"] = self.title

    def __parse_book_author_rule(self):
        # 获取包含作者名的标签文本
        author = self.search_info.get("author")
        author_length = len(author)
        author_max_length = author_length + 8
        # normalize-space(//*[contains(text(), '辰东') and string-length(text())<10]/text())
        author_xpath = f"//*[contains(text(), '{author}') and string-length(normalize-space(text()))<{author_max_length}]"
        results = get_html_element_info(self.detail_page, author_xpath)
        if not results:
            print("获取book info 作者名字标签失败")
            return False
        # 通过匹配作者名获取标签，比对标签文本
        for ele in results:
            ele_text = re.sub(u"([^\u4e00-\u9fa5：:])", "", ele.text)
            if ele_text == author or "作者" in ele_text or ("作" in ele_text and "者" in ele_text):
                self.rule_dict["ruleBookInfo"]["author"] = f"{get_full_xpath(ele)}/text()"
                break
        else:
            print("获取book info 合适作者名字失败")
            return False
        return True

    def __parse_book_kind_rule(self):
        self.rule_dict["ruleBookInfo"]["kind"] = ""
        ele_list = get_html_element_info(self.detail_page,
                                         "/html/body//*[starts-with(text(), '分类：') or starts-with(text(), '分 类：')]")
        if len(ele_list) == 1:
            self.rule_dict["ruleBookInfo"]["kind"] = get_full_xpath(ele_list[0])
        else:
            print("获取书籍详情页分类规则失败")

    def __parse_book_content_rule_new(self):
        """获取小说正文"""
        limit_rate = 0.5  # 权重
        content_xpath_list = list()
        for content_page in self.content_pages:
            nodes = get_html_element_info(content_page, '//*')  # 获取所有节点
            nodes = set(nodes)  # 节点去重
            temp_xpath = '.'
            flag = False
            for index in range(4):  # 多次循环
                if flag is True:
                    break
                max_text_length = 0
                max_node = None
                second_text_length = 0
                node_list = list()

                # 遍历所有节点，获取所有节点对应的字符长度，并且通过最长字符长度的标签判断为内容标签
                for node in nodes:
                    if temp_xpath != '.':
                        temp_str = temp_xpath.rstrip('/node()')
                        upper_node = node.xpath(temp_str)
                        if upper_node in node_list:
                            continue
                        else:
                            node_list.append(upper_node)
                    # 获取节点里面所有的文本的长度,并且比较获取长度最长的节点
                    text_length = len(''.join(node.xpath(f'{temp_xpath}/text()')))
                    if max_text_length < text_length:
                        max_text_length = text_length
                        max_node = node
                    elif text_length > second_text_length:
                        second_text_length = text_length
                else:
                    # 判断文本数量最多的节点是否大于对应比例的第二的节点，不大于则向上一级父节点继续新一轮遍历
                    if max_text_length * limit_rate > second_text_length:
                        if index == 0:
                            content_xpath_list.append(get_full_xpath(max_node))
                            flag = True
                            break
                        else:
                            sub_nodes = max_node.xpath(temp_xpath)
                            node_tag_dict = {sub_node.tag: 0 for sub_node in sub_nodes}
                            for sub_node in sub_nodes:
                                node_tag_dict[sub_node.tag] = node_tag_dict[sub_node.tag] + len(
                                    ''.join(sub_node.xpath('./text')))
                            tag_tuple = max(zip(node_tag_dict.values(), node_tag_dict.keys()))
                            node_tag = tag_tuple[1]
                            temp_node = max_node.xpath(temp_xpath.rstrip("/*"))[0]
                            xpath_str = get_full_xpath(temp_node)
                            xpath_str = f'{xpath_str}/{node_tag}'
                            content_xpath_list.append(xpath_str)
                            flag = True
                            break
                    # 继续上一级父节点遍历
                    temp_xpath = '../' * (index + 1)
                    temp_xpath = f'{temp_xpath}*'
        else:
            # 对n篇文章遍历之后获取最多数量的节点的xpath
            content_xpath = Counter(content_xpath_list).most_common()[0][0]
            self.rule_dict["ruleContent"]["content"] = content_xpath

    def __parse_book_content_rule(self):
        limit_rate = 0.3
        limit_max_text_length = 1000
        exclude_tags = ["script", "style", "option", "img", "input"]
        max_node_dict = dict()
        for page in self.content_pages:
            # 获取html所有显示文本
            filter_list = list()
            for tag in exclude_tags:
                filter_list.append(f"not(name()='{tag}')")
            filter_str = " and ".join(filter_list)
            all_text_length = len("".join(get_html_element_info(page, f"/html/body//*[{filter_str}]/text()")))
            # 获取所有节点
            ele_list = get_html_element_info(page, f"/html/body//*[{filter_str}]")
            # 排除节点text为空的标签
            temp_ele_list = list()
            for ele in ele_list:
                if ele.text:
                    temp_ele_list.append(ele)
            ele_list = temp_ele_list
            del temp_ele_list
            # 判断是否有标签的文本超过对应比率，没有则循环遍历其父节点继续判定父节点下所有该类型的标签的文本是否超过对应比率
            for index in range(5):  # 向上回溯几级父节点
                max_text_length = 0
                content_xpath = ""
                for ele in ele_list:
                    if index == 0:
                        ele_text = "".join(ele.xpath("./text()"))
                        ele_xpath = f"{get_full_xpath(ele)}/text()"
                    else:
                        # 获取父节点下对应标签的所有文本
                        full_xpath = get_full_xpath(ele)
                        ele_xpath = f"{full_xpath}/{'../' * index}{'node()/' * (index - 1)}{ele.tag}/text()"
                        ele_text = "".join(get_html_element_info(page, ele_xpath))
                    if len(ele_text) > max_text_length:
                        max_text_length = len(ele_text)
                        content_xpath = ele_xpath
                # 判断最长文本长度是否超过所有文本的指定比例,或者单个标签的文本超过对应限制
                if max_text_length > all_text_length * limit_rate or (
                        max_text_length > limit_max_text_length and index == 0):
                    if max_node_dict.get(content_xpath) is None:
                        max_node_dict[content_xpath] = 1
                    else:
                        max_node_dict[content_xpath] += 1
                    break

        # 选择出现最多的一个规则
        if len(max_node_dict) == 0:
            print("解析content规则失败")
            return False
        max_count = 0
        for xpath_str, num in max_node_dict.items():
            if num > max_count:
                max_count = num
                self.rule_dict["ruleContent"]["content"] = xpath_str
        return True

    def __parse_category_rule(self):
        """分类规则"""
        pass

    def __parse_book_name_rule(self):
        book_name = self.search_info.get("book_name")
        # 获取最大的标题标签中的文本即书名
        level_list = [1, 2, 3]
        for level in level_list:
            tag_name = f"h{level}"
            xpath_str = f"//{tag_name}"
            results = get_html_element_info(self.detail_page, xpath_str)
            if len(results) == 1:
                if results[0].text == book_name:
                    full_xpath = get_full_xpath(results[0])
                    self.rule_dict["ruleBookInfo"]["name"] = f"{full_xpath}/text()"
                    return True
        # 查找整个文档中所有的文本匹配书名
        ele_list = get_html_element_info(self.detail_page, f"/html/body//*[text()='{book_name}']")
        if len(ele_list) == 1:
            full_xpath = get_full_xpath(ele_list[0])
            self.rule_dict["ruleBookInfo"]["name"] = f"{full_xpath}/text()"
            return True
        print("获取book info书名失败")
        self.rule_dict["ruleBookInfo"]["name"] = ""
        return False

    def __parse_book_detail_info_rule(self):
        """"""
        pass

    def __parse_book_chapter_list_rule(self):
        """章节目录列表规则"""
        limit_rate = 0.25  # 权重 TODO 需要对目录有分页的进一步处理
        # 获取页面的所有a标签的数量
        a_number = len(get_html_element_info(self.chapter_list_page, '//a'))
        # 获取所有a标签的父节点
        upper_xpath = '//a/..'
        upper_nodes = get_html_element_info(self.chapter_list_page, upper_xpath)
        xpath_str = ""
        p_xpath = ""
        for index in range(4):
            # 获取a标签最多的上级节点
            max_node, max_length, a_list, temp_xpath = self.get_max_num_node(index, upper_nodes)
            if max_length > int(limit_rate * a_number):
                p_xpath = get_full_xpath(max_node)
                a_length = len(a_list)
                if a_length > 20:
                    # 获取最多的一个相对子级标签xpath
                    select_node = a_list[int(a_length / 2) - 10:int(a_length / 2) + 10]
                    xpath_list = list()
                    for node in select_node:
                        temp_xpath = ''
                        for _ in range(index):
                            node = node.getparent()
                            p_tag = node.tag
                            temp_xpath = f'{p_tag}/{p_xpath}' if temp_xpath else p_tag
                        xpath_list.append(f'/{temp_xpath}')
                    t_xpath = Counter(xpath_list).most_common()[0][0]
                    xpath_str = f"{p_xpath}{t_xpath}/a"
                else:
                    t_xpath = '/node()' * index
                    xpath_str = f"{p_xpath}{t_xpath}/a"
                break
            upper_xpath = f'{upper_xpath}/..'
            upper_nodes = get_html_element_info(self.chapter_list_page, upper_xpath)
        else:
            print('get titles failed')
            return False
        # 去重，即前几张可能是最新章节，也就是最后几张
        title_list = get_html_element_info(self.chapter_list_page, f'{xpath_str}/text()')
        ele_list = get_html_element_info(self.chapter_list_page, xpath_str)
        counter_dict = Counter(title_list)
        index = 0
        for ele in ele_list:
            if counter_dict.get(ele.text) > 1:
                index += 1
            else:
                break
        if index > 0:
            # 获取对应去重之后的xpath，即重复章节不获取
            xpath_str = f'{p_xpath}/{xpath_str.replace(f"{p_xpath}/", "").replace("/", f"[position()>{index}]/")}'
        self.rule_dict["ruleToc"]["chapterList"] = xpath_str
        self.rule_dict["ruleToc"]["chapterName"] = f'{xpath_str}/text()'
        self.rule_dict["ruleToc"]["chapterUrl"] = f'{xpath_str}/@href'
        self.content_pages_url = [url_join(self.chapter_list_page_url, href) for href in
                                  get_html_element_info(self.chapter_list_page, f'{xpath_str}/@href')[-5:]]
        return True

    def __parse_book_chapter_name_rule(self):
        """目录页章节名称规则解析"""
        pass

    def __parse_book_chapter_url_rule(self):
        """获取章节内容url"""
        pass

    def __parse_book_next_chapter_rule(self):
        """获取下一章url规则"""
        self.rule_dict["ruleContent"]["nextContentUrl"] = ""
        # 使用解析章节列表时得到的url与章节详情里面a标签的url进行匹配得到下一章的a标签位置
        # 获取所有a标签
        ele_list = get_html_element_info(self.content_pages[0], "//a")
        # 解析下一章规则
        for ele in ele_list:
            href = ele.get("href")
            if not href:
                continue
            # 判断链接是否匹配
            if href.startswith("http://") or href.startswith("https://"):
                if href in self.content_pages_url:
                    self.rule_dict["ruleContent"]["nextContentUrl"] = f"{get_full_xpath(ele)}/@href"
                    return True
            else:
                for page_url in self.content_pages_url:
                    if page_url.endswith(href):
                        self.rule_dict["ruleContent"]["nextContentUrl"] = f"{get_full_xpath(ele)}/@href"
                        return True
        # 没有下一章则解析下一页等类的规则
        for ele in ele_list:
            if ele.text.startswith("下一"):
                self.rule_dict["ruleContent"]["nextContentUrl"] = f"{get_full_xpath(ele)}/@href"
                return True
        print("解析content页面")
        return False

    def __parse_find_rule(self):
        pass

    def __parse_book_introduce_rule(self):
        """简介规则"""
        self.rule_dict["ruleBookInfo"]["intro"] = ""
        max_length = self.search_info.get("intro_max_length")
        min_length = self.search_info.get("intro_min_length")
        book_name_xpath = self.rule_dict["ruleBookInfo"]["name"]
        if max_length is not None and min_length is not None:
            # 获取书名节点
            node = get_html_element_info(self.detail_page, book_name_xpath)[0]
            # 查找其父节点下所有节点文本符合长度的节点
            for _ in range(1, 3):
                parent_node = node.getparent()
                ele_list = parent_node.xpath(
                    f"//*[string-length(text())<{max_length} and string-length(text())>{min_length}]")
                if len(ele_list) == 1:
                    self.rule_dict["ruleBookInfo"]["intro"] = f"{get_full_xpath(ele_list[0])}/text()"
                elif len(ele_list) == 0:
                    node = parent_node
                    continue
                return
        return

    def __parse_book_cover_url_rule(self):
        """详情页书籍封面规则"""
        # 获取标题xpath
        title_xpath = self.rule_dict["ruleBookInfo"]["name"].replace("/text()", "")
        node = get_html_element_info(self.detail_page, title_xpath)[0]
        # 通过标题xpath获取其父节点，通过父节点查找所有子节点中的img标签
        for index in range(1, 10):
            if node.tag == "body":
                self.rule_dict["ruleBookInfo"]["coverUrl"] = ""
                return
            parent_node = node.getparent()
            img_node_list = list(parent_node.iter(tag="img"))
            if len(img_node_list) == 1:
                break
            elif len(img_node_list) == 0:
                node = parent_node
                continue
            else:
                count = 0
                img_node = None
                for node in img_node_list:
                    width = node.get("width")
                    height = node.get("height")
                    if width and height:
                        width = re.sub(r"[^0-9]{1,4}", "", str(width))
                        height = re.sub(r"[^0-9]{1,4}", "", str(height))
                        if int(width) > 100 and int(height) > 100:
                            count += 1
                            img_node = node
                if count == 1:
                    img_node_list = [img_node]
                    break
                node = parent_node
        else:
            self.rule_dict["ruleBookInfo"]["coverUrl"] = ""
            return
        img_xpath = get_full_xpath(img_node_list[0])
        self.rule_dict["ruleBookInfo"]["coverUrl"] = f"{img_xpath}/@src"

    def __parse_book_last_chapter_rule(self):
        """详情页最新章节规则"""
        self.rule_dict["ruleBookInfo"]["lastChapter"] = ""
        # 获取以最新章节：开头的标签下的a标签
        ele_list = get_html_element_info(self.detail_page, "//*[starts-with(string(.), '最新章节')]//a")
        if len(ele_list) == 1:
            self.rule_dict["ruleBookInfo"]["lastChapter"] = f"{get_full_xpath(ele_list[0])}/@href"
            return True
        # a标签唯一则就是最新章节标签
        if len(ele_list) == 1:
            self.rule_dict["ruleBookInfo"]["lastChapter"] = f"{get_full_xpath(ele_list[0])}/@href"
            return True
        # 获取最新章节文本所在标签，查找其子标签是否有a标签
        xpath = "//*[contains(text(), '最新章节：')]//a"
        ele_list = get_html_element_info(self.detail_page, xpath)
        # a标签唯一则就是最新章节标签
        if len(ele_list) == 1:
            self.rule_dict["ruleBookInfo"]["lastChapter"] = f"{get_full_xpath(ele_list[0])}/@href"
            return True
        # 有多个a标签
        elif len(ele_list) > 1:
            for ele in ele_list:
                result = re.search(r"第.{1,8}[章节篇]{1}", ele.text)
                if result is not None:
                    self.rule_dict["ruleBookInfo"]["lastChapter"] = f"{get_full_xpath(ele)}/@href"
                    return True
            else:
                print("解析最新章节失败")
                return False
        # 没有a标签；获取最新章节父标签的所有子标签中的a标签
        ele_list = get_html_element_info(self.detail_page, "//*[contains(text(), '最新章节：')]/..//a")
        if len(ele_list) == 0:
            print("解析最新章节规则失败")
            return False
        # 对子标签进行匹配
        for ele in ele_list:
            result = re.search(r"第.{1,8}[章节篇]{1}", ele.text)
            if result is not None:
                self.rule_dict["ruleBookInfo"]["lastChapter"] = f"{get_full_xpath(ele)}/@href"
                return True
        return False

    def __parse_search_author_rule(self):
        """搜索结果作者规则"""
        # 通过搜索指定书名来查找对应作者名获取标签
        author = '辰东'
        max_author_num = 5
        results = get_html_element_info(self.search_page, f"//*[string(.)='{author}']")
        if len(results) != 0:
            # 获取到搜索书籍的作者规则
            author_xpath = get_full_xpath(results[0])
            xpath_suffix = author_xpath.rsplit("/", maxsplit=1)[1]
            # 通过父节点获取所有作者的规则
            upper_tag_path = ""
            for index in range(1, 5):
                upper_xpath = f"{author_xpath}{'/..' * index}"
                upper_tag = get_html_element_info(self.search_page, upper_xpath)[0].tag
                if upper_tag_path == "":
                    node_xpath = f"{upper_xpath}/{xpath_suffix}"
                else:
                    node_xpath = f"{upper_xpath}{upper_tag_path}/{xpath_suffix}"
                results = get_html_element_info(self.search_page, node_xpath)
                if len(results) > max_author_num:
                    self.rule_dict["ruleSearchAuthor"] = node_xpath
                    break
                upper_tag_path = f"{upper_tag_path}/{upper_tag}"
            else:
                print("获取作者规则失败")

    def __parse_search_cover_rule(self):
        pass

    def __parse_search_kind_rule(self):
        """搜索结果分类规则"""
        pass

    def __parse_search_last_chapter_rule(self):
        """搜索结果最新章节规则"""
        pass

    def __parse_search_page_rule(self):
        """搜索结果列表规则"""
        # 通过搜索的书名获取到对应书名的a标签，通过回溯父标签来获取规则
        # 获取指定内容的a标签，通过精准查找或模糊查找标签
        target_xpath_list = [
            f"//a[string(.)='{self.search_info.get('book_name')}']",
        ]
        flag = False
        for xpath in target_xpath_list:
            element_list = get_html_element_info(self.search_page, xpath)
            if element_list:
                for ele in element_list:
                    if self.__search_list_tag_analyze(ele) is True:
                        flag = True
                        # 获取对应书籍详情页url
                        self.book_info_page_url = self.get_full_url(self.url, ele.xpath("@href")[0])
                        break
            if flag is True:
                break
        else:
            print("获取搜索页规则失败")
            return False
        return True

    def __parse_search_name_rule(self):
        """搜索结果名称规则"""
        # 通过搜索名称获取到内容页面对应名称，从而获取规则
        pass

    def __parse_search_book_url_rule(self):
        pass

    def __parse_search_url_rule(self):
        """搜索url解析"""
        search_keyword = "完美世界"
        # 获取输入框xpath todo 还需要判断是否有其他字段
        search_xpath, is_selenium = self.__get_search_input_box_path(self.home_page)
        if is_selenium:
            # 通过selenium获取的xpath需要用对应的页面
            self.home_page = WebPage(self.url).find_element(by=By.XPATH, value="//html").parent.page_source
        if search_xpath == "":
            print(f"{self.title}, 获取输入框search_xpath失败，url = {self.url}")
            # 获取输入框xpath失败处理
            file_name = re.sub(u"([^\u4e00-\u9fa5\u0030-\u0039\u0041-\u005a\u0061-\u007a])", "", self.title)
            with open(f"gen_book_rule/pages/{file_name}.html", "wb") as f:
                f.write(self.home_page.encode("utf-8"))
            return False
        # 检测是否为表单提交，是表单提交则获取表单信息
        if "/form" in search_xpath:
            # 表单提交处理
            form_xpath = f"{search_xpath.split('/form')[0]}/form"
            # 获取请求方式
            result = get_html_element_info(self.home_page, f"{form_xpath}/@method")
            if len(result) == 0:
                request_method = "get"
            else:
                request_method = result[0]
            # 获取请求地址
            result = get_html_element_info(self.home_page, f"{form_xpath}/@action")
            if len(result) <= 0:
                print("获取action url失败")
                return False
            full_url = self.get_full_url(self.url, result[0])
            field_name = get_html_element_info(self.home_page, f"{search_xpath}/@name")[0]
            if request_method == "post":
                search_url = f'{full_url},{{\n  "method": "{request_method}",\n  "body": "{field_name}={{{{key}}}}"}}'
            else:
                search_url = f"{full_url}?{field_name}={{{{key}}}}"
        else:
            # 非表单提交处理
            # 完整页面和原始页面有差别，进行定位需要使用各种属性完整定位或直接使用哦个完整页面进行解析
            full_xpath = search_xpath
            if is_selenium is False:
                # 拼接出相对xpath定位元素
                filter_list = list()
                ele = get_html_element_info(self.home_page, search_xpath)[0]
                attr_list = ele.keys()
                attr_value_list = ele.values()
                for attr in attr_list:
                    result = get_html_element_info(self.home_page, f"{search_xpath}/@{attr}")
                    if result:
                        filter_list.append(f"@{attr}='{result[0]}'")
                results = get_html_element_info(self.home_page, f"{search_xpath}/@placeholder")
                if results:
                    filter_list.append(f"@value='{results[0]}'")
                filter_list = [f"@{attr}='{attr_value_list[index]}'" for index, attr in enumerate(attr_list)]
                full_xpath = f"//input[{' and '.join(filter_list)}]"
            # 操作页面
            page = WebPage(url=self.url)
            old_url = page.current_url
            search_input_box = page.find_element(by=By.XPATH, value=full_xpath)
            search_input_box.send_keys(search_keyword)
            search_input_box.send_keys(Keys.ENTER)  # TODO 暂时使用回车进行代替点击，回车不生效的网站之后再进一步处理
            if old_url == page.current_url:
                #  回车跳转不生效，寻找点击按钮跳转
                results = get_html_element_info(self.home_page, f"{full_xpath}/..//*")
                if len(results) == 0:
                    print("没有查找到正确的按钮")
                    return False
                for ele in results:
                    if get_full_xpath(ele) == full_xpath:
                        continue
                    if "搜" in str(ele.text) and "索" in str(ele.text):
                        # 点击按钮
                        page.find_element(by=By.XPATH, value=get_full_xpath(ele)).click()
                        break
                    values = ele.xpath("@value")
                    if values:
                        if "搜" in values[0] and "索" in values[0]:
                            # 点击按钮
                            page.find_element(by=By.XPATH, value=get_full_xpath(ele)).click()
                            break
                else:
                    print("没有查找到按钮")
                    return False
                if old_url == page.current_url:
                    print("没有查找到正确的按钮")
                    return False
            search_url = unquote(page.current_url).replace(search_keyword, "{{key}}")
        self.rule_dict["searchUrl"] = search_url

    def __get_search_input_box_path(self, html_text, is_selenium=False):
        keywords = ["书名", "作者", "search", "搜索", "小说"]
        type_list = constant.input_box_type_list
        for tag_type in type_list:
            # 直接查找input标签
            html = etree.HTML(html_text)
            element_list = html.xpath(f"//input[@type='{tag_type}']")
            if len(element_list) == 1:
                return get_full_xpath(element_list[0]), is_selenium
            elif len(element_list) == 0:
                # 没有input标签则使用selenium渲染后重新解析
                page = WebPage(self.url)
                element = page.find_element(by=By.XPATH, value="//html")
                if is_selenium is False:
                    return self.__get_search_input_box_path(element.parent.page_source, is_selenium=True)
                print("解析input标签xpath表达式失败")
                return "", is_selenium
            # 标签数量不为一，查找form标签下所有的input标签
            element_list = html.xpath(f"//form/*/input[@type='{tag_type}']")
            if len(element_list) == 1:
                return get_full_xpath(element_list[0]), is_selenium
            elif len(element_list) > 1:
                # input标签不唯一，对标签进行判断是不是是多个相同标签
                if len(set(html.xpath(f"//form/*/input[@type='{tag_type}']/@name"))) == 1:
                    tree = etree.ElementTree(element_list[0])
                    xpath_str = tree.getpath(element_list[0])
                    return get_full_xpath(element_list[0]), is_selenium
                else:
                    nodes = get_html_element_info(html_text, f"//form/*/input[@type='{tag_type}']")
                    for node in nodes:
                        attrs_value_str = "".join(node.values())
                        for keyword in keywords:
                            if keyword in attrs_value_str:
                                return get_full_xpath(node), is_selenium
            # 匹配标签属性中是否有关键字
            element_list = html.xpath(f"//input[@type='{tag_type}']")
            for ele in element_list:
                attrs_value_str = "".join(ele.values())
                for keyword in keywords:
                    if keyword in attrs_value_str:
                        return get_full_xpath(ele), is_selenium
        print("解析input标签xpath表达式失败")
        return "", is_selenium

    def __search_list_tag_analyze(self, ele):
        full_xpath = get_full_xpath(ele)
        # td tr标签；如果是td tr标签，则，tr[1]就为表头，结果应该从[2]开始
        if "td" in full_xpath and "tr" in full_xpath:
            if self.__analyze_search_list_tr_td_tag(full_xpath) is True:
                return True
        # ul li标签， ul为行，li为列
        if "ul" in full_xpath and "li" in full_xpath:
            if self.__analyze_search_list_ul_li_tag(full_xpath) is True:
                return True
        # div标签， 第一个和后面的规则不一致的标签（这个规则的网站不管）
        return self.__analyze_search_list_div_tag(ele)

    def __analyze_search_list_tr_td_tag(self, full_xpath):
        # tr为行标签，td为列标签
        # 目录为tr[0], 列表项为position()>1
        list_xpath = re.sub(r"tr\[[0-9]{1,3}]", "tr[position()>1]", full_xpath)
        if len(get_html_element_info(self.search_page, list_xpath)) > 0:
            self.rule_dict["ruleSearch"]["bookList"] = list_xpath
            self.rule_dict["ruleSearch"]["name"] = f"{list_xpath}/text()"
            self.rule_dict["ruleSearch"]["bookUrl"] = f"{list_xpath}/@href"
        else:
            "获取bookList xpath失败"
            return False
        # 获取表头字段索引
        head_xpath = re.sub(r"tr\[[0-9]{1,3}]/.*", "tr[1]/th", full_xpath)
        ele_list = get_html_element_info(self.search_page, head_xpath)
        kind_index = 0
        intro_index = 0
        author_index = 0
        for index, ele in enumerate(ele_list):
            # 分类
            if "分类" in ele.text or "类别" in ele.text:
                kind_index += index + 1
                continue
            # 简介
            if "简介" in ele.text or "介绍" in ele.text or "描述" in ele.text:
                intro_index += index + 1
                continue
            # 作者
            if "作者" in ele.text or ("作" in ele.text and "者" in ele.text):
                author_index += index + 1
                continue

        # 获取行下所有文本，通过查找对应作者名确定xpath
        ele_list = get_html_element_info(self.search_page, re.sub(r"/td.*", "//*", full_xpath))
        for ele in ele_list:
            if ele.text == self.search_info.get("author"):
                author_xpath = re.sub(r"tr\[[0-9]{1,3}]", "tr[position()>1]", get_full_xpath(ele))
                self.rule_dict["ruleSearch"]["author"] = f"{author_xpath}/text()"
                break
        else:
            print("获取search list author规则失败")
            return False
        # 获取分类xpath
        if kind_index > 0:
            kind_xpath = re.sub(r"td\[[0-9]{1,3}].*", f"td[{kind_index}]/text()", list_xpath)
            self.rule_dict["ruleSearch"]["kind"] = f"{kind_xpath}/text()"
        # 获取简介
        if intro_index > 0:
            intro_xpath = re.sub(r"td\[[0-9]{1,3}].*", f"td[{intro_index}]/text()", list_xpath)
            self.rule_dict["ruleSearch"]["kind"] = f"{intro_xpath}/text()"
        return True

    def __analyze_search_list_ul_li_tag(self, full_xpath):
        # 目录为//ul/li[1]，标题列表项为position()>1
        head_xpath = re.sub(r"li\[[\d]{1,4}].*", "li[1]", full_xpath)
        list_xpath = re.sub(r"li\[[\d]{1,4}]", "li[position()>1]", full_xpath)
        if len(get_html_element_info(self.search_page, list_xpath)) > 0:
            self.rule_dict["ruleSearch"]["bookList"] = list_xpath
            self.rule_dict["ruleSearch"]["name"] = f"{list_xpath}/text()"
            self.rule_dict["ruleSearch"]["bookUrl"] = f"{list_xpath}/@href"
        else:
            "获取bookList xpath失败"
            return False
        # 获取分析表头字段，从而获取对应字段的xpath
        ele_list = get_html_element_info(self.search_page, head_xpath)
        if len(ele_list) != 1:
            print("获取表头字段索引失败")
            return True

        def check_finish():
            if self.rule_dict["ruleSearch"].get("kind") is not None and \
                    self.rule_dict["ruleSearch"].get("kind") is not None and \
                    self.rule_dict["ruleSearch"].get("kind") is not None:
                return True
            return False

        def check_xpath(xpath):
            if len(get_html_element_info(self.search_page, xpath)) > 0:
                return True
            return False

        for sub_ele in ele_list[0].iter():
            if not sub_ele.text:
                continue
            # 分类
            if self.rule_dict["ruleSearch"].get("kind") is None and ("分类" in sub_ele.text or "类别" in sub_ele.text):
                sub_ele_full_xpath = get_full_xpath(sub_ele)
                kind_xpath = re.sub(r"li\[[\d]{1,4}]", "li[position()>1]", sub_ele_full_xpath)
                # 检测xpath正确性
                for _ in range(3):
                    if check_xpath(kind_xpath):
                        break
                    # xpath不正确则向父节点推
                    kind_xpath = kind_xpath.rsplit("/", maxsplit=1)[0]
                self.rule_dict["ruleSearch"]["kind"] = f"{kind_xpath}/text()"
                if check_finish():
                    break
                continue
            # 简介
            if self.rule_dict["ruleSearch"].get("intro") is None and (
                    "简介" in sub_ele.text or "介绍" in sub_ele.text or "描述" in sub_ele.text):
                sub_ele_full_xpath = get_full_xpath(sub_ele)
                intro_xpath = re.sub(r"li\[[\d]{1,4}]", "li[position()>1]", sub_ele_full_xpath)
                # 检测xpath正确性
                for _ in range(3):
                    if check_xpath(intro_xpath):
                        break
                    # xpath不正确则向父节点推
                    intro_xpath = intro_xpath.rsplit("/", maxsplit=1)[0]
                self.rule_dict["ruleSearch"]["intro"] = f"{intro_xpath}/text()"
                if check_finish():
                    break
                continue
            # 作者
            if self.rule_dict["ruleSearch"].get("author") is None and (
                    "作者" in sub_ele.text or ("作" in sub_ele.text and "者" in sub_ele.text)):
                sub_ele_full_xpath = get_full_xpath(sub_ele)
                author_xpath = re.sub(r"li\[[\d]{1,4}]", "li[position()>1]", sub_ele_full_xpath)
                # 检测xpath正确性
                for _ in range(3):
                    if check_xpath(author_xpath):
                        break
                    # xpath不正确则向父节点推
                    author_xpath = author_xpath.rsplit("/", maxsplit=1)[0]
                self.rule_dict["ruleSearch"]["author"] = f"{author_xpath}/text()"
                if check_finish():
                    break
                continue
        else:
            print("获取搜索页分类，简介，作者字段失败")
        return True

    def __analyze_search_list_div_tag(self, ele):
        pass

    @staticmethod
    def get_max_num_node(index, upper_nodes):
        max_length = 0
        max_node = None
        a_list = None
        temp_xpath = ''
        for node in upper_nodes:
            temp_xpath = f"./{'node()/' * index}" if index != 0 else './'
            # temp_xpath = f"{'../' * index}*" if index != 0 else '.'
            temp_a_list = node.xpath(f'{temp_xpath}a')
            length = len(temp_a_list)
            if length > max_length:
                max_length = length
                max_node = node
                a_list = temp_a_list
        return max_node, max_length, a_list, temp_xpath

    @staticmethod
    def get_full_url(request_url, url):
        if not url.startswith('http'):
            if url.startswith('/'):
                base_url = get_prefix_url(request_url)
            else:
                base_url = request_url
            return url_join(base_url, url)
        return url
