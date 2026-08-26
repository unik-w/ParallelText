from ebooklib import epub
from typing import List, Optional, Tuple
from ..types import Book, Chapter, AlignmentUnit
from html import escape
from bs4 import BeautifulSoup
import pathlib
import re
import xml.etree.ElementTree as ET
import zipfile
from .cover import generate_combined_cover


def extract_epub_metadata(epub_path: str) -> dict:
    """Extract metadata from an EPUB file for preservation."""
    metadata = {
        "dc_metadata": {},
        "opf_metadata": [],
        "cover_info": None,
        "media_files": [],
    }

    try:
        with zipfile.ZipFile(epub_path, "r") as zf:
            # Find OPF file
            container_xml = zf.read("META-INF/container.xml")
            container_root = ET.fromstring(container_xml)
            ns_container = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
            rootfiles = container_root.findall(".//c:rootfile", ns_container)
            if not rootfiles:
                return metadata
            opf_path = rootfiles[0].attrib.get("full-path")
            opf_dir = str(pathlib.PurePosixPath(opf_path).parent)

            # Read OPF file
            opf_xml = zf.read(opf_path)
            opf_root = ET.fromstring(opf_xml)

            ns_opf = {
                "opf": "http://www.idpf.org/2007/opf",
                "dc": "http://purl.org/dc/elements/1.1/",
            }

            # Extract Dublin Core metadata
            for dc_elem in opf_root.findall(".//dc:*", ns_opf):
                tag_name = dc_elem.tag.split("}")[-1]  # Remove namespace
                if tag_name not in metadata["dc_metadata"]:
                    metadata["dc_metadata"][tag_name] = []
                metadata["dc_metadata"][tag_name].append(
                    {"text": dc_elem.text or "", "attributes": dict(dc_elem.attrib)}
                )

            # Extract OPF-specific metadata
            for meta_elem in opf_root.findall(".//opf:metadata/opf:meta", ns_opf):
                name = meta_elem.attrib.get(
                    "name", meta_elem.attrib.get("property", "unknown")
                )
                content = meta_elem.attrib.get("content", meta_elem.text or "")
                metadata["opf_metadata"].append(
                    {
                        "name": name,
                        "content": content,
                        "attributes": dict(meta_elem.attrib),
                    }
                )

            # Find cover and media files
            manifest_items = opf_root.findall(".//opf:manifest/opf:item", ns_opf)
            for item in manifest_items:
                item_id = item.attrib.get("id", "")
                href = item.attrib.get("href", "")
                media_type = item.attrib.get("media-type", "")
                properties = item.attrib.get("properties", "")

                # Check if it's a cover
                if (
                    "cover" in properties.lower()
                    or "cover" in item_id.lower()
                    or href.lower().startswith("cover")
                ):
                    metadata["cover_info"] = {
                        "id": item_id,
                        "href": href,
                        "media_type": media_type,
                        "properties": properties,
                    }

                # Collect media files (images, fonts, etc.)
                if media_type.startswith(("image/", "font/", "application/font")):
                    abs_path = (
                        str(pathlib.PurePosixPath(opf_dir, href))
                        if opf_dir != "."
                        else href
                    )
                    try:
                        file_data = zf.read(abs_path)
                        metadata["media_files"].append(
                            {
                                "id": item_id,
                                "href": href,
                                "media_type": media_type,
                                "data": file_data,
                            }
                        )
                    except KeyError:
                        # File not found in zip
                        pass

    except Exception as e:
        print(f"Warning: Could not extract metadata from {epub_path}: {e}")

    return metadata


def extract_images_from_epub(epub_path: str) -> dict:
    """Extract all image files from an EPUB.

    Returns a dict mapping image filename to (media_type, data).
    """
    images = {}
    try:
        with zipfile.ZipFile(epub_path, "r") as zf:
            for name in zf.namelist():
                lower = name.lower()
                if any(
                    lower.endswith(ext)
                    for ext in (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp")
                ):
                    data = zf.read(name)
                    # Use just the filename part
                    fname = pathlib.PurePosixPath(name).name
                    ext = pathlib.PurePosixPath(name).suffix.lower()
                    mt = {
                        ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg",
                        ".png": "image/png",
                        ".gif": "image/gif",
                        ".svg": "image/svg+xml",
                        ".webp": "image/webp",
                    }.get(ext, "image/jpeg")
                    images[fname] = (mt, data)
    except Exception as e:
        print(f"Warning: Could not extract images from {epub_path}: {e}")
    return images


def extract_css_from_epub(epub_path: str) -> List[Tuple[str, bytes]]:
    """Return [(basename, css_bytes), ...] for every stylesheet in the EPUB."""
    sheets = []
    try:
        with zipfile.ZipFile(epub_path, "r") as zf:
            for name in zf.namelist():
                if name.lower().endswith(".css"):
                    sheets.append((pathlib.PurePosixPath(name).name, zf.read(name)))
    except Exception as e:
        print(f"Warning: Could not extract CSS from {epub_path}: {e}")
    return sheets


def extract_fonts_from_epub(epub_path: str) -> List[Tuple[str, str, bytes]]:
    """Return [(basename, media_type, data), ...] for embedded font files."""
    font_types = {
        ".ttf": "font/ttf",
        ".otf": "font/otf",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
    }
    fonts = []
    try:
        with zipfile.ZipFile(epub_path, "r") as zf:
            for name in zf.namelist():
                ext = pathlib.PurePosixPath(name).suffix.lower()
                if ext in font_types:
                    fonts.append(
                        (pathlib.PurePosixPath(name).name, font_types[ext], zf.read(name))
                    )
    except Exception as e:
        print(f"Warning: Could not extract fonts from {epub_path}: {e}")
    return fonts


def _rewrite_css_urls(css_text: str) -> str:
    """Point CSS url(...) references at the merged EPUB's flat images/fonts dirs."""
    font_exts = (".ttf", ".otf", ".woff", ".woff2")

    def repl(m: "re.Match") -> str:
        raw = m.group(1).strip().strip("'\"")
        if raw.startswith("data:"):
            return m.group(0)
        basename = pathlib.PurePosixPath(raw).name
        folder = "fonts" if basename.lower().endswith(font_exts) else "images"
        return f'url("{folder}/{basename}")'

    return re.sub(r"url\(([^)]+)\)", repl, css_text)


def _body_inner_html(xhtml: str) -> str:
    """Return the serialized inner contents of <body> from a full XHTML doc."""
    soup = BeautifulSoup(xhtml, "xml")
    body = soup.find("body")
    if body is None:
        return xhtml
    return "".join(str(c) for c in body.contents)


def _title_page_body(src_book: Book, tgt_book: Book, cover_strategy: str) -> str:
    """Build a half-and-half title page combining both books' title/author.

    Mirrors render/cover.py's split conventions: "diagonal" stacks target on
    top of source (upper/lower), "side_by_side" places target left of source.
    """

    def half(book: Book, css_class: str) -> str:
        authors = ", ".join(book.authors) if book.authors else ""
        author_html = f'<div class="tp-author">{escape(authors)}</div>' if authors else ""
        return (
            f'<div class="tp-half {css_class}">'
            f'<div class="tp-title">{escape(book.title)}</div>'
            f"{author_html}"
            f"</div>"
        )

    tgt_half = half(tgt_book, "tp-tgt")
    src_half = half(src_book, "tp-src")

    if cover_strategy == "side_by_side":
        return f'<div class="tp-page tp-row">{tgt_half}{src_half}</div>'
    return f'<div class="tp-page tp-col">{tgt_half}<hr class="tp-divider"/>{src_half}</div>'


def _rewrite_image_paths(html: str) -> str:
    """Point img/image src|href at the merged EPUB's flat images/ dir.

    Source EPUBs keep images relative to their own chapter files (e.g.
    "rsrc6HS.jpg"), but embed_images() above places every image under
    "images/<basename>" in the merged output, so references must be rewritten.
    """
    soup = BeautifulSoup(html, "xml")
    for el in soup.find_all(["img", "image"]):
        for attr in ("src", "href", "{http://www.w3.org/1999/xlink}href", "xlink:href"):
            if el.has_attr(attr):
                basename = pathlib.PurePosixPath(el[attr]).name
                el[attr] = f"images/{basename}"
    return str(soup)


def build_merged_epub(
    src_book: Book,
    tgt_book: Book,
    per_chapter_units: List[List[AlignmentUnit]],
    out_path: str,
    tgt_epub_path: Optional[str] = None,
    src_epub_path: Optional[str] = None,
    cover_strategy: str = "diagonal",
    chapter_titles: Optional[List[str]] = None,
    src_front_chapters: Optional[List[Chapter]] = None,
    src_back_chapters: Optional[List[Chapter]] = None,
) -> None:
    """Build merged EPUB matching the source book's own formatting.

    Layout:
      cover -> src_front_chapters (verbatim) -> aligned body chapters
            -> src_back_chapters (verbatim)

    Aligned pairs render as:
      source paragraph (original formatting)
      target paragraph (italics, smaller font, tight spacing)

    Front/back matter chapters are emitted verbatim (source-only, untranslated)
    using the source EPUB's own stylesheets so the whole book keeps its
    original typography — only the cover and the inline translation are new.

    Args:
        src_book: Source language book
        tgt_book: Target language book
        per_chapter_units: Aligned chapter units
        out_path: Output path for merged EPUB
        tgt_epub_path: Path to target EPUB file to extract metadata from
        src_epub_path: Path to source EPUB file for cover extraction
        cover_strategy: Cover generation strategy ("diagonal", "side_by_side")
        chapter_titles: Optional list of chapter titles for the merged output
        src_front_chapters: Source-language front matter, rendered verbatim
        src_back_chapters: Source-language back matter, rendered verbatim
    """
    out = epub.EpubBook()

    # Extract rich metadata from target EPUB if available
    tgt_metadata = {}
    if tgt_epub_path:
        tgt_metadata = extract_epub_metadata(tgt_epub_path)

    # Extract metadata from source EPUB for cover generation
    src_metadata = {}
    if src_epub_path:
        src_metadata = extract_epub_metadata(src_epub_path)

    # Set basic properties, preferring target book metadata
    if tgt_metadata.get("dc_metadata", {}).get("language"):
        lang = tgt_metadata["dc_metadata"]["language"][0]["text"]
    else:
        lang = tgt_book.language or src_book.language or "und"
    out.set_language(lang)

    # Create parallel edition title
    if tgt_metadata.get("dc_metadata", {}).get("title"):
        base_title = tgt_metadata["dc_metadata"]["title"][0]["text"]
    else:
        base_title = tgt_book.title or src_book.title
    out.set_title(f"{base_title} — ParallelText Edition")

    # Add all Dublin Core metadata from target EPUB
    if tgt_metadata.get("dc_metadata"):
        for tag, entries in tgt_metadata["dc_metadata"].items():
            if tag in ("title", "language"):  # Already handled above
                continue
            for entry in entries:
                if tag == "creator":
                    out.add_author(entry["text"])
                elif tag == "contributor":
                    out.add_author(entry["text"], role="contributor")
                # Note: ebooklib has limited metadata support, so we'll add the rest in OPF

    # Generate combined cover using modular cover generation
    src_cover_data = None
    tgt_cover_data = None

    # Extract cover data from source EPUB using metadata first, then fallback
    if src_metadata.get("media_files"):
        for media_file in src_metadata["media_files"]:
            if (
                src_metadata.get("cover_info")
                and media_file["id"] == src_metadata["cover_info"]["id"]
            ):
                src_cover_data = media_file["data"]
                break

    # Fallback: use robust cover extraction if metadata method failed
    if not src_cover_data:
        from .cover import extract_cover_from_epub

        src_cover_data = extract_cover_from_epub(src_epub_path)

    # Extract cover data from target EPUB using metadata first, then fallback
    if tgt_metadata.get("media_files"):
        for media_file in tgt_metadata["media_files"]:
            if (
                tgt_metadata.get("cover_info")
                and media_file["id"] == tgt_metadata["cover_info"]["id"]
            ):
                tgt_cover_data = media_file["data"]
                break

    # Fallback: use robust cover extraction if metadata method failed
    if not tgt_cover_data:
        from .cover import extract_cover_from_epub

        tgt_cover_data = extract_cover_from_epub(tgt_epub_path)

    # Generate combined cover if we have at least one cover image
    if src_cover_data or tgt_cover_data:
        try:
            combined_cover_data = generate_combined_cover(
                src_cover_data, tgt_cover_data, strategy=cover_strategy
            )

            # set_cover() adds its own EpubCover item internally
            out.set_cover("images/combined_cover.jpg", combined_cover_data)

        except Exception as e:
            print(f"Warning: Could not generate combined cover: {e}")
            # Fallback to original target cover if available
            if tgt_cover_data:
                out.set_cover("images/cover.jpg", tgt_cover_data)

    # Extract and embed images from source EPUB for inline images
    embedded_images = set()
    if src_epub_path:
        src_images = extract_images_from_epub(src_epub_path)
        for fname, (media_type, data) in src_images.items():
            if fname.lower().startswith("cover"):
                continue  # skip cover images, already handled
            img_item = epub.EpubItem(
                uid=f"img_{fname.replace('.', '_')}",
                file_name=f"images/{fname}",
                media_type=media_type,
                content=data,
            )
            out.add_item(img_item)
            embedded_images.add(fname)

    # Embed the source EPUB's own stylesheets + fonts so every page (front
    # matter, aligned body, back matter) keeps the original book's typography.
    src_css_links: List[str] = []
    if src_epub_path:
        for fname, media_type, data in extract_fonts_from_epub(src_epub_path):
            out.add_item(
                epub.EpubItem(
                    uid=f"font_{fname.replace('.', '_')}",
                    file_name=f"fonts/{fname}",
                    media_type=media_type,
                    content=data,
                )
            )
        for fname, data in extract_css_from_epub(src_epub_path):
            text = _rewrite_css_urls(data.decode("utf-8", errors="ignore"))
            out.add_item(
                epub.EpubItem(
                    uid=f"srccss_{fname.replace('.', '_')}",
                    file_name=f"style/{fname}",
                    media_type="text/css",
                    content=text.encode("utf-8"),
                )
            )
            src_css_links.append(f"style/{fname}")

    # Overlay CSS: only styles the translation layer (spacing + italics).
    # Loaded after the source stylesheets so it wins on the .pt-* classes,
    # everything else keeps the source book's own formatting untouched.
    css = epub.EpubItem(
        uid="style",
        file_name="style/parallel.css",
        media_type="text/css",
        content=b"""
.pt-chapter {
    padding: 1em 0.8em;
}
.pt-meta {
    font-size: 0.85em;
    color: #666;
    margin: 0 0 1.5em 0;
    text-align: center;
}
.pt-src {
    margin: 0;
}
.pt-tgt {
    font-style: italic;
    font-size: 0.9em;
    color: #555;
    margin: 0 0 0.9em 0;
}
.pt-image {
    margin: 1em 0;
    text-align: center;
}
.pt-image img {
    max-width: 100%;
    height: auto;
}
.tp-page {
    padding: 2em 1em;
    min-height: 90vh;
}
.tp-col {
    display: flex;
    flex-direction: column;
}
.tp-row {
    display: flex;
    flex-direction: row;
}
.tp-half {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    padding: 1.5em;
}
.tp-title {
    font-size: 1.6em;
    font-weight: bold;
    margin-bottom: 0.4em;
}
.tp-author {
    font-size: 1em;
    color: #555;
}
.tp-divider {
    border: none;
    border-top: 1px solid #ccc;
    margin: 1.5em 0;
    width: 100%;
}
""",
    )
    out.add_item(css)

    # ebooklib's EpubHtml.get_content() regenerates <head> from item.links —
    # any <link> embedded in the raw content string is discarded, so links
    # must be registered via add_link() on each item instead.
    css_links = src_css_links + ["style/parallel.css"]

    def _link_css(item: "epub.EpubHtml") -> None:
        for href in css_links:
            item.add_link(href=href, rel="stylesheet", type="text/css")

    spine = ["nav"]

    # Half-and-half title page combining both books' title/author
    title_item = epub.EpubHtml(title="Title Page", file_name="title.xhtml")
    _link_css(title_item)
    title_item.set_content(
        f"<html><body>{_title_page_body(src_book, tgt_book, cover_strategy)}</body></html>".encode("utf-8")
    )
    out.add_item(title_item)
    spine.append(title_item)

    def _passthrough_chapters(chapters: Optional[List[Chapter]], prefix: str) -> None:
        """Emit source-language chapters verbatim (no translation, no pt-* wrapper)."""
        if not chapters:
            return
        for i, ch in enumerate(chapters, start=1):
            body_inner = _rewrite_image_paths(_body_inner_html(ch.html))
            item = epub.EpubHtml(
                title=ch.title or f"{prefix} {i}",
                file_name=f"{prefix}_{i:03}.xhtml",
            )
            _link_css(item)
            item.set_content(f"<html><body>{body_inner}</body></html>".encode("utf-8"))
            out.add_item(item)
            spine.append(item)

    # Front matter — verbatim, source language, in original order
    _passthrough_chapters(src_front_chapters, "front")

    src_lang = src_book.language or "und"
    tgt_lang = tgt_book.language or "und"

    for i, units in enumerate(per_chapter_units, start=1):
        ch_title = (
            chapter_titles[i - 1]
            if chapter_titles and i - 1 < len(chapter_titles)
            else f"Chapter {i}"
        )
        item = epub.EpubHtml(
            title=ch_title,
            file_name=f"chap_{i:03}.xhtml",
        )
        _link_css(item)

        html = [
            "<html><body>",
            f'<div class="pt-chapter">',
            f'<div class="pt-meta">{escape(ch_title)}</div>',
        ]

        for unit in units:
            # Emit images that belong before this aligned pair
            for img_html in unit.images_before:
                html.append(f'<div class="pt-image">{_rewrite_image_paths(img_html)}</div>')

            # Skip empty trailing units (image-only)
            if not unit.src_html and not unit.tgt_html:
                continue

            # Source paragraph — original formatting
            if unit.src_html:
                html.append(
                    f'<div class="pt-src" lang="{src_lang}">{unit.src_html}</div>'
                )
            # Target paragraph — italics, smaller
            if unit.tgt_html:
                html.append(
                    f'<div class="pt-tgt" lang="{tgt_lang}">{unit.tgt_html}</div>'
                )

        html.append("</div></body></html>")
        item.set_content("".join(html).encode("utf-8"))
        out.add_item(item)
        spine.append(item)

    # Back matter — verbatim, source language, in original order
    _passthrough_chapters(src_back_chapters, "back")

    out.spine = spine
    out.toc = tuple(spine[1:])  # skip cover/title if you add one earlier
    out.add_item(epub.EpubNcx())
    out.add_item(epub.EpubNav())

    epub.write_epub(out_path, out)
