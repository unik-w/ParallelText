"""Tests for EPUB I/O operations."""

import pytest
from pathlib import Path
from paralleltext.io.epub_read import load_epub, EXCLUDE_HINTS
from paralleltext.types import Book, Chapter


class TestEpubRead:
    """Test EPUB reading functionality."""

    @pytest.fixture
    def test_data_dir(self):
        """Return path to test data directory."""
        return Path(__file__).parent / "fixtures"

    @pytest.fixture
    def german_epub(self, test_data_dir):
        """Path to German test EPUB."""
        return test_data_dir / "de.epub"

    @pytest.fixture
    def english_epub(self, test_data_dir):
        """Path to English test EPUB."""
        return test_data_dir / "en.epub"

    def test_load_epub_returns_book(self, german_epub):
        """Test that load_epub returns a Book object."""
        book = load_epub(str(german_epub))
        assert isinstance(book, Book)

    def test_book_has_required_attributes(self, german_epub):
        """Test that loaded book has all required attributes."""
        book = load_epub(str(german_epub))

        assert hasattr(book, "language")
        assert hasattr(book, "title")
        assert hasattr(book, "authors")
        assert hasattr(book, "chapters")

        assert isinstance(book.language, str)
        assert isinstance(book.title, str)
        assert isinstance(book.authors, list)
        assert isinstance(book.chapters, list)

    def test_german_book_properties(self, german_epub):
        """Test German book has expected properties."""
        book = load_epub(str(german_epub))

        # Should have German language
        assert book.language == "de" or book.language == "und"

        # Should have non-empty title
        assert len(book.title) > 0

        # Should have chapters
        assert len(book.chapters) > 0

    def test_english_book_properties(self, english_epub):
        """Test English book has expected properties."""
        book = load_epub(str(english_epub))

        # Should have English language
        assert book.language == "en" or book.language == "und"

        # Should have non-empty title
        assert len(book.title) > 0

        # Should have chapters
        assert len(book.chapters) > 0

    def test_chapters_have_required_attributes(self, german_epub):
        """Test that chapters have required attributes."""
        book = load_epub(str(german_epub))

        for chapter in book.chapters:
            assert isinstance(chapter, Chapter)
            assert hasattr(chapter, "title")
            assert hasattr(chapter, "html")
            assert isinstance(chapter.title, str)
            assert isinstance(chapter.html, str)
            assert len(chapter.html) > 0

    def test_exclude_hints_filter_chapters(self, german_epub):
        """Test that chapters with excluded hints are filtered out."""
        book = load_epub(str(german_epub))

        # Check that no chapter titles contain excluded hints
        for chapter in book.chapters:
            title_lower = chapter.title.lower()
            for hint in EXCLUDE_HINTS:
                assert (
                    hint not in title_lower
                ), f"Chapter '{chapter.title}' contains excluded hint '{hint}'"

    def test_chapters_contain_html_content(self, german_epub):
        """Test that chapters contain valid HTML content."""
        book = load_epub(str(german_epub))

        for chapter in book.chapters:
            # Should contain some HTML tags
            assert "<" in chapter.html and ">" in chapter.html

            # Should not be just whitespace
            assert chapter.html.strip()

    def test_load_nonexistent_file_raises_error(self):
        """Test that loading non-existent file raises appropriate error."""
        with pytest.raises((FileNotFoundError, OSError)):
            load_epub("nonexistent.epub")

    def test_both_test_epubs_loadable(self, german_epub, english_epub):
        """Test that both test EPUBs can be loaded successfully."""
        german_book = load_epub(str(german_epub))
        english_book = load_epub(str(english_epub))

        # Both should have chapters
        assert len(german_book.chapters) > 0
        assert len(english_book.chapters) > 0

        # Should have reasonable chapter counts (not too many, not too few)
        assert 1 <= len(german_book.chapters) <= 50
        assert 1 <= len(english_book.chapters) <= 50
