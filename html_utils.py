from bs4 import BeautifulSoup, Comment
from bs4.element import NavigableString
from hashlib import sha256


def get_html_hash(doc: str):
    # print(doc)
    soup = BeautifulSoup(doc, features="html.parser")
    for tag in soup.findAll(True):
        for element in tag(text=lambda text: isinstance(text, (Comment, NavigableString))):
            element.extract()
        tag.attrs = None

    for s in soup.select('script'):
        s.extract()
    for s in soup.select('style'):
        s.extract()

    return str(sha256(str(soup.find('body')).strip().encode()).hexdigest())
