# test_epub_inspect.py
from epub_chapter_extractor import EpubSpineExtractor
from pathlib import Path


def test_epub(epub_path: str, max_preview: int = 120):
    with EpubSpineExtractor(epub_path) as ex:
        print("== EPUB Metadata ==")
        title = ex.opf_xml.find(".//dc:title", ex.ns_opf)
        lang = ex.opf_xml.find(".//dc:language", ex.ns_opf)
        print("Title:", title.text if title is not None else "N/A")
        print("Language:", lang.text if lang is not None else "N/A")
        print(f"Spine length: {len(ex.spine_ids)} items")

        print("\n== Chapters ==")
        chapters = ex.extract_chapters(min_chars=400)
        for ch in chapters:
            print(f"[{ch.index}] {ch.title} ({ch.href})")
            print("   Preview:", ch.text_preview[:max_preview].replace("\n", " "))
            print()


if __name__ == "__main__":
    # Example usage:
    test_epub(Path("../langpub/tests/data/Der_Prozess_full.epub").resolve().__str__())
    # test_epub(Path("../langpub/tests/data/The_Trial_full.epub").resolve().__str__())
