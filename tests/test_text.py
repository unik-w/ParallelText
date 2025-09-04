"""Tests for text segmentation functionality."""

import pytest
from paralleltext.text.segment import paragraphs_from_xhtml


class TestTextSegmentation:
    """Test text segmentation functionality."""

    def test_paragraphs_from_simple_html(self):
        """Test extracting paragraphs from simple HTML."""
        html = """
        <html>
            <body>
                <p>First paragraph.</p>
                <p>Second paragraph.</p>
            </body>
        </html>
        """

        paragraphs = paragraphs_from_xhtml(html)
        assert len(paragraphs) == 2
        assert "<p>First paragraph.</p>" in paragraphs[0]
        assert "<p>Second paragraph.</p>" in paragraphs[1]

    def test_paragraphs_from_list_items(self):
        """Test extracting paragraphs from list items."""
        html = """
        <html>
            <body>
                <ul>
                    <li>First item</li>
                    <li>Second item</li>
                </ul>
            </body>
        </html>
        """

        paragraphs = paragraphs_from_xhtml(html)
        assert len(paragraphs) == 2
        assert "First item" in paragraphs[0]
        assert "Second item" in paragraphs[1]

    def test_paragraphs_filters_scripts_and_styles(self):
        """Test that scripts and styles are filtered out."""
        html = """
        <html>
            <head>
                <style>body { color: red; }</style>
            </head>
            <body>
                <p>Visible paragraph.</p>
                <script>alert('hidden');</script>
                <p>Another paragraph.</p>
            </body>
        </html>
        """

        paragraphs = paragraphs_from_xhtml(html)
        assert len(paragraphs) == 2

        # Scripts and styles should not appear in results
        combined_text = " ".join(paragraphs)
        assert "color: red" not in combined_text
        assert "alert" not in combined_text
        assert "Visible paragraph" in combined_text
        assert "Another paragraph" in combined_text

    def test_paragraphs_fallback_to_br_splitting(self):
        """Test fallback to BR splitting when no P or LI tags."""
        html = """
        <html>
            <body>
                First line<br><br>
                Second line<br><br>
                Third line
            </body>
        </html>
        """

        paragraphs = paragraphs_from_xhtml(html)
        assert len(paragraphs) >= 2  # Should split on double breaks

    def test_paragraphs_empty_html(self):
        """Test handling empty HTML."""
        html = "<html><body></body></html>"
        paragraphs = paragraphs_from_xhtml(html)
        assert isinstance(paragraphs, list)

    def test_paragraphs_no_content(self):
        """Test handling HTML with no paragraph content."""
        html = """
        <html>
            <body>
                <div>Some text but no paragraphs</div>
            </body>
        </html>
        """

        paragraphs = paragraphs_from_xhtml(html)
        # Should return list (may be empty or use fallback)
        assert isinstance(paragraphs, list)

    def test_paragraphs_mixed_content(self):
        """Test extracting paragraphs from mixed content."""
        html = """
        <html>
            <body>
                <h1>Title</h1>
                <p>First paragraph with <em>emphasis</em>.</p>
                <div>
                    <p>Nested paragraph with <strong>bold</strong> text.</p>
                </div>
                <ul>
                    <li>List item one</li>
                    <li>List item two</li>
                </ul>
                <p>Final paragraph.</p>
            </body>
        </html>
        """

        paragraphs = paragraphs_from_xhtml(html)
        assert len(paragraphs) >= 4  # At least 3 p tags + 2 li tags

        # Should preserve inline markup
        combined = " ".join(paragraphs)
        assert "<em>emphasis</em>" in combined
        assert "<strong>bold</strong>" in combined

    def test_paragraphs_preserves_inline_markup(self):
        """Test that inline markup is preserved."""
        html = """
        <html>
            <body>
                <p>Text with <a href="link">link</a> and <span class="special">span</span>.</p>
            </body>
        </html>
        """

        paragraphs = paragraphs_from_xhtml(html)
        assert len(paragraphs) == 1

        paragraph = paragraphs[0]
        assert '<a href="link">link</a>' in paragraph
        assert '<span class="special">span</span>' in paragraph

    def test_paragraphs_handles_malformed_html(self):
        """Test handling of malformed HTML."""
        html = "<p>Unclosed paragraph<p>Another paragraph</p>"

        paragraphs = paragraphs_from_xhtml(html)
        # Should still return a list and not crash
        assert isinstance(paragraphs, list)
        assert len(paragraphs) >= 1
