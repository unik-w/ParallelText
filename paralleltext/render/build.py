from ebooklib import epub
from typing import List, Optional
from ..data_types import Book, AlignmentUnit  # adjust if types live elsewhere
from html import escape
import pathlib
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


def build_merged_epub(
    src_book: Book,
    tgt_book: Book,
    per_chapter_units: List[List[AlignmentUnit]],
    out_path: str,
    tgt_epub_path: Optional[str] = None,
    src_epub_path: Optional[str] = None,
    cover_strategy: str = "diagonal",
) -> None:
    """Build merged EPUB with metadata from target (English) version.

    Args:
        src_book: Source language book
        tgt_book: Target language book
        per_chapter_units: Aligned chapter units
        out_path: Output path for merged EPUB
        tgt_epub_path: Path to target EPUB file to extract metadata from
        src_epub_path: Path to source EPUB file for cover extraction
        cover_strategy: Cover generation strategy ("diagonal", "side_by_side")
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

            # Add combined cover to EPUB
            cover_img = epub.EpubItem(
                uid="combined_cover",
                file_name="images/combined_cover.jpg",
                media_type="image/jpeg",
                content=combined_cover_data,
            )
            out.add_item(cover_img)
            out.set_cover(cover_img.file_name, combined_cover_data)

        except Exception as e:
            print(f"Warning: Could not generate combined cover: {e}")
            # Fallback to original target cover if available
            if tgt_cover_data:
                cover_img = epub.EpubItem(
                    uid="fallback_cover",
                    file_name="images/cover.jpg",
                    media_type="image/jpeg",
                    content=tgt_cover_data,
                )
                out.add_item(cover_img)
                out.set_cover(cover_img.file_name, tgt_cover_data)

    # Basic stylesheet to gray the target language and lay out two columns.
    css = epub.EpubItem(
        uid="style",
        file_name="style/parallel.css",
        media_type="text/css",
        content=b"""
html, body { margin: 0; padding: 0; font-family: serif; }
.pt-chapter { padding: 1.2rem 1rem; }
.pt-row { 
    display: grid; 
    grid-template-columns: 1fr 1fr; 
    gap: 1rem; 
    margin-bottom: 0.6rem; 
    padding: 0.4rem 0;
    border-bottom: 1px solid #f0f0f0;
}
.pt-row:last-child { border-bottom: none; }
.pt-src { 
    line-height: 1.6; 
    font-size: 1rem;
}
.pt-tgt { 
    line-height: 1.6; 
    color: #666; 
    font-size: 1rem;
    font-style: italic;
}
.pt-meta { 
    font-size: 0.9em; 
    color: #666; 
    margin: 0.5rem 0 1rem; 
    border-bottom: 2px solid #ddd;
    padding-bottom: 0.5rem;
}
/* Sentence-level specific styles */
.pt-src p, .pt-tgt p { margin: 0; }
.pt-src li, .pt-tgt li { margin: 0; }
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
