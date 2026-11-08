import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from pathlib import Path
from typing import List

from ..types import Chapter, Book

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

    # --- helper: ebooklib raises KeyError if a metadata name is missing
    def _safe_meta_first(ns: str, name: str, fallback: str = "") -> str:
        try:
            vals = book.get_metadata(ns, name)
        except KeyError:
            vals = []
        if not vals:
            return fallback
        # ebooklib returns list of tuples like: [(text, attrs_dict), ...]
        return (
            (vals[0][0] or fallback) if isinstance(vals[0], (list, tuple)) else fallback
        )

    def _safe_meta_all(ns: str, name: str) -> List[str]:
        try:
            vals = book.get_metadata(ns, name)
        except KeyError:
            vals = []
        out: List[str] = []
        for v in vals:
            if isinstance(v, (list, tuple)) and v and v[0]:
                out.append(v[0])
        return out

    lang = _safe_meta_first("DC", "language", "und") or "und"
    title = _safe_meta_first("DC", "title", Path(path).stem) or Path(path).stem
    authors = _safe_meta_all("DC", "creator")

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
        chapters.append(Chapter(title=chap_title, html=html, file_name=item.file_name))

    return Book(language=lang or "", title=title, authors=authors, chapters=chapters)
