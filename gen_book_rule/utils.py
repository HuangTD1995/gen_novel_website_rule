from urllib.parse import urlparse, urlunparse, urljoin
from posixpath import normpath

from lxml import etree


def get_prefix_url(url):
    res = urlparse(url)
    url = f'{res.scheme}://{res.netloc}'
    return url


def url_join(base, url):
    url1 = urljoin(base, url)
    arr = urlparse(url1)
    path = normpath(arr[2])
    return urlunparse((arr.scheme, arr.netloc, path, arr.params, arr.query, arr.fragment))


def get_html_element_info(html_text, xpath_str):
    html = etree.HTML(html_text)
    return html.xpath(xpath_str)


def get_full_xpath(node):
    tree = etree.ElementTree(node)
    return tree.getpath(node)
