import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from pathlib import Path
from typing import Dict, List

from ..types import Chapter, Book

MAIN_DOC_TYPES = {ebooklib.ITEM_DOCUMENT}


def _toc_title_map(book: epub.EpubBook) -> Dict[str, str]:
    """Map chapter file href (fragment stripped) -> the book's own TOC label.

    Readers show these labels (e.g. "1", "2", "VL") in their table of
    contents/sidebar, so reusing them beats guessing from <h1>-<h3> tags.
    """
    mapping: Dict[str, str] = {}

    def walk(entries) -> None:
        for entry in entries:
            if isinstance(entry, tuple):
                section, children = entry
                href = getattr(section, "href", None)
                title = getattr(section, "title", None)
                if href and title:
                    mapping.setdefault(href.split("#")[0], title)
                walk(children)
            else:
                href = getattr(entry, "href", None)
                title = getattr(entry, "title", None)
                if href and title:
                    mapping.setdefault(href.split("#")[0], title)

    walk(book.toc)
    return mapping


def load_epub(path: str) -> Book:
    """Load an EPUB and return all chapters unfiltered.

    Content classification/filtering is handled downstream by
    paralleltext.text.classify.
    """
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

    toc_titles = _toc_title_map(book)
    chapters: List[Chapter] = []

    # Iterate spine order, keep only xhtml documents
    for spine_idx, (idref, _linear) in enumerate(book.spine):
        item = book.get_item_with_id(idref)
        if item is None or item.get_type() not in MAIN_DOC_TYPES:
            continue
        html = item.get_content().decode("utf-8", errors="ignore")
        # Derive a chapter title: prefer the book's own TOC label, then
        # <h1>-<h3>/<title>, else a generic fallback.
        chap_title = toc_titles.get(item.file_name)
        if not chap_title:
            soup = BeautifulSoup(html, "xml")
            h = soup.find(["h1", "h2", "h3"]) or soup.find("title")
            chap_title = h.get_text(strip=True) if h else "Chapter"
        chapters.append(
            Chapter(title=chap_title, html=html, spine_position=spine_idx)
        )

    return Book(language=lang or "", title=title, authors=authors, chapters=chapters)
