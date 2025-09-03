# Minimal, deterministic fixtures builder for paired EN/DE EPUBs.

from __future__ import annotations
import argparse, json, os, pathlib, sys, re, zipfile, io
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional

# Local import (ensure epub_chapter_extractor.py is in the same folder or on PYTHONPATH)
from epub_chapter_extractor import extract_chapters, EpubSpineExtractor  # noqa: F401


def safe_mkdir(p: pathlib.Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def write_bytes(path: pathlib.Path, data: bytes) -> None:
    path.write_bytes(data)


def write_text(path: pathlib.Path, s: str) -> None:
    path.write_text(s, encoding="utf-8")


def slugify(s: str, maxlen: int = 60) -> str:
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"[^A-Za-z0-9\-_.]+", "", s)
    s = s.strip("-_.").lower()
    return s[:maxlen] or "untitled"


def extract_epub_metadata(epub_path: str) -> Dict[str, Any]:
    """Extract all metadata and media files from an EPUB."""
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


def _epub_nav_xhtml(book_title: str, items: List[dict]) -> bytes:
    # items: [{"href":"Text/01.xhtml", "title":"..."}]
    lis = "\n".join(
        [f'        <li><a href="{it["href"]}">{it["title"]}</a></li>' for it in items]
    )
    html = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en">
  <head><meta charset="utf-8" /><title>{book_title}</title></head>
  <body>
    <nav epub:type="toc" id="toc">
      <h2>{book_title}</h2>
      <ol>
{lis}
      </ol>
    </nav>
  </body>
</html>
"""
    return html.encode("utf-8")


def _epub_content_opf(
    book_title: str,
    language: str,
    items: List[dict],
    source_metadata: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Generate content.opf with preserved metadata from source EPUB."""
    # items: [{"id":"c01","href":"Text/01.xhtml","media":"application/xhtml+xml"}]
    # first id 'nav' reserved for nav.xhtml

    # Build manifest items
    manifest_xml = [
        '      <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
    ]

    # Add media files if available
    if source_metadata and source_metadata.get("media_files"):
        for media_file in source_metadata["media_files"]:
            properties_attr = ""
            if (
                source_metadata.get("cover_info")
                and media_file["id"] == source_metadata["cover_info"]["id"]
                and source_metadata["cover_info"].get("properties")
            ):
                properties_attr = (
                    f' properties="{source_metadata["cover_info"]["properties"]}"'
                )

            manifest_xml.append(
                f'      <item id="{media_file["id"]}" href="{media_file["href"]}" '
                f'media-type="{media_file["media_type"]}"{properties_attr}/>'
            )

    # Add chapter items
    for it in items:
        manifest_xml.append(
            f'      <item id="{it["id"]}" href="{it["href"]}" media-type="{it["media"]}"/>'
        )

    # Build spine
    spine_xml = ['      <itemref idref="nav"/>'] + [
        f'      <itemref idref="{it["id"]}"/>' for it in items
    ]

    # Generate metadata section
    metadata_lines = []

    if source_metadata and source_metadata.get("dc_metadata"):
        # Use preserved metadata
        dc_meta = source_metadata["dc_metadata"]

        # Handle identifier specially (required by EPUB spec)
        if "identifier" in dc_meta and dc_meta["identifier"]:
            first_id = dc_meta["identifier"][0]
            book_id = first_id.get("attributes", {}).get("id", "bookid")
            metadata_lines.append(
                f'    <dc:identifier id="{book_id}">{first_id["text"]}</dc:identifier>'
            )
        else:
            metadata_lines.append(
                f'    <dc:identifier id="bookid">urn:uuid:fixture-{slugify(book_title)}</dc:identifier>'
            )

        # Add other DC metadata
        for tag, entries in dc_meta.items():
            if tag == "identifier":  # Already handled above
                continue
            for entry in entries:
                attrs_str = " ".join(
                    [f'{k}="{v}"' for k, v in entry["attributes"].items()]
                )
                attrs_part = f" {attrs_str}" if attrs_str else ""
                metadata_lines.append(
                    f'    <dc:{tag}{attrs_part}>{entry["text"]}</dc:{tag}>'
                )

        # Add OPF metadata
        for meta_item in source_metadata.get("opf_metadata", []):
            attrs = meta_item["attributes"]
            if meta_item["content"]:
                if "property" in attrs:
                    refines_attr = (
                        f' refines="{attrs["refines"]}"' if "refines" in attrs else ""
                    )
                    scheme_attr = (
                        f' scheme="{attrs["scheme"]}"' if "scheme" in attrs else ""
                    )
                    metadata_lines.append(
                        f'    <meta property="{attrs["property"]}"{refines_attr}{scheme_attr}>'
                        f'{meta_item["content"]}</meta>'
                    )
                elif "name" in attrs:
                    metadata_lines.append(
                        f'    <meta name="{attrs["name"]}" content="{meta_item["content"]}"/>'
                    )
    else:
        # Fallback to minimal metadata
        metadata_lines = [
            f'    <dc:identifier id="bookid">urn:uuid:fixture-{slugify(book_title)}</dc:identifier>',
            f"    <dc:title>{book_title}</dc:title>",
            f'    <dc:language>{language or "und"}</dc:language>',
        ]

    opf = f"""<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
{chr(10).join(metadata_lines)}
  </metadata>
  <manifest>
{chr(10).join(manifest_xml)}
  </manifest>
  <spine>
{chr(10).join(spine_xml)}
  </spine>
</package>
"""
    return opf.encode("utf-8")


def write_min_epub(
    out_path: pathlib.Path,
    book_title: str,
    language: str,
    chapters: List[dict],
    source_metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Write a minimal EPUB with preserved metadata and media files:
      - mimetype (stored, first)
      - META-INF/container.xml
      - OEBPS/content.opf (with preserved metadata)
      - OEBPS/nav.xhtml
      - OEBPS/Text/NN.xhtml (chapters)
      - OEBPS/Images/* (cover and other media files)
    chapters: [{"name":"01.xhtml","title":"..","bytes":b"..."}]
    source_metadata: Metadata extracted from source EPUB
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w") as zf:
        # 1) mimetype must be first and uncompressed
        zf.writestr(
            "mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED
        )
        # 2) META-INF/container.xml
        container_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
        zf.writestr(
            "META-INF/container.xml", container_xml, compress_type=zipfile.ZIP_DEFLATED
        )

        # 3) Add media files if available (cover images, fonts, etc.)
        if source_metadata and source_metadata.get("media_files"):
            for media_file in source_metadata["media_files"]:
                # Put images in Images folder for organization
                if media_file["media_type"].startswith("image/"):
                    file_path = f"OEBPS/Images/{pathlib.Path(media_file['href']).name}"
                    # Update href for manifest
                    media_file["href"] = (
                        f"Images/{pathlib.Path(media_file['href']).name}"
                    )
                else:
                    file_path = f"OEBPS/{media_file['href']}"

                zf.writestr(
                    file_path, media_file["data"], compress_type=zipfile.ZIP_DEFLATED
                )

        # 4) OEBPS/Text/* chapters
        manifest_items = []
        nav_items = []
        for idx, ch in enumerate(chapters, start=1):
            id_ = f"c{idx:02d}"
            href = f"Text/{ch['name']}"
            manifest_items.append(
                {"id": id_, "href": href, "media": "application/xhtml+xml"}
            )
            nav_items.append({"href": href, "title": ch["title"]})
            zf.writestr(
                f"OEBPS/{href}", ch["bytes"], compress_type=zipfile.ZIP_DEFLATED
            )
        # 5) OEBPS/nav.xhtml
        zf.writestr(
            "OEBPS/nav.xhtml",
            _epub_nav_xhtml(book_title, nav_items),
            compress_type=zipfile.ZIP_DEFLATED,
        )
        # 6) OEBPS/content.opf (with preserved metadata)
        zf.writestr(
            "OEBPS/content.opf",
            _epub_content_opf(book_title, language, manifest_items, source_metadata),
            compress_type=zipfile.ZIP_DEFLATED,
        )


def build_fixtures(
    en_epub: pathlib.Path,
    de_epub: pathlib.Path,
    out_dir: pathlib.Path,
    keep_n: int = 10,
    min_chars: int = 380,
) -> Dict[str, Any]:
    # Extract metadata from original EPUBs
    en_metadata = extract_epub_metadata(str(en_epub))
    de_metadata = extract_epub_metadata(str(de_epub))

    # Extract ordered, filtered chapters (front/back matter skipped)
    en_ch = extract_chapters(str(en_epub), min_chars=min_chars)
    de_ch = extract_chapters(str(de_epub), min_chars=min_chars)

    if len(en_ch) < keep_n:
        raise ValueError(
            f"EN only has {len(en_ch)} substantive chapters; need at least {keep_n}."
        )
    if len(de_ch) < keep_n:
        raise ValueError(
            f"DE only has {len(de_ch)} substantive chapters; need at least {keep_n}."
        )

    en_kept = en_ch[:keep_n]
    de_kept = de_ch[:keep_n]

    # Prepare chapter payloads for EPUB
    en_items, de_items = [], []
    manifest_rows = []
    for i, (en_c, de_c) in enumerate(zip(en_kept, de_kept), start=1):
        num = f"{i:02d}"
        en_name = f"{num}.xhtml"
        de_name = f"{num}.xhtml"
        en_items.append({"name": en_name, "title": en_c.title, "bytes": en_c.bytes})
        de_items.append({"name": de_name, "title": de_c.title, "bytes": de_c.bytes})
        manifest_rows.append(
            {
                "index": i - 1,
                "en": {
                    "file": f"{num}.xhtml",
                    "title": en_c.title,
                    "src_href": en_c.href,
                    "preview": en_c.text_preview,
                },
                "de": {
                    "file": f"{num}.xhtml",
                    "title": de_c.title,
                    "src_href": de_c.href,
                    "preview": de_c.text_preview,
                },
            }
        )

    # Write two EPUBs with preserved metadata
    out_epub_en = out_dir / "en.epub"
    out_epub_de = out_dir / "de.epub"

    # Use original titles if available, otherwise fallback
    title_en = "Fixture EN"
    title_de = "Fixture DE"

    if en_metadata.get("dc_metadata", {}).get("title"):
        title_en = en_metadata["dc_metadata"]["title"][0]["text"]
    if de_metadata.get("dc_metadata", {}).get("title"):
        title_de = de_metadata["dc_metadata"]["title"][0]["text"]

    write_min_epub(out_epub_en, title_en, "en", en_items, en_metadata)
    write_min_epub(out_epub_de, title_de, "de", de_items, de_metadata)

    # Minimal manifest for tests (kept for convenience)
    # Note: Binary data from media_files is excluded from manifest
    en_metadata_for_manifest = {
        "dc_metadata": en_metadata.get("dc_metadata", {}),
        "opf_metadata": en_metadata.get("opf_metadata", []),
        "cover_info": en_metadata.get("cover_info"),
        "media_files_count": len(en_metadata.get("media_files", [])),
    }
    de_metadata_for_manifest = {
        "dc_metadata": de_metadata.get("dc_metadata", {}),
        "opf_metadata": de_metadata.get("opf_metadata", []),
        "cover_info": de_metadata.get("cover_info"),
        "media_files_count": len(de_metadata.get("media_files", [])),
    }

    manifest = {
        "source": {
            "en_epub": str(en_epub),
            "de_epub": str(de_epub),
        },
        "keep_n": keep_n,
        "min_chars": min_chars,
        "outputs": {
            "en_epub": str(out_epub_en),
            "de_epub": str(out_epub_de),
        },
        "pairs": manifest_rows,
        "metadata": {
            "en": en_metadata_for_manifest,
            "de": de_metadata_for_manifest,
        },
    }
    write_text(
        out_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2)
    )
    return manifest


def main():
    ap = argparse.ArgumentParser(description="Build minimal EN/DE fixtures from EPUBs.")
    ap.add_argument("--en", required=True, help="Path to EN EPUB")
    ap.add_argument("--de", required=True, help="Path to DE EPUB")
    ap.add_argument(
        "--out",
        required=True,
        help="Output directory for fixtures (will contain en.epub, de.epub, manifest.json)",
    )
    ap.add_argument(
        "--keep-n",
        type=int,
        default=10,
        help="Number of chapter pairs to keep (default: 10)",
    )
    ap.add_argument(
        "--min-chars",
        type=int,
        default=380,
        help="Minimum chars per XHTML to treat as a chapter (default: 380)",
    )
    args = ap.parse_args()

    en_epub = pathlib.Path(args.en).resolve()
    de_epub = pathlib.Path(args.de).resolve()
    out_dir = pathlib.Path(args.out).resolve()

    if not en_epub.exists():
        print(f"[ERROR] EN EPUB not found: {en_epub}", file=sys.stderr)
        sys.exit(2)
    if not de_epub.exists():
        print(f"[ERROR] DE EPUB not found: {de_epub}", file=sys.stderr)
        sys.exit(2)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = build_fixtures(
        en_epub, de_epub, out_dir, keep_n=args.keep_n, min_chars=args.min_chars
    )

    print(f"[OK] Wrote {len(manifest['pairs'])} chapter pairs into EPUB fixtures")
    print(f"     - EN EPUB: {manifest['outputs']['en_epub']}")
    print(f"     - DE EPUB: {manifest['outputs']['de_epub']}")
    print(f"     - Manifest: {out_dir/'manifest.json'}")


if __name__ == "__main__":
    main()
