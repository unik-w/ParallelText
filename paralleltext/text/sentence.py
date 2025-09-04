"""Sentence-level text segmentation for parallel text alignment."""

import re
from typing import List

from bs4 import BeautifulSoup


def sentences_from_paragraph(paragraph_html: str) -> List[str]:
    """Split a paragraph into individual sentences.

    Args:
        paragraph_html: HTML paragraph content to split

    Returns:
        List of sentence HTML strings
    """
    soup = BeautifulSoup(paragraph_html, "html.parser")

    # Handle various HTML elements, not just <p>
    element = soup.find(["p", "li"])
    if not element:
        return [paragraph_html]

    # Get the text content for sentence splitting
    text = element.get_text()

    # Handle empty or whitespace-only content
    if not text.strip():
        return []

    # Common abbreviations that should not trigger sentence breaks
    abbreviations = {
        "Mr",
        "Mrs",
        "Ms",
        "Dr",
        "Prof",
        "Sr",
        "Jr",
        "St",
        "Ave",
        "Rd",
        "Blvd",
        "Co",
        "Corp",
        "Inc",
        "Ltd",
        "vs",
        "etc",
        "i.e",
        "e.g",
        "cf",
        "al",
        "z.B",
        "ca",
        "bzw",
        "usw",
        "vgl",  # German abbreviations
    }

    # Find potential sentence boundaries
    sentence_ends = []
    for match in re.finditer(r"[.!?]\s+[A-ZÄÖÜ]", text):
        # Check if this is after an abbreviation
        period_pos = match.start()  # Position of the period
        start_pos = max(0, period_pos - 20)  # Look back up to 20 chars
        preceding_text = text[start_pos : period_pos + 1]  # Include the period

        # Check if preceded by number + period (like "1. ")
        if re.search(r"\d\.$", preceding_text):
            continue

        # Check if preceded by abbreviation + period
        is_abbreviation = False
        for abbr in abbreviations:
            if preceding_text.endswith(abbr + "."):
                is_abbreviation = True
                break

        if not is_abbreviation:
            # This is a real sentence boundary
            sentence_ends.append(period_pos + 1)  # After the punctuation

    if not sentence_ends:
        return [paragraph_html]

    # Split text at sentence boundaries
    sentence_texts = []
    start = 0
    for end_pos in sentence_ends:
        sentence_texts.append(text[start:end_pos].strip())
        start = end_pos

    # Add the last sentence
    last_sentence = text[start:].strip()
    if last_sentence:
        sentence_texts.append(last_sentence)

    # Filter out empty sentences
    sentence_texts = [s for s in sentence_texts if s]

    if len(sentence_texts) <= 1:
        return [paragraph_html]

    # Build sentence HTML by preserving the original structure
    sentences = []
    original_tag = element.name
    attrs = element.attrs

    for sentence_text in sentence_texts:
        if sentence_text:
            # Create new element with the sentence text
            new_soup = BeautifulSoup("", "html.parser")
            new_element = new_soup.new_tag(original_tag, **attrs)
            new_element.string = sentence_text
            new_soup.append(new_element)
            sentences.append(str(new_soup))

    return sentences


def sentences_from_xhtml(xhtml: str) -> List[str]:
    """Extract all sentences from XHTML content.

    Args:
        xhtml: XHTML content to process

    Returns:
        List of sentence HTML strings
    """
    from .segment import paragraphs_from_xhtml

    paragraphs = paragraphs_from_xhtml(xhtml)
    sentences = []

    for para in paragraphs:
        sentences.extend(sentences_from_paragraph(para))

    return sentences
