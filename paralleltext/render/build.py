from ebooklib import epub
from typing import List
from ..types import Book, AlignmentUnit  # adjust if types live elsewhere
from html import escape


# assume `per_chapter_units` is a list where each item is a list of AlignmentUnit objects
# and src_book/tgt_book are `Book` objects with metadata we can copy
def build_merged_epub(
    src_book: Book, tgt_book: Book, per_chapter_units: List[List[AlignmentUnit]], out_path: str
) -> None:
    out = epub.EpubBook()
    out.set_language(src_book.language or "und")
    out.set_title(f"{src_book.title} — Parallel Edition")

    # Basic stylesheet to gray the target language and lay out two columns.
    css = epub.EpubItem(
        uid="style",
        file_name="style/parallel.css",
        media_type="text/css",
        content=b"""
html, body { margin: 0; padding: 0; }
.pt-chapter { padding: 1.2rem 1rem; }
.pt-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 0.75rem; }
.pt-src { line-height: 1.5; }
.pt-tgt { line-height: 1.5; color: #666; }
.pt-meta { font-size: 0.9em; color: #666; margin: 0.5rem 0 1rem; }
""",
    )
    out.add_item(css)

    spine = ["nav"]

    for i, units in enumerate(per_chapter_units, start=1):
        item = epub.EpubHtml(
            title=f"Chapter {i}",
            file_name=f"chap_{i:03}.xhtml",
        )
        html = [
            '<html xmlns="http://www.w3.org/1999/xhtml"><head><meta charset="utf-8"/>',
            '<link rel="stylesheet" type="text/css" href="../style/parallel.css"/>',
            "</head><body>",
            f'<div class="pt-chapter"><div class="pt-meta">{escape(src_book.title)} / {escape(tgt_book.title)}</div>',
        ]
        for unit in units:
            # unit is an AlignmentUnit object with src_html and tgt_html attributes
            html.append(
                '<div class="pt-row">'
                f'<div class="pt-src" lang="{src_book.language or "und"}">{unit.src_html}</div>'
                f'<div class="pt-tgt" lang="{tgt_book.language or "und"}">{unit.tgt_html}</div>'
                "</div>"
            )
        html.append("</div></body></html>")
        item.set_content("".join(html).encode("utf-8"))
        out.add_item(item)
        spine.append(item)

    out.spine = spine
    out.toc = tuple(spine[1:])  # skip cover/title if you add one earlier
    out.add_item(epub.EpubNcx())
    out.add_item(epub.EpubNav())
    # Ensure CSS is packaged:
    out.add_item(css)

    epub.write_epub(out_path, out)
