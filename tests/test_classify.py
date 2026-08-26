"""Tests for front/back matter classification."""

import pytest
from paralleltext.types import Chapter, ChapterClass
from paralleltext.text.classify import classify_chapter, filter_book_content


def _make_chapter(title: str, html: str, spine_pos: int = 5) -> Chapter:
    return Chapter(title=title, html=html, spine_position=spine_pos)


class TestClassifyChapter:
    def test_copyright_page(self):
        ch = _make_chapter(
            "Copyright",
            "<html><body><p>© 2024 Publisher Inc. All rights reserved.</p>"
            "<p>ISBN 978-3-16-148410-0</p>"
            "<p>Published by Example Press</p></body></html>",
            spine_pos=1,
        )
        cls = classify_chapter(ch, total_chapters=20)
        assert cls in (ChapterClass.FRONT_MATTER, ChapterClass.BACK_MATTER)

    def test_impressum(self):
        ch = _make_chapter(
            "Impressum",
            "<html><body><p>Verlag: Mustermann Verlag</p>"
            "<p>Alle Rechte vorbehalten.</p>"
            "<p>ISBN 978-3-16-148410-0</p></body></html>",
            spine_pos=1,
        )
        cls = classify_chapter(ch, total_chapters=20)
        assert cls in (ChapterClass.FRONT_MATTER, ChapterClass.BACK_MATTER)

    def test_toc_navigation(self):
        ch = _make_chapter(
            "Table of Contents",
            '<html><body><nav><a href="ch1.html">Chapter 1</a>'
            '<a href="ch2.html">Chapter 2</a>'
            '<a href="ch3.html">Chapter 3</a>'
            '<a href="ch4.html">Chapter 4</a>'
            '<a href="ch5.html">Chapter 5</a>'
            '<a href="ch6.html">Chapter 6</a></nav></body></html>',
            spine_pos=0,
        )
        cls = classify_chapter(ch, total_chapters=20)
        assert cls in (ChapterClass.NAVIGATION, ChapterClass.FRONT_MATTER)

    def test_real_chapter(self):
        """A real chapter with substantive prose should be BOOK_CONTENT."""
        paras = "\n".join(
            f"<p>This is paragraph {i} of the chapter with enough text to be substantive.</p>"
            for i in range(10)
        )
        ch = _make_chapter(
            "Chapter 1: The Beginning",
            f"<html><body>{paras}</body></html>",
            spine_pos=5,
        )
        cls = classify_chapter(ch, total_chapters=20)
        assert cls == ChapterClass.BOOK_CONTENT

    def test_prose_containing_copyright_word_not_filtered(self):
        """A prose paragraph mentioning copyright should NOT be classified as boilerplate."""
        ch = _make_chapter(
            "Chapter 5",
            "<html><body>"
            "<p>The lawyer explained that the copyright for the manuscript had expired decades ago, "
            "and anyone could now publish it freely. This was an important moment in the history of publishing.</p>"
            "<p>She continued to explain the implications for the author's estate.</p>"
            "<p>Many scholars had been waiting for this day.</p>"
            "<p>The library was filled with excited researchers.</p>"
            "<p>Everyone knew this would change everything.</p>"
            "</body></html>",
            spine_pos=10,
        )
        cls = classify_chapter(ch, total_chapters=20)
        assert cls == ChapterClass.BOOK_CONTENT


class TestFilterBookContent:
    def test_filters_boilerplate_keeps_content(self):
        chapters = [
            _make_chapter("Copyright", "<html><body><p>© 2024. ISBN 978-3-16-148410-0. Published by XYZ. All rights reserved.</p></body></html>", 0),
            _make_chapter("Chapter 1", "<html><body>" + "\n".join(f"<p>Paragraph {i} with real content.</p>" for i in range(10)) + "</body></html>", 3),
            _make_chapter("Chapter 2", "<html><body>" + "\n".join(f"<p>More real content paragraph {i}.</p>" for i in range(10)) + "</body></html>", 5),
        ]
        kept = filter_book_content(chapters)
        titles = [ch.title for ch in kept]
        assert "Chapter 1" in titles
        assert "Chapter 2" in titles
