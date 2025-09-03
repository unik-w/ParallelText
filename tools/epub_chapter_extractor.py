import zipfile, pathlib, re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class Chapter:
    index: int
    href: str
    title: str
    bytes: bytes
    text_preview: str


class EpubSpineExtractor:
    def __init__(self, epub_path: str):
        self.epub_path = epub_path
        self.zf = None
        self.opf_path = None
        self.opf_dir = None
        self.opf_xml = None
        self.manifest = {}
        self.spine_ids = []
        self.ns_container = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
        self.ns_opf = {
            "opf": "http://www.idpf.org/2007/opf",
            "dc": "http://purl.org/dc/elements/1.1/",
        }
        self.ns_xhtml = {"x": "http://www.w3.org/1999/xhtml"}

    def __enter__(self):
        self.zf = zipfile.ZipFile(self.epub_path, "r")
        self._load_package()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.zf:
            self.zf.close()

    def _load_package(self):
        # Find OPF via META-INF/container.xml
        container_xml = self._read_xml("META-INF/container.xml")
        rootfiles = container_xml.findall(".//c:rootfile", self.ns_container)
        if not rootfiles:
            raise ValueError("container.xml has no <rootfile> entries")
        self.opf_path = rootfiles[0].attrib.get("full-path")
        self.opf_dir = str(pathlib.PurePosixPath(self.opf_path).parent)
        self.opf_xml = self._read_xml(self.opf_path)
        # Build manifest map
        for item in self.opf_xml.findall(".//opf:manifest/opf:item", self.ns_opf):
            self.manifest[item.attrib["id"]] = {
                "href": item.attrib["href"],
                "media-type": item.attrib.get("media-type", ""),
                "properties": item.attrib.get("properties", ""),
            }
        # Spine order
        self.spine_ids = [
            el.attrib["idref"]
            for el in self.opf_xml.findall(".//opf:spine/opf:itemref", self.ns_opf)
        ]
        if not self.spine_ids:
            raise ValueError("No spine itemrefs found in OPF")

    def _read_xml(self, path: str) -> ET.Element:
        with self.zf.open(path) as f:
            data = f.read()
        return ET.fromstring(data)

    def _abs(self, rel: str) -> str:
        return (
            str(pathlib.PurePosixPath(self.opf_dir, rel))
            if self.opf_dir != "."
            else rel
        )

    def _read_bytes(self, path: str) -> bytes:
        with self.zf.open(path) as f:
            return f.read()

    # Front-matter that should not be counted as a chapter
    FRONT_MATTER_HINTS = re.compile(
        r"(inhaltsverzeichnis|contents|toc|cover|titlepage|titelseite|impressum|copyright|colophon|dedication"
        r"|project\s+gutenberg|ebook\b|^.*-h-0\.htm(?:\.xhtml)?$)",
        re.I,
    )

    # Back-matter that should not be counted as a chapter
    BACK_MATTER_HINTS = re.compile(
        r"(the\s+full\s+project\s+gutenberg\s+license|nachwort\b|end\s+of\s+the\s+project\s+gutenberg\s+ebook)",
        re.I,
    )

    def _is_front_matter(self, href: str, properties: str, media_type: str) -> bool:
        if "nav" in (properties or ""):
            return True
        if media_type in ("application/x-dtbncx+xml",):
            return True
        if self.FRONT_MATTER_HINTS.search(href or ""):
            return True
        return False

    def _extract_title_from_xhtml(self, xml_bytes: bytes) -> Optional[str]:
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError:
            return None
        # h1, h2, title
        for tag in [
            ".//{http://www.w3.org/1999/xhtml}h1",
            ".//{http://www.w3.org/1999/xhtml}h2",
            ".//{http://www.w3.org/1999/xhtml}title",
        ]:
            el = root.find(tag)
            if el is not None and (el.text or "").strip():
                return re.sub(r"\s+", " ", el.text.strip())
        # try first strong/p
        for tag in [
            ".//{http://www.w3.org/1999/xhtml}strong",
            ".//{http://www.w3.org/1999/xhtml}p",
        ]:
            el = root.find(tag)
            if el is not None:
                txt = "".join(el.itertext() or [])
                if txt and txt.strip():
                    return re.sub(r"\s+", " ", txt.strip())[:120]
        return None

    def _strip_tags(self, html: str) -> str:
        return re.sub(r"<[^>]+>", "", html)

    def extract_chapters(self, min_chars: int = 400) -> List[Chapter]:
        chapters: List[Chapter] = []
        for idx, idref in enumerate(self.spine_ids):
            meta = self.manifest.get(idref, {})
            href = meta.get("href")
            media_type = meta.get("media-type", "")
            properties = meta.get("properties", "")
            if not href:
                continue
            absp = self._abs(href)
            # Only text-like
            if media_type not in (
                "application/xhtml+xml",
                "text/html",
                "application/xml",
                "",
            ):
                continue
            # Skip front matter
            if self._is_front_matter(href, properties, media_type):
                continue
            try:
                data = self._read_bytes(absp)
            except KeyError:
                continue
            # crude text length
            try:
                html = data.decode("utf-8", errors="ignore")
            except Exception:
                html = ""
            plain = self._strip_tags(html).strip()
            # Skip common back-matter (license, Nachwort, explicit Gutenberg markers)
            if self.BACK_MATTER_HINTS.search(plain[:4096]):
                continue
            # Extra guard: Gutenberg title page often has the phrase below and sits at spine index 0
            if idx == 0 and re.search(r"\bproject\s+gutenberg\b", plain, re.I):
                continue
            if len(plain) < min_chars:
                # likely a bridge/image/tiny page
                continue
            title = self._extract_title_from_xhtml(data) or pathlib.Path(href).stem
            preview = re.sub(r"\s+", " ", plain[:180])
            chapters.append(
                Chapter(
                    index=0, href=href, title=title, bytes=data, text_preview=preview
                )
            )
        # Re-number indexes after filtering to avoid gaps and make "first N" robust
        for i, ch in enumerate(chapters):
            ch.index = i
        return chapters


# Convenience function
def extract_chapters(epub_path: str, min_chars: int = 400):
    with EpubSpineExtractor(epub_path) as ex:
        return ex.extract_chapters(min_chars=min_chars)
