# Minimal, deterministic fixtures builder for paired EN/DE EPUBs.

from __future__ import annotations
import argparse, json, os, pathlib, sys, re, zipfile, io
from typing import List, Dict, Any

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


def _epub_content_opf(book_title: str, language: str, items: List[dict]) -> bytes:
    # items: [{"id":"c01","href":"Text/01.xhtml","media":"application/xhtml+xml"}], first id 'nav' reserved for nav.xhtml
    manifest_xml = [
        '      <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
    ]
    for it in items:
        manifest_xml.append(
            f'      <item id="{it["id"]}" href="{it["href"]}" media-type="{it["media"]}"/>'
        )
    spine_xml = ['      <itemref idref="nav"/>'] + [
        f'      <itemref idref="{it["id"]}"/>' for it in items
    ]
    opf = f"""<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">urn:uuid:fixture-{slugify(book_title)}</dc:identifier>
    <dc:title>{book_title}</dc:title>
    <dc:language>{language or 'und'}</dc:language>
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
) -> None:
    """
    Write a minimal EPUB:
      - mimetype (stored, first)
      - META-INF/container.xml
      - OEBPS/content.opf
      - OEBPS/nav.xhtml
      - OEBPS/Text/NN.xhtml (chapters)
    chapters: [{"name":"01.xhtml","title":"..","bytes":b"..."}]
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
        # 3) OEBPS/Text/* chapters
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
        # 4) OEBPS/nav.xhtml
        zf.writestr(
            "OEBPS/nav.xhtml",
            _epub_nav_xhtml(book_title, nav_items),
            compress_type=zipfile.ZIP_DEFLATED,
        )
        # 5) OEBPS/content.opf
        zf.writestr(
            "OEBPS/content.opf",
            _epub_content_opf(book_title, language, manifest_items),
            compress_type=zipfile.ZIP_DEFLATED,
        )


def build_fixtures(
    en_epub: pathlib.Path,
    de_epub: pathlib.Path,
    out_dir: pathlib.Path,
    keep_n: int = 10,
    min_chars: int = 380,
) -> Dict[str, Any]:
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

    # Write two minimal EPUBs
    out_epub_en = out_dir / "en.epub"
    out_epub_de = out_dir / "de.epub"
    # Simple book titles for fixtures
    title_en = "Fixture EN"
    title_de = "Fixture DE"
    write_min_epub(out_epub_en, title_en, "en", en_items)
    write_min_epub(out_epub_de, title_de, "de", de_items)

    # Minimal manifest for tests (kept for convenience)
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
