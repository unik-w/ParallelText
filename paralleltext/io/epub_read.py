import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from typing import List
from ..types import Book, Chapter

MAIN_DOC_TYPES = {ebooklib.ITEM_DOCUMENT}


EXCLUDE_HINTS = (
    "copyright",
    "imprint",
    "sources",
    "quellen",
    "afterword",
    "danksagung",
    "thanks",
)


def load_epub(path: str) -> Book:
    book = epub.read_epub(path)
    lang = (book.get_metadata("DC", "language") or [("", {})])[0][0] or ""
    title = (book.get_metadata("DC", "title") or [("", {})])[0][0] or ""
    authors = [a[0] for a in book.get_metadata("DC", "creator")] or []

    chapters: List[Chapter] = []

    # Iterate spine order, keep only xhtml documents
    for idref, _linear in book.spine:
        item = book.get_item_with_id(idref)
        if item is None or item.get_type() not in MAIN_DOC_TYPES:
            continue
        html = item.get_content().decode("utf-8", errors="ignore")
        # Heuristic: skip obvious back/front matter by title text
        soup = BeautifulSoup(html, "lxml")
        text_blob = soup.get_text(" ", strip=True).lower()
        if any(h in text_blob[:200] for h in EXCLUDE_HINTS):
            continue
        # Derive a chapter title
        h = soup.find(["h1", "h2", "h3"]) or soup.find("title")
        chap_title = h.get_text(strip=True) if h else "Chapter"
        chapters.append(Chapter(title=chap_title, html=html))

        return Book(
            language=lang or "", title=title, authors=authors, chapters=chapters
        )
