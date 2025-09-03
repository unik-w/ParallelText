from ebooklib import epub
from bs4 import BeautifulSoup
from typing import List
from ..types import Book, AlignmentUnit, MergeResult

CSS_PATH = "paralleltext/css/base.css"


def _wrap_pair(unit: AlignmentUnit, src_lang: str, tgt_lang: str) -> str:
    # Ensure each p has proper class/lang
    def ensure_block(html: str, klass: str, lang: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        p = soup.find("p") or soup
        if p.name != "p":
            p = soup.new_tag("p")
            p.string = soup.get_text()
            p["class"] = (p.get("class") or []) + [klass]
        if lang:
            p["lang"] = lang
        return str(p)

    src = ensure_block(unit.src_html, "src", src_lang)
    tgt = ensure_block(unit.tgt_html, "tgt", tgt_lang)
    return src + "\n" + tgt


def build_merged_epub(
    src: Book, tgt: Book, per_chapter_units: List[List[AlignmentUnit]], out_path: str
) -> None:
    book = epub.EpubBook()
    # Metadata (simple for M1)
    title = f"{src.title} / {tgt.title} (Parallel Edition)".strip()
    book.set_title(title)
    for a in sorted(set(src.authors + tgt.authors)):
        book.add_author(a)
    book.set_language(src.language or "und")

    # CSS
    with open(CSS_PATH, "r", encoding="utf-8") as f:
        css_content = f.read()
    style = epub.EpubItem(
        uid="style_base",
        file_name="styles/base.css",
        media_type="text/css",
        content=css_content,
    )
    book.add_item(style)

    spine = ["nav"]
    toc = []

    for i, units in enumerate(per_chapter_units, start=1):
        html = [
            '<html xmlns="http://www.w3.org/1999/xhtml">',
            '<head><meta charset="utf-8"/><link rel="stylesheet" type="text/css" href="styles/base.css"/></head>',
            f"<body>",
        ]
        for u in units:
            html.append(_wrap_pair(u, src.language, tgt.language))
        html.append("</body></html>")
        chapter = epub.EpubHtml(
            title=f"Chapter {i}",
            file_name=f"chap_{i:03}.xhtml",
            content="\n".join(html),
        )
        book.add_item(chapter)
        spine.append(chapter)
        toc.append(chapter)

    book.toc = tuple(toc)
    book.spine = spine

    # Nav
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(out_path, book)
