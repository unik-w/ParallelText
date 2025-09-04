"""Tests for alignment algorithms."""

import pytest
from paralleltext.align.naive import align_one_to_one
from paralleltext.types import AlignmentUnit


class TestNaiveAlignment:
    """Test naive 1:1 alignment algorithm."""

    def test_align_equal_length_lists(self):
        """Test alignment with equal length paragraph lists."""
        src_paras = ["<p>Source 1</p>", "<p>Source 2</p>", "<p>Source 3</p>"]
        tgt_paras = ["<p>Target 1</p>", "<p>Target 2</p>", "<p>Target 3</p>"]

        units = align_one_to_one(src_paras, tgt_paras)

        assert len(units) == 3
        assert all(isinstance(unit, AlignmentUnit) for unit in units)

        assert units[0].src_html == "<p>Source 1</p>"
        assert units[0].tgt_html == "<p>Target 1</p>"
        assert units[1].src_html == "<p>Source 2</p>"
        assert units[1].tgt_html == "<p>Target 2</p>"
        assert units[2].src_html == "<p>Source 3</p>"
        assert units[2].tgt_html == "<p>Target 3</p>"

    def test_align_src_longer_than_tgt(self):
        """Test alignment when source has more paragraphs than target."""
        src_paras = [
            "<p>Source 1</p>",
            "<p>Source 2</p>",
            "<p>Source 3</p>",
            "<p>Source 4</p>",
        ]
        tgt_paras = ["<p>Target 1</p>", "<p>Target 2</p>"]

        units = align_one_to_one(src_paras, tgt_paras)

        # Should truncate to shortest (target)
        assert len(units) == 2
        assert units[0].src_html == "<p>Source 1</p>"
        assert units[0].tgt_html == "<p>Target 1</p>"
        assert units[1].src_html == "<p>Source 2</p>"
        assert units[1].tgt_html == "<p>Target 2</p>"

    def test_align_tgt_longer_than_src(self):
        """Test alignment when target has more paragraphs than source."""
        src_paras = ["<p>Source 1</p>", "<p>Source 2</p>"]
        tgt_paras = [
            "<p>Target 1</p>",
            "<p>Target 2</p>",
            "<p>Target 3</p>",
            "<p>Target 4</p>",
        ]

        units = align_one_to_one(src_paras, tgt_paras)

        # Should truncate to shortest (source)
        assert len(units) == 2
        assert units[0].src_html == "<p>Source 1</p>"
        assert units[0].tgt_html == "<p>Target 1</p>"
        assert units[1].src_html == "<p>Source 2</p>"
        assert units[1].tgt_html == "<p>Target 2</p>"

    def test_align_empty_lists(self):
        """Test alignment with empty lists."""
        src_paras = []
        tgt_paras = []

        units = align_one_to_one(src_paras, tgt_paras)
        assert len(units) == 0
        assert isinstance(units, list)

    def test_align_one_empty_list(self):
        """Test alignment when one list is empty."""
        src_paras = ["<p>Source 1</p>", "<p>Source 2</p>"]
        tgt_paras = []

        units = align_one_to_one(src_paras, tgt_paras)
        assert len(units) == 0

        # Test reverse
        src_paras = []
        tgt_paras = ["<p>Target 1</p>", "<p>Target 2</p>"]

        units = align_one_to_one(src_paras, tgt_paras)
        assert len(units) == 0

    def test_align_single_paragraphs(self):
        """Test alignment with single paragraphs."""
        src_paras = ["<p>Only source paragraph</p>"]
        tgt_paras = ["<p>Only target paragraph</p>"]

        units = align_one_to_one(src_paras, tgt_paras)

        assert len(units) == 1
        assert units[0].src_html == "<p>Only source paragraph</p>"
        assert units[0].tgt_html == "<p>Only target paragraph</p>"

    def test_align_preserves_html_content(self):
        """Test that alignment preserves HTML content exactly."""
        src_paras = ["<p>Source with <em>emphasis</em> and <strong>bold</strong>.</p>"]
        tgt_paras = ['<p>Target with <a href="link">link</a> text.</p>']

        units = align_one_to_one(src_paras, tgt_paras)

        assert len(units) == 1
        assert "<em>emphasis</em>" in units[0].src_html
        assert "<strong>bold</strong>" in units[0].src_html
        assert '<a href="link">link</a>' in units[0].tgt_html

    def test_alignment_unit_structure(self):
        """Test that AlignmentUnit has correct structure."""
        src_paras = ["<p>Source</p>"]
        tgt_paras = ["<p>Target</p>"]

        units = align_one_to_one(src_paras, tgt_paras)
        unit = units[0]

        assert hasattr(unit, "src_html")
        assert hasattr(unit, "tgt_html")
        assert isinstance(unit.src_html, str)
        assert isinstance(unit.tgt_html, str)
