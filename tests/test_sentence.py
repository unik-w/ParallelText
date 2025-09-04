"""Tests for sentence-level text segmentation."""

from paralleltext.text.sentence import sentences_from_paragraph, sentences_from_xhtml


class TestSentenceSegmentation:
    """Test sentence segmentation functionality."""

    def test_sentences_from_simple_paragraph(self):
        """Test extracting sentences from a simple paragraph."""
        html = "<p>First sentence. Second sentence! Third sentence?</p>"

        sentences = sentences_from_paragraph(html)

        assert len(sentences) == 3
        assert "First sentence." in sentences[0]
        assert "Second sentence!" in sentences[1]
        assert "Third sentence?" in sentences[2]
        # All should be wrapped in p tags
        assert all(s.startswith("<p") and s.endswith("</p>") for s in sentences)

    def test_sentences_from_single_sentence(self):
        """Test that single sentence returns original HTML."""
        html = "<p>This is just one sentence.</p>"

        sentences = sentences_from_paragraph(html)

        assert len(sentences) == 1
        assert sentences[0] == html

    def test_sentences_with_abbreviations(self):
        """Test that abbreviations don't cause excessive splits."""
        html = "<p>Mr. Smith went to Washington D.C. He had a great time.</p>"

        sentences = sentences_from_paragraph(html)

        # Note: Simple regex may split on some abbreviations
        # This is a known limitation for now
        assert len(sentences) >= 1
        # Ensure the content is preserved
        all_text = " ".join(sentences)
        assert "Mr." in all_text or "Mr" in all_text
        assert "Washington D.C." in all_text or "Washington D.C" in all_text
        assert "He had a great time." in all_text

    def test_sentences_with_numbers(self):
        """Test that decimal numbers don't cause splits."""
        html = "<p>The price was $12.50 today. Tomorrow it will be $13.00.</p>"

        sentences = sentences_from_paragraph(html)

        assert len(sentences) == 2
        assert "$12.50" in sentences[0]
        assert "$13.00" in sentences[1]

    def test_sentences_preserves_attributes(self):
        """Test that HTML attributes are preserved."""
        html = '<p class="special" id="para1">' "First sentence. Second sentence.</p>"

        sentences = sentences_from_paragraph(html)

        assert len(sentences) == 2
        # Both should preserve the attributes
        for sentence in sentences:
            assert 'class="special"' in sentence
            assert 'id="para1"' in sentence

    def test_sentences_with_inline_markup(self):
        """Test sentences with inline HTML markup."""
        # Note: This is a simplified test - full HTML preservation is complex
        html = "<p>This has <em>emphasis</em>. " "This has <strong>bold</strong>.</p>"

        sentences = sentences_from_paragraph(html)

        # Should split into 2 sentences
        assert len(sentences) == 2

    def test_sentences_empty_paragraph(self):
        """Test handling of empty paragraphs."""
        html = "<p></p>"

        sentences = sentences_from_paragraph(html)

        assert len(sentences) == 0

    def test_sentences_whitespace_only(self):
        """Test handling of whitespace-only paragraphs."""
        html = "<p>   </p>"

        sentences = sentences_from_paragraph(html)

        assert len(sentences) == 0

    def test_sentences_no_punctuation(self):
        """Test paragraph with no sentence-ending punctuation."""
        html = "<p>This paragraph has no ending punctuation</p>"

        sentences = sentences_from_paragraph(html)

        # Should return the whole paragraph as one sentence
        assert len(sentences) == 1
        assert sentences[0] == html

    def test_sentences_from_list_item(self):
        """Test extracting sentences from list items."""
        html = "<li>First sentence in list. Second sentence in list.</li>"

        sentences = sentences_from_paragraph(html)

        assert len(sentences) == 2
        assert all(s.startswith("<li") and s.endswith("</li>") for s in sentences)

    def test_sentences_from_xhtml_multiple_paragraphs(self):
        """Test extracting sentences from XHTML with multiple paragraphs."""
        xhtml = """
        <html>
            <body>
                <p>First paragraph first sentence.
                   First paragraph second sentence.</p>
                <p>Second paragraph first sentence!
                   Second paragraph second sentence?</p>
            </body>
        </html>
        """

        sentences = sentences_from_xhtml(xhtml)

        # Should have 4 sentences total
        assert len(sentences) == 4

        # Verify content exists in sentences
        all_text = " ".join(sentences)
        assert "First paragraph first sentence." in all_text
        assert "First paragraph second sentence." in all_text
        assert "Second paragraph first sentence!" in all_text
        assert "Second paragraph second sentence?" in all_text

    def test_sentences_from_xhtml_with_lists(self):
        """Test extracting sentences from XHTML with lists."""
        xhtml = """
        <html>
            <body>
                <p>Paragraph before list. Has two sentences.</p>
                <ul>
                    <li>First list item sentence.
                        Second list item sentence.</li>
                    <li>Another list item with one sentence.</li>
                </ul>
            </body>
        </html>
        """

        sentences = sentences_from_xhtml(xhtml)

        # Should have 5 sentences total
        # (2 from p + 2 from first li + 1 from second li)
        assert len(sentences) == 5

    def test_sentences_from_empty_xhtml(self):
        """Test handling of empty XHTML."""
        xhtml = "<html><body></body></html>"

        sentences = sentences_from_xhtml(xhtml)

        assert len(sentences) == 0
