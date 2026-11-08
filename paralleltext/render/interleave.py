"""Write a parallel EPUB that keeps the source (e.g. German) book as it is.

The source EPUB is copied file by file - its own pages, stylesheets, fonts,
images, cover and table of contents - and only the chapters that received
translations are replaced. Each translation sits right after the source
paragraph it belongs to, styled smaller, italic and grey.
"""

import re
import uuid
import zipfile
from html.entities import name2codepoint
from typing import Dict, Iterable

from bs4 import BeautifulSoup
from bs4.element import Tag

TRANSLATION_CSS = """
.pt-tgt { font-style: italic; font-size: 0.9em; color: #555; margin: 0.2em 0 0.9em 0; }
.pt-tgt p, .pt-tgt div { margin: 0; text-indent: 0; }
"""

_XML_ENTITIES = {"amp", "lt", "gt", "quot", "apos"}
_ENTITY_RE = re.compile(r"&([A-Za-z][A-Za-z0-9]*);")


def _numeric_entities(xhtml: str) -> str:
    """Turn HTML named entities (&nbsp; ...) into numeric references.

    XHTML pages may rely on their DTD for these, which an XML parser does not
    load, so they would otherwise be lost when the page is re-serialised.
    """

    def repl(m: "re.Match") -> str:
        name = m.group(1)
        if name in _XML_ENTITIES or name not in name2codepoint:
            return m.group(0)
        return f"&#{name2codepoint[name]};"

    return _ENTITY_RE.sub(repl, xhtml)


def read_source_docs(
    src_epub_path: str, file_names: Iterable[str]
) -> Dict[str, BeautifulSoup]:
    """Parse chapter files exactly as stored in the EPUB.

    ebooklib's item content for HTML documents is regenerated (the <head> with
    the book's stylesheet links is dropped), so the raw zip entries are used.
    file_names are relative to the OPF, as ebooklib reports them.
    """
    docs = {}
    with zipfile.ZipFile(src_epub_path) as zf:
        opf = _opf_path(zf)
        opf_dir = opf.rsplit("/", 1)[0] + "/" if "/" in opf else ""
        for name in file_names:
            raw = zf.read(opf_dir + name).decode("utf-8", errors="replace")
            docs[name] = BeautifulSoup(_numeric_entities(raw), "xml")
    return docs


def translation_block(doc: BeautifulSoup, tgt_html: str, lang: str) -> Tag:
    """Wrap translated paragraph(s) in a styled <div>, cleaned for the new book.

    Images, links, ids and classes refer to the target EPUB's own files and
    stylesheet, so they are dropped.
    """
    frag = BeautifulSoup(tgt_html, "html.parser")
    for el in frag.find_all(["img", "image", "svg", "script", "style"]):
        el.decompose()
    for a in frag.find_all("a"):
        a.unwrap()
    for el in frag.find_all(True):
        el.attrs.pop("id", None)
        el.attrs.pop("class", None)
    div = doc.new_tag("div", attrs={"class": "pt-tgt", "lang": lang})
    for child in list(frag.contents):
        div.append(child)
    return div


def add_translation_style(doc: BeautifulSoup) -> None:
    head = doc.find("head")
    if head is None:
        return
    style = doc.new_tag("style", attrs={"type": "text/css"})
    style.string = TRANSLATION_CSS
    head.append(style)


def _opf_path(zf: zipfile.ZipFile) -> str:
    container = zf.read("META-INF/container.xml").decode("utf-8")
    return re.search(r'full-path="([^"]+)"', container).group(1)


def write_interleaved_epub(
    src_epub_path: str,
    replaced_docs: Dict[str, str],
    out_path: str,
    title_suffix: str = "",
) -> None:
    """Copy the source EPUB, swapping in replaced chapter documents.

    replaced_docs maps a chapter's path relative to the OPF (as ebooklib
    reports it) to its new XHTML.
    """
    with zipfile.ZipFile(src_epub_path) as zin:
        opf = _opf_path(zin)
        opf_dir = opf.rsplit("/", 1)[0] + "/" if "/" in opf else ""
        replaced = {opf_dir + name: xhtml for name, xhtml in replaced_docs.items()}

        # Give the new book its own identifier: readers key saved positions
        # and caches on it, and must not confuse it with the source edition.
        opf_text = zin.read(opf).decode("utf-8")
        old_id = _unique_identifier(opf_text)
        new_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"paralleltext:{old_id}"))

        with zipfile.ZipFile(out_path, "w") as zout:
            # The mimetype entry must come first and be stored uncompressed.
            zout.writestr(
                zipfile.ZipInfo("mimetype"),
                zin.read("mimetype"),
                compress_type=zipfile.ZIP_STORED,
            )
            for info in zin.infolist():
                if info.filename == "mimetype":
                    continue
                data = zin.read(info.filename)
                if info.filename in replaced:
                    data = replaced[info.filename].encode("utf-8")
                elif info.filename == opf:
                    text = data.decode("utf-8")
                    if title_suffix:
                        text = re.sub(
                            r"(<dc:title[^>]*>)(.*?)(</dc:title>)",
                            lambda m: m.group(1) + m.group(2) + title_suffix + m.group(3),
                            text,
                            count=1,
                            flags=re.S,
                        )
                    if old_id:
                        text = text.replace(old_id, new_id)
                    data = text.encode("utf-8")
                elif info.filename.endswith(".ncx") and old_id:
                    data = data.decode("utf-8").replace(old_id, new_id).encode("utf-8")
                zout.writestr(info.filename, data, compress_type=zipfile.ZIP_DEFLATED)


def _unique_identifier(opf_text: str) -> str:
    """Value of the OPF's unique-identifier element (without a urn:uuid: prefix)."""
    m = re.search(r'unique-identifier="([^"]+)"', opf_text)
    if not m:
        return ""
    el = re.search(
        r'<dc:identifier[^>]*\bid="' + re.escape(m.group(1)) + r'"[^>]*>(.*?)</dc:identifier>',
        opf_text,
        flags=re.S,
    )
    value = el.group(1).strip() if el else ""
    return value[len("urn:uuid:"):] if value.startswith("urn:uuid:") else value
