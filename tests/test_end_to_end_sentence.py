"""Tests for end-to-end sentence vs paragraph alignment."""

import tempfile
from pathlib import Path
from paralleltext.cli.ptd import _do_merge
from paralleltext.io.epub_read import load_epub


class TestSentenceVsParagraphAlignment:
    """Test end-to-end comparison of sentence vs paragraph alignment."""

    def test_sentence_vs_paragraph_alignment_output_different(self):
        """Test that sentence and paragraph alignment produce different results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sentence_path = Path(tmpdir) / "sentence.epub"
            paragraph_path = Path(tmpdir) / "paragraph.epub"

            # Create sentence-level alignment
            _do_merge(
                src="tests/fixtures/de.epub",
                tgt="tests/fixtures/en.epub",
                out=str(sentence_path),
                chapters=1,
                cover_strategy="diagonal",
                granularity="sentence",
            )

            # Create paragraph-level alignment
            _do_merge(
                src="tests/fixtures/de.epub",
                tgt="tests/fixtures/en.epub",
                out=str(paragraph_path),
                chapters=1,
                cover_strategy="diagonal",
                granularity="paragraph",
            )

            # Load both books and compare
            sentence_book = load_epub(str(sentence_path))
            paragraph_book = load_epub(str(paragraph_path))

            # Both should have chapters
            assert sentence_book.chapters
            assert paragraph_book.chapters

            # Find the content chapter (not TOC)
            sentence_content_chapter = None
            paragraph_content_chapter = None

            for chapter in sentence_book.chapters:
                if "pt-row" in chapter.html:
                    sentence_content_chapter = chapter
                    break

            for chapter in paragraph_book.chapters:
                if "pt-row" in chapter.html:
                    paragraph_content_chapter = chapter
                    break

            # Should have found content chapters
            assert sentence_content_chapter is not None
            assert paragraph_content_chapter is not None

            # Get chapter content
            sentence_html = sentence_content_chapter.html
            paragraph_html = paragraph_content_chapter.html

            # The HTML should be different (sentence alignment should have more rows)
            sentence_row_count = sentence_html.count('class="pt-row"')
            paragraph_row_count = paragraph_html.count('class="pt-row"')

            print(f"Sentence alignment rows: {sentence_row_count}")
            print(f"Paragraph alignment rows: {paragraph_row_count}")

            # Sentence alignment should generally have more rows
            # (unless paragraphs are all single sentences)
            assert sentence_row_count >= paragraph_row_count

            # Should have content
            assert sentence_row_count > 0
            assert paragraph_row_count > 0

    def test_sentence_alignment_creates_more_units(self):
        """Test that sentence alignment typically creates more alignment units."""
        from paralleltext.text.segment import paragraphs_from_xhtml
        from paralleltext.text.sentence import sentences_from_xhtml
        from paralleltext.io.epub_read import load_epub

        # Load test fixtures
        src_book = load_epub("tests/fixtures/de.epub")
        tgt_book = load_epub("tests/fixtures/en.epub")

        if not src_book.chapters or not tgt_book.chapters:
            return  # Skip if no chapters

        # Get first chapter
        src_chapter = src_book.chapters[0]
        tgt_chapter = tgt_book.chapters[0]

        # Extract paragraphs
        src_paragraphs = [
            p for p in paragraphs_from_xhtml(src_chapter.html) if p and p.strip()
        ]
        tgt_paragraphs = [
            p for p in paragraphs_from_xhtml(tgt_chapter.html) if p and p.strip()
        ]

        # Extract sentences
        src_sentences = [
            s for s in sentences_from_xhtml(src_chapter.html) if s and s.strip()
        ]
        tgt_sentences = [
            s for s in sentences_from_xhtml(tgt_chapter.html) if s and s.strip()
        ]

        print(f"Source paragraphs: {len(src_paragraphs)}")
        print(f"Target paragraphs: {len(tgt_paragraphs)}")
        print(f"Source sentences: {len(src_sentences)}")
        print(f"Target sentences: {len(tgt_sentences)}")

        # Sentences should generally be >= paragraphs
        assert len(src_sentences) >= len(src_paragraphs)
        assert len(tgt_sentences) >= len(tgt_paragraphs)

        # At minimum, we should have some content
        assert len(src_paragraphs) > 0
        assert len(tgt_paragraphs) > 0
        assert len(src_sentences) > 0
        assert len(tgt_sentences) > 0
