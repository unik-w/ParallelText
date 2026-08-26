"""Tests for cross-EPUB chapter matching."""

import pytest
from paralleltext.types import Chapter
from paralleltext.align.chapter_match import match_chapters, _title_similarity


class TestTitleSimilarity:
    def test_identical_titles(self):
        assert _title_similarity("Chapter 1", "Chapter 1") == 1.0

    def test_translated_titles_with_numbers(self):
        """Titles with chapter numbers stripped should match better."""
        # After cleaning, both reduce to similar content
        sim = _title_similarity("Kapitel 1: Der Anfang", "Chapter 1: The Beginning")
        # These won't have high word overlap (different languages),
        # but the function should not crash
        assert 0.0 <= sim <= 1.0

    def test_empty_titles(self):
        assert _title_similarity("", "") == 1.0

    def test_completely_different(self):
        sim = _title_similarity("Apples Oranges", "Zebras Elephants")
        assert sim == 0.0


class TestMatchChapters:
    def test_equal_chapter_counts(self):
        src = [
            Chapter(title=f"Kapitel {i}", html="<p>text</p>", spine_position=i)
            for i in range(5)
        ]
        tgt = [
            Chapter(title=f"Chapter {i}", html="<p>text</p>", spine_position=i)
            for i in range(5)
        ]
        pairs = match_chapters(src, tgt)
        matched = [(s, t) for s, t in pairs if s is not None and t is not None]
        assert len(matched) == 5

    def test_unequal_chapter_counts(self):
        src = [
            Chapter(title=f"Kapitel {i}", html="<p>text</p>", spine_position=i)
            for i in range(3)
        ]
        tgt = [
            Chapter(title=f"Chapter {i}", html="<p>text</p>", spine_position=i)
            for i in range(5)
        ]
        pairs = match_chapters(src, tgt)
        matched = [(s, t) for s, t in pairs if s is not None and t is not None]
        # Should match at least 3 (the minimum)
        assert len(matched) >= 3

    def test_empty_source(self):
        tgt = [Chapter(title="Ch 1", html="<p>text</p>", spine_position=0)]
        pairs = match_chapters([], tgt)
        assert len(pairs) == 1
        assert pairs[0][0] is None  # no source match

    def test_monotonic_ordering(self):
        """Matched pairs should maintain order."""
        src = [
            Chapter(title=f"Kapitel {i}", html="<p>text</p>", spine_position=i)
            for i in range(4)
        ]
        tgt = [
            Chapter(title=f"Chapter {i}", html="<p>text</p>", spine_position=i)
            for i in range(4)
        ]
        pairs = match_chapters(src, tgt)
        matched = [(s, t) for s, t in pairs if s is not None and t is not None]
        src_positions = [s.spine_position for s, t in matched]
        assert src_positions == sorted(src_positions)
