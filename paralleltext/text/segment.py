from bs4 import BeautifulSoup
from bs4.element import Tag
from typing import List

_BLOCK_TAGS = ["p", "li", "div", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"]


def paragraph_elements(soup: BeautifulSoup) -> List[Tag]:
    """Return the paragraph-level elements of a parsed chapter, in DOM order.

    Normally <p> and list items. Some converters (e.g. Calibre from MOBI) wrap
    each paragraph in a <div> instead of a <p>, so leaf <div>s are used too
    when they outnumber <p>/<li>.
    """
    blocks = soup.find_all(["p", "li"])
    leaf_divs = [
        el
        for el in soup.find_all("div")
        if el.get_text(strip=True) and not el.find(_BLOCK_TAGS)
    ]
    if len(leaf_divs) > len(blocks):
        leaf_ids = {id(el) for el in leaf_divs}
        blocks = [
            el
            for el in soup.find_all(["p", "li", "div"])
            if el.name != "div" or id(el) in leaf_ids
        ]
    return blocks


def paragraphs_from_xhtml(xhtml: str) -> List[str]:
    """Return a list of paragraph-level HTML strings.

    Keeps inline markup; normalizes <p> and list items as blocks.
    """
    soup = BeautifulSoup(xhtml, "lxml")

    # Remove scripts/styles
    for bad in soup.find_all(["script", "style"]):
        bad.decompose()

    blocks = [str(el) for el in paragraph_elements(soup)]

    # Fallback: if no <p> or <li>, split by double <br>
    if not blocks:
        for br in soup.find_all("br"):
            br.replace_with("\n")
            text = soup.get_text("\n")
            chunks = [c.strip() for c in text.split("\n\n") if c.strip()]
            blocks = [f"<p>{c}</p>" for c in chunks]

    return blocks
