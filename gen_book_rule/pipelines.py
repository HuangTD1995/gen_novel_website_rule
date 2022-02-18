# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import json

from itemadapter import ItemAdapter


class GenBookRulePipeline:
    def process_item(self, item, spider):
        return item

    def close_spider(self, spider):
        with open("gen_book_rule/data/success_urls.txt", "w") as f:
            f.write(json.dumps(spider.success_url_list))
        with open("gen_book_rule/data/search_info_list.txt", "w") as f:
            f.write(json.dumps(spider.search_info_list))
        with open("gen_book_rule/data/fail_urls.txt", "w") as f:
            f.write(json.dumps(spider.fail_url_list))
        pass
