"""Tests for sentence-level alignment algorithms."""

from paralleltext.align.sentence import align_sentences_one_to_one
from paralleltext.types import AlignmentUnit


class TestSentenceAlignment:
    """Test sentence-level alignment algorithms."""

    def test_align_equal_length_sentence_lists(self):
        """Test alignment with equal length sentence lists."""
        src_sentences = [
            "<p>Source sentence 1.</p>",
            "<p>Source sentence 2.</p>",
            "<p>Source sentence 3.</p>",
        ]
        tgt_sentences = [
            "<p>Target sentence 1.</p>",
            "<p>Target sentence 2.</p>",
            "<p>Target sentence 3.</p>",
        ]

        units = align_sentences_one_to_one(src_sentences, tgt_sentences)

        assert len(units) == 3
        assert all(isinstance(unit, AlignmentUnit) for unit in units)

        assert units[0].src_html == "<p>Source sentence 1.</p>"
        assert units[0].tgt_html == "<p>Target sentence 1.</p>"
        assert units[1].src_html == "<p>Source sentence 2.</p>"
        assert units[1].tgt_html == "<p>Target sentence 2.</p>"
        assert units[2].src_html == "<p>Source sentence 3.</p>"
        assert units[2].tgt_html == "<p>Target sentence 3.</p>"

    def test_align_src_longer_than_tgt_sentences(self):
        """Test alignment when source has more sentences than target."""
        src_sentences = [
            "<p>Source sentence 1.</p>",
            "<p>Source sentence 2.</p>",
            "<p>Source sentence 3.</p>",
            "<p>Source sentence 4.</p>",
        ]
        tgt_sentences = ["<p>Target sentence 1.</p>", "<p>Target sentence 2.</p>"]

        units = align_sentences_one_to_one(src_sentences, tgt_sentences)

        # Should truncate to shortest (target)
        assert len(units) == 2
        assert units[0].src_html == "<p>Source sentence 1.</p>"
        assert units[0].tgt_html == "<p>Target sentence 1.</p>"
        assert units[1].src_html == "<p>Source sentence 2.</p>"
        assert units[1].tgt_html == "<p>Target sentence 2.</p>"

    def test_align_tgt_longer_than_src_sentences(self):
        """Test alignment when target has more sentences than source."""
        src_sentences = ["<p>Source sentence 1.</p>", "<p>Source sentence 2.</p>"]
        tgt_sentences = [
            "<p>Target sentence 1.</p>",
            "<p>Target sentence 2.</p>",
            "<p>Target sentence 3.</p>",
            "<p>Target sentence 4.</p>",
        ]

        units = align_sentences_one_to_one(src_sentences, tgt_sentences)

        # Should truncate to shortest (source)
        assert len(units) == 2
        assert units[0].src_html == "<p>Source sentence 1.</p>"
        assert units[0].tgt_html == "<p>Target sentence 1.</p>"
        assert units[1].src_html == "<p>Source sentence 2.</p>"
        assert units[1].tgt_html == "<p>Target sentence 2.</p>"

    def test_align_empty_sentence_lists(self):
        """Test alignment with empty sentence lists."""
        src_sentences = []
        tgt_sentences = []

        units = align_sentences_one_to_one(src_sentences, tgt_sentences)
        assert len(units) == 0
        assert isinstance(units, list)

    def test_align_one_empty_sentence_list(self):
        """Test alignment when one sentence list is empty."""
        src_sentences = ["<p>Source sentence 1.</p>", "<p>Source sentence 2.</p>"]
        tgt_sentences = []

        units = align_sentences_one_to_one(src_sentences, tgt_sentences)
        assert len(units) == 0

        # Test reverse
        src_sentences = []
        tgt_sentences = ["<p>Target sentence 1.</p>", "<p>Target sentence 2.</p>"]

        units = align_sentences_one_to_one(src_sentences, tgt_sentences)
        assert len(units) == 0

    def test_align_single_sentences(self):
        """Test alignment with single sentences."""
        src_sentences = ["<p>Only source sentence.</p>"]
        tgt_sentences = ["<p>Only target sentence.</p>"]

        units = align_sentences_one_to_one(src_sentences, tgt_sentences)

        assert len(units) == 1
        assert units[0].src_html == "<p>Only source sentence.</p>"
        assert units[0].tgt_html == "<p>Only target sentence.</p>"

    def test_align_preserves_sentence_html_content(self):
        """Test that alignment preserves sentence HTML content exactly."""
        src_sentences = [
            "<p>Source with <em>emphasis</em> and <strong>bold</strong>.</p>"
        ]
        tgt_sentences = ['<p>Target with <a href="link">link</a> text.</p>']

        units = align_sentences_one_to_one(src_sentences, tgt_sentences)

        assert len(units) == 1
        assert "<em>emphasis</em>" in units[0].src_html
        assert "<strong>bold</strong>" in units[0].src_html
        assert '<a href="link">link</a>' in units[0].tgt_html

    def test_alignment_unit_structure_sentences(self):
        """Test that AlignmentUnit has correct structure for sentences."""
        src_sentences = ["<p>Source sentence.</p>"]
        tgt_sentences = ["<p>Target sentence.</p>"]

        units = align_sentences_one_to_one(src_sentences, tgt_sentences)
        unit = units[0]

        assert hasattr(unit, "src_html")
        assert hasattr(unit, "tgt_html")
        assert isinstance(unit.src_html, str)
        assert isinstance(unit.tgt_html, str)
